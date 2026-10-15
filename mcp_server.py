from collections.abc import Callable

from mcp.server import MCPServer
from mcp.types import ToolAnnotations

from database_manager import DatabaseManager
from mcp_session import McpSession

SERVER_NAME: str = "servicenow-developer-panel"
SERVER_INSTRUCTIONS: str = (
    "Read-only access to the ServiceNow instances configured in the ServiceNow Developer Panel. "
    "Start with list_instances to learn the instance names. Requests are GET calls on the Table "
    "API, authenticated with credentials that stay inside this server. Every request returns a "
    "cache_name: use query_cache to filter, join or aggregate the full result with SQLite, and "
    "export_cache to save it as csv or xlsx. Identical requests are served from the local cache "
    "until it expires; pass refresh to fetch fresh data."
)
LIST_INSTANCES_DESCRIPTION: str = (
    "List the configured ServiceNow instances and whether each has a usable MCP authentication "
    "method. The other tools take the instance name returned here."
)
REQUEST_TABLE_DESCRIPTION: str = (
    "Fetch records from one ServiceNow table. Returns a sample of the records and a cache_name; "
    "the full result is cached locally for query_cache and export_cache."
)
REQUEST_TABLES_DESCRIPTION: str = (
    "Fetch several tables in one request, each with its own query. All of them are stored in one "
    "cached response, so query_cache can join them. Returns the row count and columns of each "
    "table and the cache_name."
)
QUERY_CACHE_DESCRIPTION: str = (
    "Run read-only SQLite against a cached response. Each ServiceNow table is a SQLite table "
    "with TEXT columns. Returns at most 2000 rows."
)
EXPORT_CACHE_DESCRIPTION: str = (
    "Write a cached response to disk, as csv with one file per table or as an xlsx workbook "
    "with one sheet per table. Returns the absolute paths written."
)
VERIFY_ACL_DESCRIPTION: str = (
    "Check whether users holding the given sets of roles can run an operation on a table, or on "
    "one of its fields, according to the ACLs of the instance. Each profile gets a decision "
    "(allowed, conditional, denied or missing), a summary, the reasons and the controls "
    "involved. Parent table inheritance is not evaluated: missing means no ACL matched."
)
LIST_CACHED_RESPONSES_DESCRIPTION: str = (
    "List the responses in the local cache, most recent first, with the tables and row counts "
    "each holds. current is false once a response is older than the cache lifetime: it can "
    "still be queried and exported, but request tools will fetch fresh data."
)

LOCAL_READ: ToolAnnotations = ToolAnnotations(readOnlyHint=True, openWorldHint=False)
REMOTE_READ: ToolAnnotations = ToolAnnotations(
    readOnlyHint=True, idempotentHint=True, openWorldHint=True
)
LOCAL_WRITE: ToolAnnotations = ToolAnnotations(
    readOnlyHint=False, destructiveHint=False, idempotentHint=True, openWorldHint=False
)


def build_server(session: McpSession) -> MCPServer:
    server = MCPServer(SERVER_NAME, instructions=SERVER_INSTRUCTIONS)
    tools: tuple[tuple[Callable[..., object], str, ToolAnnotations], ...] = (
        (session.list_instances, LIST_INSTANCES_DESCRIPTION, LOCAL_READ),
        (session.request_table, REQUEST_TABLE_DESCRIPTION, REMOTE_READ),
        (session.request_tables, REQUEST_TABLES_DESCRIPTION, REMOTE_READ),
        (session.query_cache, QUERY_CACHE_DESCRIPTION, LOCAL_READ),
        (session.export_cache, EXPORT_CACHE_DESCRIPTION, LOCAL_WRITE),
        (session.verify_acl, VERIFY_ACL_DESCRIPTION, REMOTE_READ),
        (session.list_cached_responses, LIST_CACHED_RESPONSES_DESCRIPTION, LOCAL_READ),
    )
    for function, description, annotations in tools:
        server.tool(description=description, annotations=annotations)(function)
    return server


def main() -> None:
    database = DatabaseManager.instance()
    try:
        build_server(McpSession(database)).run()
    finally:
        database.close()


if __name__ == "__main__":
    main()
