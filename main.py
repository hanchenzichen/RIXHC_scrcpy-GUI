import os
import shlex
import sys

from PySide6.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
                             QPushButton, QTextEdit, QTabWidget, QLabel, QGroupBox, QScrollArea,
                             QRadioButton, QSplitter, QStyleFactory, QDialog, QPlainTextEdit)
from PySide6.QtCore import QThread, Qt
from PySide6.QtGui import QIcon

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
from features.registry_panel import RegistryPanel

try:
    from rix import __version__
except ImportError:  # 兼容直接以脚本方式运行（未安装 rix 包）
    __version__ = "dev"


def resource_path(name: str) -> str:
    """获取资源文件的绝对路径。

    打包成 exe 后资源被解包到 sys._MEIPASS；直接跑源码时资源就在本文件旁边。
    这样无论从哪个工作目录启动，图标都能正确加载。
    """
    base = getattr(sys, "_MEIPASS", None) or os.path.dirname(os.path.abspath(__file__))
    return os.path.join(base, name)


try:
    from rix.registry import dedupe_args
except ImportError:  # 兼容只拷贝了 main.py 与 features/ 的极简运行方式
    def dedupe_args(args):
        rendered = {}
        order = []
        for item in args:
            key = item.split('=', 1)[0]
            if key in rendered:
                order.remove(key)
            rendered[key] = item
            order.append(key)
        return [rendered[key] for key in order]


