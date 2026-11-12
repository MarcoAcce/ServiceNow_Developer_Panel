import json
import secrets
import time
from dataclasses import dataclass
from urllib.parse import parse_qs, urlencode, urlsplit

AUTHORIZE_PATH: str = "/oauth_auth.do"
TOKEN_PATH: str = "/oauth_token.do"
CURRENT_USER_PATH: str = "/api/now/ui/user/current_user"
DEFAULT_SCHEME: str = "https://"
SCHEME_SEPARATOR: str = "://"
DEFAULT_REDIRECT_URI: str = "http://localhost:8431/oauth/callback"
CLIENT_ID_KEY: str = "client_id"
CLIENT_SECRET_KEY: str = "client_secret"
REDIRECT_URI_KEY: str = "redirect_uri"
ACCESS_TOKEN_KEY: str = "access_token"
REFRESH_TOKEN_KEY: str = "refresh_token"
EXPIRES_AT_KEY: str = "expires_at"
USER_KEY: str = "user"
TOKEN_KEYS: tuple[str, ...] = (ACCESS_TOKEN_KEY, REFRESH_TOKEN_KEY, EXPIRES_AT_KEY, USER_KEY)
EXPIRES_IN_KEY: str = "expires_in"
RESPONSE_TYPE_KEY: str = "response_type"
CODE_RESPONSE_TYPE: str = "code"
GRANT_TYPE_KEY: str = "grant_type"
AUTHORIZATION_CODE_GRANT: str = "authorization_code"
REFRESH_TOKEN_GRANT: str = "refresh_token"
CODE_KEY: str = "code"
STATE_KEY: str = "state"
ERROR_KEY: str = "error"
ERROR_DESCRIPTION_KEY: str = "error_description"
RESULT_KEY: str = "result"
USER_NAME_FIELD: str = "user_name"
DISPLAY_NAME_FIELD: str = "user_display_name"
STATE_BYTES: int = 16
EXPIRY_MARGIN_SECONDS: int = 60
DEFAULT_EXPIRES_IN_SECONDS: int = 1800
MESSAGE_SEPARATOR: str = ": "
USER_LABEL: str = "{display_name} ({user_name})"

LOGIN_REQUIRED_MESSAGE: str = (
    "the OAuth method needs a login: in the ServiceNow Developer Panel, open the method "
    "under Configuration and use Login"
)
LOGIN_CANCELLED_MESSAGE: str = "the login was cancelled"
REFRESH_FAILED_MESSAGE: str = "the access token could not be refreshed ({reason}), log in again"
TOKEN_STATUS_MESSAGE: str = "the instance answered the token request with the status {status}"
INVALID_TOKEN_PAYLOAD_MESSAGE: str = (
    "the instance answered the token request with a body that is not valid json"
)
MISSING_ACCESS_TOKEN_MESSAGE: str = (
    "the instance answered the token request without an access token"
)
ACCESS_DENIED_MESSAGE: str = "the instance refused the login: {reason}"
STATE_MISMATCH_MESSAGE: str = "the answer of the instance does not belong to this login attempt"
NO_CODE_MESSAGE: str = "the address holds no authorization code"


class OAuthError(Exception):
    pass


class TokenRejected(OAuthError):
    pass


class LoginRequired(OAuthError):
    pass


@dataclass(frozen=True)
class TokenSet:
    access_token: str
    refresh_token: str
    expires_at: int


@dataclass(frozen=True)
class CallbackResult:
    code: str = ""
    state: str = ""
    error: str = ""
    description: str = ""

    @property
    def problem(self) -> str:
        if self.error:
            return ACCESS_DENIED_MESSAGE.format(reason=self.description or self.error)
        if not self.code:
            return NO_CODE_MESSAGE
        return ""


def new_state() -> str:
    return secrets.token_urlsafe(STATE_BYTES)


def endpoint_url(address: str, path: str) -> str:
    base = address.strip().rstrip("/")
    if SCHEME_SEPARATOR not in base:
        base = f"{DEFAULT_SCHEME}{base}"
    return f"{base}{path}"


def redirect_uri_of(details: dict[str, str]) -> str:
    return details.get(REDIRECT_URI_KEY, "").strip()


def serving_redirect_uri(details: dict[str, str]) -> str:
    return redirect_uri_of(details) or DEFAULT_REDIRECT_URI


def authorization_url(address: str, details: dict[str, str], state: str) -> str:
    parameters = {
        RESPONSE_TYPE_KEY: CODE_RESPONSE_TYPE,
        CLIENT_ID_KEY: details.get(CLIENT_ID_KEY, "").strip(),
        STATE_KEY: state,
    }
    query = urlencode(_with_redirect(parameters, details))
    return f"{endpoint_url(address, AUTHORIZE_PATH)}?{query}"


def code_request_body(details: dict[str, str], code: str) -> bytes:
    fields = {GRANT_TYPE_KEY: AUTHORIZATION_CODE_GRANT, CODE_KEY: code}
    return _form_body(details, _with_redirect(fields, details))


