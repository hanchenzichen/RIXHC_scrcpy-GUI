import subprocess
from PyQt6.QtWidgets import (QWidget, QVBoxLayout, QFormLayout, QGroupBox,
                             QLineEdit, QComboBox, QCheckBox, QPushButton, QHBoxLayout)


class VideoPanel(QWidget):
    """
    【终极版】视频设置面板
    根据官方 video.md 文档实现所有视频相关选项。
    """

    def __init__(self):
        super().__init__()
        main_layout = QVBoxLayout()
        main_layout.setContentsMargins(10, 10, 10, 10)
        main_layout.setSpacing(10)

        # --- 分组1: 尺寸、码率与帧率 ---
        basic_group = QGroupBox("基础设置 (尺寸、码率、帧率)")
        basic_layout = QFormLayout(basic_group)
        self.max_size_input = QLineEdit()
        self.max_size_input.setPlaceholderText("例如: 1024 或 1920 (单位: 像素)")
        self.bitrate_input = QLineEdit()
        self.bitrate_input.setPlaceholderText("例如: 8M (默认), 2M, 2000K")
        self.max_fps_input = QLineEdit()
        self.max_fps_input.setPlaceholderText("例如: 30, 60")
        self.print_fps_check = QCheckBox("在控制台打印帧率 (--print-fps)")
        basic_layout.addRow("最大尺寸 (-m):", self.max_size_input)
        basic_layout.addRow("视频码率 (-b):", self.bitrate_input)
        basic_layout.addRow("最大帧率:", self.max_fps_input)
        basic_layout.addRow(self.print_fps_check)

        # --- 分组2: 编码与显示器 ---
        encoder_group = QGroupBox("编码与显示器")
        encoder_layout = QFormLayout(encoder_group)
        self.video_codec_combo = QComboBox()
        self.video_codec_combo.addItems(["h264 (默认)", "h265", "av1"])
        self.video_encoder_input = QLineEdit()
        self.video_encoder_input.setPlaceholderText("手动指定编码器名称")
        self.display_id_input = QLineEdit()
        self.display_id_input.setPlaceholderText("例如: 1 (可通过下方按钮列出)")

        list_buttons_layout = QHBoxLayout()
        self.list_encoders_button = QPushButton("列出编码器")
        self.list_displays_button = QPushButton("列出显示器")
        list_buttons_layout.addWidget(self.list_encoders_button)
        list_buttons_layout.addWidget(self.list_displays_button)
        self.list_encoders_button.clicked.connect(lambda: self.run_list_command("--list-encoders"))
        self.list_displays_button.clicked.connect(lambda: self.run_list_command("--list-displays"))

        encoder_layout.addRow("视频编码器:", self.video_codec_combo)
        encoder_layout.addRow("指定编码器名称:", self.video_encoder_input)
        encoder_layout.addRow("指定显示器ID:", self.display_id_input)
        encoder_layout.addRow(list_buttons_layout)

        # --- 分组3: 方向、裁剪与缓冲 ---
        transform_group = QGroupBox("方向、裁剪与缓冲")
        transform_layout = QFormLayout(transform_group)
        self.orientation_combo = QComboBox()
        self.orientation_combo.addItems(["默认", "0", "90", "180", "270", "flip0", "flip90", "flip180", "flip270"])
        self.crop_input = QLineEdit()
        self.crop_input.setPlaceholderText("格式: width:height:x:y")
        self.video_buffer_input = QLineEdit()
        self.video_buffer_input.setPlaceholderText("例如: 50 (单位: 毫秒)")

        transform_layout.addRow("客户端渲染方向:", self.orientation_combo)
        transform_layout.addRow("裁剪画面:", self.crop_input)
        transform_layout.addRow("视频播放缓冲区(ms):", self.video_buffer_input)

        # --- 分组4: 播放控制 ---
        playback_group = QGroupBox("播放控制")
        playback_layout = QVBoxLayout(playback_group)
        self.no_playback_check = QCheckBox("不播放音视频 (用于录制或V4L2)")
        self.no_video_playback_check = QCheckBox("不播放视频 (但保留音频)")
        self.no_audio_playback_check = QCheckBox("不播放音频 (但保留视频)")
        playback_layout.addWidget(self.no_playback_check)
        playback_layout.addWidget(self.no_video_playback_check)
        playback_layout.addWidget(self.no_audio_playback_check)

        # --- 最终布局 ---
        main_layout.addWidget(basic_group)
        main_layout.addWidget(encoder_group)
        main_layout.addWidget(transform_group)
        main_layout.addWidget(playback_group)
        main_layout.addStretch()
        self.setLayout(main_layout)

        self.log_emitter = None

    def set_log_emitter(self, log_emitter):
        self.log_emitter = log_emitter

    def run_list_command(self, command):
        """运行列出信息的命令，并将结果打印到日志"""
        if not self.log_emitter: return
        self.log_emitter(f"\n--- 正在执行 scrcpy {command} ---")
        try:
            cmd = ['scrcpy', command]
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=10,
                                    encoding='utf-8', errors='replace')
            output = (result.stdout + "\n" + result.stderr).strip()
            self.log_emitter(output or "命令执行完毕，无输出。")
        except Exception as e:
            self.log_emitter(f"执行命令时出错: {e}")

    def get_args(self):
        """获取该面板对应的 scrcpy 命令行参数"""
        args = []

        if val := self.max_size_input.text().strip():
            args.extend(['--max-size', val])
        if val := self.bitrate_input.text().strip():
            args.extend(['--video-bit-rate', val])
        if val := self.max_fps_input.text().strip():
            args.extend(['--max-fps', val])
        if self.print_fps_check.isChecked():
            args.append('--print-fps')

        codec = self.video_codec_combo.currentText().split(' ')[0]
        if codec != "h264":  # h264是默认值
            args.extend(['--video-codec', codec])
        if val := self.video_encoder_input.text().strip():
            args.extend(['--video-encoder', val])
        if val := self.display_id_input.text().strip():
            args.extend(['--display-id', val])

        orientation = self.orientation_combo.currentText()
        if orientation != "默认":
            args.extend(['--orientation', orientation])
        if val := self.crop_input.text().strip():
            args.extend(['--crop', val])
        if val := self.video_buffer_input.text().strip():
            args.extend(['--video-buffer', val])

        if self.no_playback_check.isChecked():
            args.append('--no-playback')
        if self.no_video_playback_check.isChecked():
            args.append('--no-video-playback')
        if self.no_audio_playback_check.isChecked():
            args.append('--no-audio-playback')

        return args