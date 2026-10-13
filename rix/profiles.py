"""配置预设（profile）的读写。

预设解决的问题：每开一个新会话都要重填十几个字段。
存成 JSON，放在各平台约定的配置目录下。
"""

from __future__ import annotations

import json
import os
import re

APP_DIR_NAME = "rix-scrcpy"
NAME_RE = re.compile(r"^[\w\u4e00-\u9fff][\w\u4e00-\u9fff .-]{0,63}$")


def config_dir() -> str:
    if os.name == "nt":
        base = os.environ.get("APPDATA") or os.path.expanduser("~")
    else:
        base = os.environ.get("XDG_CONFIG_HOME") or os.path.join(os.path.expanduser("~"), ".config")
    return os.path.join(base, APP_DIR_NAME)


def profiles_path() -> str:
    return os.path.join(config_dir(), "profiles.json")


class InvalidProfileName(ValueError):
    pass


class ProfileStore:
    """极简的 profile 仓库：{名称: {参数名: 取值}}。"""

    def __init__(self, path: str | None = None):
        self.path = path or profiles_path()
        self._data: dict[str, dict] | None = None

    # ---- 读写 ----
    def load(self) -> dict[str, dict]:
        if self._data is None:
            try:
                with open(self.path, encoding="utf-8") as handle:
                    raw = json.load(handle)
                self._data = {name: dict(values) for name, values in raw.items() if isinstance(values, dict)}
            except (FileNotFoundError, json.JSONDecodeError, OSError):
                self._data = {}
        return self._data

    def flush(self) -> None:
        os.makedirs(os.path.dirname(self.path), exist_ok=True)
        with open(self.path, "w", encoding="utf-8") as handle:
            json.dump(self.load(), handle, ensure_ascii=False, indent=2, sort_keys=True)
            handle.write("\n")

    # ---- 操作 ----
    def names(self) -> list[str]:
        return sorted(self.load())

    def get(self, name: str) -> dict:
        return dict(self.load().get(name, {}))

    def put(self, name: str, values: dict) -> None:
        if not NAME_RE.match(name):
            raise InvalidProfileName(f"非法的预设名称: {name!r}（只允许字母/数字/中文/空格/._-，长度 1-64）")
        self.load()[name] = dict(values)
        self.flush()

    def update(self, name: str, values: dict) -> dict:
        """在已有预设上追加/覆盖若干参数。"""
        merged = self.get(name)
        merged.update(values)
        self.put(name, merged)
        return merged

    def delete(self, name: str) -> bool:
        data = self.load()
        if name in data:
            del data[name]
            self.flush()
            return True
        return False

    def export(self, path: str) -> None:
        with open(path, "w", encoding="utf-8") as handle:
            json.dump(self.load(), handle, ensure_ascii=False, indent=2, sort_keys=True)

    def import_(self, path: str) -> int:
        with open(path, encoding="utf-8") as handle:
            raw = json.load(handle)
        count = 0
        for name, values in raw.items():
            if isinstance(values, dict) and NAME_RE.match(name):
                self.load()[name] = dict(values)
                count += 1
        self.flush()
        return count
