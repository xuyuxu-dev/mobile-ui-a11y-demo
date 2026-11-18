#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""pixel_body: parse the raw screencap header so that hashing is stable across encoders."""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, ROOT)
from adbkit import adbkit as kit  # noqa: E402


def raw(w, h, header=16, fill=b"\x01"):
    return w.to_bytes(4, "little") + h.to_bytes(4, "little") + b"\x01\x00\x00\x00" + \
        (b"\x01\x00\x00\x00" if header == 16 else b"") + fill * (w * h * 4)


def main():
    cases = []

    body16 = kit.pixel_body(raw(2, 3, 16))
    cases.append(("16-byte header", body16 is not None and len(body16) == 2 * 3 * 4))

    body12 = kit.pixel_body(raw(2, 3, 12))
    cases.append(("12-byte header", body12 is not None and len(body12) == 2 * 3 * 4))

    cases.append(("truncated input", kit.pixel_body(b"\x00" * 8) is None))
    cases.append(("zero dimensions", kit.pixel_body(b"\x00" * 16) is None))

    junk = b"\x02\x00\x00\x00\x03\x00\x00\x00\x01\x00\x00\x00\x01\x00\x00\x00" + b"\x00" * 5
    cases.append(("length mismatch", kit.pixel_body(junk) is None))

    same = kit.pixel_body(raw(2, 3, 16)) == kit.pixel_body(raw(2, 3, 12))
    cases.append(("header length does not matter", same))

    ten = raw(10, 10, 16)
    cases.append(("crop 0 keeps every row", len(kit.pixel_body(ten)) == 10 * 10 * 4))
    cases.append(("crop 50% keeps half the rows", len(kit.pixel_body(ten, 0.5)) == 10 * 5 * 4))
    cases.append(("crop is clamped below 90%", len(kit.pixel_body(ten, 2.0)) == 10 * 1 * 4))
    cases.append(("negative crop is ignored", len(kit.pixel_body(ten, -1)) == 10 * 10 * 4))

    bad = 0
    for name, ok in cases:
        print("%-4s %s" % ("ok" if ok else "FAIL", name))
        if not ok:
            bad += 1
    print("pixel hash contract: %d/%d" % (len(cases) - bad, len(cases)))
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())