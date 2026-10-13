"""scrcpy 选项注册表：把上游参数表变成可用的配置模型。

三层结构：
    1. `options.generated.json` —— 由 tools/gen_options.py 从上游 cli.c 自动生成
       （参数名、短参数、取值说明、帮助文本、枚举取值）。
    2. `options.meta.json` —— 手工维护的语义叠加层（互斥、依赖、别名、平台限制）。
    3. 本模块 —— 把它们组合成可查询、可校验、可拼装命令行的 Registry。
"""

from __future__ import annotations

import json
import os
from typing import Iterable, Iterator, Sequence

DATA_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data")
GENERATED_PATH = os.path.join(DATA_DIR, "options.generated.json")
META_PATH = os.path.join(DATA_DIR, "options.meta.json")

# 分组规则：先按前缀匹配，再套用显式覆盖表。
# 分组只影响展示（GUI 的页签 / TUI 的分类），不影响命令行拼装。
_GROUP_BY_PREFIX = (
    ("camera-", "camera"),
    ("audio-", "audio"),
    ("video-", "video"),
    ("window-", "window"),
    ("v4l2-", "v4l2"),
    ("tunnel-", "connection"),
    ("no-vd-", "virtual-display"),
    ("new-display", "virtual-display"),
    ("flex-display", "virtual-display"),
)

_GROUP_OVERRIDES = {
    # 输入
    "keyboard": "input", "mouse": "input", "gamepad": "input", "mouse-bind": "input",
    "prefer-text": "input", "raw-key-events": "input", "no-key-repeat": "input",
    "no-mouse-hover": "input", "shortcut-mod": "input",
    # 播放控制
    "no-playback": "playback", "no-video-playback": "playback",
    "no-audio-playback": "playback", "no-audio": "audio", "no-video": "video",
    "no-control": "control",
    # 设备状态
    "stay-awake": "device", "turn-screen-off": "device", "show-touches": "device",
    "power-off-on-close": "device", "no-power-on": "device",
    "screen-off-timeout": "device", "keep-active": "device", "list-apps": "device",
    # 交互控制
    "no-clipboard-autosync": "control", "legacy-paste": "control",
    "push-target": "control", "clipboard-autosync": "control",
    # 视频
    "max-size": "video", "max-fps": "video", "orientation": "video",
    "capture-orientation": "video", "display-orientation": "video", "angle": "video",
    "crop": "video", "display-id": "video", "print-fps": "video",
    "min-size-alignment": "video", "hwdec": "video",
    "video-codec-options": "video", "ignore-video-encoder-constraints": "video",
    # 录制 / 虚拟显示
    "time-limit": "recording", "no-window": "recording",
    "display-ime-policy": "virtual-display",
    # 连接
    "serial": "connection", "otg": "connection", "port": "connection",
    "select-usb": "connection", "select-tcpip": "connection", "tcpip": "connection",
    "kill-adb-on-close": "connection", "force-adb-forward": "connection",
    # 窗口
    "background-color": "window", "render-fit": "window",
    "no-window-aspect-ratio-lock": "window", "always-on-top": "window",
    "fullscreen": "window", "disable-screensaver": "window",
    # 高级
    "no-cleanup": "advanced", "no-downsize-on-error": "advanced",
    "no-mipmaps": "advanced", "verbosity": "advanced", "render-driver": "advanced",
    "require-audio": "advanced", "no-terminal-title": "advanced",
    "pause-on-exit": "advanced", "help": "misc", "version": "misc",
}

# 分组展示顺序（GUI/TUI 用）
GROUP_ORDER = (
    "connection", "device", "video", "audio", "recording", "playback", "control",
    "input", "window", "virtual-display", "v4l2", "camera", "advanced", "misc",
)


class UnknownOptionError(KeyError):
    """使用了注册表里不存在的参数。"""


class OptionSpec:
    """单个 scrcpy 参数的描述。"""

    __slots__ = ("long", "short", "argdesc", "optional_arg", "takes_value",
                 "enum", "help", "group")

    def __init__(self, data: dict, group: str):
        self.long: str = data["long"]
        self.short: str | None = data.get("short")
        self.argdesc: str | None = data.get("argdesc")
        self.optional_arg: bool = bool(data.get("optional_arg"))
        self.takes_value: bool = bool(data.get("takes_value"))
        self.enum: list[str] = list(data.get("enum") or [])
        self.help: str = data.get("help", "")
        self.group: str = group

    @property
    def flag(self) -> str:
        return f"--{self.long}"

    def render(self, value=None) -> str | None:
        """把单个取值渲染成命令行片段；返回 None 表示该项不参与拼装。"""
        if not self.takes_value:
            if value in (None, False, "false", "False", 0, "0"):
                return None
            return self.flag
        if value is None or value == "":
            return None
        if value is True:
            # --new-display / --tcpip / --pause-on-exit 这类「值可选」的参数：
            # 用 True 表示只写参数名不带值
            return self.flag if self.optional_arg else None
        return f"{self.flag}={value}"

    def __repr__(self) -> str:  # pragma: no cover - 仅调试用
        return f"<OptionSpec {self.flag}>"


def _group_for(name: str, overrides: dict) -> str:
    if name in overrides:
        return overrides[name]
    for prefix, group in _GROUP_BY_PREFIX:
        if name.startswith(prefix):
            return group
    return "misc"


