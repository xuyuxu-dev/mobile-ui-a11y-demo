#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""ensure_foreground: dismiss a system overlay, but never navigate a real app away."""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, ROOT)
from adbkit import adbkit as kit  # noqa: E402

CALLS = []


def fake_run(focus_seq, shell_recorder):
    """Return patched current_focus/adb_shell and the sequence of back presses."""
    seq = list(focus_seq)

    def current_focus(adb, serial):
        # 序列耗尽后重复最后一个值：模拟遮罩一直存在
        if len(seq) > 1:
            return seq.pop(0)
        return seq[0] if seq else ""

    def adb_shell(adb, serial, cmd, timeout=30):
        shell_recorder.append(cmd)
        return 0, "", ""

    return current_focus, adb_shell


def case(name, focuses, package, want_back, want_result):
    backs = []
    cf, sh = fake_run(focuses, backs)
    old_cf, old_sh = kit.current_focus, kit.adb_shell
    kit.current_focus, kit.adb_shell = cf, sh
    try:
        result = kit.ensure_foreground("adb", "sn", package)
    finally:
        kit.current_focus, kit.adb_shell = old_cf, old_sh
    sent_back = any("KEYCODE_BACK" in c for c in backs)
    ok = sent_back == want_back and result.startswith(want_result)
    print("%-4s %-46s back=%-5s focus=%s" % ("ok" if ok else "FAIL", name, sent_back, result or "<empty>"))
    return ok


def main():
    cases = [
        ("already foreground", ["com.demo.canvas/.MainActivity"], "com.demo.canvas", False, "com.demo.canvas"),
        ("system overlay dismissed", ["com.android.systemui/.UsbModeChooser", "com.demo.canvas/.MainActivity"],
         "com.demo.canvas", True, "com.demo.canvas"),
        ("overlay does not go away", ["com.android.systemui/.UsbModeChooser", "com.android.systemui/.UsbModeChooser"],
         "com.demo.canvas", True, "com.android.systemui"),
        ("real app left alone", ["com.android.settings/.HWSettings"], "com.demo.canvas", False, "com.android.settings"),
        ("empty focus", [""], "com.demo.canvas", False, ""),
    ]
    passed = sum(1 for c in cases if case(*c))
    print("overlay contract: %d/%d" % (passed, len(cases)))
    return 0 if passed == len(cases) else 1


if __name__ == "__main__":
    sys.exit(main())