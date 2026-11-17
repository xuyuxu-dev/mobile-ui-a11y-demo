#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""现场核查"行级判定后仍无标签"的控件：打印类名、dp 尺寸、层级、父容器有无文字（不打印文本）。"""
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

    print("%-22s %5s %5s %5s %-8s %s" % ("class", "w", "h", "depth", "labeled", "row_labeled"))
    found = 0
    for n in root.iter("node"):
        if not ac.is_interactive(n):
            continue
        if ac.has_label(n):
            continue
        if ac.row_labeled(n, parents):
            continue
        b = ac.parse_bounds(n.attrib.get("bounds"))
        w = abs(b[2] - b[0]) / ppd if b else 0
        h = abs(b[3] - b[1]) / ppd if b else 0
        print("%-22s %5.0f %5.0f %5d %-8s %s" % (
            (n.attrib.get("class") or "").split(".")[-1], w, h, depth(n), "no", "no"))
        found += 1
    print("\n严格无标签控件: %d" % found)
    return 0


if __name__ == "__main__":
    sys.exit(main())