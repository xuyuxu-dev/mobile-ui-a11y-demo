#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
视觉定位原型：在没有无障碍节点的 Canvas 页面上，从截图里找出可点区域。

做法（刻意保持简单，便于验证）：
  1. 取页面下部一条区域
  2. 掩码 = 非白非黑的有色像素（灰底圆钮 + 蓝底选中钮）
  3. 按列投影找"连通块"，得到每个圆钮的包围盒
  4. 中心像素偏蓝 → 选中；否则未选中
输出：每个块的 (x, y, w, h, 是否选中)
"""
import json
import os
import sys

import numpy as np
from PIL import Image

HERE = os.path.dirname(os.path.abspath(__file__))


def load_rgb(path):
    with Image.open(path) as im:
        return np.asarray(im.convert("RGB")).astype(np.int16)


def mask_controls(img, y_from=0.70, y_to=0.95):
    """返回 0/1 掩码：页面下部、既不是纯白也不是纯黑、且有一定饱和度的像素。"""
    h, w, _ = img.shape
    y0, y1 = int(h * y_from), int(h * y_to)
    sub = img[y0:y1]
    r, g, b = sub[:, :, 0], sub[:, :, 1], sub[:, :, 2]
    mx = np.maximum(np.maximum(r, g), b)
    mn = np.minimum(np.minimum(r, g), b)
    val = mx
    sat = mx - mn
    # 灰底钮：亮度 200~240、饱和度低；蓝底钮：B 明显大于 R
    gray = (val > 195) & (val < 245) & (sat < 18)
    blue = (b > r + 40) & (b > 120)
    m = (gray | blue)
    return m, y0


def components(mask, min_area=1500):
    """4-邻域连通域标记（BFS）。按列投影会把相邻圆钮粘在一起——
    实测 x=300 处有 11 个抗锯齿像素，就被判成"连着的"。"""
    from collections import deque
    h, w = mask.shape
    seen = np.zeros((h, w), dtype=bool)
    out = []
    for y in range(h):
        row = mask[y]
        for x in range(w):
            if not row[x] or seen[y, x]:
                continue
            q = deque([(y, x)])
            seen[y, x] = True
            x0 = x1 = x
            y0 = y1 = y
            area = 0
            while q:
                cy, cx = q.popleft()
                area += 1
                if cx < x0: x0 = cx
                if cx > x1: x1 = cx
                if cy < y0: y0 = cy
                if cy > y1: y1 = cy
                for ny, nx in ((cy+1, cx), (cy-1, cx), (cy, cx+1), (cy, cx-1)):
                    if 0 <= ny < h and 0 <= nx < w and mask[ny, nx] and not seen[ny, nx]:
                        seen[ny, nx] = True
                        q.append((ny, nx))
            if area >= min_area:
                out.append((x0, y0, x1, y1, area))
    return out


def locate(path):
    img = load_rgb(path)
    mask, y0 = mask_controls(img)
    blobs = []
    for (xs, ys, xe, ye, area) in components(mask):
        if xe - xs < 40 or ye - ys < 40:   # 太小，忽略
            continue
        sub = img[y0 + ys:y0 + ye + 1, xs:xe + 1]
        r = sub[:, :, 0].mean()
        g = sub[:, :, 1].mean()
        b = sub[:, :, 2].mean()
        selected = bool(b > r + 30)
        blobs.append({
            "x": int(xs), "y": int(y0 + ys), "w": int(xe - xs), "h": int(ye - ys),
            "cx": int((xs + xe) / 2), "cy": int(y0 + (ys + ye) / 2),
            "selected": selected,
            "mean_rgb": [round(float(r), 1), round(float(g), 1), round(float(b), 1)],
        })
    # 去掉被其它块包含的碎片（同一圆钮的抗锯齿碎片会被单独标出来）
    def contained(a, b):
        return (a["x"] >= b["x"] and a["y"] >= b["y"]
                and a["x"] + a["w"] <= b["x"] + b["w"]
                and a["y"] + a["h"] <= b["y"] + b["h"])

    blobs = [a for a in blobs if not any(contained(a, b) for b in blobs if b is not a)]
    blobs.sort(key=lambda z: z["x"])
    return blobs


def to_gray(img):
    return img.astype(np.float32).mean(axis=2)


def match_template(screen_path, template_path, coarse=8, mask_center=0.0):
    """模板匹配（归一化互相关）。

    做法：先粗搜（降采样）拿到大致位置，再在全分辨率的小窗口内细化。
    为什么不用连通域：那个只能找规则形状；真实界面里的按钮可能是不规则图标。
    """
    scr = to_gray(load_rgb(screen_path))
    tpl = to_gray(load_rgb(template_path))
    th, tw = tpl.shape
    # 可选：屏蔽模板中心区域，只比对"外圈"。
    # 按钮中间往往写着变化的文字（A/B/C/D），直接全图比对会把分数拉低；
    # 只比对外圈形状/颜色，才能回答"这是不是同一种按钮样式"。
    mask = np.ones((th, tw), dtype=np.float32)
    if mask_center > 0:
        cw, chh = int(tw * mask_center), int(th * mask_center)
        x0 = (tw - cw) // 2
        y0 = (th - chh) // 2
        mask[y0:y0 + chh, x0:x0 + cw] = 0.0
    mask_small = mask[::coarse, ::coarse] if coarse > 1 else mask
    m_count = mask_small.sum() or 1.0
    m_count_f = mask.sum() or 1.0
    if scr.shape[0] < th or scr.shape[1] < tw:
        return None

    # 粗搜
    s_small = scr[::coarse, ::coarse]
    t_small = tpl[::coarse, ::coarse]
    ths, tws = t_small.shape
    if ths < 3 or tws < 3:
        return None
    tz = (t_small - (t_small * mask_small).sum() / m_count) * mask_small
    tnorm = np.sqrt((tz ** 2).sum()) or 1.0

    H, W = s_small.shape
    best = (-1.0, 0, 0)
    sw = np.lib.stride_tricks.sliding_window_view(s_small, (ths, tws))
    # sw 形状: (H-ths+1, W-tws+1, ths, tws)
    sw = (sw - (sw * mask_small).sum(axis=(2, 3), keepdims=True) / m_count) * mask_small
    denom = np.sqrt((sw ** 2).sum(axis=(2, 3))) * tnorm
    denom[denom == 0] = 1.0
    ncc = (sw * tz).sum(axis=(2, 3)) / denom
    idx = np.unravel_index(np.argmax(ncc), ncc.shape)
    best = (float(ncc[idx]), int(idx[1]) * coarse, int(idx[0]) * coarse)

    # 全分辨率细化（在粗结果附近 ±coarse 内）
    score0, x0, y0 = best
    xs = max(0, x0 - coarse)
    ys = max(0, y0 - coarse)
    xe = min(scr.shape[1], x0 + coarse + tw)
    ye = min(scr.shape[0], y0 + coarse + th)
    win = scr[ys:ye, xs:xe]
    if win.shape[0] < th or win.shape[1] < tw:
        return {"score": score0, "x": x0 + tw // 2, "y": y0 + th // 2, "w": tw, "h": th}
    tz2 = (tpl - (tpl * mask).sum() / m_count_f) * mask
    tn2 = np.sqrt((tz2 ** 2).sum()) or 1.0
    sw2 = np.lib.stride_tricks.sliding_window_view(win, (th, tw))
    sw2 = (sw2 - (sw2 * mask).sum(axis=(2, 3), keepdims=True) / m_count_f) * mask
    den2 = np.sqrt((sw2 ** 2).sum(axis=(2, 3))) * tn2
    den2[den2 == 0] = 1.0
    ncc2 = (sw2 * tz2).sum(axis=(2, 3)) / den2
    idx2 = np.unravel_index(np.argmax(ncc2), ncc2.shape)
    return {
        "score": float(ncc2[idx2]),
        "x": int(xs + idx2[1] + tw // 2),
        "y": int(ys + idx2[0] + th // 2),
        "w": int(tw), "h": int(th),
    }


def crop(screen_path, x, y, w, h, out_path):
    img = Image.open(screen_path).convert("RGB")
    img.crop((x, y, x + w, y + h)).save(out_path)
    return out_path


def main():
    if len(sys.argv) < 3:
        print("用法: python vision.py locate <png>")
        return 2
    cmd, path = sys.argv[1], sys.argv[2]
    if cmd == "match":
        if len(sys.argv) < 4:
            print("用法: python vision.py match <screen.png> <template.png>")
            return 2
        res = match_template(path, sys.argv[3])
        print(json.dumps(res, ensure_ascii=False, indent=2))
        return 0
    if cmd == "crop":
        if len(sys.argv) < 7:
            print("用法: python vision.py crop <screen.png> <x> <y> <w> <h> <out.png>")
            return 2
        crop(path, *[int(v) for v in sys.argv[3:7]], sys.argv[7])
        print("ok")
        return 0
    if cmd != "locate":
        print("未知命令: %s" % cmd)
        return 2
    blobs = locate(path)
    print(json.dumps(blobs, ensure_ascii=False, indent=2))
    print("\n找到 %d 个候选可点区域；选中态: %s"
          % (len(blobs), [i for i, b in enumerate(blobs) if b["selected"]]))
    return 0


if __name__ == "__main__":
    sys.exit(main())