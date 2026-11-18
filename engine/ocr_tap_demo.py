#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
三通道联动：OCR 找文字位置 → 点击 → 视觉验证状态。

页面：com.demo.canvas（整页自绘，无障碍树里没有文字）
  1. 截图 OCR，找到字母 "C" 的包围盒
  2. 点击它的中心
  3. 再截图，用视觉定位判断"选中态"是否落在第 3 个按钮上
"""
import argparse
import os
import subprocess
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.dirname(HERE))
import ocr  # noqa: E402
import vision  # noqa: E402
import re  # noqa: E402
SAFE_COMPONENT = re.compile(r"^[A-Za-z0-9_.]+/[A-Za-z0-9_.$]+$")  # 防止把任意字符串拼进 adb shell
from adbkit import adbkit as kit  # noqa: E402
import uiauto  # noqa: E402

TARGET = "C"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--serial")
    ap.add_argument("--component", default="com.demo.canvas/.MainActivity")
    ap.add_argument("--outdir", default=os.path.join(HERE, "data"))
    ap.add_argument("--dry-run", action="store_true")
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

    pkg = args.component.split('/')[0]
    # 启动后确认前台真的切过去了；系统弹窗会抢前台
    focus = uiauto.launch_component(adb, serial, args.component)
    if not focus.startswith(pkg):
        focus = uiauto.ensure_foreground(adb, serial, pkg)
    if not focus.startswith(pkg):
        print('前台不是 %s（当前 %s），可能有系统弹窗遮挡' % (pkg, focus))
        return 5
    before = os.path.join(args.outdir, "ocr-tap-before.png")
    after = os.path.join(args.outdir, "ocr-tap-after.png")
    if not kit.save_screencap(adb, serial, before):
        print("截图失败")
        return 3

    lang, words = ocr.ocr_words(before)
    if words is None:
        print("OCR 失败:", lang)
        return 4
    target = ocr.find_word(words, TARGET, fuzzy=True)
    if not target:
        print("OCR 没找到「%s」；识别到的词: %s" % (TARGET, [w["text"] for w in words]))
        return 5
    cx, cy = target["x"] + target["w"] // 2, target["y"] + target["h"] // 2
    print("1) OCR 找到「%s」：包围盒 (%d,%d,%d,%d)，中心 (%d,%d)"
          % (target["text"], target["x"], target["y"], target["w"], target["h"], cx, cy))

    if args.dry_run:
        print("2) dry-run：不点击")
        return 0
    subprocess.run([adb, "-s", serial, "shell", "input", "tap", str(cx), str(cy)],
                   stdout=subprocess.PIPE, timeout=30)
    print("2) 已点击 (%d,%d)" % (cx, cy))

    # 视觉验证：选中态应该转移到第 3 个按钮（索引 2）
    ok, sel, tries = False, [], 0
    deadline = time.time() + 4.0
    while time.time() < deadline:
        tries += 1
        if kit.save_screencap(adb, serial, after):
            blobs = vision.locate(after)
            sel = [i for i, b in enumerate(blobs) if b["selected"]]
            if sel == [2]:
                ok = True
                break
        time.sleep(0.3)
    print("3) 视觉验证：选中态=%s（轮询 %d 次，期望 [2]）" % (sel, tries))
    print("4) %s" % ("通过 ✅" if ok else "失败 ❌"))
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())