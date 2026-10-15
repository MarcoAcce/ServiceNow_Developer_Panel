from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QAbstractItemView,
    QFrame,
    QLabel,
    QPlainTextEdit,
    QPushButton,
    QSizePolicy,
    QTableWidget,
    QTableWidgetItem,
    QWidget,
)

from theme import Role, refresh_role, set_role

RULE_HEIGHT: int = 1
ELLIPSIS: str = "..."


def shorten_text(text: str, limit: int) -> str:
    return text if len(text) <= limit else f"{text[:limit]}{ELLIPSIS}"


def title_label(text: str, point_size_delta: int = 4) -> QLabel:
    label = QLabel(text)
    font = label.font()
    font.setBold(True)
    font.setPointSize(font.pointSize() + point_size_delta)
    label.setFont(font)
    set_role(label, Role.TITLE)
    return label


def section_label(text: str) -> QLabel:
    label = QLabel(text)
    font = label.font()
    font.setBold(True)
    label.setFont(font)
    set_role(label, Role.SECTION)
    return label


def hint_label(text: str) -> QLabel:
    label = QLabel(text)
    label.setWordWrap(True)
    set_role(label, Role.HINT)
    return label


def show_status(label: QLabel, text: str, failed: bool = False) -> None:
    refresh_role(label, Role.ERROR if failed else Role.HINT)
    label.setText(text)


def primary_button(text: str) -> QPushButton:
    button = QPushButton(text)
    set_role(button, Role.PRIMARY)
    return button


def danger_button(text: str) -> QPushButton:
    button = QPushButton(text)
    set_role(button, Role.DANGER)
    return button


def as_card(widget: QWidget) -> None:
    set_role(widget, Role.CARD)


def as_row(widget: QWidget) -> None:
    set_role(widget, Role.ROW)


def script_view(placeholder: str = "") -> QPlainTextEdit:
    view = QPlainTextEdit()
    view.setReadOnly(True)
    view.setLineWrapMode(QPlainTextEdit.LineWrapMode.NoWrap)
    view.setPlaceholderText(placeholder)
    set_role(view, Role.MONOSPACE)
    return view


def script_editor(placeholder: str = "") -> QPlainTextEdit:
    editor = QPlainTextEdit()
    editor.setLineWrapMode(QPlainTextEdit.LineWrapMode.NoWrap)
    editor.setPlaceholderText(placeholder)
    set_role(editor, Role.MONOSPACE)
    return editor


def horizontal_rule() -> QFrame:
    rule = QFrame()
    rule.setFrameShape(QFrame.Shape.NoFrame)
    rule.setFixedHeight(RULE_HEIGHT)
    set_role(rule, Role.RULE)
    return rule


def vertical_spacer() -> QWidget:
    spacer = QWidget()
    spacer.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Expanding)
    return spacer


def configure_table(widget: QTableWidget) -> None:
    widget.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
    widget.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
    widget.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
    widget.setAlternatingRowColors(True)
    widget.setSortingEnabled(False)
    widget.verticalHeader().setVisible(False)
    widget.horizontalHeader().setStretchLastSection(True)


def check_item(checked: bool) -> QTableWidgetItem:
    item = QTableWidgetItem()
    item.setFlags(Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsSelectable)
    item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
    item.setCheckState(
        Qt.CheckState.Checked if checked else Qt.CheckState.Unchecked
    )
    return item
