from collections.abc import Iterable
from dataclasses import dataclass


@dataclass(frozen=True)
class QueryOperator:
    key: str
    label: str
    takes_value: bool = True


OPERATORS: tuple[QueryOperator, ...] = (
    QueryOperator("=", "is"),
    QueryOperator("!=", "is not"),
    QueryOperator("STARTSWITH", "starts with"),
    QueryOperator("ENDSWITH", "ends with"),
    QueryOperator("LIKE", "contains"),
    QueryOperator("NOT LIKE", "does not contain"),
    QueryOperator("IN", "is one of"),
    QueryOperator("NOT IN", "is not one of"),
    QueryOperator(">", "greater than"),
    QueryOperator(">=", "greater than or is"),
    QueryOperator("<", "less than"),
    QueryOperator("<=", "less than or is"),
    QueryOperator("ISEMPTY", "is empty", False),
    QueryOperator("ISNOTEMPTY", "is not empty", False),
    QueryOperator("EMPTYSTRING", "is an empty string", False),
    QueryOperator("ANYTHING", "is anything", False),
)

OPERATOR_IS: QueryOperator = OPERATORS[0]
OPERATOR_IS_NOT: QueryOperator = OPERATORS[1]
OPERATOR_STARTS_WITH: QueryOperator = OPERATORS[2]
OPERATOR_CONTAINS: QueryOperator = OPERATORS[4]
OPERATOR_IS_ONE_OF: QueryOperator = OPERATORS[6]
OPERATOR_ON_OR_AFTER: QueryOperator = OPERATORS[9]

AND_SEPARATOR: str = "^"
OR_SEPARATOR: str = "^OR"
OPEN_PAREN: str = "("
CLOSE_PAREN: str = ")"


def build_condition(field: str, operator: QueryOperator, value: str) -> str:
    if not field:
        return ""
    if not operator.takes_value:
        return f"{field}{operator.key}"
    if not value:
        return ""
    return f"{field}{operator.key}{value}"


def encode_groups(groups: Iterable[Iterable[str]]) -> str:
    encoded: list[str] = []
    for group in groups:
        conditions = [condition for condition in group if condition]
        if conditions:
            encoded.append(OR_SEPARATOR.join(conditions))
    return AND_SEPARATOR.join(encoded)
