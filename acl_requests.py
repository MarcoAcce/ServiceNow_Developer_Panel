from collections.abc import Sequence
from dataclasses import replace

from query_conditions import (
    AND_SEPARATOR,
    OPERATOR_IS,
    OPERATOR_IS_ONE_OF,
    build_condition,
)
from request_model import (
    FIELDS_PARAMETER,
    LIMIT_PARAMETER,
    ORDER_PARAMETER,
    QUERY_PARAMETER,
    RequestPart,
    RequestSpec,
    RequestTarget,
)
from request_types import VERIFY_SECURITY

ACL_TABLE: str = "sys_security_acl"
ACL_ROLE_TABLE: str = "sys_security_acl_role"
ACL_OPERATION_TABLE: str = "sys_security_operation"
ACL_FIELDS: tuple[str, ...] = (
    "sys_id",
    "name",
    "operation",
    "decision_type",
    "active",
    "admin_overrides",
    "description",
    "condition",
    "script",
    "sys_updated_on",
)
ACL_ROLE_FIELDS: tuple[str, ...] = (
    "sys_security_acl",
    "sys_user_role",
    "sys_user_role.name",
)
ACL_OPERATION_FIELDS: tuple[str, ...] = ("sys_id", "name")
NAME_FIELD: str = "name"
SYS_ID_FIELD: str = "sys_id"
OPERATION_FIELD: str = "operation"
OPERATION_NAME_FIELD: str = "operation.name"
ACTIVE_FIELD: str = "active"
TYPE_FIELD: str = "type"
ROLE_ACL_FIELD: str = "sys_security_acl"
ROLE_ACL_NAME_FIELD: str = "sys_security_acl.name"
ROLE_REFERENCE_FIELD: str = "sys_user_role"
ROLE_NAME_FIELD: str = "sys_user_role.name"
RECORD_TYPE: str = "record"
ACTIVE_VALUE: str = "true"
WILDCARD_SUFFIX: str = ".*"
NAME_SEPARATOR: str = "."
VALUE_SEPARATOR: str = ","
ROLE_LIMIT: int = 10000
OPERATION_LIMIT: int = 1000
CONTROL_LIMIT: int = 1000


def field_list(fields: Sequence[str]) -> str:
    return VALUE_SEPARATOR.join(fields)


def wildcard_name(table: str) -> str:
    return f"{table}{WILDCARD_SUFFIX}"


def field_control_name(table: str, field: str) -> str:
    return f"{table}{NAME_SEPARATOR}{field}"


def name_condition(field: str, names: Sequence[str]) -> str:
    wanted = [name for name in names if name]
    if not wanted:
        return ""
    if len(wanted) == 1:
        return build_condition(field, OPERATOR_IS, wanted[0])
    return build_condition(field, OPERATOR_IS_ONE_OF, VALUE_SEPARATOR.join(wanted))


def control_query(names: Sequence[str], operation: str) -> str:
    conditions = (
        name_condition(NAME_FIELD, names),
        build_condition(OPERATION_NAME_FIELD, OPERATOR_IS, operation),
        build_condition(ACTIVE_FIELD, OPERATOR_IS, ACTIVE_VALUE),
        build_condition(TYPE_FIELD, OPERATOR_IS, RECORD_TYPE),
    )
    return AND_SEPARATOR.join(condition for condition in conditions if condition)


def role_part(names: Sequence[str]) -> RequestPart:
    parameters = {
        QUERY_PARAMETER: name_condition(ROLE_ACL_NAME_FIELD, names),
        FIELDS_PARAMETER: field_list(ACL_ROLE_FIELDS),
        LIMIT_PARAMETER: str(ROLE_LIMIT),
    }
    return RequestPart(
        table=ACL_ROLE_TABLE,
        parameters={name: value for name, value in parameters.items() if value},
        columns=ACL_ROLE_FIELDS,
    )


def operation_part() -> RequestPart:
    return RequestPart(
        table=ACL_OPERATION_TABLE,
        parameters={
            FIELDS_PARAMETER: field_list(ACL_OPERATION_FIELDS),
            LIMIT_PARAMETER: str(OPERATION_LIMIT),
        },
        columns=ACL_OPERATION_FIELDS,
    )


def acl_composite(spec: RequestSpec, names: Sequence[str]) -> RequestSpec:
    parameters = dict(spec.parameters)
    parameters[FIELDS_PARAMETER] = field_list(ACL_FIELDS)
    control = RequestPart(table=ACL_TABLE, parameters=parameters, columns=ACL_FIELDS)
    return replace(
        spec,
        table=ACL_TABLE,
        parameters=parameters,
        columns=ACL_FIELDS,
        parts=(control, role_part(names), operation_part()),
    )


def verification_request(
    names: Sequence[str], operation: str, target: RequestTarget
) -> RequestSpec:
    parameters = {
        QUERY_PARAMETER: control_query(names, operation),
        ORDER_PARAMETER: NAME_FIELD,
        LIMIT_PARAMETER: str(CONTROL_LIMIT),
    }
    spec = RequestSpec(
        request_type=VERIFY_SECURITY,
        table=ACL_TABLE,
        parameters=parameters,
        columns=(),
        target=target,
    )
    return acl_composite(spec, names)
