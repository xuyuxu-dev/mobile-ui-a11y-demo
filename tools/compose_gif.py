#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Compose the hero GIF: frames + detected boxes + tap indicator + adb command."""
import json
import os
import sys

from PIL import Image, ImageDraw, ImageFont

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(ROOT, "engine"))
import vision  # noqa: E402

REC = os.path.join(ROOT, "engine", "data", "rec")
OUT = os.path.join(ROOT, "docs", "assets", "demo.gif")
WIDTH = 380
CROP_TOP = 104
BOTTOM = 52
FONTS = [r"C:\Windows\Fonts\msyh.ttc", r"C:\Windows\Fonts\consola.ttf", r"C:\Windows\Fonts\simhei.ttf"]
NAMES = "ABCD"


def font(path_hint, size):
    for p in FONTS:
        if os.path.isfile(p) and (path_hint is None or path_hint in p):
            try:
                return ImageFont.truetype(p, size)
            except Exception:
                pass
    try:
        return ImageFont.truetype(FONTS[0], size)
    except Exception:
        return ImageFont.load_default()


def main():
    files = sorted(f for f in os.listdir(REC) if f.startswith("frame-"))
    if not files:
        print("no frames; run tools/record_demo.py first")
        return 2
    tap_path = os.path.join(REC, "taps.json")
    taps = {}
    if os.path.isfile(tap_path):
        with open(tap_path, encoding="utf-8") as f:
            for t in json.load(f):
                taps[t["frame"]] = t

    out = []
    for i, name in enumerate(files):
        path = os.path.join(REC, name)
        src = Image.open(path).convert("RGB")
        scale = WIDTH / src.width
        blobs = vision.locate(path)
        sel = [k for k, b in enumerate(blobs) if b["selected"]]

        img = src.crop((0, CROP_TOP, src.width, src.height))
        img = img.resize((WIDTH, int(img.height * scale)), Image.LANCZOS)
        canvas = Image.new("RGB", (WIDTH, img.height + BOTTOM), (12, 17, 26))
        canvas.paste(img, (0, 0))
        d = ImageDraw.Draw(canvas)

        # detected boxes
        for k, b in enumerate(blobs):
            x0 = int(b["x"] * scale)
            y0 = int((b["y"] - CROP_TOP) * scale)
            x1 = int((b["x"] + b["w"]) * scale)
            y1 = int((b["y"] + b["h"] - CROP_TOP) * scale)
            color = (59, 130, 246) if k in sel else (110, 120, 140)
            w = 3 if k in sel else 1
            d.rectangle([x0, y0, x1, y1], outline=color, width=w)
            if k < len(NAMES):
                d.text((x0 + 3, y0 - 13), NAMES[k], font=font("msyh", 12),
                       fill=(226, 232, 240))

        # tap indicator
        cmd = "adb exec-out screencap -p"
        if i in taps:
            t = taps[i]
            cx = int(t["x"] * scale)
            cy = int((t["y"] - CROP_TOP) * scale)
            r = int(52 * scale)
            for rr, wd in ((r, 2), (int(r * 0.55), 2)):
                d.ellipse([cx - rr, cy - rr, cx + rr, cy + rr], outline=(251, 146, 60), width=wd)
            d.ellipse([cx - 3, cy - 3, cx + 3, cy + 3], fill=(251, 146, 60))
            cmd = "adb shell input tap %d %d" % (t["x"], t["y"])

        sel_name = NAMES[sel[0]] if sel and sel[0] < len(NAMES) else "?"
        step = "initial" if i == 0 else "step %d" % i
        d.text((8, img.height + 6), "%s · selected: %s" % (step, sel_name),
               font=font("msyh", 13), fill=(226, 232, 240))
        d.text((8, img.height + 28), cmd, font=font("consola", 12), fill=(148, 163, 184))
        out.append(canvas)

    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    out[0].save(OUT, save_all=True, append_images=out[1:], duration=480, loop=0, optimize=True)
    print("wrote %s (%d KB, %d frames)" % (OUT, os.path.getsize(OUT) // 1024, len(out)))
    return 0


if __name__ == "__main__":
    sys.exit(main())