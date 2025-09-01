from PyQt6.QtWidgets import (QWidget, QVBoxLayout, QFormLayout, QGroupBox,
                             QComboBox, QCheckBox, QLabel)


class KeyboardPanel(QWidget):
    """
    【全新】键盘设置面板
    根据官方 keyboard.md 文档实现。
    """

    def __init__(self):
        super().__init__()
        main_layout = QVBoxLayout()
        main_layout.setContentsMargins(10, 10, 10, 10)
        main_layout.setSpacing(10)

        # --- 分组1: 键盘输入模式 ---
        mode_group = QGroupBox("键盘输入模式")
        mode_layout = QFormLayout(mode_group)

        self.keyboard_mode_combo = QComboBox()
        self.keyboard_mode_combo.addItems([
            "sdk (默认, 兼容性好)",
            "uhid (推荐, 需配置布局, -K)",
            "aoa (仅限USB)",
            "disabled (禁用键盘)"
        ])

        # 模式切换时，更新 SDK 专属选项的可用状态
        self.keyboard_mode_combo.currentTextChanged.connect(self.on_mode_changed)

        mode_layout.addRow("选择键盘模式:", self.keyboard_mode_combo)

        # --- 分组2: SDK 模式专属选项 ---
        self.sdk_options_group = QGroupBox("SDK 模式专属选项")
        sdk_layout = QFormLayout(self.sdk_options_group)
        self.prefer_text_check = QCheckBox("优先使用文本注入 (修复部分输入问题)")
        self.prefer_text_check.setToolTip("此选项会破坏游戏中的 WASD 等按键行为。")
        self.raw_key_events_check = QCheckBox("强制使用原始按键事件 (游戏模式)")
        self.no_key_repeat_check = QCheckBox("禁用按键重复事件 (优化游戏性能)")

        sdk_layout.addRow(self.prefer_text_check)
        sdk_layout.addRow(self.raw_key_events_check)
        sdk_layout.addRow(self.no_key_repeat_check)

        # --- 分组3: UHID/AOA 模式配置提示 ---
        hid_info_group = QGroupBox("物理键盘 (UHID/AOA) 配置指南")
        hid_info_layout = QVBoxLayout(hid_info_group)
        info_label_1 = QLabel("当使用 <b>UHID</b> 或 <b>AOA</b> 模式时, 您需要一次性配置手机：")
        info_label_2 = QLabel("  • 在 scrcpy 镜像窗口中按 <b>Ctrl+k</b> (或 MOD+k)。")
        info_label_3 = QLabel("  • 或在手机上进入 <b>设置 → 系统 → 语言和输入 → 实体键盘</b>。")
        info_label_4 = QLabel("  • 在此页面配置键盘布局，并可选择隐藏虚拟键盘。")
        hid_info_layout.addWidget(info_label_1)
        hid_info_layout.addWidget(info_label_2)
        hid_info_layout.addWidget(info_label_3)
        hid_info_layout.addWidget(info_label_4)

        # --- 最终布局 ---
        main_layout.addWidget(mode_group)
        main_layout.addWidget(self.sdk_options_group)
        main_layout.addWidget(hid_info_group)
        main_layout.addStretch()
        self.setLayout(main_layout)

        # 初始化UI状态
        self.on_mode_changed(self.keyboard_mode_combo.currentText())

    def on_mode_changed(self, mode_text):
        """当键盘模式切换时，控制 SDK 专属选项组的可用性"""
        mode = mode_text.split(' ')[0]
        is_sdk_mode = (mode == "sdk")
        self.sdk_options_group.setEnabled(is_sdk_mode)

    def get_args(self):
        """获取该面板对应的 scrcpy 命令行参数"""
        args = []

        mode = self.keyboard_mode_combo.currentText().split(' ')[0]

        # 只有当选择的不是默认的 "sdk" 时，才添加模式参数
        if mode != "sdk":
            args.extend(['--keyboard', mode])
        else:
            # 只有在 SDK 模式下，才检查这些专属选项
            if self.prefer_text_check.isChecked():
                args.append('--prefer-text')
            if self.raw_key_events_check.isChecked():
                args.append('--raw-key-events')
            if self.no_key_repeat_check.isChecked():
                args.append('--no-key-repeat')

        return args