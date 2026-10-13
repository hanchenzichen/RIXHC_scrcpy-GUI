# 更新日志

本项目遵循[语义化版本](https://semver.org/lang/zh-CN/)。

## [1.2.0]

### 新增

- **本地 agent 与 Web 控制台**：`rix-scrcpy serve` 启动 HTTP JSON 接口，
  并在 `/` 提供内置控制台。手机浏览器打开局域网地址即可查看设备、启动/停止会话、
  实时查看输出，无需安装桌面程序。默认仅监听 `127.0.0.1`，局域网访问需显式指定
  `--host 0.0.0.0`，并建议配合 `--token`。
- **无 GUI 依赖的会话管理层**（`rix/sessions.py`）：供 CLI、TUI 与 agent 共用，
  每个会话独立收集输出并采用环形缓冲，支持整组结束子进程。
- **`rix-scrcpy apps`**：通过 `scrcpy --list-apps` 列出设备上可启动的应用。
  相比早期依赖设备端 `aapt` 的实现，耗时由分钟级降至秒级，且能稳定获取应用名。
- **`rix-scrcpy vendor`**：下载官方 scrcpy 核心并做 SHA256 校验，支持 `status` / `install` / `path`。
- **内置 scrcpy 核心**：发布包内含官方 scrcpy（含 adb），查找优先级为
  `RIX_SCRCPY` 环境变量 → 内置核心 → 用户目录 → 系统 PATH。
- **GUI「全部参数」页签**：由选项注册表自动渲染，覆盖 scrcpy 全部 109 个参数。
- **命令预览**：启动前可查看并复制完整命令行。

### 改进

- **选项注册表**：由上游 `app/src/cli.c` 自动生成，109/109 个参数与 20 个枚举
  均可自动同步；新增 `--capture-orientation`、`--flex-display`、`--camera-zoom`、
  `--hwdec`、`--render-fit` 等此前缺失的参数。
- **GUI 面板懒加载**：切换到页签时才构建面板，降低启动时间与常驻内存。
- **日志环形缓冲**：日志面板最多保留 5000 行，避免长时间运行持续占用内存。
- **参数去重**：同名参数只保留最后一个，消除面板之间的冲突。
- **设备列表保留 unauthorized / offline 状态**，并提示用户检查手机授权。
- **摄像头模式**：不再禁用整个视频页签，仅禁用真正冲突的 `--display-id`。
- **退出时等待会话线程结束**，避免残留进程与线程告警。
- **日志读取改为块读取**，并同时处理 `\n` 与 `\r` 分隔，降低 CPU 占用。
- 图标路径基于 `__file__` / `sys._MEIPASS` 解析，任意工作目录均可正常显示。

### 修复

- 移除不存在的参数 `--server-debugger`（它只是构建期 meson 选项，
  误用会导致 scrcpy 以 unrecognized option 直接退出）。
- 修复 `developer_panel.get_args()` 因缩进错误而返回 `None` 的问题。
- 修复 `adb devices` 输出解析：不再把 adb 守护进程的启动信息当成设备。
- 修复 OTG 模式与「唯一的 TCP/IP 设备」组合无效的问题，改为给出明确提示。

### 工程

- **许可证**：GUI 由 PyQt6（GPLv3）迁移到 PySide6（LGPLv3），源码以 MIT 分发；
  新增 `THIRD_PARTY_NOTICES.md` 说明随包分发的第三方组件。
- **CI/CD**：新增测试矩阵、构建发布、上游参数漂移监控三个工作流；
  新增两个 PyInstaller 配置（GUI 使用 onedir，CLI 使用 onefile）。
- **测试**：98 个单元测试，另有 GUI 无头自检与基于 `ast` 的面板结构静态检查。
- 新增 `tools/`：注册表生成、版本一致性校验、工作流安装、仓库信息更新、
  项目改名、无 root 环境补齐系统库等脚本。

## [1.1.0]

- 初始的 GUI 版本：连接管理、多会话、按官方文档划分的配置面板。
