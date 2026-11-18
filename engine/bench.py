#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
故障注入基准：同一流程在不同故障下重复跑 N 次，统计成功率。

故障类型：
  delay=ms   每次读界面额外延迟（模拟卡顿/慢渲染）
  drop=0..1  按叶子位置**固定**丢弃一部分节点（模拟"某些内容从不暴露"）

输出 docs/BENCH.md 与 data/bench.jsonl。
"""
import argparse
import json
import os
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
DEMO = os.path.dirname(HERE)
sys.path.insert(0, DEMO)
sys.path.insert(0, HERE)
from adbkit import adbkit as ac  # noqa: E402
import uiauto  # noqa: E402
import engine as eng  # noqa: E402

PROFILES_PATH = os.path.join(HERE, "bench-profiles.json")
try:
    with open(PROFILES_PATH, encoding="utf-8") as f:
        _profiles = json.load(f)
    PROFILES = [(name, cfg) for name, cfg in _profiles.items()]
except (OSError, ValueError):
    PROFILES = [("clean", {}), ("delay500", {"delay_ms": 500}),
                ("drop30", {"leaf_drop_pct": 30}), ("drop60", {"leaf_drop_pct": 60})]

def ensure_settings(adb, serial):
    """Bring Settings to the foreground (uiauto handles the retry and the focus poll)."""
    uiauto.launch_action(adb, serial, "android.settings.SETTINGS",
                         expect_package="com.android.settings")
    return uiauto.wait_foreground(adb, serial, "com.android.settings", timeout_ms=3000)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--serial")
    ap.add_argument("--n", type=int, default=5)
    ap.add_argument("--flow", default=os.path.join(HERE, "flows", "bench-probe.json"))
    ap.add_argument("--publish", action="store_true",
                    help="写入 docs/BENCH.md（默认只写 engine/data/，避免失败的运行覆盖已发布结果）")
    args = ap.parse_args()

    adb = ac.resolve_adb(None)
    serial = args.serial
    if not serial:
        rc, out, _ = ac.sh([adb, "devices"])
        for line in out.splitlines()[1:]:
            if "\tdevice" in line:
                serial = line.split("\t")[0]
                break
    if not serial:
        print("没有设备", file=sys.stderr)
        return 2

    with open(args.flow, encoding="utf-8-sig") as f:
        flow = json.load(f)

    if not ensure_settings(adb, serial):
        print("cannot bring Settings to the foreground (device locked or busy)", file=sys.stderr)
        return 4

    os.makedirs(os.path.join(HERE, "data"), exist_ok=True)
    trace = os.path.join(HERE, "data", "bench-trace.jsonl")
    rows = []
    for name, faults in PROFILES:
        ok_n, dumps, eff, t0 = 0, 0, [], time.time()
        for i in range(args.n):
            ac.wake(adb, serial)       # wake per run: the screen may time out mid-benchmark
            r = eng.Runner(adb, serial, False, trace, faults)
            ok = r.run(flow)
            ok_n += 1 if ok else 0
            dumps += r.dump_count
            eff.append(getattr(r, "effective_drop", 0.0))
            with open(os.path.join(HERE, "data", "bench.jsonl"), "a", encoding="utf-8") as f:
                f.write(json.dumps({"profile": name, "run": i + 1, "ok": bool(ok),
                                    "dumps": r.dump_count,
                                    "eff_drop": getattr(r, "effective_drop", 0.0)},
                                   ensure_ascii=False) + "\n")
        dt = time.time() - t0
        row = {"profile": name, "n": args.n, "ok": ok_n, "rate": 100.0 * ok_n / args.n,
               "avg_dumps": dumps / float(args.n), "eff_drop": sum(eff) / len(eff),
               "avg_sec": dt / args.n}
        rows.append(row)
        print("%-22s %d/%d %5.1f%%  drop实际=%.0f%%  dumps/run=%.1f  %.1fs/run"
              % (name, ok_n, args.n, row["rate"], row["eff_drop"] * 100,
                 row["avg_dumps"], row["avg_sec"]))

    out_dir = os.path.join(DEMO, "docs") if args.publish else os.path.join(HERE, "data")
    os.makedirs(out_dir, exist_ok=True)
    L = ["# 故障注入基准", "",
         "同一流程（等待并断言两个文字）在 5 种故障下各跑 %d 次。" % args.n, "",
         "| 故障 | 实际丢节点 | 成功 | 成功率 | 平均读树次数 | 平均耗时 |",
         "|---|---|---|---|---|---|"]
    for r in rows:
        L.append("| %s | %.0f%% | %d/%d | **%.0f%%** | %.1f | %.1fs |" % (
            r["profile"], r["eff_drop"] * 100, r["ok"], r["n"], r["rate"],
            r["avg_dumps"], r["avg_sec"]))
    L += ["", "## 怎么读这张表", "",
          "- `delay` 不影响成功率 → 超时预算够用，不是靠固定 sleep",
          "- `drop` 掉成功率 → **读一次树不够**：需要重试，或对关键节点做多帧聚合",
          "- 故障是**持久**的（同一次运行固定丢同一批叶子节点）；随机丢会被轮询重试吸收，" +
          "第一版基准因此全是 100%（踩过的坑记在这里）",
          "- `hide` 是定向故障：证明框架能明确报出\"第几步、缺什么\"，而不是静默点错",
          "- 样本量小（n=%d），只说明趋势，不当作精确概率" % args.n,
          "", "复现：`python engine/bench.py --serial <SN> --n 5`", ""]
    with open(os.path.join(out_dir, "BENCH.md"), "w", encoding="utf-8") as f:
        f.write("\n".join(L) + "\n")
    print("\n写入 %s" % os.path.join(out_dir, "BENCH.md"))
    return 0


if __name__ == "__main__":
    sys.exit(main())