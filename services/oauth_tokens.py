import sqlite3
import threading
import urllib.request
from collections.abc import Callable
from dataclasses import dataclass, replace

from configuration.authentication_types import is_oauth
from configuration.config_repository import Authentication, ConfigRepository
from core.database_manager import DatabaseError
from core.oauth import (
    CURRENT_USER_PATH,
    LOGIN_CANCELLED_MESSAGE,
    LOGIN_REQUIRED_MESSAGE,
    REFRESH_FAILED_MESSAGE,
    TOKEN_PATH,
    USER_KEY,
    LoginRequired,
    OAuthError,
    TokenRejected,
    TokenSet,
    access_token_of,
    code_request_body,
    current_user_of,
    endpoint_url,
    has_refresh_token,
    is_expired,
    parse_token_payload,
    refresh_request_body,
    token_error_message,
    with_tokens,
    with_user,
)
from core.request_model import (
    AUTHORIZATION_HEADER,
    BEARER_PREFIX,
    DEFAULT_HEADERS,
    MISSING_AUTHENTICATION_MESSAGE,
    MISSING_INSTANCE_MESSAGE,
    UNREADABLE_AUTHENTICATION_MESSAGE,
    RequestTarget,
    ServiceConfigurationError,
    authentication_header,
)
from core.secret_store import SecretError
from services.http_payload import HTTP_ERROR_STATUS
from services.sync_http import (
    REQUEST_TIMEOUT_SECONDS,
    HttpAnswer,
    TransportError,
    build_opener,
    send,
)

UNAUTHORIZED_STATUS: int = 401
SERVER_ERROR_STATUS: int = 500
POST_METHOD: str = "POST"
CONTENT_TYPE_HEADER: str = "Content-Type"
FORM_CONTENT_TYPE: str = "application/x-www-form-urlencoded"
NO_TOKENS_MESSAGE: str = "no token is stored yet"
REJECTED_TOKEN_MESSAGE: str = "the instance rejected the access token it just issued"
STALE_TOKEN_MESSAGE: str = "the instance rejected the stored access token"

LoginHandler = Callable[[RequestTarget, str], Authentication | None]


@dataclass(frozen=True)
class ProbeResult:
    accepted: bool
    status: int
    user: str = ""


@dataclass(frozen=True)
class LoginState:
    details: dict[str, str]
    logged_in: bool = False
    login_required: bool = False
    message: str = ""
    user: str = ""


@dataclass(frozen=True)
class TokenStore:
    load: Callable[[int], Authentication | None]
    save: Callable[[int, dict[str, str]], None]


def user_token_store(repository: ConfigRepository) -> TokenStore:
    return TokenStore(
        load=repository.authentication, save=repository.update_authentication_details
    )


def mcp_token_store(repository: ConfigRepository) -> TokenStore:
    return TokenStore(
        load=repository.mcp_authentication, save=repository.update_mcp_authentication_details
    )


def is_oauth_target(target: RequestTarget) -> bool:
    authentication = target.authentication
    return authentication is not None and is_oauth(authentication.authentication_type)


class OAuthTokenClient:

    def __init__(self, timeout: float = REQUEST_TIMEOUT_SECONDS) -> None:
        self._timeout: float = timeout
        self._opener: urllib.request.OpenerDirector = build_opener(follow_same_origin=False)

    def exchange_code(self, address: str, details: dict[str, str], code: str) -> TokenSet:
        return self._tokens(address, code_request_body(details, code))

    def refresh(self, address: str, details: dict[str, str]) -> TokenSet:
        try:
            return self._tokens(address, refresh_request_body(details))
        except TokenRejected as error:
            raise LoginRequired(REFRESH_FAILED_MESSAGE.format(reason=error)) from None

    def probe(self, address: str, access_token: str) -> ProbeResult:
        headers = dict(DEFAULT_HEADERS)
        headers[AUTHORIZATION_HEADER] = BEARER_PREFIX + access_token
        request = urllib.request.Request(
            endpoint_url(address, CURRENT_USER_PATH), headers=headers
        )
        answer = self._send(request)
        if answer.status == UNAUTHORIZED_STATUS:
            return ProbeResult(accepted=False, status=answer.status)
        user = "" if answer.status >= HTTP_ERROR_STATUS else current_user_of(answer.payload)
        return ProbeResult(accepted=True, status=answer.status, user=user)

    def _tokens(self, address: str, body: bytes) -> TokenSet:
        headers = dict(DEFAULT_HEADERS)
        headers[CONTENT_TYPE_HEADER] = FORM_CONTENT_TYPE
        request = urllib.request.Request(
            endpoint_url(address, TOKEN_PATH), data=body, headers=headers, method=POST_METHOD
        )
        answer = self._send(request)
        if answer.status >= SERVER_ERROR_STATUS:
            raise OAuthError(token_error_message(answer.payload, answer.status))
        if answer.status >= HTTP_ERROR_STATUS:
            raise TokenRejected(token_error_message(answer.payload, answer.status))
        return parse_token_payload(answer.payload)

    def _send(self, request: urllib.request.Request) -> HttpAnswer:
        try:
            return send(self._opener, request, self._timeout)
        except TransportError as error:
            raise OAuthError(error.message) from None


