import sqlite3
import time
import urllib.request
from collections.abc import Callable

from configuration.config_repository import ConfigRepository, Instance
from core.database_manager import DatabaseError
from core.oauth import OAuthError
from core.request_model import (
    COMPOSITE_STATUS_CODE,
    LIMIT_PARAMETER,
    OFFSET_PARAMETER,
    PART_ERROR_MESSAGE,
    PreparedRequest,
    RequestResult,
    RequestSpec,
    RequestTarget,
    ResultSection,
    ServiceConfigurationError,
    composite_result,
    prepare_request,
    section_of,
)
from services.http_payload import (
    HTTP_ERROR_STATUS,
    error_message,
    has_more,
    is_paged,
    page_overrides,
    page_size,
    parameter_value,
    response_records,
)
from services.oauth_tokens import UNAUTHORIZED_STATUS, TokenManager, is_oauth_target
from services.sync_http import (
    REQUEST_TIMEOUT_SECONDS,
    HttpAnswer,
    TransportError,
    build_opener,
    send,
)
from storage.response_repository import ResponseRepository, cached_result


class RequestFailure(Exception):

    def __init__(self, message: str, status_code: int = 0) -> None:
        super().__init__(message)
        self.message: str = message
        self.status_code: int = status_code


class SyncRequestService:

    def __init__(self, responses: ResponseRepository, tokens: TokenManager) -> None:
        self._responses: ResponseRepository = responses
        self._tokens: TokenManager = tokens
        self._opener: urllib.request.OpenerDirector = build_opener()

    def send(self, request: RequestSpec) -> RequestResult:
        started = time.monotonic()
        try:
            cached = self._responses.load_cached(request)
        except (sqlite3.Error, DatabaseError, OSError):
            cached = None
        if cached is not None:
            return cached_result(request, cached, elapsed_ms(started))
        result = self._execute(request)
        if not request.stored:
            return result
        stored = self._responses.named(result)
        try:
            self._responses.record(stored)
        except (sqlite3.Error, DatabaseError, OSError, TimeoutError):
            return result
        return stored

    def _execute(self, request: RequestSpec) -> RequestResult:
        if request.composite:
            return self._execute_composite(request)
        return self._execute_single(request)

    def _execute_composite(self, request: RequestSpec) -> RequestResult:
        started = time.monotonic()
        sections: list[ResultSection] = []
        status = COMPOSITE_STATUS_CODE
        for part in request.part_specs():
            try:
                result = self._execute_single(part)
            except RequestFailure as failure:
                raise RequestFailure(
                    PART_ERROR_MESSAGE.format(table=part.table, message=failure.message),
                    failure.status_code,
                ) from None
            status = result.status_code
            sections.append(section_of(result))
        return composite_result(request, sections, status, elapsed_ms(started))

    def _execute_single(self, request: RequestSpec) -> RequestResult:
        started = time.monotonic()
        wanted = parameter_value(request, LIMIT_PARAMETER)
        offset = parameter_value(request, OFFSET_PARAMETER)
        records: list[dict[str, str]] = []
        size = 0
        while True:
            overrides: dict[str, str] = {}
            if is_paged(wanted):
                size = page_size(wanted, len(records))
                overrides = page_overrides(size, offset, len(records))
            status, received = self._fetch(request, overrides)
            records.extend(received)
            if not has_more(wanted, len(records), len(received), size):
                break
        return RequestResult(
            request=request,
            records=records,
            status_code=status,
            elapsed_ms=elapsed_ms(started),
            source=request.target.address,
        )

    def _fetch(
        self, request: RequestSpec, overrides: dict[str, str]
    ) -> tuple[int, list[dict[str, str]]]:
        answer = self._answer(request, overrides)
        if answer.status >= HTTP_ERROR_STATUS:
            raise RequestFailure(
                error_message(answer.payload, answer.reason, answer.status), answer.status
            )
        try:
            return answer.status, response_records(answer.payload)
        except ValueError as error:
            raise RequestFailure(str(error), answer.status) from None

    def _answer(self, request: RequestSpec, overrides: dict[str, str]) -> HttpAnswer:
        target = request.target
        authorization = self._authorization(lambda: self._tokens.authorization(target))
        answer = self._send(self._prepared(request, overrides, authorization))
        if answer.status != UNAUTHORIZED_STATUS or not is_oauth_target(target):
            return answer
        renewed = self._authorization(
            lambda: self._tokens.renewed_authorization(target, authorization)
        )
        return self._send(self._prepared(request, overrides, renewed))

    def _authorization(self, resolve: Callable[[], str]) -> str:
        try:
            return resolve()
        except (ServiceConfigurationError, OAuthError) as error:
            raise RequestFailure(str(error)) from None

    def _prepared(
        self, request: RequestSpec, overrides: dict[str, str], authorization: str
    ) -> PreparedRequest:
        try:
            return prepare_request(request, overrides, authorization)
        except ServiceConfigurationError as error:
            raise RequestFailure(str(error)) from None

    def _send(self, prepared: PreparedRequest) -> HttpAnswer:
        outgoing = urllib.request.Request(prepared.url, headers=prepared.headers)
        try:
            return send(self._opener, outgoing, REQUEST_TIMEOUT_SECONDS)
        except TransportError as error:
            raise RequestFailure(error.message, error.status_code) from None


def elapsed_ms(started: float) -> int:
    return int((time.monotonic() - started) * 1000)


def mcp_target(repository: ConfigRepository, instance: Instance) -> RequestTarget:
    return RequestTarget(
        instance=instance,
        authentication=repository.active_mcp_authentication(instance.id),
    )
