"""生成器的解析测试。

用一段合成的 cli.c 片段来验证解析逻辑，不依赖网络；
真正的「上游是否变化」由 .github/workflows/upstream-drift.yml 定时检查。
"""

import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from tools.gen_options import build_registry, diff_registries, parse_options  # noqa: E402

SAMPLE_CLI_C = '''
static const struct sc_option options[] = {
    {
        .longopt_id = OPT_VIDEO_CODEC,
        .longopt = "video-codec",
        .shortopt = 'c',
        .argdesc = "name",
        .text = "Select a video codec (h264, h265).\\n"
                "Default is h264.",
    },
    {
        .longopt_id = OPT_NO_AUDIO,
        .longopt = "no-audio",
        .text = "Disable audio.",
    },
    {
        .longopt_id = OPT_RECORD_FORMAT,
        .longopt = "record-format",
        .argdesc = "format",
        .text = "Force recording format.",
    },
    {
        .longopt_id = OPT_NEW_DISPLAY,
        .longopt = "new-display",
        .argdesc = "value",
        .optional_arg = true,
        .text = "Create a new display.",
    },
};

static enum sc_record_format
get_record_format(const char *name) {
    if (!strcmp(name, "mp4")) {
        return SC_RECORD_FORMAT_MP4;
    }
    if (!strcmp(name, "mkv")) {
        return SC_RECORD_FORMAT_MKV;
    }
    return 0;
}

static bool
parse_video_codec(const char *optarg, enum sc_codec *codec) {
    if (!strcmp(optarg, "h264")) {
        return true;
    }
    if (!strcmp(optarg, "h265")) {
        return true;
    }
    return false;
}

static bool
parse_record_format(const char *optarg, enum sc_record_format *format) {
    enum sc_record_format fmt = get_record_format(optarg);
    return true;
}

static bool
parse_args(int argc, char *argv[]) {
    while (true) {
        switch (c) {
            case OPT_VIDEO_CODEC:
                if (!parse_video_codec(optarg, &opts->video_codec)) {
                    return false;
                }
                break;
            case OPT_NO_AUDIO:
                opts->audio = false;
                break;
            case OPT_RECORD_FORMAT:
                if (!parse_record_format(optarg, &opts->record_format)) {
                    return false;
                }
                break;
            case OPT_NEW_DISPLAY:
                opts->new_display = true;
                break;
        }
    }
}
'''


class GeneratorTestCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.options = {item["long"]: item for item in parse_options(SAMPLE_CLI_C)}

    def test_all_options_found(self):
        self.assertEqual(
            sorted(self.options), ["new-display", "no-audio", "record-format", "video-codec"]
        )

    def test_flag_has_no_value(self):
        self.assertFalse(self.options["no-audio"]["takes_value"])
        self.assertIsNone(self.options["no-audio"]["argdesc"])

    def test_value_option_and_shortopt(self):
        codec = self.options["video-codec"]
        self.assertTrue(codec["takes_value"])
        self.assertEqual(codec["short"], "c")
        self.assertEqual(codec["argdesc"], "name")

    def test_help_text_joins_c_string_literals(self):
        self.assertEqual(
            self.options["video-codec"]["help"],
            "Select a video codec (h264, h265).\nDefault is h264.",
        )

    def test_optional_arg_detected(self):
        self.assertTrue(self.options["new-display"]["optional_arg"])

    def test_enum_extracted_directly(self):
        self.assertEqual(self.options["video-codec"]["enum"], ["h264", "h265"])

    def test_enum_extracted_through_helper_function(self):
        """record-format 的取值藏在 get_record_format() 里，需要跟一层。"""
        self.assertEqual(self.options["record-format"]["enum"], ["mp4", "mkv"])

    def test_registry_metadata(self):
        registry = build_registry(SAMPLE_CLI_C, "sample.c")
        self.assertEqual(registry["option_count"], 4)
        self.assertEqual(registry["source"], "sample.c")

    def test_diff_detects_additions_removals_and_enum_changes(self):
        old = {"options": [
            {"long": "no-audio", "enum": [], "argdesc": None},
            {"long": "old-option", "enum": [], "argdesc": None},
        ]}
        new = {"options": [
            {"long": "no-audio", "enum": [], "argdesc": None},
            {"long": "new-option", "enum": [], "argdesc": None},
            {"long": "record-format", "enum": ["mp4"], "argdesc": "format"},
        ]}
        changes = diff_registries(old, new)
        self.assertIn("+ --new-option", changes)
        self.assertIn("- --old-option", changes)
        self.assertIn("+ --record-format", changes)  # 新参数算「新增」而不是「变化」

    def test_no_diff_for_identical_registries(self):
        registry = build_registry(SAMPLE_CLI_C, "sample.c")
        self.assertEqual(diff_registries(registry, registry), [])


if __name__ == "__main__":
    unittest.main()
