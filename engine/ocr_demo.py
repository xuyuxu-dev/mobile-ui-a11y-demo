#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
OCR 通道演示：对一个**没有任何无障碍文字**的页面，读出上面写了什么。

判定：把 OCR 结果与已知关键词比对（这些词是页面固定内容），
      并报告耗时。
"""
import argparse
import os
import subprocess
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.dirname(HERE))
import re  # noqa: E402
import ocr  # noqa: E402
from adbkit import adbkit as kit  # noqa: E402

KEYWORDS = ["Canvas fixture", "tap any letter"]

# 防止把任意字符串拼进 adb shell（--component 来自命令行）
SAFE_COMPONENT = re.compile(r"^[A-Za-z0-9_.]+/[A-Za-z0-9_.$]+$")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--serial")
    ap.add_argument("--component", default="com.demo.canvas/.MainActivity")
    ap.add_argument("--outdir", default=os.path.join(HERE, "data"))
    args = ap.parse_args()
    if not SAFE_COMPONENT.match(args.component or ""):
        print("component 非法: %r" % args.component)
        return 6

    adb = kit.resolve_adb()
    serial = kit.pick_device(adb, args.serial)
    if not serial:
        print("没有设备")
        return 2
    os.makedirs(args.outdir, exist_ok=True)

    subprocess.run([adb, "-s", serial, "shell", "am start -n %s" % args.component],
                   stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=30)
    time.sleep(2.0)

    shot = os.path.join(args.outdir, "ocr-demo.png")
    t0 = time.time()
    if not kit.save_screencap(adb, serial, shot):
        print("截图失败")
        return 3
    t_shot = time.time() - t0

    t1 = time.time()
    raw, norm = ocr.ocr_image(shot)
    t_ocr = time.time() - t1
    if raw is None:
        print("OCR 失败:", norm)
        return 4

    print("1) 截图 %.0fms，OCR %.0fms" % (t_shot * 1000, t_ocr * 1000))
    print("2) 归一化文本（前 120 字）：")
    print("   " + norm[:120])
    hits = [k for k in KEYWORDS if ocr.contains(raw, k)]
    print("3) 关键词命中 %d/%d：%s" % (len(hits), len(KEYWORDS), hits))
    ok = len(hits) == len(KEYWORDS)
    print("4) %s" % ("通过 ✅" if ok else "失败 ❌"))
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())