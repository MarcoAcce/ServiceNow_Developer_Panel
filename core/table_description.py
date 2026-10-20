from collections.abc import Sequence
from dataclasses import dataclass
from enum import StrEnum

from core.query_conditions import (
    AND_SEPARATOR,
    OPERATOR_IS,
    OPERATOR_IS_NOT,
    OPERATOR_IS_NOT_EMPTY,
    OPERATOR_IS_ONE_OF,
    OR_SEPARATOR,
    build_condition,
)
from core.request_model import RequestPart, RequestResult, RequestSpec, RequestTarget
from core.request_types import TABLE_DESCRIPTION
from core.table_dictionary import (
    ACTIVE_FIELD,
    CHOICE_FIELDS,
    CHOICE_LIMIT,
    CHOICE_TABLE,
    DICTIONARY_FIELDS,
    DICTIONARY_LIMIT,
    DICTIONARY_TABLE,
    ELEMENT_FIELD,
    INACTIVE_FIELD,
    LABEL_FIELD,
    NAME_FIELD,
    OVERRIDE_FIELDS,
    OVERRIDE_LIMIT,
    OVERRIDE_TABLE,
    PARENT_NAME_FIELD,
    REFERENCE_FIELD,
    TABLE_OBJECT_TABLE,
    TRUE_VALUE,
    TYPE_FIELD,
    VALUE_SEPARATOR,
    FieldDescription,
    field_description,
    field_records,
    nearest_choices,
    nearest_overrides,
    section_records,
    table_chain,
    table_part,
)

M2M_TABLE: str = "sys_m2m"
FROM_TABLE_FIELD: str = "from_table"
TO_TABLE_FIELD: str = "to_table"
M2M_TABLE_FIELD: str = "m2m_table"
UNIQUE_FIELD: str = "unique"
DISPLAY_FIELD: str = "display"
MAX_LENGTH_FIELD: str = "max_length"
ATTRIBUTES_FIELD: str = "attributes"
REFERENCE_QUAL_FIELD: str = "reference_qual"
REFERENCE_CONDITION_FIELD: str = "reference_qual_condition"
REFERENCE_QUAL_TYPE_FIELD: str = "use_reference_qualifier"
DEFINED_ON_FIELD: str = "defined_on"
MANDATORY_COLUMN: str = "mandatory"
READ_ONLY_COLUMN: str = "read_only"
LIST_TYPE: str = "glide_list"
NEW_QUERY_SEPARATOR: str = "^NQ"
FALSE_VALUE: str = "false"
OBJECT_LIMIT: int = 10000
M2M_LIMIT: int = 1000
OBJECT_FIELDS: tuple[str, ...] = (NAME_FIELD, LABEL_FIELD, PARENT_NAME_FIELD)
DESCRIPTION_FIELDS: tuple[str, ...] = DICTIONARY_FIELDS + (
    ACTIVE_FIELD,
    UNIQUE_FIELD,
    REFERENCE_CONDITION_FIELD,
    REFERENCE_QUAL_TYPE_FIELD,
)
M2M_FIELDS: tuple[str, ...] = (FROM_TABLE_FIELD, TO_TABLE_FIELD, M2M_TABLE_FIELD)
ACTIVE_CONDITION: str = build_condition(ACTIVE_FIELD, OPERATOR_IS, TRUE_VALUE)


class RelationKind(StrEnum):
    PARENT = "parent"
    CHILD = "child"
    ONE_TO_ONE = "one_to_one"
    ONE_TO_MANY = "one_to_many"
    MANY_TO_MANY = "many_to_many"


KIND_ORDER: tuple[RelationKind, ...] = (
    RelationKind.PARENT,
    RelationKind.CHILD,
    RelationKind.ONE_TO_ONE,
    RelationKind.ONE_TO_MANY,
    RelationKind.MANY_TO_MANY,
)


@dataclass(frozen=True)
class Relation:
    table: str
    kind: RelationKind
    outgoing: bool
    via: tuple[str, ...] = ()


@dataclass(frozen=True)
class DescribedField:
    row: dict[str, str]
    record: dict[str, str]
    description: FieldDescription


def description_request(
    tables: Sequence[str], active_only: bool, target: RequestTarget
) -> RequestSpec:
    return RequestSpec(
        request_type=TABLE_DESCRIPTION,
        table=tables[0],
        parameters={},
        columns=(),
        target=target,
        parts=description_parts(tables, active_only),
    )


