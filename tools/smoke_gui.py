#!/usr/bin/env python3
"""GUI 无头自检（CI 用）。

没有手机、没有显示器也能跑：Qt 的 offscreen 平台插件让我们可以在 CI 里
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

PANELS = (
    "device_panel", "audio_panel", "video_panel", "camera_panel", "keyboard_panel",
    "mouse_panel", "gamepad_panel", "recording_panel", "control_panel", "window_panel",
    "shortcuts_panel", "virtual_display_panel", "v4l2_panel", "developer_panel",
    "registry_panel",
)


def main() -> int:
    try:
        from PySide6.QtWidgets import QApplication
    except ImportError as exc:
        print(f"跳过：未安装 PySide6（{exc}）")
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

    # 3. 每个面板的 get_args() 都要能返回列表（不能抛异常）
    for name in PANELS:
        panel = getattr(window, name, None)
        if panel is None:
            failures.append(f"面板缺失: {name}")
            continue
        try:
            args = panel.get_args()
        except Exception as exc:  # noqa: BLE001
            failures.append(f"{name}.get_args() 抛异常: {exc!r}")
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
    registry_panel = getattr(window, "registry_panel", None)
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
    print(f"GUI 无头自检通过（{len(PANELS)} 个面板）。")
    return 0


if __name__ == "__main__":
    sys.exit(main())
