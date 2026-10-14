from PySide6.QtWidgets import QFormLayout

from request_tab import RequestTab
from request_types import (
    ACL_LIST,
    BUSINESS_RULE_LIST,
    CLIENT_SCRIPT_LIST,
    DATA_POLICY_LIST,
    SCRIPT_INCLUDE_LIST,
    TABLE_DICTIONARY,
    TABLE_RECORDS,
    UI_ACTION_LIST,
    UI_POLICY_LIST,
)
from response_tab import ResponseTab
from response_tabs import (
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
from service import RequestResult, RequestService

ACTIVE_OPTIONS: tuple[str, ...] = ("true", "false")
ACL_OPERATIONS: tuple[str, ...] = ("read", "write", "create", "delete", "report_on")
ACL_TYPES: tuple[str, ...] = ("record", "client_callable_script_include", "processor", "ui_page")
CLIENT_SCRIPT_TYPES: tuple[str, ...] = ("onLoad", "onChange", "onSubmit", "onCellEdit")
CLIENT_SCRIPT_UI_TYPES: tuple[str, ...] = ("Desktop", "Mobile", "Both")
BUSINESS_RULE_WHEN: tuple[str, ...] = ("before", "after", "async", "display")
BUSINESS_RULE_ACTIONS: tuple[str, ...] = ("insert", "update", "delete", "query")
SCRIPT_INCLUDE_ACCESS: tuple[str, ...] = ("public", "package_private")
DICTIONARY_TYPES: tuple[str, ...] = ("string", "reference", "glide_date_time", "boolean", "integer", "journal_input")


class TableRecordsRequestTab(RequestTab):

    def __init__(self, service: RequestService) -> None:
        super().__init__(TABLE_RECORDS, service)

    def columns(self) -> tuple[str, ...]:
        return ("number", "short_description", "sys_created_on", "sys_updated_on", "sys_id")

    def build_filters(self, layout: QFormLayout) -> None:
        self.add_text_filter("active", "Active", "true, false or empty")
        self.add_text_filter("sys_created_onRELATIVEGE", "Created in the last", "for example javascript:gs.daysAgo(7)")

    def create_response_tab(self, result: RequestResult) -> ResponseTab:
        return TableRecordsResponseTab(result)


class DictionaryRequestTab(RequestTab):

    def __init__(self, service: RequestService) -> None:
        super().__init__(TABLE_DICTIONARY, service)

    def columns(self) -> tuple[str, ...]:
        return ("element", "column_label", "internal_type", "max_length", "mandatory", "reference")

    def build_filters(self, layout: QFormLayout) -> None:
        self.add_text_filter("name", "Table", "Table holding the fields")
        self.add_text_filter("element", "Field name", "Exact field name")
        self.add_choice_filter("internal_type", "Field type", DICTIONARY_TYPES)

    def create_response_tab(self, result: RequestResult) -> ResponseTab:
        return DictionaryResponseTab(result)


class AclRequestTab(RequestTab):

    def __init__(self, service: RequestService) -> None:
        super().__init__(ACL_LIST, service)

    def columns(self) -> tuple[str, ...]:
        return ("name", "operation", "admin_overrides", "active", "description", "script")

    def build_filters(self, layout: QFormLayout) -> None:
        self.add_text_filter("nameSTARTSWITH", "Table", "Table protected by the ACL")
        self.add_text_filter("nameCONTAINS", "Field", "Field name, for empty record level ACL")
        self.add_choice_filter("operation", "Operation", ACL_OPERATIONS)
        self.add_choice_filter("type", "Type", ACL_TYPES)
        self.add_choice_filter("active", "Active", ACTIVE_OPTIONS)

    def create_response_tab(self, result: RequestResult) -> ResponseTab:
        return AclResponseTab(result)


class ClientScriptRequestTab(RequestTab):

    def __init__(self, service: RequestService) -> None:
        super().__init__(CLIENT_SCRIPT_LIST, service)

    def columns(self) -> tuple[str, ...]:
        return ("name", "table", "type", "field_name", "ui_type", "active", "script")

    def build_filters(self, layout: QFormLayout) -> None:
        self.add_text_filter("table", "Table", "Table the script runs on")
        self.add_choice_filter("type", "Script type", CLIENT_SCRIPT_TYPES)
        self.add_text_filter("field_name", "Field", "Only for onChange and onCellEdit scripts")
        self.add_choice_filter("ui_type", "UI type", CLIENT_SCRIPT_UI_TYPES)
        self.add_choice_filter("active", "Active", ACTIVE_OPTIONS)

    def create_response_tab(self, result: RequestResult) -> ResponseTab:
        return ClientScriptResponseTab(result)


class BusinessRuleRequestTab(RequestTab):

    def __init__(self, service: RequestService) -> None:
        super().__init__(BUSINESS_RULE_LIST, service)

    def columns(self) -> tuple[str, ...]:
        return ("name", "collection", "when", "order", "action", "active", "script")

    def build_filters(self, layout: QFormLayout) -> None:
        self.add_text_filter("collection", "Table", "Table the rule runs on")
        self.add_choice_filter("when", "When", BUSINESS_RULE_WHEN)
        self.add_choice_filter("action", "Action", BUSINESS_RULE_ACTIONS)
        self.add_choice_filter("active", "Active", ACTIVE_OPTIONS)

    def create_response_tab(self, result: RequestResult) -> ResponseTab:
        return BusinessRuleResponseTab(result)


class ScriptIncludeRequestTab(RequestTab):

    def __init__(self, service: RequestService) -> None:
        super().__init__(SCRIPT_INCLUDE_LIST, service)

    def columns(self) -> tuple[str, ...]:
        return ("name", "api_name", "client_callable", "access", "active", "script")

    def build_filters(self, layout: QFormLayout) -> None:
        self.add_text_filter("nameCONTAINS", "Name contains", "Part of the script include name")
        self.add_choice_filter("client_callable", "Client callable", ACTIVE_OPTIONS)
        self.add_choice_filter("access", "Access", SCRIPT_INCLUDE_ACCESS)
        self.add_choice_filter("active", "Active", ACTIVE_OPTIONS)

    def create_response_tab(self, result: RequestResult) -> ResponseTab:
        return ScriptIncludeResponseTab(result)


class DataPolicyRequestTab(RequestTab):

    def __init__(self, service: RequestService) -> None:
        super().__init__(DATA_POLICY_LIST, service)

    def columns(self) -> tuple[str, ...]:
        return ("short_description", "model_table", "active", "reverse_if_false", "enforce_ui", "apply_import_set")

    def build_filters(self, layout: QFormLayout) -> None:
        self.add_text_filter("model_table", "Table", "Table the policy applies to")
        self.add_choice_filter("enforce_ui", "Enforced on the UI", ACTIVE_OPTIONS)
        self.add_choice_filter("apply_import_set", "Applied to import sets", ACTIVE_OPTIONS)
        self.add_choice_filter("active", "Active", ACTIVE_OPTIONS)

    def create_response_tab(self, result: RequestResult) -> ResponseTab:
        return DataPolicyResponseTab(result)


class UiPolicyRequestTab(RequestTab):

    def __init__(self, service: RequestService) -> None:
        super().__init__(UI_POLICY_LIST, service)

    def columns(self) -> tuple[str, ...]:
        return ("short_description", "table", "active", "on_load", "reverse_if_false", "order", "script_true")

    def build_filters(self, layout: QFormLayout) -> None:
        self.add_text_filter("table", "Table", "Table the policy runs on")
        self.add_choice_filter("on_load", "Runs on load", ACTIVE_OPTIONS)
        self.add_choice_filter("reverse_if_false", "Reverses if false", ACTIVE_OPTIONS)
        self.add_choice_filter("active", "Active", ACTIVE_OPTIONS)

    def create_response_tab(self, result: RequestResult) -> ResponseTab:
        return UiPolicyResponseTab(result)


class UiActionRequestTab(RequestTab):

    def __init__(self, service: RequestService) -> None:
        super().__init__(UI_ACTION_LIST, service)

    def columns(self) -> tuple[str, ...]:
        return ("name", "table", "action_name", "client", "form_button", "list_banner_button", "order", "script")

    def build_filters(self, layout: QFormLayout) -> None:
        self.add_text_filter("table", "Table", "Table the action belongs to")
        self.add_text_filter("action_name", "Action name", "Internal action name")
        self.add_choice_filter("client", "Client side", ACTIVE_OPTIONS)
        self.add_choice_filter("form_button", "Form button", ACTIVE_OPTIONS)
        self.add_choice_filter("list_banner_button", "List banner button", ACTIVE_OPTIONS)

    def create_response_tab(self, result: RequestResult) -> ResponseTab:
        return UiActionResponseTab(result)


REQUEST_TAB_CLASSES: dict[str, type[RequestTab]] = {
    TABLE_RECORDS.key: TableRecordsRequestTab,
    TABLE_DICTIONARY.key: DictionaryRequestTab,
    ACL_LIST.key: AclRequestTab,
    CLIENT_SCRIPT_LIST.key: ClientScriptRequestTab,
    BUSINESS_RULE_LIST.key: BusinessRuleRequestTab,
    SCRIPT_INCLUDE_LIST.key: ScriptIncludeRequestTab,
    DATA_POLICY_LIST.key: DataPolicyRequestTab,
    UI_POLICY_LIST.key: UiPolicyRequestTab,
    UI_ACTION_LIST.key: UiActionRequestTab,
}


def create_request_tab(key: str, service: RequestService) -> RequestTab:
    return REQUEST_TAB_CLASSES[key](service)