def description_parts(tables: Sequence[str], active_only: bool) -> tuple[RequestPart, ...]:
    table = tables[0]
    names = build_condition(NAME_FIELD, OPERATOR_IS_ONE_OF, VALUE_SEPARATOR.join(tables))
    children = build_condition(PARENT_NAME_FIELD, OPERATOR_IS, table)
    active = (ACTIVE_CONDITION,) if active_only else ()
    fields = AND_SEPARATOR.join(
        (names, build_condition(ELEMENT_FIELD, OPERATOR_IS_NOT_EMPTY, "")) + active
    )
    references = AND_SEPARATOR.join(
        (build_condition(REFERENCE_FIELD, OPERATOR_IS, table),) + active
    )
    linked = (
        build_condition(FROM_TABLE_FIELD, OPERATOR_IS, table)
        + OR_SEPARATOR
        + build_condition(TO_TABLE_FIELD, OPERATOR_IS, table)
    )
    return (
        table_part(
            TABLE_OBJECT_TABLE, (names + OR_SEPARATOR + children,), OBJECT_FIELDS, OBJECT_LIMIT
        ),
        table_part(
            DICTIONARY_TABLE,
            (fields + NEW_QUERY_SEPARATOR + references,),
            DESCRIPTION_FIELDS,
            DICTIONARY_LIMIT,
        ),
        table_part(OVERRIDE_TABLE, (names,), OVERRIDE_FIELDS, OVERRIDE_LIMIT),
        table_part(
            CHOICE_TABLE,
            (names, build_condition(INACTIVE_FIELD, OPERATOR_IS_NOT, TRUE_VALUE)),
            CHOICE_FIELDS,
            CHOICE_LIMIT,
        ),
        table_part(M2M_TABLE, (linked,), M2M_FIELDS, M2M_LIMIT),
    )


def active_only(result: RequestResult) -> bool:
    for part in result.request.parts:
        if part.table == DICTIONARY_TABLE:
            return ACTIVE_CONDITION in part.query_string
    return True


def described_fields(result: RequestResult) -> list[DescribedField]:
    tables = table_chain(result)
    own = [
        record
        for record in section_records(result, DICTIONARY_TABLE)
        if record.get(NAME_FIELD, "") in tables
    ]
    overrides = nearest_overrides(section_records(result, OVERRIDE_TABLE), tables)
    choices = nearest_choices(section_records(result, CHOICE_TABLE), tables)
    described: list[DescribedField] = []
    for record in field_records(own, tables):
        element = record.get(ELEMENT_FIELD, "")
        description = field_description(
            record, overrides.get(element, []), choices.get(element, [])
        )
        described.append(
            DescribedField(
                row=field_row(record, description), record=record, description=description
            )
        )
    return described


def field_row(record: dict[str, str], description: FieldDescription) -> dict[str, str]:
    return {
        ELEMENT_FIELD: description["name"],
        "column_label": description["label"],
        TYPE_FIELD: description["type"],
        REFERENCE_FIELD: description["reference"],
        MANDATORY_COLUMN: flag(description["mandatory"]),
        READ_ONLY_COLUMN: flag(description["read_only"]),
        DISPLAY_FIELD: record.get(DISPLAY_FIELD, ""),
        ACTIVE_FIELD: record.get(ACTIVE_FIELD, ""),
        DEFINED_ON_FIELD: description["defined_on"],
    }


def flag(value: bool) -> str:
    return TRUE_VALUE if value else FALSE_VALUE


def relations(result: RequestResult, fields: Sequence[DescribedField]) -> list[Relation]:
    table = result.table
    tables = table_chain(result)
    found: dict[tuple[str, RelationKind, bool], list[str]] = {}

    def add(other: str, kind: RelationKind, outgoing: bool, via: str = "") -> None:
        if not other:
            return
        names = found.setdefault((other, kind, outgoing), [])
        if via and via not in names:
            names.append(via)

    for parent in tables[1:]:
        add(parent, RelationKind.PARENT, True)
    for record in section_records(result, TABLE_OBJECT_TABLE):
        name = record.get(NAME_FIELD, "")
        if record.get(PARENT_NAME_FIELD, "") == table and name != table:
            add(name, RelationKind.CHILD, False)
    for field in fields:
        reference = field.description["reference"]
        add(reference, reference_kind(field.record), True, field.description["name"])
    for record in section_records(result, DICTIONARY_TABLE):
        name = record.get(NAME_FIELD, "")
        if record.get(REFERENCE_FIELD, "") != table or name in tables:
            continue
        add(name, reference_kind(record), False, record.get(ELEMENT_FIELD, ""))
    for record in section_records(result, M2M_TABLE):
        outgoing = record.get(FROM_TABLE_FIELD, "") == table
        other = record.get(TO_TABLE_FIELD if outgoing else FROM_TABLE_FIELD, "")
        add(other, RelationKind.MANY_TO_MANY, outgoing, record.get(M2M_TABLE_FIELD, ""))
    ordered = [
        Relation(table=other, kind=kind, outgoing=outgoing, via=tuple(via))
        for (other, kind, outgoing), via in found.items()
    ]
    parents = [relation for relation in ordered if relation.kind is RelationKind.PARENT]
    others = sorted(
        (relation for relation in ordered if relation.kind is not RelationKind.PARENT),
        key=lambda relation: (KIND_ORDER.index(relation.kind), relation.table),
    )
    return parents + others


def reference_kind(record: dict[str, str]) -> RelationKind:
    if record.get(TYPE_FIELD, "") == LIST_TYPE:
        return RelationKind.MANY_TO_MANY
    if record.get(UNIQUE_FIELD, "") == TRUE_VALUE:
        return RelationKind.ONE_TO_ONE
    return RelationKind.ONE_TO_MANY