def verify_login(client: OAuthTokenClient, address: str, details: dict[str, str]) -> LoginState:
    try:
        token = access_token_of(details)
        if token and not is_expired(details):
            probe = client.probe(address, token)
            if probe.accepted:
                return _logged_in(details, probe)
        if not has_refresh_token(details):
            message = NO_TOKENS_MESSAGE if not token else STALE_TOKEN_MESSAGE
            return LoginState(details, login_required=True, message=message)
        refreshed = with_tokens(details, client.refresh(address, details))
        probe = client.probe(address, access_token_of(refreshed))
        if probe.accepted:
            return _logged_in(refreshed, probe)
        return LoginState(details, login_required=True, message=REJECTED_TOKEN_MESSAGE)
    except LoginRequired as error:
        return LoginState(details, login_required=True, message=str(error))
    except OAuthError as error:
        return LoginState(details, message=str(error))


def complete_login(
    client: OAuthTokenClient, address: str, details: dict[str, str], code: str
) -> LoginState:
    try:
        tokens = client.exchange_code(address, details, code)
        updated = with_tokens(with_user(details, ""), tokens)
        probe = client.probe(address, tokens.access_token)
    except OAuthError as error:
        return LoginState(details, message=str(error))
    if not probe.accepted:
        return LoginState(details, message=REJECTED_TOKEN_MESSAGE)
    return _logged_in(updated, probe)


def _logged_in(details: dict[str, str], probe: ProbeResult) -> LoginState:
    user = probe.user or details.get(USER_KEY, "").strip()
    return LoginState(with_user(details, user), logged_in=True, user=user)


class TokenManager:

    def __init__(
        self,
        store: TokenStore,
        client: OAuthTokenClient | None = None,
        login: LoginHandler | None = None,
    ) -> None:
        self._store: TokenStore = store
        self._client: OAuthTokenClient = client or OAuthTokenClient()
        self._login: LoginHandler | None = login
        self._lock: threading.Lock = threading.Lock()

    def authorization(self, target: RequestTarget) -> str:
        return authentication_header(self.resolve(target))

    def renewed_authorization(self, target: RequestTarget, rejected: str) -> str:
        token = rejected.removeprefix(BEARER_PREFIX)
        return authentication_header(self.resolve(target, rejected_token=token))

    def resolve(self, target: RequestTarget, rejected_token: str = "") -> Authentication:
        instance = target.instance
        authentication = target.authentication
        if instance is None:
            raise ServiceConfigurationError(MISSING_INSTANCE_MESSAGE)
        if authentication is None:
            raise ServiceConfigurationError(MISSING_AUTHENTICATION_MESSAGE)
        if not is_oauth(authentication.authentication_type):
            return authentication
        with self._lock:
            current = self._stored(authentication)
            if not current.readable:
                raise ServiceConfigurationError(UNREADABLE_AUTHENTICATION_MESSAGE)
            token = access_token_of(current.details)
            if token and token != rejected_token and not is_expired(current.details):
                return current
            if not has_refresh_token(current.details):
                return self._log_in(target, current, LOGIN_REQUIRED_MESSAGE)
            try:
                tokens = self._client.refresh(instance.address, current.details)
            except LoginRequired as error:
                return self._log_in(target, current, str(error))
            details = with_tokens(current.details, tokens)
            self._save(current.id, details)
            return replace(current, details=details)

    def _log_in(
        self, target: RequestTarget, current: Authentication, reason: str
    ) -> Authentication:
        if self._login is None:
            raise LoginRequired(reason)
        renewed = self._login(replace(target, authentication=current), reason)
        if renewed is None:
            raise LoginRequired(LOGIN_CANCELLED_MESSAGE)
        self._save(renewed.id, renewed.details)
        return renewed

    def _stored(self, authentication: Authentication) -> Authentication:
        try:
            stored = self._store.load(authentication.id)
        except (sqlite3.Error, DatabaseError):
            stored = None
        return stored if stored is not None else authentication

    def _save(self, authentication_id: int, details: dict[str, str]) -> None:
        try:
            self._store.save(authentication_id, details)
        except (sqlite3.Error, DatabaseError, SecretError, TimeoutError):
            return
