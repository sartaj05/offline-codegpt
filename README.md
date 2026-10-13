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
- SQLite for local/offline development, with optional PostgreSQL through `DATABASE_URL`
- Ollama for local model inference
- 'requests' for local/provider and optional remote integrations
- 'cryptography' for encrypted workspace secrets

The deployment mode is controlled by `DEPLOYMENT_MODE`. It defaults to
`offline`, which keeps SQLite, local Ollama, local files, and Git enabled. The
mode is displayed in the UI and available from `/api/deployment/mode/`.

## Installation

For a guided Windows setup, run:

~~~powershell
.\scripts\setup-offline.ps1
~~~

## Local release checks

Run the complete local validation suite from PowerShell:

~~~powershell
.\scripts\test-all.ps1
~~~

This checks Django configuration, migration drift, the full Django test suite,
chat JavaScript syntax, and the VS Code extension manifest. Add
`-WithBrowser` only after Playwright and its browser are already installed
locally; the script never downloads browser binaries automatically.
The extension contract check covers local API auth, inline completion, diff
preview, and confirmed test execution. Authenticated browser smoke tests use
the optional `SYNTAX_LOCAL_AI_STORAGE` Playwright storage-state file.
Onboarding diagnostics show recovery commands for stopped runtimes and missing
models. Model recovery only selects an installed local model; it never performs
an automatic online download.
Benchmark a large repository without changing its index with
`python manage.py benchmark_workspace C:\path\to\repo --json` or the workspace
benchmark API. The report includes throughput, skipped files, truncation, errors,
and peak memory.

## Windows packaging

For local setup or repair, run:

~~~powershell
.\scripts\install-windows.ps1 -Offline
~~~

Offline mode expects dependency wheels in `vendor\wheels`; it never contacts a
package index. The script runs migrations, Django checks, detects Python/RAM/GPU
and Ollama/LM Studio/llama.cpp endpoints, and writes `runtime-health.json`.
`installer\SyntaxLocalAI.iss` can be built with Inno Setup to produce a Windows
installer. Uninstall preserves the source checkout; `-RemoveData -Confirmed`
moves local database, environment, media, and model data to a timestamped
backup before removal.
The setup registers `run_offline_workers --loop` at user logon; pass
`-SkipWorker` to opt out, or use `scripts\register-workers.ps1 -Unregister`.
Validate the installer definition with
`scripts\build-installer.ps1 -CheckOnly`, or omit `-CheckOnly` on a machine
with Inno Setup installed to compile the actual installer.

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

## Free Render + Neon deployment

The included `render.yaml` deploys the Django web service on Render's free
Web Service plan. Neon supplies the PostgreSQL database. This is a hosted
demo deployment, not a fully offline deployment: the database and web app are
in the cloud, while Ollama remains local unless you separately provide a
reachable hosted model runtime.

### 1. Create the Neon database

