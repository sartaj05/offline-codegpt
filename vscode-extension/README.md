# Syntax Local AI VS Code extension

Start the Django server, then install this folder as a VS Code extension.

Available commands:

- Syntax Local AI: Ask About Selection
- Syntax Local AI: Review Current File
- Syntax Local AI: Explain Selection
- Syntax Local AI: Generate Tests
- Syntax Local AI: Ask Project
- Syntax Local AI: Apply Last Suggested Code
- Syntax Local AI: Run Approved Project Tests

The extension also provides local inline completion. File review findings that
include line numbers are shown as VS Code diagnostics. Applying a suggestion
always requires confirmation; test execution uses the configured local command
and also requires confirmation.

The extension calls the localhost-only API endpoint and sends code to the local Syntax Local AI server.

JetBrains integration
---------------------
JetBrains plugins can use the same loopback endpoint at `/api/cli/ask/` with
form fields `prompt`, `code`, and `language`. The endpoint returns newline-
delimited streaming events, so a plugin can render tokens progressively without
adding a cloud dependency. Use the local server URL configured in the app.
