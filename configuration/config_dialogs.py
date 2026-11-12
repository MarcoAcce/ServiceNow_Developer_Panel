from PySide6.QtWidgets import (
    QComboBox,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QStackedWidget,
    QWidget,
)

from configuration.authentication_types import (
    AUTHENTICATION_TYPES,
    OAUTH_AUTHENTICATION,
    AuthenticationField,
    AuthenticationType,
)
from configuration.config_repository import Authentication, Instance
from configuration.login_runner import LoginRunner
from core.oauth import ACCESS_TOKEN_KEY, USER_KEY
from services.oauth_tokens import LoginState
from ui.dialogs import CANCEL_LABEL, FramelessDialog, show_error
from ui.ui_widgets import hint_label, primary_button, show_status

DEFAULT_SCHEME: str = "https://"
INSTANCE_DIALOG_WIDTH: int = 460
AUTHENTICATION_DIALOG_WIDTH: int = 560
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
LOGIN_LABEL: str = "Login"
CHECKING_MESSAGE: str = "Checking the stored tokens on the instance..."
LOGGED_IN_MESSAGE: str = "Logged in as {user}. Save to keep the tokens."
TOKEN_ACCEPTED_MESSAGE: str = "The instance accepted the token. Save to keep the tokens."
LOGIN_CANCELLED_MESSAGE: str = "The login was cancelled."
LOGIN_BEFORE_SAVE_MESSAGE: str = (
    "Use Login to log in to the instance before saving a new OAuth method."
)
STORED_USER_MESSAGE: str = "Last login: {user}."
LOGIN_SPACING: int = 10


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
        self,
        instance: Instance,
        parent: QWidget | None = None,
        authentication: Authentication | None = None,
    ) -> None:
        super().__init__(
            ADD_AUTHENTICATION_TITLE if authentication is None else EDIT_AUTHENTICATION_TITLE,
            parent,
        )
        self.setMinimumWidth(AUTHENTICATION_DIALOG_WIDTH)
        self._instance: Instance = instance
        self._authentication: Authentication | None = authentication
        self._runner: LoginRunner = LoginRunner(self)
        self.type_field: QComboBox = QComboBox()
        self.login_button: QPushButton = QPushButton(LOGIN_LABEL)
        self.login_status: QLabel = QLabel()
        self._pages: QStackedWidget = QStackedWidget()
        self._fields: dict[tuple[str, str], QLineEdit] = {}
        self._hidden: dict[tuple[str, str], str] = {}
        self._build_ui()
        if authentication is not None:
            self._fill(authentication)

    def values(self) -> tuple[str, dict[str, str]]:
        authentication_type = self._selected_type()
        return authentication_type.key, self._details_of(authentication_type)

    def accept(self) -> None:
        missing = self._missing_field(self._selected_type())
        if missing is not None:
            self._warn_missing(missing)
            return
        if self._login_missing():
            show_error(self, INVALID_INPUT_TITLE, LOGIN_BEFORE_SAVE_MESSAGE)
            self.login_button.setFocus()
            return
        super().accept()

    def _login_missing(self) -> bool:
        if self._authentication is not None:
            return False
        if self._selected_type().key != OAUTH_AUTHENTICATION.key:
            return False
        return not self._hidden.get((OAUTH_AUTHENTICATION.key, ACCESS_TOKEN_KEY), "").strip()

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
        for field in authentication_type.editable_fields:
            editor = QLineEdit()
            editor.setPlaceholderText(field.placeholder)
            if field.secret:
                editor.setEchoMode(QLineEdit.EchoMode.Password)
            self._fields[(authentication_type.key, field.key)] = editor
            layout.addRow(field.label if field.required else f"{field.label} (optional)", editor)
        if authentication_type.key == OAUTH_AUTHENTICATION.key:
            layout.addRow(self._build_login_row())
        return page

    def _build_login_row(self) -> QWidget:
        row = QWidget()
        layout = QHBoxLayout(row)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(LOGIN_SPACING)
        self.login_button.setAutoDefault(False)
        self.login_button.clicked.connect(self._on_login_clicked)
        self._runner.succeeded.connect(self._on_login_succeeded)
        self._runner.failed.connect(self._on_login_failed)
        self._runner.cancelled.connect(self._on_login_cancelled)
        self.login_status.setWordWrap(True)
        layout.addWidget(self.login_button)
        layout.addWidget(self.login_status, 1)
        return row

    def _selected_type(self) -> AuthenticationType:
        return AUTHENTICATION_TYPES[max(self.type_field.currentIndex(), 0)]

    def _details_of(self, authentication_type: AuthenticationType) -> dict[str, str]:
        details: dict[str, str] = {}
        for field in authentication_type.fields:
            key = (authentication_type.key, field.key)
            if field.hidden:
                value = self._hidden.get(key, "").strip()
            else:
                value = self._fields[key].text().strip()
            if value:
                details[field.key] = value
        return details

    def _missing_field(self, authentication_type: AuthenticationType) -> AuthenticationField | None:
        for field in authentication_type.editable_fields:
            editor = self._fields[(authentication_type.key, field.key)]
            if field.required and not editor.text().strip():
                return field
        return None

    def _warn_missing(self, field: AuthenticationField) -> None:
        show_error(self, INVALID_INPUT_TITLE, MISSING_FIELD_MESSAGE.format(label=field.label))
        self._fields[(self._selected_type().key, field.key)].setFocus()

    def _fill(self, authentication: Authentication) -> None:
        index = self.type_field.findData(authentication.authentication_type)
        if index >= 0:
            self.type_field.setCurrentIndex(index)
            self._pages.setCurrentIndex(index)
        definition = authentication.type_definition()
        for key, value in authentication.details.items():
            editor = self._fields.get((authentication.authentication_type, key))
            if editor is not None:
                editor.setText(value)
                continue
            field = definition.field_of_key(key) if definition is not None else None
            if field is not None and field.hidden:
                self._hidden[(authentication.authentication_type, key)] = value
        user = self._hidden.get((OAUTH_AUTHENTICATION.key, USER_KEY), "")
        if user:
            show_status(self.login_status, STORED_USER_MESSAGE.format(user=user))

    def _on_login_clicked(self) -> None:
        if self._runner.is_running():
            return
        missing = self._missing_field(OAUTH_AUTHENTICATION)
        if missing is not None:
            self._warn_missing(missing)
            return
        self.login_button.setEnabled(False)
        show_status(self.login_status, CHECKING_MESSAGE)
        self._runner.start(self._instance, self._details_of(OAUTH_AUTHENTICATION))

    def _on_login_succeeded(self, state: object) -> None:
        self.login_button.setEnabled(True)
        if isinstance(state, LoginState):
            self._apply_login(state)

    def _on_login_failed(self, message: str) -> None:
        self.login_button.setEnabled(True)
        show_status(self.login_status, message, failed=True)

    def _on_login_cancelled(self) -> None:
        self.login_button.setEnabled(True)
        show_status(self.login_status, LOGIN_CANCELLED_MESSAGE)

    def _apply_login(self, state: LoginState) -> None:
        for field in OAUTH_AUTHENTICATION.hidden_fields:
            key = (OAUTH_AUTHENTICATION.key, field.key)
            self._hidden[key] = state.details.get(field.key, "")
        message = TOKEN_ACCEPTED_MESSAGE
        if state.user:
            message = LOGGED_IN_MESSAGE.format(user=state.user)
        show_status(self.login_status, message)


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
