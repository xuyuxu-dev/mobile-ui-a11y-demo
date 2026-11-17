# 可交互 Canvas 夹具（demo）

包名 `com.demo.canvas`，与生产应用无关。整个页面只有一个自绘 View，
**没有任何 TextView**，但**会处理触摸**。

## 为什么需要它

`QUIZ` 里的 `MockExerciseActivity` 只画不处理触摸，所以"视觉定位 → 点击 → 状态转移"
在那上面永远验证不了。这个夹具补上了"会响应"这一环。

## 构建

```bash
# 需要 Android SDK（build-tools 34 + platforms/android-29）
powershell -ExecutionPolicy Bypass -File .\build.ps1
# 或显式指定 SDK
powershell -ExecutionPolicy Bypass -File .\build.ps1 -Sdk D:\android-sdk
```

产物：`out\canvas-fixture.apk`（约 12 KB）。

> SDK 只是**构建期**借用（默认指向工作区里已有的那份），运行期不依赖任何外部路径。

## 用

```bash
adb install -r out\canvas-fixture.apk
adb shell am start -n com.demo.canvas/.MainActivity
python ..\vision_demo.py --serial <SN> --component com.demo.canvas/.MainActivity
```

预期输出：

```
1) 定位到 4 个可点区域： #3 selected=True
2) 准备点击 #0 (154,2022)
3) 点击后重定位: 选中=[0]
4) 选中态转移: 成功
```

同时 `uiautomator dump` 只有 **5 个节点**——证明这条链路没有用无障碍树。