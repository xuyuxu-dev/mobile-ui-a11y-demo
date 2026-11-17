# 架构：两个包怎么分工

```
         ┌─────────────────────────────────────────────┐
         │  目标设备（Android，adb 连接）                │
         │   界面树 (uiautomator)   截图 (screencap)     │
         └───────────┬─────────────────────┬───────────┘
                     │                     │
      ┌──────────────▼───────┐   ┌─────────▼──────────────┐
      │ lint/collectors      │   │ engine 视觉通道         │
      │ adb_collect.py       │   │ screen_hash()          │
      │  - dump / 解析        │   │  - 截图 md5             │
      │  - 指标（距离/尺寸）   │   │  - assert_changed/stable│
      └──────────┬───────────┘   └─────────┬──────────────┘
                 │ schema（统一格式）        │
      ┌──────────▼───────────┐   ┌─────────▼──────────────┐
      │ lint/analyze         │   │ engine/engine.py       │
      │  - 报告 md/csv/svg/html│  │  - DSL 解释器          │
      │  - 基线/历史          │   │  - tap_text / wait_text │
      └──────────────────────┘   │  - trace 每步一行       │
                                  └────────────────────────┘
```

## 两层的边界

| | lint | engine |
|---|---|---|
| 输入 | 界面树 | 流程 JSON + 界面树 + 截图 |
| 输出 | 统计报告 | 每步 trace |
| 是否改变界面 | **从不** | 仅在 `--allow-taps` 时 |
| 失败语义 | 跳过该页并记录 | 立即停止并定位到具体步 |

## 一条完整链路

```
采集 → 归一(schema) → 分析(指标) → 报告
                     ↘
                      发现问题（如 Canvas 页 0 可操作节点）
                     ↗
引擎 → 文字定位失败 → 退到视觉通道（截图哈希）→ 用"变化/稳定"判断动作效果
```

## 为什么这样分层

1. **采集与分析分离**：分析器只认 schema，所以换采集通道（端侧 APK）不用改分析
2. **文字与视觉分离**：文字通道便宜但会缺失；视觉通道贵但不会缺失 → 按需降级
3. **动作与断言分离**：`tap_text` 只负责点，`assert_*` 负责验证；这样"点了但没生效"能立刻暴露

## 公共包 adbkit（已抽出）

```
ui-a11y-audit/adbkit/adbkit.py    devices / dump / 密度 / bounds / 截图哈希
```

`lint/collectors/adb_collect.py` 与 `engine/*.py` 都只依赖它，**互不依赖对方目录**：

| 包 | 依赖 |
|---|---|
| adbkit | 只有 adb |
| lint | adbkit |
| engine | adbkit |

这样拆仓时三个包可以独立发布（engine 不再依赖 lint 的路径）。

## 仍然存在的架构债

- `lint` 的 `label_dist` 与 `engine` 的 `find_text` 各自实现了一遍"找文字"，后续应统一到 adbkit。
- `vision.py` 只做连通域定位，没有模板/OCR；跨页面复用性未知。
## 断言必须"有约束力"（测试的测试）

写了 `assert_changed` 之后，必须证明它在**不该通过时会失败**，否则它就是个永远为真的装饰。

负向用例 `engine/flows/should-fail-changed.json`：

```
1  assert_stable  OK    连续两帧一致      ← 先确认画面静止
2  assert_changed FAIL  画面未变化（期望变化） ← 静止时断言变化必须失败
```

同理，`lint` 的每个指标都有对应的负向夹具（`orphan.xml`：祖先里没有任何文字 → 距离 -1）。

**原则**：每个"检查"都应配一个"必然失败"的用例，否则无法证明其有效。
## 依赖方向

```
adbkit  ←  lint  (采集/分析)
        ←  engine (流程执行)
        ←  tools  (录制/渲染)
```

| 规则 | 现状 |
|---|---|
| `adbkit` 只依赖标准库 | 是（hashlib/os/re/subprocess/time） |
| `lint` 与 `engine` 互不 import | 是（跨包实验脚本已移出） |
| 跨包脚本集中放置 | `tools/experiments/`，README 说明原因 |
| 数据与规则外置 | `capabilities.json`、`flows/*.json`、`pages.json`、`bench-profiles.json` |
| 无写死坐标 | 是（按文字或几何定位） |
| 固定延时仅限录制/实验 | 流程执行用 `POLL_MS` 轮询 |