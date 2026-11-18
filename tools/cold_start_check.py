#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Cold-start regression: put the device to sleep, then run every demo and flow.

The engine used to assume an already-awake device; a sleeping screen yields black frames
and the visual assertions fail for the wrong reason. This script makes that scenario the
default one.

  python tools/cold_start_check.py --serial <SN>
  python tools/cold_start_check.py --serial <SN> --rounds 2 --no-sleep
"""
import argparse
import os
import subprocess
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, ROOT)
from adbkit import adbkit as kit  # noqa: E402

ITEMS = [
    ("vision_demo", ["engine/vision_demo.py"]),
    ("ocr_tap_demo", ["engine/ocr_tap_demo.py"]),
    ("vision_match_demo", ["engine/vision_match_demo.py"]),
    ("canvas-visual", ["engine/engine.py", "engine/flows/canvas-visual.json"]),
    ("canvas-ocr", ["engine/engine.py", "engine/flows/canvas-ocr.json"]),
    ("settings-demo", ["engine/engine.py", "engine/flows/settings-demo.json"]),
]


def run_item(script, serial):
    cmd = [sys.executable, os.path.join(ROOT, script[0])] + \
          [os.path.join(ROOT, a) if a.endswith(".json") else a for a in script[1:]] + \
          ["--serial", serial]
    p = subprocess.run(cmd, cwd=ROOT, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=300)
    out = (p.stdout + p.stderr).decode("utf-8", "replace").strip().splitlines()
    return p.returncode, (out[-1] if out else "")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--serial")
    ap.add_argument("--adb")
    ap.add_argument("--rounds", type=int, default=1)
    ap.add_argument("--no-sleep", action="store_true", help="不主动休眠（只跑一遍）")
    args = ap.parse_args()

    adb = kit.resolve_adb(args.adb)
    serial = kit.pick_device(adb, args.serial)
    if not serial:
        print("没有设备")
        return 2

    failures = 0
    for r in range(1, args.rounds + 1):
        if not args.no_sleep:
            kit.adb_shell(adb, serial, "input keyevent KEYCODE_SLEEP", timeout=10)
            time.sleep(1.5)
            rc, out, _ = kit.adb_shell(adb, serial, "dumpsys power | grep mWakefulness=", timeout=10)
            slept = "Asleep" in (out or "")
            print("round %d: device asleep=%s" % (r, slept))
        else:
            print("round %d: (no sleep)" % r)
        for name, script in ITEMS:
            t0 = time.time()
            code, tail = run_item(script, serial)
            dt = time.time() - t0
            status = "PASS" if code == 0 else "FAIL"
            print("  %-20s %-4s %5.1fs" % (name, status, dt))
            if code != 0:
                failures += 1
                print("      " + tail[:140])
    print("\n冷启动回归: %s" % ("全部通过" if failures == 0 else "失败 %d 项" % failures))
    return 0 if failures == 0 else 1


if __name__ == "__main__":
    sys.exit(main())