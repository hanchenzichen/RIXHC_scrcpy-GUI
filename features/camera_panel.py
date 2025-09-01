from PyQt6.QtWidgets import (QWidget, QVBoxLayout, QFormLayout, QLineEdit,
                             QComboBox, QCheckBox, QGroupBox, QPushButton, QHBoxLayout)
from PyQt6.QtCore import QThread
from core.command_runner import AdbWorker


class CameraPanel(QWidget):
    """
    【全新】摄像头设置面板
    根据官方 camera.md 文档实现所有摄像头相关选项。
    """

    def __init__(self):
        super().__init__()
        main_layout = QVBoxLayout()
        main_layout.setContentsMargins(10, 10, 10, 10)

        # --- 分组1: 摄像头选择 ---
        selection_group = QGroupBox("摄像头选择")
        selection_layout = QFormLayout()

        self.camera_id_input = QLineEdit()
        self.camera_id_input.setPlaceholderText("例如: 0 (可通过下方按钮列出)")

        self.camera_facing_combo = QComboBox()
        self.camera_facing_combo.addItems(["任意 (默认)", "front (前置)", "back (后置)", "external (外置)"])

        # 列表按钮
        list_button_layout = QHBoxLayout()
        self.list_cameras_button = QPushButton("列出摄像头ID")
        self.list_camera_sizes_button = QPushButton("列出支持的尺寸")
        list_button_layout.addWidget(self.list_cameras_button)
        list_button_layout.addWidget(self.list_camera_sizes_button)
        self.list_cameras_button.clicked.connect(lambda: self.run_list_command("--list-cameras"))
        self.list_camera_sizes_button.clicked.connect(lambda: self.run_list_command("--list-camera-sizes"))

        selection_layout.addRow("指定摄像头ID:", self.camera_id_input)
        selection_layout.addRow("或按朝向选择:", self.camera_facing_combo)
        selection_layout.addRow(list_button_layout)
        selection_group.setLayout(selection_layout)

        # --- 分组2: 尺寸与帧率 ---
        size_fps_group = QGroupBox("尺寸与帧率")
        size_fps_layout = QFormLayout()

        self.camera_size_input = QLineEdit()
        self.camera_size_input.setPlaceholderText("例如: 1920x1080")

        self.camera_ar_input = QLineEdit()
        self.camera_ar_input.setPlaceholderText("例如: 16:9, 1.77, 或 sensor")

        self.camera_fps_input = QLineEdit()
        self.camera_fps_input.setPlaceholderText("例如: 60 (默认 30)")

        size_fps_layout.addRow("指定尺寸:", self.camera_size_input)
        size_fps_layout.addRow("或指定宽高比:", self.camera_ar_input)
        size_fps_layout.addRow("指定帧率:", self.camera_fps_input)
        size_fps_group.setLayout(size_fps_layout)

        # --- 最终布局 ---
        main_layout.addWidget(selection_group)
        main_layout.addWidget(size_fps_group)
        main_layout.addStretch()
        self.setLayout(main_layout)

        self.log_emitter = None

    def set_log_emitter(self, log_emitter):
        self.log_emitter = log_emitter

    def run_list_command(self, command):
        """运行列出摄像头信息的命令，并将结果打印到日志"""
        if self.log_emitter:
            self.log_emitter(f"\n正在执行 scrcpy {command} ...")
            # 注意：这里我们简化处理，直接运行一个阻塞命令
            # 因为这个操作很快，且不需要复杂的线程管理
            try:
                # 构建一个基础的 scrcpy 命令
                cmd = ['scrcpy', command]
                result = subprocess.run(cmd, capture_output=True, text=True, timeout=10,
                                        encoding='utf-8', errors='replace')
                output = (result.stdout + "\n" + result.stderr).strip()
                self.log_emitter(output or "命令执行完毕，无输出。")
            except Exception as e:
                self.log_emitter(f"执行命令时出错: {e}")

    def get_args(self):
        args = []

        # ID 和朝向是互斥的
        if cam_id := self.camera_id_input.text().strip():
            args.extend(['--camera-id', cam_id])
        elif (facing := self.camera_facing_combo.currentText().split(' ')[0]) != "任意":
            args.extend(['--camera-facing', facing])

        # 尺寸和宽高比是互斥的
        if size := self.camera_size_input.text().strip():
            args.extend(['--camera-size', size])
        elif ar := self.camera_ar_input.text().strip():
            args.extend(['--camera-ar', ar])

        if fps := self.camera_fps_input.text().strip():
            args.extend(['--camera-fps', fps])

        return args


# 需要在文件顶部添加 import subprocess
import subprocess