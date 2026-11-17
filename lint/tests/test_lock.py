#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Lock contract: exactly one writer per output file, and never a silent partial run."""
import json
import os
import subprocess
import sys
import tempfile
import time

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, os.path.join(ROOT, "lint", "collectors"))
import lockfile  # noqa: E402

HOLDER = (
    "import json, sys, time\n"
    "sys.path.insert(0, sys.argv[3])\n"
    "import lockfile\n"
    "got = lockfile.acquire(sys.argv[1])\n"
    "print(json.dumps({'ok': got['ok'], 'holder': got['holder']}))\n"
    "sys.stdout.flush()\n"
    "if got['ok']:\n"
    "    time.sleep(float(sys.argv[2]))\n"
    "    lockfile.release(got['lock'])\n"
)


def spawn(out, hold, tag):
    p = subprocess.Popen([sys.executable, "-c", HOLDER, out, str(hold), os.path.join(ROOT, "lint", "collectors")],
                         stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    line = p.stdout.readline().decode().strip()
    return p, json.loads(line) if line else {"ok": None}


def main():
    tmp = tempfile.mkdtemp(prefix="lock-test-")
    out = os.path.join(tmp, "data.jsonl")
    open(out, "w").close()

    results = []

    # 1. acquire / release / re-acquire
    a = lockfile.acquire(out)
    ok1 = a["ok"] and os.path.isfile(out + ".lock")
    lockfile.release(a["lock"])
    b = lockfile.acquire(out)
    ok2 = b["ok"] and not os.path.isfile(out + ".lock") is False
    lockfile.release(b["lock"])
    results.append(("acquire and release", ok1 and ok2))

    # 2. second acquire is refused and reports the holder pid
    held = lockfile.acquire(out)
    second = lockfile.acquire(out)
    ok3 = (not second["ok"]) and second["holder"] == str(os.getpid())
    lockfile.release(held["lock"])
    results.append(("second writer refused", ok3))

    # 3. force takes over a stale lock
    with open(out + ".lock", "w", encoding="utf-8") as f:
        f.write("999999")
    forced = lockfile.acquire(out, force=True)
    ok4 = forced["ok"] and forced["forced"]
    lockfile.release(forced["lock"])
    results.append(("force takes over", ok4))

    # 4. three concurrent holders: exactly one wins while the lock is held
    procs = [spawn(out, 0.6, "p%d" % i) for i in range(3)]
    wins = [d for _, d in procs if d.get("ok")]
    losses = [d for _, d in procs if d.get("ok") is False]
    for p, _ in procs:
        p.wait(timeout=30)
    ok5 = len(wins) == 1 and len(losses) == 2
    results.append(("concurrent: one winner", ok5))

    # 5. after everyone exits the lock is gone and can be taken again
    again = lockfile.acquire(out)
    ok6 = again["ok"]
    lockfile.release(again["lock"])
    results.append(("lock released after runs", ok6))

    bad = 0
    for name, ok in results:
        print("%-4s %s" % ("ok" if ok else "FAIL", name))
        if not ok:
            bad += 1
    print("lock contract: %d/%d" % (len(results) - bad, len(results)))
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())