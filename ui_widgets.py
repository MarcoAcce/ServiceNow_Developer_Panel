from PySide6.QtWidgets import (
    QFrame,
    QLabel,
    QPlainTextEdit,
    QPushButton,
    QSizePolicy,
    QWidget,
)

from theme import Role, refresh_role, set_role

RULE_HEIGHT: int = 1


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
