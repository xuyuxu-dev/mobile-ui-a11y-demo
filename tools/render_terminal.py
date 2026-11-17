#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Render a terminal-style animated GIF from a list of command/output lines."""
import os
import sys

from PIL import Image, ImageDraw, ImageFont

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
FONT_PATH = r"C:\Windows\Fonts\consola.ttf"
BG = (13, 17, 23)
FG = (201, 209, 217)
PROMPT = (88, 166, 255)
OK = (63, 185, 80)
DIM = (139, 148, 158)

LINES = [
    ("cmd", "python lint/collectors/collect_batch.py --serial <SN>"),
    ("out", "settings       nodes= 91 int=14 unl= 0 small= 4"),
    ("out", "display        nodes=107 int=12 unl= 0 small= 2"),
    ("out", "sound          nodes=110 int=17 unl= 0 small= 3"),
    ("out", "apps           nodes=126 int=15 unl= 0 small= 1"),
    ("out", "battery        nodes= 47 int= 7 unl= 0 small= 1"),
    ("out", "accessibility  nodes=132 int=19 unl= 0 small= 1"),
    ("ok", "6 pages collected"),
    ("cmd", "python lint/analyze/analyze.py lint/data/lint.jsonl"),
    ("ok", "report.md  report.html  matrix.csv  chart.svg"),
]


def main():
    size = 15
    font = ImageFont.truetype(FONT_PATH, size)
    line_h = 22
    width = 640
    height = line_h * (len(LINES) + 1) + 24
    frames = []
    for i in range(1, len(LINES) + 1):
        img = Image.new("RGB", (width, height), BG)
        d = ImageDraw.Draw(img)
        y = 12
        for kind, text in LINES[:i]:
            if kind == "cmd":
                d.text((14, y), "$", font=font, fill=PROMPT)
                d.text((32, y), text, font=font, fill=FG)
            elif kind == "ok":
                d.text((14, y), text, font=font, fill=OK)
            else:
                d.text((14, y), text, font=font, fill=DIM)
            y += line_h
        frames.append(img)
    out = os.path.join(ROOT, "docs", "assets", "audit.gif")
    os.makedirs(os.path.dirname(out), exist_ok=True)
    frames[0].save(out, save_all=True, append_images=frames[1:],
                   duration=[420] * (len(frames) - 1) + [1600], loop=0, optimize=True)
    print("wrote %s (%d KB, %d frames)" % (out, os.path.getsize(out) // 1024, len(frames)))


if __name__ == "__main__":
    main()