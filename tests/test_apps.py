"""`scrcpy --list-apps` 输出解析的测试。

解析规则来自设备端 server 的实现（LogUtils.buildAppListMessage）：
    List of apps:
     - VLC                       org.videolan.vlc
     * Settings                  com.android.settings
名称按 30 列对齐，名称过长时包名换行缩进显示。
"""

import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from rix.apps import parse_app_list  # noqa: E402

SAMPLE = """List of apps:
 - VLC                       org.videolan.vlc
 * Settings                  com.android.settings
 - A Very Long Application Name That Wraps
   com.example.longpackage
 * Another System App        com.android.chrome
"""


class ParseAppListTestCase(unittest.TestCase):
    def setUp(self):
        self.apps = parse_app_list(SAMPLE)

    def test_all_entries_parsed(self):
        self.assertEqual(len(self.apps), 4)

    def test_names_and_packages(self):
        self.assertEqual(
            [(app["name"], app["package"]) for app in self.apps],
            [
                ("VLC", "org.videolan.vlc"),
                ("Settings", "com.android.settings"),
                ("A Very Long Application Name That Wraps", "com.example.longpackage"),
                ("Another System App", "com.android.chrome"),
            ],
        )

    def test_system_flag(self):
        self.assertEqual(
            [app["system"] for app in self.apps],
            [False, True, False, True],
        )

    def test_ignores_noise_lines(self):
        text = "Processing Android apps... (this may take some time)\n" + SAMPLE
        self.assertEqual(len(parse_app_list(text)), 4)

    def test_empty_output_gives_empty_list(self):
        self.assertEqual(parse_app_list(""), [])
        self.assertEqual(parse_app_list("List of apps:\n"), [])

    def test_entry_without_package_is_dropped(self):
        self.assertEqual(parse_app_list("List of apps:\n - Broken Name\n"), [])

    def test_second_line_package_attaches_to_previous_entry(self):
        text = "List of apps:\n - Long Name Goes Here\n   com.example.attached\n"
        apps = parse_app_list(text)
        self.assertEqual(len(apps), 1)
        self.assertEqual(apps[0]["package"], "com.example.attached")
        self.assertEqual(apps[0]["name"], "Long Name Goes Here")


if __name__ == "__main__":
    unittest.main()
