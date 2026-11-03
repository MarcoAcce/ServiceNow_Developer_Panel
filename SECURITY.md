# Security policy

## Reporting a vulnerability

Please do not open a public issue for security problems.

Report them privately through GitHub: open the **Security** tab of this repository and choose **Report a vulnerability**. If that is not available to you, contact the maintainer through the email address on their GitHub profile.

Include what you found, the steps to reproduce it, the version you tested and, if you can, its impact. I mantain this project in my spare time: I will try to acknowledge a report within a week and to fix confirmed issues as soon as I reasonably can. Please give me a reasonable time to release a fix before disclosing the details.

## Supported versions

Only the latest release receives fixes.

## What this tool handles

Knowing what the application does helps when judging a report:

- It stores your ServiceNow instances and credentials (basic, OAuth or JWT) in a local database, encrypted with a key tied to your machine and user. The credentials are sent only to the ServiceNow instance you configure.
- Only the credentials are encrypted at rest. The data you retrieve from your instances is kept in a local cache on your machine, unencrypted apart from what your operating system provides. If that is a concern, switch to in-memory caching, so that retrieved data is never written to disk.
- It makes read-only requests (GET on the Table API). It does not write to your instances.
- The MCP server exposes the same read-only operations to the AI agent you connect. The agent does not see your credentials, but it can read any data the configured account is allowed to read, and that data is then processed by the agent and its provider. Use an account with the least privilege needed, and follow your organization's policies.
- The application sends no telemetry.

## Out of scope

- Behavior of the ServiceNow instance itself, or of the AI agent and model you connect through MCP.
- Issues that require an attacker to already control your user account or machine.
- The Windows SmartScreen warning, which appears because the installers are not code-signed (see [Building and installing](docs/build.md)).
