import sqlite3

from PySide6.QtCore import Signal
from PySide6.QtWidgets import QComboBox, QFormLayout, QHBoxLayout, QLabel, QPushButton, QWidget

from configuration.authentication_types import is_oauth, masked_details, type_label
from configuration.config_repository import Authentication, ConfigRepository, Instance
from configuration.login_runner import LoginRunner
from core.database_manager import DatabaseError
from core.oauth import USER_KEY
from core.secret_store import SecretError
from services.oauth_tokens import LoginState
from services.service import NO_AUTHENTICATION_LABEL, RequestTarget
from ui.dialogs import show_error
from ui.ui_widgets import hint_label, section_label

INSTANCE_LABEL: str = "Instance"
AUTHENTICATION_LABEL: str = "Authentication"
CACHE_LABEL: str = "Cache"
LOGIN_LABEL: str = "Login"
COMPACT_CACHE_TEXT: str = "{label} cache"
COMPACT_USER_TEXT: str = "{label} - {user}"
NO_INSTANCE_TEXT: str = "No instance configured"
NO_INSTANCE_HINT: str = "Add an instance in the configuration tab to send the requests to it."
UNREADABLE_TEXT: str = "stored on another machine, the details cannot be read"
CHECKING_TEXT: str = "Checking the login..."
LOGIN_FAILED_TITLE: str = "Login failed"
LOGIN_NOT_SAVED_TITLE: str = "Login not saved"
INSTANCE_WIDTH: int = 220
ROW_SPACING: int = 10
NO_INSTANCE_ID: int = 0


