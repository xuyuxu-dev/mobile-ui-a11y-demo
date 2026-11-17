#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""最小 schema 校验：字段存在性、类型、枚举、metrics 子字段。不依赖第三方库。"""
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
REQ = ["schema", "source", "ts", "pkg", "page", "metrics"]
METRIC_INT = ["nodes", "interactive", "unlabeled", "undersized"]
METRIC_BOOL = ["zero_node_page"]


def check(rec):
    errs = []
    for k in REQ:
        if k not in rec:
            errs.append("缺少字段 %s" % k)
    if rec.get("schema") != 1:
        errs.append("schema 必须为 1")
    if rec.get("source") not in ("adb", "apk"):
        errs.append("source 非法: %r" % rec.get("source"))
    if not isinstance(rec.get("ts"), int):
        errs.append("ts 必须是整数")
    m = rec.get("metrics") or {}
    for k in METRIC_INT:
        if not isinstance(m.get(k), int):
            errs.append("metrics.%s 必须是整数" % k)
    for k in METRIC_BOOL:
        if not isinstance(m.get(k), bool):
            errs.append("metrics.%s 必须是布尔" % k)
    if isinstance(m.get("interactive"), int) and isinstance(m.get("unlabeled"), int):
        if m["unlabeled"] > m["interactive"]:
            errs.append("unlabeled(%d) > interactive(%d)" % (m["unlabeled"], m["interactive"]))
    return errs


def main(paths):
    bad = n = 0
    for p in paths:
        with open(p, "r", encoding="utf-8-sig") as f:
            for i, line in enumerate(f, 1):
                line = line.strip()
                if not line:
                    continue
                n += 1
                try:
                    rec = json.loads(line)
                except ValueError as e:
                    # 采集中断可能留下半行：算失败，但不能让整个校验崩掉
                    print("FAIL %s:%d 无法解析：%s" % (os.path.basename(p), i, e))
                    bad += 1
                    continue
                for e in check(rec):
                    print("FAIL %s:%d %s" % (os.path.basename(p), i, e))
                    bad += 1
    print("校验 %d 条，问题 %d 个" % (n, bad))
    if n == 0:
        print("FAIL 没有记录可校验（数据集为空或路径错误）")
        return 1
    return 1 if bad else 0


if __name__ == "__main__":
    src = sys.argv[1:] or [os.path.join(ROOT, "data", "lint.jsonl")]
    sys.exit(main([p for p in src if os.path.isfile(p)]))