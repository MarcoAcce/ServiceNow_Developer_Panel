from PySide6.QtWidgets import (
    QFormLayout,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from acl_requests import verification_request
from acl_verification import FIELD_OPERATIONS, OPERATIONS, Verification
from config_repository import ConfigRepository
from filter_fields import RadioChoiceField
from request_hints import RequestHintRepository
from request_tab import RequestTab, required_label, required_message
from request_types import VERIFY_SECURITY
from response_tab import ResponseTab
from role_field import UserRoleField
from service import RequestResult, RequestService, RequestSpec
from suggestion_field import SuggestionField
from table_query_form import TABLE_PLACEHOLDER
from ui_widgets import hint_label, section_label, vertical_spacer
from verify_security_response_tab import VerifySecurityResponseTab

TARGET_SECTION: str = "Protected record"
TABLE_LABEL: str = "Table protected by the ACL"
OPERATION_LABEL: str = "Operation"
FIELD_LABEL: str = "Field protected by the ACL"
FIELD_PLACEHOLDER: str = "Field name, for example state, empty for the whole record"
TARGET_HINT: str = (
    "Only the active controls of this operation are read: the record level control of "
    "the table and, when a field is named, the control of that field or the wildcard "
    "control of the table."
)
FIELD_HINT: str = (
    "A field can only be named for read and update: the other operations are decided "
    "at the record level alone."
)
ROLES_SECTION: str = "Users to check"
ROLES_HINT: str = (
    "Every user is checked with the whole set of roles listed under it, and the admin "
    "role satisfies the controls that let the admin role override them. The roles are "
    "compared on this machine and are never sent to the instance."
)
TABLE_REQUIRED: str = required_message(TABLE_LABEL)
ROLES_REQUIRED: str = "At least one user with one role is required to verify the controls."


class VerifySecurityRequestTab(RequestTab):

    def __init__(
        self,
        service: RequestService,
        repository: ConfigRepository,
        hints: RequestHintRepository,
    ) -> None:
        self._form: QFormLayout = QFormLayout()
        self.table_field: SuggestionField = SuggestionField(self.table_names)
        self.operation_field: RadioChoiceField = RadioChoiceField(OPERATIONS)
        self.field_field: SuggestionField = SuggestionField(self._field_suggestions)
        self.roles_field: UserRoleField = UserRoleField()
        super().__init__(VERIFY_SECURITY, service, repository, hints)
        self._apply_operation()

    def target_table(self) -> str:
        return self.table_field.text().strip()

    def operation(self) -> str:
        return self.operation_field.value()

    def protected_field(self) -> str:
        if not self.takes_field():
            return ""
        return self.field_field.text().strip()

    def takes_field(self) -> bool:
        return self.operation() in FIELD_OPERATIONS

    def verification(self) -> Verification:
        return Verification(
            table=self.target_table(),
            operation=self.operation(),
            field=self.protected_field(),
            profiles=self.roles_field.profiles(),
        )

    def missing_requirement(self) -> str:
        if not self.target_table():
            return TABLE_REQUIRED
        if not self.roles_field.profiles():
            return ROLES_REQUIRED
        return ""

    def record_hints(self) -> None:
        self.record_hint(self.target_table(), self.protected_field() or None)

    def build_request(self) -> RequestSpec:
        verification = self.verification()
        return verification_request(
            verification.names,
            verification.control_operation,
            self.instance_selector.current_target(),
        )

    def create_response_tab(self, result: RequestResult) -> ResponseTab:
        return VerifySecurityResponseTab(result, self.verification())

    def build_content(self) -> QScrollArea:
        content = QWidget()
        layout = QVBoxLayout(content)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(section_label(TARGET_SECTION))
        layout.addWidget(self._build_target())
        layout.addWidget(hint_label(TARGET_HINT))
        layout.addWidget(hint_label(FIELD_HINT))
        layout.addWidget(section_label(ROLES_SECTION))
        layout.addWidget(hint_label(ROLES_HINT))
        layout.addWidget(self.roles_field)
        layout.addWidget(vertical_spacer())

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QScrollArea.Shape.NoFrame)
        scroll.setWidget(content)
        return scroll

    def _field_suggestions(self) -> list[str]:
        return self.field_names(self.target_table())

    def _build_target(self) -> QWidget:
        target = QWidget()
        self._form.setContentsMargins(0, 0, 0, 0)
        self.table_field.setPlaceholderText(TABLE_PLACEHOLDER)
        self.field_field.setPlaceholderText(FIELD_PLACEHOLDER)
        self._form.addRow(required_label(TABLE_LABEL), self.table_field)
        self._form.addRow(required_label(OPERATION_LABEL), self.operation_field)
        self._form.addRow(FIELD_LABEL, self.field_field)
        target.setLayout(self._form)
        self.table_field.textChanged.connect(self.refresh_state)
        self.operation_field.changed.connect(self._on_operation_changed)
        self.roles_field.changed.connect(self.refresh_state)
        return target

    def _on_operation_changed(self) -> None:
        self._apply_operation()
        self.refresh_state()

    def _apply_operation(self) -> None:
        self._form.setRowVisible(self.field_field, self.takes_field())
