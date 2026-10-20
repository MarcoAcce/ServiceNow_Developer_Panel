from PySide6.QtWidgets import QFormLayout, QLabel

from core.acl.acl_requests import (
    ACL_FIELDS,
    NAME_FIELD,
    OPERATION_NAME_FIELD,
    acl_composite,
    field_control_name,
    wildcard_name,
)
from configuration.config_repository import ConfigRepository
from ui.widgets.filter_fields import RadioChoiceField
from storage.request_hints import RequestHintRepository
from ui.widgets.query_builder import OPERATOR_CONTAINS, OPERATOR_IS, build_condition
from request_tabs.multiple_tables_request_tab import MultipleTablesRequestTab
from request_tabs.table_description_request_tab import TableDescriptionRequestTab
from request_tabs.request_tab import RequestTab, TableRequestTab, required_label, required_message
from ui.widgets.suggestion_field import SuggestionField
from ui.widgets.table_query_form import TABLE_PLACEHOLDER
from core.request_types import (
    ACL_LIST,
    BUSINESS_RULE_LIST,
    CLIENT_SCRIPT_LIST,
    DATA_POLICY_LIST,
    MULTIPLE_TABLES,
    SCRIPT_INCLUDE_LIST,
    TABLE_DESCRIPTION,
    TABLE_DICTIONARY,
    TABLE_RECORDS,
    UI_ACTION_LIST,
    UI_POLICY_LIST,
    VERIFY_SECURITY,
)
from response_tabs.response_tab import ResponseTab
from response_tabs.table_response_tabs import (
    AclResponseTab,
    BusinessRuleResponseTab,
    ClientScriptResponseTab,
    DataPolicyResponseTab,
    DictionaryResponseTab,
    ScriptIncludeResponseTab,
    TableRecordsResponseTab,
    UiActionResponseTab,
    UiPolicyResponseTab,
)
from services.service import RequestResult, RequestService, RequestSpec
from ui.ui_widgets import hint_label
from request_tabs.verify_security_request_tab import VerifySecurityRequestTab

ACTIVE_OPTIONS: tuple[str, ...] = ("true", "false")
ACL_OPERATIONS: tuple[str, ...] = (
    "read",
    "write",
    "create",
    "delete",
    "execute",
    "report_on",
)
ACL_TYPES: tuple[str, ...] = ("record", "client_callable_script_include", "processor", "ui_page")
CLIENT_SCRIPT_TYPES: tuple[str, ...] = ("onLoad", "onChange", "onSubmit", "onCellEdit")
CLIENT_SCRIPT_UI_TYPES: tuple[str, ...] = ("Desktop", "Mobile", "Both")
BUSINESS_RULE_WHEN: tuple[str, ...] = ("before", "after", "async", "display")
BUSINESS_RULE_ACTIONS: tuple[str, ...] = ("insert", "update", "delete", "query")
SCRIPT_INCLUDE_ACCESS: tuple[str, ...] = ("public", "package_private")
DICTIONARY_TYPES: tuple[str, ...] = ("string", "reference", "glide_date_time", "boolean", "integer", "journal_input")

ACL_SCOPE_TABLE: str = "table"
ACL_SCOPE_WILDCARD: str = "wildcard"
ACL_SCOPE_FIELD: str = "field"
ACL_SCOPES: tuple[tuple[str, str], ...] = (
    (ACL_SCOPE_TABLE, "Table"),
    (ACL_SCOPE_WILDCARD, "Wildcard"),
    (ACL_SCOPE_FIELD, "Field"),
)
ACL_SCOPE_HINTS: dict[str, str] = {
    ACL_SCOPE_TABLE: "Record level controls named after the table alone, for example incident.",
    ACL_SCOPE_WILDCARD: "Controls covering every field of the table, for example incident.*.",
    ACL_SCOPE_FIELD: "Controls covering a single field, for example incident.state.",
}
ACL_SCOPE_LABEL: str = "ACL protects"
ACL_TABLE_LABEL: str = "Table protected by the ACL"
ACL_FIELD_LABEL: str = "Field protected by the ACL"
ACL_FIELD_PLACEHOLDER: str = "Field name, for example state"
ACL_TABLE_REQUIRED: str = required_message(ACL_TABLE_LABEL)
ACL_FIELD_REQUIRED: str = required_message(ACL_FIELD_LABEL)


