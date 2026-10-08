"""GUI 面板的结构检查（纯 ast，不需要 Qt，可在任何环境运行）。

存在意义：沙箱/CI 上不一定装得上 PySide6，但「面板的 get_args() 必须返回列表」
这类结构性错误完全可以用静态分析抓住。这个测试就是为了守住一个真实踩过的坑——
删代码时把 `return args` 误缩进进了 if 分支，函数于是隐式返回 None，
GUI 直接拼不出命令行。
"""

import ast
import glob
import os
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PANEL_GLOB = os.path.join(ROOT, "features", "*.py")
# device_panel.get_args() 的契约特殊：没选设备时返回 None 表示「选择不合法」
NONE_ALLOWED = {"DevicePanel"}


def iter_panel_classes():
    for path in sorted(glob.glob(PANEL_GLOB)):
        with open(path, encoding="utf-8") as handle:
            tree = ast.parse(handle.read(), filename=path)
        for node in tree.body:
            if isinstance(node, ast.ClassDef):
                yield os.path.basename(path), node


class PanelStructureTestCase(unittest.TestCase):
    def test_every_panel_defines_get_args(self):
        missing = []
        for filename, cls in iter_panel_classes():
            if not any(isinstance(item, ast.FunctionDef) and item.name == "get_args"
                       for item in cls.body):
                missing.append(f"{filename}:{cls.name}")
        self.assertEqual(missing, [], f"这些面板缺少 get_args(): {missing}")

    def test_get_args_last_statement_is_a_return(self):
        """最后一句必须是 return，否则函数会隐式返回 None。"""
        broken = []
        for filename, cls in iter_panel_classes():
            for item in cls.body:
                if isinstance(item, ast.FunctionDef) and item.name == "get_args":
                    if not isinstance(item.body[-1], ast.Return):
                        broken.append(f"{filename}:{cls.name}")
        self.assertEqual(
            broken, [],
            f"这些面板的 get_args() 最后一句不是 return（会隐式返回 None）: {broken}",
        )

    def test_get_args_returns_the_local_list(self):
        """必须返回函数内定义的 args 变量，避免误返回别的对象。"""
        suspicious = []
        for filename, cls in iter_panel_classes():
            for item in cls.body:
                if isinstance(item, ast.FunctionDef) and item.name == "get_args":
                    last = item.body[-1]
                    value = last.value if isinstance(last, ast.Return) else None
                    # 允许：返回局部 args、返回下标表达式（注册表面板）、
                    #       返回字面量列表（device_panel 的 -d/-e）、返回 None
                    allowed = (
                        value is None
                        or (isinstance(value, ast.Name) and value.id == "args")
                        or isinstance(value, (ast.Subscript, ast.List, ast.Constant))
                    )
                    if not allowed:
                        suspicious.append(f"{filename}:{cls.name}")
        self.assertEqual(suspicious, [], f"这些面板的 get_args() 返回值可疑: {suspicious}")

    def test_registry_panel_matches_registry_size(self):
        """注册表面板必须真的覆盖全部参数（源码级检查，避免漏渲染）。"""
        path = os.path.join(ROOT, "features", "registry_panel.py")
        if not os.path.isfile(path):
            self.skipTest("没有注册表面板")
        with open(path, encoding="utf-8") as handle:
            source = handle.read()
        self.assertIn("self.registry.groups()", source)
        self.assertIn("self._editors[spec.long] = editor", source)

    def test_no_phantom_option_in_panels(self):
        """--server-debugger 从未存在于 scrcpy，任何面板都不该再引用它。"""
        offenders = []
        for path in sorted(glob.glob(PANEL_GLOB)):
            with open(path, encoding="utf-8") as handle:
                text = handle.read()
            # 允许出现在注释/说明文字里，但不允许出现在 args.append/extend 中
            for line in text.splitlines():
                stripped = line.strip()
                if stripped.startswith("#") or "从未存在" in line:
                    continue
                if "server-debugger" in line and ("append" in line or "extend" in line):
                    offenders.append(f"{os.path.basename(path)}: {stripped}")
        self.assertEqual(offenders, [], f"仍在拼装幽灵参数: {offenders}")


if __name__ == "__main__":
    unittest.main()
