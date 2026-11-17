#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
PC 侧采集通道：用 adb 的 uiautomator dump 读界面树，算出无障碍指标。

设计约束（与 demo 的架构纪律一致）：
  * 只读：不点击、不输入、不提交，只 dump 当前界面
  * 不绑定任何具体 App：包名/页面全部来自运行时，不写死
  * 只存统计值：JSON 里没有任何界面文本，避免隐私问题
输出符合 ../schema/sample.schema.json
"""
import argparse
import json
import os
import re
import subprocess
import sys
import time
import xml.etree.ElementTree as ET

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
DEMO = os.path.dirname(ROOT)
# 底层 adb 能力从公共包 adbkit 来，本文件只保留"指标"逻辑
if DEMO not in sys.path:
    sys.path.insert(0, DEMO)
from adbkit import adbkit as _kit  # noqa: E402


def resolve_adb(explicit=None):
    return _kit.resolve_adb(explicit)


def sh(args, timeout=30):
    return _kit.sh(args, timeout)


def adb_shell(adb, serial, cmd, timeout=30):
    return _kit.adb_shell(adb, serial, cmd, timeout)


def get_density(adb, serial):
    return _kit.get_density(adb, serial)


BOUNDS_RE = re.compile(r"\[(-?\d+),(-?\d+)\]\[(-?\d+),(-?\d+)\]")


def parse_bounds(s):
    return _kit.parse_bounds(s)


def is_interactive(node):
    a = node.attrib
    if a.get("clickable") == "true" or a.get("long-clickable") == "true":
        return True
    if a.get("checkable") == "true" or a.get("scrollable") == "true":
        return True
    return (a.get("class") or "").endswith("EditText")


def has_label(node):
    """自身或任一后代有文字/描述，就算"可被朗读"。
    只看自身会严重高估：真实界面里可点击的往往是容器（LinearLayout/FrameLayout），
    标签在子 TextView 上——第一版就是这么把不可读率算到 90%+ 的。"""
    a = node.attrib
    if (a.get("text") or "").strip() or (a.get("content-desc") or "").strip():
        return True
    for d in node.iter("node"):
        if d is node:
            continue
        b = d.attrib
        if (b.get("text") or "").strip() or (b.get("content-desc") or "").strip():
            return True
    return False


ROW_CONTROL = ("Switch", "CheckBox", "RadioButton", "SeekBar", "Image", "ToggleButton")


def build_parents(root):
    parents = {}
    for parent in root.iter("node"):
        for child in parent:
            if child.tag == "node":
                parents[child] = parent
    return parents


def row_labeled(node, parents, levels=2):
    """行级标签：向上找容器，若容器的子树里有文字/描述，认为该控件有行标签。
    典型场景：设置行的标题在左边 TextView，右边是 Switch——屏幕上读得出，
    但 dump 里两者是兄弟节点，只看自身/后代会把 Switch 误判为"无标签"。"""
    cls = (node.attrib.get("class") or "").split(".")[-1]
    if not any(k in cls for k in ROW_CONTROL):
        return False
    cur = node
    for _ in range(levels):
        parent = parents.get(cur)
        if parent is None:
            return False
        for d in parent.iter("node"):
            if d is node or d is cur:
                continue
            b = d.attrib
            if (b.get("text") or "").strip() or (b.get("content-desc") or "").strip():
                return True
        cur = parent
    return False


def label_distance(node, parents, max_levels=4):
    """返回标签距离：0=自身就有；n=向上第 n 层祖先（其子树里除自己这条链外）有文字；-1=都没有。
    这比"有/无标签"的二元判定更有信息量：标签离得越远，屏幕阅读器越可能读不出来。"""
    if has_label(node):
        return 0
    cur = node
    for lv in range(1, max_levels + 1):
        parent = parents.get(cur)
        if parent is None:
            return -1
        for d in parent.iter("node"):
            if d is node or d is cur:
                continue
            b = d.attrib
            if (b.get("text") or "").strip() or (b.get("content-desc") or "").strip():
                return lv
        cur = parent
    return -1


def parse_dump(xml_text, density=160.0):
    """把一页 dump 变成 metrics 字典（不含任何文本内容）。"""
    try:
        root = ET.fromstring(xml_text)
    except ET.ParseError as e:
        # 畸形/截断的 XML 不应该让整轮采集崩掉，交给调用方跳过这一页
        raise ValueError("XML 解析失败: %s" % e)
    px_per_dp = density / 160.0
    min_px = 48.0 * px_per_dp       # 48dp：无障碍建议的最小点击尺寸
    tiny_px = 24.0 * px_per_dp      # <24dp：多半是分隔条/装饰，单独统计，不算"过小"

    nodes = interactive = unlabeled = undersized = image_only = invisible = tiny = 0
    unlabeled_cls = {}
    unlabeled_row = 0
    dist = {0: 0, 1: 0, 2: 0, 3: 0, 4: 0, -1: 0}
    # package/class 在第一个 <node> 上，<hierarchy> 根节点没有
    first = root.find("node")
    pkg = (first.attrib.get("package") if first is not None else None) or "unknown"
    page = (first.attrib.get("class") if first is not None else None) or "unknown"

    parents = build_parents(root)
    for n in root.iter("node"):
        nodes += 1
        if not is_interactive(n):
            continue
        interactive += 1
        bb = parse_bounds(n.attrib.get("bounds"))
        zero_size = bool(bb) and (abs(bb[2] - bb[0]) == 0 or abs(bb[3] - bb[1]) == 0)
        if zero_size:
            invisible += 1
            # 不可见控件单独统计，不参与"无标签 / 过小"判定（现场核查：0x0 的 LinearLayout）
        else:
            d_lab = label_distance(n, parents)
            dist[d_lab] = dist.get(d_lab, 0) + 1
            if d_lab == -1:
                unlabeled += 1
                cls = n.attrib.get("class") or ""
                if "Image" in cls:
                    image_only += 1
                short = cls.split(".")[-1] or "Unknown"
                unlabeled_cls[short] = unlabeled_cls.get(short, 0) + 1
            if d_lab < 0 or d_lab > 2:
                unlabeled_row += 1
        b = parse_bounds(n.attrib.get("bounds"))
        if b and not zero_size:
            w = abs(b[2] - b[0])
            h = abs(b[3] - b[1])
            if w < min_px or h < min_px:
                if w < tiny_px or h < tiny_px:
                    tiny += 1          # 极薄/极小：现场核查过，多数是装饰条
                else:
                    undersized += 1    # 24dp~48dp：真实的"目标太小"

    return {
        "pkg": pkg,
        "page": page,
        "metrics": {
            "nodes": nodes,
            "interactive": interactive,
            "unlabeled": unlabeled,
            "undersized": undersized,
            "zero_node_page": nodes <= 2,
            # 自绘/图片化页面：整页没有任何可交互节点。
            # 注意：纯展示页（只有文字）也会命中，所以报告里要求"疑似"，需截图确认。
            "no_interactive": interactive == 0 and nodes > 0,
            "image_only": image_only,
            "invisible": invisible,
            "tiny": tiny,
            "unlabeled_classes": unlabeled_cls,
            # 行级判定之后才认为真的"无标签"（开关类控件多数有行标签）
            "unlabeled_strict": unlabeled_row,
            "label_dist": {"%d" % k: v for k, v in dist.items()},
        },
    }


def get_focus(adb, serial):
    """取当前前台组件名（pkg/Activity），作为页面标识。"""
    rc, out, _ = adb_shell(adb, serial, "dumpsys window windows | grep mCurrentFocus")
    if rc != 0:
        rc, out, _ = adb_shell(adb, serial, "dumpsys window | grep mCurrentFocus")
    m = re.search(r"([A-Za-z0-9_.]+)/([A-Za-z0-9_.$]+)", out or "")
    if m:
        return m.group(1) + "/" + m.group(2)
    return ""


def dump_current(adb, serial, xml_path="/sdcard/lint_dump.xml"):
    xml, why = _kit.dump_current(adb, serial, xml_path)
    return (xml, None) if xml else (None, why)


def make_record(source, pkg, page, metrics, device="", note=""):
    return {
        "schema": 1,
        "source": source,
        "device": device,
        "ts": int(time.time() * 1000),
        "pkg": pkg,
        "page": page,
        "metrics": metrics,
        "note": note,
    }


def main(argv=None):
    ap = argparse.ArgumentParser(description="采集一页界面并输出无障碍指标")
    ap.add_argument("--adb", help="adb 可执行文件路径")
    ap.add_argument("--serial", help="设备序列号（多设备时指定）")
    ap.add_argument("--out", default=os.path.join(ROOT, "data", "lint.jsonl"))
    ap.add_argument("--fixture", help="用本地 XML 代替真机（自测用）")
    ap.add_argument("--tag", default="", help="给这批数据打个标记")
    ap.add_argument("--shot", action="store_true", help="同时保存一张截图（仅本地，data/shots/）")
    args = ap.parse_args(argv)

    os.makedirs(os.path.dirname(args.out), exist_ok=True)
    adb = resolve_adb(args.adb)

    if args.fixture:
        with open(args.fixture, "r", encoding="utf-8-sig") as f:
            xml_text = f.read()
        density = 480.0
        device = "fixture"
    else:
        # 先确认设备在
        rc, out, err = sh([adb, "devices"])
        if rc != 0:
            print("adb 不可用: %s" % err.strip(), file=sys.stderr)
            return 2
        serial = args.serial
        if not serial:
            lines = [l.split("\t")[0] for l in out.splitlines()[1:] if "\tdevice" in l]
            if not lines:
                print("没有可用设备", file=sys.stderr)
                return 2
            serial = lines[0]
        density = get_density(adb, serial)
        xml_text, why = dump_current(adb, serial)
        if not xml_text:
            print(why, file=sys.stderr)
            return 3
        device = serial
        focus = get_focus(adb, serial)

    shot_rel = ""
    if args.shot and not args.fixture:
        shot_dir = os.path.join(ROOT, "data", "shots")
        os.makedirs(shot_dir, exist_ok=True)
        name = "shot-%d.png" % int(time.time() * 1000)
        rc3, _, _ = sh([adb] + (["-s", serial] if serial else []) +
                       ["exec-out", "screencap -p"], timeout=60)
        # exec-out 直接拿二进制更可靠，但 subprocess 这里用文件方式更简单
        rc4, _, _ = adb_shell(adb, serial, "screencap -p /sdcard/lint_shot.png", timeout=60)
        if rc4 == 0:
            rc5, _, _ = sh([adb] + (["-s", serial] if serial else []) +
                           ["pull", "/sdcard/lint_shot.png", os.path.join(shot_dir, name)], timeout=60)
            if rc5 == 0:
                shot_rel = "shots/" + name
    try:
        rec = parse_dump(xml_text, density)
    except ValueError as e:
        print(str(e), file=sys.stderr)
        return 4
    page = rec["page"]
    if not args.fixture:
        page = focus or page
    record = make_record("adb", rec["pkg"], page, rec["metrics"], device, args.tag)
    if shot_rel:
        record["shot"] = shot_rel
    with open(args.out, "a", encoding="utf-8") as f:
        f.write(json.dumps(record, ensure_ascii=False) + "\n")
    m = record["metrics"]
    print("[%s] %s / %s  nodes=%d interactive=%d unlabeled=%d undersized=%d tiny=%d invisible=%d zero=%s"
          % (record["source"], record["pkg"], record["page"],
             m["nodes"], m["interactive"], m["unlabeled"], m["undersized"],
             m.get("tiny", 0), m.get("invisible", 0), m["zero_node_page"]))
    return 0


if __name__ == "__main__":
    sys.exit(main())