class TableRecordsRequestTab(TableRequestTab):

    def __init__(
        self,
        service: RequestService,
        repository: ConfigRepository,
        hints: RequestHintRepository,
    ) -> None:
        super().__init__(TABLE_RECORDS, service, repository, hints)

    def columns(self) -> tuple[str, ...]:
        return ("number", "short_description", "sys_created_on", "sys_updated_on", "sys_id")

    def build_filters(self, layout: QFormLayout) -> None:
        self.add_boolean_filter("active", "Active")
        self.add_date_filter("sys_created_on", "Created on or after")

    def create_response_tab(self, result: RequestResult) -> ResponseTab:
        return TableRecordsResponseTab(result)


class DictionaryRequestTab(TableRequestTab):

    def __init__(
        self,
        service: RequestService,
        repository: ConfigRepository,
        hints: RequestHintRepository,
    ) -> None:
        super().__init__(TABLE_DICTIONARY, service, repository, hints)

    def columns(self) -> tuple[str, ...]:
        return ("element", "column_label", "internal_type", "max_length", "mandatory", "reference")

    def build_filters(self, layout: QFormLayout) -> None:
        self.add_table_filter("name", "Table holding the fields")
        self.add_field_filter("element", "Field name", "Exact field name")
        self.add_choice_filter("internal_type", "Field type", DICTIONARY_TYPES)

    def create_response_tab(self, result: RequestResult) -> ResponseTab:
        return DictionaryResponseTab(result)


class AclRequestTab(TableRequestTab):

    fields_option: bool = False
    collapsed_sections: bool = True

    def __init__(
        self,
        service: RequestService,
        repository: ConfigRepository,
        hints: RequestHintRepository,
    ) -> None:
        super().__init__(ACL_LIST, service, repository, hints)

    def columns(self) -> tuple[str, ...]:
        return ACL_FIELDS

    def build_filters(self, layout: QFormLayout) -> None:
        self.scope_field: RadioChoiceField = RadioChoiceField(ACL_SCOPES)
        self.scope_hint: QLabel = hint_label("")
        self.acl_table_field: SuggestionField = self.table_suggestion_field()
        self.acl_field_field: SuggestionField = self.field_suggestion_field()
        self.acl_table_field.setPlaceholderText(TABLE_PLACEHOLDER)
        self.acl_field_field.setPlaceholderText(ACL_FIELD_PLACEHOLDER)
        self.add_filter_row(ACL_SCOPE_LABEL, self.scope_field)
        self.add_filter_row("", self.scope_hint)
        self.add_filter_row(required_label(ACL_TABLE_LABEL), self.acl_table_field)
        self.add_filter_row(required_label(ACL_FIELD_LABEL), self.acl_field_field)
        self.add_choice_filter(OPERATION_NAME_FIELD, "Operation", ACL_OPERATIONS)
        self.add_choice_filter("type", "Type", ACL_TYPES)
        self.add_choice_filter("active", "Active", ACTIVE_OPTIONS)
        self.scope_field.changed.connect(self._on_scope_changed)
        self.acl_field_field.textChanged.connect(self.refresh_state)
        self.require(self.acl_table_field, ACL_TABLE_REQUIRED)
        self._apply_scope()

    def scope(self) -> str:
        return self.scope_field.value()

    def protected_table(self) -> str:
        return self.acl_table_field.text().strip()

    def protected_field(self) -> str:
        return self.acl_field_field.text().strip()

    def acl_name(self) -> str:
        table = self.protected_table()
        if not table:
            return ""
        scope = self.scope()
        if scope == ACL_SCOPE_WILDCARD:
            return wildcard_name(table)
        if scope == ACL_SCOPE_FIELD:
            field = self.protected_field()
            return field_control_name(table, field) if field else ""
        return table

    def missing_requirement(self) -> str:
        missing = super().missing_requirement()
        if missing:
            return missing
        if self.scope() == ACL_SCOPE_FIELD and not self.protected_field():
            return ACL_FIELD_REQUIRED
        return ""

    def filter_conditions(self) -> list[str]:
        conditions = super().filter_conditions()
        name = self.acl_name()
        if name:
            conditions.insert(0, build_condition(NAME_FIELD, OPERATOR_IS, name))
        return conditions

    def build_request(self) -> RequestSpec:
        return acl_composite(super().build_request(), (self.acl_name(),))

    def create_response_tab(self, result: RequestResult) -> ResponseTab:
        return AclResponseTab(result)

    def _on_scope_changed(self) -> None:
        self._apply_scope()
        self.refresh_state()

    def _apply_scope(self) -> None:
        scope = self.scope()
        self.set_filter_row_visible(self.acl_field_field, scope == ACL_SCOPE_FIELD)
        self.scope_hint.setText(ACL_SCOPE_HINTS[scope])


