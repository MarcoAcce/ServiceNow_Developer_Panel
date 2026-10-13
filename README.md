# What is this project

This project is meant as a helper tool for service now developer.
It provides a simple and desktop native UI to make Rest API call to a ServiceNow instance, displaying and querying the result.

For example you may extract all client scripts targetting a specific table, or you may query the ACL for a specific field or you may simply select all records in a table.

The same API used for the user interface are also used to define a local MCP server, so that your AI moodel of choice can interface with you ServiceNow instance.

This project provides mostly read-only methods, although put calls may be added in the future.

# How to use it

To get started with this tool you first need to configure your instance and your authentication method in the configuration dialog. 
Note: You're authentication are only saved locally and sent to ServiceNow to authenticate your requests.

You can choose to save basic authentication credentials or to use OAuth or JWT tokens, depending on what's configured on your instance.

## User interface

The *main tab* provides the buttons to send new request to the interface: clicking one of these will open the relevant *new request* tab, where you can set filters and details of your request.

When the tool receives a response to your request a new tab is generated automatically, where you can see, filter or save the result. 

The *sidebar* let'you move between the *main* tab, the *response* tabs and the *configuration* tab. You can keep as many responses as you want in the sidebar: they will be ordered by date and will be labeled using the target table name. You can also delete a *response* tab from the sidebar at any time to remove it.

## MCP

TBD

## Database

The local database is used mainly to store your instances details, your authentication methods and you UI configuration. 
The database is also used for response caching: whenever you send a request to an instance the response is saved to a local database for up to 5 minutes (configurable in the *configuration* tab) so that you can come back to it later. 

Any push call to the instance will clear your local cache for that instance.


# Code stuff

This project is written entirely in Python. 
I use pyside6 for the UI and the mcp package to create the MCP server.
The list of packages needed to build this application is in the requirement.txt file.

There are two simple scritps to build the application, either for linux or windows, with a single command.