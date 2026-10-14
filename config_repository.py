import sqlite3
from dataclasses import dataclass, field

from authentication_types import AuthenticationType, authentication_type_of_key
from database_manager import (
    CURRENT_INSTANCE_SETTING,
    DEFAULT_THEME_KEY,
    THEME_SETTING,
    DatabaseManager,
)
from secret_store import SecretError, decode_details, encode_details

INSTANCE_QUERY: str = "SELECT id, name, address FROM instance ORDER BY name COLLATE NOCASE"
AUTHENTICATION_QUERY: str = (
    "SELECT id, instance_id, authentication_type, authentication_details, active "
    "FROM authentication WHERE instance_id = ? ORDER BY id"
)
ACTIVE_AUTHENTICATION_QUERY: str = (
    "SELECT id, instance_id, authentication_type, authentication_details, active "
    "FROM authentication WHERE instance_id = ? AND active = 1"
)
CONFIGURATION_QUERY: str = "SELECT value FROM local_configuration WHERE name = ?"
CONFIGURATION_UPSERT: str = (
    "INSERT INTO local_configuration (name, value) VALUES (?, ?) "
    "ON CONFLICT (name) DO UPDATE SET value = excluded.value"
)


@dataclass(frozen=True)
class Instance:
    id: int
    name: str
    address: str


@dataclass(frozen=True)
class Authentication:
    id: int
    instance_id: int
    authentication_type: str
    active: bool
    details: dict[str, str] = field(default_factory=dict)
    readable: bool = True

    def type_definition(self) -> AuthenticationType | None:
        try:
            return authentication_type_of_key(self.authentication_type)
        except KeyError:
            return None


class ConfigRepository:

    def __init__(self, database: DatabaseManager) -> None:
        self._database: DatabaseManager = database

    def list_instances(self) -> list[Instance]:
        rows = self._database.query(INSTANCE_QUERY)
        return [Instance(id=row["id"], name=row["name"], address=row["address"]) for row in rows]

    def list_authentications(self, instance_id: int) -> list[Authentication]:
        rows = self._database.query(AUTHENTICATION_QUERY, (instance_id,))
        return [self._build_authentication(row) for row in rows]

    def active_authentication(self, instance_id: int) -> Authentication | None:
        row = self._database.query_one(ACTIVE_AUTHENTICATION_QUERY, (instance_id,))
        return self._build_authentication(row) if row is not None else None

    def configuration_value(self, name: str, default: str = "") -> str:
        row = self._database.query_one(CONFIGURATION_QUERY, (name,))
        return str(row["value"]) if row is not None else default

    def set_configuration_value(self, name: str, value: str) -> None:
        def operation(connection: sqlite3.Connection) -> None:
            connection.execute(CONFIGURATION_UPSERT, (name, value))

        self._database.write_and_wait(operation)

    def theme_key(self) -> str:
        return self.configuration_value(THEME_SETTING, DEFAULT_THEME_KEY)

    def set_theme_key(self, key: str) -> None:
        self.set_configuration_value(THEME_SETTING, key)

    def current_instance_id(self) -> int:
        value = self.configuration_value(CURRENT_INSTANCE_SETTING, "")
        return int(value) if value.isdigit() else 0

    def set_current_instance_id(self, instance_id: int) -> None:
        self.set_configuration_value(CURRENT_INSTANCE_SETTING, str(instance_id))

    def create_instance(self, name: str, address: str) -> int:
        def operation(connection: sqlite3.Connection) -> int:
            cursor = connection.execute(
                "INSERT INTO instance (name, address) VALUES (?, ?)", (name, address)
            )
            return int(cursor.lastrowid or 0)

        return int(self._database.write_and_wait(operation))

    def delete_instance(self, instance_id: int) -> None:
        def operation(connection: sqlite3.Connection) -> None:
            connection.execute("DELETE FROM instance WHERE id = ?", (instance_id,))

        self._database.write_and_wait(operation)

    def create_authentication(
        self,
        instance_id: int,
        authentication_type: str,
        details: dict[str, str],
        active: bool = False,
    ) -> int:
        payload = encode_details(details)

        def operation(connection: sqlite3.Connection) -> int:
            if active:
                _deactivate(connection, instance_id)
            cursor = connection.execute(
                "INSERT INTO authentication "
                "(instance_id, authentication_type, authentication_details, active) "
                "VALUES (?, ?, ?, ?)",
                (instance_id, authentication_type, payload, int(active)),
            )
            return int(cursor.lastrowid or 0)

        return int(self._database.write_and_wait(operation))

    def update_authentication(
        self, authentication_id: int, authentication_type: str, details: dict[str, str]
    ) -> None:
        payload = encode_details(details)

        def operation(connection: sqlite3.Connection) -> None:
            connection.execute(
                "UPDATE authentication "
                "SET authentication_type = ?, authentication_details = ? WHERE id = ?",
                (authentication_type, payload, authentication_id),
            )

        self._database.write_and_wait(operation)

    def delete_authentication(self, authentication_id: int) -> None:
        def operation(connection: sqlite3.Connection) -> None:
            connection.execute("DELETE FROM authentication WHERE id = ?", (authentication_id,))

        self._database.write_and_wait(operation)

    def set_active_authentication(
        self, instance_id: int, authentication_id: int, active: bool
    ) -> None:
        def operation(connection: sqlite3.Connection) -> None:
            _deactivate(connection, instance_id)
            if active:
                connection.execute(
                    "UPDATE authentication SET active = 1 WHERE id = ? AND instance_id = ?",
                    (authentication_id, instance_id),
                )

        self._database.write_and_wait(operation)

    def _build_authentication(self, row: sqlite3.Row) -> Authentication:
        try:
            details = decode_details(row["authentication_details"])
            readable = True
        except SecretError:
            details = {}
            readable = False
        return Authentication(
            id=row["id"],
            instance_id=row["instance_id"],
            authentication_type=row["authentication_type"],
            active=bool(row["active"]),
            details=details,
            readable=readable,
        )


def _deactivate(connection: sqlite3.Connection, instance_id: int) -> None:
    connection.execute(
        "UPDATE authentication SET active = 0 WHERE instance_id = ? AND active = 1", (instance_id,)
    )
