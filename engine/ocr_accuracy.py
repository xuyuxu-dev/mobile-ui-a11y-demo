#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
OCR 召回率测量：用无障碍树里的文字当"标准答案"，看 OCR 能认出多少。

只记录**数量**，不落盘任何界面文本：
  对每个页面，取无障碍树里长度 >= 2 的文字串，逐条检查是否出现在 OCR 结果里。
"""
import argparse
import json
import os
import subprocess
import sys
import time
import xml.etree.ElementTree as ET

HERE = os.path.dirname(os.path.abspath(__file__))
DEMO = os.path.dirname(HERE)
sys.path.insert(0, HERE)
sys.path.insert(0, DEMO)
sys.path.insert(0, os.path.join(DEMO, "lint", "collectors"))
from adbkit import adbkit as kit  # noqa: E402
import ocr  # noqa: E402

PAGES = [
    ("设置主页", "android.settings.SETTINGS"),
    ("显示", "android.settings.DISPLAY_SETTINGS"),
    ("声音", "android.settings.SOUND_SETTINGS"),
    ("WiFi", "android.settings.WIFI_SETTINGS"),
    ("应用", "android.settings.APPLICATION_SETTINGS"),
    ("电池", "android.settings.BATTERY_SAVER_SETTINGS"),
    ("日期时间", "android.settings.DATE_SETTINGS"),
]


def texts_of(xml):
    """无障碍树里的文字串（>=2 字），去重。"""
    out = set()
    try:
        root = ET.fromstring(xml)
    except ET.ParseError:
        return out
    for n in root.iter("node"):
        for k in ("text", "content-desc"):
            v = (n.attrib.get(k) or "").strip()
            if len(v) >= 2:
                out.add(v)
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--serial")
    ap.add_argument("--out", default=os.path.join(HERE, "data", "ocr-accuracy.jsonl"))
    args = ap.parse_args()

    adb = kit.resolve_adb()
    serial = kit.pick_device(adb, args.serial)
    if not serial:
        print("没有设备")
        return 2
    os.makedirs(os.path.dirname(args.out), exist_ok=True)

    rows, total, hit = [], 0, 0
    for label, action in PAGES:
        subprocess.run([adb, "-s", serial, "shell", "am start -a %s" % action],
                       stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=30)
        time.sleep(2.5)
        xml, why = kit.dump_current(adb, serial)
        if not xml:
            print("SKIP %-8s %s" % (label, why))
            continue
        truth = texts_of(xml)
        if not truth:
            print("SKIP %-8s 无障碍树里没有文字" % label)
            continue

        shot = os.path.join(os.path.dirname(args.out), "ocr-acc.png")
        if not kit.save_screencap(adb, serial, shot):
            print("SKIP %-8s 截图失败" % label)
            continue
        raw, norm = ocr.ocr_image(shot)
        if raw is None:
            print("SKIP %-8s OCR 失败: %s" % (label, norm))
            continue

        seen = ocr.normalize(raw)
        hits = [t for t in truth if ocr.normalize(t) in seen]
        total += len(truth)
        hit += len(hits)
        rate = 100.0 * len(hits) / len(truth)
        rows.append({"page": label, "strings": len(truth), "hit": len(hits), "rate": round(rate, 1)})
        print("%-8s 标准答案 %2d 条，OCR 命中 %2d 条（%.0f%%）" % (label, len(truth), len(hits), rate))

    with open(args.out, "w", encoding="utf-8") as f:
        for r in rows:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
    if total:
        print("\n合计：%d 条文字串，命中 %d 条，召回率 %.1f%%" % (total, hit, 100.0 * hit / total))
    return 0


if __name__ == "__main__":
    sys.exit(main())