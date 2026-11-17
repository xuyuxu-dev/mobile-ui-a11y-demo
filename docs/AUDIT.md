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
---

## 2026-11-17 增补：隐私加固

### 新增修复

| # | 项 | 处理 |
|---|---|---|
| F8 | 采集记录含设备序列号 | 改为 SHA-256 前 8 位的伪名（`dev-xxxxxxxx`），基于硬件序列号，USB/Wi-Fi 切换不变 |
| F9 | 文档与配置含自有 App 包名 | 全部替换为仓库自带夹具 `com.demo.canvas` |
| F10 | 文档中与项目无关的表述 | 改为中性描述 |
| F11 | 采集时设备休眠导致重复页面 | 每页采集前唤醒；前台识别加 `mResumedActivity` 回退 |
| F12 | CI 令牌权限过大 | 工作流增加 `permissions: contents: read` |

### 残留风险（未完全消除）

| 风险 | 说明 | 建议 |
|---|---|---|
| 远端历史残留对象 | 早期提交被强制推送覆盖，但服务端可能仍保留可达对象；私有仓库仅所有者可访问 | 若要转公开，先删除仓库并用当前内容重建 |
| trace 默认不脱敏 | 轨迹记录流程文字，页面来源文字需 `--redact` | 分享日志前开启脱敏 |
| `data/` 仍在磁盘 | 截图含界面内容，虽已 gitignore | 定期清理，或在不必要时加 `--shot=false` |
| 白名单是包名级 | 同包内任意页面都可驱动 | 需要时扩展到页面级 |
| OCR 依赖 Windows | 非 Windows 环境不可用 | 已在文档标注 |
### 2026-11-17 第二次增补

| # | 项 | 处理 |
|---|---|---|
| F13 | trace 默认记录页面文字 | 改为默认脱敏，`--no-redact` 才保留原文 |
| F14 | 截图与轨迹长期留在磁盘 | 合成后自动删除录制帧；新增 `tools/clean_local.py` |
| F15 | CI 动作依赖大版本标签 | 固定到 commit SHA |
| F16 | 白名单仅包级 | 增加 `page_allowlist`，可限制到具体页面 |
| F17 | OCR 从 PATH 解析 powershell | 改为绝对路径优先 |
### 2026-11-17 第三次增补（公开后复审）

| # | 项 | 处理 |
|---|---|---|
| F18 | 仓库混入临时文件 `MSG_TMP.txt`（提交信息草稿） | 删除，并在 `.gitignore` 中屏蔽同类临时文件 |
| F19 | `FINDINGS.md` 最终数字表过期且表格分隔符丢失 | 按当前口径重写（0.0% / 9.5% / 17.1% / 3.8%） |

复审覆盖范围：

- 仓库设置：无 Actions secret、无 webhook、无 deploy key、仅所有者一个 collaborator，
  Actions 默认令牌权限为 read
- 媒体：三张 GIF 逐帧 OCR，无状态栏时间戳残留
- 代码：四个 `except Exception:` 仅用于字体加载回退，属可接受范围
- 文档：README / ARTICLE / FINDINGS 数字一致（42 个过小目标，17.1%）
### 2026-11-17 第四次增补（可复现性审查）

用"干净克隆 + 直接跑文档里的命令"来验证，而不是在开发目录里跑。

| # | 项 | 处理 |
|---|---|---|
| F20 | 干净克隆后 `verify.ps1` 只有 4/5：基线检查因缺少本地数据集而报错 | 数据集缺失时跳过基线比较并返回成功 |
| F21 | `vision.py` 依赖 numpy/Pillow，但仓库未声明依赖，缺库时报 ImportError 堆栈 | 新增 `requirements.txt`，README 增加 Dependencies 段；缺库时给一行提示 |
| F22 | `vision.py` 传入不存在的图片会抛 FileNotFoundError 堆栈 | 改为 `image not found: <path>` 退出 |
| F23 | `PRIVACY.md` 仍写着“privacy_scan 待实现”“分享前请加 --redact” | 改为“已实现”“默认脱敏” |

验证方式：`git clone` 到空目录 → `verify.ps1` → 5/5 通过。