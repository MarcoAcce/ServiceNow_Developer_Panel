from collections.abc import Sequence
from dataclasses import dataclass

from core.acl.acl_requests import (
    ACL_OPERATION_TABLE,
    ACL_ROLE_TABLE,
    ACL_TABLE,
    ROLE_ACL_FIELD,
    ROLE_NAME_FIELD,
    ROLE_REFERENCE_FIELD,
)
from core.request_model import RequestResult

TRUE_VALUE: str = "true"
FALSE_VALUE: str = "false"
DENY_PREFIX: str = "deny"
ALLOW_LABEL: str = "Allow if"
DENY_LABEL: str = "Deny unless"
ROLE_SEPARATOR: str = ", "
NO_ROLE_LABEL: str = "none"
SYS_ID_FIELD: str = "sys_id"
NAME_FIELD: str = "name"
OPERATION_FIELD: str = "operation"
DECISION_FIELD: str = "decision_type"
ACTIVE_FIELD: str = "active"
ADMIN_FIELD: str = "admin_overrides"
DESCRIPTION_FIELD: str = "description"
CONDITION_FIELD: str = "condition"
SCRIPT_FIELD: str = "script"
UPDATED_FIELD: str = "sys_updated_on"
ROLES_COLUMN: str = "roles"
SCRIPT_FLAG_COLUMN: str = "has_script"

GRID_COLUMNS: tuple[str, ...] = (
    OPERATION_FIELD,
    DECISION_FIELD,
    ACTIVE_FIELD,
    ADMIN_FIELD,
    ROLES_COLUMN,
    SCRIPT_FLAG_COLUMN,
    UPDATED_FIELD,
)
GRID_CHECKBOX_COLUMNS: tuple[str, ...] = (ADMIN_FIELD, SCRIPT_FLAG_COLUMN)
EXPORT_COLUMNS: tuple[str, ...] = (
    NAME_FIELD,
    OPERATION_FIELD,
    DECISION_FIELD,
    ACTIVE_FIELD,
    ROLES_COLUMN,
    ADMIN_FIELD,
    DESCRIPTION_FIELD,
    CONDITION_FIELD,
    SCRIPT_FIELD,
    UPDATED_FIELD,
)
COLUMN_LABELS: dict[str, str] = {
    OPERATION_FIELD: "Operation",
    DECISION_FIELD: "Decision",
    ACTIVE_FIELD: "Active",
    ROLES_COLUMN: "Roles",
    SCRIPT_FLAG_COLUMN: "Has script",
    UPDATED_FIELD: "Updated",
    ADMIN_FIELD: "Admin overrides",
    CONDITION_FIELD: "Condition",
}


@dataclass(frozen=True)
class AccessControl:
    sys_id: str
    name: str
    operation: str
    decision_type: str
    active: str
    admin_overrides: str
    description: str
    condition: str
    script: str
    updated_on: str
    roles: tuple[str, ...] = ()

    @property
    def deny_unless(self) -> bool:
        return self.decision_type.strip().lower().startswith(DENY_PREFIX)

    @property
    def decision_label(self) -> str:
        return DENY_LABEL if self.deny_unless else ALLOW_LABEL

    @property
    def is_active(self) -> bool:
        return self.active.strip().lower() == TRUE_VALUE

    @property
    def overrides_admin(self) -> bool:
        return self.admin_overrides.strip().lower() == TRUE_VALUE

    @property
    def has_condition(self) -> bool:
        return bool(self.condition.strip())

    @property
    def has_script(self) -> bool:
        return bool(self.script.strip())

    @property
    def dynamic(self) -> bool:
        return self.has_condition or self.has_script

    @property
    def role_label(self) -> str:
        return ROLE_SEPARATOR.join(self.roles) or NO_ROLE_LABEL


def flag(value: bool) -> str:
    return TRUE_VALUE if value else FALSE_VALUE


def section_records(result: RequestResult, table: str) -> list[dict[str, str]]:
    for section in result.sections:
        if section.table == table:
            return section.records
    if table == ACL_TABLE and not result.sections:
        return result.records
    return []


def role_names(records: Sequence[dict[str, str]]) -> dict[str, tuple[str, ...]]:
    collected: dict[str, list[str]] = {}
    for record in records:
        control = record.get(ROLE_ACL_FIELD, "").strip()
        name = record.get(ROLE_NAME_FIELD, "").strip()
        if not name:
            name = record.get(ROLE_REFERENCE_FIELD, "").strip()
        if control and name:
            collected.setdefault(control, []).append(name)
    return {
        control: tuple(sorted(set(names))) for control, names in collected.items()
    }


def operation_names(records: Sequence[dict[str, str]]) -> dict[str, str]:
    collected: dict[str, str] = {}
    for record in records:
        sys_id = record.get(SYS_ID_FIELD, "").strip()
        name = record.get(NAME_FIELD, "").strip()
        if sys_id and name:
            collected[sys_id] = name
    return collected


def control_of(
    record: dict[str, str], roles: tuple[str, ...], operations: dict[str, str]
) -> AccessControl:
    operation = record.get(OPERATION_FIELD, "").strip()
    return AccessControl(
        sys_id=record.get(SYS_ID_FIELD, ""),
        name=record.get(NAME_FIELD, ""),
        operation=operations.get(operation, operation),
        decision_type=record.get(DECISION_FIELD, ""),
        active=record.get(ACTIVE_FIELD, ""),
        admin_overrides=record.get(ADMIN_FIELD, ""),
        description=record.get(DESCRIPTION_FIELD, ""),
        condition=record.get(CONDITION_FIELD, ""),
        script=record.get(SCRIPT_FIELD, ""),
        updated_on=record.get(UPDATED_FIELD, ""),
        roles=roles,
    )


def controls_of(result: RequestResult) -> tuple[AccessControl, ...]:
    roles = role_names(section_records(result, ACL_ROLE_TABLE))
    operations = operation_names(section_records(result, ACL_OPERATION_TABLE))
    return tuple(
        control_of(record, roles.get(record.get(SYS_ID_FIELD, ""), ()), operations)
        for record in section_records(result, ACL_TABLE)
    )


def display_record(control: AccessControl) -> dict[str, str]:
    return {
        NAME_FIELD: control.name,
        OPERATION_FIELD: control.operation,
        DECISION_FIELD: control.decision_label,
        ACTIVE_FIELD: control.active,
        ROLES_COLUMN: control.role_label,
        SCRIPT_FLAG_COLUMN: flag(control.has_script),
        ADMIN_FIELD: control.admin_overrides,
        DESCRIPTION_FIELD: control.description,
        CONDITION_FIELD: control.condition,
        SCRIPT_FIELD: control.script,
        UPDATED_FIELD: control.updated_on,
    }


def display_records(controls: Sequence[AccessControl]) -> list[dict[str, str]]:
    return [display_record(control) for control in controls]
