"""控制台编码处理的测试。

背景：Windows 上 stdout 在管道/CI 场景使用系统代码页（cp1252），
打印中文会抛 UnicodeEncodeError 并让程序崩溃。这里用 PYTHONIOENCODING
在任意平台上复现该场景，验证入口已经做了处理。
"""

import os
import subprocess
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from rix.console import enable_utf8_output  # noqa: E402


class EnableUtf8OutputTestCase(unittest.TestCase):
    def test_helper_is_idempotent(self):
        enable_utf8_output()
        enable_utf8_output()


class CliEncodingTestCase(unittest.TestCase):
    """在「窄编码」环境下运行 CLI，必须仍然返回 0（而不是崩溃）。"""

    def run_cli(self, args, encoding="cp1252"):
        env = dict(os.environ)
        env["PYTHONIOENCODING"] = encoding
        env["PYTHONPATH"] = ROOT
        return subprocess.run(
            [sys.executable, "-m", "rix.cli"] + args,
            cwd=ROOT, env=env, capture_output=True, text=True,
            encoding="utf-8", errors="replace", timeout=120,
        )

    def test_options_survives_cp1252_stdout(self):
        result = self.run_cli(["options", "--search", "codec"])
        self.assertEqual(result.returncode, 0, result.stderr[-2000:])

    def test_doctor_survives_cp1252_stdout(self):
        result = self.run_cli(["doctor"])
        self.assertIn(result.returncode, (0, 1), result.stderr[-2000:])
        self.assertNotIn("UnicodeEncodeError", result.stderr)

    def test_tui_script_survives_cp1252_stdout(self):
        env = dict(os.environ)
        env["PYTHONIOENCODING"] = "cp1252"
        env["PYTHONPATH"] = ROOT
        result = subprocess.run(
            [sys.executable, "-m", "rix.tui", "--script", "ls video; quit"],
            cwd=ROOT, env=env, capture_output=True, text=True,
            encoding="utf-8", errors="replace", timeout=120,
        )
        self.assertEqual(result.returncode, 0, result.stderr[-2000:])

    def test_check_version_survives_cp1252_stdout(self):
        env = dict(os.environ)
        env["PYTHONIOENCODING"] = "cp1252"
        result = subprocess.run(
            [sys.executable, os.path.join("tools", "check_version.py")],
            cwd=ROOT, env=env, capture_output=True, text=True,
            encoding="utf-8", errors="replace", timeout=120,
        )
        self.assertEqual(result.returncode, 0, result.stderr[-2000:])


if __name__ == "__main__":
    unittest.main()
