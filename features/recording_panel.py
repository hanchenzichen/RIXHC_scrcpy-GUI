from PyQt6.QtWidgets import (QWidget, QVBoxLayout, QFormLayout, QLineEdit,
                             QComboBox, QCheckBox, QPushButton, QFileDialog, QHBoxLayout, QGroupBox)


class RecordingPanel(QWidget):
    """
    【终极版】录制设置面板
    根据官方 recording.md 文档实现所有录制相关选项。
    """

    def __init__(self):
        super().__init__()
        main_layout = QVBoxLayout()
        main_layout.setContentsMargins(10, 10, 10, 10)
        main_layout.setSpacing(10)

        # --- 分组1: 文件与格式 ---
        file_group = QGroupBox("文件、格式与时长")
        file_layout = QFormLayout(file_group)

        # 文件名输入和浏览按钮
        self.record_file_input = QLineEdit()
        self.record_file_input.setPlaceholderText("留空则不录制, 例如: my_video.mkv")

        file_browse_layout = QHBoxLayout()
        file_browse_layout.setContentsMargins(0, 0, 0, 0)
        file_browse_layout.addWidget(self.record_file_input, 1)  # 占据更多空间
        browse_button = QPushButton("浏览...")
        browse_button.clicked.connect(self.browse_file)
        file_browse_layout.addWidget(browse_button)

        # 录制格式 (容器)
        self.record_format_combo = QComboBox()
        self.record_format_combo.addItems([
            "自动 (根据文件名)",
            "mkv (Matroska)",
            "mp4 (MP4)",
            "opus (Opus 音频)",
            "flac (FLAC 音频)",
            "wav (WAV 音频)"
        ])
        self.record_format_combo.setToolTip(
            "明确指定容器格式。\n选择“自动”时，scrcpy会根据文件名后缀自动判断。"
        )

        # 录制时长限制
        self.time_limit_input = QLineEdit()
        self.time_limit_input.setPlaceholderText("例如: 60 (单位: 秒, 也可用于非录制模式)")

        file_layout.addRow("录制文件名:", file_browse_layout)
        file_layout.addRow("录制格式:", self.record_format_combo)
        file_layout.addRow("时长限制 (秒):", self.time_limit_input)

        # --- 分组2: 播放与显示选项 ---
        playback_group = QGroupBox("录制期间的播放与显示")
        playback_layout = QVBoxLayout(playback_group)

        self.no_playback_check = QCheckBox("录制时不进行镜像 (--no-playback)")
        self.no_playback_check.setToolTip("录制时禁用视频和音频的实时播放，但窗口可能仍然存在。")

        self.no_audio_playback_check = QCheckBox("录制时仅禁用音频播放 (--no-audio-playback)")

        self.no_window_check = QCheckBox("完全后台录制 (--no-window)")
        self.no_window_check.setToolTip(
            "终极后台录制模式。\n不显示任何窗口，录制结束后需要手动停止程序或等待时长限制结束。"
        )

        playback_layout.addWidget(self.no_playback_check)
        playback_layout.addWidget(self.no_audio_playback_check)
        playback_layout.addWidget(self.no_window_check)

        # --- 最终布局 ---
        main_layout.addWidget(file_group)
        main_layout.addWidget(playback_group)
        main_layout.addStretch()
        self.setLayout(main_layout)

    def browse_file(self):
        """打开文件对话框以选择保存路径"""
        file_filter = (
            "Matroska Video (*.mkv);;"
            "MP4 Video (*.mp4);;"
            "Opus Audio (*.opus);;"
            "FLAC Audio (*.flac);;"
            "WAV Audio (*.wav);;"
            "All Files (*)"
        )

        file_path, _ = QFileDialog.getSaveFileName(
            self, "保存录制文件", "", file_filter
        )
        if file_path:
            self.record_file_input.setText(file_path)

    def get_args(self):
        """获取该面板对应的 scrcpy 命令行参数"""
        args = []

        # 时长限制是通用选项，无论是否录制都可能生效
        if val := self.time_limit_input.text().strip():
            args.extend(['--time-limit', val])

        # 只有当用户输入了文件名时，才添加所有与录制直接相关的参数
        if filename := self.record_file_input.text().strip():
            args.extend(['--record', filename])

            # 格式
            format_text = self.record_format_combo.currentText().split(' ')[0].lower()
            # 只有当用户明确选择了格式时才添加参数
            if format_text != "自动":
                args.extend(['--record-format', format_text])

            # 播放与显示
            if self.no_playback_check.isChecked():
                args.append('--no-playback')

            if self.no_audio_playback_check.isChecked():
                args.append('--no-audio-playback')

            if self.no_window_check.isChecked():
                args.append('--no-window')

        return args