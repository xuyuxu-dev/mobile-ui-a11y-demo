#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""uiauto contract: foreground policy and launch verification, without a device."""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, ROOT)
import uiauto  # noqa: E402
from uiauto import uiauto as ui  # noqa: E402


def patch(focuses, calls, repeat_last=True):
    seq = list(focuses)

    def current_focus(adb, serial):
        if len(seq) > 1 or not repeat_last:
            return seq.pop(0)
        return seq[0] if seq else ""

    def adb_shell(adb, serial, cmd, timeout=30):
        calls.append(cmd)
        return 0, "", ""

    ui.kit.current_focus = current_focus
    ui.kit.adb_shell = adb_shell


def restore():
    ui.kit.current_focus = REAL_FOCUS
    ui.kit.adb_shell = REAL_SHELL


REAL_FOCUS = ui.kit.current_focus
REAL_SHELL = ui.kit.adb_shell


def case_overlay(name, focuses, package, want_back, want_prefix):
    calls = []
    patch(focuses, calls)
    try:
        result = ui.ensure_foreground("adb", "sn", package)
    finally:
        restore()
    backs = sum(1 for c in calls if "KEYCODE_BACK" in c)
    expected_backs = 1 if want_back else 0
    ok = backs == expected_backs and result.startswith(want_prefix)
    print("%-4s %-46s backs=%d focus=%s" % ("ok" if ok else "FAIL", name, backs, result or "<empty>"))
    return ok


def case_launch(name, focuses, want_prefix, want_starts, **kw):
    calls = []
    patch(focuses, calls)
    try:
        result = ui.launch("adb", "sn", **kw)
    finally:
        restore()
    starts = sum(1 for c in calls if c.startswith("am start"))
    ok = result.startswith(want_prefix) and starts == want_starts
    if kw.get("clear_task"):
        ok = ok and any("0x10008000" in c for c in calls)
    print("%-4s %-46s starts=%d focus=%s" % ("ok" if ok else "FAIL", name, starts, result or "<empty>"))
    return ok


def alias_cases():
    import json
    import tempfile
    cases = []
    path = os.path.join(tempfile.mkdtemp(prefix="alias-"), "local.json")
    with open(path, "w", encoding="utf-8") as f:
        json.dump({"aliases": {"com.vendor.calculator": "com.real.calc"}}, f)
    table = ui.load_aliases(path)
    cases.append(("alias file is applied", table.get("com.vendor.calculator") == "com.real.calc"))
    cases.append(("unknown name passes through", ui.resolve("com.android.settings", table) == "com.android.settings"))
    cases.append(("known name is mapped", ui.resolve("com.vendor.calculator", table) == "com.real.calc"))
    cases.append(("missing file yields empty map", ui.load_aliases(os.path.join(path, "nope.json")) == {}))
    pkgs = ["com.example.calculator", "com.other.calc", "com.example.filemanager",
            "com.example.hidisk", "com.example.securitymgr", "com.unrelated"]
    cases.append(("suggests a calculator", ui.suggest_packages(pkgs, "com.vendor.calculator")[0] == "com.example.calculator"))
    cases.append(("falls back to the last token", ui.suggest_packages(pkgs, "com.vendor.unrelated") == ["com.unrelated"]))
    cases.append(("file manager hints prefer filemanager",
                  ui.suggest_packages(pkgs, "com.vendor.filemanager")[0] == "com.example.filemanager"))
    cases.append(("limit is respected", len(ui.suggest_packages(pkgs, "com.vendor.filemanager", limit=1)) == 1))
    cases.append(("unknown placeholder returns nothing", ui.suggest_packages(pkgs, "com.vendor.nothing") == []))
    bad = 0
    for name, ok in cases:
        print("%-4s %s" % ("ok" if ok else "FAIL", name))
        if not ok:
            bad += 1
    return len(cases) - bad, len(cases)


def main():
    overlay = [
        ("already foreground", ["com.demo.canvas/.MainActivity"], "com.demo.canvas", False, "com.demo.canvas"),
        ("system overlay dismissed", ["com.android.systemui/.UsbModeChooser", "com.demo.canvas/.MainActivity"],
         "com.demo.canvas", True, "com.demo.canvas"),
        ("overlay does not go away", ["com.android.systemui/.UsbModeChooser"],
         "com.demo.canvas", True, "com.android.systemui"),
        ("real app left alone", ["com.android.settings/.Settings"], "com.demo.canvas", False, "com.android.settings"),
        ("empty focus", [""], "com.demo.canvas", False, ""),
    ]
    passed = sum(1 for c in overlay if case_overlay(*c))

    launch_cases = [
        ("launch: becomes foreground", ["com.demo.canvas/.MainActivity"],
         "com.demo.canvas", 1, {"component": "com.demo.canvas/.MainActivity"}),
        ("launch: dropped start retried", ["com.android.settings/.Settings"] * 2 + ["com.demo.canvas/.MainActivity"],
         "com.demo.canvas", 2, {"component": "com.demo.canvas/.MainActivity", "wait": 0.3}),
        ("launch: never foreground", ["com.android.settings/.Settings"] * 8,
         "com.android.settings", 2, {"component": "com.demo.canvas/.MainActivity"}),
        ("launch: action with expected package", ["com.android.settings/.Settings"],
         "com.android.settings", 1, {"action": "android.settings.SETTINGS", "expect_package": "com.android.settings"}),
        ("launch: clear_task adds the flag", ["com.demo.canvas/.MainActivity"],
         "com.demo.canvas", 1, {"component": "com.demo.canvas/.MainActivity", "clear_task": True}),
    ]
    for name, focuses, prefix, starts, kw in launch_cases:
        passed += case_launch(name, focuses, prefix, starts, **kw)

    alias_ok, alias_total = alias_cases()
    passed += alias_ok
    total = len(overlay) + len(launch_cases) + alias_total
    print("uiauto contract: %d/%d" % (passed, total))
    return 0 if passed == total else 1


if __name__ == "__main__":
    sys.exit(main())