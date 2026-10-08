"""RIX Scrcpy 的核心逻辑（无 GUI 依赖）。

设计原则：
    * 本包**绝不** import PySide6 —— 这样 CLI / TUI / 未来的 Android 远程前端
      都能直接复用，也让单元测试可以在没有图形环境的 CI 上跑。
    * 选项模型来自 `data/options.generated.json`（由 tools/gen_options.py 从上游
      scrcpy 的 cli.c 生成），保证「覆盖全部功能」是构造上的结果。
"""

__version__ = "1.1.0"

__all__ = ["__version__"]
