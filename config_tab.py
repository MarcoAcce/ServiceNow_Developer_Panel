import sqlite3

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QFormLayout,
    QFrame,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from authentication_types import masked_details, type_label
from config_dialogs import AuthenticationDialog, InstanceDialog
from config_repository import Authentication, ConfigRepository, Instance
from database_manager import DatabaseError
from secret_store import SecretError
from tab import Tab
from theme import THEMES
from ui_widgets import (
    as_card,
    as_row,
    danger_button,
    hint_label,
    horizontal_rule,
    primary_button,
    section_label,
    title_label,
    vertical_spacer,
)

CONFIG_HINT: str = (
    "Configure the instances you want to query and the authentication methods available for each "
    "of them. One method per instance can be active at a time."
)
THEME_LABEL: str = "Theme"
ADD_INSTANCE_LABEL: str = "Add instance"
ADD_AUTHENTICATION_LABEL: str = "Add authentication method"
EXPAND_LABEL: str = "Expand"
COLLAPSE_LABEL: str = "Collapse"
EDIT_LABEL: str = "Edit"
DELETE_LABEL: str = "Delete"
ACTIVE_LABEL: str = "Active"
NO_INSTANCE_MESSAGE: str = "No instance configured yet. Use the button above to add the first one."
NO_AUTHENTICATION_MESSAGE: str = "No authentication method configured for this instance."
UNREADABLE_MESSAGE: str = "Stored on another machine or user account, the details cannot be read."
DELETE_INSTANCE_TITLE: str = "Delete instance"
DELETE_INSTANCE_MESSAGE: str = (
    "Delete {name} and every authentication method configured for it?\n"
    "This cannot be undone."
)
DELETE_AUTHENTICATION_TITLE: str = "Delete authentication method"
DELETE_AUTHENTICATION_MESSAGE: str = "Delete the {label} method of {name}?"
DATABASE_ERROR_TITLE: str = "Configuration not saved"
DUPLICATE_INSTANCE_MESSAGE: str = "An instance named {name} already exists."
APPEARANCE_HINT: str = (
    "The selected theme is stored in the local database and reused on the next start."
)
THEME_FIELD_WIDTH: int = 220
CARD_SPACING: int = 6


class AuthenticationRow(QFrame):

    activeToggled = Signal(object, bool)
    editRequested = Signal(object)
    deleteRequested = Signal(object)

    def __init__(self, authentication: Authentication) -> None:
        super().__init__()
        self.authentication: Authentication = authentication
        self.active_box: QCheckBox = QCheckBox(ACTIVE_LABEL)
        self._build_ui()

    def _build_ui(self) -> None:
        as_row(self)
        layout = QHBoxLayout(self)
        layout.addWidget(section_label(type_label(self.authentication.authentication_type)))
        layout.addWidget(self._build_details_label(), 1)
        self.active_box.setChecked(self.authentication.active)
        self.active_box.setEnabled(self.authentication.readable)
        self.active_box.toggled.connect(self._on_active_toggled)
        layout.addWidget(self.active_box)
        edit_button = QPushButton(EDIT_LABEL)
        edit_button.setEnabled(self.authentication.readable)
        edit_button.clicked.connect(lambda: self.editRequested.emit(self.authentication))
        layout.addWidget(edit_button)
        delete_button = danger_button(DELETE_LABEL)
        delete_button.clicked.connect(lambda: self.deleteRequested.emit(self.authentication))
        layout.addWidget(delete_button)

    def _build_details_label(self) -> QLabel:
        if not self.authentication.readable:
            return hint_label(UNREADABLE_MESSAGE)
        label = QLabel(
            masked_details(self.authentication.authentication_type, self.authentication.details)
        )
        label.setTextInteractionFlags(Qt.TextInteractionFlag.NoTextInteraction)
        return label

    def _on_active_toggled(self, checked: bool) -> None:
        self.activeToggled.emit(self.authentication, checked)


