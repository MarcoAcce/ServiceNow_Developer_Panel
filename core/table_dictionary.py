from collections.abc import Callable, Sequence
from dataclasses import replace
from typing import NotRequired, TypedDict

from core.query_conditions import (
    AND_SEPARATOR,
    OPERATOR_IS,
    OPERATOR_IS_NOT,
    OPERATOR_IS_NOT_EMPTY,
    OPERATOR_IS_ONE_OF,
    build_condition,
)
from core.request_model import (
    RequestPart,
    RequestResult,
    RequestSpec,
    RequestTarget,
    table_parameters,
)
from core.request_types import TABLE_DICTIONARY

TABLE_OBJECT_TABLE: str = "sys_db_object"
DICTIONARY_TABLE: str = "sys_dictionary"
OVERRIDE_TABLE: str = "sys_dictionary_override"
CHOICE_TABLE: str = "sys_choice"
NAME_FIELD: str = "name"
LABEL_FIELD: str = "label"
PARENT_FIELD: str = "super_class"
ELEMENT_FIELD: str = "element"
COLUMN_LABEL_FIELD: str = "column_label"
TYPE_FIELD: str = "internal_type"
REFERENCE_FIELD: str = "reference"
ACTIVE_FIELD: str = "active"
INACTIVE_FIELD: str = "inactive"
VALUE_FIELD: str = "value"
SEQUENCE_FIELD: str = "sequence"
LANGUAGE_FIELD: str = "language"
DEPENDENT_VALUE_FIELD: str = "dependent_value"
MANDATORY_ATTRIBUTE: str = "mandatory"
READ_ONLY_ATTRIBUTE: str = "read_only"
DEFAULT_VALUE_ATTRIBUTE: str = "default_value"
DEPENDENT_ATTRIBUTE: str = "dependent"
OVERRIDABLE_ATTRIBUTES: tuple[str, ...] = (
    MANDATORY_ATTRIBUTE,
    READ_ONLY_ATTRIBUTE,
    DEFAULT_VALUE_ATTRIBUTE,
    DEPENDENT_ATTRIBUTE,
    "reference_qual",
    "attributes",
    "calculation",
)
OVERRIDE_SUFFIX: str = "_override"
TRUE_VALUE: str = "true"
PREFERRED_LANGUAGE: str = "en"
PATH_SEPARATOR: str = "."
VALUE_SEPARATOR: str = ","
HIERARCHY_DEPTH: int = 5
MAXIMUM_PARENTS: int = 50
HIERARCHY_LIMIT: int = 1
TABLE_OBJECT_LIMIT: int = MAXIMUM_PARENTS + 1
DICTIONARY_LIMIT: int = 10000
OVERRIDE_LIMIT: int = 10000
CHOICE_LIMIT: int = 20000
UNSEQUENCED: int = 2**31
PARENT_PATHS: tuple[str, ...] = tuple(
    PATH_SEPARATOR.join((PARENT_FIELD,) * level + (NAME_FIELD,))
    for level in range(1, HIERARCHY_DEPTH + 1)
)
PARENT_NAME_FIELD: str = PARENT_PATHS[0]
HIERARCHY_FIELDS: tuple[str, ...] = (NAME_FIELD, LABEL_FIELD) + PARENT_PATHS
TABLE_OBJECT_FIELDS: tuple[str, ...] = (NAME_FIELD, LABEL_FIELD, PARENT_NAME_FIELD)
DICTIONARY_FIELDS: tuple[str, ...] = (
    NAME_FIELD,
    ELEMENT_FIELD,
    COLUMN_LABEL_FIELD,
    TYPE_FIELD,
    REFERENCE_FIELD,
    "max_length",
    MANDATORY_ATTRIBUTE,
    READ_ONLY_ATTRIBUTE,
    DEFAULT_VALUE_ATTRIBUTE,
    DEPENDENT_ATTRIBUTE,
    "display",
    "choice",
    "reference_qual",
    "attributes",
)
OVERRIDE_FIELDS: tuple[str, ...] = (NAME_FIELD, "base_table", ELEMENT_FIELD) + tuple(
    field
    for attribute in OVERRIDABLE_ATTRIBUTES
    for field in (f"{attribute}{OVERRIDE_SUFFIX}", attribute)
)
CHOICE_FIELDS: tuple[str, ...] = (
    NAME_FIELD,
    ELEMENT_FIELD,
    VALUE_FIELD,
    LABEL_FIELD,
    SEQUENCE_FIELD,
    DEPENDENT_VALUE_FIELD,
    LANGUAGE_FIELD,
)


