#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
第二个实验：dump 的"语义"和"成本"

1) 标准 dump vs dump --compressed：compressed 会裁掉"非重要"节点。
   两者差多少，就是 dump 自身已经过滤掉的比例 —— 也就是说，读到的树已经是简化过的。
2) 记录每次 dump 的耗时与节点数，给出吞吐模型（扫 N 页要多久）。
"""
import json
import os
import subprocess
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(ROOT, "collectors"))
import adb_collect as ac  # noqa: E402


def dump_with(adb, serial, compressed):
    flag = " -c" if compressed else ""
    t0 = time.time()
    rc, out, _ = ac.adb_shell(adb, serial, "uiautomator dump%s /sdcard/lint_dq.xml" % flag, timeout=60)
    dt = time.time() - t0
    if rc != 0 or "dumped to" not in out:
        return None, dt
    args = [adb] + (["-s", serial] if serial else []) + ["shell", "cat /sdcard/lint_dq.xml"]
    rc2, xml, _ = ac.sh(args, timeout=60)
    if rc2 != 0 or "<hierarchy" not in xml:
        return None, dt
    return xml, dt


def main():
    adb = ac.resolve_adb(None)
    serial = sys.argv[1] if len(sys.argv) > 1 else os.environ.get("ANDROID_SERIAL", "")
    with open(os.path.join(ROOT, "collectors", "pages.json"), "r", encoding="utf-8-sig") as f:
        pages = [p for p in json.load(f)["pages"] if p.get("action")][:6]
    density = ac.get_density(adb, serial)

    rows = []
    for item in pages:
        ac.adb_shell(adb, serial, "am start -a %s" % item["action"])
        time.sleep(2.5)
        xml_n, t_n = dump_with(adb, serial, False)
        xml_c, t_c = dump_with(adb, serial, True)
        if not xml_n or not xml_c:
            print("SKIP %s" % item["label"])
            continue
        mn = ac.parse_dump(xml_n, density)["metrics"]
        mc = ac.parse_dump(xml_c, density)["metrics"]
        rows.append(dict(label=item["label"], nodes=mn["nodes"], comp_nodes=mc["nodes"],
                         inter=mn["interactive"], comp_inter=mc["interactive"],
                         t=t_n * 1000, t_c=t_c * 1000))
        print("%-12s nodes=%3d -> %3d (%+.0f%%)  interactive=%2d -> %2d  %.0fms / %.0fms"
              % (item["label"], mn["nodes"], mc["nodes"],
                 100.0 * (mc["nodes"] - mn["nodes"]) / max(1, mn["nodes"]),
                 mn["interactive"], mc["interactive"], t_n * 1000, t_c * 1000))

    if rows:
        print("\n== 汇总 ==")
        n = sum(r["nodes"] for r in rows)
        c = sum(r["comp_nodes"] for r in rows)
        print("节点总数 %d -> compressed %d（少 %.1f%%）" % (n, c, 100.0 * (n - c) / max(1, n)))
        print("平均耗时 %.0fms/页（compressed %.0fms）"
              % (sum(r["t"] for r in rows) / len(rows), sum(r["t_c"] for r in rows) / len(rows)))
        print("吞吐：%.0f 页/分钟" % (60000.0 / (sum(r["t"] for r in rows) / len(rows))))
    return 0


if __name__ == "__main__":
    sys.exit(main())