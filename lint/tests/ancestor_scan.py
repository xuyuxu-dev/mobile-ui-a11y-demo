#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
定性工具：对"严格无标签"的控件，向上最多 4 级扫描祖先子树里有没有文字，
回答一个问题——它到底是"真无标签"，还是"标签在更外层"。

打印：类名 / dp 尺寸 / 层级 / 最近有文字的祖先层级（不含文本内容）
"""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(ROOT, "collectors"))
import adb_collect as ac  # noqa: E402
import xml.etree.ElementTree as ET  # noqa: E402


def main():
    adb = ac.resolve_adb(None)
    serial = sys.argv[1] if len(sys.argv) > 1 else os.environ.get("ANDROID_SERIAL", "")
    density = ac.get_density(adb, serial)
    ppd = density / 160.0
    xml_text, why = ac.dump_current(adb, serial)
    if not xml_text:
        print(why)
        return 2
    root = ET.fromstring(xml_text)
    parents = ac.build_parents(root)

    def depth(n):
        d, cur = 0, n
        while cur in parents:
            cur = parents[cur]
            d += 1
        return d

    def first_text_ancestor(n, max_levels=4):
        cur = n
        for lv in range(1, max_levels + 1):
            p = parents.get(cur)
            if p is None:
                return -1
            for d in p.iter("node"):
                if d is n or d is cur:
                    continue
                b = d.attrib
                if (b.get("text") or "").strip() or (b.get("content-desc") or "").strip():
                    return lv
            cur = p
        return -1

    print("%-20s %5s %5s %5s %s" % ("class", "w", "h", "depth", "text_ancestor_level"))
    n_found = 0
    for n in root.iter("node"):
        if not ac.is_interactive(n):
            continue
        b = ac.parse_bounds(n.attrib.get("bounds"))
        if b and (abs(b[2] - b[0]) == 0 or abs(b[3] - b[1]) == 0):
            continue
        if ac.has_label(n) or ac.row_labeled(n, parents):
            continue
        w = abs(b[2] - b[0]) / ppd if b else 0
        h = abs(b[3] - b[1]) / ppd if b else 0
        lv = first_text_ancestor(n)
        print("%-20s %5.0f %5.0f %5d %s" % (
            (n.attrib.get("class") or "").split(".")[-1], w, h, depth(n),
            ("无（4 级内都没有文字）" if lv < 0 else "第 %d 级祖先有文字" % lv)))
        n_found += 1
    print("\n严格无标签: %d" % n_found)
    return 0


if __name__ == "__main__":
    sys.exit(main())