#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""离线自测：不接手机，用夹具验证文本定位与流程解析。"""
import json
import os
import sys
import xml.etree.ElementTree as ET

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
DEMO = os.path.dirname(ROOT)
sys.path.insert(0, DEMO)
sys.path.insert(0, ROOT)
import engine as eng  # noqa: E402


def main():
    fix = os.path.join(DEMO, "lint", "fixtures", "normal.xml")
    with open(fix, encoding="utf-8-sig") as f:
        root = ET.fromstring(f.read())
    cases = [("确定", True), ("返回", True), ("不存在XYZ", False)]
    bad = 0
    for text, expect in cases:
        node, b = eng.find_text(root, text)
        got = node is not None
        if got != expect:
            print("FAIL find_text(%r) expect=%s got=%s" % (text, expect, got))
            bad += 1
        else:
            print("ok   find_text(%r) -> %s" % (text, "找到" if got else "未找到"))
    # 纯函数：bounds 中心点（点击坐标的唯一来源）
    for bounds, want in [((0, 0, 100, 200), (50, 100)), ((10, 20, 11, 22), (10, 21))]:
        got = eng.bounds_center(bounds)
        if got != want:
            print("FAIL bounds_center(%r) want=%s got=%s" % (bounds, want, got))
            bad += 1
        else:
            print("ok   bounds_center(%r) -> %s" % (bounds, got))

    # 找到的文字必须带回包围盒（点击依赖它）
    node, b = eng.find_text(root, "确定")
    if node is None or not (isinstance(b, tuple) and len(b) == 4 and b[2] > b[0] and b[3] > b[1]):
        print("FAIL find_text(确定) 需要返回有效包围盒，got=%r" % (b,))
        bad += 1
    else:
        print("ok   find_text(确定) bounds=%r" % (b,))

    flow_path = os.path.join(ROOT, "flows", "settings-demo.json")
    with open(flow_path, encoding="utf-8-sig") as f:
        flow = json.load(f)
    for s in flow["steps"]:
        if "op" not in s:
            print("FAIL 步骤缺少 op: %r" % s)
            bad += 1
    print("\n%s" % ("全部通过" if bad == 0 else "失败 %d 项" % bad))
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())