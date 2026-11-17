#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
M1.5 实验：`uiautomator dump` 作为数据源，本身靠谱吗？

测三件事（同一页面连续采 N 次）：
  1. 节点数 / 可交互数是否稳定（抖动 = 指标噪声）
  2. 有多少零尺寸节点（隐藏节点混进来会污染"点击区过小"）
  3. 单次 dump 耗时（决定能不能批量扫几百页）

用法：python tests/stability.py --serial <SN> [--n 10]
"""
import argparse
import os
import statistics
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(ROOT, "collectors"))

import adb_collect as ac  # noqa: E402


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--serial")
    ap.add_argument("--adb")
    ap.add_argument("--n", type=int, default=10)
    args = ap.parse_args()

    adb = ac.resolve_adb(args.adb)
    serial = args.serial
    if not serial:
        rc, out, _ = ac.sh([adb, "devices"])
        for line in out.splitlines()[1:]:
            if "\tdevice" in line:
                serial = line.split("\t")[0]
                break
    if not serial:
        print("没有设备", file=sys.stderr)
        return 2

    density = ac.get_density(adb, serial)
    nodes, inter, invis, cost = [], [], [], []
    for i in range(args.n):
        t0 = time.time()
        xml_text, why = ac.dump_current(adb, serial)
        dt = time.time() - t0
        if not xml_text:
            print("第 %d 次失败: %s" % (i + 1, why), file=sys.stderr)
            continue
        r = ac.parse_dump(xml_text, density)["metrics"]
        nodes.append(r["nodes"])
        inter.append(r["interactive"])
        invis.append(r.get("invisible", 0))
        cost.append(dt)
        print("  #%02d nodes=%d interactive=%d invisible=%d %.0fms"
              % (i + 1, r["nodes"], r["interactive"], r.get("invisible", 0), dt * 1000))

    if not nodes:
        return 3

    def stat(v):
        return (min(v), max(v), statistics.mean(v),
                (statistics.pstdev(v) if len(v) > 1 else 0.0))

    print("\n== 结果 ==")
    for name, v in (("nodes", nodes), ("interactive", inter), ("invisible", invis)):
        mn, mx, mean, sd = stat(v)
        print("%-12s min=%d max=%d mean=%.1f sd=%.2f  抖动=%.1f%%"
              % (name, mn, mx, mean, sd, (100.0 * (mx - mn) / mean) if mean else 0))
    print("dump 耗时   mean=%.0fms max=%.0fms" % (statistics.mean(cost) * 1000, max(cost) * 1000))
    print("\n结论要点：")
    print("- 若 nodes 抖动 > 5%%，说明单次采样不可比，必须固定等待或多次取中位数")
    print("- invisible > 0 说明树里含隐藏节点，指标必须把它们与'过小'分开")
    return 0


if __name__ == "__main__":
    sys.exit(main())