class FieldChoice(TypedDict):
    value: str
    label: str
    dependent_value: NotRequired[str]


class FieldOverride(TypedDict):
    attribute: str
    value: str
    table: str


class FieldDescription(TypedDict):
    name: str
    label: str
    type: str
    reference: str
    defined_on: str
    mandatory: bool
    read_only: bool
    default_value: NotRequired[str]
    dependent: NotRequired[str]
    overrides: NotRequired[list[FieldOverride]]
    choices: NotRequired[list[FieldChoice]]


def hierarchy_request(table: str, target: RequestTarget) -> RequestSpec:
    query = build_condition(NAME_FIELD, OPERATOR_IS, table)
    return RequestSpec(
        request_type=TABLE_DICTIONARY,
        table=TABLE_OBJECT_TABLE,
        parameters=table_parameters(query, HIERARCHY_FIELDS, "", HIERARCHY_LIMIT),
        columns=HIERARCHY_FIELDS,
        target=target,
    ).transient()


def parent_names(record: dict[str, str]) -> tuple[str, ...]:
    names: list[str] = []
    for path in PARENT_PATHS:
        name = record.get(path, "").strip()
        if not name:
            break
        names.append(name)
    return tuple(names)


def description_root(table: str, target: RequestTarget) -> RequestSpec:
    return RequestSpec(
        request_type=TABLE_DICTIONARY,
        table=table,
        parameters={},
        columns=(),
        target=target,
    )


def description_request(tables: Sequence[str], target: RequestTarget) -> RequestSpec:
    return replace(description_root(tables[0], target), parts=description_parts(tables))


def description_parts(tables: Sequence[str]) -> tuple[RequestPart, ...]:
    names = build_condition(NAME_FIELD, OPERATOR_IS_ONE_OF, VALUE_SEPARATOR.join(tables))
    return (
        table_part(TABLE_OBJECT_TABLE, (names,), TABLE_OBJECT_FIELDS, TABLE_OBJECT_LIMIT),
        table_part(
            DICTIONARY_TABLE,
            (
                names,
                build_condition(ELEMENT_FIELD, OPERATOR_IS_NOT_EMPTY, ""),
                build_condition(ACTIVE_FIELD, OPERATOR_IS, TRUE_VALUE),
            ),
            DICTIONARY_FIELDS,
            DICTIONARY_LIMIT,
        ),
        table_part(OVERRIDE_TABLE, (names,), OVERRIDE_FIELDS, OVERRIDE_LIMIT),
        table_part(
            CHOICE_TABLE,
            (names, build_condition(INACTIVE_FIELD, OPERATOR_IS_NOT, TRUE_VALUE)),
            CHOICE_FIELDS,
            CHOICE_LIMIT,
        ),
    )


def table_part(
    table: str, conditions: Sequence[str], fields: tuple[str, ...], limit: int
) -> RequestPart:
    query = AND_SEPARATOR.join(conditions)
    return RequestPart(
        table=table, parameters=table_parameters(query, fields, "", limit), columns=fields
    )


def section_records(result: RequestResult, table: str) -> list[dict[str, str]]:
    for section in result.sections:
        if section.table == table:
            return section.records
    return []


def table_chain(result: RequestResult) -> tuple[str, ...]:
    parents = {
        record.get(NAME_FIELD, ""): record.get(PARENT_NAME_FIELD, "").strip()
        for record in section_records(result, TABLE_OBJECT_TABLE)
    }
    chain: list[str] = []
    current = result.table
    while current in parents and current not in chain:
        chain.append(current)
        current = parents[current]
    return tuple(chain)


def table_label(result: RequestResult) -> str:
    for record in section_records(result, TABLE_OBJECT_TABLE):
        if record.get(NAME_FIELD, "") == result.table:
            return record.get(LABEL_FIELD, "")
    return ""


def matches_description(result: RequestResult) -> bool:
    tables = table_chain(result)
    return bool(tables) and result.request.parts == description_parts(tables)


def field_descriptions(result: RequestResult, wanted: Sequence[str]) -> list[FieldDescription]:
    tables = table_chain(result)
    overrides = nearest_overrides(section_records(result, OVERRIDE_TABLE), tables)
    choices = nearest_choices(section_records(result, CHOICE_TABLE), tables)
    descriptions: list[FieldDescription] = []
    for record in field_records(section_records(result, DICTIONARY_TABLE), tables):
        element = record.get(ELEMENT_FIELD, "")
        if wanted and element not in wanted:
            continue
        descriptions.append(
            field_description(record, overrides.get(element, []), choices.get(element, []))
        )
    return descriptions


