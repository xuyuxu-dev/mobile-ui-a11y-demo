#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Compose the OCR-channel GIF: screenshot -> OCR boxes -> tap -> verified state."""
import json
import os
import sys

from PIL import Image, ImageDraw, ImageFont

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(ROOT, "engine"))
import vision  # noqa: E402

REC = os.path.join(ROOT, "engine", "data", "ocr-rec")
OUT = os.path.join(ROOT, "docs", "assets", "ocr.gif")
WIDTH, CROP_TOP, BOTTOM = 380, 104, 52
FONTS = [r"C:\Windows\Fonts\msyh.ttc", r"C:\Windows\Fonts\consola.ttf"]
NAMES = "ABCD"


def font(path_hint, size):
    for p in FONTS:
        if os.path.isfile(p) and (path_hint is None or path_hint in p):
            try:
                return ImageFont.truetype(p, size)
            except Exception:
                pass
    return ImageFont.load_default()


def base(path):
    src = Image.open(path).convert("RGB")
    scale = WIDTH / src.width
    img = src.crop((0, CROP_TOP, src.width, src.height))
    img = img.resize((WIDTH, int(img.height * scale)), Image.LANCZOS)
    canvas = Image.new("RGB", (WIDTH, img.height + BOTTOM), (12, 17, 26))
    canvas.paste(img, (0, 0))
    return canvas, scale, img.height


def main():
    meta_path = os.path.join(REC, "meta.json")
    if not os.path.isfile(meta_path):
        print("run tools/record_ocr.py first")
        return 2
    with open(meta_path, encoding="utf-8") as f:
        meta = json.load(f)
    before = os.path.join(REC, "stage-0.png")
    after = os.path.join(REC, "stage-2.png")
    letters = meta["letters"]
    tap = meta["tap"]

    frames = []
    stages = [
        ("before", "adb exec-out screencap -p", "1/3 screenshot"),
        ("boxes", "ocr: %d letters detected" % len(letters), "2/3 OCR bounding boxes"),
        ("tap", "adb shell input tap %d %d" % (tap["x"], tap["y"]),
         "3/3 tap the OCR box of %s" % tap["text"]),
        ("after", "selected: %s" % (NAMES[meta["selected_after"][0]]
                                   if meta["selected_after"] else "?"),
         "verified visually"),
    ]
    for kind, cmd, caption in stages:
        path = after if kind == "after" else before
        canvas, scale, h = base(path)
        d = ImageDraw.Draw(canvas)
        if kind in ("boxes", "after"):
            for w in letters:
                x0 = int(w["x"] * scale)
                y0 = int((w["y"] - CROP_TOP) * scale)
                x1 = int((w["x"] + w["w"]) * scale)
                y1 = int((w["y"] + w["h"] - CROP_TOP) * scale)
                d.rectangle([x0, y0, x1, y1], outline=(244, 114, 182), width=2)
        if kind == "after":
            sel = [i for i, b in enumerate(vision.locate(path)) if b["selected"]]
            for i, b in enumerate(vision.locate(path)):
                if i in sel:
                    x0 = int(b["x"] * scale); y0 = int((b["y"] - CROP_TOP) * scale)
                    x1 = int((b["x"] + b["w"]) * scale); y1 = int((b["y"] + b["h"] - CROP_TOP) * scale)
                    d.rectangle([x0, y0, x1, y1], outline=(59, 130, 246), width=3)
        if kind == "tap":
            cx = int(tap["x"] * scale); cy = int((tap["y"] - CROP_TOP) * scale)
            r = int(52 * scale)
            d.ellipse([cx - r, cy - r, cx + r, cy + r], outline=(251, 146, 60), width=2)
            d.ellipse([cx - 3, cy - 3, cx + 3, cy + 3], fill=(251, 146, 60))
        d.text((8, h + 6), caption, font=font("msyh", 13), fill=(226, 232, 240))
        d.text((8, h + 28), cmd, font=font("consola", 12), fill=(148, 163, 184))
        frames.append(canvas)

    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    frames[0].save(OUT, save_all=True, append_images=frames[1:],
                   duration=[1300, 1300, 900, 1800], loop=0, optimize=True)
    print("wrote %s (%d KB, %d frames)" % (OUT, os.path.getsize(OUT) // 1024, len(frames)))
    return 0


if __name__ == "__main__":
    sys.exit(main())