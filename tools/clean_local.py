#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Delete locally generated artefacts (screenshots, traces, build output).

Nothing here is tracked by git; the point is to avoid leaving interface
screenshots on disk after a demo run.
"""
import os
import shutil
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
TARGETS = [
    os.path.join(ROOT, "data"),
    os.path.join(ROOT, "engine", "data"),
    os.path.join(ROOT, "engine", "fixture", "out"),
    os.path.join(ROOT, "engine", "a11ycount", "out"),
    os.path.join(ROOT, "lint", "data", "shots"),
]


def main():
    removed = 0
    for path in TARGETS:
        if os.path.isdir(path):
            shutil.rmtree(path, ignore_errors=True)
            print("removed", os.path.relpath(path, ROOT))
            removed += 1
    # keep the analysed dataset and reports; drop raw screenshots only
    shots = os.path.join(ROOT, "lint", "data")
    if os.path.isdir(shots):
        for name in os.listdir(shots):
            if name.endswith(".png") or name.endswith(".log"):
                os.remove(os.path.join(shots, name))
                print("removed lint/data/%s" % name)
                removed += 1
    print("total removed:", removed)
    return 0


if __name__ == "__main__":
    sys.exit(main())