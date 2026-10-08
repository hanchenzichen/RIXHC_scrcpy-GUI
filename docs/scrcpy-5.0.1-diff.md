# 与上游 scrcpy 5.0.1 的差异报告

核对基准：上游 `master` @ `a60891a`（meson version 5.0.1），Release 页最新为
**v5.0.1，发布于 2026-10-08**。复现命令见文末附录。

## 摘要

| 项目 | 结论 |
| --- | --- |
| 上游最新版本 | **5.0.1**（前一个 5.0，再往前 4.1 / 4.0 / 3.3.4） |
| 你的 GUI 面向的版本 | 至少需要 **≥ 3.2**（用了 `--display-ime-policy`），注释与 3.2/3.3 文档一致 |
| 长参数总数（上游） | 5.0.1 共 **109** 个 |
| 你的 GUI 用到的长参数 | **78** 个 |
| 其中在 5.0.1 已失效 | **1** 个：`--server-debugger`（从未存在过，勾选即启动失败） |
| 5.0.1 有、你没有 | **32** 个 |
| 枚举值过期的下拉框 | 2 处（`--video-codec`、`--record-format`） |
| doc 目录结构 | 有变化：`virtual_display.md` → `virtual-display.md`（v4.0 起），另新增若干文档 |

## 一、版本情况

各版本 `cli.c` 中的长参数数量：

| 版本 | v2.7 | v3.0 | v3.1 | v3.2 | v3.3.4 | v4.0 | v4.1 | v5.0 | v5.0.1 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 参数数 | 100 | 108 | 109 | 110 | 110 | 106 | 108 | 109 | 109 |

v4.0 参数数反而变少（106），因为 4.0 做了一轮清理，删掉了被新参数取代的旧选项。

## 二、doc 目录的变化

- v3.3.4 的 `doc/`：`virtual_display.md`（下划线），无 `verify-release.md`。
- v4.0 起：重命名为 **`virtual-display.md`**（连字符），新增 `verify-release.md`。
- 5.0.1 的 `doc/` 共 21 个文件：
  `audio build camera connection control develop device gamepad keyboard linux
  macos mouse otg recording shortcuts tunnels v4l2 verify-release video
  virtual-display window windows`。

你代码注释里引用的 `camera.md / audio.md / video.md / control.md / device.md /
recording.md / window.md / gamepad.md / mouse.md / keyboard.md` **全部仍然存在**，
只是内容都更新过；唯一改过名字的是虚拟显示文档（你没按文件名引用它）。

## 三、参数级差异

### 3.1 幽灵参数（会导致启动失败）

`--server-debugger`（`features/developer_panel.py:77,150-151`）

- v1.25 → v5.0.1 的每一个 `cli.c` 里都不存在（逐 tag 拉取 `app/src/cli.c` 核对）；
- GitHub 代码搜索 `server-debugger` 在默认分支上 **0 命中**；
- 上游唯一相关的是**构建期** meson 选项 `-Dserver_debugger=true`（`doc/develop.md:493`），
  它不是命令行参数。

后果：用户一旦勾选「启用 Server 调试器」，scrcpy 会以
`unrecognized option '--server-debugger'` 退出，整个会话起不来。
**建议：移除该控件，或改成说明「需自行用 meson 编译带调试器的 server」。**

### 3.2 上游有、你没有的 32 个参数

**长期就存在（≥2.7），属于纯粹遗漏：**

