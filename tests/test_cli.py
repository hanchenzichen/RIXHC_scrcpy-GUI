"""预设存储与 CLI 行为的测试。"""

import io
import json
import os
import sys
import tempfile
import unittest
from contextlib import redirect_stdout

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from rix.cli import main  # noqa: E402
from rix.profiles import InvalidProfileName, ProfileStore  # noqa: E402


class ProfileStoreTestCase(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.path = os.path.join(self.tmp.name, "profiles.json")
        self.store = ProfileStore(self.path)

    def tearDown(self):
        self.tmp.cleanup()

    def test_put_and_get_roundtrip(self):
        self.store.put("gaming", {"max-fps": "60", "no-audio": True})
        self.assertEqual(ProfileStore(self.path).get("gaming"), {"max-fps": "60", "no-audio": True})
        self.assertEqual(self.store.names(), ["gaming"])

    def test_update_merges(self):
        self.store.put("gaming", {"max-fps": "60"})
        merged = self.store.update("gaming", {"no-audio": True})
        self.assertEqual(merged, {"max-fps": "60", "no-audio": True})

    def test_delete(self):
        self.store.put("tmp", {"no-audio": True})
        self.assertTrue(self.store.delete("tmp"))
        self.assertFalse(self.store.delete("tmp"))

    def test_missing_file_is_empty_not_error(self):
        self.assertEqual(self.store.names(), [])

    def test_invalid_name_rejected(self):
        for bad in ("", "a" * 100, "bad/name", "bad\nname"):
            with self.subTest(name=bad):
                with self.assertRaises(InvalidProfileName):
                    self.store.put(bad, {})

    def test_export_import(self):
        self.store.put("gaming", {"max-fps": "60"})
        export_path = os.path.join(self.tmp.name, "export.json")
        self.store.export(export_path)
        other = ProfileStore(os.path.join(self.tmp.name, "other.json"))
        self.assertEqual(other.import_(export_path), 1)
        self.assertEqual(other.get("gaming"), {"max-fps": "60"})


class CliTestCase(unittest.TestCase):
    def run_cli(self, argv):
        buffer = io.StringIO()
        with redirect_stdout(buffer):
            code = main(argv)
        return code, buffer.getvalue()

    def test_options_json_lists_every_option(self):
        code, output = self.run_cli(["options", "--json"])
        self.assertEqual(code, 0)
        payload = json.loads(output)
        self.assertEqual(len(payload), 109)

    def test_options_search(self):
        code, output = self.run_cli(["options", "--search", "vaapi"])
        self.assertEqual(code, 0)
        self.assertIn("--hwdec", output)

    def test_check_ok(self):
        code, output = self.run_cli(["check", "--set", "video-bit-rate=16M", "--set", "no-audio"])
        self.assertEqual(code, 0)
        self.assertIn("--video-bit-rate=16M", output)
        self.assertIn("校验通过", output)

    def test_check_reports_conflict(self):
        code, output = self.run_cli(
            ["check", "--set", "camera-id=0", "--set", "camera-facing=front"]
        )
        self.assertEqual(code, 1)
        self.assertIn("互斥", output)

    def test_check_reports_phantom_option(self):
        code, output = self.run_cli(["check", "--set", "server-debugger"])
        self.assertEqual(code, 1)
        self.assertIn("从未存在", output)

    def test_run_print_only(self):
        code, output = self.run_cli(
            ["run", "--print", "--binary", "/usr/bin/scrcpy", "--set", "no-audio"]
        )
        self.assertEqual(code, 0)
        self.assertIn("scrcpy", output)
        self.assertIn("--no-audio", output)

    def test_run_with_unknown_option_returns_error(self):
        code, _ = self.run_cli(["run", "--print", "--set", "definitely-not-an-option=1"])
        self.assertEqual(code, 2)

    def test_extra_args_are_appended(self):
        code, output = self.run_cli(
            ["run", "--print", "--binary", "scrcpy", "--set", "no-audio",
             "--extra-args", "--some-future-flag"]
        )
        self.assertEqual(code, 0)
        self.assertTrue(output.strip().endswith("--some-future-flag"))

    def test_profiles_roundtrip_via_cli(self):
        with tempfile.TemporaryDirectory() as tmp:
            old = os.environ.get("XDG_CONFIG_HOME"), os.environ.get("APPDATA")
            os.environ["XDG_CONFIG_HOME"] = tmp
            os.environ["APPDATA"] = tmp
            try:
                code, _ = self.run_cli(["profiles", "save", "ci-test", "--set", "max-fps=30"])
                self.assertEqual(code, 0)
                code, output = self.run_cli(["profiles", "list"])
                self.assertEqual(code, 0)
                self.assertIn("ci-test", output)
                code, output = self.run_cli(["check", "--profile", "ci-test"])
                self.assertEqual(code, 0)
                self.assertIn("--max-fps=30", output)
            finally:
                for key, value in zip(("XDG_CONFIG_HOME", "APPDATA"), old):
                    if value is None:
                        os.environ.pop(key, None)
                    else:
                        os.environ[key] = value

    def test_missing_profile_reports_error(self):
        with self.assertRaises(SystemExit):
            main(["check", "--profile", "no-such-profile"])


if __name__ == "__main__":
    unittest.main()
