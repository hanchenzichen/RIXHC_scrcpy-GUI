import subprocess
import sys
from PyQt6.QtCore import QObject, pyqtSignal, QThread


# (LogReader 和 ScrcpyWorker 类保持不变)
class LogReader(QObject):
    new_log = pyqtSignal(str)
    finished = pyqtSignal()
    _is_running = True

    def __init__(self, pipe):
        super().__init__()
        self.pipe = pipe

    def run(self):
        decoder = sys.stdout.encoding or 'utf-8'
        line_buffer = bytearray()
        while self._is_running:
            try:
                byte = self.pipe.read(1)
                if not byte:
                    if line_buffer: self.new_log.emit(line_buffer.decode(decoder, errors='replace'))
                    break
                line_buffer.append(byte[0])
                if byte == b'\n':
                    self.new_log.emit(line_buffer.decode(decoder, errors='replace'))
                    line_buffer.clear()
            except (IOError, ValueError):
                break
        self.pipe.close()
        self.finished.emit()

    def stop(self):
        self._is_running = False


class ScrcpyWorker(QObject):
    log_signal = pyqtSignal(str)
    finished_signal = pyqtSignal()
    process = None
    _log_reader_thread = None
    _log_reader = None

    def run(self, cmd):
        self.log_signal.emit(f"正在执行命令: {' '.join(cmd)}\n")
        try:
            self.process = subprocess.Popen(
                cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, bufsize=0,
                creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == 'win32' else 0
            )
            self._log_reader_thread = QThread()
            self._log_reader = LogReader(self.process.stdout)
            self._log_reader.moveToThread(self._log_reader_thread)
            self._log_reader.new_log.connect(self.log_signal)
            self._log_reader_thread.started.connect(self._log_reader.run)
            self._log_reader.finished.connect(self._log_reader_thread.quit)
            self._log_reader_thread.start()
            self.process.wait()
        except FileNotFoundError:
            self.log_signal.emit("错误: scrcpy 命令未找到。\n")
        except Exception as e:
            self.log_signal.emit(f"启动 scrcpy 时发生错误: {e}\n")
        self.stop_log_reader()
        self.finished_signal.emit()

    def stop_log_reader(self):
        if self._log_reader: self._log_reader.stop()
        if self._log_reader_thread and self._log_reader_thread.isRunning():
            self._log_reader_thread.quit()
            self._log_reader_thread.wait(1000)

    def stop(self):
        self.stop_log_reader()
        if self.process and self.process.poll() is None:
            self.log_signal.emit("正在停止 scrcpy 进程...\n")
            self.process.terminate()
            try:
                self.process.wait(timeout=3)
            except subprocess.TimeoutExpired:
                self.log_signal.emit("进程无法正常终止，强制结束。\n")
                self.process.kill()
            self.log_signal.emit("进程已停止。\n")


