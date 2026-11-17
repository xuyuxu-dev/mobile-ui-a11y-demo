# Flow Engine (engine package)

一份 JSON 流程 → adb 执行。**默认 dry-run**：未显式传 `--allow-taps` 时不产生点击。

## 为什么单独一个包

体检器（`../lint`）回答"界面读不读得出来"；引擎回答"读得出来时，怎么稳定地操作"。
两者共享同一套界面树读取代码（`../lint/collectors/adb_collect.py`），但不共享状态：
可以分别发布，也可以一起用。

## 用法

```bash
# dry-run：只解析 + 定位，不点击（默认）
python engine.py flows/settings-demo.json --serial <SN>

# 真的执行（只做导航类操作）
python engine.py flows/settings-demo.json --serial <SN> --allow-taps
```

输出示例：

```
1  launch         OK    android.settings.SETTINGS
2  assert_text    OK    设置主页已加载
3  tap_text       OK    点击 (576,2251) 声音
4  assert_text    OK    已进入声音设置
5  back           OK    返回
6  assert_text    OK    已回到设置主页

流程通过
```

## 流程格式

```json
{"steps": [
  {"op": "launch", "action": "android.settings.SETTINGS", "settle_text": "声音"},
  {"op": "assert_text", "text": "声音", "desc": "设置主页已加载"},
  {"op": "tap_text", "text": "声音", "settle_text": "铃声"},
  {"op": "back"}
]}
```

'支持：

| op | 作用 |
|---|---|
| `launch` | 启动应用/页面（action / component / package） |
| `wait_text` | 轮询直到文字出现 |
| `assert_text` | 断言文字出现（失败即停） |
| `wait_gone` | 轮询直到文字消失（弹窗/toast） |
| `tap_text` | 按文字定位并点击中心（默认 dry-run 只报坐标） |
| `back` / `home` | 返回 / 回桌面 |
| `assert_changed` | **视觉通道**：截图哈希变化（不依赖无障碍树） |
| `assert_stable` | 连续两帧哈希一致（判断动画结束） |
| `ocr_contains` | **OCR 通道**：截图识别文字，断言包含某段（用于无障碍无文字的页面） |
| `tap_ocr_text` | **OCR 通道**：找到文字包围盒并点击其中心 |'

## 三条硬约束

1. **无固定 sleep**：用 `settle_text` 轮询界面，不用"等 2 秒"
2. **dry-run 默认开**：没加 `--allow-taps` 时，第一次点击后所有步骤标 SKIP
3. **只做导航**：不提交、不支付、不输入；要扩展需显式加白名单

## 每步都有 trace

`data/engine-trace.jsonl` 一行一步：`{ts, step, op, ok, detail}`。
失败时能回答"第几步、期望什么、当时找没找到"，而不是只看一个异常栈。