# 端侧通道（M2，暂未实现）

预留位。若 M1.5 对照实验证明 `uiautomator dump` 明显少于实时无障碍树，则在此实现独立 APK：

- 包名：`com.demo.lint`（占位，尚未实现）
- 自己的无障碍服务、自己的 keystore、自己的签名
- 只做采样并写 `files/lint/*.jsonl`，不点击、不输入、不提交
- 输出必须符合 `../schema/sample.schema.json`

不做端侧通道的理由也要写在这里（若最终决定不做）：见 `../docs/EXPERIMENT_M1_5.md`