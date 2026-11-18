#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Runner behaviour with a fake adb layer (no device).

Covers the parts that only ever ran on hardware: text waiting, tap targeting,
dry-run gating, change detection, stability and key events.
"""
import json
import os
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
DEMO = os.path.dirname(ROOT)
sys.path.insert(0, DEMO)
sys.path.insert(0, ROOT)
import engine as eng  # noqa: E402

HOME_XML = ('<hierarchy><node text="确定" bounds="[100,200][300,400]" clickable="true"/>'
            '<node text="取消" bounds="[400,200][600,400]" clickable="true"/></hierarchy>')
TAPPED_XML = ('<hierarchy><node text="已点击" bounds="[100,200][300,400]" clickable="true"/></hierarchy>')
BLANK_XML = '<hierarchy><node text="" bounds="[0,0][1,1]"/></hierarchy>'


class FakeDevice:
    """Minimal adb stand-in: a screen state that reacts to taps and starts."""

    def __init__(self, start="home"):
        self.state = start
        self.calls = []

    def dump_current(self, adb, serial):
        if self.state == "home":
            return HOME_XML, ""
        if self.state == "tapped":
            return TAPPED_XML, ""
        return BLANK_XML, ""

    def adb_shell(self, adb, serial, cmd, timeout=30):
        self.calls.append(cmd)
        if cmd.startswith("input tap"):
            self.state = "tapped"
        elif cmd.startswith("am start") or cmd.startswith("monkey"):
            self.state = "home"
        return 0, "", ""

    def screen_hash(self, adb, serial):
        return "hash-" + self.state


REAL = (eng.ac.dump_current, eng.ac.adb_shell, eng.ac.screen_hash)


def install(dev):
    eng.ac.dump_current = dev.dump_current
    eng.ac.adb_shell = dev.adb_shell
    eng.ac.screen_hash = dev.screen_hash


def restore():
    eng.ac.dump_current, eng.ac.adb_shell, eng.ac.screen_hash = REAL


def run(flow, dev, allow_taps):
    tmp = tempfile.mkdtemp(prefix="runner-")
    trace = os.path.join(tmp, "trace.jsonl")
    install(dev)
    try:
        r = eng.Runner("adb", "SERIAL", allow_taps, trace)
        ok = r.run({"steps": flow})
    finally:
        restore()
    lines = [json.loads(l) for l in open(trace, encoding="utf-8") if l.strip()]
    return ok, dev.calls, lines


def case(name, flow, allow_taps, want_ok, want_call=None, want_missing_call=None, start="home"):
    dev = FakeDevice(start)
    ok, calls, lines = run(flow, dev, allow_taps)
    good = ok == want_ok
    if want_call:
        good = good and any(want_call in c for c in calls)
    if want_missing_call:
        good = good and not any(want_missing_call in c for c in calls)
    good = good and len(lines) == len(flow)
    print("%-4s %-46s ok=%s calls=%d trace=%d" % ("ok" if good else "FAIL", name, ok, len(calls), len(lines)))
    if not good:
        print("     calls: %s" % calls)
        print("     trace: %s" % [l["op"] for l in lines])
    return good


def main():
    cases = [
        ("wait_text finds the label",
         [{"op": "wait_text", "text": "确定"}], True, True),
        ("wait_text times out",
         [{"op": "wait_text", "text": "不存在", "timeout": 300}], True, False),
        ("tap_text sends the centre of the bounds",
         [{"op": "tap_text", "text": "确定"}], True, True, "input tap 200 300"),
        ("dry-run never taps",
         [{"op": "tap_text", "text": "确定"}], False, True, None, "input tap"),
        ("dry-run marks later steps as SKIP",
         [{"op": "tap_text", "text": "确定"}, {"op": "back"}], False, True, None, "input tap"),
        ("assert_changed sees the tapped frame",
         [{"op": "tap_text", "text": "确定"}, {"op": "assert_changed", "timeout": 800}], True, True),
        ("assert_stable passes on a settled screen",
         [{"op": "assert_stable", "timeout": 800}], True, True),
        ("launch is compared against the pre-launch frame",
         [{"op": "launch", "component": "com.demo.canvas/.MainActivity"},
          {"op": "assert_changed", "timeout": 800}], True, True, None, None, "blank"),
        ("back sends keyevent 4",
         [{"op": "back"}], True, True, "keyevent 4"),
        ("home sends keyevent 3",
         [{"op": "home"}], True, True, "keyevent 3"),
    ]
    passed = sum(1 for c in cases if case(*c))
    print("runner contract: %d/%d" % (passed, len(cases)))
    return 0 if passed == len(cases) else 1


if __name__ == "__main__":
    sys.exit(main())