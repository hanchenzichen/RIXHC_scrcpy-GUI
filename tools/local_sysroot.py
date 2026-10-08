#!/usr/bin/env python3
"""在没有 root 的环境里，把 Qt 需要的系统库（libGL/X11/freetype…）解到本地目录。

背景：这个沙箱没有 root，`apt-get install` 用不了，PySide6 一 import 就报
`libGL.so.1: cannot open shared object file`。但 Debian 的 Packages 索引和 .deb
都可以直接下载，用 dpkg-deb 解包到临时目录再设 LD_LIBRARY_PATH 即可。

用法：
    python3 tools/local_sysroot.py --wanted libgl1 libegl1 libx11-6 ...
    python3 tools/local_sysroot.py --from-ldd <某个.so或可执行文件>
"""

from __future__ import annotations

import argparse
import os
import re
import subprocess
import sys
import urllib.request

PACKAGES_INDEX = "https://deb.debian.org/debian/dists/bookworm/main/binary-amd64/Packages.xz"
MIRROR = "https://deb.debian.org/debian/"
CORE_SKIP = {"libc6", "libgcc-s1", "libstdc++6", "libcrypt1", "base-files"}


def _fetch(url: str, dest: str) -> None:
    request = urllib.request.Request(url, headers={"User-Agent": "local-sysroot"})
    with urllib.request.urlopen(request, timeout=300) as resp, open(dest, "wb") as handle:
        handle.write(resp.read())


def load_index(cache_dir: str) -> dict[str, dict]:
    os.makedirs(cache_dir, exist_ok=True)
    index_path = os.path.join(cache_dir, "Packages")
    if not os.path.exists(index_path):
        compressed = index_path + ".xz"
        if not os.path.exists(compressed):
            print("下载 Debian 包索引 …")
            _fetch(PACKAGES_INDEX, compressed)
        with open(index_path, "wb") as out:
            subprocess.run(["xz", "-d", "-c", compressed], stdout=out, check=True)

    packages: dict[str, dict] = {}
    current: dict[str, str] = {}
    with open(index_path, encoding="utf-8", errors="replace") as handle:
        for line in handle:
            if not line.strip():
                if "Package" in current:
                    packages[current["Package"]] = current
                current = {}
                continue
            if line.startswith((" ", "\t")):
                continue
            if ": " in line:
                key, value = line.split(": ", 1)
                current[key] = value.strip()
    if "Package" in current:
        packages[current["Package"]] = current
    return packages


def parse_depends(value: str) -> list[str]:
    names = []
    for group in value.split(","):
        first = group.split("|")[0].strip()
        name = re.split(r"[\s(]", first)[0]
        if name:
            names.append(name)
    return names


def resolve(packages: dict[str, dict], wanted: list[str]) -> list[str]:
    result: list[str] = []
    seen: set[str] = set()
    queue = list(wanted)
    while queue:
        name = queue.pop(0)
        if name in seen or name in CORE_SKIP:
            continue
        seen.add(name)
        info = packages.get(name)
        if not info:
            print(f"  ! 索引里没有 {name}（跳过）")
            continue
        result.append(name)
        queue.extend(parse_depends(info.get("Depends", "")))
    return result


def missing_libs(path: str) -> list[str]:
    output = subprocess.run(["ldd", path], capture_output=True, text=True).stdout
    return sorted({line.split("=>")[0].strip() for line in output.splitlines() if "not found" in line})


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="无 root 安装系统库到本地目录")
    parser.add_argument("--wanted", nargs="*", default=[])
    parser.add_argument("--from-ldd", action="append", default=[],
                        help="根据某个 .so/可执行文件缺失的库自动补齐（可重复）")
    parser.add_argument("--cache", default="/tmp/deb-sysroot")
    parser.add_argument("--root", default="/tmp/sysroot")
    args = parser.parse_args(argv)

    packages = load_index(args.cache)
    print(f"索引中共 {len(packages)} 个包")

    wanted = list(args.wanted)
    if args.from_ldd:
        # 通过 lib 文件名反查包名：Debian 里没有直接映射，这里用常见映射表 + 提示
        print("提示：--from-ldd 只做报告，实际包名请用 --wanted 指定。")
        for path in args.from_ldd:
            print(f"  {path} 缺少: {missing_libs(path)}")

    if not wanted:
        print("没有指定 --wanted，退出。")
        return 1

    names = resolve(packages, wanted)
    print(f"需要下载 {len(names)} 个包：{', '.join(names)}")

    os.makedirs(args.cache, exist_ok=True)
    os.makedirs(args.root, exist_ok=True)
    for name in names:
        info = packages.get(name)
        if not info or "Filename" not in info:
            continue
        deb = os.path.join(args.cache, os.path.basename(info["Filename"]))
        if not os.path.exists(deb):
            print(f"  下载 {name} …")
            _fetch(MIRROR + info["Filename"], deb)
        subprocess.run(["dpkg-deb", "-x", deb, args.root], check=True)

    libdirs = [os.path.join(args.root, "usr/lib/x86_64-linux-gnu"),
               os.path.join(args.root, "lib/x86_64-linux-gnu"),
               os.path.join(args.root, "usr/lib/x86_64-linux-gnu/dri")]
    libdirs = [d for d in libdirs if os.path.isdir(d)]
    print("\n解包完成。设置环境变量：\n")
    print(f"  export LD_LIBRARY_PATH={':'.join(libdirs)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
