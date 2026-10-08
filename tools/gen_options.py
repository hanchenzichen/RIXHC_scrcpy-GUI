#!/usr/bin/env python3
"""从上游 scrcpy 的 `app/src/cli.c` 生成选项注册表。

为什么要自动生成：
    上游每个版本都会增删参数（5.0.1 有 109 个长参数）。手工在 UI 里维护这些
    参数必然跟不上——本项目就曾因此落后 32 个参数、还写错了一个从不存在的
    `--server-debugger`。把 `cli.c` 当作唯一事实来源后，UI 与 CLI 都由这份
    注册表驱动，「覆盖全部功能」变成构造上的保证。

提取内容：
    * 长参数名、短参数、取值说明（argdesc）、是否可选值
    * 帮助文本（把 C 的字符串拼接还原成一段话）
    * 枚举取值（顺着 switch 分支找到 parse_xxx()，再抓里面的 strcmp 字面量）

用法：
    python3 tools/gen_options.py                       # 从上游 master 生成
    python3 tools/gen_options.py --source path/to/cli.c
    python3 tools/gen_options.py --check               # CI 用：有漂移则退出码 1
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
import urllib.request

DEFAULT_SOURCE = (
    "https://raw.githubusercontent.com/Genymobile/scrcpy/master/app/src/cli.c"
)
REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DEFAULT_OUT = os.path.join(REPO_ROOT, "rix", "data", "options.generated.json")

ENTRY_RE = re.compile(r"\n    \{\n(.*?)\n    \},", re.S)
STRING_RE = re.compile(r'"((?:[^"\\]|\\.)*)"')


def fetch_source(source: str) -> str:
    if source.startswith(("http://", "https://")):
        with urllib.request.urlopen(source, timeout=60) as resp:  # noqa: S310
            return resp.read().decode("utf-8")
    with open(source, encoding="utf-8") as handle:
        return handle.read()


def unescape_c_string(text: str) -> str:
    return (
        text.replace("\\n", "\n")
        .replace('\\"', '"')
        .replace("\\t", "\t")
        .replace("\\\\", "\\")
    )


def join_c_strings(fragment: str) -> str:
    """把 C 源码里一串相邻的字符串字面量拼成一段文本。"""
    parts = STRING_RE.findall(fragment)
    return unescape_c_string("".join(parts))


def extract_options_block(text: str) -> str:
    start = text.index("static const struct sc_option options[] = {")
    end = text.index("\n};", start)
    return text[start:end]


def extract_switch_cases(text: str) -> dict[str, str]:
    """返回 {case 标签: case 体源码}，用于把参数与它的解析函数对上。"""
    # 直接定位到第一个 case OPT_... 的位置，比匹配 "switch (c) {" 更稳
    # （cli.c 里有多个 switch (c)，只有这个包含参数分支）
    start = text.index("\n            case OPT_")
    end = text.index("\n        }", start)
    body = text[start:end]
    cases: dict[str, str] = {}
    positions = [(m.start(), m.group(1)) for m in re.finditer(r"\n            case ([^:]+):", body)]
    for idx, (pos, label) in enumerate(positions):
        stop = positions[idx + 1][0] if idx + 1 < len(positions) else len(body)
        cases[label.strip()] = body[pos:stop]
    return cases


def extract_function_bodies(text: str) -> dict[str, str]:
    bodies: dict[str, str] = {}
    # 形如：parse_video_codec(const char *optarg, ...) {  ... }
    # 也覆盖 get_record_format(const char *name) 这类被间接调用的辅助函数
    # 允许函数签名换行（例如 parse_capture_orientation 的参数分了三行）
    pattern = r"\n(\w+)\(const char \*\w+[^{]*\{(.*?)\n\}"
    for match in re.finditer(pattern, text, re.S):
        bodies[match.group(1)] = match.group(2)
    return bodies


LITERAL_PATTERNS = (
    # 常规写法：if (!strcmp(optarg, "h264"))
    re.compile(r'strcmp\(\w+, "([^"]+)"\)'),
    # shortcut-mod 用的宏：STREQ("lctrl", item, len)
    re.compile(r'STREQ\("([^"]+)"'),
)


def _literals(body: str) -> list[str]:
    found: list[str] = []
    for pattern in LITERAL_PATTERNS:
        found.extend(pattern.findall(body))
    return found


def collect_enum_values(body: str, bodies: dict[str, str], depth: int = 0,
                        seen: set[str] | None = None) -> list[str]:
    """从函数体里收集合法取值，并顺着被调用的辅助函数再找几层。

    上游的解析函数有多种写法：
      * strcmp(optarg, "h264")            —— 最常见
      * strcmp(s, "0")                    —— 形参名不叫 optarg
      * get_record_format(optarg)         —— 再套一层辅助函数
      * STREQ("lctrl", item, len)         —— 宏
    所以这里既要放宽字面量匹配，也要做有限深度的函数内联。
    """
    if depth > 3 or not body:
        return []
    seen = seen if seen is not None else set()
    values = _literals(body)
    if values:
        return values
    for callee in re.findall(r"\b(\w+)\(", body):
        if callee in bodies and callee not in seen:
            seen.add(callee)
            nested = collect_enum_values(bodies[callee], bodies, depth + 1, seen)
            if nested:
                return nested
    return []


def parse_options(text: str) -> list[dict]:
    block = extract_options_block(text)
    cases = extract_switch_cases(text)
    bodies = extract_function_bodies(text)

    options: list[dict] = []
    for entry in ENTRY_RE.findall(block):
        longopt_match = re.search(r'\.longopt = "([^"]+)"', entry)
        if not longopt_match:
            continue
        longopt = longopt_match.group(1)
        shortopt_match = re.search(r"\.shortopt = '([^']+)'", entry)
        argdesc_match = re.search(r'\.argdesc = "([^"]*)"', entry)
        longopt_id_match = re.search(r"\.longopt_id = (OPT_\w+)", entry)

        text_match = re.search(r"\.text =", entry)
        help_text = join_c_strings(entry[text_match.end():]) if text_match else ""

        enum_values: list[str] = []
        if longopt_id_match:
            case_body = cases.get(longopt_id_match.group(1), "")
            for callee in re.findall(r"\b(parse_\w+)\(", case_body):
                enum_values = collect_enum_values(bodies.get(callee, ""), bodies)
                if enum_values:
                    break
            if not enum_values:
                enum_values = re.findall(r'strcmp\(optarg, "([^"]+)"\)', case_body)

        options.append(
            {
                "long": longopt,
                "short": shortopt_match.group(1) if shortopt_match else None,
                "argdesc": argdesc_match.group(1) if argdesc_match else None,
                "optional_arg": ".optional_arg = true" in entry,
                "takes_value": bool(argdesc_match),
                "enum": enum_values,
                "help": help_text.strip(),
            }
        )

    options.sort(key=lambda item: item["long"])
    return options


def build_registry(text: str, source: str) -> dict:
    options = parse_options(text)
    return {
        "schema": 1,
        "source": source,
        "option_count": len(options),
        "options": options,
    }


def diff_registries(old: dict, new: dict) -> list[str]:
    old_map = {item["long"]: item for item in old.get("options", [])}
    new_map = {item["long"]: item for item in new.get("options", [])}
    lines: list[str] = []
    for name in sorted(new_map.keys() - old_map.keys()):
        lines.append(f"+ --{name}")
    for name in sorted(old_map.keys() - new_map.keys()):
        lines.append(f"- --{name}")
    for name in sorted(old_map.keys() & new_map.keys()):
        before, after = old_map[name], new_map[name]
        if before.get("enum") != after.get("enum"):
            lines.append(f"~ --{name} 枚举: {before.get('enum')} -> {after.get('enum')}")
        if before.get("argdesc") != after.get("argdesc"):
            lines.append(f"~ --{name} 取值说明: {before.get('argdesc')} -> {after.get('argdesc')}")
    return lines


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="生成 scrcpy 选项注册表")
    parser.add_argument("--source", default=DEFAULT_SOURCE, help="cli.c 的路径或 URL")
    parser.add_argument("--out", default=DEFAULT_OUT, help="输出 JSON 路径")
    parser.add_argument("--check", action="store_true", help="仅检查是否有漂移（CI 用）")
    args = parser.parse_args(argv)

    text = fetch_source(args.source)
    registry = build_registry(text, args.source)

    if args.check:
        if not os.path.exists(args.out):
            print(f"缺少 {args.out}，请先运行 tools/gen_options.py 生成。")
            return 1
        with open(args.out, encoding="utf-8") as handle:
            committed = json.load(handle)
        changes = diff_registries(committed, registry)
        if changes:
            print("检测到上游 scrcpy 参数变化：")
            for line in changes:
                print("  " + line)
            return 1
        print(f"无变化（{registry['option_count']} 个参数）。")
        return 0

    os.makedirs(os.path.dirname(args.out), exist_ok=True)
    with open(args.out, "w", encoding="utf-8") as handle:
        json.dump(registry, handle, ensure_ascii=False, indent=2, sort_keys=True)
        handle.write("\n")
    print(f"已写入 {args.out}：{registry['option_count']} 个参数。")
    return 0


if __name__ == "__main__":
    sys.exit(main())
