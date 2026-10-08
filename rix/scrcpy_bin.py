"""定位 scrcpy / adb 可执行文件，并读取版本号。

为什么单独一个模块：
    * 用户常见情况是「下载了 scrcpy-win64 解压版但没加进 PATH」，
      所以要支持环境变量覆盖 + 常见安装目录探测；
    * GUI 与 CLI 都要用到，且都不该依赖 Qt。
"""

from __future__ import annotations

import os
import re
import shutil
import subprocess
import sys
from typing import Iterator

ENV_OVERRIDES = {"scrcpy": "RIX_SCRCPY", "adb": "RIX_ADB"}

# 常见的「解压即用」目录（很多用户就是从这里启动的）
_WINDOWS_DIRS = (
    os.path.join(os.environ.get("LOCALAPPDATA", ""), "scrcpy"),
    os.path.join(os.environ.get("USERPROFILE", ""), "scrcpy"),
    os.path.join(os.environ.get("USERPROFILE", ""), "Downloads"),
    "C:\\scrcpy",
    "C:\\platform-tools",
)
_POSIX_DIRS = ("/usr/local/bin", "/usr/bin", "/snap/bin", "/opt/homebrew/bin", "/usr/lib/android-sdk/platform-tools")


def _vendor_candidates(name: str) -> Iterator[str]:
    """内置（随程序分发或用户自行安装）的 scrcpy/adb。

    官方发布包同时包含 scrcpy 与 adb，所以两者都从这里找。
    延迟 import 是为了避免与 rix.vendor 形成循环依赖。
    """
    try:
        from rix.vendor import vendor_dirs
    except ImportError:  # pragma: no cover - 极端情况下退化为只用系统安装
        return
    exe = name + ".exe" if os.name == "nt" else name
    for directory in vendor_dirs():
        yield os.path.join(directory, exe)


def _candidates(name: str) -> Iterator[str]:
    env_name = ENV_OVERRIDES.get(name)
    if env_name and os.environ.get(env_name):
        yield os.environ[env_name]

    # 内置核心优先于系统 PATH：这样「随程序分发的版本」一定自洽
    yield from _vendor_candidates(name)

    found = shutil.which(name)
    if found:
        yield found

    exe = name + ".exe" if os.name == "nt" else name
    dirs = _WINDOWS_DIRS if os.name == "nt" else _POSIX_DIRS
    for base in dirs:
        if not base:
            continue
        yield os.path.join(base, exe)
        yield os.path.join(base, name)
        # scrcpy 解压包目录名通常带版本号，例如 scrcpy-win64-v3.1
        if os.path.isdir(base):
            try:
                for entry in sorted(os.listdir(base), reverse=True):
                    if name in entry.lower():
                        yield os.path.join(base, entry, exe)
            except OSError:
                pass


def find_binary(name: str = "scrcpy") -> str | None:
    """按「环境变量 → PATH → 常见目录」的顺序找到可执行文件。"""
    for path in _candidates(name):
        if path and os.path.isfile(path) and os.access(path, os.X_OK):
            return path
    return None


def run_capture(cmd: list[str], timeout: int = 15) -> str:
    """执行命令并返回 stdout+stderr（失败时返回错误信息而不是抛异常）。"""
    try:
        proc = subprocess.run(
            cmd, capture_output=True, text=True, timeout=timeout,
            encoding="utf-8", errors="replace",
            creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0,
        )
    except FileNotFoundError:
        return f"未找到可执行文件: {cmd[0]}"
    except subprocess.TimeoutExpired:
        return f"命令执行超时: {' '.join(cmd)}"
    except OSError as exc:  # pragma: no cover - 平台相关
        return f"执行失败: {exc}"
    return ((proc.stdout or "") + (proc.stderr or "")).strip()


VERSION_RE = re.compile(r"scrcpy\s+(\d+(?:\.\d+)*)")


def scrcpy_version(path: str | None = None) -> str | None:
    """返回形如 '5.0.1' 的版本号；找不到时返回 None。"""
    binary = path or find_binary("scrcpy")
    if not binary:
        return None
    output = run_capture([binary, "--version"])
    match = VERSION_RE.search(output)
    if match:
        return match.group(1)
    return None


def version_tuple(version: str | None) -> tuple[int, ...]:
    if not version:
        return ()
    return tuple(int(part) for part in re.findall(r"\d+", version))


def supports(version: str | None, minimum: str) -> bool:
    """判断已安装版本是否 >= minimum（版本未知时保守返回 False）。"""
    current, required = version_tuple(version), version_tuple(minimum)
    if not current:
        return False
    length = max(len(current), len(required))
    return current + (0,) * (length - len(current)) >= required + (0,) * (length - len(required))


def adb_devices(adb_path: str | None = None) -> list[dict]:
    """解析 `adb devices -l`，返回 [{serial, state, model}]。

    注意：这里保留了 unauthorized / offline 设备（旧版 GUI 把它们过滤掉了，
    导致用户看到「未找到设备」却不知道手机正在等授权）。
    """
    binary = adb_path or find_binary("adb")
    if not binary:
        return []
    output = run_capture([binary, "devices", "-l"])
    devices: list[dict] = []
    for line in output.splitlines()[1:]:
        line = line.strip()
        if not line or "\t" not in line and " " not in line:
            continue
        parts = line.split()
        if len(parts) < 2:
            continue
        info = {"serial": parts[0], "state": parts[1], "model": ""}
        for token in parts[2:]:
            if token.startswith("model:"):
                info["model"] = token.split(":", 1)[1]
        devices.append(info)
    return devices
