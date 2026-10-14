import sqlite3

from PySide6.QtCore import Signal
from PySide6.QtWidgets import QComboBox, QFormLayout, QHBoxLayout, QLabel, QWidget

from authentication_types import masked_details, type_label
from config_repository import ConfigRepository, Instance
from database_manager import DatabaseError
from service import NO_AUTHENTICATION_LABEL, RequestTarget
from ui_widgets import hint_label, section_label

INSTANCE_LABEL: str = "Instance"
AUTHENTICATION_LABEL: str = "Authentication"
NO_INSTANCE_TEXT: str = "No instance configured"
NO_INSTANCE_HINT: str = "Add an instance in the configuration tab to send the requests to it."
UNREADABLE_TEXT: str = "stored on another machine, the details cannot be read"
INSTANCE_WIDTH: int = 220
ROW_SPACING: int = 10
NO_INSTANCE_ID: int = 0


class InstanceSelector(QWidget):

    changed = Signal()

    def __init__(self, repository: ConfigRepository, compact: bool = False) -> None:
        super().__init__()
        self._repository: ConfigRepository = repository
        self._compact: bool = compact
        self._instances: list[Instance] = []
        self.instance_field: QComboBox = QComboBox()
        self.authentication_label: QLabel = hint_label("")
        self.hint_label: QLabel = hint_label(NO_INSTANCE_HINT)
        self._build_ui()
        self.reload()
        self.instance_field.currentIndexChanged.connect(self._on_instance_changed)

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
        self.hint_label.setVisible(False)

    def _build_full(self) -> None:
        self.instance_field.setFixedWidth(INSTANCE_WIDTH)
        layout = QFormLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addRow(INSTANCE_LABEL, self.instance_field)
        layout.addRow(AUTHENTICATION_LABEL, self.authentication_label)
        layout.addRow(self.hint_label)

    def _refresh_details(self) -> None:
        instance = self.current_instance()
        self.hint_label.setVisible(not self._compact and instance is None)
        if instance is None:
            self.instance_field.setToolTip("")
            self.authentication_label.setText(NO_AUTHENTICATION_LABEL)
            return
        self.instance_field.setToolTip(instance.address)
        self.authentication_label.setText(self._authentication_text(instance))

    def _authentication_text(self, instance: Instance) -> str:
        authentication = self._repository.active_authentication(instance.id)
        if authentication is None:
            return NO_AUTHENTICATION_LABEL
        label = type_label(authentication.authentication_type)
        if self._compact:
            return label
        if not authentication.readable:
            return f"{label} ({UNREADABLE_TEXT})"
        return f"{label} - {masked_details(authentication.authentication_type, authentication.details)}"

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
