"""由选项注册表自动渲染的「全部参数」面板。

为什么需要它：
    手写面板永远追不上上游（本项目就曾落后 32 个参数）。这个面板直接从
    `rix` 的选项注册表渲染控件，因此**上游新增参数时它自动出现**，
    GUI 从此和 CLI/TUI 一样做到「全参数覆盖」。

控件映射规则：
    * 无取值的开关  → 复选框
    * 有枚举取值    → 下拉框（第一项是「不设置」）
    * 其它有取值    → 单行输入框
"""

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (QCheckBox, QComboBox, QFormLayout, QGroupBox, QLabel,
                               QLineEdit, QScrollArea, QVBoxLayout, QWidget)

try:
    from rix.registry import load_registry
except ImportError:  # pragma: no cover - 源码被单独拷贝时的兜底
    load_registry = None

GROUP_TITLES = {
    "connection": "连接", "device": "设备状态", "video": "视频", "audio": "音频",
    "recording": "录制", "playback": "播放控制", "control": "交互控制", "input": "输入设备",
    "window": "窗口", "virtual-display": "虚拟显示", "v4l2": "V4L2（Linux）",
    "camera": "摄像头", "advanced": "高级", "misc": "其它",
}

UNSET_TEXT = "（不设置）"


class RegistryPanel(QWidget):
    """把注册表里的全部参数渲染成可勾选/可填写的控件。"""

    def __init__(self):
        super().__init__()
        self.registry = load_registry() if load_registry else None
        self._editors: dict[str, QWidget] = {}
        self.log_emitter = None

        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)

        if self.registry is None:
            layout.addWidget(QLabel("未能加载 rix 选项注册表（请确认已安装本项目）。"))
            return

        header = QLabel(
            f"由选项注册表自动生成，覆盖 scrcpy 全部 <b>{self.registry.option_count}</b> 个参数。"
            "这里的设置会与其它面板的设置合并，重复项以最后出现的为准。"
        )
        header.setWordWrap(True)
        layout.addWidget(header)

        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("过滤参数，例如 codec / camera / 90")
        self.search_input.textChanged.connect(self._apply_filter)
        layout.addWidget(self.search_input)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        container = QWidget()
        container_layout = QVBoxLayout(container)
        self._group_boxes: list[tuple[QGroupBox, list[tuple[QWidget, str]]]] = []

        for group, specs in self.registry.groups().items():
            box = QGroupBox(f"{GROUP_TITLES.get(group, group)}（{len(specs)}）")
            form = QFormLayout(box)
            rows: list[tuple[QWidget, str]] = []
            for spec in specs:
                editor = self._make_editor(spec)
                self._editors[spec.long] = editor
                label = QLabel(f"--{spec.long}")
                if spec.help:
                    label.setToolTip(spec.help)
                    editor.setToolTip(spec.help)
                form.addRow(label, editor)
                rows.append((label, spec.long))
                rows.append((editor, spec.long))
            self._group_boxes.append((box, rows))
            container_layout.addWidget(box)
        container_layout.addStretch()
        scroll.setWidget(container)
        layout.addWidget(scroll)

    # ---- 构建控件 ----
    def _make_editor(self, spec) -> QWidget:
        if spec.enum:
            combo = QComboBox()
            combo.addItem(UNSET_TEXT)
            for value in spec.enum:
                combo.addItem(value)
            return combo
        if not spec.takes_value:
            return QCheckBox()
        edit = QLineEdit()
        if spec.argdesc:
            edit.setPlaceholderText(f"<{spec.argdesc}>")
        return edit

    # ---- 过滤 ----
    def _apply_filter(self, text: str):
        needle = text.strip().lower().lstrip("-")
        for box, rows in self._group_boxes:
            visible = 0
            for widget, name in rows:
                matched = (not needle) or needle in name.lower()
                widget.setVisible(matched)
                if isinstance(widget, QLabel):
                    visible += 1 if matched else 0
            box.setVisible(visible > 0)

    # ---- 与其它面板相同的接口 ----
    def set_log_emitter(self, emitter):
        self.log_emitter = emitter

    def set_camera_mode(self, enabled: bool):
        """摄像头模式下 --display-id 无意义，直接禁用。"""
        editor = self._editors.get("display-id")
        if editor is not None:
            editor.setEnabled(not enabled)

    def current_values(self) -> dict:
        values: dict = {}
        for name, editor in self._editors.items():
            if isinstance(editor, QCheckBox):
                if editor.isChecked():
                    values[name] = True
            elif isinstance(editor, QComboBox):
                if editor.currentIndex() > 0:
                    values[name] = editor.currentText()
            elif isinstance(editor, QLineEdit):
                text = editor.text().strip()
                if text:
                    values[name] = text
        return values

    def get_args(self) -> list[str]:
        if self.registry is None:
            return []
        values = self.current_values()
        # build_argv 返回的第一项是 'scrcpy'，这里只要参数部分
        return self.registry.build_argv(values)[1:]
