#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""CLI contract tests: invalid input must fail with the documented exit code, not a traceback."""
import json
import os
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
ENGINE = os.path.dirname(HERE)
ENGINE_PY = os.path.join(ENGINE, "engine.py")


def run_flow(text=None, path=None):
    if path is None:
        fd, path = tempfile.mkstemp(suffix=".json")
        os.close(fd)
        with open(path, "w", encoding="utf-8") as f:
            f.write(text)
    p = subprocess.run([sys.executable, ENGINE_PY, path, "--serial", "TESTSERIAL"],
                       stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    out = (p.stdout + p.stderr).decode("utf-8", "replace")
    if path != text:
        try:
            os.remove(path)
        except OSError:
            pass
    return p.returncode, out


CASES = [
    ("missing file", None, 2),
    ("invalid json", "{", 2),
    ("steps not a list", '{"steps": "abc"}', 6),
    ("unknown op", '{"steps":[{"op":"no_such_op"}]}', 6),
    ("injection", '{"steps":[{"op":"launch","component":"com.a/.B; id"}]}', 6),
    ("unauthorised package", '{"steps":[{"op":"launch","package":"com.tencent.mm"}]}', 6),
    ("package-only launch on a page-restricted package",
     '{"steps":[{"op":"launch","package":"com.demo.canvas"}]}', 6),
    ("component outside the allowlist",
     '{"steps":[{"op":"launch","component":"com.demo.canvas/.OtherActivity"}]}', 6),
]


def main():
    bad = 0
    for name, flow, want in CASES:
        if flow is None:
            path = os.path.join(tempfile.gettempdir(), "definitely-missing-flow.json")
            code, out = run_flow(None, path)
        else:
            code, out = run_flow(flow)
        ok = code == want and "Traceback" not in out
        print("%-4s %-52s exit=%d want=%d" % ("ok" if ok else "FAIL", name, code, want))
        if not ok:
            bad += 1
            print("     " + out.strip().splitlines()[-1][:120] if out.strip() else "")
    print("cli contract: %d/%d" % (len(CASES) - bad, len(CASES)))
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())