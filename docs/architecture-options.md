# 多端架构与 UI 技术选型建议

> 前提假设：提问里的 “thinker” 指的是 **Tkinter**。
> 需求归纳：① 内存占用低 ② 无异常/稳定体验 ③ 覆盖 scrcpy 全部功能
> ④ Android + Windows 图形客户端 ⑤ Windows/Linux 的 TUI/CLI。

## 一、结论先行

1. **不要试图用「一个 UI 框架」同时打四个端。** 把核心逻辑抽成无 UI 依赖的库，
   四端都做薄壳。这是唯一能让 4 个客户端不变成 4 倍工作量的办法。
2. **UI 框架按端各选**：Windows GUI 走「低内存」路线（Tkinter/ttk 或 Rust+Slint），
   TUI 单独选（Textual 或 ratatui），Android 不要指望复用桌面 GUI 框架。
3. **最关键的一条**：不要再用手写面板维护 109 个参数。改成
   **由上游 `cli.c` / `scrcpy --help` 自动生成的「选项注册表」驱动 UI 与参数拼装**。
   这样「scrcpy 全部功能」是**构造上保证**的，而不是靠人工追版本
   （你现在落后 32 个参数、还带着一个幽灵参数，根因就是这个）。
4. **Android 跑不了 scrcpy 引擎**（见第四节），必须选「远程前端」或「原生客户端」二选一。

## 二、UI 框架对比（内存 / 稳定 / 打包 / 多端复用）

典型常驻内存（量级参考，务必在自己目标机上实测）：

| 方案 | 语言 | 典型 RSS | 打包体积 | 开发速度 | 覆盖全参数 UI | Android | TUI |
| --- | --- | --- | --- | --- | --- | --- | --- |
| Tkinter/ttk | Python | 25–45 MB | PyInstaller ~15–25 MB | 中（控件少、样式旧） | 够用（表单为主） | ❌（Kivy 是另一套） | ❌ |
| PyQt6/PySide6（现状） | Python | 60–110 MB | ~60–90 MB | 快（控件最全） | 很好 | ❌ | ❌ |
| Dear PyGui / imgui | Python/C++ | 25–45 MB | ~20–30 MB | 快（但非原生观感） | 好 | ❌ | ❌ |
| Rust + Slint | Rust | 15–30 MB | 单 exe 5–15 MB | 中 | 好（声明式 .slint） | ✅ 官方支持 | ❌ |
| Rust + egui/iced | Rust | 15–30 MB | 单 exe 5–15 MB | 中 | 好 | 勉强（非官方路径） | ✅（ratatui 同生态） |
| Tauri（Web 前端） | Rust+Web | 60–120 MB（WebView2 另计） | ~10 MB + 运行时 | 快 | 很好 | ❌ | ❌ |
| Flutter desktop | Dart | 80–150 MB | ~40 MB | 快 | 很好 | ✅（同语言） | ❌ |
| Avalonia / WinUI3 | C# | 60–120 MB | 自包含 ~60 MB | 快 | 很好 | ✅（Avalonia） | ❌ |

**关于「省内存」的真相**：GUI 框架之间差的这 40 MB，通常被 scrcpy 自己
（视频解码缓冲 + 渲染）100–300 MB 的占用盖过去了。所以：

- 真正在意内存 → **优先把 TUI/CLI 做好**（不开 GUI 时几乎零额外开销），
  GUI 只在需要可视化配置时开；
- 目标机是低配 Windows → Tkinter 或 Rust+Slint 才是有意义的优化；
- **别为了省内存选 Tauri/Flutter**，它们的运行时反而更重。

**关于「无异常」**：这一项和框架基本无关，真正的风险点是
① 线程/进程生命周期（`core/session_manager.py` 那几个 P0）
② GUI 与已安装 scrcpy 的**版本漂移**（→ 用 `scrcpy --version` + 注册表版本门控）
③ 打包（PyInstaller + Qt 插件、图标相对路径、PATH 里没有 adb/scrcpy）
④ Windows 控制台的 UTF-8/ANSI 编码（TUI 尤其容易翻车）
⑤ 多设备/多会话并发。

## 三、推荐架构：一份核心 + 四个薄壳

```
                    ┌──────────────── 选项注册表（自动生成） ────────────────┐
                    │ tools/gen_options.py ← 上游 app/src/cli.c / --help    │
                    │ 产出 options.json：109 个参数 + 版本区间 + 取值 + 互斥 │
                    └────────────────────────┬─────────────────────────────┘
                                             │
   ┌─────────────────────────────────────────┴──────────────────────────────┐
   │  core（无 UI 依赖，可单测）                                            │
   │   • profile 模型（保存/加载/校验）   • 命令拼装（registry → argv）      │
   │   • 版本探测与门控   • 会话监督（spawn/stop/日志流/多实例）             │
   └─────────────────────────────────────────┬──────────────────────────────┘
                                             │
                          ┌──────────────────┴──────────────────┐
                          │  本地 agent（127.0.0.1 JSON-RPC/WS） │
                          │  会话列表 / 启动停止 / 日志流 / 能力查询│
                          └───┬───────────────┬───────────────┬──┘
                              │               │               │
                     Windows GUI        TUI / CLI        Android 客户端
                     (Tkinter 或 Slint)  (Textual/ratatui) (远程前端，连 agent)
```

