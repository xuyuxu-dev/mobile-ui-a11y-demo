#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ADR-01 判定实验：`uiautomator dump`（PC 侧）与**实时无障碍树**（端侧）差多少？

需要先启用随包提供的只读计数服务 com.demo.a11ycount/.CountService：
    settings put secure enabled_accessibility_services <原值>:com.demo.a11ycount/.CountService
实验结束务必还原（脚本不负责改设置，避免误伤生产无障碍服务）。

输出：data/endchannel.jsonl + 终端表格
"""
import argparse
import json
import os
import subprocess
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "engine"))
sys.path.insert(0, os.path.join(ROOT, "lint", "collectors"))
from adbkit import adbkit as kit  # noqa: E402
import adb_collect as ac  # noqa: E402

COUNT_PATH = "/sdcard/Android/data/com.demo.a11ycount/files/count.json"
_ALIASES = {}
try:
    import uiauto
    _ALIASES = uiauto.load_aliases()
except Exception:
    pass
PAGES = [
    ("设置主页", {"action": "android.settings.SETTINGS"}),
    ("显示", {"action": "android.settings.DISPLAY_SETTINGS"}),
    ("WiFi", {"action": "android.settings.WIFI_SETTINGS"}),
    ("应用", {"action": "android.settings.APPLICATION_SETTINGS"}),
    ("计算器", {"package": "com.vendor.calculator"}),
    ("自绘夹具", {"component": "com.demo.canvas/.MainActivity"}),
]
# 占位包名在本地映射成真实包名
PAGES = [(label, {k: _ALIASES.get(v, v) for k, v in cfg.items()}) for label, cfg in PAGES]


def run(cmd):
    return subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=60)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--serial")
    ap.add_argument("--out", default=os.path.join(HERE, "data", "endchannel.jsonl"))
    args = ap.parse_args()

    adb = kit.resolve_adb()
    serial = kit.pick_device(adb, args.serial)
    if not serial:
        print("没有设备")
        return 2
    density = kit.get_density(adb, serial)
    os.makedirs(os.path.dirname(args.out), exist_ok=True)

    rows = []
    for label, target in PAGES:
        if "action" in target:
            run([adb, "-s", serial, "shell", "am start -a %s" % target["action"]])
        elif "component" in target:
            run([adb, "-s", serial, "shell", "am start -n %s" % target["component"]])
        else:
            run([adb, "-s", serial, "shell",
                 "monkey -p %s -c android.intent.category.LAUNCHER 1" % target["package"]])
        time.sleep(2.5)

        xml, why = kit.dump_current(adb, serial)
        if not xml:
            print("SKIP %-8s dump 失败: %s" % (label, why))
            continue
        try:
            m = ac.parse_dump(xml, density)["metrics"]
        except ValueError as e:
            print("SKIP %-8s %s" % (label, e))
            continue

        # 让端侧服务重新计数
        run([adb, "-s", serial, "shell", "am broadcast -a com.demo.a11ycount.COUNT"])
        time.sleep(0.6)
        rc, out, _ = kit.adb_shell(adb, serial, "cat %s" % COUNT_PATH)
        a_nodes = a_int = -1
        if rc == 0 and out.strip().startswith("{"):
            try:
                obj = json.loads(out.strip())
                a_nodes = int(obj.get("nodes", -1))
                a_int = int(obj.get("interactive", -1))
            except ValueError:
                pass

        row = {"page": label, "dump_nodes": m["nodes"], "dump_interactive": m["interactive"],
               "a11y_nodes": a_nodes, "a11y_interactive": a_int,
               "node_diff": (a_nodes - m["nodes"]) if a_nodes >= 0 else None}
        rows.append(row)
        print("%-8s dump=%3d/%2d  端侧=%3d/%2d  差值=%s"
              % (label, m["nodes"], m["interactive"], a_nodes, a_int,
                 ("%+d" % row["node_diff"]) if row["node_diff"] is not None else "n/a"))

    with open(args.out, "w", encoding="utf-8") as f:
        for r in rows:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")

    valid = [r for r in rows if r["node_diff"] is not None]
    if valid:
        diffs = sorted(abs(r["node_diff"]) for r in valid)
        mid = diffs[len(diffs) // 2]
        rel = [abs(r["node_diff"]) / max(1, r["dump_nodes"]) * 100 for r in valid]
        rel.sort()
        print("\n有效样本 %d 页；差值中位数 %d 个节点，相对中位数 %.1f%%"
              % (len(valid), mid, rel[len(rel) // 2]))
        print("ADR-01 门槛（差异中位数 ≥10%% 才做端侧通道）：%s"
              % ("达到" if rel[len(rel) // 2] >= 10 else "未达到"))
    return 0


if __name__ == "__main__":
    sys.exit(main())