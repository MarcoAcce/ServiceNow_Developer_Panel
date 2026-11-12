from dataclasses import dataclass

from core.oauth import (
    ACCESS_TOKEN_KEY,
    CLIENT_ID_KEY,
    CLIENT_SECRET_KEY,
    DEFAULT_REDIRECT_URI,
    EXPIRES_AT_KEY,
    REDIRECT_URI_KEY,
    REFRESH_TOKEN_KEY,
    USER_KEY,
)

MASK: str = "********"
DETAIL_SEPARATOR: str = "   "
EMPTY_DETAILS: str = "no detail stored"


@dataclass(frozen=True)
class AuthenticationField:
    key: str
    label: str
    secret: bool = False
    required: bool = True
    placeholder: str = ""
    hidden: bool = False
    listed: bool = True


@dataclass(frozen=True)
class AuthenticationType:
    key: str
    label: str
    description: str
    fields: tuple[AuthenticationField, ...]

    def field_of_key(self, key: str) -> AuthenticationField | None:
        for field in self.fields:
            if field.key == key:
                return field
        return None

    @property
    def editable_fields(self) -> tuple[AuthenticationField, ...]:
        return tuple(field for field in self.fields if not field.hidden)

    @property
    def hidden_fields(self) -> tuple[AuthenticationField, ...]:
        return tuple(field for field in self.fields if field.hidden)


BASIC_AUTHENTICATION: AuthenticationType = AuthenticationType(
    key="basic",
    label="Basic authentication",
    description="User name and password sent on every request.",
    fields=(
        AuthenticationField("username", "User name", placeholder="Instance user name"),
        AuthenticationField("password", "Password", secret=True),
    ),
)
OAUTH_AUTHENTICATION: AuthenticationType = AuthenticationType(
    key="oauth",
    label="OAuth login",
    description=(
        "Authorization code flow: in the application registry of the instance, create an "
        "OAuth API endpoint for external clients with {default} as redirect URL, then copy "
        "its client id and client secret here. Enter the redirect URL below only if you "
        "registered another address on this computer. Login opens the login page in your "
        "browser; the panel receives the answer on the redirect URL and keeps the tokens "
        "it is issued, renewing them on its own."
    ).format(default=DEFAULT_REDIRECT_URI),
    fields=(
        AuthenticationField(
            CLIENT_ID_KEY, "Client id", placeholder="Client ID of the application registry entry"
        ),
        AuthenticationField(CLIENT_SECRET_KEY, "Client secret", secret=True),
        AuthenticationField(
            REDIRECT_URI_KEY,
            "Redirect URL",
            required=False,
            placeholder=DEFAULT_REDIRECT_URI,
        ),
        AuthenticationField(USER_KEY, "User", required=False, hidden=True),
        AuthenticationField(
            ACCESS_TOKEN_KEY, "Access token", secret=True, required=False, hidden=True,
            listed=False,
        ),
        AuthenticationField(
            REFRESH_TOKEN_KEY, "Refresh token", secret=True, required=False, hidden=True,
            listed=False,
        ),
        AuthenticationField(
            EXPIRES_AT_KEY, "Token expiry", required=False, hidden=True, listed=False
        ),
    ),
)

AUTHENTICATION_TYPES: tuple[AuthenticationType, ...] = (
    BASIC_AUTHENTICATION,
    OAUTH_AUTHENTICATION,
)


def authentication_type_of_key(key: str) -> AuthenticationType:
    for authentication_type in AUTHENTICATION_TYPES:
        if authentication_type.key == key:
            return authentication_type
    raise KeyError(key)


def is_oauth(key: str) -> bool:
    return key == OAUTH_AUTHENTICATION.key


def type_label(key: str) -> str:
    try:
        return authentication_type_of_key(key).label
    except KeyError:
        return key


def masked_details(key: str, details: dict[str, str]) -> str:
    try:
        authentication_type = authentication_type_of_key(key)
    except KeyError:
        return EMPTY_DETAILS
    parts: list[str] = []
    for field in authentication_type.fields:
        value = details.get(field.key, "").strip()
        if not value or not field.listed:
            continue
        parts.append(f"{field.label}: {MASK if field.secret else value}")
    return DETAIL_SEPARATOR.join(parts) if parts else EMPTY_DETAILS
