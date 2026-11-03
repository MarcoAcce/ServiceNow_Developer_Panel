# Database

The application creates and keeps local SQLite databases. 
They store:
- your instances and their authentication methods, **encrypted** (with a key tied to your machine and user)
- your settings, such as theme, cache expiration and suggestions
- the cached responses

The databases live in the `data` folder next to the application. 
If that folder is not writable, the application uses `%LOCALAPPDATA%\ServiceNowDeveloperPanel` on Windows or `~/.local/share/ServiceNowDeveloperPanel` on Linux.

## Caching

Responses are cached locally, so that they can be queried and reused.

Each instance can use one of two caching options, chosen with the *In-memory cache* toggle in the *Configuration* tab:
- **Persistent** (default): responses are saved to files in the `cache` folder.
- **In-memory**: responses are kept in RAM and never written to disk. They use more memory and are lost once the application and every MCP client are closed.

Switching option deletes the cached responses of that instance.

- Repeated requests reuse the cached response until it expires. You can use the *refresh* button to force a new request.
- Cached responses expire after 5 minutes by default. You can change this time in the *Configuration* tab.
- Expired responses are cleaned up at startup, or manually with *Clean up cache now* in the *Configuration* tab.

# Links
- [Configuration](Configuration.md)
- [Back to README](../README.md)