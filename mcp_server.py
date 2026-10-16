from collections.abc import Callable

from mcp.server import MCPServer
from mcp.types import ToolAnnotations

from core.database_manager import DatabaseManager
from services.mcp_session import McpSession

SERVER_NAME: str = "servicenow-developer-panel"
SERVER_INSTRUCTIONS: str = (
    "Read-only access to the ServiceNow instances configured in the ServiceNow Developer Panel. "
    "Start with list_instances to learn the instance names, and use describe_table to learn the "
    "fields of a table before querying it. Requests are GET calls on the Table API, "
    "authenticated with credentials that stay inside this server. Every request returns a "
    "cache_name: use query_cache to filter, join or aggregate the full result with SQLite, and "
    "export_cache to save it as csv or xlsx. query_cache reads one cache_name at a time, so "
    "fetch the tables you want to join together with request_tables, and use add_tables to add "
    "more tables to that same cached response later. Identical requests are served from the "
    "local cache until it expires; pass refresh to fetch fresh data. Read the warnings of every "
    "response: they report results cut by the limit and fields the table does not have. "
    "Business rules are in sys_script, with the table in collection; client scripts, UI "
    "actions and UI policies are in sys_script_client, sys_ui_action and sys_ui_policy, with "
    "the table in table. Roles are granted to users in sys_user_has_role and to groups in "
    "sys_group_has_role, group members are in sys_user_grmember and roles contained in other "
    "roles in sys_user_role_contains: the roles field of sys_user and sys_user_group is not "
    "reliable."
)
LIST_INSTANCES_DESCRIPTION: str = (
    "List the configured ServiceNow instances and whether each has a usable MCP authentication "
    "method. The other tools take the instance name returned here."
)
REQUEST_TABLE_DESCRIPTION: str = (
    "Fetch records from one ServiceNow table. Returns a sample of the records, any warnings and "
    "a cache_name; the full result is cached locally for query_cache and export_cache. To join "
    "several tables, fetch them with request_tables instead."
)
REQUEST_TABLES_DESCRIPTION: str = (
    "Fetch several tables in one request, each with its own query, fields and limit. All of "
    "them are stored in one cached response, so query_cache can join them. Returns the row "
    "count and columns of each table, any warnings and the cache_name. Example arguments: "
    '{"instance": "dev", "tables": [{"table": "sys_user_group", "fields": ["sys_id", "name"], '
    '"limit": 1000}, {"table": "sys_group_has_role", "query": "role.name=itil", '
    '"fields": ["group", "role", "group.name"], "limit": 5000}]}'
)
DESCRIBE_TABLE_DESCRIPTION: str = (
    "List the fields of a table from the instance dictionary, including the fields it inherits "
    "from the tables it extends, for example task for incident. Each field has its name, label "
    "and type, the table that defines it, the table it points to for reference and list "
    "fields, and whether it is mandatory or read only. The dictionary overrides of the table "
    "and of its parents are applied and listed under overrides. default_value, dependent and "
    "choices appear only when the field has them; choices are the active values and labels to "
    "use in queries, with the dependent_value of the dependent field when they depend on one. "
    "Use it before querying a table whose fields you do not know for sure, custom application "
    "tables included. Inactive fields are left out. The returned cache_name holds the tables "
    "sys_db_object, sys_dictionary, sys_dictionary_override and sys_choice, where name is the "
    "table and element the field."
)
ADD_TABLES_DESCRIPTION: str = (
    "Add tables to a response cached by request_tables, so query_cache can join them with the "
    "tables it already holds. Only the new tables are fetched. If the cached response has "
    "expired, every table is requested again into a new cached response and the returned "
    "cache_name changes. Returns the same summary as request_tables, for every table of the "
    "response."
)
QUERY_CACHE_DESCRIPTION: str = (
    "Run read-only SQLite against a cached response. Each ServiceNow table is a SQLite table "
    "with TEXT columns. Returns at most 2000 rows; truncated is true when more matched."
)
EXPORT_CACHE_DESCRIPTION: str = (
    "Write a cached response to disk, as csv with one file per table or as an xlsx workbook "
    "with one sheet per table. Returns the absolute paths written."
)
VERIFY_ACL_DESCRIPTION: str = (
    "Check whether users holding the given sets of roles can run an operation on a table, or on "
    "one of its fields, according to the ACLs of the instance. Each profile gets a decision "
    "(allowed, conditional, denied or missing), a summary, the reasons and the controls "
    "involved. Scripts and conditions are not run: conditional means the scripts and "
    "conditions listed in the controls decide. The controls also show which roles each ACL "
    "requires. Parent table inheritance is not evaluated: missing means no ACL matched."
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
REMOTE_APPEND: ToolAnnotations = ToolAnnotations(readOnlyHint=True, openWorldHint=True)
LOCAL_WRITE: ToolAnnotations = ToolAnnotations(
    readOnlyHint=False, destructiveHint=False, idempotentHint=True, openWorldHint=False
)


def build_server(session: McpSession) -> MCPServer:
    server = MCPServer(SERVER_NAME, instructions=SERVER_INSTRUCTIONS)
    tools: tuple[tuple[Callable[..., object], str, ToolAnnotations], ...] = (
        (session.list_instances, LIST_INSTANCES_DESCRIPTION, LOCAL_READ),
        (session.describe_table, DESCRIBE_TABLE_DESCRIPTION, REMOTE_READ),
        (session.request_table, REQUEST_TABLE_DESCRIPTION, REMOTE_READ),
        (session.request_tables, REQUEST_TABLES_DESCRIPTION, REMOTE_READ),
        (session.add_tables, ADD_TABLES_DESCRIPTION, REMOTE_APPEND),
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
