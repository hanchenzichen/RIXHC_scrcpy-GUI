# RIX Scrcpy

![Python](https://img.shields.io/badge/Python-3.10+-blue.svg) ![PySide6](https://img.shields.io/badge/Qt-PySide6-green.svg) ![License](https://img.shields.io/badge/License-MIT-yellow.svg) ![Options](https://img.shields.io/badge/scrcpy%20options-109%2F109-success.svg)

一个功能完整的 Scrcpy 控制中心：**GUI + TUI + CLI 三种前端，共用同一份核心**。
目标是把 scrcpy 的**全部命令行参数**都变成可点、可填、可预览的选项，并且**自动跟随上游版本**。

A feature-complete control center for [scrcpy](https://github.com/Genymobile/scrcpy) with
GUI, TUI and CLI front-ends sharing one headless core.

---

## 🌟 核心特性

- **📱 连接管理器**：USB / 无线连接、USB 自动配对、多设备选择。
- **🚀 多开会话**：同时管理多个 scrcpy 实例，各自独立配置。
- **🎬 全参数覆盖**：由 `app/src/cli.c` 自动生成的**选项注册表**驱动，当前覆盖 scrcpy **109/109** 个长参数（含 vp8/vp9、m4a/mka/aac、`--capture-orientation`、`--flex-display`、`--camera-zoom`、`--hwdec` 等新参数）。
- **📦 内置 scrcpy 核心**：随程序分发**官方发布包**（含 adb），下载时用上游 `SHA256SUMS.txt` 校验，
  解包后原样保留上游 LICENSE。不再需要用户自己装 scrcpy 或配 PATH。
- **🧩 「全部参数」页签**：由注册表自动渲染，GUI 里也能设置全部 109 个参数。
- **⚡ 秒级应用列表**：用 `scrcpy --list-apps` 取可启动应用（旧方案依赖设备上的 aapt，多数手机根本没有）。
- **🔍 命令预览**：启动前可查看并复制完整命令行，排错不用再猜。
- **💾 配置预设**：把常用组合存成 profile，一键复用。
- **🧭 三种前端**：Windows/Linux 桌面 GUI、跨平台 TUI、可脚本化的 CLI。
- **🩺 自带体检**：`rix-scrcpy doctor` 会检查 scrcpy/adb 是否就绪、版本是否够新、参数是否健康。

## 🖥️ 三种前端

| 前端 | 启动方式 | 适用场景 |
| --- | --- | --- |
| GUI | `python main.py` 或打包好的 `RIX_Scrcpy_GUI` | 日常可视化配置 |
| CLI | `rix-scrcpy run --set ...` | 脚本、批处理、CI、远程 SSH |
| TUI | `rix-scrcpy-tui` 或 `python -m rix.tui` | 没有桌面环境、想省内存 |

## 🛠️ 安装与运行

### 依赖

1. **Python 3.10+**
2. **scrcpy** 与 **adb**：**通常不需要自己安装**——发布包已内置官方 scrcpy 核心（含 adb）。
   如果你已有自己的版本，查找优先级为：
   `RIX_SCRCPY` 环境变量 → 内置核心 → 用户目录（`vendor install`）→ 系统 PATH。
3. Python 依赖：

```bash
pip install -r requirements.txt      # GUI 需要 PySide6
pip install -e .                     # 安装 CLI/TUI 命令（可选）
```

### GUI

```bash
python main.py
```

### CLI（无需图形环境）

```bash
rix-scrcpy doctor                       # 体检：内置核心/scrcpy/adb/版本/参数
rix-scrcpy vendor install               # 下载官方 scrcpy 核心（SHA256 校验）
rix-scrcpy apps --json                  # 列出设备上可启动的应用（秒级）
rix-scrcpy options --search codec -v    # 浏览全部参数
rix-scrcpy check --set video-bit-rate=16M --set capture-orientation=90
rix-scrcpy run --set max-fps=60 --set no-audio --print
rix-scrcpy profiles save gaming --set max-fps=60 --set no-audio
rix-scrcpy run --profile gaming
rix-scrcpy run --set no-audio --extra-args "--some-future-flag"
```

### TUI

```bash
python -m rix.tui
rix> ls video
rix> set video-bit-rate=16M
rix> set capture-orientation=90
rix> preview
rix> run
```

## 🧠 它是怎么做到「覆盖全部参数」的

上游 scrcpy 每个版本都会增删参数。手工维护 UI 面板必然跟不上——本项目早期版本就曾
落后 32 个参数、还误把一个从不存在的 `--server-debugger` 做成了开关。

现在改成**自动生成 + 语义叠加**：

```
上游 app/src/cli.c  ──tools/gen_options.py──▶  rix/data/options.generated.json
                                                 （109 个参数：名称/短参数/取值/帮助/枚举）
                                                        │
                      rix/data/options.meta.json  ────────┤（手工维护：互斥、依赖、别名、平台限制）
                                                        ▼
                                               rix/registry.py（查询 / 校验 / 拼命令行）
                                                        │
                            ┌───────────────────────────┼───────────────────────────┐
                          GUI                          TUI                         CLI
```

枚举取值也是自动抓的（顺着 `cli.c` 的 switch 分支找到 `parse_xxx()`，再提取 `strcmp` 字面量），
所以上游新增 `vp8/vp9`、`m4a/mka/aac` 这类取值时，不会再有「下拉框缺选项」的问题。

**上游变了怎么办**：`.github/workflows/upstream-drift.yml` 每周自动对比一次，
有变化就自动开 Issue，处理方式只有两步——重新生成 + 补语义。

## 📁 目录结构

```
main.py                  GUI 入口
core/                    GUI 侧的进程/线程管理（Qt 相关）
features/                各个设置面板（GUI）
rix/                     无 GUI 依赖的核心
  registry.py            选项注册表：查询 / 校验 / 拼装命令行
  profiles.py            配置预设
  scrcpy_bin.py          定位 scrcpy/adb、读版本
  cli.py                 CLI（rix-scrcpy）
  tui/                   TUI（纯标准库）
  data/                  自动生成的注册表 + 手工语义层
tools/
  gen_options.py         从上游 cli.c 生成注册表
  check_version.py       版本一致性校验（CI 用）
  smoke_gui.py           GUI 无头自检（CI 用）
tests/                   69 个单元测试
docs/                    评审记录、架构方案、CI 方案、优化路线（roadmap.md）
RIX_Scrcpy.spec          GUI 打包配置（onedir）
RIX_Scrcpy_CLI.spec      CLI 打包配置（onefile）
ci/workflows/            GitHub Actions 工作流定义（用 install_workflows.py 安装）
```

## 👩‍💻 开发

```bash
python tools/gen_options.py                # 重新生成注册表（需要网络）
python tools/gen_options.py --source path/to/cli.c   # 或从本地文件生成
python -m unittest discover -s tests -t .  # 跑测试
QT_QPA_PLATFORM=offscreen python tools/smoke_gui.py  # GUI 无头自检
python tools/check_version.py              # 版本一致性
```

## 🚀 CI / 发布

> **注意**：工作流定义放在 `ci/workflows/`，需要安装到 `.github/workflows/` 后才会生效：
>
> ```bash
> python tools/install_workflows.py          # 复制到 .github/workflows/
> python tools/install_workflows.py --check  # 检查是否已安装且内容一致
> ```
>
> 之所以不直接放在 `.github/workflows/`：某些自动化凭证没有 `workflows` 权限，
> 推送该目录会被 GitHub 拒绝。用你自己的账号（或已授权的 token）推送即可。

### 内置核心是怎么来的

构建时由 CI 执行（见 `ci/workflows/build.yml`）：

```bash
python -m rix.vendor install --version 5.0.1 --target vendor/scrcpy
```

它会下载官方发布包 → 用 `SHA256SUMS.txt` 校验 → 解包到 `vendor/scrcpy/`，
然后由 `RIX_Scrcpy.spec` 一起打进安装包。升级 scrcpy 只需改工作流里的
`SCRCPY_VERSION`。合规说明见 `THIRD_PARTY_NOTICES.md`。

| 工作流 | 触发 | 作用 |
| --- | --- | --- |
| `ci.yml` | push / PR | Windows + Linux × Python 3.10/3.12 跑语法检查、69 个单元测试、GUI 无头自检；另有「内置核心端到端」作业真实下载官方 scrcpy 并执行 |
| `build.yml` | 打 `v*` tag 或手动 | 打包 Windows/Linux 的 GUI（onedir）与 CLI（onefile），打 tag 时自动创建 Release |
| `upstream-drift.yml` | 每周一 / 手动 | 对比上游 scrcpy 参数，有变化自动开 Issue |

发布流程：把 `rix/__init__.py` 的 `__version__` 改成新版本 → 提交 → 打 tag（如 `v1.1.0`）→
CI 会校验 tag 与代码版本一致，然后构建全部产物并创建 Release。

## ⚠️ 关于许可证（重要）

- 本项目使用 **PySide6（LGPL v3）** 而不是 PyQt6（GPL v3），因此可以合法地以 **MIT** 分发打包好的程序。
- 发布包内置的是**未经修改的官方 scrcpy 发布包**（Apache-2.0，其中也包含 adb），
  上游 `LICENSE` 文件原样保留在包内 `scrcpy/` 目录，并有 `SHA256` 校验；
  详见 `THIRD_PARTY_NOTICES.md`。不想用内置核心的话，删掉 `scrcpy/` 目录即可自动回退到系统 PATH。
- Windows 上未签名的 exe 首次运行会触发 SmartScreen 提示，点「更多信息」→「仍要运行」即可。
