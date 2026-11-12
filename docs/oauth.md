# OAuth login

With the OAuth login method the panel works with your own user account on the instance without storing your password: you log in to the instance in your browser once, and the panel keeps the tokens the instance issues and renews them on its own.

## On the instance

An administrator registers the panel as an OAuth application:

1. Open *System OAuth > Application Registry*, click *New* and choose *Create an OAuth API endpoint for external clients*.
2. Give it a name, for example *ServiceNow Developer Panel*.
3. Set the *Redirect URL* to `http://localhost:8431/oauth/callback`. While a login is in progress the panel answers at this address on your computer; nothing else has to be installed.
4. Save, then copy the *Client ID* and the *Client Secret*, unlocking the secret field to read it. The token lifespans can stay at their defaults: the access token is renewed automatically with the refresh token, and only the end of the refresh token lifespan, 100 days by default, requires a new login.

## In the panel

1. In the *Configuration* tab, expand the instance and click *Add authentication method*, or *Add MCP authentication method* for the local MCP server.
2. Choose *OAuth login* and paste the client id and the client secret. Leave *Redirect URL* empty, unless the address registered on the instance differs from the default above: then enter the registered one, which must be an `http://localhost` address.
3. Click *Login* and complete the login described below. A new method can be saved only after a first login.
4. Click *Save*.

## The login flow

1. The panel opens the login page of the instance in your browser and shows a login dialog.
2. Sign in to the instance and click *Allow*.
3. The instance sends your browser to the redirect URL, a page served by the panel that shows the authorization code. The login dialog completes the login on its own and closes, and the method shows the user you are logged in as.
4. If that page cannot be reached, for example because the address is already in use on your computer, copy the code shown by your browser, or the address of the page you landed on, and paste it in the login dialog.

Requests then use the stored tokens and renew them without asking. When the renewal is no longer possible, the login dialog appears again when a request needs it; you can also log in ahead of time with the *Login* button next to the active method on the home page and on the request pages, or in the configuration. For the MCP server, the agent calls the `login_oauth` tool: the panel opens the same browser login and waits for you to allow the access. The tokens are never shown to the agent.

## Troubleshooting

- **Invalid redirect_uri**: the redirect URL registered on the instance does not match. Register `http://localhost:8431/oauth/callback`, or enter the registered address in the method.
- **The login failed: ... access_denied**: the client id or the client secret is wrong, or the application registry entry is inactive.
- **The browser did not open**: use the link in the login dialog.

# Links

- [Configuration](configuration.md)
- [MCP server](mcp.md)
- [Back to README](../README.md)
