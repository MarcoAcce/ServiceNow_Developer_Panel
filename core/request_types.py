from dataclasses import dataclass


@dataclass(frozen=True)
class RequestType:
    key: str
    label: str
    group: str
    table: str
    description: str
    home_label: str = ""

    @property
    def button_label(self) -> str:
        return self.home_label or self.label


GROUP_FEATURED: str = "Featured"
GROUP_TABLES: str = "Tables"
GROUP_SCRIPTS: str = "Scripts"
GROUP_UI: str = "UI elements"

TABLE_RECORDS: RequestType = RequestType(
    key="table_records",
    label="Table records",
    group=GROUP_TABLES,
    table="",
    description="Query any table by name and retrieve its records.",
)
MULTIPLE_TABLES: RequestType = RequestType(
    key="multiple_tables",
    label="Multiple tables",
    group=GROUP_FEATURED,
    table="",
    description=(
        "Request several tables one after the other, then query the cached result with sql."
    ),
    home_label="Multiple tables - queriable",
)
TABLE_DICTIONARY: RequestType = RequestType(
    key="table_dictionary",
    label="Dictionary entries",
    group=GROUP_TABLES,
    table="sys_dictionary",
    description="List the dictionary entries defined on a table.",
)
ACL_LIST: RequestType = RequestType(
    key="acl_list",
    label="ACL list",
    group=GROUP_FEATURED,
    table="sys_security_acl",
    description="Inspect the access controls of a table or a single field.",
)
VERIFY_SECURITY: RequestType = RequestType(
    key="verify_security",
    label="Verify security",
    group=GROUP_FEATURED,
    table="sys_security_acl",
    description=(
        "Check which users, by their roles, can run an operation on a table or a field."
    ),
)
TABLE_DESCRIPTION: RequestType = RequestType(
    key="table_description",
    label="Describe table",
    group=GROUP_FEATURED,
    table="sys_dictionary",
    description=(
        "List every field of a table, inherited ones included, and draw its relations."
    ),
    home_label="Describe table - dictionary",
)
CLIENT_SCRIPT_LIST: RequestType = RequestType(
    key="client_script_list",
    label="Client scripts",
    group=GROUP_SCRIPTS,
    table="sys_script_client",
    description="List the client scripts running on a table.",
)
BUSINESS_RULE_LIST: RequestType = RequestType(
    key="business_rule_list",
    label="Business rules",
    group=GROUP_SCRIPTS,
    table="sys_script",
    description="List the business rules of a table and when they run.",
)
SCRIPT_INCLUDE_LIST: RequestType = RequestType(
    key="script_include_list",
    label="Script includes",
    group=GROUP_SCRIPTS,
    table="sys_script_include",
    description="Search the script includes available on the instance.",
)
DATA_POLICY_LIST: RequestType = RequestType(
    key="data_policy_list",
    label="Data policies",
    group=GROUP_SCRIPTS,
    table="sys_data_policy2",
    description="List the data policies applied to a table.",
)
UI_POLICY_LIST: RequestType = RequestType(
    key="ui_policy_list",
    label="UI policies",
    group=GROUP_UI,
    table="sys_ui_policy",
    description="List the UI policies of a table and their conditions.",
)
UI_ACTION_LIST: RequestType = RequestType(
    key="ui_action_list",
    label="UI actions",
    group=GROUP_UI,
    table="sys_ui_action",
    description="List buttons, links and context menu items of a table.",
)

REQUEST_TYPES: tuple[RequestType, ...] = (
    TABLE_RECORDS,
    MULTIPLE_TABLES,
    TABLE_DICTIONARY,
    ACL_LIST,
    VERIFY_SECURITY,
    TABLE_DESCRIPTION,
    CLIENT_SCRIPT_LIST,
    BUSINESS_RULE_LIST,
    SCRIPT_INCLUDE_LIST,
    DATA_POLICY_LIST,
    UI_POLICY_LIST,
    UI_ACTION_LIST,
)

TABLE_API_GROUPS: tuple[str, ...] = (
    GROUP_TABLES,
    GROUP_SCRIPTS,
    GROUP_UI,
)

ANY_VALUE: str = "Any"


def request_types_of_group(group: str) -> tuple[RequestType, ...]:
    return tuple(request_type for request_type in REQUEST_TYPES if request_type.group == group)


def request_type_of_key(key: str) -> RequestType:
    for request_type in REQUEST_TYPES:
        if request_type.key == key:
            return request_type
    raise KeyError(key)
