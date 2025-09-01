from PyQt6.QtWidgets import (QWidget, QVBoxLayout, QFormLayout, QGroupBox,
                             QComboBox, QCheckBox, QLineEdit, QLabel)


class MousePanel(QWidget):
    """
    【全新】鼠标设置面板
    根据官方 mouse.md 文档实现。
    """

    def __init__(self):
        super().__init__()
        main_layout = QVBoxLayout()
        main_layout.setContentsMargins(10, 10, 10, 10)
        main_layout.setSpacing(10)

        # --- 分组1: 鼠标输入模式 ---
        mode_group = QGroupBox("鼠标输入模式")
        mode_layout = QFormLayout(mode_group)

        self.mouse_mode_combo = QComboBox()
        self.mouse_mode_combo.addItems([
            "sdk (默认, 绝对坐标)",
            "uhid (推荐, 捕捉鼠标, -M)",
            "aoa (仅限USB)",
            "disabled (禁用鼠标)"
        ])

        # 模式切换时，更新相关选项
        self.mouse_mode_combo.currentTextChanged.connect(self.on_mode_changed)

        mode_layout.addRow("选择鼠标模式:", self.mouse_mode_combo)

        # --- 分组2: SDK 模式专属选项 ---
        self.sdk_options_group = QGroupBox("SDK 模式专属选项")
        sdk_layout = QFormLayout(self.sdk_options_group)
        self.no_mouse_hover_check = QCheckBox("禁用鼠标悬停事件")
        sdk_layout.addRow(self.no_mouse_hover_check)

        # --- 分组3: 鼠标按键绑定 (高级) ---
        bindings_group = QGroupBox("鼠标按键绑定 (高级)")
        bindings_layout = QFormLayout(bindings_group)
        info_label = QLabel("绑定字符: + (转发), - (忽略), b (返回), h (主页), s (切换), n (通知)")

        self.primary_bindings_input = QLineEdit()
        self.primary_bindings_input.setPlaceholderText("右键/中键/4键/5键")

        self.secondary_bindings_input = QLineEdit()
        self.secondary_bindings_input.setPlaceholderText("Shift + 右/中/4/5")

        bindings_layout.addWidget(info_label)
        bindings_layout.addRow("主要绑定:", self.primary_bindings_input)
        bindings_layout.addRow("次要绑定 (Shift):", self.secondary_bindings_input)

        # --- 最终布局 ---
        main_layout.addWidget(mode_group)
        main_layout.addWidget(self.sdk_options_group)
        main_layout.addWidget(bindings_group)
        main_layout.addStretch()
        self.setLayout(main_layout)

        # 初始化UI状态
        self.on_mode_changed(self.mouse_mode_combo.currentText())

    def on_mode_changed(self, mode_text):
        """当鼠标模式切换时，控制相关选项组的可用性并设置默认绑定"""
        mode = mode_text.split(' ')[0]
        is_sdk_mode = (mode == "sdk")

        self.sdk_options_group.setEnabled(is_sdk_mode)

        # 智能设置默认按键绑定
        if is_sdk_mode:
            self.primary_bindings_input.setText("bhsn")
            self.secondary_bindings_input.setText("++++")
        elif mode in ["uhid", "aoa"]:
            self.primary_bindings_input.setText("++++")
            self.secondary_bindings_input.setText("bhsn")
        else:  # disabled
            self.primary_bindings_input.clear()
            self.secondary_bindings_input.clear()

    def get_args(self):
        """获取该面板对应的 scrcpy 命令行参数"""
        args = []

        mode = self.mouse_mode_combo.currentText().split(' ')[0]

        # 模式
        if mode != "sdk":
            args.extend(['--mouse', mode])
        elif self.no_mouse_hover_check.isChecked():
            # 仅在 SDK 模式下此选项有效
            args.append('--no-mouse-hover')

        # 按键绑定
        primary = self.primary_bindings_input.text().strip()
        secondary = self.secondary_bindings_input.text().strip()

        if primary or secondary:
            # 检查默认值，如果和智能填充的一样，则不添加参数，让命令更简洁
            is_sdk_default = (mode == "sdk" and primary == "bhsn" and secondary == "++++")
            is_hid_default = (mode in ["uhid", "aoa"] and primary == "++++" and secondary == "bhsn")

            if not is_sdk_default and not is_hid_default:
                if secondary:
                    args.extend(['--mouse-bind', f"{primary}:{secondary}"])
                elif primary:
                    args.extend(['--mouse-bind', primary])

        return args