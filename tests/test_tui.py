"""TUI 命令层的测试（不依赖真实终端）。"""

import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from rix.tui import Session  # noqa: E402


class TuiSessionTestCase(unittest.TestCase):
    def setUp(self):
        self.session = Session()

    def test_help_and_quit(self):
        keep_going, output = self.session.execute("help")
        self.assertTrue(keep_going)
        self.assertIn("ls", output)
        keep_going, _ = self.session.execute("quit")
        self.assertFalse(keep_going)

    def test_set_and_show(self):
        self.session.execute("set video-bit-rate=16M")
        self.session.execute("set no-audio")
        _, output = self.session.execute("show")
        self.assertIn("--video-bit-rate=16M", output)
        self.assertIn("--no-audio=True", output)

    def test_unset(self):
        self.session.execute("set no-audio")
        _, output = self.session.execute("unset no-audio")
        self.assertIn("已取消", output)
        _, output = self.session.execute("show")
        self.assertIn("还没有设置", output)

    def test_set_rejects_unknown_option(self):
        _, output = self.session.execute("set server-debugger")
        self.assertIn("从未存在", output)
        self.assertNotIn("server-debugger", self.session.values)

    def test_set_warns_on_conflict(self):
        self.session.execute("set camera-id=0")
        _, output = self.session.execute("set camera-facing=front")
        self.assertIn("互斥", output)

    def test_preview_uses_registry(self):
        self.session.execute("set no-audio")
        _, output = self.session.execute("preview")
        self.assertIn("--no-audio", output)

    def test_run_emits_command_for_caller(self):
        self.session.execute("set no-audio")
        _, output = self.session.execute("run")
        self.assertTrue(output.startswith("RUN:"))
        self.assertIn("--no-audio", output)

    def test_ls_group_and_unknown_group(self):
        _, output = self.session.execute("ls video")
        self.assertIn("--video-codec", output)
        _, output = self.session.execute("ls not-a-group")
        self.assertIn("没有分组", output)

    def test_search(self):
        _, output = self.session.execute("search hwdec")
        self.assertIn("--hwdec", output)

    def test_profile_save_and_load(self):
        import tempfile

        from rix.profiles import ProfileStore

        with tempfile.TemporaryDirectory() as tmp:
            self.session.store = ProfileStore(os.path.join(tmp, "profiles.json"))
            self.session.execute("set max-fps=60")
            self.session.execute("save tui-test")
            self.session.execute("unset max-fps")
            _, output = self.session.execute("load tui-test")
            self.assertIn("已载入", output)
            self.assertEqual(self.session.values, {"max-fps": "60"})

    def test_load_missing_profile(self):
        _, output = self.session.execute("load nope")
        self.assertIn("没有预设", output)

    def test_unknown_command(self):
        _, output = self.session.execute("dance")
        self.assertIn("未知命令", output)


if __name__ == "__main__":
    unittest.main()
