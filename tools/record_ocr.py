#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Record an OCR-driven tap on the fixture: screenshot -> OCR boxes -> tap -> verify."""
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
import ocr  # noqa: E402
import vision  # noqa: E402

COMPONENT = "com.demo.canvas/.MainActivity"
OUT = os.path.join(ROOT, "engine", "data", "ocr-rec")


def main():
    adb = kit.resolve_adb()
    serial = kit.pick_device(adb)
    if not serial:
        print("no device")
        return 2
    os.makedirs(OUT, exist_ok=True)
    for f in os.listdir(OUT):
        os.remove(os.path.join(OUT, f))

    kit.adb_shell(adb, serial, "input keyevent KEYCODE_WAKEUP")
    time.sleep(0.5)
    kit.adb_shell(adb, serial, "am start -n %s" % COMPONENT)
    time.sleep(2.0)
    for _ in range(2):
        kit.save_screencap(adb, serial, os.path.join(OUT, "_warm.png"))
        time.sleep(0.4)

    before = os.path.join(OUT, "stage-0.png")
    kit.save_screencap(adb, serial, before)
    sel = [i for i, b in enumerate(vision.locate(before)) if b["selected"]]

    lang, words = ocr.ocr_words(before)
    if words is None:
        print("ocr failed: %s" % lang)
        return 3
    letters = [w for w in words if w["text"].strip().upper() in "ABCD"]
    letters.sort(key=lambda w: w["x"])
    target = None
    for w in letters:
        idx = "ABCD".index(w["text"].strip().upper())
        if not sel or idx != sel[0]:
            target = (idx, w)
            break
    if not target:
        print("no ocr letter to tap (letters=%d)" % len(letters))
        return 4

    idx, w = target
    cx = w["x"] + w["w"] // 2
    cy = w["y"] + w["h"] // 2
    kit.adb_shell(adb, serial, "input tap %d %d" % (cx, cy))
    time.sleep(0.6)
    after = os.path.join(OUT, "stage-2.png")
    kit.save_screencap(adb, serial, after)

    meta = {
        "letters": [{"text": w["text"], "x": w["x"], "y": w["y"], "w": w["w"], "h": w["h"]} for w in letters],
        "tap": {"idx": idx, "x": cx, "y": cy, "text": w["text"]},
        "selected_before": sel,
        "selected_after": [i for i, b in enumerate(vision.locate(after)) if b["selected"]],
    }
    with open(os.path.join(OUT, "meta.json"), "w", encoding="utf-8") as f:
        json.dump(meta, f, ensure_ascii=False, indent=2)
    print("ocr letters=%d tap=%s(%d,%d) before=%s after=%s"
          % (len(letters), w["text"], cx, cy, sel, meta["selected_after"]))
    return 0


if __name__ == "__main__":
    sys.exit(main())