class Registry:
    """全部 scrcpy 参数的查询、校验与命令行拼装入口。"""

    def __init__(self, generated: dict, meta: dict, group_overrides: dict | None = None):
        self.source: str = generated.get("source", "")
        self.overrides = dict(_GROUP_OVERRIDES)
        self.overrides.update(group_overrides or {})
        self.meta = meta or {}
        self._options: dict[str, OptionSpec] = {}
        for item in generated.get("options", []):
            spec = OptionSpec(item, _group_for(item["long"], self.overrides))
            self._options[spec.long] = spec

    # ---- 查询 ----
    @property
    def option_count(self) -> int:
        return len(self._options)

    def __len__(self) -> int:
        return len(self._options)

    def __iter__(self) -> Iterator[OptionSpec]:
        return iter(self.sorted_options())

    def __contains__(self, name: str) -> bool:
        return name.lstrip("-") in self._options

    def get(self, name: str) -> OptionSpec:
        key = name.lstrip("-")
        try:
            return self._options[key]
        except KeyError as exc:
            hint = self.meta.get("never_existed", {}).get(key)
            message = f"未知的 scrcpy 参数: --{key}"
            if hint:
                message += f"\n注意：{hint}"
            raise UnknownOptionError(message) from exc

    def sorted_options(self) -> list[OptionSpec]:
        return sorted(self._options.values(), key=lambda spec: (spec.group, spec.long))

    def groups(self) -> dict[str, list[OptionSpec]]:
        result: dict[str, list[OptionSpec]] = {}
        for spec in self.sorted_options():
            result.setdefault(spec.group, []).append(spec)
        ordered = {name: result[name] for name in GROUP_ORDER if name in result}
        for name in sorted(result):
            ordered.setdefault(name, result[name])
        return ordered

    def search(self, text: str) -> list[OptionSpec]:
        needle = text.lower().lstrip("-")
        return [
            spec for spec in self.sorted_options()
            if needle in spec.long or needle in spec.help.lower()
            or any(needle in value for value in spec.enum)
        ]

    # ---- 校验 ----
    def validate(self, values: dict) -> list[str]:
        """返回人类可读的警告列表（不抛异常，便于 UI 逐条展示）。"""
        warnings: list[str] = []
        for name in values:
            if name not in self:
                hint = self.meta.get("never_existed", {}).get(name)
                warnings.append(hint or f"未知参数 --{name}，将被忽略。")
        for left, right in self.meta.get("conflicts", []):
            if values.get(left) not in (None, False, "") and values.get(right) not in (None, False, ""):
                warnings.append(f"--{left} 与 --{right} 互斥，不能同时设置。")
        for target, needed in self.meta.get("requires", {}).items():
            if values.get(target) in (None, False, "") or not needed:
                continue
            for dep in needed:
                if values.get(dep) in (None, False, ""):
                    warnings.append(f"--{target} 需要同时设置 --{dep}。")
        for name, value in values.items():
            if name in self and value is True:
                spec = self.get(name)
                if spec.takes_value and not spec.optional_arg:
                    warnings.append(f"--{name} 需要提供取值，例如 --{name}=<{spec.argdesc}>。")
        for name, value in values.items():
            if name in self and self.get(name).enum and value not in (None, True, False):
                if str(value) not in self.get(name).enum:
                    warnings.append(
                        f"--{name}={value} 不是有效取值，可选：{', '.join(self.get(name).enum)}"
                    )
        return warnings

    # ---- 拼装 ----
    def build_argv(self, values: dict, extra_args: Sequence[str] = (),
                   binary: str = "scrcpy") -> list[str]:
        """把 {参数名: 取值} 拼成完整命令行。排序保证结果可复现（便于测试与预览）。"""
        argv = [binary]
        for name in sorted(values):
            spec = self.get(name)
            rendered = spec.render(values[name])
            if rendered:
                argv.append(rendered)
        argv.extend(extra_args)
        return argv


def _read_json(path: str) -> dict:
    with open(path, encoding="utf-8") as handle:
        return json.load(handle)


def load_registry(generated_path: str = GENERATED_PATH, meta_path: str = META_PATH) -> Registry:
    return Registry(_read_json(generated_path), _read_json(meta_path))


def dedupe_args(args: Sequence[str]) -> list[str]:
    """去掉重复参数，后出现的覆盖先出现的，并保持原有相对顺序。

    多个面板可能提供同一个开关（例如「不播放」在视频面板与录制面板里各有一份），
    拼在一起会出现两个同名参数；scrcpy 只认最后一个，语义含糊。
    """
    rendered: dict[str, str] = {}
    order: list[str] = []
    for item in args:
        key = item.split("=", 1)[0]
        if key in rendered:
            order.remove(key)
        rendered[key] = item
        order.append(key)
    return [rendered[key] for key in order]


def parse_assignments(items: Iterable[str]) -> dict:
    """把 ['video-bit-rate=16M', 'no-audio'] 解析成 {'video-bit-rate': '16M', 'no-audio': True}。"""
    values: dict = {}
    for item in items:
        if "=" in item:
            key, value = item.split("=", 1)
            values[key.strip().lstrip("-")] = value
        else:
            values[item.strip().lstrip("-")] = True
    return values
