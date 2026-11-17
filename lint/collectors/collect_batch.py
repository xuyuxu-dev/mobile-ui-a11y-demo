#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
按 pages.json 批量采集（可复现：同样清单跑出同样页面集）。
只读：启动页面 + dump 统计，不点击、不输入。
"""
import argparse
import json
import os
import subprocess
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)
import adb_collect as ac  # noqa: E402


def launch(adb, serial, item, wait):
    if item.get("component"):
        ac.adb_shell(adb, serial, "am start -n %s" % item["component"])
    elif item.get("action"):
        ac.adb_shell(adb, serial, "am start -a %s" % item["action"])
    elif item.get("package"):
        ac.adb_shell(adb, serial, "monkey -p %s -c android.intent.category.LAUNCHER 1" % item["package"])
    else:
        return False
    time.sleep(wait)
    return True


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--serial")
    ap.add_argument("--adb")
    ap.add_argument("--pages", default=os.path.join(HERE, "pages.json"))
    ap.add_argument("--out", default=os.path.join(ROOT, "data", "lint.jsonl"))
    ap.add_argument("--wait", type=float, default=3.0)
    ap.add_argument("--only", help="只跑某个 label")
    ap.add_argument("--fresh", action="store_true", help="先清空输出文件（默认追加）")
    args = ap.parse_args()

    adb = ac.resolve_adb(args.adb)
    rc, out, err = ac.sh([adb, "devices"])
    serial = args.serial
    if not serial:
        for line in out.splitlines()[1:]:
            if "\tdevice" in line:
                serial = line.split("\t")[0]
                break
    if not serial:
        print("没有设备: %s" % err.strip(), file=sys.stderr)
        return 2

    with open(args.pages, "r", encoding="utf-8-sig") as f:
        pages = json.load(f)["pages"]

    density = ac.get_density(adb, serial)
    os.makedirs(os.path.dirname(args.out), exist_ok=True)
    if args.fresh and os.path.isfile(args.out):
        os.remove(args.out)
    ok = 0
    for item in pages:
        if args.only and item.get("label") != args.only:
            continue
        # 屏幕休眠会让 dump 返回空树或停在上一页，采集前先唤醒
        if not ac._kit.wake(adb, serial):
            print("SKIP %-14s 屏幕无法唤醒" % item.get("label"))
            continue
        if not launch(adb, serial, item, args.wait):
            continue
        xml_text, why = ac.dump_current(adb, serial)
        if not xml_text:
            print("SKIP %-14s %s" % (item.get("label"), why))
            continue
        try:
            rec = ac.parse_dump(xml_text, density)
        except ValueError as e:
            print("SKIP %-14s %s" % (item.get("label"), e))
            continue
        focus = ac.get_focus(adb, serial) or rec["page"]
        record = ac.make_record("adb", rec["pkg"], focus, rec["metrics"],
                                ac._kit.device_tag(ac._kit.hardware_id(adb, serial)),
                                item.get("label", ""))
        with open(args.out, "a", encoding="utf-8") as f:
            f.write(json.dumps(record, ensure_ascii=False) + "\n")
            f.flush()          # 中断时最多丢当前页，不留半行
        m = record["metrics"]
        print("%-14s %-52s nodes=%3d int=%2d unl=%2d small=%2d tiny=%2d"
              % (item.get("label"), focus.split("/")[-1][:50], m["nodes"], m["interactive"],
                 m["unlabeled"], m["undersized"], m.get("tiny", 0)))
        ok += 1
    print("\n完成 %d 页 -> %s" % (ok, args.out))
    return 0


if __name__ == "__main__":
    sys.exit(main())