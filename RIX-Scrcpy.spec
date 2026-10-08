# -*- mode: python ; coding: utf-8 -*-
"""
PyInstaller 打包配置（RIX Scrcpy GUI，onedir 模式）。

为什么用 onedir 而不是 onefile：
  onefile 每次启动都要把整个包解压到 %TEMP%，启动慢、内存峰值高，还容易被杀软误报。
  onedir 启动快、内存曲线平缓，符合本项目「省内存 + 无异常」的目标。

注意：本文件必须纳入版本管理，否则构建不可复现。
用法（仓库根目录）：pyinstaller RIX-Scrcpy.spec --noconfirm
"""

import os
import sys

# SPECPATH 由 PyInstaller 注入，指向本文件所在目录（仓库根目录）
ROOT = SPECPATH
ICON = os.path.join(ROOT, "RIXHC.ico")
NOTICES = os.path.join(ROOT, "THIRD_PARTY_NOTICES.md")
# 内置 scrcpy 核心：由 CI（或 tools/ 手动执行 python -m rix.vendor install）准备到
# vendor/scrcpy/。存在就一起打包，不存在则程序自动回退到系统 PATH。
VENDOR_DIR = os.path.join(ROOT, "vendor", "scrcpy")

DATAS = [(ICON, ".")]
if os.path.isfile(NOTICES):
    DATAS.append((NOTICES, "."))
if os.path.isdir(VENDOR_DIR):
    DATAS.append((VENDOR_DIR, "scrcpy"))

# 这些 Qt 模块本项目完全用不到，排除掉可以显著减小体积
EXCLUDES = [
    "PySide6.QtWebEngineCore",
    "PySide6.QtWebEngineWidgets",
    "PySide6.QtWebEngineQuick",
    "PySide6.QtQuick",
    "PySide6.QtQuickWidgets",
    "PySide6.QtQml",
    "PySide6.Qt3DCore",
    "PySide6.QtCharts",
    "PySide6.QtDataVisualization",
    "PySide6.QtMultimedia",
    "PySide6.QtMultimediaWidgets",
    "PySide6.QtPdf",
    "PySide6.QtPdfWidgets",
    "PySide6.QtBluetooth",
    "PySide6.QtNfc",
    "PySide6.QtPositioning",
    "PySide6.QtSql",
    "PySide6.QtTest",
    "PySide6.QtDesigner",
    "PySide6.QtHelp",
    "PySide6.QtOpenGLWidgets",
    "tkinter",
    "unittest",
    "pytest",
]

a = Analysis(
    [os.path.join(ROOT, "main.py")],
    pathex=[ROOT],
    binaries=[],
    # 图标、第三方声明、以及内置的 scrcpy 核心
    datas=DATAS,
    hiddenimports=[],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=EXCLUDES,
    noarchive=False,
)

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="RIX-Scrcpy",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,  # GUI 程序，不弹控制台
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=ICON,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name="RIX-Scrcpy",
)
