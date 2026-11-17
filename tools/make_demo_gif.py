#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""从真实截图合成 demo GIF（不伪造界面）。"""
import os
import sys

from PIL import Image, ImageDraw, ImageFont

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
OUT = os.path.join(ROOT, "docs", "assets", "demo.gif")
WIDTH = 380
CAPTION_H = 34
FONTS = [r"C:\Windows\Fonts\msyh.ttc", r"C:\Windows\Fonts\msyhbd.ttc", r"C:\Windows\Fonts\simhei.ttf"]


def font(size):
    for p in FONTS:
        if os.path.isfile(p):
            try:
                return ImageFont.truetype(p, size)
            except Exception:
                pass
    return ImageFont.load_default()


def frame(path, caption):
    img = Image.open(path).convert("RGB")
    ratio = WIDTH / img.width
    img = img.resize((WIDTH, int(img.height * ratio)), Image.LANCZOS)
    canvas = Image.new("RGB", (WIDTH, CAPTION_H + img.height), (17, 24, 39))
    ImageDraw.Draw(canvas).text((10, 8), caption, font=font(15), fill=(235, 240, 250))
    canvas.paste(img, (0, CAPTION_H))
    return canvas


def main():
    src = [
        ("engine/data/canvas-page.png", "① 无障碍树：8 节点 / 0 可交互"),
        ("engine/data/vision-before.png", "② 视觉定位：4 个按钮，#3 为选中态"),
        ("engine/data/vision-after.png", "③ 点击后重算：选中态变为 #0"),
        ("engine/data/ocr-fixture3.png", "④ OCR：识别文字并给出包围盒"),
    ]
    frames, missing = [], []
    for rel, cap in src:
        p = os.path.join(ROOT, rel)
        if not os.path.isfile(p):
            missing.append(rel)
            continue
        frames.append(frame(p, cap))
    if missing:
        print("缺少截图：%s" % missing)
        return 2
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    frames[0].save(OUT, save_all=True, append_images=frames[1:],
                   duration=[1200, 1400, 1400, 1600], loop=0, optimize=True)
    print("写出 %s（%d KB，%d 帧）" % (OUT, os.path.getsize(OUT) // 1024, len(frames)))
    return 0


if __name__ == "__main__":
    sys.exit(main())