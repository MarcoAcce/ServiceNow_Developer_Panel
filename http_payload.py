import json
from typing import Any

from request_model import LIMIT_PARAMETER, OFFSET_PARAMETER, RequestSpec

REQUEST_TIMEOUT_MS: int = 30000
MAXIMUM_PAGE_SIZE: int = 10000
HTTP_ERROR_STATUS: int = 400
RESULT_KEY: str = "result"
ERROR_KEY: str = "error"
MESSAGE_KEY: str = "message"
DETAIL_KEY: str = "detail"
VALUE_KEY: str = "value"
DISPLAY_VALUE_KEY: str = "display_value"
MESSAGE_SEPARATOR: str = ": "
TRUE_VALUE: str = "true"
FALSE_VALUE: str = "false"
INVALID_PAYLOAD_MESSAGE: str = "the instance answered with a body that is not valid json"
UNEXPECTED_PAYLOAD_MESSAGE: str = "the instance answered without a result list"
STATUS_MESSAGE: str = "the instance answered with the status {status}"
NO_RESPONSE_MESSAGE: str = "the instance did not answer"


def parameter_value(request: RequestSpec, name: str) -> int:
    value = request.parameters.get(name, "").strip()
    return int(value) if value.isdigit() else 0


def is_paged(wanted: int) -> bool:
    return wanted > MAXIMUM_PAGE_SIZE


def page_size(wanted: int, collected: int) -> int:
    return min(MAXIMUM_PAGE_SIZE, wanted - collected)


def page_overrides(size: int, offset: int, collected: int) -> dict[str, str]:
    return {
        LIMIT_PARAMETER: str(size),
        OFFSET_PARAMETER: str(offset + collected),
    }


def has_more(wanted: int, collected: int, received: int, size: int) -> bool:
    if not is_paged(wanted) or received < size:
        return False
    return collected < wanted


def response_records(payload: bytes) -> list[dict[str, str]]:
    result = response_document(payload).get(RESULT_KEY)
    if isinstance(result, dict):
        result = [result]
    if not isinstance(result, list):
        raise ValueError(UNEXPECTED_PAYLOAD_MESSAGE)
    return [record_of(entry) for entry in result if isinstance(entry, dict)]


def response_document(payload: bytes) -> dict[str, Any]:
    if not payload:
        raise ValueError(NO_RESPONSE_MESSAGE)
    try:
        document = json.loads(payload.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise ValueError(INVALID_PAYLOAD_MESSAGE) from error
    if not isinstance(document, dict):
        raise ValueError(UNEXPECTED_PAYLOAD_MESSAGE)
    return document


def error_message(payload: bytes, reason: str, status: int) -> str:
    details = payload_error(payload)
    if details and reason:
        return f"{reason}{MESSAGE_SEPARATOR}{details}"
    return details or reason or STATUS_MESSAGE.format(status=status)


def payload_error(payload: bytes) -> str:
    try:
        document = response_document(payload)
    except ValueError:
        return ""
    details = document.get(ERROR_KEY)
    if not isinstance(details, dict):
        return ""
    parts = [
        str(details.get(key, "")).strip()
        for key in (MESSAGE_KEY, DETAIL_KEY)
        if str(details.get(key, "")).strip()
    ]
    return MESSAGE_SEPARATOR.join(parts)


def record_of(entry: dict[str, Any]) -> dict[str, str]:
    return {str(key): value_of(value) for key, value in entry.items()}


def value_of(value: Any) -> str:
    if isinstance(value, dict):
        for key in (DISPLAY_VALUE_KEY, VALUE_KEY):
            if key in value:
                return value_of(value[key])
        return ""
    if value is None:
        return ""
    if isinstance(value, bool):
        return TRUE_VALUE if value else FALSE_VALUE
    return str(value)
