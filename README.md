# What is this project

This project is meant as a helper tool for service now developer.
It provides a simple, desktop native UI to make Rest API call to a ServiceNow instance and to browse and query the result.

For example, you may extract all client scripts targeting a table, check the ACLs for a field, or you simply select all records in a table.

The same APIs used for the user interface also powers a local MCP server, so your AI model of choice can browse and study your ServiceNow instance.

This tool provides read-only methods, although PUT calls may be added in the future.

![Home tab](docs/images/home.png)

# Warning notice

This tool pulls data from a selected ServiceNow instance, using user provided authentication, to process it locally. Always make sure not to violate your organization's policies. I do not in any way condone misuse of this tool.

# How to use it

To get started with this tool first configure your instance and authentication methods in the *Configuration* tab. 
Note: Your credentials are only saved locally and sent to ServiceNow to authenticate your requests.

- [Configuration](docs/configuration.md): settings, instances and authentication methods.
- [User interface](docs/user_interface.md): tabs and sidebar.
- [Database](docs/database.md): what is stored locally and where, how responses are reused and when they expire.
- [MCP](docs/mcp.md): the MCP server and its tools.

## User interface

The *main tab* provides the buttons to send new request to the interface: clicking one of these will open the relevant *new request* tab, where you can set filters and details of your request.

When the tool receives a response to your request a new tab is generated automatically, where you can see, filter or save the result. 

The *sidebar* let'you move between the *main* tab, the *response* tabs and the *configuration* tab. You can keep as many responses as you want in the sidebar: they will be ordered by date and will be labeled using the target table name. You can also delete a *response* tab from the sidebar at any time to remove it.

## Database

The local database is used to store your instances details, your authentication methods, your UI configuration and for response caching.

### Caching

Whenever you send a request to an instance the response is saved to a local database to enable querying of the responses and other more complex features.

Any repeated request will simply reuse the cache until it expires, but you can always use the *refresh* button to force a new request and cache refresh.

All cached responses have an expiration after which they're no longer used: subsequent calls will result in a new request. By default the cache last 5 minutes, this value is configurable in the *configuration* tab: 

The cache is automatically cleaned at startup, but there's a button to clean it manually in the *configuration* tab.

## MCP

The application comes with a MCP server that allows AI agent to perform basically everything the user can do.
Agents will be able to fetch tables from the instance, cache them locally and then query them using plain SQL. This is the core feature of the MCP server, it empowers the agent to do search as deeply as it wants in the instance, using standard SQL instructions like Join and Group By which are not supported by the Table API.

The Describe table tool will allow them to understand how a table is defined, parsing the instance Dictionary for all its fields.
The Verify ACL tool allows agent to check the protections on a table or its field and to understand who can perform operations.

You still need to use the main application UI to add a instances and authentication for the MCP server.


# Code stuff

This project is written entirely in Python. 
I used `Pyside6` for the UI and the `mcp` package for the MCP server.
The list of packages needed to build this application is in the `requirement.txt` file.

`build_linux.sh` and `build_windows.sh` build the application and its installer with a
single command.
