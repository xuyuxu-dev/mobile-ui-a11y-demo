#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
"点击区过小"的现场核查：列出当前页面最小的若干个可交互节点（只打印类名与 dp 尺寸，不打印文本）。
用途：确认 21% 的"过小"是真实缺陷，还是裁剪/测量误差。
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
    rows = []
    for n in root.iter("node"):
        if not ac.is_interactive(n):
            continue
        b = ac.parse_bounds(n.attrib.get("bounds"))
        if not b:
            continue
        w = abs(b[2] - b[0]) / ppd
        h = abs(b[3] - b[1]) / ppd
        if w == 0 or h == 0:
            continue
        rows.append((min(w, h), w, h, (n.attrib.get("class") or "").split(".")[-1], ac.has_label(n)))
    rows.sort()
    print("density=%.0f  interactive=%d  最小 8 个：" % (density, len(rows)))
    print("%-24s %6s %6s %-8s %s" % ("class", "w(dp)", "h(dp)", "labeled", "verdict"))
    for mn, w, h, cls, lab in rows[:8]:
        verdict = "OK" if mn >= 48 else ("过小" if mn >= 24 else "极小")
        print("%-24s %6.1f %6.1f %-8s %s" % (cls, w, h, "yes" if lab else "no", verdict))
    small = [r for r in rows if r[0] < 48]
    print("\n< 48dp: %d / %d (%.0f%%)" % (len(small), len(rows), 100.0 * len(small) / max(1, len(rows))))
    tiny = [r for r in small if r[0] < 24]
    print("< 24dp: %d（这些基本是图标内边距/装饰，应人工复核）" % len(tiny))
    return 0


if __name__ == "__main__":
    sys.exit(main())