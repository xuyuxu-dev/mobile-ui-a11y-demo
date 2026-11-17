#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
OCR 通道：把截图变成文字，用于"无障碍树里什么都没有"的页面。

实现：调用 Windows 自带的 OCR（Windows.Media.Ocr，zh-Hans-CN 可用）。
为什么用系统 OCR：本机没有 tesseract，PyPI 也不可达；系统引擎零安装、支持中文。

已知问题：中文结果里字与字之间会插空格（"模 拟 习 题"），需要 normalize。
"""
import json
import os
import re
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
PS_SCRIPT = os.path.join(HERE, "ocr_win.ps1")   # 随包自带，不依赖外部目录

CJK = re.compile(r"[\u4e00-\u9fff]")


def normalize(text):
    """去掉中日韩字符之间被 OCR 插入的空格，其余空白保留。"""
    if not text:
        return ""
    chars = list(text)
    out = []
    for i, c in enumerate(chars):
        if c == " ":
            prev = chars[i - 1] if i > 0 else ""
            nxt = chars[i + 1] if i + 1 < len(chars) else ""
            if CJK.match(prev or "") and CJK.match(nxt or ""):
                continue
        out.append(c)
    return "".join(out).strip()


def ocr_image(path, timeout=90):
    """返回 (raw_text, normalized_text)。失败返回 (None, 原因)。"""
    if not os.path.isfile(path):
        return None, "文件不存在: %s" % path
    if not os.path.isfile(PS_SCRIPT):
        return None, "缺少 OCR 脚本: %s" % PS_SCRIPT
    cmd = ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", PS_SCRIPT, "-Path", path]
    try:
        p = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=timeout)
    except subprocess.TimeoutExpired:
        return None, "OCR 超时"
    out = p.stdout.decode("utf-8", "replace")
    if p.returncode != 0 or "---- 识别结果 ----" not in out:
        return None, (p.stderr.decode("utf-8", "replace") or out)[:300]
    body = out.split("---- 识别结果 ----", 1)[1].strip()
    return body, normalize(body)


def ocr_words(path, timeout=90):
    """返回 (语言, [{text,x,y,w,h}]) —— 带包围盒，可用于"按文字点击"。"""
    cmd = ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", PS_SCRIPT,
           "-Path", path, "-Json"]
    try:
        p = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=timeout)
    except subprocess.TimeoutExpired:
        return None, "OCR 超时"
    out = p.stdout.decode("utf-8", "replace").strip()
    if not out:
        return None, "OCR 无输出"
    try:
        obj = json.loads(out)
    except ValueError:
        return None, out[:200]
    if "error" in obj:
        return None, obj["error"]
    return obj.get("language"), obj.get("words", [])


def find_word(words, needle, fuzzy=False):
    """在词表里找目标；默认要求包含（归一化后比较）。"""
    target = normalize(needle)
    for w in words:
        if normalize(w.get("text", "")) == target:
            return w
    if fuzzy:
        for w in words:
            if target in normalize(w.get("text", "")):
                return w
    return None


def _compact(s):
    """去掉所有空白并转小写。OCR 会把英文单词拆开（"Ca nvas fixture"），
    按原样比对必然失败。"""
    return re.sub(r"\s+", "", s or "").lower()


def contains(text, needle):
    if not needle:
        return False
    if normalize(needle) in normalize(text or ""):
        return True
    # 退一步：忽略全部空白再比一次
    return _compact(needle) in _compact(text)


def main():
    if len(sys.argv) < 2:
        print("用法: python ocr.py <png> [关键词...]")
        return 2
    path = sys.argv[1]
    raw, norm = ocr_image(path)
    if raw is None:
        print("OCR 失败:", norm)
        return 3
    print("原始:", raw[:400])
    print("归一:", norm[:400])
    for kw in sys.argv[2:]:
        print("含 %-12s : %s" % (kw, contains(raw, kw)))
    return 0


if __name__ == "__main__":
    sys.exit(main())