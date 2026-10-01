# Syntax Local AI

Syntax Local AI is a private, local-first coding workspace built with Django and Ollama. It lets developers ask questions about code, upload project files, run guarded checks, plan agent tasks, review changes, manage workspace access, and generate deployment assets without sending coding context to a hosted AI provider by default.

## What the project includes

### Local coding workspace

- Streaming responses from a local Ollama model.
- Model selection and per-user Ollama settings.
- Paste code, upload files, upload project folders, and upload images.
- Automatic language detection, syntax highlighting, copy controls, and downloadable responses.
- Editable user prompts with conversation revisions.
- Chat history with rename, pin, archive, search, and export support.
- Markdown, JSON, and PDF chat export.

### Project knowledge and code intelligence

- Project file indexing and retrieval-augmented context.
- Project search with relevant file and line references.
- File preview, re-index, and delete controls.
- Architecture graph analysis and cross-repository impact analysis.
- API contract analysis and documentation generation.
- Dependency analysis, security scanning, and secret detection.

### Agent platform

- Agent planning with approval checkpoints.
- Multi-agent teams with roles, shared context, and progress checkpoints.
- Secure runtime limits for timeout, memory, output, approval, and network blocking.
- Durable background jobs with pause, resume, retry, cancel, logs, and checkpoints.
- Guarded Python, JavaScript, and in-memory SQL execution.
- Unit-test generation and test workspace execution.

### Evaluation and observability

- Evaluation tasks, model runs, scoring, regression suites, and dashboard results.
- AI request timing, success rate, input/output usage, and model activity.
- Live-polled agent, team, and background-job timelines.
- Local resource summaries for recorded CPU, memory, and tool-call metadata.

### Workspace, identity, and security

- User accounts with per-user sessions, project knowledge, and uploads.
- Team workspaces with admin, developer, reviewer, and viewer roles.
- Workspace approval policies and audit history.
- OIDC authorization-code login with PKCE and allowed-domain checks.
- SAML entrypoint configuration and signed-gateway callback surface.
- SCIM-style user provisioning and deprovisioning with rotating bearer tokens.
- Encrypted workspace secrets vault with masked listings, versioning, reveal auditing, and rotation.

### Integrations and delivery

- Git status, diff, staging, and commit workflows.
- Optional remote repository, issue, and pull-request integrations.
- MCP tools and local/custom connectors with write approval.
- Extension marketplace with permission review, installation, uninstall, rollback metadata, and custom extension publishing.
- Dockerfile, Docker Compose, GitHub Actions, GitLab CI, and dev-container generation.
- Production deployment kit generation for Docker Compose and Kubernetes.
- Generated health checks, environment validation, backup scripts, and rollback scripts.
- Incident analysis, browser-test generation, model routing, provenance generation, and verification.

## Requirements

- Windows, macOS, or Linux.
- Python 3.10 or newer.
- Ollama installed and running locally.
- At least one coding model, such as 'qwen2.5-coder:1.5b'.
- Optional vision model, such as 'llava:latest', for image analysis.

The project uses:

- Django 5.2
- SQLite for local development
- Ollama for local model inference
- 'requests' for local/provider and optional remote integrations
- 'cryptography' for encrypted workspace secrets

## Installation

For a guided Windows setup, run:

~~~powershell
.\scripts\setup-offline.ps1
~~~

Use `-SkipOllama` when preparing the Python environment on a machine that will receive Ollama separately.

### Windows PowerShell

From the project directory:

~~~powershell
py -3 -m venv venv
.\venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r requirements.txt
Copy-Item .env.example .env
python manage.py migrate
python manage.py check
~~~

If PowerShell blocks activation, run the following in the current PowerShell window and activate again:

~~~powershell
Set-ExecutionPolicy -Scope Process Bypass
~~~

### macOS or Linux

~~~bash
python3 -m venv venv
source venv/bin/activate
python -m pip install --upgrade pip
pip install -r requirements.txt
cp .env.example .env
python manage.py migrate
python manage.py check
~~~

## Configure Ollama

Start Ollama before using the AI features:

~~~powershell
ollama serve
ollama pull qwen2.5-coder:1.5b
ollama pull llava:latest
~~~

On Windows, Ollama may already be running as a desktop application. Verify it with:

~~~powershell
ollama list
~~~

