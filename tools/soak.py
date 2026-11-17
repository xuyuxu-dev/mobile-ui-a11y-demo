#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Soak and concurrency checks for the dump path.

  python tools/soak.py --serial <SN> --dumps 60
  python tools/soak.py --serial <SN> --writers 4

The first mode reports dump latency and failure rate; the second runs several
collectors against the same output file and verifies that no line is corrupted.
"""
import argparse
import json
import os
import statistics
import subprocess
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "lint", "collectors"))
from adbkit import adbkit as kit  # noqa: E402


def dump_soak(adb, serial, n):
    times, bad = [], 0
    for i in range(n):
        t0 = time.time()
        xml, why = kit.dump_current(adb, serial)
        dt = time.time() - t0
        if not xml:
            bad += 1
            print("  #%03d FAIL %s" % (i + 1, why))
        else:
            times.append(dt)
        if (i + 1) % 20 == 0:
            print("  ... %d/%d" % (i + 1, n))
    if times:
        times_sorted = sorted(times)
        p95 = times_sorted[int(len(times_sorted) * 0.95) - 1]
        print("dumps=%d ok=%d fail=%d mean=%.2fs p95=%.2fs max=%.2fs"
              % (n, len(times), bad, statistics.mean(times), p95, max(times)))
    # /sdcard 上的临时文件是否残留
    rc, out, _ = kit.adb_shell(adb, serial, "ls /sdcard/window_dump.xml /sdcard/dump.xml 2>/dev/null")
    left = len([l for l in out.splitlines() if l.strip()])
    print("leftover dump files on device: %d" % left)
    return 0 if bad == 0 and left == 0 else 1


def writer_soak(adb, serial, writers, out):
    """Lock contention: only one collector may own an output file.

    Concurrent appends are not atomic on Windows (two writers can seek to the same
    end), so the collector takes a lock file; the others must refuse with exit 4.
    """
    lock = out + ".lock"
    for path in (out, lock):
        if os.path.exists(path):
            os.remove(path)
    procs = []
    for _ in range(writers):
        procs.append(subprocess.Popen(
            [sys.executable, os.path.join(ROOT, "lint", "collectors", "collect_batch.py"),
             "--serial", serial, "--out", out, "--only", "settings-main"],
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, cwd=ROOT))
        time.sleep(0.4)          # 让第一个进程先拿到锁
    for p in procs:
        p.wait(timeout=300)
    codes = [p.returncode for p in procs]
    refused = sum(1 for c in codes if c == 4)
    ok_proc = sum(1 for c in codes if c == 0)
    left = os.path.exists(lock)
    lines = [l for l in open(out, encoding="utf-8") if l.strip()] if os.path.exists(out) else []
    bad = 0
    for l in lines:
        try:
            json.loads(l)
        except ValueError:
            bad += 1
    print("writers=%d exit=%s success=%d refused=%d lock_left=%s lines=%d corrupted=%d"
          % (writers, codes, ok_proc, refused, left, len(lines), bad))
    good = ok_proc == 1 and refused == writers - 1 and not left and bad == 0 and lines
    return 0 if good else 1


def append_race(writers, out, per_writer=50):
    """Informational: what concurrent appends do to one file without a lock."""
    os.makedirs(os.path.dirname(out) or ".", exist_ok=True)
    open(out, "w", encoding="utf-8").close()
    code = (
        "import json, sys\n"
        "fd = open(sys.argv[1], 'a', encoding='utf-8')\n"
        "for i in range(int(sys.argv[3])):\n"
        "    fd.write(json.dumps({'w': sys.argv[2], 'i': i}) + chr(10))\n"
        "    fd.flush()\n"
        "fd.close()\n"
    )
    procs = [subprocess.Popen([sys.executable, "-c", code, out, "w%d" % i, str(per_writer)], cwd=ROOT)
             for i in range(writers)]
    for p in procs:
        p.wait(timeout=120)
    lines = [l for l in open(out, encoding="utf-8") if l.strip()]
    bad = sum(1 for l in lines if not l.rstrip().endswith("}"))
    print("append race: writers=%d lines=%d expected=%d lost=%d corrupted=%d"
          % (writers, len(lines), writers * per_writer, writers * per_writer - len(lines), bad))
    return 0

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--serial")
    ap.add_argument("--adb")
    ap.add_argument("--dumps", type=int, default=0)
    ap.add_argument("--writers", type=int, default=0, help="锁竞争测试（需要设备）")
    ap.add_argument("--append-race", type=int, default=0, help="无锁并发追加（观察用）")
    ap.add_argument("--out", default=os.path.join(ROOT, "data", "soak.jsonl"))
    args = ap.parse_args()

    if args.append_race:
        return append_race(args.append_race, args.out)
    adb = kit.resolve_adb(args.adb)
    serial = kit.pick_device(adb, args.serial)
    if not serial:
        print("没有设备")
        return 2
    if args.writers:
        return writer_soak(adb, serial, args.writers, args.out)
    if args.dumps:
        kit.wake(adb, serial)
        return dump_soak(adb, serial, args.dumps)
    print("需要 --dumps 或 --writers")
    return 2


if __name__ == "__main__":
    sys.exit(main())