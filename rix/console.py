"""控制台输出编码处理。

背景：
    Windows 上 Python 的 stdout/stderr 在**非控制台**（管道、重定向、CI）场景下
    使用系统 ANSI 代码页（英文系统 cp1252、中文系统 cp936），无法编码中文时会直接抛
    `UnicodeEncodeError` 并让整个程序崩溃。CI 的 Windows 运行器就是这种情况：
    GUI 无头自检本身通过了，却在最后打印结果时挂掉。

处理方式：
    在程序入口把标准输出切换为 UTF-8 且 `errors="replace"`，这样：
      * 能编码的字符正常输出；
      * 不能编码的字符退化为替代符号，而不是让程序崩溃。
"""

from __future__ import annotations

import sys


def enable_utf8_output() -> None:
    """把 stdout/stderr 切到 UTF-8。可重复调用，失败时静默忽略。"""
    for stream in (sys.stdout, sys.stderr):
        reconfigure = getattr(stream, "reconfigure", None)
        if reconfigure is None:  # 已被重定向为不支持 reconfigure 的对象
            continue
        try:
            reconfigure(encoding="utf-8", errors="replace")
        except (ValueError, OSError):  # pragma: no cover - 平台相关
            pass