The default local Ollama server is:

~~~text
http://127.0.0.1:11434
~~~

The application starts with 'qwen2.5-coder:1.5b' as the default coding model. The Ollama panel lets each authenticated user change the server URL, model, temperature, top-p, and context length.

## Environment configuration

Copy '.env.example' to '.env' and replace the development secret:

~~~text
DJANGO_SECRET_KEY=replace-with-a-long-random-value
OLLAMA_VISION_MODEL=llava:latest
~~~

Important:

- Keep 'DJANGO_SECRET_KEY' private and stable in production.
- The secrets vault derives its encryption key from Django’s secret key. Changing the key makes existing encrypted vault values unreadable.
- Do not commit '.env', API tokens, passwords, provider secrets, or generated production environment files.
- Provider, Git, MCP, and remote integrations are optional and should be enabled only when needed.

## Run the application

Activate the virtual environment, then run:

~~~powershell
.\venv\Scripts\Activate.ps1
python manage.py runserver
~~~

Open:

~~~text
http://127.0.0.1:8000/
~~~

For a different port:

~~~powershell
python manage.py runserver 127.0.0.1:8080
~~~

### Watch a project folder

Keep a local folder indexed while you work:

~~~powershell
python manage.py watch_project C:\path\to\project --username YOUR_USER
~~~

Use `--once` for a single incremental scan. The watcher reads supported local files and reuses the normal project index and document parsers.

## First-time user workflow

1. Open the home page.
2. Use guest mode for basic local chat without an account.
3. Create an account from **Create free account** to unlock project uploads, images, history, workspaces, agent tools, exports, and quality tools.
4. Choose an Ollama model and language.
5. Paste code or upload one or more files.
6. Enter a prompt, such as:
   - 'Explain this code step by step'
   - 'Find security problems and suggest fixes'
   - 'Generate tests for this file'
   - 'Refactor this code for production'
7. Use the response controls to copy, download, edit the prompt, or regenerate the answer.
8. Open a panel from the top toolbar when you need a specialized workflow.

## UI panel guide

### Ollama

Change the local server URL, default model, temperature, top-p, and context length. The model manager can list, pull, activate, and delete local Ollama models.

### Remote

Configure optional GitHub/GitLab-style repository integrations, inspect repositories and issues, and create draft pull requests. Review the remote provider and token settings before enabling write operations.

### Tools

Manage MCP connectors and run read-only project searches. Write-capable tools require approval and are recorded in the MCP tool-call history.

### Extensions

Review requested permissions before installing an extension. Available actions include:

- Install after approving all requested permissions.
- Uninstall an installed extension.
- Roll back when a previous version is available.
- Publish a custom extension manifest using the SDK form.

### Metrics

View AI request counts, success rate, latency, input/output usage, active jobs, tool calls, agent logs, team checkpoints, and job timeline events. The panel refreshes while open.

### Eval Lab

Create evaluation tasks, run them against selected models, score results, create regression suites, and inspect model comparisons in the results dashboard.

### Team

Create workspaces, add members, assign roles, review audit events, and manage workspace access.

### DevOps

Generate Dockerfiles, Docker Compose files, GitHub Actions, and GitLab CI files. Paste build or server logs to receive findings and recommendations.

### Deploy

Generate a deployment kit containing:

- 'docker-compose.deploy.yml'
- Kubernetes Deployment and Service manifests
- Health checks and readiness/liveness probes
- 'scripts/backup.sh'
- 'scripts/rollback.sh'
- Deployment checklist

Paste '.env' content into the validator to detect malformed lines, empty values, and literal secrets.

The toolkit generates files and guidance; it does not deploy to a server automatically.

### Docs

Generate README content, API documentation, architecture summaries, onboarding guides, and changelog-style documentation from local project context.

### Review

Run the AI review gate against a diff and test output. The gate reports blocking findings and approval status before a release or merge.

### Deps

Analyze dependency manifests for outdated, risky, or suspicious packages and review recommended actions.

### Browser

Generate Playwright-style browser tests and analyze browser test reports.

### Router

Route a task to a suitable local model based on task complexity, memory, and available GPU information.

### Env

Generate a development container configuration with recommended extensions and local development settings.

### Incident

Analyze incident logs, traces, and metrics and produce likely causes and next actions.

