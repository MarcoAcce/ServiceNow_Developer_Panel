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

# Code stuff

This project is written entirely in Python. 
I used `Pyside6` for the UI and the `mcp` package for the MCP server.
The list of packages needed to build this application is in the `requirement.txt` file.

`build_linux.sh` and `build_windows.sh` build the application and its installer with a
single command.
