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


def launch_case(name, focuses, component, want_starts, want_shell_calls):
    """launch_component: poll until the component owns the foreground, retry once."""
    seq = list(focuses)
    calls = []

    def current_focus(adb, serial):
        return seq.pop(0) if seq else ""

    def adb_shell(adb, serial, cmd, timeout=30):
        calls.append(cmd)
        return 0, "", ""

    old_cf, old_sh = kit.current_focus, kit.adb_shell
    kit.current_focus, kit.adb_shell = current_focus, adb_shell
    try:
        result = kit.launch_component("adb", "sn", component, wait=0.6, tries=2)
    finally:
        kit.current_focus, kit.adb_shell = old_cf, old_sh
    starts = sum(1 for c in calls if c.startswith("am start"))
    ok = result.startswith(want_starts) and starts == want_shell_calls
    print("%-4s %-46s starts=%d focus=%s" % ("ok" if ok else "FAIL", name, starts, result or "<empty>"))
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

    launch_cases = [
        ("launch: becomes foreground", ["com.demo.canvas/.MainActivity"],
         "com.demo.canvas/.MainActivity", "com.demo.canvas", 1),
        ("launch: first start dropped, retry works",
         ["com.android.settings/.HWSettings"] * 3 + ["com.demo.canvas/.MainActivity"],
         "com.demo.canvas/.MainActivity", "com.demo.canvas", 2),
        ("launch: never becomes foreground",
         ["com.android.settings/.HWSettings"] * 8,
         "com.demo.canvas/.MainActivity", "com.android.settings", 2),
    ]
    passed += sum(1 for c in launch_cases if launch_case(*c))
    total = len(cases) + len(launch_cases)
    print("foreground contract: %d/%d" % (passed, total))
    return 0 if passed == total else 1


if __name__ == "__main__":
    sys.exit(main())