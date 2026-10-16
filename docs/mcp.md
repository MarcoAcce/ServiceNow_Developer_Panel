# MCP

The application comes with a local MCP server that lets AI agents do most of what you do through the UI. 
It is read-only: every request is a GET call on the Table API.

The core feature is SQL queries on cached data: agents can fetch tables from the instance to cache them locally and query using plain SQL. 
This lets them study the instance as deeply as they need, with joins and group by that the Table API does not support.

## Tools

| Tool | Purpose |
| --- | --- |
| `list_instances` | List the configured instances |
| `request_table` | Fetch records from one table |
| `request_tables` | Fetch several tables into one cache, so they can be joined |
| `add_tables` | Add tables to an existing cache |
| `query_cache` | Query a cache with SQL |
| `export_cache` | Save a cache as CSV or XLSX |
| `list_cached_responses` | List the cached responses |
| `describe_table` | Read the fields of a table from the instance dictionary |
| `verify_acl` | Check who can perform an operation on a table or field |

## Setup

Instances and credentials are managed through the main application: add an *MCP authentication* method to each instance the server should reach (see [Configuration](configuration.md)).
Agents never see these credentials.

The installer saves an `mcp.json` file in the install folder. 
Add its content to the MCP configuration of your client, for example [`mcp.json`](../.mcp.json)

# Links

- [Back to README](../README.md)
- [Configuration](configuration.md)