def field_description(
    record: dict[str, str], overrides: list[FieldOverride], choices: list[FieldChoice]
) -> FieldDescription:
    effective = {attribute: record.get(attribute, "") for attribute in OVERRIDABLE_ATTRIBUTES}
    effective.update({override["attribute"]: override["value"] for override in overrides})
    description = FieldDescription(
        name=record.get(ELEMENT_FIELD, ""),
        label=record.get(COLUMN_LABEL_FIELD, ""),
        type=record.get(TYPE_FIELD, ""),
        reference=record.get(REFERENCE_FIELD, ""),
        defined_on=record.get(NAME_FIELD, ""),
        mandatory=effective[MANDATORY_ATTRIBUTE] == TRUE_VALUE,
        read_only=effective[READ_ONLY_ATTRIBUTE] == TRUE_VALUE,
    )
    if effective[DEFAULT_VALUE_ATTRIBUTE]:
        description["default_value"] = effective[DEFAULT_VALUE_ATTRIBUTE]
    if effective[DEPENDENT_ATTRIBUTE]:
        description["dependent"] = effective[DEPENDENT_ATTRIBUTE]
    if overrides:
        description["overrides"] = overrides
    if choices:
        description["choices"] = choices
    return description


def field_records(
    records: Sequence[dict[str, str]], tables: Sequence[str]
) -> list[dict[str, str]]:
    chosen: dict[str, dict[str, str]] = {}
    for record in sorted(records, key=table_rank(tables)):
        element = record.get(ELEMENT_FIELD, "").strip()
        if element:
            chosen.setdefault(element, record)
    return [chosen[element] for element in sorted(chosen)]


def nearest_overrides(
    records: Sequence[dict[str, str]], tables: Sequence[str]
) -> dict[str, list[FieldOverride]]:
    chosen: dict[tuple[str, str], FieldOverride] = {}
    for record in sorted(records, key=table_rank(tables)):
        element = record.get(ELEMENT_FIELD, "").strip()
        for attribute in OVERRIDABLE_ATTRIBUTES:
            if record.get(f"{attribute}{OVERRIDE_SUFFIX}", "") != TRUE_VALUE:
                continue
            chosen.setdefault(
                (element, attribute),
                FieldOverride(
                    attribute=attribute,
                    value=record.get(attribute, ""),
                    table=record.get(NAME_FIELD, ""),
                ),
            )
    grouped: dict[str, list[FieldOverride]] = {}
    for (element, _), override in chosen.items():
        grouped.setdefault(element, []).append(override)
    return grouped


def nearest_choices(
    records: Sequence[dict[str, str]], tables: Sequence[str]
) -> dict[str, list[FieldChoice]]:
    rank = table_rank(tables)

    def order(record: dict[str, str]) -> tuple[int, bool, int]:
        preferred = record.get(LANGUAGE_FIELD, "") == PREFERRED_LANGUAGE
        return rank(record), not preferred, sequence_of(record)

    sources: dict[str, str] = {}
    seen: set[tuple[str, str, str]] = set()
    grouped: dict[str, list[FieldChoice]] = {}
    for record in sorted(records, key=order):
        element = record.get(ELEMENT_FIELD, "").strip()
        if sources.setdefault(element, record.get(NAME_FIELD, "")) != record.get(NAME_FIELD, ""):
            continue
        dependent = record.get(DEPENDENT_VALUE_FIELD, "")
        key = (element, dependent, record.get(VALUE_FIELD, ""))
        if key in seen:
            continue
        seen.add(key)
        choice = FieldChoice(value=record.get(VALUE_FIELD, ""), label=record.get(LABEL_FIELD, ""))
        if dependent:
            choice["dependent_value"] = dependent
        grouped.setdefault(element, []).append(choice)
    return grouped


def table_rank(tables: Sequence[str]) -> Callable[[dict[str, str]], int]:
    rank = {table: index for index, table in enumerate(tables)}

    def position(record: dict[str, str]) -> int:
        return rank.get(record.get(NAME_FIELD, ""), len(rank))

    return position


def sequence_of(record: dict[str, str]) -> int:
    try:
        return int(record.get(SEQUENCE_FIELD, ""))
    except ValueError:
        return UNSEQUENCED
