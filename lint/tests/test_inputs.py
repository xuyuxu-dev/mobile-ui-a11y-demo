#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Input-handling contract: broken or empty datasets must fail closed, without tracebacks."""
import json
import os
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
PY = sys.executable


def run(script, *args):
    p = subprocess.run([PY, os.path.join(ROOT, script)] + list(args),
                       stdout=subprocess.PIPE, stderr=subprocess.PIPE, cwd=ROOT)
    return p.returncode, (p.stdout + p.stderr).decode("utf-8", "replace")


def write(path, text):
    with open(path, "w", encoding="utf-8") as f:
        f.write(text)


def main():
    tmp = tempfile.mkdtemp(prefix="lint-inputs-")
    empty = os.path.join(tmp, "empty.jsonl")
    write(empty, "")
    bad = os.path.join(tmp, "bad.jsonl")
    write(bad, "not json\n{\"schema\": 1, \"ts\": 1")
    cut = os.path.join(tmp, "cut.jsonl")
    good = os.path.join(tmp, "good.jsonl")
    run("lint/collectors/adb_collect.py", "--fixture", "lint/fixtures/normal.xml", "--out", good)
    with open(good, encoding="utf-8") as f:
        first = f.readline().strip()
    write(cut, first + "\n" + first[:60])

    cases = [
        ("analyze empty", ("lint/analyze/analyze.py", empty, "--outdir", os.path.join(tmp, "o1")), 2),
        ("analyze all-bad", ("lint/analyze/analyze.py", bad, "--outdir", os.path.join(tmp, "o2")), 2),
        ("schema empty", ("lint/tests/schema_check.py", empty), 1),
        ("privacy empty", ("lint/tests/privacy_scan.py", empty), 1),
        ("schema truncated line", ("lint/tests/schema_check.py", cut), 1),
        ("privacy truncated line", ("lint/tests/privacy_scan.py", cut), 1),
        ("baseline malformed", ("lint/tests/baseline_check.py", bad), 2),
        ("analyze valid", ("lint/analyze/analyze.py", good, "--outdir", os.path.join(tmp, "o3")), 0),
    ]
    failed = 0
    for name, args, want in cases:
        code, out = run(*args)
        ok = code == want and "Traceback" not in out
        print("%-4s %-28s exit=%d want=%d" % ("ok" if ok else "FAIL", name, code, want))
        if not ok:
            failed += 1
            tail = (out.strip().splitlines() or [""])[-1][:120]
            print("     " + tail)
    print("input contract: %d/%d" % (len(cases) - failed, len(cases)))
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())