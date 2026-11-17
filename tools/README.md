# 演示素材生成

| 脚本 | 作用 |
|---|---|
| `record_demo.py` | 真机录制：在自绘夹具上依次点击四个按钮，逐帧截图 |
| `compose_gif.py` | 把录制帧合成 GIF；每帧的选中态由视觉重新识别，标注与画面一致 |
| `make_demo_gif.py` | 备用：从已有截图拼 4 帧静态演示 |

## 用法

```bash
python tools/record_demo.py     # 需要连接设备并解锁屏幕
python tools/compose_gif.py     # 输出 docs/assets/demo.gif
```

录制帧写入 `engine/data/rec/`（已 gitignore），GIF 输出到 `docs/assets/`（随仓库发布）。

## 前提

- 设备已连接且屏幕解锁
- 目标页面为 `com.demo.canvas/.MainActivity`（自绘夹具，点击只切换选中态）