class AdbWorker(QObject):
    """
    【最终清洁版】后台工作类
    """
    refreshed_signal = pyqtSignal(list, str)
    command_finished_signal = pyqtSignal(str)
    packages_listed_signal = pyqtSignal(list)
    auto_pair_step_signal = pyqtSignal(str)
    auto_pair_finished_signal = pyqtSignal(str)

    def _run_adb_command_safe(self, cmd: list, timeout=15):
        try:
            process = subprocess.Popen(
                cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
                encoding='utf-8', errors='replace',
                creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == 'win32' else 0
            )
            stdout, stderr = process.communicate(timeout=timeout)
            if process.returncode != 0:
                raise Exception(stderr.strip() or f"命令返回了非零代码: {process.returncode}")
            return stdout.strip()
        except FileNotFoundError:
            raise Exception("adb.exe 未找到")
        except subprocess.TimeoutExpired:
            raise Exception(f"命令 '{' '.join(cmd)}' 执行超时")
        except Exception as e:
            raise Exception(f"执行 '{' '.join(cmd)}' 时出错: {e}")

    def refresh_devices(self, retries=0):
        try:
            output = self._run_adb_command_safe(['adb', 'devices'])
            lines = output.strip().split('\n')
            devices = [line.split('\t')[0] for line in lines[1:] if '\tdevice' in line]
            log_msg = f"找到设备: {', '.join(devices)}" if devices else "未找到已连接的设备。"
            self.refreshed_signal.emit(devices, log_msg)
        except Exception as e:
            self.refreshed_signal.emit([], f"获取设备列表失败: {e}")

    def list_packages_with_names(self):
        try:
            self.command_finished_signal.emit("正在获取第三方应用包名...")
            output = self._run_adb_command_safe(['adb', 'shell', 'pm', 'list', 'packages', '-f', '-3'])
            lines = [line.replace('package:', '').strip() for line in output.split('\n') if line]
            app_list = []
            total = len(lines)
            self.command_finished_signal.emit(f"找到 {total} 个应用，正在查询应用名...")
            for i, line in enumerate(lines):
                if '=' not in line: continue
                path, package = line.split('=', 1)
                try:
                    label_output = self._run_adb_command_safe(
                        ['adb', 'shell', f"aapt d badging '{path}' | grep application-label:"], timeout=3)
                    app_name = label_output.split("'")[1]
                    app_list.append({'name': app_name, 'package': package})
                    if (i + 1) % 10 == 0 or i + 1 == total:
                        self.command_finished_signal.emit(f"进度: {i + 1}/{total} ({app_name})")
                except Exception:
                    app_list.append({'name': package, 'package': package})
            self.packages_listed_signal.emit(app_list)
            self.command_finished_signal.emit(f"成功获取 {len(app_list)} 个应用的详细信息。")
        except Exception as e:
            self.command_finished_signal.emit(f"获取应用列表失败: {e}")
            self.packages_listed_signal.emit([])

    def kill_server(self):
        try:
            self._run_adb_command_safe(['adb', 'kill-server'])
            self.command_finished_signal.emit("ADB 服务已成功关闭。")
        except Exception as e:
            self.command_finished_signal.emit(f"关闭 ADB 服务失败: {e}")

    def restart_server(self):
        try:
            self.command_finished_signal.emit("尝试关闭现有 ADB 服务...")
            self._run_adb_command_safe(['adb', 'kill-server'], timeout=5)
            self.command_finished_signal.emit("正在启动新的 ADB 服务...")
            output = self._run_adb_command_safe(['adb', 'start-server'])
            clean_output = output.replace('\n', ' ').strip()
            if 'successfully' in clean_output or clean_output == '':
                self.command_finished_signal.emit("ADB 服务已成功重启！")
            else:
                self.command_finished_signal.emit(f"重启 ADB 服务可能存在问题: {clean_output}")
        except Exception as e:
            self.command_finished_signal.emit(f"重启 ADB 服务时发生严重错误: {e}")

    def enable_tcpip_mode(self, device_serial=None):
        cmd = ['adb']
        if device_serial: cmd.extend(['-s', device_serial])
        cmd.extend(['tcpip', '5555'])
        return self._run_adb_command_safe(cmd, timeout=10)

    def connect_to_device(self, ip_address):
        return self._run_adb_command_safe(['adb', 'connect', ip_address])

    def disconnect_from_device(self, ip_address):
        return self._run_adb_command_safe(['adb', 'disconnect', ip_address])

    def get_device_ip(self, device_serial=None):
        cmd = ['adb']
        if device_serial: cmd.extend(['-s', device_serial])
        cmd.extend(['shell', 'ip', 'route'])
        output = self._run_adb_command_safe(cmd, timeout=10)
        ip_addresses = [word for word in output.split() if '.' in word and all(p.isdigit() for p in word.split('.'))]
        if ip_addresses:
            return ip_addresses[-1]
        raise Exception("无法解析IP地址。")

    def auto_pair_sequence(self, usb_device_serial):
        try:
            self.auto_pair_step_signal.emit("步骤1: 正在获取USB设备IP地址...")
            ip_address = self.get_device_ip(usb_device_serial)
            self.auto_pair_step_signal.emit(f"获取到IP地址: {ip_address}")
            self.auto_pair_step_signal.emit("步骤2: 正在为设备开启TCP/IP模式...")
            self.enable_tcpip_mode(usb_device_serial)
            self.auto_pair_step_signal.emit(f"步骤3: 正在通过无线方式连接到 {ip_address}...")
            connect_output = self.connect_to_device(ip_address)
            self.auto_pair_step_signal.emit(f"连接结果: {connect_output}")
            self.auto_pair_finished_signal.emit("自动配对完成！请拔下USB线，并刷新设备列表查看。")
        except Exception as e:
            self.auto_pair_finished_signal.emit(f"自动配对失败: {e}")