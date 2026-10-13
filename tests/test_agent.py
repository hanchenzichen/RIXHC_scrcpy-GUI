"""本地 agent 的接口测试。

在回环地址上以随机端口启动真实 HTTP 服务，用 urllib 调用各接口；
会话部分用 Python 自身作为被启动程序，因此不依赖 scrcpy 或真机。
"""

import json
import os
import sys
import threading
import time
import unittest
import urllib.error
import urllib.request

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from rix.agent import AgentState, make_server  # noqa: E402

PY = sys.executable


class AgentHarness:
    """公共装置：起服务、发请求、等待条件。不继承 TestCase，避免被子类重复收集。"""

    token = None

    @classmethod
    def setUpClass(cls):
        cls.state = AgentState(token=cls.token)
        cls.httpd = make_server("127.0.0.1", 0, cls.state)
        cls.port = cls.httpd.server_address[1]
        cls.thread = threading.Thread(target=cls.httpd.serve_forever, daemon=True)
        cls.thread.start()

    @classmethod
    def tearDownClass(cls):
        cls.state.supervisor.stop_all(timeout=3)
        cls.httpd.shutdown()
        cls.httpd.server_close()

    @property
    def base(self) -> str:
        return f"http://127.0.0.1:{self.port}"

    def request(self, path, method="GET", payload=None, token=None):
        data = json.dumps(payload).encode() if payload is not None else None
        request = urllib.request.Request(self.base + path, data=data, method=method)
        if data:
            request.add_header("Content-Type", "application/json")
        if token:
            request.add_header("X-Rix-Token", token)
        with urllib.request.urlopen(request, timeout=15) as response:
            body = response.read().decode("utf-8")
            return response.status, (json.loads(body) if body.startswith(("{", "[")) else body)

    def wait_for(self, predicate, timeout=15.0):
        deadline = time.time() + timeout
        while time.time() < deadline:
            if predicate():
                return True
            time.sleep(0.1)
        return False



class AgentTestCase(AgentHarness, unittest.TestCase):

    # ---- 只读接口 ----
    def test_status(self):
        status, payload = self.request("/api/status")
        self.assertEqual(status, 200)
        self.assertEqual(payload["app"], "rix-scrcpy")
        self.assertEqual(payload["option_count"], 109)
        self.assertIn("vendor", payload)

    def test_options_and_filter(self):
        _, all_options = self.request("/api/options")
        self.assertEqual(len(all_options), 109)
        _, filtered = self.request("/api/options?search=codec")
        self.assertTrue(any(item["long"] == "video-codec" for item in filtered))
        _, by_group = self.request("/api/options?group=video")
        self.assertTrue(all(item["group"] == "video" for item in by_group))

    def test_web_console_is_served(self):
        status, body = self.request("/")
        self.assertEqual(status, 200)
        self.assertIn("RIX Scrcpy", body)

    def test_sessions_initially_empty(self):
        _, payload = self.request("/api/sessions")
        self.assertIsInstance(payload, list)

    def test_unknown_endpoint_returns_404(self):
        with self.assertRaises(urllib.error.HTTPError) as ctx:
            self.request("/api/nope")
        self.assertEqual(ctx.exception.code, 404)

    # ---- 会话操作 ----
    def test_start_session_and_read_log(self):
        _, payload = self.request("/api/sessions", "POST", {
            "values": {},
            "extra_args": ["-c", "print('agent-log-line')"],
            "binary": PY,
            "label": "agent-test",
        })
        self.assertTrue(payload["ok"], payload)
        session_id = payload["session"]["id"]
        captured = {}

        def has_line():
            _, log = self.request(f"/api/sessions/{session_id}/log?since=0")
            captured["log"] = log
            return any("agent-log-line" in line for line in log["lines"])

        self.assertTrue(self.wait_for(has_line))
        self.assertIn("next", captured["log"])

    def test_start_session_rejects_unknown_option(self):
        _, payload = self.request("/api/sessions", "POST", {
            "values": {"definitely-not-real": "1"}, "binary": PY,
        })
        self.assertFalse(payload["ok"])
        self.assertIn("未知参数", payload["error"])

    def test_stop_session(self):
        _, payload = self.request("/api/sessions", "POST", {
            "values": {},
            "extra_args": ["-c", "import time; time.sleep(60)"],
            "binary": PY,
        })
        session_id = payload["session"]["id"]
        self.assertTrue(self.wait_for(
            lambda: any(item["id"] == session_id for item in self.request("/api/sessions")[1])))
        _, stopped = self.request(f"/api/sessions/{session_id}", "DELETE")
        self.assertTrue(stopped["ok"])
        self.assertEqual(stopped["session"]["status"], "stopped")

    def test_stop_unknown_session_returns_404(self):
        with self.assertRaises(urllib.error.HTTPError) as ctx:
            self.request("/api/sessions/no-such-session", "DELETE")
        self.assertEqual(ctx.exception.code, 404)

    def test_log_of_unknown_session_returns_404(self):
        with self.assertRaises(urllib.error.HTTPError) as ctx:
            self.request("/api/sessions/no-such-session/log")
        self.assertEqual(ctx.exception.code, 404)

    def test_profiles_endpoint(self):
        _, payload = self.request("/api/profiles")
        self.assertIsInstance(payload, dict)


class AgentTokenTestCase(AgentHarness, unittest.TestCase):
    """设置了 token 时必须校验，否则局域网内任何设备都能控制。"""

    token = "unit-test-token"

    def test_request_without_token_is_rejected(self):
        with self.assertRaises(urllib.error.HTTPError) as ctx:
            self.request("/api/status")
        self.assertEqual(ctx.exception.code, 401)

    def test_request_with_header_token_is_accepted(self):
        status, payload = self.request("/api/status", token=self.token)
        self.assertEqual(status, 200)
        self.assertEqual(payload["app"], "rix-scrcpy")

    def test_request_with_query_token_is_accepted(self):
        status, _ = self.request(f"/api/status?token={self.token}")
        self.assertEqual(status, 200)


if __name__ == "__main__":
    unittest.main()
