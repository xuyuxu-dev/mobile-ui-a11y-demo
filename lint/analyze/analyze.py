#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
分析层：只认 schema，不关心数据来自 adb 还是端侧通道。
输出 data/matrix.csv（按应用）、data/pages.csv（按页面）、data/report.md。
"""
import argparse
import csv
import html as html_mod
import json
import time
import os
import sys
from collections import defaultdict

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
KEYS = ("nodes", "interactive", "unlabeled", "undersized", "image_only", "invisible")


def load(paths):
    recs, skipped = [], 0
    for p in paths:
        with open(p, "r", encoding="utf-8-sig") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    recs.append(json.loads(line))
                except ValueError:
                    skipped += 1   # 坏行不该让整份报告失败
    if skipped:
        print("警告：跳过 %d 行无法解析的记录" % skipped, file=sys.stderr)
    if not recs:
        print("没有可用记录：数据集为空或全部损坏（跳过 %d 行）" % skipped, file=sys.stderr)
    # 去重：同 pkg+page 同一秒只留一条（两通道重复采到同一页时不双算）
    seen, out = set(), []
    for r in recs:
        k = (r.get("pkg"), r.get("page"), r.get("ts", 0) // 1000)
        if k in seen:
            continue
        seen.add(k)
        out.append(r)
    return out


def pct(a, b):
    return (100.0 * a / b) if b else 0.0


def agg_by(recs, keyfn):
    agg = defaultdict(lambda: dict({k: 0 for k in KEYS}, pages=0, zero_pages=0, no_int=0))
    for r in recs:
        a = agg[keyfn(r)]
        a["pages"] += 1
        for k in KEYS:
            a[k] += int(r["metrics"].get(k, 0))
        if r["metrics"].get("zero_node_page"):
            a["zero_pages"] += 1
        if r["metrics"].get("no_interactive"):
            a["no_int"] += 1
    return agg


def load_page_types():
    path = os.path.join(HERE, "page_types.json")
    if not os.path.isfile(path):
        return [], "其他"
    with open(path, "r", encoding="utf-8-sig") as f:
        cfg = json.load(f)
    return [(t["prefix"], t["type"]) for t in cfg.get("types", [])], cfg.get("default", "其他")


def type_of(pkg, mapping, default):
    for prefix, t in mapping:
        if pkg.startswith(prefix):
            return t
    return default


def type_stats(recs, mapping, default):
    agg = {}
    for r in recs:
        t = type_of(r["pkg"], mapping, default)
        a = agg.setdefault(t, {"pages": 0, "interactive": 0, "small": 0,
                               "rowlab": 0, "dist": 0, "no_int": 0})
        m = r["metrics"]
        a["pages"] += 1
        a["interactive"] += m["interactive"]
        a["small"] += m.get("undersized", 0)
        a["no_int"] += 1 if m.get("no_interactive") else 0
        for k, v in (m.get("label_dist") or {}).items():
            a["dist"] += int(v)
            if k not in ("0", "-1"):
                a["rowlab"] += int(v)
    return agg


def label_dist_total(recs):
    agg = {}
    for r in recs:
        for k, v in (r["metrics"].get("label_dist") or {}).items():
            agg[k] = agg.get(k, 0) + int(v)
    return agg


def class_totals(recs):
    agg = defaultdict(int)
    for r in recs:
        for k, v in (r["metrics"].get("unlabeled_classes") or {}).items():
            agg[k] += int(v)
    return dict(sorted(agg.items(), key=lambda kv: -kv[1]))


def append_history(outdir, recs, by_pkg):
    path = os.path.join(outdir, "history.csv")
    new = not os.path.isfile(path)
    ti = sum(v["interactive"] for v in by_pkg.values())
    tu = sum(v["unlabeled"] for v in by_pkg.values())
    ts = sum(v["undersized"] for v in by_pkg.values())
    row = {"ts": int(time.time()), "pages": len(recs), "interactive": ti,
           "unlabeled": tu, "unreadable_pct": "%.1f" % pct(tu, ti),
           "undersized": ts, "undersized_pct": "%.1f" % pct(ts, ti)}
    with open(path, "a", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(row.keys()))
        if new:
            w.writeheader()
        w.writerow(row)


def write_csv(path, cols, rows):
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=cols)
        w.writeheader()
        for r in rows:
            w.writerow(r)


def pearson(xs, ys):
    n = len(xs)
    if n < 3:
        return 0.0
    mx, my = sum(xs) / n, sum(ys) / n
    num = sum((x - mx) * (y - my) for x, y in zip(xs, ys))
    dx = sum((x - mx) ** 2 for x in xs) ** 0.5
    dy = sum((y - my) ** 2 for y in ys) ** 0.5
    return num / (dx * dy) if dx and dy else 0.0


def write_html(path, recs, by_pkg, by_page):
    """生成一个自包含的 HTML（内嵌 SVG），方便截图/汇报。"""
    xs = [r["metrics"]["nodes"] for r in recs]
    ys = [pct(r["metrics"]["unlabeled"], max(1, r["metrics"]["interactive"])) for r in recs]
    r_p = pearson(xs, ys)
    total_i = sum(v["interactive"] for v in by_pkg.values())
    ld_h = label_dist_total(recs)
    total_u = sum(v for kk, v in ld_h.items() if kk not in ("0", "-1"))
    total_s = sum(v["undersized"] for v in by_pkg.values())
    # 包名/页面名来自设备（不可信），进 HTML 前必须转义
    rows = "".join(
        "<tr><td>%s</td><td>%d</td><td>%d</td><td>%.1f%%</td><td>%.1f%%</td><td>%d</td></tr>"
        % (html_mod.escape(str(k)), v["pages"], v["interactive"],
           pct(v["unlabeled"], max(1, v["interactive"])),
           pct(v["undersized"], max(1, v["interactive"])), v["no_int"])
        for k, v in sorted(by_pkg.items(), key=lambda kv: -kv[1]["pages"]))
    svg = ""
    svg_path = os.path.join(os.path.dirname(path), "chart.svg")
    if os.path.isfile(svg_path):
        with open(svg_path, encoding="utf-8") as f:
            svg = f.read()
    html = """<!doctype html><meta charset="utf-8">
