import sqlite3
import time
import urllib.error
import urllib.request
from email.message import Message
from typing import IO
from urllib.parse import urlsplit

from configuration.config_repository import ConfigRepository, Instance
from core.database_manager import DatabaseError
from services.http_payload import (
    HTTP_ERROR_STATUS,
    REQUEST_TIMEOUT_MS,
    error_message,
    has_more,
    is_paged,
    page_overrides,
    page_size,
    parameter_value,
    response_records,
)
from core.request_model import (
    COMPOSITE_STATUS_CODE,
    LIMIT_PARAMETER,
    OFFSET_PARAMETER,
    PART_ERROR_MESSAGE,
    RequestResult,
    RequestSpec,
    RequestTarget,
    ResultSection,
    ServiceConfigurationError,
    composite_result,
    prepare_request,
    section_of,
)
from storage.response_repository import ResponseRepository, cached_result

REQUEST_TIMEOUT_SECONDS: float = REQUEST_TIMEOUT_MS / 1000
TIMEOUT_MESSAGE: str = "the instance did not answer within {seconds:.0f} seconds"
CONNECTION_MESSAGE: str = "the instance could not be reached: {reason}"
REDIRECT_MESSAGE: str = "the instance redirected the request to another address"


class RequestFailure(Exception):

    def __init__(self, message: str, status_code: int = 0) -> None:
        super().__init__(message)
        self.message: str = message
        self.status_code: int = status_code


class SameOriginRedirectHandler(urllib.request.HTTPRedirectHandler):

    def redirect_request(
        self,
        req: urllib.request.Request,
        fp: IO[bytes],
        code: int,
        msg: str,
        headers: Message,
        newurl: str,
    ) -> urllib.request.Request | None:
        if origin_of(req.full_url) != origin_of(newurl):
            return None
        return super().redirect_request(req, fp, code, msg, headers, newurl)


class SyncRequestService:

    def __init__(self, responses: ResponseRepository) -> None:
        self._responses: ResponseRepository = responses
        self._opener: urllib.request.OpenerDirector = urllib.request.build_opener(
            SameOriginRedirectHandler
        )

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
        try:
            prepared = prepare_request(request, overrides)
        except ServiceConfigurationError as error:
            raise RequestFailure(str(error)) from None
        outgoing = urllib.request.Request(prepared.url, headers=prepared.headers)
        try:
            with self._opener.open(outgoing, timeout=REQUEST_TIMEOUT_SECONDS) as response:
                status = int(response.status)
                payload = response.read()
        except urllib.error.HTTPError as error:
            raise failure_of(error) from None
        except TimeoutError:
            raise RequestFailure(TIMEOUT_MESSAGE.format(seconds=REQUEST_TIMEOUT_SECONDS)) from None
        except urllib.error.URLError as error:
            raise RequestFailure(CONNECTION_MESSAGE.format(reason=error.reason)) from None
        except OSError as error:
            raise RequestFailure(CONNECTION_MESSAGE.format(reason=error.strerror)) from None
        if status >= HTTP_ERROR_STATUS:
            raise RequestFailure(error_message(payload, "", status), status)
        try:
            return status, response_records(payload)
        except ValueError as error:
            raise RequestFailure(str(error), status) from None


def failure_of(error: urllib.error.HTTPError) -> RequestFailure:
    if error.code < HTTP_ERROR_STATUS:
        return RequestFailure(REDIRECT_MESSAGE, error.code)
    try:
        payload = error.read()
    except OSError:
        payload = b""
    return RequestFailure(error_message(payload, str(error.reason), error.code), error.code)


def origin_of(url: str) -> tuple[str, str]:
    parts = urlsplit(url)
    return parts.scheme.lower(), parts.netloc.lower()


def elapsed_ms(started: float) -> int:
    return int((time.monotonic() - started) * 1000)


def mcp_target(repository: ConfigRepository, instance: Instance) -> RequestTarget:
    return RequestTarget(
        instance=instance,
        authentication=repository.active_mcp_authentication(instance.id),
    )