class InstanceSelector(QWidget):

    changed = Signal()
    authenticationChanged = Signal()

    def __init__(self, repository: ConfigRepository, compact: bool = False) -> None:
        super().__init__()
        self._repository: ConfigRepository = repository
        self._compact: bool = compact
        self._instances: list[Instance] = []
        self._login_authentication: Authentication | None = None
        self._runner: LoginRunner = LoginRunner(self)
        self.instance_field: QComboBox = QComboBox()
        self.authentication_label: QLabel = hint_label("")
        self.login_button: QPushButton = QPushButton(LOGIN_LABEL)
        self.cache_label: QLabel = hint_label("")
        self.hint_label: QLabel = hint_label(NO_INSTANCE_HINT)
        self._build_ui()
        self.reload()
        self.instance_field.currentIndexChanged.connect(self._on_instance_changed)
        self.login_button.clicked.connect(self._on_login_clicked)
        self._runner.succeeded.connect(self._on_login_succeeded)
        self._runner.failed.connect(self._on_login_failed)
        self._runner.cancelled.connect(self._on_login_cancelled)

    def reload(self) -> None:
        selected = self.current_instance_id() or self._repository.current_instance_id()
        self._instances = self._repository.list_instances()
        self.instance_field.blockSignals(True)
        self.instance_field.clear()
        for instance in self._instances:
            self.instance_field.addItem(instance.name, instance.id)
        if not self._instances:
            self.instance_field.addItem(NO_INSTANCE_TEXT, NO_INSTANCE_ID)
        self.instance_field.setEnabled(bool(self._instances))
        index = self.instance_field.findData(selected)
        self.instance_field.setCurrentIndex(max(index, 0))
        self.instance_field.blockSignals(False)
        self._refresh_details()

    def current_instance_id(self) -> int:
        data = self.instance_field.currentData()
        return int(data) if isinstance(data, int) else NO_INSTANCE_ID

    def current_instance(self) -> Instance | None:
        instance_id = self.current_instance_id()
        for instance in self._instances:
            if instance.id == instance_id:
                return instance
        return None

    def current_target(self) -> RequestTarget:
        instance = self.current_instance()
        if instance is None:
            return RequestTarget()
        return RequestTarget(
            instance=instance,
            authentication=self._repository.active_authentication(instance.id),
        )

    def set_instance_id(self, instance_id: int) -> None:
        index = self.instance_field.findData(instance_id)
        if index >= 0:
            self.instance_field.setCurrentIndex(index)

    def _build_ui(self) -> None:
        self.instance_field.setMinimumWidth(INSTANCE_WIDTH)
        if self._compact:
            self._build_compact()
            return
        self._build_full()

    def _build_compact(self) -> None:
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(ROW_SPACING)
        layout.addWidget(section_label(INSTANCE_LABEL))
        layout.addWidget(self.instance_field)
        layout.addWidget(self.authentication_label, 1)
        layout.addWidget(self.login_button)
        layout.addWidget(self.cache_label)
        self.hint_label.setVisible(False)

    def _build_full(self) -> None:
        self.instance_field.setFixedWidth(INSTANCE_WIDTH)
        layout = QFormLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addRow(INSTANCE_LABEL, self.instance_field)
        layout.addRow(AUTHENTICATION_LABEL, self._build_authentication_row())
        layout.addRow(CACHE_LABEL, self.cache_label)
        layout.addRow(self.hint_label)

    def _build_authentication_row(self) -> QWidget:
        row = QWidget()
        layout = QHBoxLayout(row)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(ROW_SPACING)
        layout.addWidget(self.authentication_label, 1)
        layout.addWidget(self.login_button)
        return row

    def _refresh_details(self) -> None:
        instance = self.current_instance()
        self.hint_label.setVisible(not self._compact and instance is None)
        if instance is None:
            self.instance_field.setToolTip("")
            self.authentication_label.setText(NO_AUTHENTICATION_LABEL)
            self.cache_label.setText("")
            self.login_button.setVisible(False)
            return
        authentication = self._repository.active_authentication(instance.id)
        self.instance_field.setToolTip(instance.address)
        self.authentication_label.setText(self._authentication_text(authentication))
        self.cache_label.setText(self._cache_text(instance))
        self.login_button.setVisible(_can_log_in(authentication))

    def _cache_text(self, instance: Instance) -> str:
        if self._compact:
            return COMPACT_CACHE_TEXT.format(label=instance.cache_label)
        return instance.cache_label

    def _authentication_text(self, authentication: Authentication | None) -> str:
        if authentication is None:
            return NO_AUTHENTICATION_LABEL
        label = type_label(authentication.authentication_type)
        if not authentication.readable:
            return label if self._compact else f"{label} ({UNREADABLE_TEXT})"
        if self._compact:
            user = authentication.details.get(USER_KEY, "").strip()
            return COMPACT_USER_TEXT.format(label=label, user=user) if user else label
        details = masked_details(authentication.authentication_type, authentication.details)
        return f"{label} - {details}"

    def _on_instance_changed(self) -> None:
        instance_id = self.current_instance_id()
        if instance_id:
            self._remember(instance_id)
        self._refresh_details()
        self.changed.emit()

    def _remember(self, instance_id: int) -> None:
        try:
            self._repository.set_current_instance_id(instance_id)
        except (sqlite3.Error, DatabaseError):
            return

    def _on_login_clicked(self) -> None:
        instance = self.current_instance()
        if instance is None or self._runner.is_running():
            return
        authentication = self._repository.active_authentication(instance.id)
        if not _can_log_in(authentication) or authentication is None:
            return
        self._login_authentication = authentication
        self.login_button.setEnabled(False)
        self.authentication_label.setText(CHECKING_TEXT)
        self._runner.start(instance, authentication.details)

    def _on_login_succeeded(self, state: object) -> None:
        authentication = self._login_authentication
        self._finish_login()
        if not isinstance(state, LoginState) or authentication is None:
            return
        try:
            self._repository.update_authentication_details(authentication.id, state.details)
        except (sqlite3.Error, DatabaseError, SecretError, TimeoutError) as error:
            show_error(self, LOGIN_NOT_SAVED_TITLE, str(error))
        self._refresh_details()
        self.authenticationChanged.emit()

    def _on_login_failed(self, message: str) -> None:
        self._finish_login()
        show_error(self, LOGIN_FAILED_TITLE, message)

    def _on_login_cancelled(self) -> None:
        self._finish_login()

    def _finish_login(self) -> None:
        self._login_authentication = None
        self.login_button.setEnabled(True)
        self._refresh_details()


def _can_log_in(authentication: Authentication | None) -> bool:
    return (
        authentication is not None
        and authentication.readable
        and is_oauth(authentication.authentication_type)
    )
