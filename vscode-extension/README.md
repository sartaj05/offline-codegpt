# Syntax Local AI VS Code extension

Start the Django server, then install this folder as a VS Code extension.

Available commands:

- Syntax Local AI: Ask About Selection
- Syntax Local AI: Review Current File
- Syntax Local AI: Explain Selection
- Syntax Local AI: Generate Tests
- Syntax Local AI: Ask Project

The extension calls the localhost-only API endpoint and sends code to the local Syntax Local AI server.

JetBrains integration
---------------------
JetBrains plugins can use the same loopback endpoint at `/api/cli/ask/` with
form fields `prompt`, `code`, and `language`. The endpoint returns newline-
delimited streaming events, so a plugin can render tokens progressively without
adding a cloud dependency. Use the local server URL configured in the app.
