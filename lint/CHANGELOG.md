# Changelog（demo）

## 0.3.0 — 2026-11-17

### Changed

- **指标从二元改为分布**：新增 `label_dist`（标签距离：0=自身，1..4=祖先层级，-1=无）。
  结论随之改变：真实"无标签"是 **0%**，但 **9.5% 依赖行/祖先标签**（屏幕阅读器风险区）
- 按应用表与 SVG 图改为展示"行标签率"，因为"无标签率"已归零
- `tests/ancestor_scan.py`：现场核查严格无标签控件的标签到底在第几层祖先

### Fixed

- 之前 0.8% 的"真实缺陷"经核查全部是标签距离 >2 的案例（SeekBar 的标签在第 4 级祖先）

## 0.2.0 — 2026-11-17

### Added

- `unlabeled_strict`：行级标签判定（开关类控件的标签常在同级 TextView 上，`labelFor` 不被 dump 导出）
- `unlabeled_classes`：缺标签控件的类名分布（只存类名，不含文本）
- 零尺寸控件单独计为 `invisible`，不参与「无标签/过小」判定
- `data/report.html`：自包含 HTML 报告（内嵌 SVG，可直接截图）
- `data/history.csv`：每次运行的指标快照，便于看趋势
- `tests/strict_unlabeled_diag.py`：现场核查"严格无标签"控件
- 相关性统计：节点数 vs 不可读率 r=-0.08（弱相关，说明不是规模效应）

### Changed

- 报告同时给出两个口径：真实缺陷 0.8%（行级判定后）与上界 9.4%（不判定行级）

## 0.1.0 — 2026-11-17

首个可跑版本：只读采集 + 指标 + 报告 + 三道校验。

### Added

- `collectors/adb_collect.py`：adb dump → 指标（nodes/interactive/unlabeled/undersized/tiny/invisible/image_only/no_interactive）
- `collectors/collect_batch.py` + `collectors/pages.json`：页面清单外置，22 页一键复现
- `analyze/analyze.py`：`report.md` / `matrix.csv` / `pages.csv` / `chart.svg`（手写 SVG，无绘图依赖）
- `tests/`：离线自测、schema 校验、隐私扫描、指标基线、稳定性实验、过小节点现场核查、dump 语义对比
- `docs/`：FINDINGS（指标口径与弯路）、EXPERIMENT_M1_5（实验）、DECISIONS（ADR）、PRIVACY、POST
- `run_all.ps1`：一条命令跑完 5 步

### Findings

- 指标口径会让结论差 10 倍（90%+ → 10.0%）
- `<24dp` 多为装饰，拆分后过小率 21.3% → 18.1%
- dump 稳定（抖动 0%）但慢（1.86s/页，32 页/分钟）
- 滚动导致 ±7% 抖动；WebView 页仅 2 个节点带文字

### Not done

- 端侧采集通道（判定门槛见 ADR-01）
- 端侧采集通道（判定依据见 DECISIONS 的 ADR-01）
- 第三方应用审计