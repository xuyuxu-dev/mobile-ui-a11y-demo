#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""隐私自检：确认 jsonl 里没有任何界面文本字段（只允许统计量与标识）。"""
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
ALLOWED = {"schema", "source", "device", "ts", "pkg", "page", "metrics", "shot", "note"}
ALLOWED_M = {"nodes", "interactive", "unlabeled", "undersized", "image_only", "invisible",
             "zero_node_page", "no_interactive", "tiny", "unlabeled_classes", "unlabeled_strict", "label_dist"}
# 这些 key 一旦出现，说明有人把界面文本存进来了
FORBIDDEN = {"text", "content_desc", "contentDescription", "desc", "input", "clip", "html"}


def main(paths):
    bad = 0
    n = 0
    for p in paths:
        with open(p, "r", encoding="utf-8-sig") as f:
            for i, line in enumerate(f, 1):
                line = line.strip()
                if not line:
                    continue
                n += 1
                rec = json.loads(line)
                extra = set(rec) - ALLOWED
                if extra:
                    print("FAIL %s:%d 顶层多余字段 %s" % (p, i, extra))
                    bad += 1
                for k in set(rec.get("metrics", {})) - ALLOWED_M:
                    print("FAIL %s:%d metrics 多余字段 %s" % (p, i, k))
                    bad += 1
                if set(rec) & FORBIDDEN:
                    print("FAIL %s:%d 含文本类字段 %s" % (p, i, set(rec) & FORBIDDEN))
                    bad += 1
    print("扫描 %d 条记录，问题 %d 个" % (n, bad))
    if n == 0:
        print("FAIL 没有记录可扫描（数据集为空或路径错误）")
        return 1
    return 1 if bad else 0


if __name__ == "__main__":
    src = sys.argv[1:] or [os.path.join(ROOT, "data", "lint.jsonl")]
    sys.exit(main([p for p in src if os.path.isfile(p)]))