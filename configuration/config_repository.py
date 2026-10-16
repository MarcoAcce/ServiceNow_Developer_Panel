import sqlite3
from dataclasses import dataclass, field

from configuration.authentication_types import AuthenticationType, authentication_type_of_key
from core.database_manager import (
    CACHE_LIFETIME_SETTING,
    CURRENT_INSTANCE_SETTING,
    DEFAULT_THEME_KEY,
    SUGGESTION_COUNT_SETTING,
    THEME_SETTING,
    DatabaseManager,
)
from core.secret_store import SecretError, decode_details, encode_details

INSTANCE_QUERY: str = "SELECT id, name, address FROM instance ORDER BY name COLLATE NOCASE"
AUTHENTICATION_TABLE: str = "authentication"
MCP_AUTHENTICATION_TABLE: str = "mcp_authentication"
AUTHENTICATION_QUERY: str = (
    "SELECT id, instance_id, authentication_type, authentication_details, active "
    "FROM {table} WHERE instance_id = ? ORDER BY id"
)
ACTIVE_AUTHENTICATION_QUERY: str = (
    "SELECT id, instance_id, authentication_type, authentication_details, active "
    "FROM {table} WHERE instance_id = ? AND active = 1"
)
AUTHENTICATION_INSERT: str = (
    "INSERT INTO {table} "
    "(instance_id, authentication_type, authentication_details, active) "
    "VALUES (?, ?, ?, ?)"
)
AUTHENTICATION_UPDATE: str = (
    "UPDATE {table} SET authentication_type = ?, authentication_details = ? WHERE id = ?"
)
AUTHENTICATION_DELETE: str = "DELETE FROM {table} WHERE id = ?"
AUTHENTICATION_ACTIVATE: str = (
    "UPDATE {table} SET active = 1 WHERE id = ? AND instance_id = ?"
)
AUTHENTICATION_DEACTIVATE: str = (
    "UPDATE {table} SET active = 0 WHERE instance_id = ? AND active = 1"
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
        return self._list_authentications(AUTHENTICATION_TABLE, instance_id)

    def active_authentication(self, instance_id: int) -> Authentication | None:
        return self._active_authentication(AUTHENTICATION_TABLE, instance_id)

    def list_mcp_authentications(self, instance_id: int) -> list[Authentication]:
        return self._list_authentications(MCP_AUTHENTICATION_TABLE, instance_id)

    def active_mcp_authentication(self, instance_id: int) -> Authentication | None:
        return self._active_authentication(MCP_AUTHENTICATION_TABLE, instance_id)

    def _list_authentications(self, table: str, instance_id: int) -> list[Authentication]:
        rows = self._database.query(AUTHENTICATION_QUERY.format(table=table), (instance_id,))
        return [self._build_authentication(row) for row in rows]

    def _active_authentication(self, table: str, instance_id: int) -> Authentication | None:
        row = self._database.query_one(
            ACTIVE_AUTHENTICATION_QUERY.format(table=table), (instance_id,)
        )
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

    def cache_lifetime_minutes(self) -> int:
        return self._database.cache_lifetime_minutes()

    def set_cache_lifetime_minutes(self, minutes: int) -> None:
        self.set_configuration_value(CACHE_LIFETIME_SETTING, str(minutes))

    def suggestion_count(self) -> int:
        return self._database.suggestion_count()

    def set_suggestion_count(self, count: int) -> None:
        self.set_configuration_value(SUGGESTION_COUNT_SETTING, str(count))

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
        return self._create_authentication(
            AUTHENTICATION_TABLE, instance_id, authentication_type, details, active
        )

    def update_authentication(
        self, authentication_id: int, authentication_type: str, details: dict[str, str]
    ) -> None:
        self._update_authentication(
            AUTHENTICATION_TABLE, authentication_id, authentication_type, details
        )

    def delete_authentication(self, authentication_id: int) -> None:
        self._delete_authentication(AUTHENTICATION_TABLE, authentication_id)

    def set_active_authentication(
        self, instance_id: int, authentication_id: int, active: bool
    ) -> None:
        self._set_active_authentication(
            AUTHENTICATION_TABLE, instance_id, authentication_id, active
        )

    def create_mcp_authentication(
        self,
        instance_id: int,
        authentication_type: str,
        details: dict[str, str],
        active: bool = False,
    ) -> int:
        return self._create_authentication(
            MCP_AUTHENTICATION_TABLE, instance_id, authentication_type, details, active
        )

    def update_mcp_authentication(
        self, authentication_id: int, authentication_type: str, details: dict[str, str]
    ) -> None:
        self._update_authentication(
            MCP_AUTHENTICATION_TABLE, authentication_id, authentication_type, details
        )

    def delete_mcp_authentication(self, authentication_id: int) -> None:
        self._delete_authentication(MCP_AUTHENTICATION_TABLE, authentication_id)

    def set_active_mcp_authentication(
        self, instance_id: int, authentication_id: int, active: bool
    ) -> None:
        self._set_active_authentication(
            MCP_AUTHENTICATION_TABLE, instance_id, authentication_id, active
        )

    def _create_authentication(
        self,
        table: str,
        instance_id: int,
        authentication_type: str,
        details: dict[str, str],
        active: bool,
    ) -> int:
        payload = encode_details(details)

        def operation(connection: sqlite3.Connection) -> int:
            if active:
                _deactivate(connection, table, instance_id)
            cursor = connection.execute(
                AUTHENTICATION_INSERT.format(table=table),
                (instance_id, authentication_type, payload, int(active)),
            )
            return int(cursor.lastrowid or 0)

        return int(self._database.write_and_wait(operation))

    def _update_authentication(
        self,
        table: str,
        authentication_id: int,
        authentication_type: str,
        details: dict[str, str],
    ) -> None:
        payload = encode_details(details)

        def operation(connection: sqlite3.Connection) -> None:
            connection.execute(
                AUTHENTICATION_UPDATE.format(table=table),
                (authentication_type, payload, authentication_id),
            )

        self._database.write_and_wait(operation)

    def _delete_authentication(self, table: str, authentication_id: int) -> None:
        def operation(connection: sqlite3.Connection) -> None:
            connection.execute(
                AUTHENTICATION_DELETE.format(table=table), (authentication_id,)
            )

        self._database.write_and_wait(operation)

    def _set_active_authentication(
        self, table: str, instance_id: int, authentication_id: int, active: bool
    ) -> None:
        def operation(connection: sqlite3.Connection) -> None:
            _deactivate(connection, table, instance_id)
            if active:
                connection.execute(
                    AUTHENTICATION_ACTIVATE.format(table=table),
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


def _deactivate(connection: sqlite3.Connection, table: str, instance_id: int) -> None:
    connection.execute(AUTHENTICATION_DEACTIVATE.format(table=table), (instance_id,))
