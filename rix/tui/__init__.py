"""极简 TUI（Windows/Linux 通用，纯标准库实现）。

为什么不用 Textual：本项目「省内存」是硬指标，而 Textual 会额外拉进
rich 等依赖（常驻 60–90 MB）。这个 TUI 只依赖标准库，可以在服务器、
CI、老机器上跑；命令与 GUI/CLI 共用同一份选项注册表。

交互命令：
    ls [分组]              列出参数
    search 关键字          搜索参数
    set 参数=值            设置参数（只写参数名表示打开开关，如 set no-audio）
    unset 参数             取消设置
    show                   查看当前已设置项
    preview                打印将要执行的命令
    run                    启动 scrcpy
    save 名称 / load 名称  保存 / 载入预设
    help / quit
"""

from __future__ import annotations

import argparse
import sys

from rix import __version__
from rix.profiles import ProfileStore
from rix.registry import UnknownOptionError, load_registry, parse_assignments
from rix.scrcpy_bin import find_binary

HELP = __doc__


class Session:
    """TUI 的状态与命令执行（与终端交互解耦，便于测试）。"""

    def __init__(self):
        self.registry = load_registry()
        self.values: dict = {}
        self.store = ProfileStore()
        self.binary = find_binary("scrcpy") or "scrcpy"

    # ---- 命令 ----
    def execute(self, line: str) -> tuple[bool, str]:
        line = line.strip()
        if not line:
            return True, ""
        parts = line.split(maxsplit=1)
        command, argument = parts[0], (parts[1].strip() if len(parts) > 1 else "")

        if command in ("quit", "exit", "q"):
            return False, "再见。"
        if command in ("help", "?"):
            return True, HELP or ""
        if command in ("ls", "list"):
            specs = self.registry.groups().get(argument) if argument else self.registry.sorted_options()
            if specs is None:
                return True, f"没有分组 '{argument}'，可用：{', '.join(self.registry.groups())}"
            lines = [f"[{spec.group}] --{spec.long}" + (f"=<{spec.argdesc}>" if spec.takes_value else "")
                     for spec in specs]
            return True, "\n".join(lines)
        if command == "search":
            specs = self.registry.search(argument)
            return True, "\n".join(f"--{spec.long}" for spec in specs) or "没有匹配项。"
        if command == "set":
            if not argument:
                return True, "用法：set 参数=值"
            try:
                values = parse_assignments([argument])
                for name in values:
                    self.registry.get(name)
            except UnknownOptionError as exc:
                return True, str(exc)
            warnings = self.registry.validate({**self.values, **values})
            self.values.update(values)
            return True, "\n".join(f"⚠ {w}" for w in warnings) or f"已设置 {argument}"
        if command == "unset":
            name = argument.lstrip("-")
            removed = self.values.pop(name, None)
            return True, f"已取消 --{name}" if removed is not None else f"--{name} 本来就没设置。"
        if command == "show":
            if not self.values:
                return True, "（还没有设置任何参数）"
            return True, "\n".join(f"--{k}={v}" for k, v in sorted(self.values.items()))
        if command in ("preview", "p"):
            argv = self.registry.build_argv(self.values, binary=self.binary)
            return True, " ".join(argv)
        if command == "run":
            argv = self.registry.build_argv(self.values, binary=self.binary)
            return True, "RUN:" + "\0".join(argv)
        if command == "save":
            self.store.update(argument, self.values)
            return True, f"预设 '{argument}' 已保存。"
        if command == "load":
            if argument not in self.store.names():
                return True, f"没有预设 '{argument}'，现有：{', '.join(self.store.names()) or '（无）'}"
            self.values = self.store.get(argument)
            return True, f"已载入预设 '{argument}'。"
        return True, f"未知命令：{command}（输入 help 查看帮助）"


def run(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="rix-scrcpy tui", description="极简 TUI")
    parser.add_argument("--script", help="非交互模式：用 ';' 分隔的命令序列")
    parser.add_argument("--profile", help="启动时载入预设")
    parser.add_argument("--list", action="store_true", help="只打印分组概览后退出")
    args = parser.parse_args(argv)

    session = Session()
    if args.profile:
        session.execute(f"load {args.profile}")
    if args.list:
        for group, specs in session.registry.groups().items():
            print(f"{group:18s} {len(specs):3d} 个参数")
        print(f"\n共 {session.registry.option_count} 个参数（RIX Scrcpy {__version__}）")
        return 0

    if args.script:
        for line in args.script.split(";"):
            keep_going, output = session.execute(line)
            if output:
                print(output)
            if not keep_going:
                break
        return 0

    print(f"RIX Scrcpy TUI {__version__} —— 输入 help 查看命令，quit 退出。")
    while True:
        try:
            line = input("rix> ")
        except (EOFError, KeyboardInterrupt):
            print()
            break
        keep_going, output = session.execute(line)
        if output:
            if output.startswith("RUN:"):
                import subprocess

                argv_run = output[4:].split("\0")
                print("执行: " + " ".join(argv_run))
                try:
                    subprocess.call(argv_run)
                except FileNotFoundError:
                    print("找不到 scrcpy，请检查安装或设置 RIX_SCRCPY。")
            else:
                print(output)
        if not keep_going:
            break
    return 0


if __name__ == "__main__":
    sys.exit(run())
