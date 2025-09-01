import subprocess
import sys
from PyQt6.QtWidgets import (QWidget, QVBoxLayout, QFormLayout, QGroupBox,
                             QCheckBox, QPushButton, QLineEdit, QLabel, QHBoxLayout)


class V4l2Panel(QWidget):  # Python 类名通常不大写 "L"
    """
    【修正版】V4L2 Sink 面板 (Linux 专属)
    """

    def __init__(self):
        super().__init__()
        main_layout = QVBoxLayout()
        main_layout.setContentsMargins(10, 10, 10, 10)
        main_layout.setSpacing(10)

        self.enable_v4l2_check = QCheckBox("启用 V4L2 Sink (将手机作为摄像头)")
        self.enable_v4l2_check.toggled.connect(self.toggle_options)

        self.options_groupbox = QGroupBox("V4L2 选项")
        options_layout = QFormLayout(self.options_groupbox)

        device_path_layout = QHBoxLayout()
        self.v4l2_sink_input = QLineEdit()
        self.v4l2_sink_input.setPlaceholderText("例如: /dev/video0")
        self.list_devices_button = QPushButton("列出可用设备")
        self.list_devices_button.clicked.connect(self.handle_list_devices)
        device_path_layout.addWidget(self.v4l2_sink_input, 1)
        device_path_layout.addWidget(self.list_devices_button)

        self.no_playback_check = QCheckBox("仅输出到 V4L2 (不显示镜像窗口)")
        self.v4l2_buffer_input = QLineEdit()
        self.v4l2_buffer_input.setPlaceholderText("例如: 300 (单位: 毫秒)")

        options_layout.addRow("V4L2 设备路径:", device_path_layout)
        options_layout.addRow(self.no_playback_check)
        options_layout.addRow("V4L2 缓冲区(ms):", self.v4l2_buffer_input)

        info_group = QGroupBox("Linux 系统配置指南")
        info_layout = QVBoxLayout(info_group)
        info_label_1 = QLabel("1. 安装模块: <b>sudo apt install v4l2loopback-dkms</b>")
        info_label_2 = QLabel("2. 加载模块: <b>sudo modprobe v4l2loopback</b>")
        info_label_3 = QLabel("3. (可选) 解决兼容问题: <b>... exclusive_caps=1</b>")
        info_layout.addWidget(info_label_1)
        info_layout.addWidget(info_label_2)
        info_layout.addWidget(info_label_3)

        main_layout.addWidget(self.enable_v4l2_check)
        main_layout.addWidget(self.options_groupbox)
        main_layout.addWidget(info_group)
        main_layout.addStretch()
        self.setLayout(main_layout)

        self.toggle_options(False)
        self.log_emitter = None

    def set_log_emitter(self, log_emitter):
        """【核心修正】补上这个被遗漏的方法"""
        self.log_emitter = log_emitter

    def toggle_options(self, checked):
        self.options_groupbox.setEnabled(checked)

    def handle_list_devices(self):
        if not self.log_emitter: return
        self.log_emitter("\n--- 正在查找 V4L2 设备 ---")
        try:
            # 使用 find 命令，比 ls 更安全
            result = subprocess.run(['find', '/dev', '-name', 'video*'],
                                    capture_output=True, text=True, timeout=5)
            if result.returncode == 0 and result.stdout:
                self.log_emitter("找到以下设备:")
                self.log_emitter(result.stdout.strip())
            else:
                self.log_emitter("未找到 /dev/video* 设备。请确认您已加载 v4l2loopback 模块。")
        except Exception as e:
            self.log_emitter(f"查找设备时出错: {e}")

    def get_args(self):
        if not self.enable_v4l2_check.isChecked() or not sys.platform.startswith('linux'):
            return []

        args = []
        if sink_path := self.v4l2_sink_input.text().strip():
            args.extend(['--v4l2-sink', sink_path])
        else:
            if self.log_emitter:
                self.log_emitter("警告: 已启用 V4L2 Sink 但未提供设备路径。")

        if self.no_playback_check.isChecked():
            args.append('--no-video-playback')
        if buffer_val := self.v4l2_buffer_input.text().strip():
            args.extend(['--v4l2-buffer', buffer_val])

        return args