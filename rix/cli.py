"""RIX Scrcpy 命令行入口。

设计目标：
    * 能表达注册表里的**全部** 109 个参数（`--set 参数=值`），
      并保留 `--extra-args` 透传，所以即使上游新增了参数、注册表还没更新，
      用户也不会被卡住；
    * 完全不依赖 Qt，能在服务器/CI/无图形环境的 Windows 与 Linux 上运行。

用法示例：
    rix-scrcpy options --search codec
    rix-scrcpy run --set video-bit-rate=16M --set capture-orientation=90 --print
    rix-scrcpy profiles save gaming --set max-fps=60 --set no-audio
    rix-scrcpy run --profile gaming
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys

from rix import __version__
from rix.profiles import InvalidProfileName, ProfileStore
from rix.registry import UnknownOptionError, load_registry, parse_assignments
from rix import vendor
from rix.scrcpy_bin import find_binary, run_capture, scrcpy_version, supports


def _print_command(argv: list[str]) -> None:
    if sys.platform == "win32":
        print(subprocess.list2cmdline(argv))
    else:
        import shlex

        print(shlex.join(argv))


def cmd_version(args) -> int:
    print(f"RIX Scrcpy {__version__}")
    scrcpy = args.binary or find_binary("scrcpy")
    if not scrcpy:
        print("scrcpy: 未找到（请安装 scrcpy 或设置环境变量 RIX_SCRCPY 指向可执行文件）")
    else:
        print(f"scrcpy: {scrcpy} (版本 {scrcpy_version(scrcpy) or '未知'})")
    adb = find_binary("adb")
    print(f"adb:    {adb or '未找到'}")
    info = vendor.status()
    if info["bundled"]:
        print(f"内置核心: {info['version'] or '已就位'}（{info['bundled']}）")
    elif info["user"]:
        print(f"用户安装: {info['version'] or '已就位'}（{info['user']}）")
    else:
        print("内置核心: 未安装（可用 `rix-scrcpy vendor install` 一键获取官方 scrcpy）")
    registry = load_registry()
    print(f"选项注册表: {registry.option_count} 个参数")
    return 0


def cmd_options(args) -> int:
    registry = load_registry()
    specs = registry.search(args.search) if args.search else registry.sorted_options()
    if args.group:
        specs = [spec for spec in specs if spec.group == args.group]
    if args.json:
        print(json.dumps(
            [
                {
                    "long": spec.long, "short": spec.short, "group": spec.group,
                    "argdesc": spec.argdesc, "enum": spec.enum, "help": spec.help,
                }
                for spec in specs
            ],
            ensure_ascii=False, indent=2,
        ))
        return 0
    current_group = None
    for spec in specs:
        if spec.group != current_group:
            current_group = spec.group
            print(f"\n[{current_group}]")
        short = f"-{spec.short}, " if spec.short else ""
        value = f"=<{spec.argdesc}>" if spec.takes_value else ""
        print(f"  {short}--{spec.long}{value}")
        if spec.enum:
            print(f"      取值: {', '.join(spec.enum)}")
        if args.verbose and spec.help:
            for line in spec.help.splitlines():
                print(f"      {line}")
    print(f"\n共 {len(specs)} 个参数。")
    return 0


def _collect_values(args) -> dict:
    values: dict = {}
    store = ProfileStore()
    if getattr(args, "profile", None):
        if args.profile not in store.names():
            raise SystemExit(f"找不到预设 '{args.profile}'，可用预设：{', '.join(store.names()) or '（无）'}")
        values.update(store.get(args.profile))
    values.update(parse_assignments(getattr(args, "set", None) or []))
    return values


def cmd_check(args) -> int:
    registry = load_registry()
    values = _collect_values(args)
    warnings = registry.validate(values)
    # 未知参数已在 warnings 里报告，这里不再拼装（否则会抛异常、丢掉其他提示）
    if not [name for name in values if name not in registry]:
        _print_command(registry.build_argv(values, args.extra_args or []))
    if warnings:
        print("\n发现以下问题：")
        for warning in warnings:
            print(f"  ⚠ {warning}")
        return 1
    print("\n校验通过。")
    return 0


def cmd_run(args) -> int:
    registry = load_registry()
    values = _collect_values(args)
    binary = args.binary or find_binary("scrcpy") or "scrcpy"
    argv = registry.build_argv(values, args.extra_args or [], binary=binary)
    for warning in registry.validate(values):
        print(f"⚠ {warning}", file=sys.stderr)
    if args.print_only:
        _print_command(argv)
        return 0
    print("执行: " + " ".join(argv))
    try:
        return subprocess.call(argv)
    except FileNotFoundError:
        print("错误：找不到 scrcpy，请先安装，或用 --binary 指定路径。", file=sys.stderr)
        return 127


def cmd_devices(args) -> int:
    adb = args.binary or find_binary("adb")
    if not adb:
        print("未找到 adb。", file=sys.stderr)
        return 127
    print(run_capture([adb, "devices", "-l"]))
    return 0


def cmd_profiles(args) -> int:
    store = ProfileStore()
    if args.action == "list":
        names = store.names()
        if not names:
            print("还没有任何预设。用 `rix-scrcpy profiles save <名称> --set ...` 创建。")
        for name in names:
            values = store.get(name)
            rendered = " ".join(f"--{k}={v}" for k, v in sorted(values.items()))
            print(f"{name}  ({len(values)} 项)  {rendered}")
        return 0
    if args.action == "show":
        print(json.dumps(store.get(args.name), ensure_ascii=False, indent=2))
        return 0
    if args.action == "save":
        try:
            store.update(args.name, parse_assignments(args.set or []))
        except InvalidProfileName as exc:
            print(exc, file=sys.stderr)
            return 1
        print(f"预设 '{args.name}' 已保存（{len(store.get(args.name))} 项）。")
        return 0
    if args.action == "delete":
        print(f"预设 '{args.name}' {'已删除' if store.delete(args.name) else '不存在'}。")
        return 0
    if args.action == "export":
        store.export(args.path)
        print(f"已导出到 {args.path}")
        return 0
    if args.action == "import":
        print(f"已从 {args.path} 导入 {store.import_(args.path)} 个预设。")
        return 0
    return 1


def cmd_apps(args) -> int:
    """列出设备上可启动的应用（用 scrcpy --list-apps，比 aapt 方案快几个数量级）。"""
    from rix.apps import list_apps

    try:
        apps = list_apps(binary=args.binary, serial=getattr(args, "serial", None))
    except Exception as exc:  # noqa: BLE001
        print(f"获取失败: {exc}", file=sys.stderr)
        return 1
    if args.json:
        print(json.dumps(apps, ensure_ascii=False, indent=2))
        return 0
    for app in apps:
        flag = "系统" if app["system"] else "用户"
        print(f"[{flag}] {app['name']}  ({app['package']})")
    print("共 %d 个可启动应用。" % len(apps))
    return 0


def cmd_vendor(args) -> int:
    """管理内置 scrcpy 核心（下载官方发布包并校验 SHA256）。"""
    if args.action == "status":
        info = vendor.status()
        print(f"平台:      {info['platform']}")
        print(f"内置目录:  {info['bundled'] or '（无）'}")
        print(f"用户目录:  {info['user'] or '（无）'}")
        print(f"当前版本:  {info['version'] or '未安装'}")
        print(f"可执行文件: {info['path'] or '（无）'}")
        return 0
    if args.action == "path":
        print(vendor.bundled_vendor_dir() or vendor.user_vendor_dir())
        return 0
    try:
        target = vendor.install(version=args.version, target_dir=args.target,
                                plat=args.platform, verify=not args.no_verify)
    except Exception as exc:  # noqa: BLE001 - 网络/校验失败都要给用户看得懂的提示
        print(f"安装失败: {exc}", file=sys.stderr)
        return 1
    print(f"完成：{target}")
    print("提示：官方包同时包含 adb，无需再单独安装。")
    return 0


def cmd_doctor(args) -> int:
    """体检：把本项目踩过的坑一次性查出来。"""
    problems = 0
    registry = load_registry()
    version = scrcpy_version(args.binary or find_binary("scrcpy"))

    print("== 环境检查 ==")
    info = vendor.status()
    if info["bundled"]:
        print(f"v 内置 scrcpy {info['version'] or ''}（随程序分发）")
    elif info["user"]:
        print(f"v 用户目录 scrcpy {info['version'] or ''}（{info['user']}）")
    else:
        print("i 未安装内置核心，可运行 `rix-scrcpy vendor install`")
    if not find_binary("scrcpy"):
        print("x 未找到 scrcpy（设置 RIX_SCRCPY 或加入 PATH）")
        problems += 1
    else:
        print(f"v scrcpy {version or '(版本未知)'}")
    if not find_binary("adb"):
        print("x 未找到 adb")
        problems += 1
    else:
        print("v adb 可用")
    if version and not supports(version, "3.2"):
        print(f"x 版本过低：注册表按新版本参数生成，需要 scrcpy >= 3.2（当前 {version}）")
        problems += 1
    print(f"v 选项注册表: {registry.option_count} 个参数")

    print("\n== 参数健康度 ==")
    for name, note in registry.meta.get("never_existed", {}).items():
        print(f"x --{name}: {note}")
        problems += 1
    if problems == 0:
        print("一切正常。")
    return 1 if problems else 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="rix-scrcpy", description="RIX Scrcpy 命令行工具")
    parser.add_argument("--version", action="version", version=f"RIX Scrcpy {__version__}")
    parser.add_argument("--binary", help="scrcpy 可执行文件的路径")
    sub = parser.add_subparsers(dest="command", required=True)

    p = sub.add_parser("version", help="显示各组件版本")
    p.add_argument("--binary", help="scrcpy 可执行文件路径")
    p.set_defaults(func=cmd_version)

    p = sub.add_parser("options", help="列出全部 scrcpy 参数")
    p.add_argument("--group", help="只看某个分组")
    p.add_argument("--search", help="按关键字搜索")
    p.add_argument("--json", action="store_true")
    p.add_argument("-v", "--verbose", action="store_true", help="显示帮助文本")
    p.set_defaults(func=cmd_options)

    for name, func, help_text in (
        ("check", cmd_check, "校验一组参数并打印将要执行的命令"),
        ("run", cmd_run, "拼装参数并启动 scrcpy"),
    ):
        p = sub.add_parser(name, help=help_text)
        p.add_argument("--profile", help="使用已保存的预设")
        p.add_argument("--set", action="append", metavar="KEY=VALUE",
                       help="设置参数，可重复，例如 --set video-bit-rate=16M")
        p.add_argument("--extra-args", nargs=argparse.REMAINDER,
                       help="透传给 scrcpy 的原始参数（放在最后）")
        p.add_argument("--binary", help="scrcpy 可执行文件路径")
        if name == "run":
            p.add_argument("--print", dest="print_only", action="store_true",
                           help="只打印命令不执行")
        p.set_defaults(func=func)

    p = sub.add_parser("devices", help="列出 adb 设备（含 unauthorized/offline 状态）")
    p.add_argument("--binary", help="adb 可执行文件路径")
    p.set_defaults(func=cmd_devices)

    p = sub.add_parser("profiles", help="管理配置预设")
    p.add_argument("action", choices=["list", "show", "save", "delete", "export", "import"])
    p.add_argument("name", nargs="?", default="")
    p.add_argument("--set", action="append", metavar="KEY=VALUE")
    p.add_argument("--path", default="profiles.json")
    p.set_defaults(func=cmd_profiles)

    p = sub.add_parser("apps", help="列出设备上可启动的应用")
    p.add_argument("--serial", help="设备序列号")
    p.add_argument("--json", action="store_true")
    p.add_argument("--binary", help="scrcpy 可执行文件路径")
    p.set_defaults(func=cmd_apps)

    p = sub.add_parser("vendor", help="管理内置 scrcpy 核心")
    p.add_argument("action", choices=["status", "install", "path"])
    p.add_argument("--version", help="scrcpy 版本（默认取上游最新）")
    p.add_argument("--target", help="安装目录")
    p.add_argument("--platform", help="平台标识，如 win64 / linux-x86_64")
    p.add_argument("--no-verify", action="store_true", help="跳过 SHA256 校验（不建议）")
    p.set_defaults(func=cmd_vendor)

    p = sub.add_parser("doctor", help="检查环境与参数健康度")
    p.add_argument("--binary", help="scrcpy 可执行文件路径")
    p.set_defaults(func=cmd_doctor)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        return args.func(args)
    except UnknownOptionError as exc:
        print(exc, file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
