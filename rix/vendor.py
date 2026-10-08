"""内置（vendor）scrcpy 核心：下载、校验、解包、定位。

为什么内置：
    用户最常见的失败原因不是本程序的问题，而是「没装 scrcpy / 装了但不在 PATH /
    scrcpy 与 adb 版本不匹配」。把官方发布的 scrcpy 核心随程序一起分发，
    可以一次性消除这三类问题——官方包本身就同时包含 scrcpy 与 adb。

合规做法（重要）：
    * 只分发**未经修改**的官方发布包，解包后原样保留上游的 `LICENSE`/`LICENSE.txt`；
    * 同时在本项目里保留 `THIRD_PARTY_NOTICES.md` 说明来源、版本与许可证；
    * 下载时用上游发布的 `SHA256SUMS.txt` 做完整性校验。

查找顺序（find_scrcpy_binary）：
    1. 环境变量 `RIX_SCRCPY`
    2. 随程序打包的 `scrcpy/` 目录
    3. 用户数据目录下的 `vendor/scrcpy`（用 `rix-scrcpy vendor install` 安装）
    4. 系统 PATH 与常见安装位置
"""

from __future__ import annotations

import hashlib
import json
import os
import platform as platform_module
import shutil
import sys
import tarfile
import urllib.request
import zipfile

RELEASES_API = "https://api.github.com/repos/Genymobile/scrcpy/releases/latest"
DOWNLOAD_URL = "https://github.com/Genymobile/scrcpy/releases/download/{tag}/{asset}"
SUMS_URL = "https://github.com/Genymobile/scrcpy/releases/download/{tag}/SHA256SUMS.txt"

APP_DIR_NAME = "rix-scrcpy"


def _appdata_dir() -> str:
    if os.name == "nt":
        base = os.environ.get("LOCALAPPDATA") or os.path.expanduser("~")
    else:
        base = os.environ.get("XDG_DATA_HOME") or os.path.join(os.path.expanduser("~"), ".local", "share")
    return os.path.join(base, APP_DIR_NAME)


def user_vendor_dir() -> str:
    """用户级安装目录（运行时 `vendor install` 的目标）。"""
    return os.path.join(_appdata_dir(), "vendor", "scrcpy")


def bundled_vendor_dir() -> str | None:
    """随程序分发的目录。

    覆盖三种运行方式：
      * PyInstaller 打包后：资源在 sys._MEIPASS/scrcpy
      * 解压即用：可执行文件同级的 scrcpy/
      * 源码运行：仓库根目录的 vendor/scrcpy
    """
    candidates = []
    meipass = getattr(sys, "_MEIPASS", None)
    if meipass:
        candidates.append(os.path.join(meipass, "scrcpy"))
    if getattr(sys, "frozen", False):
        candidates.append(os.path.join(os.path.dirname(sys.executable), "scrcpy"))
    candidates.append(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "vendor", "scrcpy"))
    for path in candidates:
        if os.path.isdir(path):
            return path
    return None


def vendor_dirs() -> list[str]:
    dirs = []
    for path in (bundled_vendor_dir(), user_vendor_dir()):
        if path:
            dirs.append(path)
    return dirs


def current_platform() -> str:
    """返回资产名里的平台标识，例如 win64 / linux-x86_64 / macos-aarch64。"""
    system = sys.platform
    machine = platform_module.machine().lower()
    if system == "win32":
        if machine in ("arm64", "aarch64"):
            return "winarm64"
        if machine in ("x86", "i386", "i686"):
            return "win32"
        return "win64"
    if system == "darwin":
        return "macos-aarch64" if machine in ("arm64", "aarch64") else "macos-x86_64"
    return "linux-x86_64" if machine in ("x86_64", "amd64") else f"linux-{machine}"


def asset_name(version: str, plat: str | None = None) -> str:
    plat = plat or current_platform()
    extension = "zip" if plat.startswith("win") else "tar.gz"
    return f"scrcpy-{plat}-v{version}.{extension}"


def _urlopen(url: str, timeout: int = 60):
    request = urllib.request.Request(url, headers={"User-Agent": "rix-scrcpy-vendor"})
    return urllib.request.urlopen(request, timeout=timeout)  # noqa: S310


def latest_version() -> str:
    """查询上游最新版本号（不含 v 前缀）。"""
    with _urlopen(RELEASES_API, timeout=30) as resp:
        payload = json.load(resp)
    return str(payload["tag_name"]).lstrip("v")


def sha256_of(path: str) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def fetch_expected_hash(tag: str, asset: str, timeout: int = 30) -> str | None:
    try:
        with _urlopen(SUMS_URL.format(tag=tag), timeout=timeout) as resp:
            text = resp.read().decode("utf-8", errors="replace")
    except OSError:
        return None
    for line in text.splitlines():
        parts = line.split()
        if len(parts) == 2 and parts[1] == asset:
            return parts[0].lower()
    return None


def download(version: str, dest_path: str, plat: str | None = None, log=print) -> tuple[str, str | None]:
    """下载官方发布包到 dest_path，返回 (版本, 期望的 sha256 或 None)。"""
    tag = f"v{version}"
    asset = asset_name(version, plat)
    url = DOWNLOAD_URL.format(tag=tag, asset=asset)
    log(f"下载 {asset} ...")
    os.makedirs(os.path.dirname(os.path.abspath(dest_path)), exist_ok=True)
    with _urlopen(url, timeout=300) as resp, open(dest_path, "wb") as handle:
        shutil.copyfileobj(resp, handle, length=1024 * 1024)
    expected = fetch_expected_hash(tag, asset)
    return version, expected


