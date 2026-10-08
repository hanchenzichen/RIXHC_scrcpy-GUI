#!/usr/bin/env python3
"""把 `ci/workflows/*.yml` 安装到 `.github/workflows/`。

为什么需要这一步：
    某些自动化凭证（GitHub App / 未授予 `workflows` 权限的 token）无法推送
    `.github/workflows/` 下的文件，会被 GitHub 以
    「refusing to allow ... without `workflows` permission」拒绝。
    因此工作流定义先放在 `ci/workflows/`，由本脚本（或你手动复制）安装到位。

用法：
    python tools/install_workflows.py            # 安装
    python tools/install_workflows.py --check    # 只检查是否已安装且内容一致
"""

from __future__ import annotations

import argparse
import filecmp
import os
import shutil
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC_DIR = os.path.join(ROOT, "ci", "workflows")
DST_DIR = os.path.join(ROOT, ".github", "workflows")


def workflow_files() -> list[str]:
    if not os.path.isdir(SRC_DIR):
        return []
    return sorted(name for name in os.listdir(SRC_DIR) if name.endswith((".yml", ".yaml")))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="安装 GitHub Actions 工作流")
    parser.add_argument("--check", action="store_true", help="只检查，不写入")
    args = parser.parse_args(argv)

    files = workflow_files()
    if not files:
        print(f"在 {SRC_DIR} 下没有找到任何工作流文件。")
        return 1

    if args.check:
        missing = [name for name in files
                   if not os.path.exists(os.path.join(DST_DIR, name))]
        outdated = [name for name in files
                    if name not in missing
                    and not filecmp.cmp(os.path.join(SRC_DIR, name),
                                        os.path.join(DST_DIR, name), shallow=False)]
        for name in missing:
            print(f"未安装: {name}")
        for name in outdated:
            print(f"内容不一致: {name}")
        if missing or outdated:
            print("\n请运行：python tools/install_workflows.py")
            return 1
        print(f"已安装且一致：{', '.join(files)}")
        return 0

    os.makedirs(DST_DIR, exist_ok=True)
    for name in files:
        shutil.copyfile(os.path.join(SRC_DIR, name), os.path.join(DST_DIR, name))
        print(f"已安装 .github/workflows/{name}")
    print("\n接下来：\n"
          "  1. git add .github/workflows && git commit -m 'ci: enable workflows'\n"
          "  2. git push —— 需要你的账号（或授予 workflows 权限的 token）才能推送\n"
          "  3. 到仓库的 Actions 页面确认工作流已出现")
    return 0


if __name__ == "__main__":
    sys.exit(main())