| 参数 | 说明 / 建议归属 |
| --- | --- |
| `--list-apps` | ★ 见 3.4，可彻底替代你现在的 `aapt` 方案 |
| `--kill-adb-on-close` | 关闭 scrcpy 时结束 adb server；可与你已有的「关闭 ADB 服务」按钮整合 |
| `--tcpip[=IP]` | 一步完成「开 TCP/IP + 连接」；你现在是手工 `adb tcpip` + `adb connect` |
| `--select-usb` / `--select-tcpip` | 就是 `-d` / `-e` 的长名，补上更清晰 |
| `--port` | 配合已有的 `--tunnel-port` 使用 |
| `--video-codec-options` | 对应你已实现的 `--audio-codec-options` |
| `--render-driver` | 软件渲染兼容（老显卡 / 虚拟机） |
| `--verbosity` | 日志级别，排错时很有用 |
| `--pause-on-exit[=always\|if-error]` | Windows 双击 bat 场景 |
| `--require-audio` | 无音频设备时直接报错，而不是静默降级 |
| `--no-cleanup` | 退出时不在设备上清理 server |
| `--no-downsize-on-error` | 编码器失败时不要自动降分辨率 |
| `--no-mipmaps` | 纹理相关，老旧 GPU 兼容 |
| `--no-terminal-title` | 不改终端标题（GUI 场景无感，可略） |
| `--help` / `--version` | ★ 用 `scrcpy --version` 检测用户装的版本，顺便解决版本适配 |
| `--camera-high-speed` | 高速摄像模式（v2.7 就有，一直没做） |

**3.0 起新增：**

- `--angle=degrees`（自定义角度旋转）
- `--capture-orientation`（采集方向，**会影响录制**）
- `--display-orientation`（客户端显示方向，语义更明确）
- `--record-orientation`

**4.0 起新增：**

- `--flex-display` / `-x`（虚拟显示跟随窗口尺寸，和 `--new-display` 是绝配）
- `--camera-torch`、`--camera-zoom=1.5`
- `--keep-active`（周期性注入用户活动，防息屏）
- `--background-color=#234567`
- `--render-fit=letterbox|unscaled|stretched`
- `--min-size-alignment=8`
- `--no-window-aspect-ratio-lock`

**4.1 / 5.0 起新增：**

- `--ignore-video-encoder-constraints`（4.1）
- `--hwdec=auto|disabled|vaapi|d3d11va|videotoolbox`（5.0，硬件解码模式）


### 3.3 枚举值过期（参数没错，是下拉框少选项）

| 控件 | 你的取值 | 5.0.1 实际支持 |
| --- | --- | --- |
| `--video-codec`（`video_panel.py:37`） | h264 / h265 / av1 | h264 / h265 / av1 / **vp8 / vp9** |
| `--record-format`（`recording_panel.py:34`） | 自动 / mkv / mp4 / opus / flac / wav | mp4 / mkv / **m4a** / **mka** / opus / **aac** / flac / wav |

**已核对、仍然完全正确的枚举：**

- `--keyboard`：sdk / uhid / aoa / disabled ✅
- `--mouse`：sdk / uhid / aoa / disabled ✅
- `--gamepad`：disabled / uhid / aoa ✅
- `--audio-source`：你列的 11 个（output…voice-performance）与 `doc/audio.md` 一字不差 ✅
- `--audio-codec`：opus / aac / flac / raw ✅
- `--shortcut-mod`：lctrl / rctrl / lalt / ralt / lsuper / rsuper ✅
- `--mouse-bind` 绑定字符：`+` `-` `b` `h` `s` `n`（`n` 仍是「展开通知面板」）✅
- `--camera-facing`：front / back / external；与 `--camera-id` 互斥（你的实现已正确处理）✅
- `--new-display` 语法：`1920x1080`、`1920x1080/420`、`=/240` 均未变 ✅
- `--start-app` 的 `+`（先强停）/ `?`（按名称搜索）前缀未变 ✅
- `--no-window` 仍有效（含义：不建窗口，隐含 `--no-video-playback`）✅
- `--display-ime-policy=local` 仍有效 ✅

**语义已变、需要留意的 1 个：**

- `--orientation` 在 5.0.1 仍然接受，但帮助文本已写明
  *"Same as `--display-orientation=value`"* —— 它现在只是旧别名。
  你的「客户端渲染方向」语义没错，但**无法设置采集方向**
  （`--capture-orientation`，这个才会影响录制内容）。

### 3.4 ★ 用 `--list-apps` 替掉现在的 `aapt` 方案

