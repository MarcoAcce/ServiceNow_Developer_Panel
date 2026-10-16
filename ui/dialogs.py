from PySide6.QtCore import QSize, Qt
from PySide6.QtWidgets import (
    QDialog,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from ui.icons import ERROR_ICON, WARNING_ICON, Tone, themed_icon
from ui.theme import current_theme
from ui.ui_widgets import danger_button, primary_button
from ui.window_frame import WindowFrame

MESSAGE_DIALOG_WIDTH: int = 440
CONTENT_MARGIN: int = 16
CONTENT_SPACING: int = 16
MESSAGE_SPACING: int = 12
BUTTON_SPACING: int = 8
MESSAGE_ICON_SIZE: int = 24
CONFIRM_LABEL: str = "Confirm"
CANCEL_LABEL: str = "Cancel"
CLOSE_LABEL: str = "Close"


class FramelessDialog(QDialog):

    def __init__(self, title: str, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowFlag(Qt.WindowType.FramelessWindowHint, True)
        self.setWindowTitle(title)
        self.setSizeGripEnabled(False)
        self._frame: WindowFrame = WindowFrame(self, resizable=False)
        content = QWidget()
        self.content_layout: QVBoxLayout = QVBoxLayout(content)
        self.content_layout.setContentsMargins(
            CONTENT_MARGIN, CONTENT_MARGIN, CONTENT_MARGIN, CONTENT_MARGIN
        )
        self.content_layout.setSpacing(CONTENT_SPACING)
        self._frame.set_body(content)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        layout.addWidget(self._frame)
        self._frame.title_bar.set_theme(current_theme())

    def add_button_row(self, *buttons: QPushButton) -> None:
        row = QHBoxLayout()
        row.setSpacing(BUTTON_SPACING)
        row.addStretch(1)
        for button in buttons:
            row.addWidget(button)
        self.content_layout.addLayout(row)


class MessageDialog(FramelessDialog):

    def __init__(
        self,
        title: str,
        message: str,
        parent: QWidget | None = None,
        icon: str | None = None,
        tone: Tone = Tone.SECONDARY,
    ) -> None:
        super().__init__(title, parent)
        self.setMinimumWidth(MESSAGE_DIALOG_WIDTH)
        self.content_layout.addLayout(self._build_message(message, icon, tone), 1)

    def _build_message(self, message: str, icon: str | None, tone: Tone) -> QHBoxLayout:
        layout = QHBoxLayout()
        layout.setSpacing(MESSAGE_SPACING)
        if icon is not None:
            layout.addWidget(self._build_icon(icon, tone), 0, Qt.AlignmentFlag.AlignTop)
        label = QLabel(message)
        label.setWordWrap(True)
        layout.addWidget(label, 1)
        return layout

    def _build_icon(self, icon: str, tone: Tone) -> QLabel:
        label = QLabel()
        label.setFixedSize(MESSAGE_ICON_SIZE, MESSAGE_ICON_SIZE)
        pixmap = themed_icon(icon, tone, MESSAGE_ICON_SIZE).pixmap(
            QSize(MESSAGE_ICON_SIZE, MESSAGE_ICON_SIZE)
        )
        label.setPixmap(pixmap)
        return label


class ConfirmationDialog(MessageDialog):

    def __init__(
        self,
        title: str,
        message: str,
        parent: QWidget | None = None,
        confirm_label: str = CONFIRM_LABEL,
        destructive: bool = False,
    ) -> None:
        super().__init__(title, message, parent, WARNING_ICON, Tone.SECONDARY)
        cancel_button = QPushButton(CANCEL_LABEL)
        cancel_button.setDefault(True)
        cancel_button.clicked.connect(self.reject)
        confirm_button = (
            danger_button(confirm_label) if destructive else primary_button(confirm_label)
        )
        confirm_button.clicked.connect(self.accept)
        self.add_button_row(cancel_button, confirm_button)


class ErrorDialog(MessageDialog):

    def __init__(self, title: str, message: str, parent: QWidget | None = None) -> None:
        super().__init__(title, message, parent, ERROR_ICON, Tone.DANGER)
        close_button = primary_button(CLOSE_LABEL)
        close_button.setDefault(True)
        close_button.clicked.connect(self.accept)
        self.add_button_row(close_button)


def ask_confirmation(
    parent: QWidget,
    title: str,
    message: str,
    confirm_label: str = CONFIRM_LABEL,
    destructive: bool = False,
) -> bool:
    dialog = ConfirmationDialog(title, message, parent, confirm_label, destructive)
    return dialog.exec() == QDialog.DialogCode.Accepted


def show_error(parent: QWidget, title: str, message: str) -> None:
    ErrorDialog(title, message, parent).exec()
