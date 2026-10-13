#!/usr/bin/env python3
"""GUI 无头自检（CI 用）。

没有设备、没有显示器也能运行：Qt 的 offscreen 平台插件使得可以在 CI 中
真正实例化整个主窗口，从而抓到「导入即崩溃」「控件初始化异常」这类问题
（这类问题光靠语法检查是抓不到的）。

本地运行：
    QT_QPA_PLATFORM=offscreen python tools/smoke_gui.py
"""

from __future__ import annotations

import os
import sys
import traceback

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# 左侧 device_panel 是常驻面板（不是页签），其余通过 window.panel(名字) 取得
PANELS = (
    "audio", "video", "camera", "recording", "control", "keyboard", "mouse",
    "gamepad", "window", "shortcuts", "virtual_display", "v4l2", "developer", "registry",
)


def main() -> int:
    try:
        from PySide6.QtWidgets import QApplication
    except ImportError as exc:
        message = str(exc)
        if "cannot open shared object" in message or "libGL" in message:
            print("跳过：PySide6 已安装但缺少系统图形库（libGL/X11 等）。")
            print("  Linux 上可执行：sudo apt install libgl1 libegl1 libx11-6 libxkbcommon0 "
                  "libglib2.0-0 libfreetype6 libfontconfig1 libdbus-1-3")
            print("  或直接在桌面系统上运行本脚本。")
        else:
            print(f"跳过：未安装 PySide6（{message}）")
        return 0

    from main import ScrcpyMainMenu, resource_path

    app = QApplication.instance() or QApplication(sys.argv)
    failures: list[str] = []

    # 1. 图标资源路径：无论从哪个工作目录启动都必须能找到
    icon = resource_path("RIXHC.ico")
    if not os.path.isfile(icon):
        failures.append(f"找不到图标资源: {icon}")

    # 2. 主窗口能构造出来
    try:
        window = ScrcpyMainMenu()
        window.show()
        app.processEvents()
    except Exception:
        print("主窗口构造失败：")
        traceback.print_exc()
        return 1

    # 2.5 面板懒加载：刚构造完时不应把所有面板都建出来（启动性能的关键）
    total_tabs = len(getattr(window, "_tab_names", []))
    built_before = len(getattr(window, "_panels", {}))
    if total_tabs and built_before >= total_tabs:
        failures.append(
            f"面板懒加载失效：构造后已构建 {built_before}/{total_tabs} 个面板")

    # 3. 每个面板的 get_args() 都要能返回列表（不能抛异常）
    #    懒加载下先显式构建全部面板
    window.ensure_all_panels()
    app.processEvents()
    if total_tabs and len(window._panels) != total_tabs:
        failures.append(f"ensure_all_panels() 后只构建了 {len(window._panels)}/{total_tabs} 个面板")
    #    例外：device_panel 在「没选设备」时会返回 None 表示选择不合法，
    #    主窗口据此中止启动并给出提示，这是既定契约。
    for name in PANELS:
        panel = getattr(window, name, None) if name == "device_panel" else window.panel(name)
        if panel is None:
            failures.append(f"面板缺失: {name}")
            continue
        try:
            args = panel.get_args()
        except Exception as exc:  # noqa: BLE001
            failures.append(f"{name}.get_args() 抛异常: {exc!r}")
            continue
        if args is None and name == "device_panel":
            continue
        if not isinstance(args, list) or not all(isinstance(item, str) for item in args):
            failures.append(f"{name}.get_args() 返回值不是字符串列表: {args!r}")

    # 4. 参数拼装与命令预览路径（不弹窗，只走逻辑）
    for is_otg in (False, True):
        try:
            window.build_session_args(is_otg=is_otg)
        except Exception as exc:  # noqa: BLE001
            failures.append(f"build_session_args(is_otg={is_otg}) 抛异常: {exc!r}")
    try:
        window.format_command(["--no-audio"])
    except Exception as exc:  # noqa: BLE001
        failures.append(f"format_command 抛异常: {exc!r}")

    # 4.5 注册表面板必须覆盖全部参数，且不能出现幽灵参数
    registry_panel = window.panel("registry")
    if registry_panel is not None and registry_panel.registry is not None:
        total = registry_panel.registry.option_count
        rendered = len(registry_panel._editors)
        if rendered != total:
            failures.append(f"注册表面板只渲染了 {rendered}/{total} 个参数")
        if "server-debugger" in registry_panel.registry:
            failures.append("注册表里出现了从未存在的参数 --server-debugger")

    # 5. 干净退出（会触发 closeEvent → 停止所有会话）
    window.close()
    app.processEvents()

    if failures:
        print("GUI 自检失败：")
        for item in failures:
            print(f"  - {item}")
        return 1
    print(f"GUI 无头自检通过（{len(PANELS)} 个页签面板 + 常驻设备面板）。")
    return 0


if __name__ == "__main__":
    sys.exit(main())
