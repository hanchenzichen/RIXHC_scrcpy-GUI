#!/usr/bin/env python3
"""一键重命名项目（仓库名 / 可执行文件名 / 包名 / 显示名）。

为什么需要脚本：
    项目名字散落在 20 多个文件里（pyproject、两个 PyInstaller spec、README、
    CI 工作流、main.py 的窗口标题、文档……），手工改极易漏。
    这个脚本把「名字映射」集中在一处，一次改完，并且支持 --dry-run 预览。

用法：
    python tools/rename_project.py --dry-run                    # 预览（推荐先看）
    python tools/rename_project.py                              # 用推荐名 rix-scrcpy
    python tools/rename_project.py --repo scrcpy-deck --dist scrcpy-deck \
        --exe ScrcpyDeck --display "ScrcpyDeck"                 # 换成别的名字
    python tools/rename_project.py --rename-repo                # 顺带重命名 GitHub 仓库（需 admin 权限）
"""

from __future__ import annotations

import argparse
import os
import re
import shutil
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SKIP_DIRS = {".git", "vendor", "dist", "build", "__pycache__", ".github", ".cline-home", ".idea"}
TEXT_SUFFIXES = (".py", ".md", ".toml", ".yml", ".yaml", ".spec", ".txt", ".cfg", ".ini")
# 本脚本自身不能参与替换：否则 OLD 映射表会被改掉，以后就没法再改名了
SKIP_FILES = {os.path.join(ROOT, "tools", "rename_project.py")}

# 默认目标：仓库名与分发包名统一成 rix-scrcpy（PyPI 上可用，且保留 scrcpy 关键字便于搜索）
DEFAULTS = {
    "repo": "rix-scrcpy",           # GitHub 仓库名
    "dist": "rix-scrcpy",           # PyPI 分发包名 / CLI 命令名
    "display": "RIX Scrcpy",        # 界面显示名
    "exe": "RIX-Scrcpy",            # GUI 可执行文件/目录名
    "gui_spec": "RIX-Scrcpy",       # GUI 的 PyInstaller spec 文件名（不含扩展名）
    "cli_spec": "rix-scrcpy-cli",   # CLI 的 PyInstaller spec 文件名（不含扩展名）
}

# 当前使用的旧名字（按长度从长到短替换，避免前缀互相干扰）
OLD = {
    "repo": "RIXHC_scrcpy-GUI",
    "dist": "rix-scrcpy",
    "display": "RIX Scrcpy",
    "exe": "RIX_Scrcpy_GUI",
    "gui_spec": "RIX_Scrcpy",
    "cli_spec": "RIX_Scrcpy_CLI",
}


def iter_text_files():
    for base, dirs, files in os.walk(ROOT):
        dirs[:] = [d for d in dirs if d not in SKIP_DIRS]
        for name in files:
            path = os.path.join(base, name)
            if name.endswith(TEXT_SUFFIXES) and path not in SKIP_FILES:
                yield path


def build_mappings(target: dict) -> list[tuple[str, str]]:
    """生成 (旧, 新) 替换表；键顺序保证长名字先被替换。"""
    order = ["repo", "exe", "cli_spec", "gui_spec", "display", "dist"]
    pairs = [(OLD[key], target[key]) for key in order]
    return [(old, new) for old, new in pairs if old != new]


def rewrite_file(path: str, mappings: list[tuple[str, str]], dry_run: bool) -> int:
    try:
        with open(path, encoding="utf-8") as handle:
            original = handle.read()
    except (UnicodeDecodeError, OSError):
        return 0
    updated = original
    for old, new in mappings:
        updated = updated.replace(old, new)
    if updated == original:
        return 0
    changed = sum(1 for old, new in mappings if old in original)
    if not dry_run:
        with open(path, "w", encoding="utf-8") as handle:
            handle.write(updated)
    return changed


def rename_files(target: dict, dry_run: bool) -> list[tuple[str, str]]:
    """重命名两个 PyInstaller spec 文件。"""
    renames = [
        (os.path.join(ROOT, f"{OLD['gui_spec']}.spec"), os.path.join(ROOT, f"{target['gui_spec']}.spec")),
        (os.path.join(ROOT, f"{OLD['cli_spec']}.spec"), os.path.join(ROOT, f"{target['cli_spec']}.spec")),
    ]
    done = []
    for src, dst in renames:
        if os.path.isfile(src) and src != dst:
            if not dry_run:
                shutil.move(src, dst)
            done.append((os.path.relpath(src, ROOT), os.path.relpath(dst, ROOT)))
    return done