### Arch

Analyze project architecture and cross-repository service relationships. Cross-repository input uses this shape:

~~~json
[
  {
    "name": "api",
    "files": [
      {"filename": "users.py", "content": "..."}
    ]
  }
]
~~~

### API

Analyze API specifications and implementation code for contract mismatches, missing endpoints, and response issues.

### Proof

Generate and verify artifact provenance based on files and commit information.

### Policy

Manage workspace approval policies, enterprise identity settings, OIDC/SAML metadata, SCIM settings, and audit retention.

### Secrets

Create workspace-scoped secrets as an administrator. Vault listings always remain masked. A secret is returned only after an explicit admin reveal action, and reveal/update/delete operations are audited.

## Agent workflow

The agent workspace supports:

1. Create a plan from a goal.
2. Review protected actions before execution.
3. Run a single task or create a multi-agent team.
4. Queue a durable background job.
5. Pause, resume, retry, or cancel the job.
6. Inspect logs and checkpoints in Metrics.
7. Run guarded code and tests through the runtime limits.

The secure runtime defaults to a three-second timeout, 128 MB memory limit, bounded output, approval required, and blocked network access. Administrators should review these limits before using the feature with untrusted code.

## Enterprise identity and SCIM

Open **Policy → Enterprise SSO and SCIM** as a workspace administrator.

### OIDC

Configure:

- Provider: 'OIDC'
- Issuer URL
- Client ID
- Allowed email domains
- Optional SSO enforcement setting

Users can select **Continue with OIDC** from the login page. The flow uses a short-lived session state and PKCE. Successful identity claims are linked to a local Django user and workspace membership.

### SAML

Configure the SAML entrypoint URL and use **Continue with SAML** from the login page. The application provides the handoff and callback surface, but intentionally does not accept unsigned SAML assertions. Use a signed SAML gateway or a verified SAML adapter before enabling production SAML login.

### SCIM

1. Enable SCIM in the Policy panel.
2. Rotate the SCIM token.
3. Copy the token immediately; it is shown only once.
4. Send the token as a bearer token.
5. Include the workspace ID in 'X-Workspace-ID'.

Example request:

~~~powershell
$headers = @{
  Authorization = "Bearer YOUR_SCIM_TOKEN"
  "X-Workspace-ID" = "1"
}
$body = @{
  userName = "developer@example.com"
  displayName = "Example Developer"
  active = $true
  role = "developer"
} | ConvertTo-Json
$request = @{
  Method = "Post"
  Uri = "http://127.0.0.1:8000/api/identity/scim/"
  Headers = $headers
  ContentType = "application/json"
  Body = $body
}
Invoke-RestMethod @request
~~~

SCIM provisioning creates or updates a local user and workspace membership. Deprovisioning disables the user and removes the workspace membership when permitted.

## Important API groups

All protected API routes require an authenticated session and Django CSRF protection for browser write requests.

~~~text
POST /api/ask-code/                         Ask the local model
GET  /api/models/                           List local models
GET/POST /api/ollama/settings/              Ollama settings
GET/POST /api/project/                      Project files
GET     /api/observability/                 AI and agent metrics
GET/POST /api/agent/teams/                  Multi-agent teams
GET/POST /api/agent/jobs/                   Durable background jobs
GET/POST /api/sandbox/policy/               Secure runtime policy
GET/POST /api/evaluations/tasks/            Evaluation tasks
GET/POST /api/workspace/                    Workspace membership
GET/POST /api/identity/enterprise/          OIDC/SAML/SCIM settings
GET/POST /api/identity/scim/                SCIM directory operations
GET/POST /api/secrets/                      Encrypted secret listing/upsert
POST     /api/secrets/<id>/reveal/          Explicit admin reveal
DELETE   /api/secrets/<id>/                 Delete a secret
GET/POST /api/extensions/marketplace/       Marketplace and SDK
POST     /api/deployment/kit/               Generate deployment assets
POST     /api/deployment/validate/          Validate environment content
POST     /api/security/scan/                Security scanning
POST     /api/tests/generate/               Test generation
POST     /api/tests/run/                   Guarded test execution
POST     /api/git/status/                   Git workspace status
POST     /api/git/diff/                     Git diff
POST     /api/git/commit/                   Create a local Git commit
POST     /api/mcp/                          MCP JSON-RPC tools
~~~

