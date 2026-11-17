#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
视觉闭环 demo（Canvas 页面，零无障碍节点）：

  1. 截图 → 找出 A/B/C/D 四个圆钮的位置
  2. 判断哪个是"选中态"（蓝色）
  3. 用几何坐标点击一个未选中的钮
  4. 再截图 → 确认"选中态"确实转移了

这是"动作可寻址 + 可验证"的最小证明：全程不读无障碍树。
"""
import os
import subprocess
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import vision  # noqa: E402
import re  # noqa: E402
SAFE_COMPONENT = re.compile(r"^[A-Za-z0-9_.]+/[A-Za-z0-9_.$]+$")  # 防止把任意字符串拼进 adb shell

ADB = None
SERIAL = None


def capture(path):
    args = [ADB] + (["-s", SERIAL] if SERIAL else []) + ["exec-out", "screencap", "-p"]
    out = subprocess.run(args, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=60)
    if out.returncode != 0 or not out.stdout:
        return False
    with open(path, "wb") as f:
        f.write(out.stdout)
    return True


def tap(x, y):
    args = [ADB] + (["-s", SERIAL] if SERIAL else []) + ["shell", "input", "tap", str(x), str(y)]
    return subprocess.run(args, stdout=subprocess.PIPE, timeout=30).returncode == 0


def main():
    global ADB, SERIAL
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--serial")
    ap.add_argument("--adb")
    ap.add_argument("--outdir", default=os.path.join(HERE, "data"))
    ap.add_argument("--dry-run", action="store_true", help="只定位不点击")
    ap.add_argument("--component", default="com.demo.canvas/.MainActivity",
                    help="先把目标页面切到前台（默认是可交互的自绘夹具）")
    args = ap.parse_args()
    if not SAFE_COMPONENT.match(args.component or ""):
        print("component 非法: %r" % args.component)
        return 6

    sys.path.insert(0, os.path.dirname(HERE))
    from adbkit import adbkit as ac
    ADB = ac.resolve_adb(args.adb)
    SERIAL = args.serial
    if not SERIAL:
        rc, out, _ = ac.sh([ADB, "devices"])
        for line in out.splitlines()[1:]:
            if "\tdevice" in line:
                SERIAL = line.split("\t")[0]
                break
    if not SERIAL:
        print("没有设备")
        return 2

    os.makedirs(args.outdir, exist_ok=True)
    # 先把目标页切到前台，否则截到的是当前随便什么界面
    if args.component:
        subprocess.run([ADB] + (["-s", SERIAL] if SERIAL else []) +
                       ["shell", "am start -n %s" % args.component],
                       stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=30)
        time.sleep(2.0)
    before = os.path.join(args.outdir, "vision-before.png")
    after = os.path.join(args.outdir, "vision-after.png")

    if not capture(before):
        print("截图失败")
        return 3
    blobs = vision.locate(before)
    print("1) 定位到 %d 个可点区域：" % len(blobs))
    for i, b in enumerate(blobs):
        print("   #%d (%d,%d) %dx%d selected=%s" % (i, b["cx"], b["cy"], b["w"], b["h"], b["selected"]))

    if len(blobs) < 2:
        print("候选不足，退出")
        return 4

    sel = [i for i, b in enumerate(blobs) if b["selected"]]
    target_idx = next((i for i in range(len(blobs)) if i not in sel), 0)
    target = blobs[target_idx]
    print("2) 当前选中: %s；准备点击 #%d (%d,%d)"
          % (sel or "无", target_idx, target["cx"], target["cy"]))

    if args.dry_run:
        print("3) dry-run：不点击")
        return 0

    tap(target["cx"], target["cy"])
    # 轮询等待"选中态真的转移"，不用固定 sleep（固定 0.8s 实测会偶发失败）
    sel2, tries = [], 0
    deadline = time.time() + 4.0
    while time.time() < deadline:
        tries += 1
        if capture(after):
            blobs2 = vision.locate(after)
            sel2 = [i for i, b in enumerate(blobs2) if b["selected"]]
            if sel2 == [target_idx]:
                break
        time.sleep(0.3)
    print("3) 点击后重定位: %d 个区域，选中=%s（轮询 %d 次）"
          % (len(blobs2) if 'blobs2' in dir() else 0, sel2, tries))

    ok = (sel2 == [target_idx])
    print("4) 选中态转移: %s" % ("成功 ✅" if ok else "失败 ❌（期望 %d）" % target_idx))
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())