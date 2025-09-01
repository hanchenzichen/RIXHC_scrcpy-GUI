from PyQt6.QtWidgets import (QWidget, QVBoxLayout, QFormLayout, QGroupBox,
                             QCheckBox, QLineEdit, QLabel)


class ControlPanel(QWidget):
    """
    【终极版 - 设备状态管理器】
    整合了 control.md 和 device.md 中的所有相关选项。
    """

    def __init__(self):
        super().__init__()
        main_layout = QVBoxLayout()
        main_layout.setContentsMargins(10, 10, 10, 10)
        main_layout.setSpacing(10)

        # --- 分组1: 设备状态控制 (来自 device.md) ---
        device_state_group = QGroupBox("设备状态控制")
        device_state_layout = QFormLayout(device_state_group)

        self.stay_awake_check = QCheckBox("保持唤醒 (仅限USB连接时, -w)")
        self.turn_screen_off_check = QCheckBox("启动时关闭屏幕 (-S)")
        self.show_touches_check = QCheckBox("显示物理触摸操作 (-t)")
        self.power_off_on_close_check = QCheckBox("关闭scrcpy时关闭屏幕")
        self.no_power_on_check = QCheckBox("启动时不点亮屏幕")

        self.screen_off_timeout_input = QLineEdit()
        self.screen_off_timeout_input.setPlaceholderText("例如: 300 (单位: 秒)")

        device_state_layout.addRow(self.stay_awake_check)
        device_state_layout.addRow(self.turn_screen_off_check)
        device_state_layout.addRow(self.show_touches_check)
        device_state_layout.addRow(self.power_off_on_close_check)
        device_state_layout.addRow(self.no_power_on_check)
        device_state_layout.addRow("屏幕关闭超时(秒):", self.screen_off_timeout_input)

        # --- 分组2: 交互控制 (来自 control.md) ---
        interaction_group = QGroupBox("交互控制")
        interaction_layout = QVBoxLayout(interaction_group)
        self.readonly_check = QCheckBox("只读模式 (禁用所有控制, -n)")

        # 剪贴板和文件拖放设置
        clipboard_layout = QFormLayout()
        self.no_clipboard_autosync_check = QCheckBox("禁用剪贴板自动同步")
        self.legacy_paste_check = QCheckBox("使用传统粘贴模式")
        self.push_target_input = QLineEdit()
        self.push_target_input.setPlaceholderText("例如: /sdcard/Movies/")
        clipboard_layout.addRow(self.no_clipboard_autosync_check)
        clipboard_layout.addRow(self.legacy_paste_check)
        clipboard_layout.addRow("文件推送目标路径:", self.push_target_input)

        interaction_layout.addWidget(self.readonly_check)
        interaction_layout.addLayout(clipboard_layout)

        # --- 最终布局 ---
        main_layout.addWidget(device_state_group)
        main_layout.addWidget(interaction_group)
        main_layout.addStretch()
        self.setLayout(main_layout)

    def get_args(self):
        """获取该面板对应的 scrcpy 命令行参数"""
        args = []

        # 设备状态
        if self.stay_awake_check.isChecked():
            args.append('--stay-awake')
        if self.turn_screen_off_check.isChecked():
            args.append('--turn-screen-off')
        if self.show_touches_check.isChecked():
            args.append('--show-touches')
        if self.power_off_on_close_check.isChecked():
            args.append('--power-off-on-close')
        if self.no_power_on_check.isChecked():
            args.append('--no-power-on')
        if val := self.screen_off_timeout_input.text().strip():
            args.extend(['--screen-off-timeout', val])

        # 交互控制
        if self.readonly_check.isChecked():
            args.append('--no-control')
        if self.no_clipboard_autosync_check.isChecked():
            args.append('--no-clipboard-autosync')
        if self.legacy_paste_check.isChecked():
            args.append('--legacy-paste')
        if target_path := self.push_target_input.text().strip():
            args.extend(['--push-target', target_path])

        return args