上游从 v3.0 起提供 `scrcpy --list-apps`，由设备端 server 直接枚举
**可启动的应用**（`enabled` 且存在 launch intent），输出带应用名与包名：

```
List of apps:
 - VLC                       org.videolan.vlc
 * Settings                  com.android.settings      ← `*` 表示系统应用
```

（实现见 `server/.../device/Device.java:listApps()` 与 `util/LogUtils.java:buildAppListMessage()`，
名称按 30 列对齐。）

对比你现在的实现（`core/command_runner.py:124-148`）：

| | 现在（aapt） | 改成 `--list-apps` |
| --- | --- | --- |
| 命令次数 | 1 + N 次 `adb shell`（N = 应用数） | **1 次** |
| 耗时 | 分钟级（每条失败要等 3s 超时） | 秒级 |
| 应用名 | 多数设备上 `aapt` 不存在 → 全部退化为包名 | 稳定拿到应用名 |
| 结果准确性 | 含不可启动的应用，且 `-3` 把系统应用也滤掉了 | 只列可启动应用，与 `--start-app` 完全对应 |

注意：`--list-apps` 是一次性模式（列出后即退出，不镜像），输出在 stdout/stderr，
解析上面那种 `- 名称  包名` 的行即可。

## 四、你的 GUI 的版本下限

按「参数最早出现的版本」反推：78 个参数中 70 个 ≤ v2.7 就有，另有 8 个来自 3.x
（`--new-display` / `--no-vd-system-decorations` / `--start-app` / `--video-buffer` /
`--screen-off-timeout` 属 3.0，`--no-vd-destroy-content` 属 3.1，`--display-ime-policy` 属 3.2）。

**结论：你的 GUI 至少需要 scrcpy ≥ 3.2，代码面向的是 3.2/3.3 那一版文档。**
从 3.2 到 5.0.1 中间隔了 3.3、4.0、4.1、5.0 四个版本周期，
上面 32 个缺失参数里有一半是这期间新增的。

## 五、优先建议

1. **删掉 `--server-debugger`**（唯一的「勾了就起不来」的参数）。
2. **应用列表改用 `scrcpy --list-apps`**，把分钟级等待和 aapt 依赖一起干掉。
3. 补 3.x 的方向体系：新增 `--capture-orientation`（影响录制）、保留 `--orientation`
   作为显示方向、再加 `--angle`；录制面板补 `--record-orientation`。
4. 虚拟显示面板补 `--flex-display`；相机面板补 `--camera-zoom` / `--camera-torch` /
   `--camera-high-speed`。
5. 下拉框补值：`--video-codec` 加 vp8/vp9，`--record-format` 加 m4a/mka/aac。
6. 加 `--version` 检测 + `--hwdec` / `--render-fit` / `--background-color` 这类
   4.x/5.x 的体验型选项。

## 附录：复现方式

```bash
# 最新版本
gh api repos/Genymobile/scrcpy/releases/latest --jq .tag_name

# 上游权威参数表在 app/src/cli.c 的 options[] 里
git clone --depth 1 https://github.com/Genymobile/scrcpy /tmp/scrcpy-upstream
grep -oE '\.longopt = "[a-z0-9-]+"' /tmp/scrcpy-upstream/app/src/cli.c | \
  sed 's/.*"\(.*\)"/\1/' | sort -u > /tmp/up.txt

# 本项目实际用到的参数
grep -rhoE -- '--[a-z0-9-]+' --include=*.py core features main.py | \
  sed 's/^--//' | sort -u > /tmp/gui.txt

comm -23 /tmp/gui.txt /tmp/up.txt   # GUI 用但上游没有（= 幽灵参数）
comm -13 /tmp/gui.txt /tmp/up.txt   # 上游有但 GUI 没有（= 缺口）
```

历史版本对照用：
`gh api "repos/Genymobile/scrcpy/contents/app/src/cli.c?ref=v4.0" --jq .content | base64 -d`