为什么要有 agent 这一层：它是「四端复用」的杠杆点，同时**顺手把远程控制做出来了**
（你 `developer_panel.py` 里已经在折腾 tunnel host，这条路的终点就是它）。
Android 端只要能连到 PC 上的 agent，就不需要重新实现任何 scrcpy 逻辑。

## 四、Android 端：能不能做到，取决于你要哪一种

| 方案 | 可行性 | 工作量 | 说明 |
| --- | --- | --- | --- |
| A. Android 当**遥控器**（PC 跑 scrcpy，手机连 PC 的 agent） | ✅ 完全可行 | 1–2 周 | 甚至可以先做一个 WebUI 塞进 WebView，零 Android 开发量 |
| B. Android 当**独立 scrcpy 客户端**（自己连 USB OTG 上的设备、自己解码） | ⚠️ 可行但很重 | 数月 | 需要 Kotlin + MediaCodec 解 H.264 + 自己实现 ADB 协议（社区有 AdbLib / libadb-android 这类库）与 scrcpy 协议；还要处理 USB host 权限、OTG 兼容性、厂商 ROM 差异 |
| C. Android 上**直接跑 scrcpy 引擎** | ❌ 不可行 | — | scrcpy 是桌面程序：依赖 SDL/FFmpeg 桌面渲染 + 需要 adb server；Termux 里跑 aarch64 版属于玩具级，要 X11 + OTG 权限 |

**建议先做 A，把 B 当作独立项目立项。** 注意 A 也顺带覆盖了「手机看平板/看另一台手机」
之外的大多数实际需求（在沙发上用手机控制 PC 上连着的设备）。

## 五、TUI/CLI 怎么做最划算

- **CLI 先做，而且要能表达全部参数**：
  `rix run --profile gaming --set video-bit-rate=16M --set capture-orientation=90 --extra-args "--foo=bar"`。
  有了 `--extra-args` 透传，即使注册表暂时缺某个新参数，用户也不会被卡住。
- **TUI 用同一份注册表渲染**：Python 选 Textual（开发快，内存 60–90 MB，
  比 PyQt6 轻但不算「极省」）；真要省内存选 Rust 的 ratatui（10–20 MB 单 exe）。
- Windows 上 TUI 要注意：现代 Windows Terminal 支持 ANSI，但老 conhost 需要
  VT 模式（Textual/rich 已处理；自己写要注意），另外中文/emoji 宽度对齐容易错行。

## 六、前进方向（每阶段都能独立交付）

| 阶段 | 内容 | 产出 |
| --- | --- | --- |
| P0 抽核 | `core/` 去掉 UI 依赖；写 `tools/gen_options.py` 生成 `options.json`；CLI 跑通全部参数 | 一个能在 Win/Linux 用的 CLI |
| P1 agent | core 包成本地 JSON-RPC/WS 服务（会话列表、启动停止、日志流、能力查询） | 后续所有客户端的地基 |
| P2 Windows GUI | 由注册表自动渲染分组表单（分组直接对齐上游 doc 的章节）+ 命令预览 + 配置预设 + 版本检测 | 替代现在的 13 个手写面板 |
| P3 TUI | 同一份注册表渲染，支持 profile 切换与日志面板 | Win/Linux TUI |
| P4 Android | 先做远程前端（连 agent），后续再评估原生客户端 | Android 客户端 |

## 七、给你的具体建议

- **想省内存又要开发快**：Windows GUI 用 **Tkinter/ttk**（Python 生态不换语言），
  TUI 用 Textual，CLI 用 argparse。代价是 UI 观感朴素、复杂联动控件要自己搭。
- **想要真正的单文件小内存 + 未来上 Android**：整体迁 **Rust + Slint**
  （桌面 + Android 同一套 `.slint` 描述），TUI 用 ratatui，CLI 用 clap。
  代价是重写工作量。
- **想保留现在的观感**：继续 PyQt6，但**必须**先把「注册表驱动」和「抽核」做掉，
  否则每跟一个上游版本就要手改十几个文件（这次的 32 个缺失参数就是证据）。
- 不论选哪条路，**顺序都应该是：注册表 → 抽核 → CLI → agent → GUI/TUI → Android**。
  先做 CLI/注册表，成本最低、收益最大，而且它同时也是 GUI 的地基。
