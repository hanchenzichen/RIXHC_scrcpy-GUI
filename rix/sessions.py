"""无 GUI 依赖的会话管理（纯标准库）。

与 `core/session_manager.py` 的区别：
    后者依赖 Qt 的 QThread/QObject，只服务 GUI；本模块是 CLI / TUI / agent 共用的实现，
    因此可以在服务器、CI、无图形环境中运行，也更容易测试。

能力：
    * 启动 / 停止 / 列举多个 scrcpy 会话
    * 每个会话独立收集输出（环形缓冲，避免长时间运行吃内存）
    * 记录退出码与状态，便于前端展示
"""

from __future__ import annotations

import os
import signal
import subprocess
import sys
import threading
import time
import uuid
from collections import deque

DEFAULT_LOG_LINES = 2000

# Windows 下不弹出控制台窗口
_CREATE_FLAGS = subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0


class Session:
    """单个 scrcpy 会话。"""

    def __init__(self, session_id: str, argv: list[str], label: str = "",
                 max_log_lines: int = DEFAULT_LOG_LINES):
        self.id = session_id
        self.argv = list(argv)
        self.label = label or " ".join(argv[:2])
        self.started_at = time.time()
        self.status = "starting"          # starting / running / exited / stopped / failed
        self.returncode: int | None = None
        self.error: str | None = None
        self._log: deque[str] = deque(maxlen=max_log_lines)
        self._log_lock = threading.Lock()
        self._process: subprocess.Popen | None = None
        self._reader: threading.Thread | None = None

    # ---- 输出 ----
    def append_log(self, line: str) -> None:
        with self._log_lock:
            self._log.append(line.rstrip("\r\n"))

    def read_log(self, since: int = 0) -> tuple[list[str], int]:
        """返回 (从 since 开始的新行, 下一个 since 值)。"""
        with self._log_lock:
            lines = list(self._log)
        return lines[since:], len(lines)

    def log_text(self, since: int = 0) -> str:
        lines, _ = self.read_log(since)
        return "\n".join(lines)

    def log_size(self) -> int:
        with self._log_lock:
            return len(self._log)

    # ---- 生命周期 ----
    def _attach(self, process: subprocess.Popen) -> None:
        self._process = process
        self.status = "running"
        self._reader = threading.Thread(target=self._pump, args=(process,), daemon=True)
        self._reader.start()

    def _pump(self, process: subprocess.Popen) -> None:
        assert process.stdout is not None
        try:
            for line in process.stdout:
                self.append_log(line)
        except (ValueError, OSError):
            pass
        finally:
            try:
                process.stdout.close()
            except (OSError, ValueError):
                pass
        code = process.wait()
        self.returncode = code
        if self.status == "running":
            self.status = "exited" if code == 0 else "failed"
            if code != 0:
                self.append_log(f"[进程退出，返回码 {code}]")

    @property
    def running(self) -> bool:
        return self._process is not None and self._process.poll() is None

    def stop(self, timeout: float = 5.0) -> bool:
        """终止会话。返回 True 表示进程已结束。"""
        process = self._process
        if process is None or process.poll() is not None:
            return True
        self.status = "stopped"
        try:
            if os.name == "nt":
                process.terminate()
            else:
                # 结束整个进程组，避免 scrcpy 的子进程（如 adb）残留
                os.killpg(os.getpgid(process.pid), signal.SIGTERM)
        except (ProcessLookupError, PermissionError, OSError):
            try:
                process.terminate()
            except OSError:
                pass
        try:
            process.wait(timeout=timeout)
            return True
        except subprocess.TimeoutExpired:
            self.append_log("[进程未在超时内退出，强制结束]")
            try:
                if os.name == "nt":
                    process.kill()
                else:
                    os.killpg(os.getpgid(process.pid), signal.SIGKILL)
            except (ProcessLookupError, PermissionError, OSError):
                try:
                    process.kill()
                except OSError:
                    pass
            try:
                process.wait(timeout=timeout)
            except subprocess.TimeoutExpired:
                return False
            return True

    def to_dict(self, log_tail: int = 0) -> dict:
        data = {
            "id": self.id,
            "label": self.label,
            "argv": self.argv,
            "command": " ".join(self.argv),
            "status": self.status,
            "returncode": self.returncode,
            "started_at": self.started_at,
            "uptime": round(time.time() - self.started_at, 1),
            "error": self.error,
        }
        if log_tail:
            size = self.log_size()
            lines, _ = self.read_log(max(0, size - log_tail))
            data["log"] = lines
        return data


class SessionSupervisor:
    """管理多个会话，线程安全。"""

    def __init__(self, max_log_lines: int = DEFAULT_LOG_LINES):
        self.max_log_lines = max_log_lines
        self._sessions: dict[str, Session] = {}
        self._lock = threading.Lock()
        self._counter = 0

    # ---- 查询 ----
    def list(self) -> list[Session]:
        with self._lock:
            return sorted(self._sessions.values(), key=lambda item: item.started_at)

    def get(self, session_id: str) -> Session | None:
        with self._lock:
            return self._sessions.get(session_id)

    def prune_finished(self) -> int:
        """清理已结束的会话，返回清理数量。"""
        with self._lock:
            done = [sid for sid, item in self._sessions.items() if not item.running]
            for sid in done:
                del self._sessions[sid]
            return len(done)

    # ---- 生命周期 ----
    def start(self, argv: list[str], label: str = "") -> Session:
        with self._lock:
            self._counter += 1
            session_id = f"S{self._counter}-{uuid.uuid4().hex[:6]}"
            session = Session(session_id, argv, label, self.max_log_lines)
            self._sessions[session_id] = session

        try:
            process = subprocess.Popen(
                argv,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                stdin=subprocess.DEVNULL,
                text=True,
                encoding="utf-8",
                errors="replace",
                bufsize=1,
                creationflags=_CREATE_FLAGS,
                # POSIX 下单独进程组，便于连同子进程一起结束
                start_new_session=(os.name != "nt"),
            )
        except FileNotFoundError:
            session.status = "failed"
            session.error = f"未找到可执行文件: {argv[0]}"
            session.append_log(session.error)
            return session
        except OSError as exc:
            session.status = "failed"
            session.error = str(exc)
            session.append_log(f"启动失败: {exc}")
            return session

        session._attach(process)
        return session

    def stop(self, session_id: str, timeout: float = 5.0) -> bool:
        session = self.get(session_id)
        if session is None:
            return False
        return session.stop(timeout)

    def stop_all(self, timeout: float = 5.0) -> int:
        count = 0
        for session in self.list():
            if session.running and session.stop(timeout):
                count += 1
        return count

    def wait_for_exit(self, session_id: str, timeout: float = 10.0) -> int | None:
        session = self.get(session_id)
        if session is None or session._process is None:
            return None
        try:
            return session._process.wait(timeout=timeout)
        except subprocess.TimeoutExpired:
            return None

    def build_argv(self, registry, values: dict, extra_args: list[str] | None = None,
                   binary: str | None = None) -> list[str]:
        """用注册表把配置拼成命令行（供 agent / CLI 复用）。"""
        return registry.build_argv(values, extra_args or [], binary=binary or "scrcpy")
