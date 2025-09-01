# RIX Scrcpy GUI

![Python](https://img.shields.io/badge/Python-3.9+-blue.svg) ![PyQt6](https://img.shields.io/badge/PyQt-6-green.svg) ![License](https://img.shields.io/badge/License-MIT-yellow.svg)

一个功能极其全面的 Scrcpy 图形化控制中心，旨在将 Scrcpy 官方文档中的所有命令行参数都转化为直观的 UI 选项。

A feature-rich GUI control center for Scrcpy, designed to bring all the command-line options from the official documentation into an intuitive user interface.

## 🌟 核心特性 (Core Features)

- **📱 连接管理器**: 支持 USB/无线连接, 自动配对, 多设备选择。
- **🚀 多开会话**: 同时管理多个 scrcpy 实例，每个实例都有独立的配置。
- **🎬 全功能面板**: 精细控制视频、音频、录制、摄像头、键盘、鼠标、游戏手柄、窗口、虚拟显示等所有 scrcpy 参数。
- **🎮 OTG 模式**: 支持在不开启 USB 调试的情况下，通过物理键鼠模式直接控制设备。
- **💡 智能引导**: 自动禁用不兼容的选项，提供配置提示和快捷键速查表。
- **跨平台**: 基于 Python 和 PyQt6 构建，可在 Windows, macOS 和 Linux 上运行。

## 🛠️ 安装与运行 (Installation & Usage)

### 依赖 (Prerequisites)

1.  **Python 3**: 确保您的电脑上安装了 Python 3.9 或更高版本。
2.  **Scrcpy**: 确保 `scrcpy` 和 `adb` 已经安装，并且可以在您的命令行中直接运行。
3.  **项目依赖**: 在项目根目录下，通过命令行安装 PyQt6：
    ```bash
    pip install PyQt6
    ```

### 运行 (Running the application)

在项目的根目录下，通过命令行启动主程序：

```bash
python main.py