1. Create a project at [Neon](https://console.neon.tech/).
2. Open **Connect** and copy the PostgreSQL connection string. Use the pooled
   connection string when Neon offers one for the project.
3. Keep the complete URL, including `sslmode=require`, private. It looks like:

~~~text
postgresql://USER:PASSWORD@HOST/DBNAME?sslmode=require
~~~

For a local PostgreSQL smoke test, set it only in the current PowerShell
session and run migrations:

~~~powershell
$env:DATABASE_URL = "postgresql://USER:PASSWORD@HOST/DBNAME?sslmode=require"
$env:DJANGO_DEBUG = "false"
$env:ALLOWED_HOSTS = "127.0.0.1,localhost"
$env:CSRF_TRUSTED_ORIGINS = ""
python manage.py migrate
python manage.py check --deploy
~~~

Remove the variables or open a new PowerShell window to return to local
SQLite/offline development.

### 2. Deploy Django on Render

1. Push this repository to GitHub.
2. In [Render](https://dashboard.render.com/), choose **New -> Blueprint** and
   select the repository. Render detects `render.yaml`.
3. When Render asks for values marked `sync: false`, enter:
   - `DATABASE_URL`: the Neon connection string.
   - `ALLOWED_HOSTS`: the exact Render hostname, for example
     `syntax-local-ai.onrender.com`.
   - `CSRF_TRUSTED_ORIGINS`: the full HTTPS origin, for example
     `https://syntax-local-ai.onrender.com`.
4. Keep `DJANGO_DEBUG=false`. Render generates `DJANGO_SECRET_KEY` from the
   Blueprint configuration.
   The Blueprint sets `DEPLOYMENT_MODE=hosted`, which requires sign-in and
   disables local Ollama, filesystem, Git, shell, and local-agent endpoints.
5. Create the service. Its build command automatically installs dependencies,
   runs migrations, and collects static files. Its start command runs:

~~~text
gunicorn offline_codegpt.wsgi:application --bind 0.0.0.0:$PORT
~~~

6. Open `https://YOUR-SERVICE.onrender.com/health/`. A successful deployment
   returns JSON with `"status": "ok"`.

### 3. Commands after deployment

Run these locally before pushing future changes:

~~~powershell
python manage.py check --deploy
python manage.py makemigrations --check --dry-run
python manage.py migrate --plan
.\scripts\test-all.ps1
~~~

Render runs the production commands from `render.yaml` on every deployment:

~~~text
python -m pip install -r requirements.txt
python manage.py migrate --noinput
python manage.py collectstatic --noinput
gunicorn offline_codegpt.wsgi:application --bind 0.0.0.0:$PORT
~~~

### Free-tier limitations

- Render's free web service sleeps after inactivity, so the first request can
  be slow.
- Render's local filesystem is temporary. Do not rely on it for uploaded
  documents, model files, RAG indexes, backups, or SQLite data.
- Use Neon for durable application metadata. Add object storage or a paid
  persistent disk before making user uploads and indexes production data.
- Do not run Ollama or download large models in the free Render web service.
  Keep local AI features on the user's machine or use a separate paid GPU
  runtime.
- Never commit `.env`, database URLs, passwords, or generated secret keys.

## Hybrid local connector

Set `DEPLOYMENT_MODE=hybrid` when the Django UI and database are hosted but
Ollama and a project workspace stay on a trusted local machine. The connector
uses outbound HTTPS polling, so the hosted service never opens an inbound
port on the local computer.

1. Set `DEPLOYMENT_MODE=hybrid` on the hosted app and sign in.
2. Open **Workspace tools -> Connector**, choose **Generate pairing code**.
3. On the local computer, install the project requirements and run:

~~~powershell
python scripts/local_connector.py --server-url https://YOUR-SERVICE.onrender.com --pairing-code ONE_TIME_CODE --workspace C:\path\to\project
~~~

The command prints a connector token once. Store it locally and use it for
future runs:

~~~powershell
python scripts/local_connector.py --server-url https://YOUR-SERVICE.onrender.com --token SAVED_TOKEN --workspace C:\path\to\project
~~~

The connector supports Ollama health/generation, workspace listing, file
reads, and Git status. Direct chat generation is queued from the signed-in
user's explicit chat action; Connector-panel tool commands are queued as
`awaiting_approval`. Approve or reject those commands before the local process
can poll and run them.

### Desktop controller and auto-start

Windows users can keep the connector process manageable from a small Tkinter
controller:

~~~powershell
python scripts/local_connector_tray.py --server-url https://YOUR-SERVICE.onrender.com --token SAVED_TOKEN --workspace C:\path\to\project
~~~

Register or remove logon auto-start explicitly:

~~~powershell
.\scripts\register-connector-startup.ps1 -Register -ServerUrl https://YOUR-SERVICE.onrender.com -Token SAVED_TOKEN -Workspace C:\path\to\project
.\scripts\register-connector-startup.ps1 -Unregister
~~~

The controller only starts or stops the outbound connector; it does not open
an inbound port or grant additional permissions.
Tokens are hashed in the database, pairing codes expire after ten minutes,
and the Connector panel can revoke a token at any time. Use HTTPS
for the hosted URL and never paste the token into source control.

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
Model capabilities are synchronized from the local runtime inventory. If a
configured model is missing, chat selects the configured fallback or another
installed compatible model; it never downloads a replacement automatically.

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

Run `python manage.py security_audit --json --fail-on-high` or open
`/api/security/audit/` to review local shell, dynamic-code, sandbox, and tool
permission boundaries. The audit is read-only and does not replace human code
review.

Backup format v2 preserves local RAG chunks, document layout metadata, runtime
and privacy settings, and model capability metadata. Model weights are not
included in the archive; restore those through the local runtime's own manager.

Scanned PDFs are indexed with the local vision runtime when native PDF text
extraction returns no useful text. Set `LOCAL_OCR_ENABLED=0` to disable this
fallback or lower `LOCAL_OCR_MAX_PAGES` for large documents. OCR remains local
to the configured runtime and is not sent to a hosted provider.
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
