import sqlite3
from collections.abc import Sequence
from dataclasses import dataclass

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QFormLayout,
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QScrollArea,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from configuration.authentication_types import masked_details, type_label
from core.background_task import BackgroundTask
from configuration.config_dialogs import AuthenticationDialog, InstanceDialog
from configuration.config_repository import Authentication, ConfigRepository, Instance
from core.database_manager import DatabaseError, DatabaseManager
from ui.dialogs import ask_confirmation, show_error
from storage.request_hints import RequestHintRepository
from core.secret_store import SecretError
from ui.tab import Tab
from ui.theme import THEMES
from ui.ui_widgets import (
    as_card,
    as_row,
    danger_button,
    hint_label,
    horizontal_rule,
    primary_button,
    section_label,
    show_status,
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
USER_KIND: str = "user"
MCP_KIND: str = "mcp"
AUTHENTICATION_SECTION_LABEL: str = "Authentication"
MCP_AUTHENTICATION_SECTION_LABEL: str = "MCP authentication"
MCP_AUTHENTICATION_HINT: str = (
    "Used only by the local MCP server. Agents that call the server never see these details."
)
ADD_MCP_AUTHENTICATION_LABEL: str = "Add MCP authentication method"
NO_MCP_AUTHENTICATION_MESSAGE: str = (
    "No MCP authentication method configured for this instance."
)
DELETE_MCP_AUTHENTICATION_MESSAGE: str = "Delete the {label} MCP method of {name}?"
DATABASE_ERROR_TITLE: str = "Configuration not saved"
DUPLICATE_INSTANCE_MESSAGE: str = "An instance named {name} already exists."
APPEARANCE_HINT: str = (
    "The selected theme is stored in the local database and reused on the next start."
)
CACHE_HINT: str = (
    "Responses are reused for this long before the instance is queried again. The clean up "
    "deletes the expired responses, their cache files and the cache files nothing refers to."
)
CACHE_LIFETIME_LABEL: str = "Expiration"
CACHE_LIFETIME_SUFFIX: str = " minutes"
CLEANUP_LABEL: str = "Clean up cache now"
CLEANUP_CONFIRM_LABEL: str = "Clean up"
CLEANUP_TITLE: str = "Clean up cache"
CLEANUP_MESSAGE: str = (
    "Delete the expired responses, their cache files and the cache files nothing refers to?\n"
    "This cannot be undone."
)
CLEANUP_RUNNING_MESSAGE: str = "Cleaning up the local cache..."
CLEANUP_RESULT_MESSAGE: str = (
    "Removed {responses} expired responses and {files} unused cache files."
)
CLEANUP_ERROR_MESSAGE: str = "The clean up failed: {message}"
LIFETIME_SAVED_MESSAGE: str = "Responses now expire after {minutes} minutes."
MINIMUM_CACHE_MINUTES: int = 1
MAXIMUM_CACHE_MINUTES: int = 10080
SUGGESTION_HINT: str = (
    "How many table and field names already used are offered when you click a table or a field "
    "box on a request page. The most recent ones come first."
)
SUGGESTION_COUNT_LABEL: str = "Names offered"
SUGGESTION_SAVED_MESSAGE: str = "Requests now offer up to {count} names."
CLEAR_SUGGESTIONS_LABEL: str = "Clear suggestions"
CLEAR_SUGGESTIONS_CONFIRM_LABEL: str = "Clear"
CLEAR_SUGGESTIONS_TITLE: str = "Clear suggestions"
CLEAR_SUGGESTIONS_MESSAGE: str = (
    "Forget every table and field name used so far?\nThis cannot be undone."
)
SUGGESTIONS_CLEARED_MESSAGE: str = "Cleared {count} remembered names."
NO_SUGGESTION_MESSAGE: str = "There was nothing to clear."
MINIMUM_SUGGESTIONS: int = 1
MAXIMUM_SUGGESTIONS: int = 100
THEME_FIELD_WIDTH: int = 220
CARD_SPACING: int = 6
ACTION_SPACING: int = 10


@dataclass(frozen=True)
class AuthenticationSection:
    kind: str
    title: str
    hint: str
    empty_message: str
    add_label: str
    delete_message: str


USER_SECTION: AuthenticationSection = AuthenticationSection(
    kind=USER_KIND,
    title=AUTHENTICATION_SECTION_LABEL,
    hint="",
    empty_message=NO_AUTHENTICATION_MESSAGE,
    add_label=ADD_AUTHENTICATION_LABEL,
    delete_message=DELETE_AUTHENTICATION_MESSAGE,
)
MCP_SECTION: AuthenticationSection = AuthenticationSection(
    kind=MCP_KIND,
    title=MCP_AUTHENTICATION_SECTION_LABEL,
    hint=MCP_AUTHENTICATION_HINT,
    empty_message=NO_MCP_AUTHENTICATION_MESSAGE,
    add_label=ADD_MCP_AUTHENTICATION_LABEL,
    delete_message=DELETE_MCP_AUTHENTICATION_MESSAGE,
)
AUTHENTICATION_SECTIONS: tuple[AuthenticationSection, ...] = (USER_SECTION, MCP_SECTION)


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


class AuthenticationList(QWidget):

    addRequested = Signal(object, object)
    activeToggled = Signal(object, bool, object)
    editRequested = Signal(object, object)
    deleteRequested = Signal(object, object)

    def __init__(
        self,
        instance: Instance,
        section: AuthenticationSection,
        authentications: list[Authentication],
    ) -> None:
        super().__init__()
        self.instance: Instance = instance
        self.section: AuthenticationSection = section
        self._build_ui(authentications)

    def _build_ui(self, authentications: list[Authentication]) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(CARD_SPACING)
        layout.addWidget(section_label(self.section.title))
        if self.section.hint:
            layout.addWidget(hint_label(self.section.hint))
        if not authentications:
            layout.addWidget(hint_label(self.section.empty_message))
        for authentication in authentications:
            layout.addWidget(self._build_row(authentication))
        add_button = QPushButton(self.section.add_label)
        add_button.clicked.connect(lambda: self.addRequested.emit(self.instance, self.section))
        layout.addWidget(add_button)

    def _build_row(self, authentication: Authentication) -> AuthenticationRow:
        row = AuthenticationRow(authentication)
        row.activeToggled.connect(self._on_active_toggled)
        row.editRequested.connect(self._on_edit_requested)
        row.deleteRequested.connect(self._on_delete_requested)
        return row

    def _on_active_toggled(self, authentication: Authentication, active: bool) -> None:
        self.activeToggled.emit(authentication, active, self.section)

    def _on_edit_requested(self, authentication: Authentication) -> None:
        self.editRequested.emit(authentication, self.section)

    def _on_delete_requested(self, authentication: Authentication) -> None:
        self.deleteRequested.emit(authentication, self.section)


class InstanceCard(QFrame):

    expandRequested = Signal(object)
    collapseRequested = Signal(object)
    deleteRequested = Signal(object)
    addAuthenticationRequested = Signal(object, object)
    authenticationActiveToggled = Signal(object, bool, object)
    authenticationEditRequested = Signal(object, object)
    authenticationDeleteRequested = Signal(object, object)

    def __init__(self, instance: Instance, expanded: bool) -> None:
        super().__init__()
        self.instance: Instance = instance
        self._expanded: bool = expanded
        self._toggle_button: QPushButton = QPushButton(COLLAPSE_LABEL if expanded else EXPAND_LABEL)
        self._body: QWidget = QWidget()
        self._body_layout: QVBoxLayout = QVBoxLayout(self._body)
        self._build_ui()

    def set_authentications(
        self, listings: Sequence[tuple[AuthenticationSection, list[Authentication]]]
    ) -> None:
        _clear_layout(self._body_layout)
        for index, (section, authentications) in enumerate(listings):
            if index:
                self._body_layout.addWidget(horizontal_rule())
            self._body_layout.addWidget(self._build_list(section, authentications))

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

    def _build_list(
        self, section: AuthenticationSection, authentications: list[Authentication]
    ) -> AuthenticationList:
        listing = AuthenticationList(self.instance, section, authentications)
        listing.addRequested.connect(self.addAuthenticationRequested.emit)
        listing.activeToggled.connect(self.authenticationActiveToggled.emit)
        listing.editRequested.connect(self.authenticationEditRequested.emit)
        listing.deleteRequested.connect(self.authenticationDeleteRequested.emit)
        return listing

    def _on_toggle_clicked(self) -> None:
        if self._expanded:
            self.collapseRequested.emit(self.instance)
        else:
            self.expandRequested.emit(self.instance)


class ConfigTab(Tab):

    configurationChanged = Signal()
    themeChanged = Signal(str)

    def __init__(
        self, title: str, repository: ConfigRepository, database: DatabaseManager
    ) -> None:
        super().__init__(title)
        self._repository: ConfigRepository = repository
        self._database: DatabaseManager = database
        self._hints: RequestHintRepository = RequestHintRepository(database)
        self._expanded_instance_id: int | None = None
        self._cleanup_task: BackgroundTask | None = None
        self.theme_field: QComboBox = QComboBox()
        self.cache_lifetime_field: QSpinBox = QSpinBox()
        self.cleanup_button: QPushButton = QPushButton(CLEANUP_LABEL)
        self.cache_status_label: QLabel = QLabel()
        self.suggestion_count_field: QSpinBox = QSpinBox()
        self.clear_suggestions_button: QPushButton = QPushButton(CLEAR_SUGGESTIONS_LABEL)
        self.suggestion_status_label: QLabel = QLabel()
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
        root.addWidget(section_label("Cache"))
        root.addLayout(self._build_cache())
        root.addWidget(section_label("Suggestions"))
        root.addLayout(self._build_suggestions())
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

    def _build_cache(self) -> QFormLayout:
        layout = QFormLayout()
        layout.setContentsMargins(0, 0, 0, 0)
        self.cache_lifetime_field.setFixedWidth(THEME_FIELD_WIDTH)
        self.cache_lifetime_field.setRange(MINIMUM_CACHE_MINUTES, MAXIMUM_CACHE_MINUTES)
        self.cache_lifetime_field.setSuffix(CACHE_LIFETIME_SUFFIX)
        self.cache_lifetime_field.setKeyboardTracking(False)
        self.cache_lifetime_field.setValue(self._repository.cache_lifetime_minutes())
        self.cache_lifetime_field.valueChanged.connect(self._on_cache_lifetime_changed)
        layout.addRow(CACHE_LIFETIME_LABEL, self.cache_lifetime_field)
        layout.addRow(hint_label(CACHE_HINT))
        layout.addRow(self._build_cache_actions())
        return layout

    def _build_cache_actions(self) -> QWidget:
        actions = QWidget()
        layout = QHBoxLayout(actions)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(ACTION_SPACING)
        self.cleanup_button.clicked.connect(self._on_cleanup_clicked)
        layout.addWidget(self.cleanup_button)
        layout.addWidget(self.cache_status_label, 1)
        return actions

    def _build_suggestions(self) -> QFormLayout:
        layout = QFormLayout()
        layout.setContentsMargins(0, 0, 0, 0)
        self.suggestion_count_field.setFixedWidth(THEME_FIELD_WIDTH)
        self.suggestion_count_field.setRange(MINIMUM_SUGGESTIONS, MAXIMUM_SUGGESTIONS)
        self.suggestion_count_field.setKeyboardTracking(False)
        self.suggestion_count_field.setValue(self._repository.suggestion_count())
        self.suggestion_count_field.valueChanged.connect(self._on_suggestion_count_changed)
        layout.addRow(SUGGESTION_COUNT_LABEL, self._build_suggestion_actions())
        layout.addRow(hint_label(SUGGESTION_HINT))
        layout.addRow(self.suggestion_status_label)
        return layout

    def _build_suggestion_actions(self) -> QWidget:
        actions = QWidget()
        layout = QHBoxLayout(actions)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(ACTION_SPACING)
        self.clear_suggestions_button.clicked.connect(self._on_clear_suggestions_clicked)
        layout.addWidget(self.suggestion_count_field)
        layout.addWidget(self.clear_suggestions_button)
        layout.addStretch(1)
        return actions

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
            card.set_authentications(
                [
                    (section, self._authentications(section, instance.id))
                    for section in AUTHENTICATION_SECTIONS
                ]
            )
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

    def _on_cache_lifetime_changed(self, minutes: int) -> None:
        try:
            self._repository.set_cache_lifetime_minutes(minutes)
        except (sqlite3.Error, DatabaseError) as error:
            self._show_database_error(error)
            return
        show_status(self.cache_status_label, LIFETIME_SAVED_MESSAGE.format(minutes=minutes))

    def _on_suggestion_count_changed(self, count: int) -> None:
        try:
            self._repository.set_suggestion_count(count)
        except (sqlite3.Error, DatabaseError) as error:
            self._show_database_error(error)
            return
        show_status(self.suggestion_status_label, SUGGESTION_SAVED_MESSAGE.format(count=count))

    def _on_clear_suggestions_clicked(self) -> None:
        confirmed = ask_confirmation(
            self,
            CLEAR_SUGGESTIONS_TITLE,
            CLEAR_SUGGESTIONS_MESSAGE,
            CLEAR_SUGGESTIONS_CONFIRM_LABEL,
            destructive=True,
        )
        if not confirmed:
            return
        try:
            cleared = self._hints.clear()
        except (sqlite3.Error, DatabaseError, TimeoutError) as error:
            self._show_database_error(error)
            return
        show_status(
            self.suggestion_status_label,
            SUGGESTIONS_CLEARED_MESSAGE.format(count=cleared)
            if cleared
            else NO_SUGGESTION_MESSAGE,
        )

    def _on_cleanup_clicked(self) -> None:
        if self._cleanup_task is not None:
            return
        confirmed = ask_confirmation(
            self,
            CLEANUP_TITLE,
            CLEANUP_MESSAGE,
            CLEANUP_CONFIRM_LABEL,
            destructive=True,
        )
        if not confirmed:
            return
        self.cleanup_button.setEnabled(False)
        show_status(self.cache_status_label, CLEANUP_RUNNING_MESSAGE)
        task = BackgroundTask(self._clean_up_cache, self)
        task.finished.connect(self._on_cleanup_finished)
        task.failed.connect(self._on_cleanup_failed)
        self._cleanup_task = task
        task.start()

    def _clean_up_cache(self) -> tuple[int, int]:
        responses = self._database.purge_expired_responses()
        return responses, self._database.purge_orphan_caches()

    def _on_cleanup_finished(self, counts: object) -> None:
        self._release_cleanup()
        responses, files = counts if isinstance(counts, tuple) else (0, 0)
        show_status(
            self.cache_status_label,
            CLEANUP_RESULT_MESSAGE.format(responses=responses, files=files),
        )

    def _on_cleanup_failed(self, message: str) -> None:
        self._release_cleanup()
        show_status(
            self.cache_status_label,
            CLEANUP_ERROR_MESSAGE.format(message=message),
            failed=True,
        )

    def _release_cleanup(self) -> None:
        task = self._cleanup_task
        self._cleanup_task = None
        if task is not None:
            task.deleteLater()
        self.cleanup_button.setEnabled(True)

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
            show_error(self, DATABASE_ERROR_TITLE, DUPLICATE_INSTANCE_MESSAGE.format(name=name))
            return
        except (sqlite3.Error, DatabaseError) as error:
            self._show_database_error(error)
            return
        self._announce()

    def _on_delete_instance(self, instance: Instance) -> None:
        confirmed = ask_confirmation(
            self,
            DELETE_INSTANCE_TITLE,
            DELETE_INSTANCE_MESSAGE.format(name=instance.name),
            DELETE_LABEL,
            destructive=True,
        )
        if not confirmed:
            return
        try:
            self._repository.delete_instance(instance.id)
        except (sqlite3.Error, DatabaseError) as error:
            self._show_database_error(error)
            return
        if self._expanded_instance_id == instance.id:
            self._expanded_instance_id = None
        self._announce()

    def _on_add_authentication(
        self, instance: Instance, section: AuthenticationSection
    ) -> None:
        dialog = AuthenticationDialog(self)
        if dialog.exec() != AuthenticationDialog.DialogCode.Accepted:
            return
        authentication_type, details = dialog.values()
        try:
            first_method = not self._authentications(section, instance.id)
            self._create_authentication(
                section, instance.id, authentication_type, details, first_method
            )
        except (sqlite3.Error, DatabaseError, SecretError) as error:
            self._show_database_error(error)
            return
        self._expanded_instance_id = instance.id
        self._announce()

    def _on_edit_authentication(
        self, authentication: Authentication, section: AuthenticationSection
    ) -> None:
        dialog = AuthenticationDialog(self, authentication)
        if dialog.exec() != AuthenticationDialog.DialogCode.Accepted:
            return
        authentication_type, details = dialog.values()
        try:
            self._update_authentication(
                section, authentication.id, authentication_type, details
            )
        except (sqlite3.Error, DatabaseError, SecretError) as error:
            self._show_database_error(error)
            return
        self._announce()

    def _on_delete_authentication(
        self, authentication: Authentication, section: AuthenticationSection
    ) -> None:
        instance_name = self._instance_name(authentication.instance_id)
        confirmed = ask_confirmation(
            self,
            DELETE_AUTHENTICATION_TITLE,
            section.delete_message.format(
                label=type_label(authentication.authentication_type), name=instance_name
            ),
            DELETE_LABEL,
            destructive=True,
        )
        if not confirmed:
            return
        try:
            self._delete_authentication(section, authentication.id)
        except (sqlite3.Error, DatabaseError) as error:
            self._show_database_error(error)
            return
        self._announce()

    def _on_authentication_active_toggled(
        self, authentication: Authentication, active: bool, section: AuthenticationSection
    ) -> None:
        try:
            self._set_active_authentication(
                section, authentication.instance_id, authentication.id, active
            )
        except (sqlite3.Error, DatabaseError) as error:
            self._show_database_error(error)
        self._announce()

    def _authentications(
        self, section: AuthenticationSection, instance_id: int
    ) -> list[Authentication]:
        if section.kind == MCP_KIND:
            return self._repository.list_mcp_authentications(instance_id)
        return self._repository.list_authentications(instance_id)

    def _create_authentication(
        self,
        section: AuthenticationSection,
        instance_id: int,
        authentication_type: str,
        details: dict[str, str],
        active: bool,
    ) -> None:
        if section.kind == MCP_KIND:
            self._repository.create_mcp_authentication(
                instance_id, authentication_type, details, active=active
            )
            return
        self._repository.create_authentication(
            instance_id, authentication_type, details, active=active
        )

    def _update_authentication(
        self,
        section: AuthenticationSection,
        authentication_id: int,
        authentication_type: str,
        details: dict[str, str],
    ) -> None:
        if section.kind == MCP_KIND:
            self._repository.update_mcp_authentication(
                authentication_id, authentication_type, details
            )
            return
        self._repository.update_authentication(authentication_id, authentication_type, details)

    def _delete_authentication(
        self, section: AuthenticationSection, authentication_id: int
    ) -> None:
        if section.kind == MCP_KIND:
            self._repository.delete_mcp_authentication(authentication_id)
            return
        self._repository.delete_authentication(authentication_id)

    def _set_active_authentication(
        self,
        section: AuthenticationSection,
        instance_id: int,
        authentication_id: int,
        active: bool,
    ) -> None:
        if section.kind == MCP_KIND:
            self._repository.set_active_mcp_authentication(
                instance_id, authentication_id, active
            )
            return
        self._repository.set_active_authentication(instance_id, authentication_id, active)

    def _instance_name(self, instance_id: int) -> str:
        for instance in self._repository.list_instances():
            if instance.id == instance_id:
                return instance.name
        return ""

    def _announce(self) -> None:
        self.reload()
        self.configurationChanged.emit()

    def _show_database_error(self, error: Exception) -> None:
        show_error(self, DATABASE_ERROR_TITLE, str(error))


def _clear_layout(layout: QVBoxLayout) -> None:
    while layout.count():
        item = layout.takeAt(0)
        widget = item.widget() if item is not None else None
        if widget is not None:
            widget.setParent(None)
            widget.deleteLater()
