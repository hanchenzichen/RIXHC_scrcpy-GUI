#!/usr/bin/env python3
"""版本一致性校验。

单一事实来源是 `rix/__init__.py` 里的 `__version__`：
    * 打包时用它给产物命名/展示；
    * 发布时要求 git tag（v1.1.0）与它完全一致，避免「tag 打了但代码里还是旧版本」
      这种最容易让用户困惑的问题。
"""

from __future__ import annotations

import argparse
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
INIT_PATH = os.path.join(ROOT, "rix", "__init__.py")


def code_version() -> str:
    with open(INIT_PATH, encoding="utf-8") as handle:
        match = re.search(r'^__version__\s*=\s*"([^"]+)"', handle.read(), re.M)
    if not match:
        raise SystemExit(f"无法从 {INIT_PATH} 读取 __version__")
    return match.group(1)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="校验版本号")
    parser.add_argument("--tag", help="git tag（如 v1.1.0）")
    args = parser.parse_args(argv)

    version = code_version()
    print(f"代码中的版本号: {version}")

    if args.tag:
        tag_version = args.tag.lstrip("v")
        if tag_version != version:
            print(
                f"错误：tag '{args.tag}' 与代码里的版本 '{version}' 不一致。\n"
                f"请把 rix/__init__.py 的 __version__ 改成 {tag_version} 后重新打 tag。",
                file=sys.stderr,
            )
            return 1
        print(f"tag {args.tag} 与代码版本一致 ✓")
    return 0


if __name__ == "__main__":
    sys.exit(main())
