# RIX Scrcpy GUI — 代码评审笔记

评审范围：`main.py`、`core/`、`features/`（13 个面板），单次提交 `5755159`。
说明：本沙箱内没有 `PyQt6` / `scrcpy` / `adb`，因此以下结论来自静态阅读，
已在注释中标出「需实机验证」的项。全部文件 `compileall` 通过，无语法错误。

## 一、整体评价

- **架构选型是对的**：每个功能面板只负责「画 UI + `get_args()`」，主窗口负责
  拼装命令行，`SessionManager` 负责进程生命周期。新增一个 scrcpy 参数只需要
  在对应面板加一个控件，扩展成本很低。
- **细节上的产品思维不错**：能省略默认值的就不拼参数（`--mouse`/`--keyboard`/
  `--gamepad` 默认模式不传）、非 Linux 平台禁用 V4L2 页签、音频源与视频源联动、
  大量 tooltip 解释、快捷键速查表。这些都超出「命令行参数搬运工」的水平。
- **主要短板集中在三处**：线程/进程生命周期管理、几个「看起来能用其实会失败」
  的功能（应用列表、OTG+TCP/IP）、以及工程化（依赖声明、测试、打包、资源路径）。

## 二、P0 — 正确性 / 稳定性

1. **跨线程直接调用 + 退出时不等待线程**
   `core/session_manager.py:42-45` 在主线程里直接调用 `worker.stop()`，
   而 `ScrcpyWorker` 已经被 `moveToThread` 到别的线程，等于跨线程调用对象方法。
   同时 `stop_all_sessions()`（同文件 56-59）只是发出 stop，不等待线程结束，
   `main.py:270-273` 的 `closeEvent` 立刻 `event.accept()`。
   结果：退出时可能打印 `QThread: Destroyed while thread is still running`，
   进程也可能残留 scrcpy。建议 stop 用 `QMetaObject.invokeMethod(..., QueuedConnection)`
   或信号触发，并在 closeEvent 里统一 join（带超时兜底）。
2. **`LogReader` 逐字节读管道**
   `core/command_runner.py:19-28` 用 `self.pipe.read(1)` 循环 → 每行 N 次系统调用，
   scrcpy 日志量大时会明显吃 CPU。另外只有遇到 `\n` 才 emit，而 scrcpy 的
   进度信息多用 `\r`，会一直堆在 `line_buffer` 里。
   建议 `readline()` 或 `read(4096)` + 按 `\r`/`\n` 切分。
3. **`DevicePanel` 的 `self.thread` 被复用导致的竞态**
   `features/device_panel.py:145`、`171-182`：`update_combo_box()` /
   `on_generic_command_finished()` 都通过 `self.thread.quit()` 收尾，但
   `self.thread` 是「最近一次创建的线程」。自动配对 → 自动刷新设备列表这条链上，
   线程 A 完成时会先创建线程 B，随后 A 的 `finished` 回调把按钮重新启用，
   用户此时可再点一次（如手动刷新），`self.thread` 被换成 C；等 B 的
   `update_combo_box` 触发时，它 `quit()` 的其实是 C，B 永远不会退出（线程泄漏），
   同时 C 被提前打断。建议加 `busy` 标志位，并把 thread 作为局部变量/按次持有。
4. **同一个参数被多个面板重复拼装**
   `--no-playback`：`features/video_panel.py:135` 与 `features/recording_panel.py:114`；
   `--no-audio-playback` 同样两处；`--no-video-playback` 在 video 与 v4l2 面板各有一份。
   同一份配置里出现两个同名参数不仅含义含糊（后写的覆盖），也让「录制时后台镜像」
   这种组合变得不可预测。建议把播放控制收敛到唯一面板。
5. **OTG + TCP/IP 是无效组合**
   `main.py:230-233` 给 `-e`（唯一的 TCP/IP 设备）也起了 `TCP-OTG` 的名字。
   `--otg` 需要真实 USB 连接的设备，`-e` 场景下必然启动失败。
   建议在 OTG 分支里直接禁用 `-e` 选项并给出提示。

## 三、P1 — 功能与体验

6. **应用列表（`--start-app` 辅助）在多数设备上拿不到应用名**
   `core/command_runner.py:136-143` 通过 `adb shell "aapt d badging ..."` 取 label。
   `aapt` 在绝大多数正式版 Android（AOSP user build / 厂商 ROM）里根本不存在，
   于是每条都会走 except 分支回退成包名；又因为逐条 `adb shell`（timeout=3s），
   100 个第三方应用最坏情况要等到分钟级，这正是那句「首次加载可能需要数分钟」的来源。
   **需实机验证**后建议：优先直接缓存包名列表（scrcpy 的 `--start-app=<package>` 本就接受包名），
   或在 PC 侧用 `apkanalyzer`/`aapt` 解析 pull 下来的 APK，并改成每 50 条打一次进度。
