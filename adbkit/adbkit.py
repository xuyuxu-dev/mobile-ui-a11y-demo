#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
adbkit：两个包共用的 adb 原语（设备发现 / 读界面树 / 读密度 / 截图哈希）。

为什么单独抽出来：
  原来 lint 和 engine 各自 import lint/collectors/adb_collect.py，
  拆仓时第二个仓库会依赖第一个仓库的路径。抽成公共包后，两边都只依赖 adbkit。

这里只放"和业务无关"的底层能力，不放指标、不放流程。
"""
import hashlib
import os
import re
import subprocess
import time

HERE = os.path.dirname(os.path.abspath(__file__))
DEMO = os.path.dirname(HERE)
# 工作区里 adb 的常见位置（不写死单个绝对路径）
_ADB_CANDIDATES = [
    os.path.join(DEMO, "..", "platform-tools", "adb.exe"),
    os.path.join(DEMO, "..", "platform-tools", "adb"),
]


def resolve_adb(explicit=None):
    cands = []
    if explicit:
        cands.append(explicit)
    if os.environ.get("ADB"):
        cands.append(os.environ["ADB"])
    cands += [os.path.abspath(p) for p in _ADB_CANDIDATES]
    for c in cands:
        if c and os.path.isfile(c):
            return c
    return "adb"


def sh(args, timeout=30):
    p = subprocess.run(args, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=timeout)
    return p.returncode, p.stdout.decode("utf-8", "replace"), p.stderr.decode("utf-8", "replace")


def adb_shell(adb, serial, cmd, timeout=30):
    args = [adb] + (["-s", serial] if serial else []) + ["shell", cmd]
    return sh(args, timeout)


def devices(adb):
    rc, out, _ = sh([adb, "devices"])
    if rc != 0:
        return []
    return [l.split("\t")[0] for l in out.splitlines()[1:] if "\tdevice" in l]


def pick_device(adb, serial=None):
    if serial:
        return serial
    ds = devices(adb)
    return ds[0] if ds else None


def hardware_id(adb, serial):
    """Prefer the hardware serial so the tag is stable across USB and Wi-Fi transports."""
    rc, out, _ = adb_shell(adb, serial, "getprop ro.serialno", timeout=10)
    if rc == 0:
        hw = out.strip()
        if hw and len(hw) >= 6:
            return hw
    return serial


def device_tag(serial):
    """Stable pseudonym for a device.

    The raw serial identifies a physical phone, so collected records store this
    short hash instead: distinct devices stay distinguishable, the serial does not
    leave the machine.
    """
    import hashlib
    if not serial:
        return "unknown"
    if serial == "fixture":
        return "fixture"
    return "dev-" + hashlib.sha256(serial.encode("utf-8")).hexdigest()[:8]


def get_density(adb, serial):
    rc, out, _ = adb_shell(adb, serial, "wm density")
    if rc == 0:
        m = re.search(r"(\d+)\s*$", out.strip(), re.M)
        if m:
            return float(m.group(1))
        m = re.search(r"density[:\s]+(\d+)", out)
        if m:
            return float(m.group(1))
    return 160.0


def wake(adb, serial):
    """Bring the device out of sleep; returns True when the display is on."""
    for _ in range(3):
        rc, out, _ = adb_shell(adb, serial, "dumpsys power | grep mWakefulness=", timeout=10)
        if "Awake" in (out or ""):
            return True
        adb_shell(adb, serial, "input keyevent KEYCODE_WAKEUP", timeout=10)
        time.sleep(0.4)
    rc, out, _ = adb_shell(adb, serial, "dumpsys power | grep mWakefulness=", timeout=10)
    return "Awake" in (out or "")


def current_focus(adb, serial):
    """Foreground component, with a fallback for ROMs whose window dump is empty."""
    for cmd in ("dumpsys window windows | grep mCurrentFocus",
                "dumpsys window | grep mCurrentFocus",
                "dumpsys activity activities | grep mResumedActivity"):
        rc, out, _ = adb_shell(adb, serial, cmd, timeout=15)
        m = re.search(r"([A-Za-z0-9_.]+)/([A-Za-z0-9_.$]+)", out or "")
        if m:
            return m.group(1) + "/" + m.group(2)
    return ""


BOUNDS_RE = re.compile(r"\[(-?\d+),(-?\d+)\]\[(-?\d+),(-?\d+)\]")


def parse_bounds(s):
    m = BOUNDS_RE.match(s or "")
    return tuple(int(x) for x in m.groups()) if m else None


def dump_current(adb, serial, xml_path="/sdcard/adbkit_dump.xml"):
    """dump 当前界面并返回 XML 文本；(None, 原因) 表示失败。"""
    rc, out, err = adb_shell(adb, serial, "uiautomator dump %s" % xml_path, timeout=40)
    if rc != 0 or "dumped to" not in out:
        return None, "uiautomator dump 失败: %s" % (err.strip() or out.strip())[:200]
    rc2, xml, err2 = adb_shell(adb, serial, "cat %s" % xml_path, timeout=40)
    if rc2 != 0 or "<hierarchy" not in xml:
        return None, "读取 dump 失败: %s" % (err2.strip() or "")[:200]
    return xml, ""


def screencap(adb, serial):
    """返回 PNG 原始字节；失败返回 None。"""
    args = [adb] + (["-s", serial] if serial else []) + ["exec-out", "screencap -p"]
    p = subprocess.run(args, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=60)
    if p.returncode != 0 or not p.stdout:
        return None
    return p.stdout


def screen_hash(adb, serial):
    data = screencap(adb, serial)
    return hashlib.md5(data).hexdigest() if data else None


def save_screencap(adb, serial, path):
    data = screencap(adb, serial)
    if not data:
        return False
    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
    with open(path, "wb") as f:
        f.write(data)
    return True