class ScrcpyMainMenu(QMainWindow):
    """
    Scrcpy 控制中心主窗口 (UI 优化最终版)。
    """

    def __init__(self):
        super().__init__()
        self.setWindowTitle(f'RIX-Scrcpy 控制中心 v{__version__} @hanchenzichen')
        self.setGeometry(200, 200, 700, 800)
        self.setWindowIcon(QIcon(resource_path('RIXHC.ico')))

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
        self.registry_panel = RegistryPanel()
        self.registry_panel.set_log_emitter(self.log)

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
        tabs.addTab(self.registry_panel, "全部参数")

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
        self.preview_button = QPushButton("🔍 预览命令")
        self.preview_button.setToolTip("查看将要执行的完整 scrcpy 命令行（方便排错与反馈问题）")
        self.start_button.clicked.connect(self.start_new_session)
        self.start_otg_button.clicked.connect(self.start_otg_session)
        self.preview_button.clicked.connect(self.preview_command)
        layout.addWidget(self.start_button)
        layout.addWidget(self.start_otg_button)
        layout.addWidget(self.preview_button)
        return group

    def connect_manager_signals(self):
        self.session_manager.log_signal.connect(self.log)
        self.session_manager.session_started.connect(self.add_session_to_ui)
        self.session_manager.session_stopped.connect(self.remove_session_from_ui)

    def on_source_changed(self, is_display_checked):
        is_camera_checked = not is_display_checked
        # 视频页签在摄像头模式下**保持可用**：码率/编码器/方向/裁剪对摄像头同样有意义。
        # 只禁用真正与 --video-source=camera 冲突的项（显示器 ID）。
        self.video_panel.set_camera_mode(is_camera_checked)
        self.tab_widget.setTabEnabled(self.tab_widget.indexOf(self.virtual_display_panel), is_display_checked)
        self.tab_widget.setTabEnabled(self.tab_widget.indexOf(self.camera_panel), is_camera_checked)
        if is_camera_checked:
            self.audio_panel.audio_source_combo.setCurrentText("mic (麦克风)")
        else:
            self.audio_panel.audio_source_combo.setCurrentText("output (内部声音, 默认)")

    def build_session_args(self, is_otg=False):
        """把界面上所有面板的设置拼装成 scrcpy 命令行参数。

        返回 (session_name_hint, cmd_args)；参数不合法时返回 (None, None)。
        预览与启动共用这一份逻辑，避免「预览的和实际执行的不一致」。
        """
        device_args = self.device_panel.get_args()
        if device_args is None:
            return None, None

        if '-d' in device_args:
            session_name_hint = "USB"
        elif '-e' in device_args:
            session_name_hint = "TCP/IP"
        else:
            session_name_hint = device_args[1]

        cmd_args = list(device_args)

        if is_otg:
            # OTG 模式只认设备选择 + 键鼠手柄，其余设置一律忽略
            if '--keyboard=disabled' in self.keyboard_panel.get_args():
                cmd_args.append('--keyboard=disabled')
            if '--mouse=disabled' in self.mouse_panel.get_args():
                cmd_args.append('--mouse=disabled')
            if '--gamepad=aoa' in self.gamepad_panel.get_args():
                cmd_args.append('--gamepad=aoa')
            return f"{session_name_hint}-OTG", dedupe_args(cmd_args)

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
        cmd_args.extend(self.registry_panel.get_args())
        return session_name_hint, dedupe_args(cmd_args)

    @staticmethod
    def format_command(cmd_args, is_otg=False):
        """把参数列表拼成一条可复制、可粘贴到终端的命令。"""
        base = ['scrcpy', '--otg'] if is_otg else ['scrcpy']
        return ' '.join(shlex.quote(a) for a in base + cmd_args)

    def preview_command(self):
        """显示将要执行的完整命令行（排错/反馈问题时非常有用）。"""
        lines = []
        _, mirror_args = self.build_session_args(is_otg=False)
        if mirror_args:
            lines.append("[镜像会话]")
            lines.append(self.format_command(mirror_args))
        _, otg_args = self.build_session_args(is_otg=True)
        if otg_args:
            lines.append("")
            lines.append("[OTG 模式]")
            lines.append(self.format_command(otg_args, is_otg=True))
        if not lines:
            return
        text = chr(10).join(lines)
        self.log("--- 命令预览 ---")
        for line in lines:
            if line:
                self.log(line)

        dlg = QDialog(self)
        dlg.setWindowTitle("命令预览")
        dlg.resize(780, 280)
        layout = QVBoxLayout(dlg)
        layout.addWidget(QLabel("将执行以下命令（可全选复制）："))
        edit = QPlainTextEdit(text)
        edit.setReadOnly(True)
        edit.setLineWrapMode(QPlainTextEdit.LineWrapMode.WidgetWidth)
        layout.addWidget(edit)
        buttons = QHBoxLayout()
        copy_btn = QPushButton("复制到剪贴板")
        copy_btn.clicked.connect(lambda: QApplication.clipboard().setText(text))
        close_btn = QPushButton("关闭")
        close_btn.clicked.connect(dlg.accept)
        buttons.addStretch()
        buttons.addWidget(copy_btn)
        buttons.addWidget(close_btn)
        layout.addLayout(buttons)
        dlg.exec()

    def start_new_session(self):
        session_name_hint, cmd_args = self.build_session_args(is_otg=False)
        if cmd_args is None:
            return
        self.session_manager.start_session(session_name_hint, cmd_args, is_otg=False)

    def start_otg_session(self):
        if self.device_panel.selection_mode == 'tcpip':
            # --otg 需要真实 USB 连接的设备，-e（唯一的 TCP/IP 设备）必然失败
            self.log("错误：OTG 模式需要 USB 连接的设备，不能使用『唯一的TCP/IP设备 (-e)』。")
            return
        session_name_hint, cmd_args = self.build_session_args(is_otg=True)
        if cmd_args is None:
            return
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
def main(argv=None):
    """GUI 入口（也作为 PyInstaller 与 console_scripts 的入口）。"""
    app = QApplication(sys.argv if argv is None else argv)
    app.setApplicationName("RIX Scrcpy GUI")
    app.setApplicationVersion(__version__)
    app.setStyle(QStyleFactory.create('Fusion'))
    window = ScrcpyMainMenu()
    window.show()
    return app.exec()


if __name__ == '__main__':
    sys.exit(main())
