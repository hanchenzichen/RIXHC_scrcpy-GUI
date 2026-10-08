# 第三方组件声明（Third-Party Notices）

本项目的**源代码**以 MIT 许可发布（见 `LICENSE`）。分发的**二进制包**中还包含以下
第三方组件，它们各自遵循自己的许可证。我们只做**原样分发**，不修改其代码。

---

## 1. scrcpy（随包分发，未修改）

- 项目：https://github.com/Genymobile/scrcpy
- 作者：Romain Vimont（Genymobile）
- 许可证：**Apache License 2.0**
- 分发方式：直接解包**官方发布包**（`scrcpy-win64-vX.Y.Z.zip` /
  `scrcpy-linux-x86_64-vX.Y.Z.tar.gz` 等），未做任何修改。
- 许可证全文：随包保留在 `scrcpy/LICENSE`（Windows 为 `scrcpy/LICENSE.txt`），
  亦即上游发布包内的原始文件。
- 完整性：下载时使用上游发布的 `SHA256SUMS.txt` 做校验
  （见 `rix/vendor.py`），校验失败会删除文件并中止。

## 2. Android platform-tools（adb，随 scrcpy 官方包一并分发）

- scrcpy 的官方发布包**自带 `adb`**（`adb.exe` / `adb`）与 Windows 下的
  `AdbWinApi.dll`、`AdbWinUsbApi.dll`。
- 本项目没有单独下载或修改 adb，只是原样保留 scrcpy 官方包里的文件。
- 版权归 Google LLC / The Android Open Source Project 所有，遵循 Android SDK
  随附的许可条款。相关声明文件同样保留在 `scrcpy/` 目录内（若上游包中提供）。

## 3. PySide6 / Qt for Python（随包分发，未修改）

- 项目：https://code.qt.io/cgit/pyside/pyside-setup.git/
- 许可证：**LGPL v3**（本项目以动态链接方式使用，未修改其源代码）
- 依据 LGPL v3，你可以用自己编译或获取的兼容版本替换包内的 PySide6/Qt 动态库；
  许可证全文随包提供于 `PySide6/` 目录内。

## 4. 其他 Python 依赖

`requirements.txt` 中列出的依赖各自遵循其许可证，其许可证文本随包内对应的
`dist-info` 目录一并分发。

---

## 为什么选择「随包分发 scrcpy」

用户使用本程序失败的最常见原因，并不是程序本身的 bug，而是：

1. 没有安装 scrcpy；
2. 安装了但不在 `PATH` 里（尤其是 Windows 解压版）；
3. scrcpy 与 adb 版本不匹配。

把**未经修改**的官方 scrcpy 发布包随程序分发，可以一次性消除这三类问题，
同时通过保留上游 `LICENSE` 文件 + `SHA256` 校验来满足许可证与完整性要求。

如果你不希望使用内置核心，可以：

- 删除包内的 `scrcpy/` 目录，程序会自动回退到系统 `PATH`；或
- 设置环境变量 `RIX_SCRCPY` / `RIX_ADB` 指向你自己的版本。
