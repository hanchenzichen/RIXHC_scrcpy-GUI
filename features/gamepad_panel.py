from PyQt6.QtWidgets import (QWidget, QVBoxLayout, QFormLayout, QGroupBox, QComboBox)


class GamepadPanel(QWidget):
    """
    【全新】游戏手柄设置面板
    根据官方 gamepad.md 文档实现。
    """

    def __init__(self):
        super().__init__()
        main_layout = QVBoxLayout()
        main_layout.setContentsMargins(10, 10, 10, 10)

        # --- 分组: 游戏手柄模式 ---
        gamepad_group = QGroupBox("游戏手柄模式")
        gamepad_layout = QFormLayout(gamepad_group)

        self.gamepad_mode_combo = QComboBox()
        self.gamepad_mode_combo.addItems([
            "disabled (禁用, 默认)",
            "uhid (推荐, -G)",
            "aoa (仅限USB连接)"
        ])

        # 添加详细的 Tooltip 解释
        self.gamepad_mode_combo.setItemData(0, "不转发任何手柄输入。", 1)  # 第三个参数是 Role，1 代表 ToolTipRole
        self.gamepad_mode_combo.setItemData(1,
                                            "通过 UHID 内核模块模拟物理手柄，推荐此模式。\n可能在旧版安卓上因权限问题无法工作。",
                                            1)
        self.gamepad_mode_combo.setItemData(2, "通过 AOAv2 协议模拟物理手柄。\n此模式仅在通过 USB 数据线连接时有效。", 1)

        gamepad_layout.addRow("选择手柄模式:", self.gamepad_mode_combo)

        # --- 最终布局 ---
        main_layout.addWidget(gamepad_group)
        main_layout.addStretch()
        self.setLayout(main_layout)

    def get_args(self):
        """获取该面板对应的 scrcpy 命令行参数"""
        args = []

        mode_text = self.gamepad_mode_combo.currentText().split(' ')[0]

        # 只有当选择的不是默认的 "disabled" 时，才添加参数
        if mode_text != "disabled":
            args.extend(['--gamepad', mode_text])

        return args