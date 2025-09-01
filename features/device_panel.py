from PyQt6.QtWidgets import (QWidget, QHBoxLayout, QVBoxLayout, QLabel, QComboBox,
                             QPushButton, QGroupBox, QLineEdit, QRadioButton)
from PyQt6.QtCore import QThread
from core.command_runner import AdbWorker


class DevicePanel(QWidget):
    """
    【连接管理器版】设备面板
    """

    def __init__(self):
        super().__init__()
        main_layout = QVBoxLayout()
        main_layout.setContentsMargins(0, 10, 0, 10)
        main_layout.setSpacing(10)

        # 分组1: 设备选择
        selection_group = QGroupBox("设备选择")
        selection_layout = QVBoxLayout(selection_group)
        device_list_layout = QHBoxLayout()
        self.device_label = QLabel('当前设备:')
        self.device_combo = QComboBox()
        self.refresh_button = QPushButton('🔃 刷新')
        device_list_layout.addWidget(self.device_label)
        device_list_layout.addWidget(self.device_combo, 1)
        device_list_layout.addWidget(self.refresh_button)

        self.selection_mode = 'serial'
        mode_layout = QHBoxLayout()
        mode_label = QLabel("启动时选择:")
        self.serial_radio = QRadioButton("按上方列表 (-s)")
        self.usb_radio = QRadioButton("唯一的USB设备 (-d)")
        self.tcpip_radio = QRadioButton("唯一的TCP/IP设备 (-e)")
        self.serial_radio.setChecked(True)
        mode_layout.addWidget(mode_label)
        mode_layout.addWidget(self.serial_radio)
        mode_layout.addWidget(self.usb_radio)
        mode_layout.addWidget(self.tcpip_radio)
        self.serial_radio.toggled.connect(lambda: self.set_selection_mode('serial'))
        self.usb_radio.toggled.connect(lambda: self.set_selection_mode('usb'))
        self.tcpip_radio.toggled.connect(lambda: self.set_selection_mode('tcpip'))
        selection_layout.addLayout(device_list_layout)
        selection_layout.addLayout(mode_layout)
        main_layout.addWidget(selection_group)

        # 分组2: 无线连接 (TCP/IP)
        wireless_group = QGroupBox("无线连接")
        wireless_layout = QVBoxLayout(wireless_group)
        ip_layout = QHBoxLayout()
        self.ip_input = QLineEdit()
        self.ip_input.setPlaceholderText("输入设备IP地址, 如: 192.168.1.10:5555")
        self.connect_button = QPushButton("🔗 连接")
        self.disconnect_button = QPushButton("🔌 断开")
        ip_layout.addWidget(self.ip_input, 1)
        ip_layout.addWidget(self.connect_button)
        ip_layout.addWidget(self.disconnect_button)
        auto_pair_layout = QHBoxLayout()
        self.auto_pair_button = QPushButton("USB自动配对无线连接 (需先用USB连接设备)")
        auto_pair_layout.addWidget(self.auto_pair_button)
        wireless_layout.addLayout(ip_layout)
        wireless_layout.addLayout(auto_pair_layout)
        main_layout.addWidget(wireless_group)

        # 分组3: ADB服务控制
        adb_group = QGroupBox("ADB 服务")
        adb_layout = QHBoxLayout(adb_group)
        self.restart_adb_button = QPushButton('🔄 重启ADB服务')
        self.kill_adb_button = QPushButton('🛑 关闭ADB服务')
        adb_layout.addWidget(self.restart_adb_button)
        adb_layout.addWidget(self.kill_adb_button)
        main_layout.addWidget(adb_group)

        self.setLayout(main_layout)

        # 连接信号
        self.refresh_button.clicked.connect(self.refresh_devices)
        self.restart_adb_button.clicked.connect(self.handle_restart_server)
        self.kill_adb_button.clicked.connect(self.handle_kill_server)
        self.connect_button.clicked.connect(self.handle_connect)
        self.disconnect_button.clicked.connect(self.handle_disconnect)
        self.auto_pair_button.clicked.connect(self.handle_auto_pair)

        self.log_emitter = None
        self.thread = None
        self.worker = None

    def set_log_emitter(self, log_emitter):
        self.log_emitter = log_emitter

    def set_selection_mode(self, mode):
        self.selection_mode = mode

    def set_all_buttons_enabled(self, enabled):
        self.refresh_button.setEnabled(enabled)
        self.restart_adb_button.setEnabled(enabled)
        self.kill_adb_button.setEnabled(enabled)
        self.connect_button.setEnabled(enabled)
        self.disconnect_button.setEnabled(enabled)
        self.auto_pair_button.setEnabled(enabled)

    def get_args(self):
        if self.selection_mode == 'usb': return ['-d']
        if self.selection_mode == 'tcpip': return ['-e']
        device_id = self.device_combo.currentText()
        if not device_id:
            if self.log_emitter: self.log_emitter("错误：请先选择一个设备！")
            return None
        return ['--serial', device_id]

    def handle_connect(self):
        ip = self.ip_input.text().strip()
        if not ip:
            if self.log_emitter: self.log_emitter("请输入IP地址！")
            return
        self.run_generic_adb_command(('connect_to_device', ip), f"正在连接到 {ip}...")

    def handle_disconnect(self):
        ip = self.ip_input.text().strip()
        if not ip:
            if self.log_emitter: self.log_emitter("请输入IP地址！")
            return
        self.run_generic_adb_command(('disconnect_from_device', ip), f"正在从 {ip} 断开...")

    def handle_auto_pair(self):
        usb_devices = [item for item in [self.device_combo.itemText(i) for i in range(self.device_combo.count())] if
                       ':' not in item]
        if not usb_devices:
            if self.log_emitter: self.log_emitter("自动配对失败：未找到通过USB连接的设备。")
            return
        self.run_generic_adb_command(('auto_pair_sequence', usb_devices[0]), "正在开始自动配对...")

    def refresh_devices(self):
        self.run_generic_adb_command('refresh_devices', "正在刷新设备列表...")

    def handle_kill_server(self):
        self.run_generic_adb_command('kill_server', "正在关闭 ADB 服务...")

    def handle_restart_server(self):
        self.run_generic_adb_command('restart_server', "正在重启 ADB 服务...")

    def run_generic_adb_command(self, command_info, log_message: str):
        if self.log_emitter: self.log_emitter(log_message)
        self.set_all_buttons_enabled(False)
        self.thread = QThread()
        self.worker = AdbWorker()
        self.worker.moveToThread(self.thread)

        if isinstance(command_info, tuple):
            command_name, args = command_info
            command_to_run = lambda: getattr(self.worker, command_name)(args)
        else:
            command_name = command_info
            command_to_run = getattr(self.worker, command_name)

        self.thread.started.connect(command_to_run)

        if command_name == 'refresh_devices':
            self.worker.refreshed_signal.connect(self.update_combo_box)
        elif command_name == 'auto_pair_sequence':
            self.worker.auto_pair_step_signal.connect(self.log_emitter)
            self.worker.auto_pair_finished_signal.connect(self.on_generic_command_finished)
        else:
            self.worker.command_finished_signal.connect(self.on_generic_command_finished)

        self.thread.finished.connect(self.thread.deleteLater)
        self.thread.finished.connect(self.worker.deleteLater)
        self.thread.finished.connect(lambda: self.set_all_buttons_enabled(True))
        self.thread.start()

    def update_combo_box(self, devices, log_msg):
        current_selection = self.device_combo.currentText()
        self.device_combo.clear()
        if devices: self.device_combo.addItems(devices)
        if current_selection in devices: self.device_combo.setCurrentText(current_selection)
        if self.log_emitter: self.log_emitter(log_msg)
        if self.thread: self.thread.quit()

    def on_generic_command_finished(self, log_msg: str):
        if self.log_emitter: self.log_emitter(log_msg)
        if self.thread: self.thread.quit()
        if "配对完成" in log_msg or "连接到" in log_msg or "断开" in log_msg:
            self.refresh_devices()