from PyQt6.QtWidgets import (QWidget, QVBoxLayout, QFormLayout, QGroupBox,
                             QLineEdit, QCheckBox, QHBoxLayout, QLabel)


class WindowPanel(QWidget):
    """
    【终极版】窗口设置面板
    根据官方 window.md 文档实现所有窗口相关选项。
    """

    def __init__(self):
        super().__init__()
        main_layout = QVBoxLayout()
        main_layout.setContentsMargins(10, 10, 10, 10)
        main_layout.setSpacing(10)

        # --- 分组1: 标题与位置 ---
        position_group = QGroupBox("窗口标题、位置与尺寸")
        position_layout = QFormLayout(position_group)

        self.window_title_input = QLineEdit()
        self.window_title_input.setPlaceholderText("默认为设备型号")

        # 将 X 和 Y 放在同一行
        pos_xy_layout = QHBoxLayout()
        pos_xy_layout.setContentsMargins(0, 0, 0, 0)
        self.window_x_input = QLineEdit()
        self.window_x_input.setPlaceholderText("X 坐标")
        self.window_y_input = QLineEdit()
        self.window_y_input.setPlaceholderText("Y 坐标")
        pos_xy_layout.addWidget(QLabel("X:"))
        pos_xy_layout.addWidget(self.window_x_input)
        pos_xy_layout.addWidget(QLabel("Y:"))
        pos_xy_layout.addWidget(self.window_y_input)

        # 将宽度和高度放在同一行
        size_wh_layout = QHBoxLayout()
        size_wh_layout.setContentsMargins(0, 0, 0, 0)
        self.window_width_input = QLineEdit()
        self.window_width_input.setPlaceholderText("宽度")
        self.window_height_input = QLineEdit()
        self.window_height_input.setPlaceholderText("高度")
        size_wh_layout.addWidget(QLabel("宽:"))
        size_wh_layout.addWidget(self.window_width_input)
        size_wh_layout.addWidget(QLabel("高:"))
        size_wh_layout.addWidget(self.window_height_input)

        position_layout.addRow("窗口标题:", self.window_title_input)
        position_layout.addRow("初始位置:", pos_xy_layout)
        position_layout.addRow("初始尺寸:", size_wh_layout)

        # --- 分组2: 窗口样式与行为 ---
        style_group = QGroupBox("窗口样式与行为")
        style_layout = QVBoxLayout(style_group)
        self.borderless_check = QCheckBox("无边框窗口")
        self.always_on_top_check = QCheckBox("窗口总在最前")
        self.fullscreen_check = QCheckBox("启动时全屏 (-f)")
        self.disable_screensaver_check = QCheckBox("禁用电脑屏幕保护")

        info_label = QLabel("<i>注意：'--no-window' 选项请在“录制设置”面板中查找。</i>")

        style_layout.addWidget(self.borderless_check)
        style_layout.addWidget(self.always_on_top_check)
        style_layout.addWidget(self.fullscreen_check)
        style_layout.addWidget(self.disable_screensaver_check)
        style_layout.addWidget(info_label)

        # --- 最终布局 ---
        main_layout.addWidget(position_group)
        main_layout.addWidget(style_group)
        main_layout.addStretch()
        self.setLayout(main_layout)

    def get_args(self):
        """获取该面板对应的 scrcpy 命令行参数"""
        args = []

        if val := self.window_title_input.text().strip():
            args.extend(['--window-title', val])
        if val := self.window_x_input.text().strip():
            args.extend(['--window-x', val])
        if val := self.window_y_input.text().strip():
            args.extend(['--window-y', val])
        if val := self.window_width_input.text().strip():
            args.extend(['--window-width', val])
        if val := self.window_height_input.text().strip():
            args.extend(['--window-height', val])

        if self.borderless_check.isChecked():
            args.append('--window-borderless')
        if self.always_on_top_check.isChecked():
            args.append('--always-on-top')
        if self.fullscreen_check.isChecked():
            args.append('--fullscreen')
        if self.disable_screensaver_check.isChecked():
            args.append('--disable-screensaver')

        return args