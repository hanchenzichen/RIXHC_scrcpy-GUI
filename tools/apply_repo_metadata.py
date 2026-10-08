#!/usr/bin/env python3
"""一键更新 GitHub 仓库的「说明与信息」（需要仓库管理员权限）。

为什么需要单独一步：仓库的 description / topics / homepage 属于仓库设置，
必须用有 admin 权限的凭证调用 API。自动化凭证通常没有该权限
（会返回 403 Resource not accessible by integration）。

用法：
    gh auth status                 # 确认已登录且有权限
    python tools/apply_repo_metadata.py            # 应用
    python tools/apply_repo_metadata.py --dry-run  # 只打印将要执行的命令
"""

from __future__ import annotations

import argparse
import shutil
import subprocess
import sys

REPO = "hanchenzichen/RIXHC_scrcpy-GUI"

DESCRIPTION = (
    "Scrcpy 控制中心：GUI + TUI + CLI 三端共用一份核心；内置官方 scrcpy 核心"
    "（SHA256 校验）；109/109 参数全覆盖并自动跟随上游版本"
)
HOMEPAGE = f"https://github.com/{REPO}#readme"
TOPICS = [
    "scrcpy", "android", "adb", "screen-mirroring", "gui", "tui", "cli",
    "pyside6", "qt", "python", "windows", "linux", "github-actions",
]


def run(cmd: list[str], dry_run: bool) -> int:
    print("$ " + " ".join(cmd))
    if dry_run:
        return 0
    return subprocess.call(cmd)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="更新仓库说明与信息")
    parser.add_argument("--dry-run", action="store_true", help="只打印命令，不执行")
    parser.add_argument("--repo", default=REPO)
    args = parser.parse_args(argv)

    if not shutil.which("gh"):
        print("需要 GitHub CLI（gh）。安装后运行 `gh auth login`。", file=sys.stderr)
        return 1

    code = run([
        "gh", "api", "-X", "PATCH", f"repos/{args.repo}",
        "-f", f"description={DESCRIPTION}",
        "-f", f"homepage={HOMEPAGE}",
        "--jq", "{description, homepage}",
    ], args.dry_run)
    if code:
        print("\n提示：若返回 403，说明当前凭证没有仓库 admin 权限，请换用仓库所有者的账号。",
              file=sys.stderr)
        return code

    topic_args: list[str] = ["gh", "api", "-X", "PUT", f"repos/{args.repo}/topics"]
    for topic in TOPICS:
        topic_args += ["-f", f"names[]={topic}"]
    topic_args += ["--jq", ".names"]
    return run(topic_args, args.dry_run)


if __name__ == "__main__":
    sys.exit(main())
