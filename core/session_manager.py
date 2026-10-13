import time

from PySide6.QtCore import QThread, QObject, Signal
# 使用绝对导入，确保 IDE 能正确解析
from core.command_runner import ScrcpyWorker


class SessionManager(QObject):
    """
    负责启动、管理和停止多个 Scrcpy 会话。
    """
    session_started = Signal(str, str)
    session_stopped = Signal(str)
    log_signal = Signal(str)

    def __init__(self):
        super().__init__()
        self.active_sessions = {}
        self.session_counter = 0

    def start_session(self, session_name_hint: str, cmd_args: list, is_otg=False):
        self.session_counter += 1
        session_type = "OTG" if is_otg else "Session"
        session_id = f"{session_type}-{self.session_counter}_{session_name_hint.replace(':', '-')[:10]}"

        base_cmd = ['scrcpy', '--otg'] if is_otg else ['scrcpy']
        final_cmd = base_cmd + cmd_args

        thread = QThread()
        worker = ScrcpyWorker()
        worker.moveToThread(thread)

        worker.log_signal.connect(self.log_signal)
        worker.finished_signal.connect(lambda: self._on_session_finished(session_id))

        thread.started.connect(lambda: worker.run(final_cmd))
        thread.start()

        self.active_sessions[session_id] = {'thread': thread, 'worker': worker}

        self.session_started.emit(session_id, session_name_hint)
        self.log_signal.emit(f"会话 '{session_id}' 已启动。")

    def stop_session(self, session_id: str):
        if session_id in self.active_sessions:
            worker = self.active_sessions[session_id]['worker']
            worker.stop()

    def _on_session_finished(self, session_id: str):
        if session_id in self.active_sessions:
            session_info = self.active_sessions.pop(session_id)
            thread = session_info['thread']
            thread.quit()
            thread.wait()
            self.session_stopped.emit(session_id)
            self.log_signal.emit(f"会话 '{session_id}' 已彻底停止并清理。")

    def stop_all_sessions(self, timeout_ms: int = 8000):
        """停止所有会话，并等待线程真正退出。

        退出时不等待线程是早期版本的隐患：QThread 还在跑而解释器已经开始销毁
        对象，会打印 "QThread: Destroyed while thread is still running"，
        严重时直接崩溃、或留下没有回收的 scrcpy 进程。
        """
        session_ids = list(self.active_sessions.keys())
        if not session_ids:
            return
        for sid in session_ids:
            self.stop_session(sid)

        deadline = time.monotonic() + timeout_ms / 1000.0
        for sid in session_ids:
            info = self.active_sessions.get(sid)
            if not info:
                continue
            thread = info['thread']
            remaining = int(max(0.0, deadline - time.monotonic()) * 1000)
            thread.quit()
            if not thread.wait(remaining):
                self.log_signal.emit(f"警告：会话 '{sid}' 未能在超时内结束，请检查是否有残留的 scrcpy 进程。")
