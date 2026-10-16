from dataclasses import dataclass

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
    label="OAuth token",
    description="Tokens issued by an OAuth application registry entry.",
    fields=(
        AuthenticationField("client_id", "Client id"),
        AuthenticationField("client_secret", "Client secret", secret=True),
        AuthenticationField("refresh_token", "Refresh token", secret=True),
        AuthenticationField("access_token", "Access token", secret=True, required=False),
    ),
)
JWT_AUTHENTICATION: AuthenticationType = AuthenticationType(
    key="jwt",
    label="JWT token",
    description="Signed JWT exchanged for an access token by the instance.",
    fields=(
        AuthenticationField(
            "key_id", "Key id", required=False, placeholder="Signing key identifier"
        ),
        AuthenticationField("token", "Token", secret=True),
    ),
)

AUTHENTICATION_TYPES: tuple[AuthenticationType, ...] = (
    BASIC_AUTHENTICATION,
    OAUTH_AUTHENTICATION,
    JWT_AUTHENTICATION,
)


def authentication_type_of_key(key: str) -> AuthenticationType:
    for authentication_type in AUTHENTICATION_TYPES:
        if authentication_type.key == key:
            return authentication_type
    raise KeyError(key)


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
        if not value:
            continue
        parts.append(f"{field.label}: {MASK if field.secret else value}")
    return DETAIL_SEPARATOR.join(parts) if parts else EMPTY_DETAILS
