from collections.abc import Sequence

from PySide6.QtCore import QPoint, QSizeF, Qt
from PySide6.QtGui import QGuiApplication, QResizeEvent, QTextOption
from PySide6.QtWidgets import (
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QPlainTextEdit,
    QPushButton,
    QSizePolicy,
    QToolTip,
    QVBoxLayout,
    QWidget,
)

from ui.icons import COPY_ICON, IconButton, Tone
from ui.theme import Role, set_role
from ui.ui_widgets import hint_label, section_label

TITLE_WIDTH: int = 150
ROW_SPACING: int = 8
DETAIL_SPACING: int = 4
CHOICE_COLUMN_SPACING: int = 16
CHOICE_ROW_SPACING: int = 2
COPIED_TEXT: str = "Copied to the clipboard"
COPY_TOOLTIP: str = "Copy {title} to the clipboard"
COPY_CHOICE_TOOLTIP: str = "Copy the value {value} to the clipboard"
CHOICE_COUNT_TITLE: str = "{title} ({count})"
CHOICE_HEADERS: tuple[str, ...] = ("Value", "Label", "Dependent value")
DEPENDENT_COLUMN: int = 2
FILL_COLUMN: int = 4


def copy_to_clipboard(text: str, anchor: QWidget) -> None:
    clipboard = QGuiApplication.clipboard()
    if clipboard is None:
        return
    clipboard.setText(text)
    QToolTip.showText(anchor.mapToGlobal(QPoint(0, anchor.height())), COPIED_TEXT, anchor)


def detail_title(text: str) -> QLabel:
    label = section_label(text)
    label.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop)
    return label


class CopyButton(IconButton):

    def __init__(self, tooltip: str) -> None:
        super().__init__(COPY_ICON, tooltip, Tone.SECONDARY)
        self._content: str = ""
        self.clicked.connect(lambda: copy_to_clipboard(self._content, self))

    def set_content(self, content: str) -> None:
        self._content = content


class CodeBlock(QPlainTextEdit):

    def __init__(self) -> None:
        super().__init__()
        self.setReadOnly(True)
        self.setLineWrapMode(QPlainTextEdit.LineWrapMode.WidgetWidth)
        self.setWordWrapMode(QTextOption.WrapMode.WrapAtWordBoundaryOrAnywhere)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        set_role(self, Role.MONOSPACE)
        layout = self.document().documentLayout()
        layout.documentSizeChanged.connect(self._on_size_changed)

    def set_code(self, text: str) -> None:
        self.setPlainText(text)
        self._fit_height()

    def resizeEvent(self, event: QResizeEvent) -> None:
        super().resizeEvent(event)
        self._fit_height()

    def _on_size_changed(self, size: QSizeF) -> None:
        self._fit_height()

    def _fit_height(self) -> None:
        lines = max(1, int(self.document().documentLayout().documentSize().height()))
        margin = int(2 * self.document().documentMargin())
        overhead = self.height() - self.viewport().height()
        height = lines * self.fontMetrics().lineSpacing() + margin + overhead
        if height != self.height():
            self.setFixedHeight(height)


class InlineDetail(QWidget):

    def __init__(self, title: str, copyable: bool = False) -> None:
        super().__init__()
        self.value_label: QLabel = QLabel()
        self.copy_button: CopyButton | None = (
            CopyButton(COPY_TOOLTIP.format(title=title.lower())) if copyable else None
        )
        self._layout: QHBoxLayout = QHBoxLayout(self)
        self._layout.setContentsMargins(0, 0, 0, 0)
        self._layout.setSpacing(ROW_SPACING)
        title_label = detail_title(title)
        title_label.setFixedWidth(TITLE_WIDTH)
        self.value_label.setWordWrap(True)
        self.value_label.setTextInteractionFlags(
            Qt.TextInteractionFlag.TextSelectableByMouse
        )
        self._layout.addWidget(title_label, 0, Qt.AlignmentFlag.AlignTop)
        self._layout.addWidget(self.value_label, 0, Qt.AlignmentFlag.AlignVCenter)
        if self.copy_button is not None:
            self._layout.addWidget(self.copy_button, 0, Qt.AlignmentFlag.AlignVCenter)
        self._layout.addStretch(1)

    def add_action(self, button: QPushButton) -> None:
        self._layout.insertWidget(self._layout.count() - 1, button)

    def set_value(self, value: str) -> None:
        self.value_label.setText(value)
        if self.copy_button is not None:
            self.copy_button.set_content(value)
        self.setVisible(bool(value))


class CodeDetail(QWidget):

    def __init__(self, title: str) -> None:
        super().__init__()
        self.code_block: CodeBlock = CodeBlock()
        self.copy_button: CopyButton = CopyButton(COPY_TOOLTIP.format(title=title.lower()))
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(DETAIL_SPACING)
        header = QHBoxLayout()
        header.setContentsMargins(0, 0, 0, 0)
        header.setSpacing(ROW_SPACING)
        header.addWidget(detail_title(title))
        header.addWidget(self.copy_button)
        header.addStretch(1)
        layout.addLayout(header)
        layout.addWidget(self.code_block)

    def set_value(self, value: str) -> None:
        self.code_block.set_code(value)
        self.copy_button.set_content(value)
        self.setVisible(bool(value))


class ChoiceDetail(QWidget):

    def __init__(self, title: str) -> None:
        super().__init__()
        self._title: str = title
        self.title_label: QLabel = detail_title(title)
        self._grid_widget: QWidget = QWidget()
        self._grid: QGridLayout = QGridLayout(self._grid_widget)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(DETAIL_SPACING)
        layout.addWidget(self.title_label)
        self._grid.setContentsMargins(0, 0, 0, 0)
        self._grid.setHorizontalSpacing(CHOICE_COLUMN_SPACING)
        self._grid.setVerticalSpacing(CHOICE_ROW_SPACING)
        self._grid.setColumnStretch(FILL_COLUMN, 1)
        layout.addWidget(self._grid_widget)

    def set_choices(self, choices: Sequence[tuple[str, str, str]]) -> None:
        self._clear()
        self.title_label.setText(CHOICE_COUNT_TITLE.format(title=self._title, count=len(choices)))
        dependent = any(choice[DEPENDENT_COLUMN] for choice in choices)
        headers = CHOICE_HEADERS if dependent else CHOICE_HEADERS[:DEPENDENT_COLUMN]
        for column, header in enumerate(headers):
            self._grid.addWidget(hint_label(header), 0, column)
        for row, choice in enumerate(choices, start=1):
            value, label, dependent_value = choice
            cells = (value, label, dependent_value) if dependent else (value, label)
            for column, text in enumerate(cells):
                cell = QLabel(text)
                cell.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
                self._grid.addWidget(cell, row, column)
            button = CopyButton(COPY_CHOICE_TOOLTIP.format(value=value))
            button.set_content(value)
            self._grid.addWidget(button, row, len(cells))
        self.setVisible(bool(choices))

    def _clear(self) -> None:
        while self._grid.count():
            item = self._grid.takeAt(0)
            widget = item.widget() if item is not None else None
            if widget is not None:
                widget.setParent(None)
                widget.deleteLater()
