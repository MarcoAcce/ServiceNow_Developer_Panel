from PySide6.QtWidgets import (
    QComboBox,
    QFormLayout,
    QLineEdit,
    QPushButton,
    QStackedWidget,
    QWidget,
)

from configuration.authentication_types import AUTHENTICATION_TYPES, AuthenticationType
from configuration.config_repository import Authentication
from ui.dialogs import CANCEL_LABEL, FramelessDialog, show_error
from ui.ui_widgets import hint_label, primary_button

DEFAULT_SCHEME: str = "https://"
INSTANCE_DIALOG_WIDTH: int = 460
AUTHENTICATION_DIALOG_WIDTH: int = 520
ADD_INSTANCE_TITLE: str = "Add instance"
ADD_AUTHENTICATION_TITLE: str = "Add authentication method"
EDIT_AUTHENTICATION_TITLE: str = "Edit authentication method"
INSTANCE_HINT: str = "The address is the base url of the instance, without any api path."
AUTHENTICATION_HINT: str = (
    "Credentials are encrypted before they are written to the local database."
)
MISSING_NAME_MESSAGE: str = "Enter a name for the instance."
MISSING_ADDRESS_MESSAGE: str = "Enter the address of the instance."
MISSING_FIELD_MESSAGE: str = "Enter a value for {label}."
INVALID_INPUT_TITLE: str = "Incomplete configuration"
SAVE_LABEL: str = "Save"


class InstanceDialog(FramelessDialog):

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(ADD_INSTANCE_TITLE, parent)
        self.setMinimumWidth(INSTANCE_DIALOG_WIDTH)
        self.name_field: QLineEdit = QLineEdit()
        self.address_field: QLineEdit = QLineEdit()
        self._build_ui()

    def values(self) -> tuple[str, str]:
        return self.name_field.text().strip(), _normalised_address(self.address_field.text())

    def accept(self) -> None:
        name, address = self.values()
        if not name:
            self._warn(MISSING_NAME_MESSAGE, self.name_field)
            return
        if not address:
            self._warn(MISSING_ADDRESS_MESSAGE, self.address_field)
            return
        super().accept()

    def _build_ui(self) -> None:
        self.content_layout.addWidget(hint_label(INSTANCE_HINT))
        form = QFormLayout()
        self.name_field.setPlaceholderText("Name shown in the panel, for example development")
        self.address_field.setPlaceholderText("https://example.service-now.com")
        form.addRow("Name", self.name_field)
        form.addRow("Address", self.address_field)
        self.content_layout.addLayout(form)
        self.add_button_row(*_form_buttons(self))

    def _warn(self, message: str, target: QLineEdit) -> None:
        show_error(self, INVALID_INPUT_TITLE, message)
        target.setFocus()


class AuthenticationDialog(FramelessDialog):

    def __init__(
        self, parent: QWidget | None = None, authentication: Authentication | None = None
    ) -> None:
        super().__init__(
            ADD_AUTHENTICATION_TITLE if authentication is None else EDIT_AUTHENTICATION_TITLE,
            parent,
        )
        self.setMinimumWidth(AUTHENTICATION_DIALOG_WIDTH)
        self.type_field: QComboBox = QComboBox()
        self._pages: QStackedWidget = QStackedWidget()
        self._fields: dict[tuple[str, str], QLineEdit] = {}
        self._build_ui()
        if authentication is not None:
            self._fill(authentication)

    def values(self) -> tuple[str, dict[str, str]]:
        authentication_type = self._selected_type()
        details: dict[str, str] = {}
        for field in authentication_type.fields:
            value = self._fields[(authentication_type.key, field.key)].text().strip()
            if value:
                details[field.key] = value
        return authentication_type.key, details

    def accept(self) -> None:
        authentication_type = self._selected_type()
        _, details = self.values()
        for field in authentication_type.fields:
            if field.required and not details.get(field.key):
                show_error(
                    self, INVALID_INPUT_TITLE, MISSING_FIELD_MESSAGE.format(label=field.label)
                )
                self._fields[(authentication_type.key, field.key)].setFocus()
                return
        super().accept()

    def _build_ui(self) -> None:
        self.content_layout.addWidget(hint_label(AUTHENTICATION_HINT))
        form = QFormLayout()
        for authentication_type in AUTHENTICATION_TYPES:
            self.type_field.addItem(authentication_type.label, authentication_type.key)
            self._pages.addWidget(self._build_page(authentication_type))
        self.type_field.currentIndexChanged.connect(self._pages.setCurrentIndex)
        form.addRow("Type", self.type_field)
        self.content_layout.addLayout(form)
        self.content_layout.addWidget(self._pages)
        self.add_button_row(*_form_buttons(self))
        self._pages.setCurrentIndex(0)

    def _build_page(self, authentication_type: AuthenticationType) -> QWidget:
        page = QWidget()
        layout = QFormLayout(page)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addRow(hint_label(authentication_type.description))
        for field in authentication_type.fields:
            editor = QLineEdit()
            editor.setPlaceholderText(field.placeholder)
            if field.secret:
                editor.setEchoMode(QLineEdit.EchoMode.Password)
            self._fields[(authentication_type.key, field.key)] = editor
            layout.addRow(field.label if field.required else f"{field.label} (optional)", editor)
        return page

    def _selected_type(self) -> AuthenticationType:
        return AUTHENTICATION_TYPES[max(self.type_field.currentIndex(), 0)]

    def _fill(self, authentication: Authentication) -> None:
        index = self.type_field.findData(authentication.authentication_type)
        if index >= 0:
            self.type_field.setCurrentIndex(index)
            self._pages.setCurrentIndex(index)
        for key, value in authentication.details.items():
            editor = self._fields.get((authentication.authentication_type, key))
            if editor is not None:
                editor.setText(value)


def _form_buttons(dialog: FramelessDialog) -> tuple[QPushButton, QPushButton]:
    cancel_button = QPushButton(CANCEL_LABEL)
    cancel_button.clicked.connect(dialog.reject)
    save_button = primary_button(SAVE_LABEL)
    save_button.setDefault(True)
    save_button.clicked.connect(dialog.accept)
    return cancel_button, save_button


def _normalised_address(text: str) -> str:
    address = text.strip().rstrip("/")
    if not address:
        return ""
    return address if "://" in address else f"{DEFAULT_SCHEME}{address}"
