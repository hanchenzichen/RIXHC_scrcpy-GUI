import subprocess
import os
from PyQt6.QtWidgets import (QWidget, QVBoxLayout, QFormLayout, QGroupBox,
                             QCheckBox, QPushButton, QFileDialog, QMessageBox, QLabel, QLineEdit)


class DeveloperPanel(QWidget):
    """
    【功能增强版】开发者/高级设置面板
    新增远程设备隧道功能。
    """

    def __init__(self):
        super().__init__()
        main_layout = QVBoxLayout()
        main_layout.setContentsMargins(10, 10, 10, 10)
        main_layout.setSpacing(10)

        # --- 分组1: 底层连接选项 ---
        connection_group = QGroupBox("底层连接选项")
        connection_layout = QFormLayout(connection_group)
        self.force_adb_forward_check = QCheckBox("强制使用 ADB forward 模式")
        self.force_adb_forward_check.setToolTip(
            "默认使用 reverse 模式 (电脑监听，手机连接)。\n"
            "在某些网络环境下或使用特定SSH隧道时，切换到 forward 模式可能解决连接问题。"
        )
        connection_layout.addRow(self.force_adb_forward_check)

        # --- 分组2: 远程设备隧道 ---
        tunnel_group = QGroupBox("远程设备隧道 (连接互联网上的设备)")
        tunnel_layout = QFormLayout(tunnel_group)

        self.tunnel_host_input = QLineEdit()
        self.tunnel_host_input.setPlaceholderText("例如: 192.168.1.2 (远程主机IP)")
        self.tunnel_host_input.setToolTip(
            "填写远程主机的IP地址。\n"
            "警告：直接连接未加密，强烈建议使用SSH隧道。"
        )

        self.tunnel_port_input = QLineEdit()
        self.tunnel_port_input.setPlaceholderText("例如: 27183 (留空则使用默认端口)")

        info_label = QLabel(
            "使用此功能前，需在远程主机上启动 ADB Server 并设置环境变量。\n"
            "<b>强烈建议使用 SSH 隧道以保证连接安全。</b>"
        )
        info_label.setWordWrap(True)

        tunnel_layout.addRow("隧道主机IP:", self.tunnel_host_input)
        tunnel_layout.addRow("隧道端口(可选):", self.tunnel_port_input)
        tunnel_layout.addWidget(info_label)

        # --- 分组3: 独立 Server 模式 (高级) ---
        server_group = QGroupBox("独立 Server 模式 (供 VLC 等外部应用使用)")
        server_layout = QVBoxLayout(server_group)
        self.enable_standalone_server_check = QCheckBox("启用独立 Server 模式 (不通过 scrcpy 启动)")
        self.enable_standalone_server_check.toggled.connect(self.toggle_standalone_options)

        self.standalone_options_widget = QWidget()
        standalone_options_layout = QFormLayout(self.standalone_options_widget)

        self.server_path_button = QPushButton("选择 scrcpy-server 文件")
        self.server_path_label = QLabel("未选择")
        self.server_path_button.clicked.connect(self.select_server_file)

        self.start_standalone_button = QPushButton("启动独立 Server")
        self.start_standalone_button.clicked.connect(self.handle_start_standalone_server)

        standalone_options_layout.addRow(self.server_path_button, self.server_path_label)
        standalone_options_layout.addRow(self.start_standalone_button)
        server_layout.addWidget(self.enable_standalone_server_check)
        server_layout.addWidget(self.standalone_options_widget)

        # --- 分组4: 调试 ---
        debug_group = QGroupBox("调试")
        debug_layout = QFormLayout(debug_group)
        self.server_debugger_check = QCheckBox("启用 Server 调试器 (--server-debugger)")
        debug_layout.addRow(self.server_debugger_check)

        # --- 最终布局 ---
        main_layout.addWidget(connection_group)
        main_layout.addWidget(tunnel_group)
        main_layout.addWidget(server_group)
        main_layout.addWidget(debug_group)
        main_layout.addStretch()
        self.setLayout(main_layout)

        # 初始化UI
        self.toggle_standalone_options(False)
        self.log_emitter = None

    def set_log_emitter(self, log_emitter):
        self.log_emitter = log_emitter

    def toggle_standalone_options(self, checked):
        self.standalone_options_widget.setEnabled(checked)

    def select_server_file(self):
        file_path, _ = QFileDialog.getOpenFileName(self, "选择 scrcpy-server 文件", "", "JAR and Other Files (*.jar *)")
        if file_path:
            self.server_path_label.setText(os.path.basename(file_path))
            self.server_path_label.setToolTip(file_path)

    def handle_start_standalone_server(self):
        server_path = self.server_path_label.toolTip()
        if not server_path or not os.path.exists(server_path):
            QMessageBox.warning(self, "错误", "请先选择一个有效的 scrcpy-server 文件！")
            return

        if self.log_emitter:
            self.log_emitter("--- 启动独立 Server ---")
            try:
                self.log_emitter("步骤1: 正在推送 server 文件...")
                subprocess.run(['adb', 'push', server_path, '/data/local/tmp/scrcpy-server-manual.jar'], check=True)

                self.log_emitter("步骤2: 正在设置端口转发 (tcp:27185)...")
                subprocess.run(['adb', 'forward', 'tcp:27185', 'localabstract:scrcpy'], check=True)

                self.log_emitter("步骤3: 正在后台启动 server 进程...")
                cmd = [
                    'adb', 'shell',
                    'CLASSPATH=/data/local/tmp/scrcpy-server-manual.jar',
                    'app_process', '/', 'com.genymobile.scrcpy.Server',
                    '2.4',
                    'tunnel_forward=true', 'audio=false', 'control=false',
                    'cleanup=false', 'raw_stream=true', 'max_size=1920'
                ]
                subprocess.Popen(cmd)

                self.log_emitter("\n独立 Server 已在后台启动！")
                self.log_emitter("您现在可以使用VLC等播放器打开以下网络串流地址:")
                self.log_emitter("tcp://localhost:27185")
                self.log_emitter("注意：请手动通过 ADB 或我们的 GUI 关闭 ADB 服务来停止 Server。")

            except Exception as e:
                self.log_emitter(f"启动独立 Server 失败: {e}")

    def get_args(self):
        """获取该面板对应的 scrcpy 命令行参数"""
        args = []
        if self.force_adb_forward_check.isChecked():
            args.append('--force-adb-forward')

        if host := self.tunnel_host_input.text().strip():
            args.extend(['--tunnel-host', host])

        if port := self.tunnel_port_input.text().strip():
            args.extend(['--tunnel-port', port])

        if self.server_debugger_check.isChecked():
            args.append('--server-debugger')

        return args