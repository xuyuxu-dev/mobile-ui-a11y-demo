# 全量审计报告（2026-11-17）

范围：`ui-a11y-audit/` 全部代码（adbkit / lint / engine / fixture），共 72 个文件。
方法：自动扫描（隐私关键字、危险调用、网络访问、文件类型）+ 手工逐模块审查 +
**攻击性测试**（畸形输入、注入、越权）。

## 结论先说

发现 **7 个问题**，其中 2 个属安全类（注入面），全部已修复并加回归测试。
没有发现：外联网络、`shell=True`/`eval`/`pickle`、危险权限、真实平台指纹、明文凭据入库。

## 发现清单

| # | 严重度 | 问题 | 状态 |
|---|---|---|---|
| F1 | 中 | 畸形/截断 XML 让采集器直接抛异常 | ✅ 已修（跳过该页，退出码 4） |
| F2 | 中 | 一行坏 JSONL 让整份报告失败 | ✅ 已修（跳过并告警） |
| F3 | 中 | 包名/页面名未转义就写进 `report.html`/SVG → **HTML 注入** | ✅ 已修（`html.escape`） |
| F4 | **高** | 流程里的 `component/action/package` 直接拼进 `adb shell` → **命令注入** | ✅ 已修（字符集白名单 + 能力白名单 + 未知 op 拒绝） |
| F5 | 中 | 演示脚本的 `--component` 同样可注入 | ✅ 已修（同一个正则） |
| F6 | 中 | 引擎 trace 会落盘**页面文字**（OCR 命中内容、目标文字） | ✅ 已修（`--redact` 脱敏） |
| F7 | 低 | 签名密钥 `fixture.jks` 在仓库目录里 | ✅ 已修（`.gitignore` + 文档说明仅供 demo） |

## 攻击性测试（修复后复测）

| 测试 | 修复前 | 修复后 |
|---|---|---|
| 畸形 XML | 抛异常崩 | 退出码 4，跳过 |
| 坏 JSONL 行 | 抛异常崩 | 跳过 1 行，正常出报告 |
| 包名 = `<script>alert(1)</script>` | 原样进 HTML | 转义为 `&lt;script&gt;` |
| component = `com.a/.B; id > /sdcard/pwned.txt` | 原样拼接 | 拒绝：含非法字符 |
| package = `com.tencent.mm`（未登记） | 直接启动 | 拒绝：包名未授权 |

## 防御措施（已内建）

1. **能力白名单** `engine/capabilities.json`：只允许演示目标（系统设置/计算器/自建夹具），
   默认拒绝；`--allow-any` 才能跳过（文档标注危险）。
2. **流程加载期校验**：未知 op、非法字符、未授权目标 → 直接拒绝，不执行任何一次 adb 调用。
3. **默认 dry-run**：不加 `--allow-taps` 不产生任何点击。
4. **只读优先**：lint 从不点击输入，只 dump。
5. **数据最小化**：lint 的 JSON 只存统计量（无文本字段），有 `privacy_scan.py` 强制检查。
6. **脱敏开关**：分享 trace 时 `--redact` 去掉页面文字。

## 隐私评估

| 项 | 现状 |
|---|---|
| 采集内容 | 包名、页面名、节点计数（无文本、无截图内容） |
| 截图 | 只写在 `data/`（已 gitignore），本地留存，可随时删 |
| trace | 默认含流程文字；`--redact` 可脱敏；`data/` 不进仓库 |
| 设备残留 | `/sdcard/lint_dump.xml`、`/sdcard/adbkit_dump.xml`（公开的界面树文件，可删） |
| 凭据 | 无 token/密码入库；demo keystore 密码明文但仅用于自签 demo APK |

## 合规评估

| 项 | 现状 |
|---|---|
| 目标范围 | 只驱动系统设置/计算器/自建夹具；**不含任何校园/学习平台** |
| 动作类型 | 只做导航与选择；不提交、不支付、不输入凭据 |
| 平台指纹 | 全仓库检索：无任何校园/在线学习平台的名称、包名或接口标识 |
| 个人信息 | 全仓库检索：无任何个人身份信息 |
| 许可证 | MIT；无第三方代码拷贝（OCR 用的是系统 API） |
| 合规风险 | 低：本质是"界面可读性测量 + 演示用自动化"，不针对具体平台 |

## 残留风险（诚实记录）

1. **trace 仍含流程作者写的文字**（如 `launch canvas-fixture`、步骤 desc）；
   `--redact` 只能去掉页面来源的文字，流程自带的说明文字仍会保留。
2. **`data/` 下的截图**可能包含界面内容（仅本地，已 gitignore，未自动清理）。
3. **OCR 依赖 Windows 系统引擎**：非 Windows 或未装中文语言包时不可用（会直接报错，不静默降级）。
4. **能力白名单是"包名级"**：同包内的任意页面都能被驱动，未做到"页面级"授权。
5. **未做并发/多设备场景**：同一 adb 设备被两个进程同时驱动时行为未定义。

## 复现审计

```bash
python lint/tests/selftest.py          # 指标口径
python lint/tests/privacy_scan.py lint/data/lint.jsonl
python lint/tests/schema_check.py lint/data/lint.jsonl
python engine/engine.py <恶意flow>      # 应被拒绝（退出码 6）
./verify.ps1                           # 5 道闸门
```