class ClientScriptRequestTab(TableRequestTab):

    def __init__(
        self,
        service: RequestService,
        repository: ConfigRepository,
        hints: RequestHintRepository,
    ) -> None:
        super().__init__(CLIENT_SCRIPT_LIST, service, repository, hints)

    def columns(self) -> tuple[str, ...]:
        return ("name", "table", "type", "field_name", "ui_type", "active", "script")

    def build_filters(self, layout: QFormLayout) -> None:
        self.add_table_filter("table", "Table the script runs on")
        self.add_choice_filter("type", "Script type", CLIENT_SCRIPT_TYPES)
        self.add_field_filter("field_name", "Field", "Only for onChange and onCellEdit scripts")
        self.add_choice_filter("ui_type", "UI type", CLIENT_SCRIPT_UI_TYPES)
        self.add_choice_filter("active", "Active", ACTIVE_OPTIONS)

    def create_response_tab(self, result: RequestResult) -> ResponseTab:
        return ClientScriptResponseTab(result)


class BusinessRuleRequestTab(TableRequestTab):

    def __init__(
        self,
        service: RequestService,
        repository: ConfigRepository,
        hints: RequestHintRepository,
    ) -> None:
        super().__init__(BUSINESS_RULE_LIST, service, repository, hints)

    def columns(self) -> tuple[str, ...]:
        return ("name", "collection", "when", "order", "action", "active", "script")

    def build_filters(self, layout: QFormLayout) -> None:
        self.add_table_filter("collection", "Table the rule runs on")
        self.add_choice_filter("when", "When", BUSINESS_RULE_WHEN)
        self.add_choice_filter("action", "Action", BUSINESS_RULE_ACTIONS)
        self.add_choice_filter("active", "Active", ACTIVE_OPTIONS)

    def create_response_tab(self, result: RequestResult) -> ResponseTab:
        return BusinessRuleResponseTab(result)


class ScriptIncludeRequestTab(TableRequestTab):

    def __init__(
        self,
        service: RequestService,
        repository: ConfigRepository,
        hints: RequestHintRepository,
    ) -> None:
        super().__init__(SCRIPT_INCLUDE_LIST, service, repository, hints)

    def columns(self) -> tuple[str, ...]:
        return ("name", "api_name", "client_callable", "access", "active", "script")

    def build_filters(self, layout: QFormLayout) -> None:
        self.add_text_filter(
            "name",
            "Name contains",
            "Part of the script include name",
            OPERATOR_CONTAINS,
        )
        self.add_choice_filter("client_callable", "Client callable", ACTIVE_OPTIONS)
        self.add_choice_filter("access", "Access", SCRIPT_INCLUDE_ACCESS)
        self.add_choice_filter("active", "Active", ACTIVE_OPTIONS)

    def create_response_tab(self, result: RequestResult) -> ResponseTab:
        return ScriptIncludeResponseTab(result)


