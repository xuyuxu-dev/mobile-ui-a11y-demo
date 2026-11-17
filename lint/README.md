# Accessibility Audit (lint package)

以**只读**方式测量界面的可读性：多少可交互控件屏幕阅读器读不出来、多少点击区小于 48dp、
多少页面没有任何可操作节点。输出可复现的 CSV、SVG 与 HTML 报告。

与任何现有生产应用零耦合：不引用外部代码、不共享包名、不读写外部文件。

## Metrics

| 指标 | 定义 |
|---|---|
| 标签距离 `label_dist` | 0 = 控件自身有文字；n = 向上第 n 层祖先提供文字；-1 = 4 层内均无 |
| 无标签 `unlabeled` | 标签距离为 -1 的可交互控件 |
| 过小 `undersized` | 可交互且宽或高在 24–48dp 之间 |
| 装饰性小节点 `tiny` | 小于 24dp，单独统计，不计入过小 |
| 不可见 `invisible` | bounds 宽或高为 0，单独统计，不参与上述判定 |
| 无可操作节点 `no_interactive` | 整页可交互控件数为 0（疑似自绘/图片化界面） |
| 零节点页 `zero_node_page` | 整页节点数 ≤ 2（极端情况） |

## 实测（26 页 / 10 应用，可一键复现）

| 指标 | 数值 |
|---|---|
| 可交互控件 | 245 |
| 无标签（4 层内无文字） | **0（0.0%）** |
| 依赖行/祖先标签（距离 ≥1） | 23（9.5%） |
| 点击区 24–48dp | 42（17.1%） |
| 点击区 < 24dp（装饰） | 6 |
| 不可见控件 | 3 |
| 无可操作节点页 | 1（3.8%，Canvas 自绘页） |

最差页面（按无标签率，可交互 ≥3）：

```
设置·日期时间   66.7%
设置·输入法     44.4%
设置·电池节能   28.6%
设置·无障碍     21.1%
设置·声音       17.6%
```

## 运行

```bash
# 依赖：Python 3.8+、adb（或用环境变量 ADB 指定路径）
# 采集当前页面（只读，不点击）
python collectors/adb_collect.py --serial <SN> --out data/lint.jsonl --tag 手动采样

# 采集时同时保存截图（为"无可操作节点"页面留证据）
python collectors/adb_collect.py --serial <SN> --out data/lint.jsonl --shot

# 分析：生成 data/report.md / matrix.csv / pages.csv / chart.svg / report.html
python analyze/analyze.py data/lint.jsonl

# 离线自测（不需要手机）
python tests/selftest.py

# 数据源稳定性实验（同页连续 dump N 次）
python tests/stability.py --serial <SN> --n 8
```

## 关键发现

1. **口径比工具重要**：四次修正——只看自身（90%+）→ 看子树（10.2%）→ 行级标签（0.8%）
   → **标签距离分布**（真实无标签 0%，9.5% 依赖行标签）。同一数据源，结论相差两个数量级。
2. **dump 稳定但慢**：同页连采 8 次节点数抖动 0%，单页 1.86s，扫 500 页约 16 分钟。
3. **自绘页面确实读不到**：Canvas 页面仅 8 个装饰节点、0 个可交互控件。
4. **规模不是原因**：节点数与无标签率相关系数 r = -0.06，页面复杂度不能作为代理指标。

详细记录：`docs/FINDINGS.md`、`docs/EXPERIMENT_M1_5.md`。

## 边界

- 只读：不点击、不输入、不提交、不登录
- 只存统计量：JSON 中不含任何界面文本（见 `docs/PRIVACY.md`）
- 样本为系统设置与系统自带应用，未审计第三方应用
- 以静态页面为主，滚动/动画期间的采样未覆盖

## 配套包

同仓库的 `engine/` 负责"读出来之后如何稳定操作"（默认 dry-run），两者只共同依赖 `adbkit`。

## 目录

```
schema/     数据格式（双通道共用；端侧通道若实现须遵守）
collectors/ adb 采集器（PC 侧）
analyze/    分析器：只认 schema，不关心数据来源
fixtures/   离线夹具（无手机也能跑）
tests/      自测、数据源实验、现场核查脚本
docs/       实验记录、隐私边界、架构决策
android/    端侧通道预留位（当前未实现，判定依据见 docs/DECISIONS.md）
```