<title>无障碍体检报告</title>
<style>
 body{font-family:system-ui,-apple-system,"Segoe UI",sans-serif;margin:32px;color:#111;max-width:960px}
 h1{font-size:22px;margin-bottom:4px} .sub{color:#666;font-size:13px;margin-bottom:24px}
 .cards{display:flex;gap:16px;margin:20px 0 28px}
 .card{border:1px solid #e5e7eb;border-radius:10px;padding:14px 18px;min-width:150px}
 .card b{display:block;font-size:26px;line-height:1.2}
 .card span{color:#666;font-size:12px}
 table{border-collapse:collapse;width:100%%;font-size:13px;margin-top:8px}
 th,td{border-bottom:1px solid #eee;padding:6px 8px;text-align:left}
 th{color:#555;font-weight:600}
 .note{color:#888;font-size:12px;margin-top:18px;line-height:1.7}
</style>
<h1>移动 UI 无障碍体检</h1>
<div class="sub">只读审计（uiautomator 界面树）；口径：不可读=可交互节点自身或后代无 text/content-desc</div>
<div class="cards">
  <div class="card"><b>%d</b><span>采样页面</span></div>
  <div class="card"><b>%d</b><span>可交互控件</span></div>
  <div class="card"><b>%.1f%%</b><span>依赖行/祖先标签</span></div>
  <div class="card"><b>%.1f%%</b><span>点击区 24–48dp</span></div>
</div>
%s
<h3 style="margin-top:28px">按应用</h3>
<table><tr><th>应用</th><th>页面</th><th>可交互</th><th>不可读</th><th>过小</th><th>无可操作页</th></tr>
%s</table>
<div class="note">
节点数与不可读率的相关系数 r = <b>%.2f</b>（绝对值 &lt;0.3 视为弱相关；说明"页面越大越差"并不成立）。<br>
数据来自 %d 条采样记录；零尺寸节点单独统计，不计入"过小"。<br>
本报告只含统计量，不含任何界面文本或截图。
</div>
""" % (total_pages_of(by_pkg), total_i, pct(total_u, total_i), pct(total_s, total_i),
       svg, rows, r_p, len(recs))
    with open(path, "w", encoding="utf-8") as f:
        f.write(html)
    return "html: r=%.2f" % r_p


def total_pages_of(by_pkg):
    return sum(v["pages"] for v in by_pkg.values())


def write_svg(path, by_pkg, recs=None):
    """手写 SVG 条形图：不引入任何绘图依赖，方便在 GitHub 里直接看。"""
    items = [(k, pct(v["unlabeled"], max(1, v["interactive"])),
              pct(v["undersized"], max(1, v["interactive"]))) for k, v in by_pkg.items()]
    items.sort(key=lambda x: -x[1])
    if not items:
        return
    row_h, top, left, width = 34, 60, 300, 520
    h = top + row_h * len(items) + 40
    parts = ['<svg xmlns="http://www.w3.org/2000/svg" width="%d" height="%d" font-family="monospace" font-size="13">' % (left + width + 80, h),
             '<text x="12" y="26" font-size="17">可读性 / 点击区 缺陷率（按应用）</text>',
             '<text x="12" y="46" font-size="12" fill="#666">蓝=不可读（无标签）  橙=点击区 24~48dp</text>']
    for i, (pkg, unread, small) in enumerate(items):
        y = top + i * row_h
        parts.append('<text x="12" y="%d" font-size="12">%s</text>'
                     % (y + 14, html_mod.escape(pkg[:34])))  # 防止 SVG 注入
        for j, (val, color) in enumerate(((unread, "#3b82f6"), (small, "#f59e0b"))):
            w = max(1, val / 100.0 * width)
            yy = y + j * 12
            parts.append('<rect x="%d" y="%d" width="%.1f" height="10" fill="%s" rx="2"/>' % (left, yy, w, color))
            parts.append('<text x="%.1f" y="%d" font-size="11" fill="#333">%.1f%%</text>' % (left + w + 6, yy + 9, val))
    parts.append('</svg>')
    with open(path, "w", encoding="utf-8") as f:
        f.write("\n".join(parts))


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("inputs", nargs="*")
    ap.add_argument("--outdir", default=os.path.join(ROOT, "data"))
    args = ap.parse_args(argv)
    paths = [p for p in (args.inputs or [os.path.join(ROOT, "data", "lint.jsonl")]) if os.path.isfile(p)]
    if not paths:
        print("no input")
        return 2
    recs = load(paths)
    if not recs:
        # 空数据集意味着采集失败或输入放错；静默产出空报告会让下游门禁误判为通过
        return 2
    by_pkg = agg_by(recs, lambda r: r["pkg"])
    by_page = agg_by(recs, lambda r: (r["pkg"], r["page"]))

    try:
        os.makedirs(args.outdir, exist_ok=True)
    except OSError as e:
        print("无法创建输出目录：%s（%s）" % (args.outdir, e), file=sys.stderr)
        return 2
    pkg_cols = ["pkg", "pages", "interactive", "unlabeled", "unreadable_pct",
                "undersized", "undersized_pct", "no_int", "zero_pages"]
    write_csv(os.path.join(args.outdir, "matrix.csv"), pkg_cols, [
        {"pkg": k, "pages": a["pages"], "interactive": a["interactive"],
         "unlabeled": a["unlabeled"], "unreadable_pct": "%.1f" % pct(a["unlabeled"], a["interactive"]),
         "undersized": a["undersized"], "undersized_pct": "%.1f" % pct(a["undersized"], a["interactive"]),
         "no_int": a["no_int"], "zero_pages": a["zero_pages"]}
        for k, a in sorted(by_pkg.items(), key=lambda kv: -kv[1]["pages"])])

    page_cols = ["pkg", "page", "interactive", "unlabeled", "unreadable_pct", "undersized", "no_interactive"]
    page_rows = []
    for (pkg, page), a in by_page.items():
        m = [r for r in recs if r["pkg"] == pkg and r["page"] == page][0]["metrics"]
        page_rows.append({"pkg": pkg, "page": page, "interactive": a["interactive"],
                          "unlabeled": a["unlabeled"],
                          "unreadable_pct": "%.1f" % pct(a["unlabeled"], a["interactive"]),
                          "undersized": a["undersized"],
                          "no_interactive": m.get("no_interactive", False)})
    page_rows.sort(key=lambda r: (-r["interactive"], r["pkg"]))
    write_csv(os.path.join(args.outdir, "pages.csv"), page_cols, page_rows)

    total_pages = sum(a["pages"] for a in by_pkg.values())
    ti = sum(a["interactive"] for a in by_pkg.values())
    tu = sum(a["unlabeled"] for a in by_pkg.values())
    ts = sum(a["undersized"] for a in by_pkg.values())
    tz = sum(a["zero_pages"] for a in by_pkg.values())
    ld = label_dist_total(recs)
    tdist = sum(ld.values())
    rowlab = sum(v for k, v in ld.items() if k not in ("0", "-1"))
    tni = sum(a["no_int"] for a in by_pkg.values())

    L = ["# 无障碍体检报告", "", "## 总体", "", "| 指标 | 数值 |", "|---|---|",
         "| 采样页面 | %d |" % total_pages,
         "| 可交互控件 | %d |" % ti,
         "| 无标签（4 层祖先内都找不到） | %d（%.1f%%）|" % (tu, pct(tu, ti)),
         "| 依赖行/祖先标签（距离≥1） | %d（%.1f%%）|" % (rowlab, pct(rowlab, tdist)),
         "| 点击区 < 48dp | %d（%.1f%%）|" % (ts, pct(ts, ti)),
         "| 无可操作节点页 | %d（%.1f%%）|" % (tni, pct(tni, total_pages)),
         "| 零节点页 | %d（%.1f%%）|" % (tz, pct(tz, total_pages)),
         "", "## 按应用", "",
         "| 应用 | 页面 | 可交互 | 无标签 | 行标签 | 过小 |", "|---|---|---|---|---|---|"]
    for k, a in sorted(by_pkg.items(), key=lambda kv: -kv[1]["pages"]):
        # 该应用的行标签率
        ra = 0
        ti_a = 0
        for r in recs:
            if r["pkg"] != k:
                continue
            for kk, vv in (r["metrics"].get("label_dist") or {}).items():
                ti_a += int(vv)
                if kk not in ("0", "-1"):
                    ra += int(vv)
        L.append("| %s | %d | %d | %.1f%% | %.1f%% | %.1f%% |" % (
            k, a["pages"], a["interactive"],
            pct(a["unlabeled"], a["interactive"]), pct(ra, ti_a),
            pct(a["undersized"], a["interactive"])))

    mapping, default_type = load_page_types()
    ts = type_stats(recs, mapping, default_type)
    if ts:
        L += ["", "## 按页面类型", "",
              "| 类型 | 页面 | 可交互 | 行标签 | 过小 | 无可操作 |", "|---|---|---|---|---|---|"]
        for t, a in sorted(ts.items(), key=lambda kv: -kv[1]["interactive"]):
            L.append("| %s | %d | %d | %.1f%% | %.1f%% | %d |" % (
                t, a["pages"], a["interactive"], pct(a["rowlab"], a["dist"]),
                pct(a["small"], a["interactive"]), a["no_int"]))

    if ld:
        L += ["", "## 标签距离分布（0=自身带标签，n=向上第 n 层）", "",
              "| 距离 | 控件数 | 占比 |", "|---|---|---|"]
        for k in ("0", "1", "2", "3", "4", "-1"):
            v = ld.get(k, 0)
            name = "无（4 层内未找到）" if k == "-1" else k
            L.append("| %s | %d | %.1f%% |" % (name, v, pct(v, tdist)))
        L.append("")
        L.append("> 距离越远，屏幕阅读器越可能读不出来：理想是 0，1–2 属于常见"
                 "（列表行/开关行），4 已经需要靠外层容器兜底。")

    cls = class_totals(recs)
    if cls:
        L += ["", "## 缺标签最多的控件类型", "", "| 控件类型 | 缺标签数量 |", "|---|---|"]
        for k, v in list(cls.items())[:10]:
            L.append("| %s | %d |" % (k, v))

    L += ["", "## 不可读率（按应用，条形 = 每 2% 一格）", "", "```"]
    for k, v in sorted(by_pkg.items(), key=lambda kv: -pct(kv[1]["unlabeled"], max(1, kv[1]["interactive"]))):
        r = pct(v["unlabeled"], max(1, v["interactive"]))
        L.append("%-38s %5.1f%% %s" % (k[:38], r, "#" * int(round(r / 2))))
    L.append("```")

    L += ["", "## 最差页面（可交互 >= 3，按不可读率）", "",
          "| 应用 | 页面 | 可交互 | 不可读 |", "|---|---|---|---|"]
    shown = 0
    for r in sorted(page_rows, key=lambda r: -float(r["unreadable_pct"])):
        if r["interactive"] < 3 or float(r["unreadable_pct"]) == 0:
            continue
        L.append("| %s | %s | %d | %s%% |" % (r["pkg"], r["page"].split("/")[-1], r["interactive"], r["unreadable_pct"]))
        shown += 1
        if shown >= 10:
            break
    if shown == 0:
        L.append("| （无） | | | |")

    no_int = [(k[0], k[1]) for k, a in by_page.items() if a["no_int"]]
    if no_int:
        L += ["", "## 无可操作节点的页面（疑似自绘/图片化，需截图确认）", ""]
        for pkg, page in no_int:
            L.append("- `%s` / `%s`" % (pkg, page.split("/")[-1]))

    L += ["", "---", "",
          "**口径**：不可读 = 可交互节点自身或任一后代既无 text 也无 content-desc；",
          "点击区过小 = 宽或高 < 48dp（零尺寸节点单独计为 invisible，不算过小）；",
          "无可操作节点 = 整页 interactive == 0（纯展示页也会命中，故写作「疑似」）；",
          "零尺寸（invisible）控件单独统计，不参与「无标签/过小」判定；",
          "「行级判定」= 开关类控件的标签常在同级 TextView 上（labelFor），向上两级找兄弟节点文字。"]
    with open(os.path.join(args.outdir, "report.md"), "w", encoding="utf-8") as f:
        f.write("\n".join(L) + "\n")
    write_svg(os.path.join(args.outdir, "chart.svg"), by_pkg, recs)
    append_history(args.outdir, recs, by_pkg)
    stats = write_html(os.path.join(args.outdir, "report.html"), recs, by_pkg, by_page)
    print(stats)
    print("records=%d pkgs=%d pages=%d -> %s" % (len(recs), len(by_pkg), len(by_page), args.outdir))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())