class DataPolicyRequestTab(TableRequestTab):

    def __init__(
        self,
        service: RequestService,
        repository: ConfigRepository,
        hints: RequestHintRepository,
    ) -> None:
        super().__init__(DATA_POLICY_LIST, service, repository, hints)

    def columns(self) -> tuple[str, ...]:
        return ("short_description", "model_table", "active", "reverse_if_false", "enforce_ui", "apply_import_set")

    def build_filters(self, layout: QFormLayout) -> None:
        self.add_table_filter("model_table", "Table the policy applies to")
        self.add_choice_filter("enforce_ui", "Enforced on the UI", ACTIVE_OPTIONS)
        self.add_choice_filter("apply_import_set", "Applied to import sets", ACTIVE_OPTIONS)
        self.add_choice_filter("active", "Active", ACTIVE_OPTIONS)

    def create_response_tab(self, result: RequestResult) -> ResponseTab:
        return DataPolicyResponseTab(result)


class UiPolicyRequestTab(TableRequestTab):

    def __init__(
        self,
        service: RequestService,
        repository: ConfigRepository,
        hints: RequestHintRepository,
    ) -> None:
        super().__init__(UI_POLICY_LIST, service, repository, hints)

    def columns(self) -> tuple[str, ...]:
        return ("short_description", "table", "active", "on_load", "reverse_if_false", "order", "script_true")

    def build_filters(self, layout: QFormLayout) -> None:
        self.add_table_filter("table", "Table the policy runs on")
        self.add_choice_filter("on_load", "Runs on load", ACTIVE_OPTIONS)
        self.add_choice_filter("reverse_if_false", "Reverses if false", ACTIVE_OPTIONS)
        self.add_choice_filter("active", "Active", ACTIVE_OPTIONS)

    def create_response_tab(self, result: RequestResult) -> ResponseTab:
        return UiPolicyResponseTab(result)


class UiActionRequestTab(TableRequestTab):

    def __init__(
        self,
        service: RequestService,
        repository: ConfigRepository,
        hints: RequestHintRepository,
    ) -> None:
        super().__init__(UI_ACTION_LIST, service, repository, hints)

    def columns(self) -> tuple[str, ...]:
        return ("name", "table", "action_name", "client", "form_button", "list_banner_button", "order", "script")

    def build_filters(self, layout: QFormLayout) -> None:
        self.add_table_filter("table", "Table the action belongs to")
        self.add_text_filter("action_name", "Action name", "Internal action name")
        self.add_choice_filter("client", "Client side", ACTIVE_OPTIONS)
        self.add_choice_filter("form_button", "Form button", ACTIVE_OPTIONS)
        self.add_choice_filter("list_banner_button", "List banner button", ACTIVE_OPTIONS)

    def create_response_tab(self, result: RequestResult) -> ResponseTab:
        return UiActionResponseTab(result)


REQUEST_TAB_CLASSES: dict[str, type[RequestTab]] = {
    TABLE_RECORDS.key: TableRecordsRequestTab,
    MULTIPLE_TABLES.key: MultipleTablesRequestTab,
    TABLE_DICTIONARY.key: DictionaryRequestTab,
    ACL_LIST.key: AclRequestTab,
    VERIFY_SECURITY.key: VerifySecurityRequestTab,
    TABLE_DESCRIPTION.key: TableDescriptionRequestTab,
    CLIENT_SCRIPT_LIST.key: ClientScriptRequestTab,
    BUSINESS_RULE_LIST.key: BusinessRuleRequestTab,
    SCRIPT_INCLUDE_LIST.key: ScriptIncludeRequestTab,
    DATA_POLICY_LIST.key: DataPolicyRequestTab,
    UI_POLICY_LIST.key: UiPolicyRequestTab,
    UI_ACTION_LIST.key: UiActionRequestTab,
}


def create_request_tab(
    key: str,
    service: RequestService,
    repository: ConfigRepository,
    hints: RequestHintRepository,
) -> RequestTab:
    return REQUEST_TAB_CLASSES[key](service, repository, hints)
