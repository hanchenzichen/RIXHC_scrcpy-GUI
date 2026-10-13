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


# 日志面板保留的最大行数（环形缓冲）
LOG_MAX_LINES = 5000


PANEL_SPECS = (
    # (内部名, 页签标题, 构造工厂)
    ("audio", "音频", AudioPanel),
    ("video", "视频", VideoPanel),
    ("camera", "摄像头", CameraPanel),
    ("recording", "录制", RecordingPanel),
    ("control", "控制", ControlPanel),
    ("keyboard", "键盘", KeyboardPanel),
    ("mouse", "鼠标", MousePanel),
    ("gamepad", "游戏手柄", GamepadPanel),
    ("window", "窗口", WindowPanel),
    ("shortcuts", "快捷键", ShortcutsPanel),
    ("virtual_display", "虚拟显示", VirtualDisplayPanel),
    ("v4l2", "V4L2", V4l2Panel),
    ("developer", "开发者", DeveloperPanel),
    ("registry", "全部参数", RegistryPanel),
)

# 面板按此顺序拼装命令行，保证结果稳定可复现
PANEL_ARG_ORDER = (
    "video", "virtual_display", "audio", "recording", "control",
    "window", "shortcuts", "v4l2", "developer", "gamepad", "keyboard", "mouse",
    "registry",
)


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
        # 面板按需构建：启动时只建第一个页签，切到哪个才建哪个
        self._panels = {}
        self._tab_names = []
        self._panel_factories = {}
        self._tab_layouts = {}
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
        for name, title, factory in PANEL_SPECS:
            container = QWidget()
            layout = QVBoxLayout(container)
            layout.setContentsMargins(0, 0, 0, 0)
            tabs.addTab(container, title)
            self._tab_names.append(name)
            self._panel_factories[name] = factory
            self._tab_layouts[name] = layout
        tabs.currentChanged.connect(self._on_tab_changed)

        if not sys.platform.startswith('linux'):
            v4l2_index = self._tab_names.index('v4l2')
            tabs.setTabEnabled(v4l2_index, False)
            tabs.setTabToolTip(v4l2_index, "此功能仅在 Linux 操作系统上可用")

        self._ensure_panel(0)
        return tabs

    def _on_tab_changed(self, index: int):
        self._ensure_panel(index)

    def _ensure_panel(self, index: int):
        """首次显示某个页签时才构建对应面板，降低启动时间与常驻内存。"""
        if index < 0 or index >= len(self._tab_names):
            return None
        name = self._tab_names[index]
        if name in self._panels:
            return self._panels[name]
        panel = self._panel_factories[name]()
        if hasattr(panel, 'set_log_emitter'):
            panel.set_log_emitter(self.log)
        self._tab_layouts[name].addWidget(panel)
        self._panels[name] = panel
        self._apply_panel_state(name, panel)
        return panel

    def panel(self, name: str):
        """取得已构建的面板；未构建时返回 None（视为未做任何设置）。"""
        return self._panels.get(name)

    def ensure_all_panels(self):
        """强制构建全部面板（无头自检等场景使用）。"""
        for index in range(len(self._tab_names)):
            self._ensure_panel(index)

    def _apply_panel_state(self, name: str, panel):
        """面板构建后同步一次全局状态（例如摄像头模式）。"""
        if name in ('video', 'registry') and hasattr(panel, 'set_camera_mode'):
            panel.set_camera_mode(self.source_camera_radio.isChecked())

    def _panel_args(self, name: str):
        """未构建的面板没有任何设置，返回空列表。"""
        panel = self._panels.get(name)
        return panel.get_args() if panel is not None else []

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
        # 用 QPlainTextEdit 而不是 QTextEdit：日志场景性能更好，
        # 且支持 setMaximumBlockCount —— 相当于环形缓冲，
        # 避免长时间运行时日志无限增长吃内存。
        self.log_output = QPlainTextEdit()
        self.log_output.setReadOnly(True)
        self.log_output.setMaximumBlockCount(LOG_MAX_LINES)
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
        # 视频页签在摄像头模式下保持可用：码率/编码器/方向/裁剪对摄像头同样有意义，
        # 只禁用真正与 --video-source=camera 冲突的项（显示器 ID）。
        for name in ('video', 'registry'):
            panel = self._panels.get(name)
            if panel is not None and hasattr(panel, 'set_camera_mode'):
                panel.set_camera_mode(is_camera_checked)
        self.tab_widget.setTabEnabled(self._tab_names.index('virtual_display'), is_display_checked)
        self.tab_widget.setTabEnabled(self._tab_names.index('camera'), is_camera_checked)
        audio = self._panels.get('audio')
        if audio is not None:
            audio.audio_source_combo.setCurrentText(
                "mic (麦克风)" if is_camera_checked else "output (内部声音, 默认)")

    def build_session_args(self, is_otg=False):
        """把界面上所有面板的设置拼装成 scrcpy 命令行参数。

        返回 (session_name_hint, cmd_args)；参数不合法时返回 (None, None)。
        预览与启动共用这一份逻辑，避免「预览的和实际执行的不一致」。
        未构建的面板（用户没打开过）视为未做任何设置。
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
            if '--keyboard=disabled' in self._panel_args('keyboard'):
                cmd_args.append('--keyboard=disabled')
            if '--mouse=disabled' in self._panel_args('mouse'):
                cmd_args.append('--mouse=disabled')
            if '--gamepad=aoa' in self._panel_args('gamepad'):
                cmd_args.append('--gamepad=aoa')
            return f"{session_name_hint}-OTG", dedupe_args(cmd_args)

        if self.source_camera_radio.isChecked():
            cmd_args.append('--video-source=camera')
            cmd_args.extend(self._panel_args('camera'))
            video_panel = self._panels.get('video')
            if video_panel is not None:
                max_size = video_panel.max_size_input.text().strip()
                if max_size:
                    cmd_args.extend(['--max-size', max_size])
        for name in PANEL_ARG_ORDER:
            if name == 'camera':
                continue
            cmd_args.extend(self._panel_args(name))
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
        self.log_output.appendPlainText(message.strip())
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
