#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
模板匹配闭环：验证"选中态"这个视觉特征是否跟着点击移动。

  1. 截图，连通域找到 4 个按钮，取出"当前选中"那个当模板
  2. 点击另一个按钮
  3. 重新截图，用模板匹配找"选中样式"现在在哪
  4. 位置应该等于刚才点的那个按钮

与 vision_demo 的区别：那边依赖"蓝色"这个先验；这边只依赖"长相"，
所以理论上对任意外观的按钮都成立（图标、图片、不规则形状）。
"""
import argparse
import os
import subprocess
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.dirname(HERE))
import vision  # noqa: E402
import re  # noqa: E402
SAFE_COMPONENT = re.compile(r"^[A-Za-z0-9_.]+/[A-Za-z0-9_.$]+$")  # 防止把任意字符串拼进 adb shell
from adbkit import adbkit as kit  # noqa: E402


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

    before = os.path.join(args.outdir, "match-before.png")
    after = os.path.join(args.outdir, "match-after.png")
    tpl = os.path.join(args.outdir, "match-template.png")

    if not kit.save_screencap(adb, serial, before):
        print("截图失败")
        return 3
    blobs = vision.locate(before)
    sel = [i for i, b in enumerate(blobs) if b["selected"]]
    if not blobs or not sel:
        print("没定位到按钮或没有选中态")
        return 4
    src = blobs[sel[0]]
    vision.crop(before, src["x"], src["y"], src["w"], src["h"], tpl)
    print("1) 取『选中态』作模板：来自 #%d (%d,%d) %dx%d"
          % (sel[0], src["cx"], src["cy"], src["w"], src["h"]))

    target_idx = next((i for i in range(len(blobs)) if i not in sel), 0)
    tgt = blobs[target_idx]
    print("2) 点击 #%d (%d,%d)" % (target_idx, tgt["cx"], tgt["cy"]))
    subprocess.run([adb, "-s", serial, "shell", "input", "tap", str(tgt["cx"]), str(tgt["cy"])],
                   stdout=subprocess.PIPE, timeout=30)
    # 轮询等待画面变化（固定 sleep 在真机上偶发失败）
    ok_cap = False
    deadline = time.time() + 4.0
    while time.time() < deadline:
        if kit.save_screencap(adb, serial, after):
            ok_cap = True
            break
        time.sleep(0.3)
    if not ok_cap:
        print("第二次截图失败")
        return 3
    # 只比对圆环（忽略中间变化的字母）：模板中间被屏蔽，分值才稳定
    res = vision.match_template(after, tpl, mask_center=0.52)
    if not res:
        print("匹配失败")
        return 5
    print("3) 模板匹配：score=%.3f 位置=(%d,%d)" % (res["score"], res["x"], res["y"]))

    dist = ((res["x"] - tgt["cx"]) ** 2 + (res["y"] - tgt["cy"]) ** 2) ** 0.5
    ok = res["score"] >= 0.90 and dist <= 40
    print("4) 与点击位置距离 %.0fpx（阈值 40），得分阈值 0.90 → %s"
          % (dist, "通过 ✅" if ok else "失败 ❌"))
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())