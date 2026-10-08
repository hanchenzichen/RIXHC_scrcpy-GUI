# 让 AI 助手最大化自由发挥：授权清单与协作约定

这份文档是给「在这个仓库里干活的 AI 助手」看的，也是给仓库主人的一份清单：
**把哪些权限/约定交出去，就能换来多少自主推进。**

---

## 一、我当前实际拥有的能力（本仓库实测）

| 能力 | 状态 | 说明 |
| --- | --- | --- |
| 推分支、开 PR、改 PR 描述 | ✅ | 本次已推送 11 个提交并维护 PR #1 |
| 读仓库、读 API、读 Release | ✅ | |
| 安装纯 Python 依赖（PySide6 等） | ✅ | PyPI 可达，需要 `--trusted-host`（见第六节） |
| 在没有 root 的环境补系统图形库 | ✅ | `tools/local_sysroot.py`：下载 `.deb` 解包 + `LD_LIBRARY_PATH` |
| 跑 GUI 无头自检 | ✅ | `QT_QPA_PLATFORM=offscreen python tools/smoke_gui.py` |
| 下载并校验内置 scrcpy 核心 | ✅ | `python -m rix.vendor install` |
| **推送 `.github/workflows/`** | ❌ | 凭证缺少 `workflows` 权限，会被 GitHub 拒绝 |
| **改仓库设置**（描述 / topics / 改名 / 可见性） | ❌ | `admin: false`，403 |
| **合并 PR、打 tag、发 Release** | ⚠️ | 技术上能做，但属于对外不可逆动作，需要你明确授权 |
| **连真机调试** | ❌ | 沙箱永远没有 Android 设备 |

---

## 二、你只需要做这几件事（按性价比排序）

| 优先级 | 做什么 | 我能多做多少 |
| --- | --- | --- |
| ★★★ | 给自动化凭证补 `workflows` 权限，或自己跑一次 `python tools/install_workflows.py` | CI 由我直接维护，不用再走 `ci/workflows/` + 安装脚本的绕路 |
| ★★★ | 告诉我「默认决策策略」（第三节），不用每次确认 | 我一次推进一整批，而不是每步都停下来问 |
| ★★ | 授权我「合并自己的 PR」或明确「由你合并」 | 决定我能否走完「开发→验证→合并」闭环 |
| ★★ | 补 `administration` 权限（可选） | 我能改仓库描述/topics、改仓库名（现在只能给你脚本） |
| ★ | 在你自己机器上跑一次真机验证（连手机启动一次） | 我这边永远测不到真机行为，这是唯一的盲区 |

---

## 三、默认决策策略（建议直接采用）

以下是我在没有额外指示时会采用的默认值。**改这张表就等于改我的行为。**

| 事项 | 默认值 |
| --- | --- |
| 项目名 / 显示名 | `rix-scrcpy` / `RIX Scrcpy` |
| 许可证 | MIT 源码 + PySide6（LGPL）动态链接 |
| 语言与版本 | Python 3.10+ |
| GUI / TUI / CLI 技术栈 | PySide6 / 标准库 / argparse |
| 打包形态 | GUI = onedir（启动快、内存平缓）；CLI = onefile |
| 分支策略 | 只在 `cline/*` 分支上改，通过 PR 交付，不直接推 `main` |
| 提交粒度 | 每个「可验证的小步」一次提交，提交信息说明做了什么 |
| 测试要求 | 新增逻辑必须有单测；GUI 改动必须能过无头自检 |
| 依赖策略 | 优先标准库；新增依赖必须写进 `requirements.txt` 并说明理由 |
| 不确定时 | 选**可逆、改动小、有测试覆盖**的方案 |
| 文档 | 行为变了就同步 README 与 `docs/roadmap.md` |
| 代码风格 | 跟随现有风格；注释解释「为什么」而不是「是什么」 |

---

## 四、不可逆 / 对外可见的动作（我会先停下来问）

- 发布 Release、打 tag、删除分支或仓库、改仓库可见性
- 改仓库名、改项目名、改许可证
- 引入付费或闭源依赖
- 重写 git 历史、强制推送
- 删除用户数据（配置、预设、缓存）

**除此之外的事，默认我可以自己决定并直接做完再汇报。**

---

## 五、汇报节奏

- 做完一个可验证的批次就提交并汇报，不等确认。
- 每批次汇报固定四段：**改了什么 / 怎么验证的 / 风险与边界 / 下一步建议**。
- 需要你决策时，一次把选项列全（含我的推荐与理由），你回一句话即可。
- 我不确定的地方会明确写「未验证」，不会假装测过。

---

## 六、沙箱环境备忘（下次开工直接照做）

```bash
# 1) 装 Python 依赖（沙箱的 MITM 证书没进信任链，需要 --trusted-host）
python3 -m pip install --break-system-packages \
    --trusted-host pypi.org --trusted-host files.pythonhosted.org PySide6-Essentials

# 2) 补 Qt 需要的系统图形库（没有 root，用下载 .deb 解包的方式）
python3 tools/local_sysroot.py --wanted libgl1 libegl1 libx11-6 libglib2.0-0 \
    libxkbcommon0 libfreetype6 libfontconfig1 libdbus-1-3
export LD_LIBRARY_PATH=/tmp/sysroot/usr/lib/x86_64-linux-gnu:/tmp/sysroot/lib/x86_64-linux-gnu

# 3) 跑 GUI 无头自检（能抓出「导入即崩溃」「面板返回 None」这类真问题）
QT_QPA_PLATFORM=offscreen python tools/smoke_gui.py

# 4) 端到端验证内置 scrcpy 核心（下载 + SHA256 校验 + 解包 + 执行）
python3 -m rix.vendor install --version 5.0.1 --target /tmp/vendor_test
/tmp/vendor_test/scrcpy --version
```

已知环境限制：

- 没有 Android 真机 → 涉及设备的行为只能靠单测 + 你本机验证。
- 没有字体（fontconfig 报错）→ 生成截图会缺字，暂不产出 README 截图。
- 无 root → 系统级安装一律走「下载解包到临时目录 + 环境变量」。

---

## 七、如果你把上面的权限都给了，我会立刻做这些

1. 把 `ci/workflows/` 直接落到 `.github/workflows/`，跑通第一轮 CI 并修掉所有红灯。
2. 应用仓库描述与 topics，重命名仓库为 `rix-scrcpy`。
3. 做 roadmap 里的「本地 agent（`rix-scrcpy serve`）+ Android 远程前端」。
4. 补 GUI 懒加载、日志环形缓冲等性能项。
5. 打 `v1.1.0` tag，走一遍完整的自动发布，确认 Release 里四个产物可用。