def extract(archive_path: str, target_dir: str, log=print) -> None:
    """解包并去掉顶层目录；已存在的内容会被覆盖。"""
    os.makedirs(target_dir, exist_ok=True)
    if archive_path.endswith(".zip"):
        with zipfile.ZipFile(archive_path) as archive:
            members = archive.namelist()
            prefix = members[0].split("/")[0] + "/" if members else ""
            top = members[0].split("/")[0] if members else ""
            for member in members:
                if member.rstrip("/") == top:
                    continue
                relative = member[len(prefix):] if member.startswith(prefix) else member
                if not relative:
                    continue
                destination = os.path.join(target_dir, relative)
                if member.endswith("/"):
                    os.makedirs(destination, exist_ok=True)
                    continue
                os.makedirs(os.path.dirname(destination), exist_ok=True)
                with archive.open(member) as source, open(destination, "wb") as out:
                    shutil.copyfileobj(source, out)
    else:
        with tarfile.open(archive_path) as archive:
            members = archive.getmembers()
            # 注意：TarInfo.name 会把结尾的斜杠去掉，所以顶层目录要单独跳过
            top = members[0].name.split("/")[0] if members else ""
            prefix = top + "/"
            for member in members:
                if member.name == top:
                    continue
                relative = member.name[len(prefix):] if member.name.startswith(prefix) else member.name
                if not relative:
                    continue
                member.name = relative
                try:
                    # Python 3.12+ 支持 filter，可防止路径穿越；旧版本回退
                    archive.extract(member, target_dir, filter="data")
                except TypeError:
                    archive.extract(member, target_dir)
    if os.name != "nt":
        for name in ("scrcpy", "adb"):
            path = os.path.join(target_dir, name)
            if os.path.isfile(path):
                os.chmod(path, 0o755)
    log(f"已解包到 {target_dir}")


def install(version: str | None = None, target_dir: str | None = None,
            plat: str | None = None, verify: bool = True, log=print) -> str:
    """下载 + 校验 + 解包官方 scrcpy，返回安装目录。"""
    version = version or latest_version()
    target_dir = target_dir or user_vendor_dir()
    archive_path = os.path.join(_appdata_dir(), "cache", asset_name(version, plat))
    _, expected = download(version, archive_path, plat, log=log)

    if verify and expected:
        actual = sha256_of(archive_path)
        if actual != expected:
            os.remove(archive_path)
            raise RuntimeError(
                f"SHA256 校验失败，已删除下载文件。\n  期望: {expected}\n  实际: {actual}"
            )
        log("SHA256 校验通过")
    elif verify:
        log("警告：未取到上游 SHA256SUMS，跳过校验。")

    if os.path.isdir(target_dir):
        shutil.rmtree(target_dir)
    extract(archive_path, target_dir, log=log)
    log(f"scrcpy {version} 已安装到 {target_dir}")
    return target_dir


def status() -> dict:
    """返回内置核心的现状，供 CLI/GUI 展示。"""
    from rix.scrcpy_bin import VERSION_RE, run_capture

    result = {"platform": current_platform(), "bundled": None, "user": None,
              "version": None, "path": None}
    bundled = bundled_vendor_dir()
    user = user_vendor_dir()
    if bundled:
        result["bundled"] = bundled
    if os.path.isdir(user):
        result["user"] = user
    for directory in (bundled, user):
        if not directory:
            continue
        exe = os.path.join(directory, "scrcpy.exe" if os.name == "nt" else "scrcpy")
        if os.path.isfile(exe):
            match = VERSION_RE.search(run_capture([exe, "--version"], timeout=10))
            result["version"] = match.group(1) if match else "未知"
            result["path"] = exe
            break
    return result


def main(argv: list[str] | None = None) -> int:
    """供 CI / 高级用户使用：python -m rix.vendor install --target vendor/scrcpy"""
    import argparse

    parser = argparse.ArgumentParser(prog="python -m rix.vendor", description="内置 scrcpy 核心管理")
    sub = parser.add_subparsers(dest="command", required=True)
    p = sub.add_parser("install", help="下载并安装官方 scrcpy 到指定目录")
    p.add_argument("--version", help="版本号（默认取上游最新）")
    p.add_argument("--target", help="目标目录")
    p.add_argument("--platform", dest="plat", help="平台标识，如 win64 / linux-x86_64")
    p.add_argument("--no-verify", action="store_true", help="跳过 SHA256 校验（不建议）")
    sub.add_parser("status", help="显示内置核心现状")
    args = parser.parse_args(argv)

    if args.command == "status":
        info = status()
        print(f"平台: {info['platform']}")
        print(f"内置目录: {info['bundled'] or '（无）'}")
        print(f"用户目录: {info['user'] or '（无）'}")
        print(f"版本: {info['version'] or '未安装'}")
        return 0

    install(version=args.version, target_dir=args.target, plat=args.plat,
            verify=not args.no_verify)
    return 0


if __name__ == "__main__":
    sys.exit(main())
