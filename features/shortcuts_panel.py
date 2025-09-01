from PyQt6.QtWidgets import (QWidget, QVBoxLayout, QFormLayout, QGroupBox,
                             QComboBox, QLabel, QScrollArea)
from PyQt6.QtCore import Qt


class ShortcutsPanel(QWidget):
    """
    【全新】快捷键面板
    提供快捷键修饰符 (MOD) 的自定义选项，并作为快捷键速查表。
    """

    def __init__(self):
        super().__init__()
        main_layout = QVBoxLayout()
        main_layout.setContentsMargins(10, 10, 10, 10)

        # --- 分组1: 修饰键 (MOD) 设置 ---
        mod_group = QGroupBox("快捷键修饰符 (MOD) 设置")
        mod_layout = QFormLayout(mod_group)

        self.shortcut_mod_combo = QComboBox()
        self.shortcut_mod_combo.addItems([
            "默认 (lalt, lsuper)",
            "lctrl (左 Ctrl)",
            "rctrl (右 Ctrl)",
            "lalt (左 Alt)",
            "ralt (右 Alt)",
            "lsuper (左 Super/Win/Cmd)",
            "rsuper (右 Super/Win/Cmd)"
        ])

        mod_layout.addRow("选择修饰键:", self.shortcut_mod_combo)

        # --- 分组2: 快捷键速查表 ---
        cheatsheet_group = QGroupBox("快捷键速查表 (MOD + Key)")
        cheatsheet_layout = QVBoxLayout(cheatsheet_group)

        # 使用 QScrollArea 以防内容过多
        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_widget = QWidget()
        scroll_layout = QFormLayout(scroll_widget)
        scroll_layout.setRowWrapPolicy(QFormLayout.RowWrapPolicy.WrapAllRows)
        scroll_layout.setLabelAlignment(Qt.AlignmentFlag.AlignLeft)

        shortcuts = {
            "<b>f</b>": "切换全屏模式",
            "<b>h</b>": "主页 (HOME)",
            "<b>b</b> 或 <b>Backspace</b>": "返回 (BACK)",
            "<b>s</b>": "切换应用 (APP_SWITCH)",
            "<b>m</b>": "菜单 (MENU)",
            "<b>p</b>": "电源键 (POWER)",
            "<b>o</b>": "关闭设备屏幕 (镜像继续)",
            "<b>Shift + o</b>": "打开设备屏幕",
            "<b>↑ / ↓</b>": "音量增 / 减",
            "<b>← / →</b>": "向左 / 右旋转屏幕",
            "<b>r</b>": "旋转设备屏幕 (切换方向)",
            "<b>n</b>": "展开通知面板",
            "<b>Shift + n</b>": "收起通知面板",
            "<b>c / x / v</b>": "复制 / 剪切 / 粘贴",
            "<b>i</b>": "开关 FPS 计数器 (在控制台显示)",
            "<b>g</b>": "调整窗口为 1:1 像素完美尺寸",
            "<b>w</b>": "调整窗口去黑边",
        }

        for key, desc in shortcuts.items():
            scroll_layout.addRow(QLabel(key), QLabel(desc))

        scroll_area.setWidget(scroll_widget)
        cheatsheet_layout.addWidget(scroll_area)

        # --- 最终布局 ---
        main_layout.addWidget(mod_group)
        main_layout.addWidget(cheatsheet_group)
        self.setLayout(main_layout)

    def get_args(self):
        """获取该面板对应的 scrcpy 命令行参数"""
        args = []

        mod_text = self.shortcut_mod_combo.currentText().split(' ')[0]

        # 只有当选择的不是默认值时，才添加参数
        if mod_text != "默认":
            args.extend(['--shortcut-mod', mod_text])

        return args