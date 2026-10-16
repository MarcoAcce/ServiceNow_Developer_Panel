from collections.abc import Sequence


def ordered_columns(
    columns: Sequence[str], records: Sequence[dict[str, str]]
) -> tuple[str, ...]:
    received: dict[str, None] = {}
    for record in records:
        for column in record:
            received.setdefault(column, None)
    if not received:
        return tuple(column for column in columns if column)
    ordered = [column for column in columns if column in received]
    known = set(ordered)
    return tuple(ordered + [column for column in received if column not in known])
