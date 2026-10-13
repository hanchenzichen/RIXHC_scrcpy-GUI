"""注册表的回归测试。

这些测试同时扮演「文档」的角色：把「上游有哪些参数、哪些枚举」钉死在这里，
一旦注册表被改坏（或上游改了取值），CI 立刻会红。
"""

import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from rix.registry import (  # noqa: E402
    UnknownOptionError,
    load_registry,
    parse_assignments,
)


class RegistryTestCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.registry = load_registry()

    def test_option_count_matches_upstream(self):
        # scrcpy 5.0.1 的 cli.c 里共有 109 个长参数
        self.assertEqual(self.registry.option_count, 109)

    def test_enum_values_are_extracted(self):
        """枚举值来自上游 parse_xxx()，这里锁定几个关键项。"""
        expected = {
            "video-codec": ["h264", "h265", "av1", "vp8", "vp9"],
            "audio-codec": ["opus", "aac", "flac", "raw"],
            "record-format": ["mp4", "mkv", "m4a", "mka", "opus", "aac", "flac", "wav"],
            "keyboard": ["disabled", "sdk", "uhid", "aoa"],
            "mouse": ["disabled", "sdk", "uhid", "aoa"],
            "gamepad": ["disabled", "uhid", "aoa"],
            "shortcut-mod": ["lctrl", "rctrl", "lalt", "ralt", "lsuper", "rsuper"],
            "hwdec": ["auto", "disabled", "vaapi", "d3d11va", "videotoolbox"],
            "render-fit": ["letterbox", "stretched", "unscaled"],
            "camera-facing": ["front", "back", "external"],
            "display-ime-policy": ["local", "fallback", "hide"],
        }
        for name, values in expected.items():
            with self.subTest(option=name):
                self.assertEqual(self.registry.get(name).enum, values)

    def test_audio_source_has_eleven_values(self):
        self.assertEqual(len(self.registry.get("audio-source").enum), 11)

    def test_phantom_option_is_rejected_with_hint(self):
        """--server-debugger 从未存在于 scrcpy，必须给出明确提示。"""
        with self.assertRaises(UnknownOptionError) as ctx:
            self.registry.get("server-debugger")
        self.assertIn("从未存在", str(ctx.exception))

    def test_newly_added_options_are_present(self):
        """这些是早期版本漏掉、现在必须覆盖的参数。"""
        for name in ("capture-orientation", "record-orientation", "angle", "flex-display",
                     "camera-zoom", "camera-torch", "keep-active", "hwdec", "render-fit",
                     "video-codec-options", "list-apps", "tcpip", "kill-adb-on-close"):
            with self.subTest(option=name):
                self.assertIn(name, self.registry)

    def test_build_argv_is_sorted_and_renders_values(self):
        argv = self.registry.build_argv(
            {"video-bit-rate": "16M", "no-audio": True, "capture-orientation": "90"},
            ["--serial", "abc"],
        )
        self.assertEqual(
            argv,
            ["scrcpy", "--capture-orientation=90", "--no-audio",
             "--video-bit-rate=16M", "--serial", "abc"],
        )

    def test_build_argv_skips_false_and_empty(self):
        argv = self.registry.build_argv({"no-audio": False, "max-fps": "", "max-size": None})
        self.assertEqual(argv, ["scrcpy"])

    def test_optional_value_option(self):
        """--new-display 的值是可选的。"""
        self.assertTrue(self.registry.get("new-display").optional_arg)
        self.assertEqual(self.registry.build_argv({"new-display": "1920x1080/420"}),
                         ["scrcpy", "--new-display=1920x1080/420"])
        self.assertEqual(self.registry.build_argv({"new-display": True}),
                         ["scrcpy", "--new-display"])

    def test_validate_reports_conflicts_and_dependencies(self):
        warnings = self.registry.validate({
            "camera-id": "0",
            "camera-facing": "front",
            "record-format": "mkv",
            "server-debugger": True,
        })
        joined = " | ".join(warnings)
        self.assertIn("互斥", joined)
        self.assertIn("需要同时设置 --record", joined)
        self.assertIn("从未存在", joined)

    def test_validate_rejects_bad_enum_value(self):
        warnings = self.registry.validate({"video-codec": "h266"})
        self.assertTrue(any("不是有效取值" in warning for warning in warnings))

    def test_validate_accepts_valid_combination(self):
        self.assertEqual(
            self.registry.validate({"video-codec": "vp9", "max-fps": "60", "no-audio": True}),
            [],
        )

    def test_groups_cover_every_option(self):
        grouped = sum(len(items) for items in self.registry.groups().values())
        self.assertEqual(grouped, self.registry.option_count)

    def test_search_matches_name_help_and_enum(self):
        self.assertTrue(any(spec.long == "video-codec" for spec in self.registry.search("codec")))
        self.assertTrue(any(spec.long == "hwdec" for spec in self.registry.search("vaapi")))

    def test_parse_assignments(self):
        self.assertEqual(
            parse_assignments(["video-bit-rate=16M", "no-audio", "--max-fps=60"]),
            {"video-bit-rate": "16M", "no-audio": True, "max-fps": "60"},
        )


if __name__ == "__main__":
    unittest.main()
