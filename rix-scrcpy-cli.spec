# -*- mode: python ; coding: utf-8 -*-
"""
PyInstaller 打包配置（CLI / TUI，onefile 模式）。

CLI 是纯命令行程序，没有启动解压成本的顾虑，所以用 onefile：
用户拿到单个可执行文件，不需要安装 Python，也不需要解压目录。

用法（仓库根目录）：pyinstaller rix-scrcpy-cli.spec --noconfirm
"""

import os

ROOT = SPECPATH
DATA_DIR = os.path.join(ROOT, "rix", "data")

a = Analysis(
    [os.path.join(ROOT, "rix", "cli.py")],
    pathex=[ROOT],
    binaries=[],
    # 选项注册表是运行期读取的 JSON，必须一起打进去
    datas=[(DATA_DIR, os.path.join("rix", "data"))]
    # 说明：CLI 单文件刻意**不**内置 scrcpy（否则体积翻几倍），
    # 需要时运行 `rix-scrcpy vendor install` 即可一键获取官方核心。
    hiddenimports=["rix.registry", "rix.profiles", "rix.scrcpy_bin"],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=["PySide6", "PyQt6", "tkinter", "unittest"],
    noarchive=False,
)

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name="rix-scrcpy",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=True,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