def refresh_request_body(details: dict[str, str]) -> bytes:
    return _form_body(
        details,
        {
            GRANT_TYPE_KEY: REFRESH_TOKEN_GRANT,
            REFRESH_TOKEN_KEY: details.get(REFRESH_TOKEN_KEY, "").strip(),
        },
    )


def parse_token_payload(payload: bytes, now: int | None = None) -> TokenSet:
    document = _json_object(payload)
    access_token = _text(document.get(ACCESS_TOKEN_KEY))
    if not access_token:
        raise OAuthError(MISSING_ACCESS_TOKEN_MESSAGE)
    try:
        lifetime = int(document.get(EXPIRES_IN_KEY, DEFAULT_EXPIRES_IN_SECONDS))
    except (TypeError, ValueError):
        lifetime = DEFAULT_EXPIRES_IN_SECONDS
    moment = int(time.time()) if now is None else now
    return TokenSet(
        access_token=access_token,
        refresh_token=_text(document.get(REFRESH_TOKEN_KEY)),
        expires_at=moment + lifetime,
    )


def token_error_message(payload: bytes, status: int) -> str:
    message = TOKEN_STATUS_MESSAGE.format(status=status)
    try:
        document = _json_object(payload)
    except OAuthError:
        return message
    reason = _text(document.get(ERROR_DESCRIPTION_KEY)) or _text(document.get(ERROR_KEY))
    return f"{message}{MESSAGE_SEPARATOR}{reason}" if reason else message


def current_user_of(payload: bytes) -> str:
    try:
        document = _json_object(payload)
    except OAuthError:
        return ""
    result = document.get(RESULT_KEY)
    if not isinstance(result, dict):
        return ""
    user_name = _text(result.get(USER_NAME_FIELD))
    display_name = _text(result.get(DISPLAY_NAME_FIELD))
    if user_name and display_name:
        return USER_LABEL.format(display_name=display_name, user_name=user_name)
    return display_name or user_name


def with_tokens(details: dict[str, str], tokens: TokenSet) -> dict[str, str]:
    updated = dict(details)
    updated[ACCESS_TOKEN_KEY] = tokens.access_token
    updated[REFRESH_TOKEN_KEY] = tokens.refresh_token or details.get(REFRESH_TOKEN_KEY, "")
    updated[EXPIRES_AT_KEY] = str(tokens.expires_at)
    return updated


def with_user(details: dict[str, str], user: str) -> dict[str, str]:
    updated = dict(details)
    updated[USER_KEY] = user
    return updated


def access_token_of(details: dict[str, str]) -> str:
    return details.get(ACCESS_TOKEN_KEY, "").strip()


def has_refresh_token(details: dict[str, str]) -> bool:
    return bool(details.get(REFRESH_TOKEN_KEY, "").strip())


def is_expired(details: dict[str, str], now: int | None = None) -> bool:
    if not access_token_of(details):
        return True
    value = details.get(EXPIRES_AT_KEY, "").strip()
    if not value.isdigit():
        return True
    moment = int(time.time()) if now is None else now
    return moment >= int(value) - EXPIRY_MARGIN_SECONDS


def parse_callback(url: str) -> CallbackResult | None:
    query = parse_qs(urlsplit(url.strip()).query, keep_blank_values=True)
    code = _first(query, CODE_KEY)
    error = _first(query, ERROR_KEY)
    if not code and not error:
        return None
    return CallbackResult(
        code=code,
        state=_first(query, STATE_KEY),
        error=error,
        description=_first(query, ERROR_DESCRIPTION_KEY),
    )


def _with_redirect(fields: dict[str, str], details: dict[str, str]) -> dict[str, str]:
    redirect_uri = redirect_uri_of(details)
    if redirect_uri:
        fields[REDIRECT_URI_KEY] = redirect_uri
    return fields


def _form_body(details: dict[str, str], fields: dict[str, str]) -> bytes:
    body = {
        CLIENT_ID_KEY: details.get(CLIENT_ID_KEY, "").strip(),
        CLIENT_SECRET_KEY: details.get(CLIENT_SECRET_KEY, "").strip(),
    }
    body.update(fields)
    return urlencode(body).encode("utf-8")


def _json_object(payload: bytes) -> dict[str, object]:
    try:
        document = json.loads(payload.decode("utf-8"))
    except (UnicodeDecodeError, ValueError) as error:
        raise OAuthError(INVALID_TOKEN_PAYLOAD_MESSAGE) from error
    if not isinstance(document, dict):
        raise OAuthError(INVALID_TOKEN_PAYLOAD_MESSAGE)
    return document


def _text(value: object) -> str:
    return str(value).strip() if value is not None else ""


def _first(query: dict[str, list[str]], key: str) -> str:
    values = query.get(key, [])
    return values[0].strip() if values else ""