7. **摄像头模式把整个「视频」页签禁用，导致无法设置码率/编码器/帧率**
   `main.py:187-189` 只要选摄像头就 disable 视频页，但相机模式同样需要
   `--video-bit-rate` / `--video-codec` / `--orientation` / `--crop`。
   同时 `main.py:208` 在相机模式下仍然去读**被禁用**的 `video_panel.max_size_input`，
   用户看不到也改不了这个值，却会偷偷生效。建议只禁用「视频源」相关项，
   或把 max-size 输入搬到摄像头面板。
8. **GUI 线程里跑阻塞命令（会假死）**
   `video_panel.py:93-104`（`--list-encoders` / `--list-displays`）、
   `camera_panel.py:71-85`、`v4l2_panel.py:65-78`、以及
   `developer_panel.py:104-136`（`adb push` + 启动独立 server）。
   这些操作 1~10 秒不等，期间整个窗口无响应。应统一走 `AdbWorker` 那套线程封装。
9. **设备列表隐藏了 unauthorized / offline 状态**
   `core/command_runner.py:118` 只保留 `'\tdevice'` 的行。用户插上手机（未授权、
   正在弹调试授权框）时会看到「未找到已连接的设备」，很难自查。
   建议显示设备 + 状态，并对 `unauthorized` 给出明确提示。
10. **tooltip 与实现不一致**
    `features/audio_panel.py:47-51` 写着「勾选此项会自动设置音频源」，
    但 `get_args()`（120-126）只是 `--audio-dup`，没有设置 `--audio-source=playback`。
11. **`get_args()` 带副作用**
    `v4l2_panel.py:88-89` 在构造函数里往日志写警告。getter 应该是纯的，
    否则「预览命令」这类功能会重复写日志。建议把校验提前到启动流程里。

## 四、P2 — 工程化

12. 没有 `requirements.txt` / `pyproject.toml`（README 只说 `pip install PyQt6`），
    没有一行测试，没有 CI。`core/`、`features/` 缺 `__init__.py`
    （现在靠 namespace package 能跑，但 PyInstaller/IDE 容易踩坑）。
13. `main.py:37` 的 `QIcon('RIXHC.ico')` 是相对 CWD 的路径：从别的目录启动、
    或打包成 exe 后就会丢图标。应基于 `__file__` 解析，或做冻结资源路径处理。
    `.gitignore` 里忽略 `*.spec` 说明确实在用 PyInstaller，但构建脚本没进仓库。
14. 小瑕疵：`features/camera_panel.py:108-109` 把 `import subprocess` 写在文件末尾
    （能跑，但很危险，且 `QThread` / `AdbWorker` 是未使用的 import）；
    `command_runner.py:114` 的 `retries` 参数从未使用；
    解码用 `sys.stdout.encoding`（Windows GBK 控制台下会乱码，建议固定 utf-8）。
15. **README 说「所有参数都已 UI 化」，实际还有缺口**（对照 scrcpy 3.x 文档，
    **建议按你实际使用的版本再核一遍**）：`--kill-adb-on-close`、`--port`、
    `--tcpip`（目前是手工 `adb tcpip` + `adb connect` 代替）、
    `--video-codec-options`、`--no-downsize-on-error`、`--keep-active`、
    `--forward-all-clicks`、`--clipboard-autosync`、`--camera-high-speed`、
    `--no-cleanup`、`--no-video`（audio 面板有，video 面板没有）等。
16. `developer_panel.py:124` 把 scrcpy-server 版本硬编码成 `2.4`。
    用户装的 scrcpy 版本一变，这个「独立 Server 模式」就会因协议不匹配而失败，
    建议从 `scrcpy --version` 推断或让用户显式选择。

## 五、我会优先做的三件事

1. **修 P0 的线程/进程收尾**（1、3）：这是唯一的崩溃/残留进程来源，改动量小。
2. **加「命令预览 + 复制」**：在启动按钮旁显示将要执行的完整命令行。
   成本极低，但对用户信任、以及你自己排错帮助巨大 —— 现在所有参数错误
   都只能靠用户贴日志。
3. **加「scrcpy 可执行文件路径 / 版本」设置项 + 配置预设（保存/加载）**。
    很多用户用的是 scrcpy-win64 解压版、没进 PATH；预设则能解决
    「每开一个新会话都要重填十几个字段」的核心痛点。
