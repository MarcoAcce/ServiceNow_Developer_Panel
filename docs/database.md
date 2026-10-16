# Database

The application creates and keeps local SQLite databases. 
They store:
- your instances and their authentication methods, **encrypted** (with a key tied to your machine and user)
- your settings, such as theme, cache expiration and suggestions
- the cached responses

The databases live in the `data` folder next to the application. 
If that folder is not writable, the application uses `%LOCALAPPDATA%\ServiceNowDeveloperPanel` on Windows or `~/.local/share/ServiceNowDeveloperPanel` on Linux.

## Caching

Every response is saved to a local database, so that it can be queried and reused.

- Repeated requests reuse the cached response until it expires. You can use the *refresh* button to force a new request.
- Cached responses expire after 5 minutes by default. You can change this time in the *Configuration* tab.
- Expired responses are cleaned up at startup, or manually with *Clean up cache now* in the *Configuration* tab.

# Links
- [Configuration](Configuration.md)
- [Back to README](../README.md)