class InstanceCard(QFrame):

    expandRequested = Signal(object)
    collapseRequested = Signal(object)
    deleteRequested = Signal(object)
    addAuthenticationRequested = Signal(object)
    authenticationActiveToggled = Signal(object, bool)
    authenticationEditRequested = Signal(object)
    authenticationDeleteRequested = Signal(object)

    def __init__(self, instance: Instance, expanded: bool) -> None:
        super().__init__()
        self.instance: Instance = instance
        self._expanded: bool = expanded
        self._toggle_button: QPushButton = QPushButton(COLLAPSE_LABEL if expanded else EXPAND_LABEL)
        self._body: QWidget = QWidget()
        self._body_layout: QVBoxLayout = QVBoxLayout(self._body)
        self._build_ui()

    def set_authentications(self, authentications: list[Authentication]) -> None:
        _clear_layout(self._body_layout)
        if not authentications:
            self._body_layout.addWidget(hint_label(NO_AUTHENTICATION_MESSAGE))
        for authentication in authentications:
            self._body_layout.addWidget(self._build_row(authentication))
        add_button = QPushButton(ADD_AUTHENTICATION_LABEL)
        add_button.clicked.connect(lambda: self.addAuthenticationRequested.emit(self.instance))
        self._body_layout.addWidget(add_button)

    def _build_ui(self) -> None:
        as_card(self)
        root = QVBoxLayout(self)
        root.setSpacing(CARD_SPACING)
        root.addLayout(self._build_header())
        self._body_layout.setContentsMargins(0, 0, 0, 0)
        self._body.setVisible(self._expanded)
        root.addWidget(self._body)

    def _build_header(self) -> QHBoxLayout:
        header = QHBoxLayout()
        header.addWidget(section_label(self.instance.name))
        header.addWidget(hint_label(self.instance.address), 1)
        self._toggle_button.clicked.connect(self._on_toggle_clicked)
        header.addWidget(self._toggle_button)
        delete_button = danger_button(DELETE_LABEL)
        delete_button.clicked.connect(lambda: self.deleteRequested.emit(self.instance))
        header.addWidget(delete_button)
        return header

    def _build_row(self, authentication: Authentication) -> AuthenticationRow:
        row = AuthenticationRow(authentication)
        row.activeToggled.connect(self.authenticationActiveToggled.emit)
        row.editRequested.connect(self.authenticationEditRequested.emit)
        row.deleteRequested.connect(self.authenticationDeleteRequested.emit)
        return row

    def _on_toggle_clicked(self) -> None:
        if self._expanded:
            self.collapseRequested.emit(self.instance)
        else:
            self.expandRequested.emit(self.instance)


