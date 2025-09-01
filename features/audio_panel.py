from PyQt6.QtWidgets import (QWidget, QVBoxLayout, QFormLayout, QLineEdit,
                             QComboBox, QCheckBox, QGroupBox, QLabel)
from PyQt6.QtCore import Qt


class AudioPanel(QWidget):
    """
    音频设置面板 (完整版)
    根据官方 audio.md 文档实现所有音频相关选项。
    """

    def __init__(self):
        super().__init__()
        main_layout = QVBoxLayout()
        main_layout.setContentsMargins(10, 10, 10, 10)

        # --- 主控制 ---
        self.enable_audio_check = QCheckBox("转发音频 (需要 Android 11+)")
        self.enable_audio_check.setChecked(True)  # 默认开启
        self.enable_audio_check.toggled.connect(self.toggle_all_options)

        self.audio_only_check = QCheckBox("仅音频模式 (--no-video --no-control)")
        self.audio_only_check.setToolTip(
            "勾选此项可禁用视频和控制，仅转发音频。\n"
            "适合将手机用作麦克风或听音乐。"
        )

        # --- 基本选项 ---
        self.basic_options_group = QGroupBox("基本音频选项")
        basic_layout = QFormLayout()

        self.audio_source_combo = QComboBox()
        self.audio_source_combo.addItems([
            "output (内部声音, 默认)",
            "playback (应用声音, A13+)",
            "mic (麦克风)",
            "mic-unprocessed (未处理麦克风)",
            "mic-camcorder (摄像机麦克风)",
            "mic-voice-recognition (语音识别麦克风)",
            "mic-voice-communication (语音通信麦克风)",
            "voice-call (语音通话)",
            "voice-call-uplink (通话上行)",
            "voice-call-downlink (通话下行)",
            "voice-performance (现场表演)"
        ])

        self.audio_dup_check = QCheckBox("在电脑和手机上同时播放")
        self.audio_dup_check.setToolTip(
            "需要 Android 13+ 且音频源为 'playback'。\n"
            "勾选此项会自动设置音频源。"
        )

        self.audio_codec_combo = QComboBox()
        self.audio_codec_combo.addItems([
            "opus (默认)",
            "aac",
            "flac",
            "raw (未压缩)"
        ])

        self.audio_bitrate_input = QLineEdit()
        self.audio_bitrate_input.setPlaceholderText("例如: 128K (默认 128kbps)")

        basic_layout.addRow("音频源:", self.audio_source_combo)
        basic_layout.addRow(self.audio_dup_check)
        basic_layout.addRow("音频编解码器:", self.audio_codec_combo)
        basic_layout.addRow("音频码率:", self.audio_bitrate_input)
        self.basic_options_group.setLayout(basic_layout)

        # --- 高级/缓冲选项 ---
        self.advanced_options_group = QGroupBox("高级与缓冲选项")
        advanced_layout = QFormLayout()

        self.audio_buffer_input = QLineEdit()
        self.audio_buffer_input.setPlaceholderText("例如: 50 (默认 50ms)")

        self.audio_output_buffer_input = QLineEdit()
        self.audio_output_buffer_input.setPlaceholderText("例如: 5 (默认 5ms, 谨慎修改)")

        self.audio_encoder_input = QLineEdit()
        self.audio_encoder_input.setPlaceholderText("指定编码器名称, 如 c2.android.opus.encoder")

        self.audio_codec_options_input = QLineEdit()
        self.audio_codec_options_input.setPlaceholderText("key=value,key2=value2...")

        advanced_layout.addRow("音频缓冲区 (ms):", self.audio_buffer_input)
        advanced_layout.addRow("音频输出缓冲区 (ms):", self.audio_output_buffer_input)
        advanced_layout.addRow(QLabel("---"))
        advanced_layout.addRow("指定音频编码器:", self.audio_encoder_input)
        advanced_layout.addRow("编码器参数:", self.audio_codec_options_input)
        self.advanced_options_group.setLayout(advanced_layout)

        # --- 布局 ---
        main_layout.addWidget(self.enable_audio_check)
        main_layout.addWidget(self.audio_only_check)
        main_layout.addWidget(self.basic_options_group)
        main_layout.addWidget(self.advanced_options_group)
        main_layout.addStretch()
        self.setLayout(main_layout)

        # 初始化UI状态
        self.toggle_all_options(self.enable_audio_check.isChecked())

    def toggle_all_options(self, checked):
        """根据主复选框的状态来启用或禁用所有相关选项"""
        self.audio_only_check.setEnabled(checked)
        self.basic_options_group.setEnabled(checked)
        self.advanced_options_group.setEnabled(checked)

    def get_args(self):
        """获取该面板对应的 scrcpy 命令行参数"""
        if not self.enable_audio_check.isChecked():
            return ['--no-audio']

        args = []

        if self.audio_only_check.isChecked():
            args.extend(['--no-video', '--no-control'])

        # 音频复制 (--audio-dup) 优先，因为它会隐含音频源
        if self.audio_dup_check.isChecked():
            args.append('--audio-dup')
        else:
            source_text = self.audio_source_combo.currentText().split(' ')[0]
            if source_text != "output":  # output 是默认值
                args.extend(['--audio-source', source_text])

        codec_text = self.audio_codec_combo.currentText().split(' ')[0]
        if codec_text != "opus":  # opus 是默认值
            args.extend(['--audio-codec', codec_text])

        if val := self.audio_bitrate_input.text().strip():
            args.extend(['--audio-bit-rate', val])

        if val := self.audio_buffer_input.text().strip():
            args.extend(['--audio-buffer', val])

        if val := self.audio_output_buffer_input.text().strip():
            args.extend(['--audio-output-buffer', val])

        if val := self.audio_encoder_input.text().strip():
            args.extend(['--audio-encoder', val])

        if val := self.audio_codec_options_input.text().strip():
            args.extend(['--audio-codec-options', val])

        return args