## Safety boundaries

- The default AI provider is local Ollama.
- Python and JavaScript execution runs through guarded checks/runtime limits; do not treat the sandbox as a complete operating-system security boundary.
- SQL execution uses an in-memory database.
- Network access is blocked by the secure runtime policy.
- Remote Git and repository features are optional and can change external state; review actions and permissions before using them.
- Generated Docker, Kubernetes, CI, backup, and rollback files must be reviewed before production use.
- Do not paste production secrets into prompts, logs, issue descriptions, or generated files.

## Testing and verification

Run the full test suite:

~~~powershell
.\venv\Scripts\Activate.ps1
python manage.py check
python manage.py test
node --check static\chat\app.js
~~~

The current suite covers authentication, streaming chat, uploads, project search, agents, sandbox policies, background jobs, evaluations, workspaces, SSO, SCIM, secrets, extensions, deployment generation, Git workflows, security scanning, and integrations.

## Troubleshooting

### Ollama connection errors

Check that Ollama is running and that the selected model exists:

~~~powershell
ollama list
ollama run qwen2.5-coder:1.5b
~~~

If the Ollama server uses a different URL, update it in the Ollama panel after signing in.

### Database or migration errors

~~~powershell
python manage.py makemigrations
python manage.py migrate
python manage.py check
~~~

Do not delete 'db.sqlite3' in a project containing data unless you intentionally want to reset the local database.

### Images are not understood

Install and pull the configured vision model:

~~~powershell
ollama pull llava:latest
~~~

Then verify 'OLLAMA_VISION_MODEL' in '.env'.

### SSO callback errors

Confirm that the provider redirect URI exactly matches the application callback:

~~~text
http://127.0.0.1:8000/sso/oidc/callback/
~~~

For SAML, confirm that a signed gateway or verified adapter is configured. The application rejects unsigned assertions by design.

## Project layout

~~~text
chat/
  models.py              Database models
  views.py               Web views and API endpoints
  urls.py                Application routes
  sandbox.py             Guarded code execution
  vault.py               Encrypted secret helpers
  deployment.py          Deployment artifact generation
  architecture.py        Architecture analysis
  cross_repository.py    Cross-repository analysis
  quality.py             Code quality checks
  security.py            Security scanning
  devops.py              DevOps artifact and log analysis
  migrations/            Database migrations
  tests.py               Django feature tests

offline_codegpt/
  settings.py            Django configuration
  urls.py                Root URL configuration

templates/chat/
  index.html             Main application interface
  login.html             Local and SSO login page
  signup.html            Account creation page

static/chat/
  app.js                 Frontend behavior and API calls
  app.css                Application styling

requirements.txt         Python dependencies
.env.example             Environment variable template
manage.py                Django management entry point
~~~

## Git workflow

Create a feature branch and commit each feature separately:

~~~powershell
git checkout -b feature/my-change
git status
git add .
git commit -m "feat: describe the change"
git log --oneline -10
git push -u origin feature/my-change
~~~

## Recommended next features

The strongest next roadmap items, based on the current implementation, are:

1. **Production SAML adapter and SSO administration**
   - Add signed assertion validation, certificate rotation, metadata import, provider discovery caching, and SSO enforcement in the local login policy.

2. **Real-time agent event streaming**
   - Replace polling with SSE or WebSockets.
   - Stream tool calls, approvals, logs, resource updates, and job state changes in real time.

3. **Scoped secret injection**
   - Inject selected vault secrets into approved agent jobs and sandbox processes without exposing values to prompts or logs.
   - Add short-lived credentials and per-tool secret permissions.

4. **Signed and isolated extension execution**
   - Add package signatures, publisher trust, extension version manifests, isolated workers, dependency scanning, and marketplace review workflows.

5. **Approved deployment execution**
   - Turn generated deployment assets into a guarded workflow with preflight checks, health monitoring, live rollout progress, automatic rollback, and deployment audit history.

Recommended order:

~~~text
Signed SAML and SSO enforcement
  -> Real-time agent streaming
  -> Scoped secret injection
  -> Signed extension runtime
  -> Approved deployment execution
~~~

Product direction:

> Syntax Local AI is a private local development platform that plans, edits, tests, reviews, documents, and ships software with human approval.
