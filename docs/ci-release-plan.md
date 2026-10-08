# GitHub 平台能力与 CI/发布方案（待确认，尚未实施）

> ## 实施状态（已执行）
>
> | 项目 | 状态 |
> | --- | --- |
> | LICENSE（MIT）+ 第三方说明 | 已完成 |
> | requirements.txt / pyproject.toml / 版本单一来源 | 已完成 |
> | PyQt6 → PySide6 迁移（解决 GPL/MIT 冲突） | 已完成 |
> | PyInstaller spec（GUI onedir + CLI onefile）纳入版本管理 | 已完成 |
> | `ci.yml`（Windows+Linux × Python 3.10/3.12：语法检查 + 52 个单测 + GUI 无头自检） | 已完成 |
> | `build.yml`（打 tag 自动出包 + 创建 Release） | 已完成 |
> | `upstream-drift.yml`（每周对比上游参数，自动开 Issue） | 已完成 |
> | 选项注册表生成器 + `rix` 无 GUI 核心 + CLI + TUI | 已完成 |
> | 工作流安装到 `.github/workflows/` | **待你执行**（见下） |
>
> ⚠️ 工作流文件放在 `ci/workflows/`，需要运行 `python tools/install_workflows.py`
> 复制到 `.github/workflows/` 后再推送——因为当前自动化凭证没有 `workflows` 权限，
> 直接推送该目录会被 GitHub 拒绝（`refusing to allow ... without workflows permission`）。
>
> 用你自己的账号执行：
> ```bash
> python tools/install_workflows.py
> git add .github/workflows && git commit -m "ci: enable workflows" && git push
> ```

> 本文只是方案说明，**仓库里还没有做任何改动**。你确认后我再执行。

## 一、仓库现状盘点（2026-10-08 通过 API 核对）

| 项目 | 现状 | 含义 |
| --- | --- | --- |
| 可见性 | **public** | GitHub Actions **完全免费、不限分钟数**（这条很关键） |
| 默认分支 | `main` | — |
| Stars / Forks | 4 / 0 | 已有外部用户 |
| Releases | 已有 **v1.0.0**，挂着 `RIX_Scrcpy_GUI.exe` | 说明现在是「本地打包 → 手动上传」 |
| Actions workflows | **无** | 没有 CI，也没有自动构建 |
| LICENSE 文件 | **不存在**（README 徽章写 MIT，但 API 显示 license=null） | 默认是「保留所有权利」，且与 PyQt6 的 GPLv3 冲突（见第三节） |
| Issues / Wiki | 开启 / 开启 | 可以配合 Issue 模板 |
| Discussions | 关闭 | 可选开启 |

## 二、GitHub 能替你做的事（按本项目需要排序）

| 功能 | 它能替你做什么 | 本项目的用法 |
| --- | --- | --- |
| **Actions** | 免费给你一台云端 Windows/Linux 机器，你声明「什么时候跑什么命令」 | 自动打包 exe、跑自检 |
| **workflow_dispatch** | 网页上出现一个「Run workflow」按钮 | 不写代码也能一键出包 |
| **Matrix 矩阵构建** | 一份配置同时跑 Windows + Linux + 多个 Python 版本 | Win exe + Linux tar.gz 一起出 |
| **Artifacts** | 每次运行产生的文件可在网页下载（保留 90 天） | 测试版包，不用发 Release |
| **Releases + tag** | 打 tag 自动创建发布页、挂下载文件、生成更新日志 | 取代你现在的「本地打包 + 手动上传」 |
| **Caching** | 缓存 pip / PyInstaller 依赖 | 构建从几分钟降到几十秒 |
| **Secrets** | 存放证书、令牌，不进代码库 | 将来做 Windows 代码签名 |
| **Environments + 审批** | 发布前需要你手动批准 | 防止误发布 |
| **Packages (GHCR)** | 托管 Docker 镜像 | 给 Linux CLI/TUI 用户一条 `docker run` |
| **PyPI（配合 Actions）** | `pip install rix-scrcpy` 直接装 CLI/TUI | 第 2 阶段可选 |
| **Pages** | 静态网站托管 | 文档站 / 未来的 WebUI |
| **schedule 定时任务** | 定时跑 workflow | ★ 每周检测上游 scrcpy 参数变化，自动开 Issue |
| **Dependabot / CodeQL** | 自动提依赖升级 PR、自动扫安全问题 | public 仓库免费 |
| **Rulesets 分支保护** | 保护 main，只允许 PR 合并 | 配合现在的分支工作流 |
| **Issue 模板** | 结构化 bug 报告 | 省掉来回追问环境信息 |

