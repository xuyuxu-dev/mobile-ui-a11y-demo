#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
指标基线：跑完采集后与 baseline.json 对比，漂移超过阈值就报警。
用途：换 ROM / 换设备 / 改了口径时，第一时间发现数字不对，而不是直接写进报告。
"""
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
TOL = 0.15  # 允许 15% 漂移


def totals(path):
    try:
        recs = [json.loads(l) for l in open(path, encoding="utf-8-sig") if l.strip()]
    except ValueError as e:
        print("数据集不是合法 JSONL：%s（%s）" % (path, e))
        return None
    m = [r["metrics"] for r in recs]
    g = lambda k: sum(x.get(k, 0) for x in m)
    ld = {}
    for x in m:
        for k, v in (x.get("label_dist") or {}).items():
            ld[k] = ld.get(k, 0) + int(v)
    row_labeled = sum(v for k, v in ld.items() if k not in ("0", "-1"))
    return {"pages": len(recs), "interactive": g("interactive"), "unlabeled": g("unlabeled"),
            "unlabeled_strict": g("unlabeled_strict"), "undersized": g("undersized"),
            "tiny": g("tiny"), "invisible": g("invisible"), "row_labeled": row_labeled,
            "no_interactive": sum(1 for x in m if x.get("no_interactive"))}


def main():
    data = sys.argv[1] if len(sys.argv) > 1 else os.path.join(ROOT, "data", "lint.jsonl")
    bpath = os.path.join(HERE, "baseline.json")
    if not os.path.isfile(bpath):
        print("缺少基线文件，跳过")
        return 0
    if not os.path.isfile(data):
        # 数据集是本地生成的（data/ 已 gitignore），干净克隆里不存在属正常
        print("无本地数据集，跳过基线比较")
        return 0
    cur = totals(data)
    if cur is None:
        return 2
    base = json.load(open(bpath, encoding="utf-8"))
    bad = 0
    for k, v in base.items():
        c = cur.get(k, 0)
        dev = abs(c - v) / max(1, v)
        # 小计数（如 tiny=5）用百分比会把 ±1 放大成 20%：至少允许 1 个单位的抖动
        slack = max(1, int(round(v * TOL)))
        flagged = abs(c - v) > slack
        if flagged:
            bad += 1
        print("%-14s baseline=%4d now=%4d dev=%5.1f%% slack=%d %s"
              % (k, v, c, dev * 100, slack, "DRIFT" if flagged else "OK"))
    print("\n%s" % ("基线一致" if bad == 0 else "漂移 %d 项（检查是否换了设备/改了口径）" % bad))
    return 0 if bad == 0 else 1


if __name__ == "__main__":
    sys.exit(main())