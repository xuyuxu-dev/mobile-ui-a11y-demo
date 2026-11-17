#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""离线自测：不接手机，用夹具验证指标口径（含标签距离）。CI 里跑这个。"""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(ROOT, "collectors"))
import adb_collect as ac  # noqa: E402

FIX = os.path.join(ROOT, "fixtures")

# 文件名 -> 期望（density 固定 480，即 1dp=3px）
CASES = [
    # normal：Button 自带文字(d0)、EditText 靠祖先(d1)、ImageButton 自带 desc(d0)
    ("normal.xml", dict(nodes=5, interactive=3, unlabeled=0,
                        undersized=2, zero_node_page=False, no_interactive=False,
                        dist={"0": 2, "1": 1})),
    # canvas：整页只有一个自绘容器
    ("canvas.xml", dict(nodes=1, interactive=0, unlabeled=0,
                        undersized=0, zero_node_page=True, no_interactive=True,
                        dist={})),
    # webview：3 张图 + 按钮 + 容器，其中图片与容器靠祖先 "提交" 取得标签(d1)
    ("webview.xml", dict(nodes=6, interactive=5, unlabeled=0,
                         undersized=4, zero_node_page=False, no_interactive=False,
                         dist={"0": 1, "1": 4})),
    # orphan：祖先链上没有任何文字 → 距离 -1，计入 unlabeled
    ("orphan.xml", dict(nodes=4, interactive=2, unlabeled=2,
                        undersized=1, zero_node_page=False, no_interactive=False,
                        dist={"-1": 2})),   # ImageView 140px=46.7dp < 48dp
]


def main():
    failed = 0
    for name, want in CASES:
        with open(os.path.join(FIX, name), "r", encoding="utf-8-sig") as f:
            xml = f.read()
        got = ac.parse_dump(xml, 480.0)["metrics"]
        checks = {k: v for k, v in want.items() if k != "dist"}
        for k, v in checks.items():
            if got.get(k) != v:
                print("FAIL %-12s %-14s want=%s got=%s" % (name, k, v, got.get(k)))
                failed += 1
        if "dist" in want:
            d = {k: int(v) for k, v in (got.get("label_dist") or {}).items() if int(v) > 0}
            if d != want["dist"]:
                print("FAIL %-12s label_dist want=%s got=%s" % (name, want["dist"], d))
                failed += 1
        if failed == 0:
            print("ok   %-12s %s" % (name, got))
    print("\n%s" % ("全部通过" if failed == 0 else "失败 %d 项" % failed))
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())