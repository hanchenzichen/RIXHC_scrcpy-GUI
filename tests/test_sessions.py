"""会话管理层的测试。

用 Python 自身作为「被启动的程序」，因此不依赖 scrcpy 或 Android 设备。
"""

import os
import sys
import time
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from rix.sessions import SessionSupervisor  # noqa: E402

PY = sys.executable


def wait_for(predicate, timeout=10.0, interval=0.05):
    deadline = time.time() + timeout
    while time.time() < deadline:
        if predicate():
            return True
        time.sleep(interval)
    return False


class SessionSupervisorTestCase(unittest.TestCase):
    def setUp(self):
        self.supervisor = SessionSupervisor(max_log_lines=50)

    def tearDown(self):
        self.supervisor.stop_all(timeout=3)

    def test_start_collects_output_and_reports_running(self):
        session = self.supervisor.start([PY, "-u", "-c", "print('hello-scrcpy'); import time; time.sleep(30)"])
        self.assertTrue(wait_for(lambda: "hello-scrcpy" in session.log_text()))
        self.assertTrue(session.running)
        self.assertEqual(session.status, "running")

    def test_stop_terminates_process(self):
        session = self.supervisor.start([PY, "-u", "-c", "import time; time.sleep(60)"])
        self.assertTrue(wait_for(lambda: session.running))
        self.assertTrue(self.supervisor.stop(session.id, timeout=5))
        self.assertFalse(session.running)
        self.assertEqual(session.status, "stopped")

    def test_short_lived_process_reports_exit_code(self):
        session = self.supervisor.start([PY, "-u", "-c", "print('done')"])
        self.assertTrue(wait_for(lambda: session.status != "running"))
        self.assertEqual(session.returncode, 0)
        self.assertEqual(session.status, "exited")

    def test_nonzero_exit_is_marked_failed(self):
        session = self.supervisor.start([PY, "-u", "-c", "import sys; sys.exit(3)"])
        self.assertTrue(wait_for(lambda: session.status != "running"))
        self.assertEqual(session.status, "failed")
        self.assertEqual(session.returncode, 3)

    def test_missing_binary_is_reported_not_raised(self):
        session = self.supervisor.start(["definitely-not-a-real-binary-xyz"])
        self.assertEqual(session.status, "failed")
        self.assertIn("未找到可执行文件", session.error or "")

    def test_log_is_ring_buffered(self):
        """日志必须是有上限的环形缓冲，否则长时间运行会吃光内存。"""
        script = "for i in range(200): print('line', i, flush=True)"
        session = self.supervisor.start([PY, "-c", script])
        self.assertTrue(wait_for(lambda: session.status != "running"))
        lines, next_index = session.read_log(0)
        self.assertLessEqual(len(lines), 50)
        self.assertEqual(next_index, len(lines))
        self.assertIn("line 199", "\n".join(lines))

    def test_incremental_log_reading(self):
        session = self.supervisor.start(
            [PY, "-u", "-c", "print('first'); import time; time.sleep(0.3); print('second'); time.sleep(30)"])
        self.assertTrue(wait_for(lambda: "first" in session.log_text()))
        lines, cursor = session.read_log(0)
        self.assertIn("first", "\n".join(lines))
        self.assertTrue(wait_for(lambda: "second" in session.log_text()))
        new_lines, new_cursor = session.read_log(cursor)
        self.assertIn("second", "\n".join(new_lines))
        self.assertGreater(new_cursor, cursor)

    def test_list_and_get_and_prune(self):
        first = self.supervisor.start([PY, "-u", "-c", "import time; time.sleep(30)"])
        second = self.supervisor.start([PY, "-u", "-c", "print('x')"])
        self.assertTrue(wait_for(lambda: second.status != "running"))
        self.assertEqual(len(self.supervisor.list()), 2)
        self.assertIsNotNone(self.supervisor.get(first.id))
        self.assertIsNone(self.supervisor.get("no-such-session"))
        self.assertEqual(self.supervisor.prune_finished(), 1)
        self.assertEqual(len(self.supervisor.list()), 1)

    def test_to_dict_shape(self):
        session = self.supervisor.start([PY, "-u", "-c", "import time; time.sleep(30)"], label="unit-test")
        payload = session.to_dict(log_tail=5)
        self.assertEqual(payload["label"], "unit-test")
        self.assertIn("command", payload)
        self.assertIn("uptime", payload)
        self.assertIn("log", payload)

    def test_stop_unknown_session_returns_false(self):
        self.assertFalse(self.supervisor.stop("no-such-session"))


if __name__ == "__main__":
    unittest.main()
