# 只读无障碍计数夹具

包名 `com.demo.a11ycount`。启用后**只遍历节点并写一个 json**，不点击、不输入、不手势。

## 用途

验证 ADR-01：`uiautomator dump`（PC 侧）与实时无障碍树（端侧）差多少。

## 用法（务必还原设置）

```bash
# 1) 记下原值
adb shell settings get secure enabled_accessibility_services

# 2) 临时追加（用冒号分隔）
adb shell settings put secure enabled_accessibility_services '<原值>:com.demo.a11ycount/.CountService'

# 3) 跑实验
python engine/endchannel_probe.py --serial <SN>

# 4) 还原
adb shell settings put secure enabled_accessibility_services '<原值>'
```

结果：`/sdcard/Android/data/com.demo.a11ycount/files/count.json`

## 关键提醒

`res/xml/count_service.xml` 里的 `flagIncludeNotImportantViews` **会决定实验结论**：
不加时端侧节点数比 dump 少 65%，加了反而多 10.6%。