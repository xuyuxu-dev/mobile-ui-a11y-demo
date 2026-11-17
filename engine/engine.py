#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
最小流程引擎：一份 JSON 流程 -> adb 执行。

设计约束：
  * 默认 dry-run（只解析/定位，不点击），加 --allow-taps 才真的点
  * 没有固定 sleep：用 wait_text 等界面出现（状态轮询）
  * 每步一条 trace，失败立即停并报出"哪一步、期望什么、当时有什么"
  * 只做导航类操作，不做提交/支付类动作（能力白名单）
"""
import argparse
import json
import os
import re
import sys
import time
import xml.etree.ElementTree as ET

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(os.path.dirname(ROOT), ""))
from adbkit import adbkit as ac  # noqa: E402
import ocr as ocr_mod  # noqa: E402

POLL_MS = 400
DEFAULT_TIMEOUT = 8000

# 流程里的 component/action/package 会被拼进 `adb shell` 命令，
# 必须严格限制字符集——否则一个恶意流程就能在设备上执行任意 shell 命令。
SAFE_TARGET = re.compile(r"^[A-Za-z0-9_.]+(?::[A-Za-z0-9_]+)?(?:/[A-Za-z0-9_.$]+)?$")
OPS = {"launch", "wait_text", "assert_text", "wait_gone", "tap_text", "tap_ocr_text",
       "ocr_contains", "assert_changed", "assert_stable", "back", "home"}


def load_capabilities():
    path = os.path.join(HERE, "capabilities.json")
    if not os.path.isfile(path):
        return None
    with open(path, "r", encoding="utf-8-sig") as f:
        return json.load(f)


def check_target(kind, value, caps, allow_any=False):
    """kind: action / package / component。默认拒绝未登记的目标。"""
    if allow_any or caps is None:
        return
    if kind == "action":
        if not any(value.startswith(p) for p in caps.get("actions", [])):
            raise ValueError("动作未授权: %s（见 capabilities.json）" % value)
    elif kind == "package":
        if value not in caps.get("packages", []):
            raise ValueError("包名未授权: %s（见 capabilities.json）" % value)
        # 按包名启动会落到任意页面，绕过页面级限制；这类包必须显式写 component
        if (caps.get("page_allowlist") or {}).get(value):
            raise ValueError("包 %s 需要显式指定 component，不能按包名启动" % value)
    elif kind == "component":
        if value not in caps.get("components", []):
            raise ValueError("组件未授权: %s（见 capabilities.json）" % value)
        pkg = value.split("/")[0]
        per_page = (caps.get("page_allowlist") or {}).get(pkg)
        if per_page and value not in per_page:
            raise ValueError("该包只允许指定页面: %s（见 capabilities.json）" % pkg)


def validate_flow(flow, caps=None, allow_any=False):
    if not isinstance(flow.get("steps"), list):
        raise ValueError("steps 必须是数组")
    """加载期就校验：未知 op 直接失败；目标字段必须匹配安全字符集并通过白名单。"""
    if not isinstance(flow, dict) or not isinstance(flow.get("steps"), list):
        raise ValueError("流程格式错误：需要 {steps: [...]}")
    for i, step in enumerate(flow["steps"], 1):
        op = step.get("op")
        if op not in OPS:
            raise ValueError("第 %d 步：未知操作 %r" % (i, op))
        for k in ("component", "action", "package"):
            v = step.get(k)
            if not v:
                continue
            if not SAFE_TARGET.match(str(v)):
                raise ValueError("第 %d 步：%s 含非法字符 %r" % (i, k, v))
            check_target(k, v, caps, allow_any)
    return True


def screen_hash(adb, serial):
    """截图哈希走公共包 adbkit，保持两个包同一实现。"""
    return ac.screen_hash(adb, serial)


def bounds_center(bounds):
    x1, y1, x2, y2 = bounds
    return (x1 + x2) // 2, (y1 + y2) // 2


def find_text(root, text):
    """返回第一个 text 或 content-desc 等于/包含 text 的节点。"""
    for n in root.iter("node"):
        a = n.attrib
        t = (a.get("text") or "").strip()
        d = (a.get("content-desc") or "").strip()
        if t == text or d == text or (text in t) or (text in d):
            b = ac.parse_bounds(a.get("bounds"))
            if b:
                return n, b
    return None, None


class Runner:
    def __init__(self, adb, serial, allow_taps, trace_path, faults=None, redact=False):
        self.adb = adb
        self.serial = serial
        self.allow_taps = allow_taps
        self.trace_path = trace_path
        self.log = []
        self.dry_stopped = False   # dry-run 遇到第一次点击后，后续步标记为 SKIP
        self.faults = faults or {}
        self.redact = redact
        self.dump_count = 0
        self.dump_fail = 0

    @staticmethod
    def _redact(detail):
        """把可能来自**页面**的文字去掉：引号内的、OCR 命中的、未找到的目标。
        界面文字属于用户数据，分享 trace 时应开启。"""
        if not detail:
            return detail
        s = re.sub(r"「[^」]*」", "「…」", detail)
        s = re.sub(r"(未找到[:：]\s*)\S+", r"\1<text>", s)
        s = re.sub(r"(点击 \([-\d,]+\) )(\S+)", r"\1<text>", s)
        return s

    def trace(self, step_idx, op, ok, detail):
        if self.redact:
            detail = self._redact(detail)
        rec = {"ts": int(time.time() * 1000), "step": step_idx, "op": op,
               "ok": ok, "detail": detail}
        self.log.append(rec)
        with open(self.trace_path, "a", encoding="utf-8") as f:
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")
        print("%-2d %-14s %s  %s" % (step_idx, op, "OK  " if ok else "FAIL", detail))

    def dump(self):
        """读界面树；这里也是故障注入点（延迟 / 随机丢节点）。"""
        self.dump_count += 1
        delay = float(self.faults.get("delay", 0)) / 1000.0
        if delay > 0:
            time.sleep(delay)
        xml, why = ac.dump_current(self.adb, self.serial)
        if not xml:
            self.dump_fail += 1
            return None, why
        root = ET.fromstring(xml)
        hide = self.faults.get("hide")
        if hide:
            # 精确定向故障：把包含指定文字的节点整棵摘掉，模拟"这个锚点永远不出现"
            target = str(hide)
            for parent in list(root.iter("node")):
                for child in list(parent):
                    if child.tag != "node":
                        continue
                    a = child.attrib
                    if target in (a.get("text") or "") or target in (a.get("content-desc") or ""):
                        parent.remove(child)
            self.effective_drop = 1.0

        drop = float(self.faults.get("drop", 0))
        if drop > 0:
            # 模拟"只读到部分树"：只删**叶子**节点。
            # 删父节点会连带整棵子树，实际损失远大于设定值——第一版就是这么把 10% 变成 60%+ 的。
            # 持久故障：按叶子位置固定丢弃，而不是每次随机。
            # 随机丢会被"轮询重试"吸收掉，测不出问题（第一版基准全是 100%）。
            before = sum(1 for _ in root.iter("node"))
            leaves = [n for n in root.iter("node") if len(list(n)) == 0]
            step = int(round(1.0 / drop)) if drop > 0 else 0
            removed = 0
            for idx, n in enumerate(leaves):
                if step and idx % step == 0:
                    for parent in root.iter("node"):
                        if n in list(parent):
                            parent.remove(n)
                            removed += 1
                            break
            after = sum(1 for _ in root.iter("node"))
            self.effective_drop = (before - after) / float(max(1, before))
        return root, ""

    def wait_text(self, text, timeout=DEFAULT_TIMEOUT):
        """状态轮询直到文字出现；不 sleep 固定时长。"""
        deadline = time.time() + timeout / 1000.0
        last = ""
        while time.time() < deadline:
            root, why = self.dump()
            if root is None:
                last = why
            else:
                node, b = find_text(root, text)
                if node is not None:
                    return node, b
                last = "未找到: %s" % text
            time.sleep(POLL_MS / 1000.0)
        return None, last or "超时"

    def run(self, flow):
        for i, step in enumerate(flow["steps"], 1):
            op = step.get("op")
            if op == "assert_changed":
                step["_hash"] = screen_hash(self.adb, self.serial)   # 动作前的基准
            if self.dry_stopped and op != "launch":
                self.trace(i, op, True, "SKIP（dry-run 未实际点击）")
                continue
            if op == "launch":
                target = step.get("action") or step.get("component") or step.get("package")
                if step.get("action"):
                    ac.adb_shell(self.adb, self.serial, "am start -a %s" % step["action"])
                elif step.get("component"):
                    ac.adb_shell(self.adb, self.serial, "am start -n %s" % step["component"])
                else:
                    ac.adb_shell(self.adb, self.serial, "monkey -p %s -c android.intent.category.LAUNCHER 1" % step["package"])
                if step.get("settle_text"):
                    node, info = self.wait_text(step["settle_text"])
                    if node is None:
                        self.trace(i, op, False, "启动后未等到 %s（%s）" % (step["settle_text"], info))
                        return False
                self.trace(i, op, True, target)
            elif op == "wait_text":
                node, info = self.wait_text(step["text"])
                ok = node is not None
                self.trace(i, op, ok, step["text"] if ok else "未等到 %s（%s）" % (step["text"], info))
                if not ok:
                    return False
            elif op == "assert_text":
                node, info = self.wait_text(step["text"], timeout=step.get("timeout", DEFAULT_TIMEOUT))
                ok = node is not None
                self.trace(i, op, ok, step.get("desc", step["text"]) + ("（未出现）" if not ok else ""))
                if not ok:
                    return False
            elif op == "tap_text":
                node, info = self.wait_text(step["text"])
                if node is None:
                    self.trace(i, op, False, "找不到可点击目标 %s（%s）" % (step["text"], info))
                    return False
                b = ac.parse_bounds(node.attrib.get("bounds"))
                if not b:
                    self.trace(i, op, False, "目标没有 bounds: %s" % step["text"])
                    return False
                x, y = bounds_center(b)
                if not self.allow_taps:
                    self.trace(i, op, True, "[dry-run] 将点击 (%d,%d) %s" % (x, y, step["text"]))
                    self.dry_stopped = True   # 之后依赖界面变化的步骤只做标记
                    continue
                else:
                    ac.adb_shell(self.adb, self.serial, "input tap %d %d" % (x, y))
                    self.trace(i, op, True, "点击 (%d,%d) %s" % (x, y, step["text"]))
                if step.get("settle_text"):
                    node2, info2 = self.wait_text(step["settle_text"])
                    if node2 is None:
                        self.trace(i, op, False, "点击后未等到 %s（%s）" % (step["settle_text"], info2))
                        return False
            elif op == "tap_ocr_text":
                # OCR 通道点击：截图 → OCR 词框 → 点击该词中心。
                # 用于"无障碍树没有文字、但画面上有文字"的按钮。
                shot = os.path.join(ROOT, "data", "ocr-tap-%d.png" % i)
                if not ac.save_screencap(self.adb, self.serial, shot):
                    self.trace(i, op, False, "截图失败")
                    return False
                lang, words = ocr_mod.ocr_words(shot)
                if words is None:
                    self.trace(i, op, False, "OCR 失败: %s" % lang)
                    return False
                w = ocr_mod.find_word(words, step["text"], fuzzy=True)
                if not w:
                    self.trace(i, op, False, "OCR 未找到「%s」（共 %d 个词）" % (step["text"], len(words)))
                    return False
                cx = w["x"] + w["w"] // 2
                cy = w["y"] + w["h"] // 2
                if not self.allow_taps:
                    self.trace(i, op, True, "[dry-run] 将点击 OCR 词「%s」(%d,%d)" % (w["text"], cx, cy))
                    self.dry_stopped = True
                    continue
                ac.adb_shell(self.adb, self.serial, "input tap %d %d" % (cx, cy))
                self.trace(i, op, True, "点击 OCR 词「%s」(%d,%d)" % (w["text"], cx, cy))

            elif op == "ocr_contains":
                # 视觉-文字通道：截图 → OCR → 断言包含某段文字。
                # 用于无障碍树里根本没有文字的页面（Canvas/图片化界面）。
                shot = os.path.join(ROOT, "data", "ocr-step-%d.png" % i)
                if not ac.save_screencap(self.adb, self.serial, shot):
                    self.trace(i, op, False, "截图失败")
                    return False
                raw, norm = ocr_mod.ocr_image(shot)
                if raw is None:
                    self.trace(i, op, False, "OCR 失败: %s" % norm)
                    return False
                ok = ocr_mod.contains(raw, step["text"])
                self.trace(i, op, ok, ("OCR 命中「%s」" % step["text"]) if ok
                           else ("OCR 未命中「%s」，实际前 60 字: %s" % (step["text"], norm[:60])))
                if not ok:
                    return False

            elif op == "wait_gone":
                deadline = time.time() + step.get("timeout", DEFAULT_TIMEOUT) / 1000.0
                gone = False
                while time.time() < deadline:
                    root, _ = self.dump()
                    if root is None:
                        time.sleep(POLL_MS / 1000.0)
                        continue
                    node, _ = find_text(root, step["text"])
                    if node is None:
                        gone = True
                        break
                    time.sleep(POLL_MS / 1000.0)
                self.trace(i, op, gone, ("%s 已消失" % step["text"]) if gone
                           else ("%s 仍在" % step["text"]))
                if not gone:
                    return False

            elif op == "assert_changed":
                # 视觉通道：截图哈希判断"画面变了没有"，完全不依赖无障碍树。
                before = step.get("_hash") or screen_hash(self.adb, self.serial)
                deadline = time.time() + step.get("timeout", DEFAULT_TIMEOUT) / 1000.0
                changed = False
                while time.time() < deadline:
                    time.sleep(POLL_MS / 1000.0)
                    h = screen_hash(self.adb, self.serial)
                    if h and h != before:
                        changed = True
                        break
                self.trace(i, op, changed, "画面已变化" if changed else "画面未变化（期望变化）")
                if not changed:
                    return False

            elif op == "assert_stable":
                # "稳定"= 连续两帧哈希相同（不是"整段时间都不变"，那对有动画的页面不成立）
                deadline = time.time() + step.get("timeout", DEFAULT_TIMEOUT) / 1000.0
                prev = screen_hash(self.adb, self.serial)
                stable = False
                while time.time() < deadline:
                    time.sleep(POLL_MS / 1000.0)
                    h = screen_hash(self.adb, self.serial)
                    if h and prev and h == prev:
                        stable = True
                        break
                    prev = h
                self.trace(i, op, stable, "连续两帧一致" if stable else "画面持续变化（期望稳定）")
                if not stable:
                    return False

            elif op == "back":
                ac.adb_shell(self.adb, self.serial, "input keyevent 4")
                self.trace(i, op, True, "返回")
            elif op == "home":
                ac.adb_shell(self.adb, self.serial, "input keyevent 3")
                self.trace(i, op, True, "回到桌面")
            else:
                self.trace(i, op, False, "未知操作: %r" % op)
                return False
        return True


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("flow")
    ap.add_argument("--serial")
    ap.add_argument("--adb")
    ap.add_argument("--allow-taps", action="store_true", help="真的点击（默认 dry-run）")
    ap.add_argument("--trace", default=os.path.join(ROOT, "data", "engine-trace.jsonl"))
    ap.add_argument("--redact", dest="redact", action="store_true", default=True,
                    help="trace 脱敏（默认开启）")
    ap.add_argument("--no-redact", dest="redact", action="store_false",
                    help="trace 记录原始文字（仅本地调试）")
    ap.add_argument("--allow-any", action="store_true",
                    help="跳过能力白名单（危险：允许驱动任意应用）")
    ap.add_argument("--fault", action="append", default=[],
                    help="故障注入，可多次：delay=800 / drop=0.2")
    args = ap.parse_args()

    try:
        with open(args.flow, "r", encoding="utf-8-sig") as f:
            flow = json.load(f)
    except OSError as e:
        print("无法读取流程文件：%s（%s）" % (args.flow, e), file=sys.stderr)
        return 2
    except ValueError as e:
        print("流程文件不是合法 JSON：%s（%s）" % (args.flow, e), file=sys.stderr)
        return 2

    caps = load_capabilities()
    try:
        validate_flow(flow, caps, getattr(args, "allow_any", False))
    except ValueError as e:
        print("流程被拒绝：%s" % e, file=sys.stderr)
        return 6

    adb = ac.resolve_adb(args.adb)
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
    rc, state, _ = ac.sh([adb, "-s", serial, "get-state"])
    if state.strip() != "device":
        print("设备不可用：%s（%s）" % (serial, (state or "offline").strip()), file=sys.stderr)
        return 3

    os.makedirs(os.path.dirname(args.trace), exist_ok=True)
    print("flow: %s  设备: %s  模式: %s" % (flow.get("name"), serial,
          "真点击" if args.allow_taps else "dry-run"))
    faults = {}
    for item in args.fault:
        k, _, v = item.partition("=")
        faults[k.strip()] = float(v)
    runner = Runner(adb, serial, args.allow_taps, args.trace, faults, args.redact)
    ok = runner.run(flow)
    if faults:
        print("故障注入: %s  dump 次数=%d 失败=%d" % (faults, runner.dump_count, runner.dump_fail))
    print("\n%s" % ("流程通过" if ok else "流程失败"))
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())