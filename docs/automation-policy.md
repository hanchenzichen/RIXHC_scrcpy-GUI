# 自动化协作约定

本仓库接受自动化助手参与开发。本文件说明协作边界、默认技术决策与变更汇报方式，
便于维护者与后续贡献者判断：**哪些改动可以直接提交，哪些必须先确认。**

---

## 一、环境能力与限制

| 能力 | 状态 | 说明 |
| --- | --- | --- |
| 推送分支、创建与更新 PR | ✅ | 交付方式为 `cline/*` 分支 + PR |
| 读写 Issue、Release、Actions 记录 | ✅ | |
| 安装 Python 依赖 | ✅ | 沙箱内需 `--trusted-host`（见第六节） |
| 无 root 环境下补齐系统图形库 | ✅ | `tools/local_sysroot.py`：下载 `.deb` 解包 + `LD_LIBRARY_PATH` |
| GUI 无头自检 | ✅ | `QT_QPA_PLATFORM=offscreen python tools/smoke_gui.py` |
| 下载并校验内置 scrcpy 核心 | ✅ | `python -m rix.vendor install` |
| 推送 `.github/workflows/` | ❌ | 凭证缺少 `workflows` 权限，GitHub 会拒绝推送 |
| 修改仓库设置（描述 / topics / 改名 / 可见性） | ❌ | 需要 `administration` 权限 |
| 合并 PR、打 tag、发布 Release | ⚠️ | 技术上可行，属对外不可逆动作，需事先确认 |
| 连接 Android 真机 | ❌ | 无设备，涉及设备的行为只能靠单元测试与维护者本地验证 |

---

## 二、需要维护者执行的操作

以下操作依赖仓库管理员权限，无法由自动化流程完成。

| 项目 | 操作 | 原因 |
| --- | --- | --- |
| Actions 令牌权限 | Settings → Actions → General → Workflow permissions → **Read and write** | 发布作业需要创建 Release，否则会失败 |
| 启用工作流 | `python tools/install_workflows.py`，随后提交 `.github/workflows/` 并推送 | 自动化凭证无法推送该目录 |
| 仓库信息 | `python tools/apply_repo_metadata.py` | 修改描述与 topics 需要 `administration` 权限 |
| 项目改名 | `python tools/rename_project.py --rename-repo` | 修改仓库名需要 `administration` 权限 |
| 真机验证 | 连接设备启动一次完整会话 | 自动化环境没有 Android 设备 |

---

## 三、默认技术决策

未收到额外指示时，采用下列默认值：

| 事项 | 默认值 |
| --- | --- |
| 项目名 / 显示名 | `rix-scrcpy` / `RIX Scrcpy` |
| 许可证 | 源码 MIT + PySide6（LGPL v3）动态链接 |
| 语言与版本 | Python 3.10+ |
| GUI / TUI / CLI 技术栈 | PySide6 / 标准库 / argparse |
| 打包形态 | GUI 使用 onedir（启动快、内存曲线平缓）；CLI 使用 onefile |
| 分支策略 | 仅在 `cline/*` 分支改动，通过 PR 交付，不直接推送 `main` |
| 提交粒度 | 每个可验证的小步一次提交，提交信息说明改动内容 |
| 测试要求 | 新增逻辑必须有单元测试；GUI 改动必须通过无头自检 |
| 依赖策略 | 优先标准库；新增依赖须写入 `requirements.txt` 并说明理由 |
| 取舍原则 | 不确定时选择可逆、改动小、有测试覆盖的方案 |
| 文档 | 行为变更同步更新 README 与 `docs/roadmap.md` |

---

## 四、需要事先确认的动作

- 发布 Release、打 tag、删除分支或仓库、变更仓库可见性
- 更改项目名、包名或许可证
- 引入付费或闭源依赖
- 重写 Git 历史、强制推送
- 删除用户数据（配置、预设、缓存）

除上述范围外的改动，默认可以直接实施，完成后汇报。

---

## 五、变更汇报格式

每批改动完成后，在对应的 Issue 下更新，固定四段：

1. **改动内容**（涉及文件与行为变化）
2. **验证方式**（测试数量、无头自检、实测输出）
3. **风险与边界**（未验证的部分明确标注）
4. **后续建议**（含需要维护者决策的选项）

---

## 六、沙箱环境备忘

```bash
# 1) 安装 Python 依赖（沙箱的中间人证书未进入信任链，需 --trusted-host）
python3 -m pip install --break-system-packages \
    --trusted-host pypi.org --trusted-host files.pythonhosted.org PySide6-Essentials

# 2) 补齐 Qt 依赖的系统图形库（无 root，采用下载 .deb 解包的方式）
python3 tools/local_sysroot.py --wanted libgl1 libegl1 libx11-6 libglib2.0-0 \
    libxkbcommon0 libfreetype6 libfontconfig1 libdbus-1-3
export LD_LIBRARY_PATH=/tmp/sysroot/usr/lib/x86_64-linux-gnu:/tmp/sysroot/lib/x86_64-linux-gnu

# 3) GUI 无头自检（可发现「导入即崩溃」「面板返回 None」等问题）
QT_QPA_PLATFORM=offscreen python tools/smoke_gui.py

# 4) 内置 scrcpy 核心端到端验证
python3 -m rix.vendor install --version 5.0.1 --target /tmp/vendor_test
/tmp/vendor_test/scrcpy --version
```

已知限制：无 Android 真机；无字体（生成截图会缺字）；无 root（系统级安装统一走临时目录 + 环境变量）。

---

## 七、仓库文本规范

本仓库为公开仓库，所有文本面向公众，需保持中性的项目文档语气：

- **适用范围**：提交信息、Issue、PR 标题与描述、文档、代码注释。
- **应当避免**：一对一对话语气（如「你只需要…」「我会…」）、协作过程细节
  （通知设置、权限协商、口令式确认）。
- **建议写法**：以「本项目」「维护者」「使用者」为主语，说明事实、原因与影响。
- **内部协调内容**（权限申请、通知渠道、进度同步方式）不写入仓库。
