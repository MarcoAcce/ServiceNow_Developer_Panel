import urllib.error
import urllib.request
from dataclasses import dataclass
from email.message import Message
from typing import IO
from urllib.parse import urlsplit

from services.http_payload import HTTP_ERROR_STATUS, REQUEST_TIMEOUT_MS

REQUEST_TIMEOUT_SECONDS: float = REQUEST_TIMEOUT_MS / 1000
TIMEOUT_MESSAGE: str = "the instance did not answer within {seconds:.0f} seconds"
CONNECTION_MESSAGE: str = "the instance could not be reached: {reason}"
REDIRECT_MESSAGE: str = "the instance redirected the request to another address"


@dataclass(frozen=True)
class HttpAnswer:
    status: int
    payload: bytes
    reason: str = ""


class TransportError(Exception):

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


class NoRedirectHandler(urllib.request.HTTPRedirectHandler):

    def redirect_request(
        self,
        req: urllib.request.Request,
        fp: IO[bytes],
        code: int,
        msg: str,
        headers: Message,
        newurl: str,
    ) -> urllib.request.Request | None:
        return None


def origin_of(url: str) -> tuple[str, str]:
    parts = urlsplit(url)
    return parts.scheme.lower(), parts.netloc.lower()


def build_opener(follow_same_origin: bool = True) -> urllib.request.OpenerDirector:
    handler = SameOriginRedirectHandler if follow_same_origin else NoRedirectHandler
    return urllib.request.build_opener(handler)


def send(
    opener: urllib.request.OpenerDirector,
    request: urllib.request.Request,
    timeout: float = REQUEST_TIMEOUT_SECONDS,
) -> HttpAnswer:
    try:
        with opener.open(request, timeout=timeout) as response:
            return HttpAnswer(int(response.status), response.read(), str(response.reason or ""))
    except urllib.error.HTTPError as error:
        if error.code < HTTP_ERROR_STATUS:
            raise TransportError(REDIRECT_MESSAGE, error.code) from None
        return HttpAnswer(error.code, _read_payload(error), str(error.reason or ""))
    except TimeoutError:
        raise TransportError(TIMEOUT_MESSAGE.format(seconds=timeout)) from None
    except urllib.error.URLError as error:
        raise TransportError(CONNECTION_MESSAGE.format(reason=error.reason)) from None
    except OSError as error:
        raise TransportError(CONNECTION_MESSAGE.format(reason=error.strerror or error)) from None


def _read_payload(error: urllib.error.HTTPError) -> bytes:
    try:
        return error.read()
    except OSError:
        return b""
