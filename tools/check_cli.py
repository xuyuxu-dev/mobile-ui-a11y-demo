#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""CLI smoke test: every argparse entry point must answer --help.

This catches broken imports, missing modules and syntax-level wiring without a device.
Scripts that do not parse arguments are skipped.
"""
import os
import re
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
SKIP_DIRS = {".git", "__pycache__", "data", "out", "fixtures", "flows"}


def entry_points():
    found = []
    me = os.path.abspath(__file__)
    for root, dirs, files in os.walk(ROOT):
        dirs[:] = [d for d in dirs if d not in SKIP_DIRS]
        for name in sorted(files):
            if not name.endswith(".py"):
                continue
            path = os.path.join(root, name)
            try:
                text = open(path, encoding="utf-8").read()
            except OSError:
                continue
            if os.path.abspath(path) == me:
                continue          # 自己会无限递归
            if "argparse" not in text or '__name__ == "__main__"' not in text:
                continue
            found.append(path)
    return found


def main():
    paths = entry_points()
    try:
        import PIL  # noqa: F401
        have_pil = True
    except ImportError:
        have_pil = False
    failed = []
    for path in paths:
        rel = os.path.relpath(path, ROOT)
        if not have_pil:
            text = open(path, encoding="utf-8").read()
            if "from PIL" in text:
                print("skip %-44s (Pillow missing)" % rel)
                continue
        try:
            p = subprocess.run([sys.executable, path, "--help"], cwd=ROOT,
                               stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=60)
        except subprocess.TimeoutExpired:
            print("FAIL %-44s timeout" % rel)
            failed.append(rel)
            continue
        ok = p.returncode == 0
        print("%-4s %-44s exit=%d" % ("ok" if ok else "FAIL", rel, p.returncode))
        if not ok:
            failed.append(rel)
            tail = (p.stderr or p.stdout).decode("utf-8", "replace").strip().splitlines()
            if tail:
                print("     " + tail[-1][:140])
    print("cli smoke: %d/%d" % (len(paths) - len(failed), len(paths)))
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())