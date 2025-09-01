import sys
from PyQt6.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
                             QPushButton, QTextEdit, QTabWidget, QLabel, QGroupBox, QScrollArea,
                             QRadioButton, QSplitter, QStyleFactory)
from PyQt6.QtCore import QThread, Qt
from PyQt6.QtGui import QIcon

# -----------------------------------------------------------------------------
# 导入所有核心与功能模块
# -----------------------------------------------------------------------------
from core.session_manager import SessionManager
from features.device_panel import DevicePanel
from features.audio_panel import AudioPanel
from features.video_panel import VideoPanel
from features.camera_panel import CameraPanel
from features.keyboard_panel import KeyboardPanel
from features.mouse_panel import MousePanel
from features.gamepad_panel import GamepadPanel
from features.recording_panel import RecordingPanel
from features.control_panel import ControlPanel
from features.window_panel import WindowPanel
from features.shortcuts_panel import ShortcutsPanel
from features.virtual_display_panel import VirtualDisplayPanel
from features.v4l2_panel import V4l2Panel
from features.developer_panel import DeveloperPanel


class ScrcpyMainMenu(QMainWindow):
    """
    Scrcpy 控制中心主窗口 (UI 优化最终版)。
    """

    def __init__(self):
        super().__init__()
        self.setWindowTitle('RIX_Scrcpy 控制中心@hanchenzichen')
        self.setGeometry(200, 200, 700, 800)
        self.setWindowIcon(QIcon('RIXHC.ico'))

        self.session_manager = SessionManager()
        self.initUI()
        self.connect_manager_signals()
        self.device_panel.refresh_devices()

    def initUI(self):
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QVBoxLayout(central_widget)
        main_layout.setContentsMargins(10, 10, 10, 10)
        main_layout.setSpacing(10)

        main_splitter = QSplitter(Qt.Orientation.Horizontal)

        left_widget = QWidget()
        left_layout = QVBoxLayout(left_widget)
        left_layout.setContentsMargins(0, 0, 0, 0)

        self.device_panel = self._create_device_panel()
        self.source_group = self._create_source_panel()
        self.tab_widget = self._create_tabs_panel()

        left_layout.addWidget(self.device_panel)
        left_layout.addWidget(self.source_group)
        left_layout.addWidget(self.tab_widget, 1)

        right_widget = QWidget()
        right_layout = QVBoxLayout(right_widget)
        right_layout.setContentsMargins(0, 0, 0, 0)

        right_splitter = QSplitter(Qt.Orientation.Vertical)
        self.session_group = self._create_session_panel()
        self.log_group = self._create_log_panel()

        right_splitter.addWidget(self.session_group)
        right_splitter.addWidget(self.log_group)
        right_splitter.setSizes([300, 500])
        right_layout.addWidget(right_splitter)

        main_splitter.addWidget(left_widget)
        main_splitter.addWidget(right_widget)
        main_splitter.setSizes([350, 350])

        control_group = self._create_control_panel()

        main_layout.addWidget(main_splitter, 1)
        main_layout.addWidget(control_group)

        self.on_source_changed(True)

    def _create_device_panel(self):
        panel = DevicePanel()
        panel.set_log_emitter(self.log)
        return panel

    def _create_source_panel(self):
        group = QGroupBox("视频源")
        layout = QHBoxLayout(group)
        self.source_display_radio = QRadioButton("手机屏幕")
        self.source_camera_radio = QRadioButton("摄像头")
        self.source_display_radio.setChecked(True)
        layout.addWidget(self.source_display_radio)
        layout.addWidget(self.source_camera_radio)
        self.source_display_radio.toggled.connect(self.on_source_changed)
        return group

    def _create_tabs_panel(self):
        tabs = QTabWidget()
        self.audio_panel = AudioPanel()
        self.video_panel = VideoPanel()
        self.camera_panel = CameraPanel()
        self.camera_panel.set_log_emitter(self.log)
        self.keyboard_panel = KeyboardPanel()
        self.mouse_panel = MousePanel()
        self.gamepad_panel = GamepadPanel()
        self.recording_panel = RecordingPanel()
        self.control_panel = ControlPanel()
        self.window_panel = WindowPanel()
        self.shortcuts_panel = ShortcutsPanel()
        self.virtual_display_panel = VirtualDisplayPanel()
        self.virtual_display_panel.set_log_emitter(self.log)
        self.v4l2_panel = V4l2Panel()
        self.v4l2_panel.set_log_emitter(self.log)
        self.developer_panel = DeveloperPanel()
        self.developer_panel.set_log_emitter(self.log)

        tabs.addTab(self.audio_panel, "音频")
        tabs.addTab(self.video_panel, "视频")
        tabs.addTab(self.camera_panel, "摄像头")
        tabs.addTab(self.recording_panel, "录制")
        tabs.addTab(self.control_panel, "控制")
        tabs.addTab(self.keyboard_panel, "键盘")
        tabs.addTab(self.mouse_panel, "鼠标")
        tabs.addTab(self.gamepad_panel, "游戏手柄")
        tabs.addTab(self.window_panel, "窗口")
        tabs.addTab(self.shortcuts_panel, "快捷键")
        tabs.addTab(self.virtual_display_panel, "虚拟显示")
        tabs.addTab(self.v4l2_panel, "V4L2")
        tabs.addTab(self.developer_panel, "开发者")

        if not sys.platform.startswith('linux'):
            v4l2_index = tabs.indexOf(self.v4l2_panel)
            tabs.setTabEnabled(v4l2_index, False)
            tabs.setTabToolTip(v4l2_index, "此功能仅在 Linux 操作系统上可用")

        return tabs

    def _create_session_panel(self):
        group = QGroupBox("活动会话")
        layout = QVBoxLayout(group)
        self.session_list_layout = QVBoxLayout()
        self.session_list_layout.setContentsMargins(5, 5, 5, 5)
        self.session_list_layout.setSpacing(5)
        self.session_list_layout.addStretch()
        self.session_list_widget = QWidget()
        self.session_list_widget.setLayout(self.session_list_layout)
        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setWidget(self.session_list_widget)
        layout.addWidget(scroll_area)
        return group

    def _create_log_panel(self):
        group = QGroupBox("日志输出")
        layout = QVBoxLayout(group)
        self.log_output = QTextEdit()
        self.log_output.setReadOnly(True)
        layout.addWidget(self.log_output)
        return group

    def _create_control_panel(self):
        group = QGroupBox("启动控制")
        layout = QHBoxLayout(group)
        self.start_button = QPushButton("🚀 启动镜像会话")
        self.start_otg_button = QPushButton("🎮 启动 OTG 模式")
        self.start_button.clicked.connect(self.start_new_session)
        self.start_otg_button.clicked.connect(self.start_otg_session)
        layout.addWidget(self.start_button)
        layout.addWidget(self.start_otg_button)
        return group

    def connect_manager_signals(self):
        self.session_manager.log_signal.connect(self.log)
        self.session_manager.session_started.connect(self.add_session_to_ui)
        self.session_manager.session_stopped.connect(self.remove_session_from_ui)

    def on_source_changed(self, is_display_checked):
        is_camera_checked = not is_display_checked
        self.tab_widget.setTabEnabled(self.tab_widget.indexOf(self.video_panel), is_display_checked)
        self.tab_widget.setTabEnabled(self.tab_widget.indexOf(self.virtual_display_panel), is_display_checked)
        self.tab_widget.setTabEnabled(self.tab_widget.indexOf(self.camera_panel), is_camera_checked)
        if is_camera_checked:
            self.audio_panel.audio_source_combo.setCurrentText("mic (麦克风)")
        else:
            self.audio_panel.audio_source_combo.setCurrentText("output (内部声音, 默认)")

    def start_new_session(self):
        device_args = self.device_panel.get_args()
        if device_args is None: return
        if '-d' in device_args:
            session_name_hint = "USB"
        elif '-e' in device_args:
            session_name_hint = "TCP/IP"
        else:
            session_name_hint = device_args[1]
        cmd_args = list(device_args)
        if self.source_camera_radio.isChecked():
            cmd_args.append('--video-source=camera')
            cmd_args.extend(self.camera_panel.get_args())
            if max_size := self.video_panel.max_size_input.text().strip():
                cmd_args.extend(['--max-size', max_size])
        else:
            cmd_args.extend(self.video_panel.get_args())
            cmd_args.extend(self.virtual_display_panel.get_args())
        cmd_args.extend(self.audio_panel.get_args())
        cmd_args.extend(self.recording_panel.get_args())
        cmd_args.extend(self.control_panel.get_args())
        cmd_args.extend(self.window_panel.get_args())
        cmd_args.extend(self.shortcuts_panel.get_args())
        cmd_args.extend(self.v4l2_panel.get_args())
        cmd_args.extend(self.developer_panel.get_args())
        cmd_args.extend(self.gamepad_panel.get_args())
        cmd_args.extend(self.keyboard_panel.get_args())
        cmd_args.extend(self.mouse_panel.get_args())
        self.session_manager.start_session(session_name_hint, cmd_args, is_otg=False)

    def start_otg_session(self):
        device_args = self.device_panel.get_args()
        if device_args is None: return
        if '-d' in device_args:
            session_name_hint = "USB-OTG"
        elif '-e' in device_args:
            session_name_hint = "TCP-OTG"
        else:
            session_name_hint = f"{device_args[1]}-OTG"
        cmd_args = list(device_args)
        keyboard_args = self.keyboard_panel.get_args()
        if '--keyboard=disabled' in keyboard_args: cmd_args.append('--keyboard=disabled')
        mouse_args = self.mouse_panel.get_args()
        if '--mouse=disabled' in mouse_args: cmd_args.append('--mouse=disabled')
        gamepad_args = self.gamepad_panel.get_args()
        if '--gamepad=aoa' in gamepad_args: cmd_args.append('--gamepad=aoa')
        self.log("注意：OTG 模式将忽略除设备选择、键鼠手柄之外的所有设置。")
        self.session_manager.start_session(session_name_hint, cmd_args, is_otg=True)

    def add_session_to_ui(self, session_id: str, device_id_hint: str):
        widget = QWidget()
        h_layout = QHBoxLayout(widget)
        h_layout.setContentsMargins(5, 5, 5, 5)
        label = QLabel(f"[{session_id}] 设备: {device_id_hint}")
        stop_btn = QPushButton("停止")
        stop_btn.setFixedSize(60, 25)
        stop_btn.clicked.connect(lambda: self.session_manager.stop_session(session_id))
        h_layout.addWidget(label)
        h_layout.addStretch()
        h_layout.addWidget(stop_btn)
        widget.setObjectName(session_id)
        self.session_list_layout.insertWidget(self.session_list_layout.count() - 1, widget)
        self.log(f"UI添加会话显示: {session_id}")

    def remove_session_from_ui(self, session_id: str):
        widget_to_remove = self.session_list_widget.findChild(QWidget, session_id)
        if widget_to_remove:
            self.session_list_layout.removeWidget(widget_to_remove)
            widget_to_remove.deleteLater()
            self.log(f"UI移除会话显示: {session_id}")

    def log(self, message: str):
        self.log_output.append(message.strip())
        self.log_output.verticalScrollBar().setValue(self.log_output.verticalScrollBar().maximum())

    def closeEvent(self, event):
        self.log("正在关闭应用程序，清理所有活动会话...")
        self.session_manager.stop_all_sessions()
        event.accept()


# -----------------------------------------------------------------------------
# 程序主入口
# -----------------------------------------------------------------------------
if __name__ == '__main__':
    app = QApplication(sys.argv)
    app.setStyle(QStyleFactory.create('Fusion'))
    main_menu = ScrcpyMainMenu()
    main_menu.show()
    sys.exit(app.exec())