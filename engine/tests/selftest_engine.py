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