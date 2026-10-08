"""获取设备上「可启动应用」的列表。

为什么不用 adb + aapt：
    早期实现是 `adb shell "aapt d badging <apk>"` 逐个应用查名字。问题是
    绝大多数正式版 Android 根本没有 aapt，于是每条都失败（还要等 3 秒超时），
    最终退化成只显示包名，100 个应用要等分钟级。

    scrcpy 从 v3.0 起自带 `--list-apps`：由设备端 server 直接枚举可启动应用，
    一次调用就能拿到「应用名 + 包名」（`*` 表示系统应用），秒级完成。
"""

from __future__ import annotations

import re
import sys

from rix.scrcpy_bin import find_binary, run_capture

# 形如：  - VLC                       org.videolan.vlc
#         * Settings                  com.android.settings
_ENTRY_RE = re.compile(r"^\s*([-*])\s+(.*)$")
_PACKAGE_RE = re.compile(r"^[A-Za-z0-9_]+(\.[A-Za-z0-9_]+)+$")


def parse_app_list(text: str) -> list[dict]:
    """解析 `scrcpy --list-apps` 的输出。

    名称按 30 列对齐；名称过长时，包名会换行并缩进显示，
    所以还要处理「续行」的情况。
    """
    apps: list[dict] = []
    current: dict | None = None
    for raw in text.splitlines():
        line = raw.rstrip()
        if not line.strip():
            continue
        stripped = line.strip()
        if stripped.lower().startswith("list of apps") or stripped.startswith("Processing Android apps"):
            continue

        entry = _ENTRY_RE.match(line)
        if entry:
            marker, body = entry.group(1), entry.group(2).strip()
            parts = body.rsplit(None, 1)
            name, package = (parts[0].strip(), parts[1]) if len(parts) == 2 else (body, "")
            if package and not _PACKAGE_RE.match(package):
                name, package = body, ""
            if not package:
                # 包名在下一行（名称太长被换行）
                current = {"name": name, "package": "", "system": marker == "*"}
                apps.append(current)
                continue
            current = {"name": name or package, "package": package, "system": marker == "*"}
            apps.append(current)
            continue

        # 续行：只有包名
        if current is not None and not current["package"] and _PACKAGE_RE.match(stripped):
            current["package"] = stripped
            if not current["name"]:
                current["name"] = stripped

    return [app for app in apps if app["package"]]


def list_apps(binary: str | None = None, serial: str | None = None, timeout: int = 120) -> list[dict]:
    """调用 `scrcpy --list-apps` 并解析结果。"""
    executable = binary or find_binary("scrcpy")
    if not executable:
        raise RuntimeError("未找到 scrcpy（可用 `rix-scrcpy vendor install` 安装内置核心）")
    cmd = [executable, "--list-apps"]
    if serial:
        cmd += ["--serial", serial]
    output = run_capture(cmd, timeout=timeout)
    apps = parse_app_list(output)
    if not apps:
        raise RuntimeError(f"没有解析到应用列表，原始输出：\n{output[:2000]}")
    return apps


def main(argv: list[str] | None = None) -> int:
    import argparse
    import json

    parser = argparse.ArgumentParser(prog="python -m rix.apps", description="列出设备上可启动的应用")
    parser.add_argument("--binary", help="scrcpy 可执行文件路径")
    parser.add_argument("--serial", help="设备序列号")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)

    try:
        apps = list_apps(args.binary, args.serial)
    except Exception as exc:  # noqa: BLE001
        print(f"获取失败: {exc}", file=sys.stderr)
        return 1
    if args.json:
        print(json.dumps(apps, ensure_ascii=False, indent=2))
        return 0
    for app in apps:
        flag = "系统" if app["system"] else "用户"
        print(f"[{flag}] {app['name']}  ({app['package']})")
    print(f"\n共 {len(apps)} 个可启动应用。")
    return 0


if __name__ == "__main__":
    sys.exit(main())
