import json
import os
from PyQt6.QtWidgets import (QWidget, QVBoxLayout, QFormLayout, QLineEdit,
                             QComboBox, QCheckBox, QGroupBox, QPushButton, QHBoxLayout, QCompleter, QLabel)
from PyQt6.QtCore import QThread, Qt, QStandardPaths
from core.command_runner import AdbWorker


class VirtualDisplayPanel(QWidget):
    """
    【体验优化版】虚拟显示面板
    将分辨率和DPI拆分，并增强了UI逻辑联动。
    """

    def __init__(self):
        super().__init__()

        # 定义缓存文件路径
        cache_dir = QStandardPaths.writableLocation(QStandardPaths.StandardLocation.CacheLocation)
        app_cache_dir = os.path.join(cache_dir, 'scrcpy-gui-cache')
        os.makedirs(app_cache_dir, exist_ok=True)
        self.cache_file = os.path.join(app_cache_dir, 'app_list.json')

        # 统一的 UI 初始化
        self.initUI()

        self.toggle_options(False)
        self.log_emitter = None
        self.full_app_list_data = []
        self.thread = None
        self.worker = None

        # 程序启动时，尝试从缓存加载
        self.load_app_list_from_cache()

    def initUI(self):
        """构建此面板的所有UI组件"""
        main_layout = QVBoxLayout()
        main_layout.setContentsMargins(10, 10, 10, 10)

        self.enable_vd_check = QCheckBox("启用新的虚拟显示")
        self.enable_vd_check.toggled.connect(self.toggle_options)

        self.options_groupbox = QGroupBox("虚拟显示与启动应用选项")
        options_layout = QFormLayout()

        # 分辨率和DPI
        resolution_layout = QHBoxLayout()
        resolution_layout.setContentsMargins(0, 0, 0, 0)
        self.vd_resolution_input = QLineEdit()
        self.vd_resolution_input.setPlaceholderText("例如: 1920x1080")
        self.vd_dpi_input = QLineEdit()
        self.vd_dpi_input.setPlaceholderText("例如: 420")
        resolution_layout.addWidget(self.vd_resolution_input, 2)
        resolution_layout.addWidget(QLabel("DPI:"))
        resolution_layout.addWidget(self.vd_dpi_input, 1)

        # 启动应用
        self.start_app_combo = QComboBox()
        self.start_app_combo.setEditable(True)
        self.start_app_combo.setPlaceholderText("输入应用名或包名进行筛选...")
        self.start_app_combo.lineEdit().setClearButtonEnabled(True)

        self.completer = QCompleter(self)
        self.completer.setCaseSensitivity(Qt.CaseSensitivity.CaseInsensitive)
        self.completer.setFilterMode(Qt.MatchFlag.MatchContains)
        self.start_app_combo.setCompleter(self.completer)

        self.get_apps_button = QPushButton("获取应用列表")
        self.get_apps_button.clicked.connect(self.fetch_app_list)

        app_layout = QHBoxLayout()
        app_layout.setContentsMargins(0, 0, 0, 0)
        app_layout.addWidget(self.start_app_combo, 1)
        app_layout.addWidget(self.get_apps_button)

        self.force_stop_app_check = QCheckBox("启动前强制停止 (+)")
        self.search_by_name_check = QCheckBox("按应用名搜索 (?)")
        self.search_by_name_check.setToolTip("勾选后，将使用 ?<文本> 的方式启动应用")

        app_options_layout = QHBoxLayout()
        app_options_layout.addWidget(self.force_stop_app_check)
        app_options_layout.addWidget(self.search_by_name_check)

        # 其他虚拟显示选项
        self.no_decorations_check = QCheckBox("禁用系统装饰")
        self.no_decorations_check.setToolTip("禁用后，必须通过下方选项启动一个App，否则屏幕将是黑的。")
        self.no_decorations_check.toggled.connect(self.on_no_decorations_toggled)

        self.no_destroy_check = QCheckBox("关闭时不销毁内容")
        self.ime_policy_combo = QComboBox()
        self.ime_policy_combo.addItems(["默认", "local (输入法显示在虚拟屏幕)"])
        self.ime_policy_combo.setToolTip("此策略也适用于通过 --display-id 选择的物理显示器。")

        options_layout.addRow("分辨率/DPI:", resolution_layout)
        options_layout.addRow("启动应用:", app_layout)
        options_layout.addRow(app_options_layout)
        options_layout.addRow(self.no_decorations_check)
        options_layout.addRow(self.no_destroy_check)
        options_layout.addRow("输入法策略:", self.ime_policy_combo)

        self.options_groupbox.setLayout(options_layout)
        main_layout.addWidget(self.enable_vd_check)
        main_layout.addWidget(self.options_groupbox)
        main_layout.addStretch()
        self.setLayout(main_layout)

    def set_log_emitter(self, log_emitter):
        self.log_emitter = log_emitter

    def load_app_list_from_cache(self):
        if os.path.exists(self.cache_file):
            try:
                with open(self.cache_file, 'r', encoding='utf-8') as f:
                    cached_data = json.load(f)
                if cached_data:
                    self.populate_app_list(cached_data, from_cache=True)
                    if self.log_emitter:
                        self.log_emitter(f"已从缓存加载 {len(cached_data)} 个应用。")
            except (json.JSONDecodeError, IOError):
                if self.log_emitter:
                    self.log_emitter("缓存文件已损坏，请重新获取。")

    def run_adb_task(self, command_name, log_message):
        if self.log_emitter: self.log_emitter(log_message)
        self.get_apps_button.setEnabled(False)
        self.get_apps_button.setText("获取中...")

        self.thread = QThread()
        self.worker = AdbWorker()
        self.worker.moveToThread(self.thread)
        self.worker.command_finished_signal.connect(self.log_emitter)

        if command_name == 'list_packages_with_names':
            self.worker.packages_listed_signal.connect(self.populate_app_list)

        self.thread.started.connect(getattr(self.worker, command_name))
        self.thread.finished.connect(self.thread.deleteLater)
        self.thread.finished.connect(self.worker.deleteLater)
        self.thread.finished.connect(lambda: self.get_apps_button.setEnabled(True))

        self.thread.start()

    def fetch_app_list(self):
        self.run_adb_task('list_packages_with_names', "正在后台获取应用列表 (首次加载可能需要数分钟)...")

    def populate_app_list(self, app_list_data, from_cache=False):
        self.full_app_list_data = app_list_data
        display_list = [f"{app['name']} ({app['package']})" for app in app_list_data]

        current_text = self.start_app_combo.currentText()
        self.start_app_combo.clear()
        self.start_app_combo.addItems(display_list)
        self.start_app_combo.lineEdit().setText(current_text)
        self.completer.setModel(self.start_app_combo.model())

        if not from_cache:
            try:
                with open(self.cache_file, 'w', encoding='utf-8') as f:
                    json.dump(app_list_data, f, ensure_ascii=False, indent=2)
                if self.log_emitter:
                    self.log_emitter("应用列表已成功缓存到本地。")
            except IOError:
                if self.log_emitter:
                    self.log_emitter("警告：无法写入应用列表缓存文件。")

        self.get_apps_button.setText("刷新列表")

        if not from_cache and self.thread:
            self.thread.quit()

    def on_no_decorations_toggled(self, checked):
        if checked:
            self.start_app_combo.setPlaceholderText("必须启动一个应用！(如桌面启动器)")
        else:
            self.start_app_combo.setPlaceholderText("输入应用名或包名进行筛选...")

    def toggle_options(self, checked):
        # 启用/禁用虚拟显示专属选项
        is_enabled = self.enable_vd_check.isChecked()
        self.vd_resolution_input.setEnabled(is_enabled)
        self.vd_dpi_input.setEnabled(is_enabled)
        self.no_decorations_check.setEnabled(is_enabled)
        self.no_destroy_check.setEnabled(is_enabled)
        self.ime_policy_combo.setEnabled(is_enabled)

    def get_args(self):
        args = []

        # 虚拟显示参数
        if self.enable_vd_check.isChecked():
            resolution = self.vd_resolution_input.text().strip()
            dpi = self.vd_dpi_input.text().strip()
            new_display_value = ""
            if resolution:
                new_display_value += resolution
            if dpi:
                new_display_value += f"/{dpi}"

            if new_display_value:
                args.append(f"--new-display={new_display_value}")
            else:
                args.append("--new-display")

            if self.no_decorations_check.isChecked():
                args.append('--no-vd-system-decorations')
            if self.no_destroy_check.isChecked():
                args.append('--no-vd-destroy-content')
            ime_policy = self.ime_policy_combo.currentText().split(' ')[0]
            if ime_policy != "默认":
                args.extend(['--display-ime-policy', ime_policy])

        # 启动应用参数 (独立于虚拟显示)
        current_text = self.start_app_combo.currentText().strip()
        if current_text:
            app_identifier = ""
            if '(' in current_text and ')' in current_text:
                if self.search_by_name_check.isChecked():
                    app_identifier = current_text.split('(')[0].strip()
                else:
                    app_identifier = current_text.split('(')[-1].replace(')', '').strip()
            else:
                app_identifier = current_text

            prefix = ""
            if self.force_stop_app_check.isChecked():
                prefix += "+"
            if self.search_by_name_check.isChecked():
                prefix += "?"

            if app_identifier:
                args.extend(['--start-app', f"{prefix}{app_identifier}"])

        return args