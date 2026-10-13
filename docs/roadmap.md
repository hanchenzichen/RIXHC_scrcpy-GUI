# 优化方向与可添加功能

本文件记录「接下来还能做什么」，已完成的会打勾。分四类：性能/内存、稳定性、
体验、工程与分发。

## 一、已完成（本轮）

- [x] **选项注册表**：从上游 `cli.c` 自动生成，109/109 参数 + 20 个枚举自动提取
- [x] **内置 scrcpy 核心**：官方发布包 + SHA256 校验 + 原样保留上游 LICENSE
- [x] **三端共用一份核心**：GUI / TUI / CLI 都走 `rix`
- [x] **命令预览**（GUI）：启动前可查看并复制完整命令行
- [x] **配置预设**：CLI 与 TUI 已支持，可跨会话复用
- [x] **`doctor` 体检**：检查 scrcpy/adb/版本/参数健康度
- [x] **GUI「全部参数」页签**：由注册表自动渲染，上游加参数即自动出现
- [x] **应用列表改用 `scrcpy --list-apps`**：从分钟级降到秒级，且能拿到应用名
- [x] **参数去重**：同名参数只保留最后一个，消除面板间的冲突
- [x] **修复幽灵参数** `--server-debugger`、**修摄像头模式的页签联动**
- [x] **P0 修复**：日志块读取、退出等待线程、图标路径
- [x] **CI/CD**：测试矩阵、构建发布、上游漂移监控
- [x] **许可证合规**：PySide6（LGPL）替代 PyQt6（GPL），附第三方声明

## 二、性能与内存

- [x] **GUI 面板懒加载**：切换到页签时才构建面板（`main.py` 的 `_ensure_panel`）；
      无头自检中加入了「构造后不得建出全部面板」的回归检查。
- [x] **日志环形缓冲**：日志面板改用 `QPlainTextEdit` 并设置 `setMaximumBlockCount(5000)`。
- [ ] 日志导出到文件。
- [ ] **会话列表虚拟化**：多开会话很多时，用 `QListView` + model 替代逐个 widget。
- [ ] **`scrcpy --version` 结果缓存**：避免每次刷新都起进程。
- [ ] **可选：TUI 用 Textual**：现在 TUI 是纯标准库实现（省内存但观感朴素）。
      可以做成「检测到 textual 就用它，否则回退标准库版」。

## 三、稳定性

- [ ] **会话监督升级**：`ScrcpyWorker.run()` 目前阻塞在 worker 线程里，
      停止只能跨线程直接调用。建议改为独立 `threading.Thread` + 队列，
      Qt 只负责信号投递，彻底消除跨线程调用。
- [ ] **进程组回收**：Windows 上用 `CREATE_NEW_PROCESS_GROUP` + `taskkill /T`
      确保 scrcpy 的子进程（如 adb）也被回收。
- [ ] **崩溃日志**：`sys.excepthook` + Qt 异常钩子，写入
      `%LOCALAPPDATA%/rix-scrcpy/logs/`，便于用户反馈。
- [ ] **断线自动重连**：无线连接掉线后自动重试 N 次。
- [ ] **CI 增加打包产物冒烟**：目前只测了 CLI 单文件；GUI 产物应做一次
      「解压 → 启动 → 退出」的检查（Windows runner 可用 offscreen 平台）。

## 四、体验

- [ ] **首启动向导**：检测不到 scrcpy 时，引导「一键下载内置核心」或「指定路径」。
- [ ] **GUI 接入预设**：`rix.profiles` 已可用，GUI 只需加一个下拉框与保存按钮。
- [ ] **GUI 显示版本与体检结果**：把 `doctor` 的输出做成一屏「环境」页。
- [x] **设备状态可视化**：CLI、agent 与 GUI 日志均会显示 `unauthorized` / `offline` 状态，
      并给出「请在手机上允许 USB 调试」等提示。
- [ ] **虚拟显示面板与注册表合并**：`--new-display` / `--flex-display` /
      `--display-ime-policy` 在「全部参数」页签里也能设置，存在重复入口。
- [ ] **快捷键冲突提示**：`--shortcut-mod` 与系统快捷键冲突时给出提醒。
- [ ] **多语言**：目前 UI 中文为主，可抽出 `i18n/` 做中英双语。

## 五、工程与分发

- [x] **本地 agent**：`rix-scrcpy serve` 提供 HTTP JSON 接口（会话、设备、参数、预设、
      日志增量拉取），并内置 Web 控制台，手机浏览器即可使用；默认仅监听 `127.0.0.1`，
      支持 `--token` 限制访问。
- [x] **移动端可用入口**：由 agent 提供 Web 控制台，手机浏览器即可查看设备、启停会话与查看输出。
- [ ] **原生 Android 客户端**：远程前端（连 PC 上的 agent）；
      原生客户端（Kotlin + MediaCodec + ADB 协议库）属于独立项目。
- [ ] **Linux AppImage**：比 tar.gz 更友好。
- [ ] **PyPI 发布**：`pip install rix-scrcpy` 即可用 CLI/TUI。
- [ ] **GHCR 镜像**：给 Linux CLI 用户一条 `docker run`。
- [ ] **Windows 代码签名**：SignPath.io 对开源免费，可消除 SmartScreen 警告。
- [ ] **上游版本监控增强**：除参数外，再监控 scrcpy 新版本发布，
      自动提 PR 更新 `ci/workflows/build.yml` 里的 `SCRCPY_VERSION`。
- [ ] **测试覆盖**：GUI 侧的联动逻辑（页签启用、去重、摄像头模式）目前靠
      无头自检兜底，可以补一个 `pytest-qt` 级别的用例。
- [ ] **`docs/` 整理**：把评审记录归档，正文只保留用户文档。

## 六、明确不做（及原因）

- **不自己实现 ADB 协议**：adb 已经是稳定可靠的组件，重写没有收益。
- **不在 Android 上跑 scrcpy 引擎**：scrcpy 依赖桌面渲染栈与 adb server，
  不可行；Android 端只能做「远程前端」或「原生客户端」。
- **不修改上游 scrcpy 二进制**：一旦修改就要承担维护与许可证上的额外义务，
  且会让 SHA256 校验失去意义。
