#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""UI-level helpers built on adbkit primitives.

`adbkit` stays a thin adb layer (shell, dump, screenshot, hashing). Everything that
makes a policy decision about *what is on screen* — starting an activity, waiting for
its package to own the foreground, dismissing a system overlay — lives here so the
collector, the flow engine, the demos and the benchmark share one implementation.
"""
import json
import os
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)
from adbkit import adbkit as kit  # noqa: E402

LAUNCHER_HINT = "launcher"
ALIAS_FILE = os.path.join(ROOT, "local.json")


def load_aliases(path=None):
    """Read the local placeholder → real name mapping.

    The repository ships neutral names (com.vendor.calculator); a real device uses the
    vendor packages, which are kept out of version control in local.json.
    """
    path = path or ALIAS_FILE
    try:
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
    except (OSError, ValueError):
        return {}
    aliases = data.get("aliases") or {}
    return {str(k): str(v) for k, v in aliases.items() if k and v}


PACKAGE_HINTS = {
    "calculator": ["calculator", "calc"],
    "filemanager": ["filemanager", "hidisk", "files"],
    "systemmanager": ["systemmanager", "systemui"],
    "security": ["securitymgr", "security", "privacycenter", "privacy"],
}


def suggest_packages(packages, placeholder, limit=5):
    """Rank installed packages that could stand in for a placeholder name.

    `com.vendor.calculator` looks for packages containing "calculator"; ambiguous
    placeholders (security) return several candidates so the caller can show them.
    """
    token = str(placeholder).rsplit(".", 1)[-1].lower()
    hints = PACKAGE_HINTS.get(token, [token])
    scored = []
    for pkg in packages:
        low = pkg.lower()
        for rank, hint in enumerate(hints):
            if hint and hint in low:
                scored.append((rank, len(pkg), pkg))
                break
    scored.sort()
    return [pkg for _, _, pkg in scored[:limit]]


def resolve(name, aliases=None):
    """Map a placeholder to the local name; unknown names pass through unchanged."""
    if not name:
        return name
    table = aliases if aliases is not None else load_aliases()
    return table.get(name, name)
DEFAULT_POLL_MS = 250


def wait_foreground(adb, serial, package, timeout_ms=3000, poll_ms=DEFAULT_POLL_MS):
    """Poll until package owns the foreground."""
    deadline = time.time() + timeout_ms / 1000.0
    while time.time() < deadline:
        if kit.current_focus(adb, serial).startswith(package):
            return True
        time.sleep(poll_ms / 1000.0)
    return False


def wait_left_launcher(adb, serial, timeout_ms=3000, poll_ms=DEFAULT_POLL_MS):
    """Poll until the foreground is no longer a launcher (for targets without a known package)."""
    deadline = time.time() + timeout_ms / 1000.0
    while time.time() < deadline:
        focus = kit.current_focus(adb, serial)
        if focus and LAUNCHER_HINT not in focus.lower():
            return True
        time.sleep(poll_ms / 1000.0)
    return False


def start_command(component=None, action=None, package=None, clear_task=False):
    """Build the start command; clear_task forces the target task to its entry page."""
    flags = " -f 0x10008000" if clear_task else ""
    if component:
        return "am start -n %s%s" % (component, flags)
    if action:
        return "am start -a %s%s" % (action, flags)
    if package:
        return "monkey -p %s -c android.intent.category.LAUNCHER 1" % package
    return None


def launch(adb, serial, component=None, action=None, package=None, clear_task=False,
           expect_package=None, wait=3.0, tries=2):
    """Start the target and confirm the foreground moved as expected.

    The first start after a wake is sometimes dropped; without this check callers read
    the previous screen and report a confusing failure. Returns the final foreground.
    """
    cmd = start_command(component, action, package, clear_task)
    if cmd is None:
        return ""
    kit.wake(adb, serial)   # 屏幕睡着时启动会落在后台，截图全是黑帧
    package = expect_package or (component.split("/")[0] if component else None)
    timeout_ms = int(wait * 1000)
    for _ in range(tries):
        kit.adb_shell(adb, serial, cmd, timeout=30)
        moved = wait_foreground(adb, serial, package, timeout_ms) if package \
            else wait_left_launcher(adb, serial, timeout_ms)
        if moved:
            return kit.current_focus(adb, serial)
        kit.adb_shell(adb, serial, "input keyevent 82", timeout=10)
    return kit.current_focus(adb, serial)


def launch_component(adb, serial, component, wait=3.0, tries=2):
    return launch(adb, serial, component=component, wait=wait, tries=tries)


def launch_action(adb, serial, action, expect_package=None, clear_task=False, wait=3.0, tries=2):
    return launch(adb, serial, action=action, clear_task=clear_task,
                  expect_package=expect_package, wait=wait, tries=tries)


def ensure_foreground(adb, serial, package, back_packages=("com.android.systemui", "android")):
    """Dismiss a system overlay (e.g. the USB mode chooser) and re-check.

    Only overlays owned by the listed system packages are dismissed with BACK; a real
    application in front is left untouched so the caller can report it instead of
    navigating away from it.
    """
    focus = kit.current_focus(adb, serial)
    if not focus or focus.startswith(package):
        return focus
    owner = focus.split("/")[0]
    if owner not in back_packages:
        return focus
    kit.adb_shell(adb, serial, "input keyevent KEYCODE_BACK", timeout=10)
    for _ in range(10):
        time.sleep(0.2)
        focus = kit.current_focus(adb, serial)
        if not focus or focus.startswith(package):
            break
    return focus