def update_pyproject(target: dict, dry_run: bool) -> list[str]:
    """pyproject.toml 的 name 与 console_scripts 需要精确替换，单独处理。"""
    path = os.path.join(ROOT, "pyproject.toml")
    if not os.path.isfile(path):
        return []
    with open(path, encoding="utf-8") as handle:
        text = handle.read()
    notes = []
    updated = re.sub(r'^name = "[^"]+"', f'name = "{target["dist"]}"', text, count=1, flags=re.M)
    if updated != text:
        notes.append(f'[project] name -> {target["dist"]}')
    updated = re.sub(r'^rix-scrcpy = "', f'{target["dist"]} = "', updated, count=1, flags=re.M)
    updated = re.sub(r'^rix-scrcpy-gui = "', f'{target["dist"]}-gui = "', updated, count=1, flags=re.M)
    if not dry_run and updated != text:
        with open(path, "w", encoding="utf-8") as handle:
            handle.write(updated)
    return notes


def rename_github_repo(owner: str, old: str, new: str) -> int:
    print(f"$ gh api -X PATCH repos/{owner}/{old} -f name={new}")
    code = subprocess.call(["gh", "api", "-X", "PATCH", f"repos/{owner}/{old}", "-f", f"name={new}"])
    if code == 0:
        print("GitHub 仓库已重命名。旧地址会自动跳转到新地址，"
              "但 Release 附件的直链会变化，外部若引用过需要更新。")
    else:
        print("重命名失败：通常是当前凭证没有 admin 权限，请用仓库所有者账号执行。", file=sys.stderr)
    return code


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="重命名项目")
    parser.add_argument("--repo", default=DEFAULTS["repo"], help="GitHub 仓库名")
    parser.add_argument("--dist", default=DEFAULTS["dist"], help="PyPI 分发包名 / CLI 命令名")
    parser.add_argument("--display", default=DEFAULTS["display"], help="界面显示名")
    parser.add_argument("--exe", default=DEFAULTS["exe"], help="GUI 可执行文件/目录名")
    parser.add_argument("--gui-spec", default=None, help="GUI spec 文件名（默认跟随 --exe）")
    parser.add_argument("--cli-spec", default=DEFAULTS["cli_spec"], help="CLI spec 文件名")
    parser.add_argument("--dry-run", action="store_true", help="只预览不修改")
    parser.add_argument("--rename-repo", action="store_true", help="同时重命名 GitHub 仓库（需 admin）")
    parser.add_argument("--owner", default="hanchenzichen", help="GitHub 用户名")
    args = parser.parse_args(argv)

    target = {
        "repo": args.repo,
        "dist": args.dist,
        "display": args.display,
        "exe": args.exe,
        "gui_spec": args.gui_spec or args.exe,
        "cli_spec": args.cli_spec,
    }
    mappings = build_mappings(target)

    print("=== 名字映射 ===")
    for key in ("repo", "dist", "display", "exe", "gui_spec", "cli_spec"):
        marker = "" if OLD[key] == target[key] else "   <- 变化"
        print(f"  {key:9s} {OLD[key]:22s} -> {target[key]}{marker}")

    if not mappings:
        print("\n没有需要替换的内容（目标名与当前一致）。")
    else:
        print("\n=== 受影响的文件 ===")
        touched = 0
        for path in iter_text_files():
            count = rewrite_file(path, mappings, args.dry_run)
            if count:
                touched += 1
                print(f"  {os.path.relpath(path, ROOT)}  ({count} 类替换)")
        print(f"共 {touched} 个文件。")

        print("\n=== 文件重命名 ===")
        for src, dst in rename_files(target, args.dry_run):
            print(f"  {src} -> {dst}")

        for note in update_pyproject(target, args.dry_run):
            print(f"  pyproject.toml: {note}")

    if args.dry_run:
        print("\n（这是预览模式，未做任何修改。去掉 --dry-run 即可应用。）")
        return 0

    if args.rename_repo:
        rename_github_repo(args.owner, OLD["repo"], target["repo"])
    else:
        print("\n提示：GitHub 仓库名需要仓库 admin 权限，可执行：\n"
              f"  python tools/rename_project.py --rename-repo --repo {target['repo']}")

    print("\n接下来建议：\n"
          "  1. python -m unittest discover -s tests -t .   # 确认测试仍全绿\n"
          "  2. python tools/install_workflows.py           # 工作流里的产物名也需要同步\n"
          "  3. git add -A && git commit -m \"chore: rename project\"")
    return 0


if __name__ == "__main__":
    sys.exit(main())
