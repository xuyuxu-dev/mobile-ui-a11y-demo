#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Record real-device frames on the interactive canvas fixture.

Saves frames plus a taps.json sidecar (frame index, button index, x, y).
"""
import json
import os
import subprocess
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "engine"))
from adbkit import adbkit as kit  # noqa: E402
import vision  # noqa: E402

COMPONENT = "com.demo.canvas/.MainActivity"
OUTDIR = os.path.join(ROOT, "engine", "data", "rec")
SEQ = [0, 1, 2, 3, 2, 1, 0, 3]


def main():
    adb = kit.resolve_adb()
    serial = kit.pick_device(adb)
    if not serial:
        print("no device")
        return 2
    os.makedirs(OUTDIR, exist_ok=True)
    for f in os.listdir(OUTDIR):
        os.remove(os.path.join(OUTDIR, f))

    kit.adb_shell(adb, serial, "input keyevent KEYCODE_WAKEUP")
    time.sleep(0.6)
    kit.adb_shell(adb, serial, "input keyevent 82")
    time.sleep(0.4)
    kit.adb_shell(adb, serial, "am start -n %s" % COMPONENT)
    time.sleep(2.0)

    # warm-up: the first frame right after launch may miss freshly drawn content
    for _ in range(2):
        kit.save_screencap(adb, serial, os.path.join(OUTDIR, "_warm.png"))
        time.sleep(0.5)
    n = 0
    if not kit.save_screencap(adb, serial, os.path.join(OUTDIR, "frame-%02d.png" % n)):
        print("capture failed")
        return 3
    print("frame %02d initial" % n)
    n += 1

    taps = []
    for idx in SEQ:
        tmp = os.path.join(OUTDIR, "_locate.png")
        if not kit.save_screencap(adb, serial, tmp):
            continue
        blobs = vision.locate(tmp)
        if len(blobs) < 4:
            print("locate failed (%d)" % len(blobs))
            continue
        b = blobs[idx]
        kit.adb_shell(adb, serial, "input tap %d %d" % (b["cx"], b["cy"]))
        time.sleep(0.45)
        p = os.path.join(OUTDIR, "frame-%02d.png" % n)
        if kit.save_screencap(adb, serial, p):
            taps.append({"frame": n, "idx": idx, "x": b["cx"], "y": b["cy"]})
            print("frame %02d tap #%d (%d,%d)" % (n, idx, b["cx"], b["cy"]))
            n += 1
        time.sleep(0.12)

    tmp = os.path.join(OUTDIR, "_locate.png")
    if os.path.exists(tmp):
        os.remove(tmp)
    with open(os.path.join(OUTDIR, "taps.json"), "w", encoding="utf-8") as f:
        json.dump(taps, f, ensure_ascii=False, indent=2)
    print("%d frames recorded" % n)
    return 0


if __name__ == "__main__":
    sys.exit(main())