**结论：你是 public 仓库，上面这些全部免费，一分钱不花。**

## 三、发版时必须注意的三件事

1. **许可证冲突（最容易踩）**
   - `PyQt6` 是 **GPLv3**（不是 LGPL）。你现在 README 声称 MIT，但仓库没有 LICENSE 文件，
     且计划分发 PyInstaller 打包的 exe → 属于「GPL 代码 + MIT 声明」的矛盾状态。
   - 两条路：**① 换 `PySide6`（LGPLv3，API 几乎一样）→ 可以合法用 MIT 分发；
     ② 项目改 GPLv3 → 必须开源、不能闭源分发。**
   - 建议选 ①：反正 GUI 后续要重写，现在换成本最低。无论选哪条，都要补一个真正的 `LICENSE` 文件。
2. **不要捆绑 scrcpy / adb**
   - scrcpy 是 Apache-2.0，Android platform-tools 有自己的条款。
   - 你现在的做法（要求用户自行安装 scrcpy，程序去检测）**既省事又合规**，建议保持，
     改成「自动探测 scrcpy 路径 + 一键跳转下载页」。
3. **Windows 未签名 exe 会触发 SmartScreen「未知发布者」**
   - 免费方案：SignPath.io 对开源项目免费，有官方 GitHub Action；
   - 或至少在 Release 说明里写清「点『更多信息』→『仍要运行』」。
4. **打包形态建议用 onedir（目录 + zip）而不是 onefile**
   - onefile 每次启动都要解压到 `%TEMP%`：启动慢、占内存峰值高，还容易被杀软误报；
   - onedir 启动快、内存曲线平缓，符合你「省内存 + 无异常」的目标。

## 四、推进方案（三步，每步独立可交付、可回退）

### 第 0 步：构建与发布基座（不动任何业务逻辑）
- 新增 `LICENSE`、`requirements.txt`、`pyproject.toml`；
- `.github/workflows/ci.yml`：push / PR 时在 **windows-latest + ubuntu-latest** 上
  跑 `python -m compileall` + **无头导入自检**（`QT_QPA_PLATFORM=offscreen` 实例化主窗口，
  没有手机也能跑，能抓到真实崩溃）；
- `.github/workflows/build.yml`：`workflow_dispatch` 手动触发 + 打 `v*` tag 自动触发
  → Windows 上用 PyInstaller 出 **onedir zip**，Linux 出 tar.gz，
  产物进 Artifacts；打 tag 时自动创建 Release 并附文件；
- 把 PyInstaller 的 `.spec` 纳入版本管理（现在 `.gitignore` 忽略了 `*.spec`，
  导致构建不可复现），并在 spec 里用 `__file__` 定位 `RIXHC.ico`
  （修掉「从别的目录启动就丢图标」的 bug）。

### 第 1 步：抽核 + 选项注册表 + CLI
- `tools/gen_options.py`：从上游 `app/src/cli.c` 生成 `options.json`
  （109 个参数 + 取值 + 说明 + 引入版本）；
- CLI 骨架 + 单元测试 → 接入 CI；
- **新增定时 workflow**：每周拉一次上游 cli.c，diff 出参数增删，自动开 Issue 提醒
  （这样你再也不会像这次一样落后 32 个参数）。

### 第 2 步：多端构建
- 矩阵出包：Windows GUI（onedir zip）/ Linux GUI（tar.gz，可选 AppImage）/ CLI+TUI（zip + tar.gz）；
- 可选：PyPI 发布 `pip install rix-scrcpy`；GHCR 发布 CLI 的 Docker 镜像；
- Android 客户端出现后，直接用 ubuntu runner 构建 APK。

## 五、需要你拍板的三件事

1. **许可证**：换成 PySide6 走 MIT，还是整个项目转 GPLv3？（影响后面所有分发）
2. **是否先做第 0 步**：只加构建/发布，不碰现有代码逻辑，做完你在 GitHub 网页上
   点一下按钮就能拿到 exe。
3. **发布形态**：onedir zip（推荐）还是 onefile 单 exe？