class ConfigTab(Tab):

    configurationChanged = Signal()
    themeChanged = Signal(str)

    def __init__(self, title: str, repository: ConfigRepository) -> None:
        super().__init__(title)
        self._repository: ConfigRepository = repository
        self._expanded_instance_id: int | None = None
        self.theme_field: QComboBox = QComboBox()
        self._build_ui()
        self.reload()

    def reload(self) -> None:
        _clear_layout(self._instances_layout)
        instances = self._repository.list_instances()
        if not instances:
            self._expanded_instance_id = None
            self._instances_layout.addWidget(hint_label(NO_INSTANCE_MESSAGE))
        for instance in instances:
            self._instances_layout.addWidget(self._build_card(instance))
        self._instances_layout.addWidget(vertical_spacer())

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.addWidget(title_label("Configuration"))
        root.addWidget(hint_label(CONFIG_HINT))
        root.addWidget(horizontal_rule())
        root.addWidget(section_label("Appearance"))
        root.addLayout(self._build_appearance())
        root.addWidget(horizontal_rule())
        root.addLayout(self._build_toolbar())

        content = QWidget()
        self._instances_layout: QVBoxLayout = QVBoxLayout(content)
        self._instances_layout.setContentsMargins(0, 0, 0, 0)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QScrollArea.Shape.NoFrame)
        scroll.setWidget(content)
        root.addWidget(scroll)

    def _build_appearance(self) -> QFormLayout:
        layout = QFormLayout()
        layout.setContentsMargins(0, 0, 0, 0)
        self.theme_field.setFixedWidth(THEME_FIELD_WIDTH)
        for theme in THEMES:
            self.theme_field.addItem(theme.label, theme.key)
        index = self.theme_field.findData(self._repository.theme_key())
        self.theme_field.setCurrentIndex(max(index, 0))
        self.theme_field.currentIndexChanged.connect(self._on_theme_selected)
        layout.addRow(THEME_LABEL, self.theme_field)
        layout.addRow(hint_label(APPEARANCE_HINT))
        return layout

    def _build_toolbar(self) -> QHBoxLayout:
        toolbar = QHBoxLayout()
        toolbar.addWidget(section_label("Instances"))
        toolbar.addStretch(1)
        add_button = primary_button(ADD_INSTANCE_LABEL)
        add_button.clicked.connect(self._on_add_instance)
        toolbar.addWidget(add_button)
        return toolbar

    def _build_card(self, instance: Instance) -> InstanceCard:
        expanded = instance.id == self._expanded_instance_id
        card = InstanceCard(instance, expanded)
        if expanded:
            card.set_authentications(self._repository.list_authentications(instance.id))
        card.expandRequested.connect(self._on_expand)
        card.collapseRequested.connect(self._on_collapse)
        card.deleteRequested.connect(self._on_delete_instance)
        card.addAuthenticationRequested.connect(self._on_add_authentication)
        card.authenticationActiveToggled.connect(self._on_authentication_active_toggled)
        card.authenticationEditRequested.connect(self._on_edit_authentication)
        card.authenticationDeleteRequested.connect(self._on_delete_authentication)
        return card

    def _on_theme_selected(self, index: int) -> None:
        key = self.theme_field.itemData(index)
        if not isinstance(key, str):
            return
        try:
            self._repository.set_theme_key(key)
        except (sqlite3.Error, DatabaseError) as error:
            self._show_database_error(error)
            return
        self.themeChanged.emit(key)

    def _on_expand(self, instance: Instance) -> None:
        self._expanded_instance_id = instance.id
        self.reload()

    def _on_collapse(self, instance: Instance) -> None:
        if self._expanded_instance_id == instance.id:
            self._expanded_instance_id = None
        self.reload()

    def _on_add_instance(self) -> None:
        dialog = InstanceDialog(self)
        if dialog.exec() != InstanceDialog.DialogCode.Accepted:
            return
        name, address = dialog.values()
        try:
            self._expanded_instance_id = self._repository.create_instance(name, address)
        except sqlite3.IntegrityError:
            QMessageBox.warning(
                self, DATABASE_ERROR_TITLE, DUPLICATE_INSTANCE_MESSAGE.format(name=name)
            )
            return
        except (sqlite3.Error, DatabaseError) as error:
            self._show_database_error(error)
            return
        self._announce()

    def _on_delete_instance(self, instance: Instance) -> None:
        confirmed = QMessageBox.question(
            self,
            DELETE_INSTANCE_TITLE,
            DELETE_INSTANCE_MESSAGE.format(name=instance.name),
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if confirmed != QMessageBox.StandardButton.Yes:
            return
        try:
            self._repository.delete_instance(instance.id)
        except (sqlite3.Error, DatabaseError) as error:
            self._show_database_error(error)
            return
        if self._expanded_instance_id == instance.id:
            self._expanded_instance_id = None
        self._announce()

    def _on_add_authentication(self, instance: Instance) -> None:
        dialog = AuthenticationDialog(self)
        if dialog.exec() != AuthenticationDialog.DialogCode.Accepted:
            return
        authentication_type, details = dialog.values()
        first_method = not self._repository.list_authentications(instance.id)
        try:
            self._repository.create_authentication(
                instance.id, authentication_type, details, active=first_method
            )
        except (sqlite3.Error, DatabaseError, SecretError) as error:
            self._show_database_error(error)
            return
        self._expanded_instance_id = instance.id
        self._announce()

    def _on_edit_authentication(self, authentication: Authentication) -> None:
        dialog = AuthenticationDialog(self, authentication)
        if dialog.exec() != AuthenticationDialog.DialogCode.Accepted:
            return
        authentication_type, details = dialog.values()
        try:
            self._repository.update_authentication(authentication.id, authentication_type, details)
        except (sqlite3.Error, DatabaseError, SecretError) as error:
            self._show_database_error(error)
            return
        self._announce()

    def _on_delete_authentication(self, authentication: Authentication) -> None:
        instance_name = self._instance_name(authentication.instance_id)
        confirmed = QMessageBox.question(
            self,
            DELETE_AUTHENTICATION_TITLE,
            DELETE_AUTHENTICATION_MESSAGE.format(
                label=type_label(authentication.authentication_type), name=instance_name
            ),
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if confirmed != QMessageBox.StandardButton.Yes:
            return
        try:
            self._repository.delete_authentication(authentication.id)
        except (sqlite3.Error, DatabaseError) as error:
            self._show_database_error(error)
            return
        self._announce()

    def _on_authentication_active_toggled(
        self, authentication: Authentication, active: bool
    ) -> None:
        try:
            self._repository.set_active_authentication(
                authentication.instance_id, authentication.id, active
            )
        except (sqlite3.Error, DatabaseError) as error:
            self._show_database_error(error)
        self._announce()

    def _instance_name(self, instance_id: int) -> str:
        for instance in self._repository.list_instances():
            if instance.id == instance_id:
                return instance.name
        return ""

    def _announce(self) -> None:
        self.reload()
        self.configurationChanged.emit()

    def _show_database_error(self, error: Exception) -> None:
        QMessageBox.warning(self, DATABASE_ERROR_TITLE, str(error))


def _clear_layout(layout: QVBoxLayout) -> None:
    while layout.count():
        item = layout.takeAt(0)
        widget = item.widget() if item is not None else None
        if widget is not None:
            widget.setParent(None)
            widget.deleteLater()
