# Syntax Local AI Deployment Guide

This guide covers the supported deployment modes and the recommended free
hosted setup:

> Render Free Django Web Service + Neon Free PostgreSQL

## Deployment modes

| Mode | Django/database | Ollama/files/Git | Use case |
| --- | --- | --- | --- |
| `offline` | Local SQLite | Local machine | Private offline development |
| `hosted` | Render + Neon | Disabled by design | Public hosted web app |
| `hybrid` | Render + Neon | Local connector | Hosted UI with local coding workspace |

The Render Blueprint defaults to `hosted`. Use `hybrid` only after pairing the
local connector from the Connector panel.

## Prerequisites

- A GitHub repository containing this project.
- A [Neon](https://console.neon.tech/) account.
- A [Render](https://dashboard.render.com/) account.
- Python 3.11 for local validation.
- Node.js for the JavaScript and VS Code extension checks.

Do not commit `.env`, database URLs, passwords, connector tokens, or secret
keys.

## 1. Create the Neon database

1. Create a Neon project.
2. Open **Connect**.
3. Copy the PostgreSQL connection string.
4. Prefer Neon's pooled connection string for a serverless/free web service.
5. Keep `sslmode=require` in the connection string.

The value has this shape:

```text
postgresql://USER:PASSWORD@HOST/DBNAME?sslmode=require
```

Never put this value in Git or in a committed `.env` file.

## 2. Validate locally before pushing

From PowerShell:

```powershell
python -m venv venv
.\venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r requirements.txt

python manage.py check --deploy
python manage.py makemigrations --check --dry-run
python manage.py migrate --plan
.\scripts\test-all.ps1
```

To test the Neon connection locally for the current PowerShell session only:

```powershell
$env:DATABASE_URL = "postgresql://USER:PASSWORD@HOST/DBNAME?sslmode=require"
$env:DJANGO_DEBUG = "false"
$env:DEPLOYMENT_MODE = "hosted"
$env:ALLOWED_HOSTS = "127.0.0.1,localhost"
$env:CSRF_TRUSTED_ORIGINS = ""

python manage.py check --deploy
python manage.py migrate
```

Close the PowerShell window or remove these variables to return to local
SQLite development.

## 3. Deploy on Render

1. Push the repository to GitHub:

   ```powershell
   git push origin main
   ```

2. In Render, choose **New → Blueprint**.
3. Select the GitHub repository.
4. Render detects `render.yaml`.
5. Set the values marked `sync: false`:

   ```text
   DATABASE_URL=your complete Neon PostgreSQL URL
   ALLOWED_HOSTS=your-service-name.onrender.com
   CSRF_TRUSTED_ORIGINS=https://your-service-name.onrender.com
   ```

6. Keep these values:

   ```text
   DJANGO_DEBUG=false
   DEPLOYMENT_MODE=hosted
   DATABASE_SSLMODE=require
   ```

7. Let Render generate `DJANGO_SECRET_KEY`.
8. Create the service and wait for the first deployment to finish.

The Blueprint runs:

```text
python -m pip install -r requirements.txt
python manage.py migrate --noinput
python manage.py collectstatic --noinput
gunicorn offline_codegpt.wsgi:application --bind 0.0.0.0:$PORT
```

## 4. Verify the deployment

Open:

```text
https://YOUR-SERVICE.onrender.com/health/
```

Expected response:

```json
{"status":"ok","service":"syntax-local-ai"}
```

Then verify:

- The home page loads over HTTPS.
- Static CSS and JavaScript load correctly.
- Signup and login work.
- A user can create a chat.
- `/api/deployment/mode/` reports `hosted`.
- Local Ollama, shell, filesystem, and Git endpoints are blocked in hosted mode.

## 5. Use Hybrid mode

Hybrid mode keeps the Django UI and Neon database hosted while Ollama and the
project workspace remain on the developer's machine.

1. Change Render's `DEPLOYMENT_MODE` to `hybrid`.
2. Sign in to the hosted application.
3. Open **Workspace tools → Connector**.
4. Generate a one-time pairing code.
5. On the local computer run:

   ```powershell
   python scripts/local_connector.py `
     --server-url https://YOUR-SERVICE.onrender.com `
     --pairing-code ONE_TIME_CODE `
     --workspace C:\path\to\project
   ```

6. Save the printed token securely.
7. Use the token for future runs:

   ```powershell
   python scripts/local_connector.py `
     --server-url https://YOUR-SERVICE.onrender.com `
     --token SAVED_TOKEN `
     --workspace C:\path\to\project
   ```

The connector uses outbound HTTPS polling. The hosted server does not open an
inbound port on the local computer. Connector commands remain approval-gated,
and connector policies control file, Git, Ollama, test, shell, and patch
permissions.

For Windows tray control:

```powershell
python scripts/local_connector_tray.py `
  --server-url https://YOUR-SERVICE.onrender.com `
  --token SAVED_TOKEN `
  --workspace C:\path\to\project
```

## 6. Useful post-deployment commands

Run locally before every production push:

```powershell
python manage.py check --deploy
python manage.py makemigrations --check --dry-run
python manage.py migrate --plan
.\scripts\test-all.ps1
git status
git push origin main
```

Render automatically redeploys after a push when `autoDeploy: true` is active.

## Environment variables

| Variable | Required | Description |
| --- | --- | --- |
| `DJANGO_SECRET_KEY` | Yes in production | Stable private Django secret; Render can generate it |
| `DJANGO_DEBUG` | Yes | Use `false` on Render |
| `DEPLOYMENT_MODE` | Yes | `offline`, `hosted`, or `hybrid` |
| `DATABASE_URL` | Yes on Render | Neon PostgreSQL URL |
| `DATABASE_SSLMODE` | Recommended | `require` |
| `DATABASE_CONN_MAX_AGE` | Optional | Database connection reuse, default `60` |
| `ALLOWED_HOSTS` | Yes | Render hostname without `https://` |
| `CSRF_TRUSTED_ORIGINS` | Yes | Full HTTPS Render origin |

## Troubleshooting

### Database connection failure

- Confirm the Neon URL is complete and starts with `postgresql://`.
- Use the pooled Neon connection string.
- Keep `sslmode=require`.
- Check that `DATABASE_URL` was entered as a secret environment variable in
  Render, not in source control.

### Bad Request or CSRF failure

Set:

```text
ALLOWED_HOSTS=your-service-name.onrender.com
CSRF_TRUSTED_ORIGINS=https://your-service-name.onrender.com
```

Redeploy after changing environment variables.

### Static files are missing

Check the Render deploy log for:

```text
python manage.py collectstatic --noinput
```

The project uses WhiteNoise for static files. Do not add `staticfiles/` to Git.

### Ollama is unavailable in hosted mode

This is expected. Render cannot reach Ollama on a private computer. Use local
`offline` mode or switch to `hybrid` mode and run the local connector.

### Render service is slow after inactivity

The free web service sleeps. The first request after inactivity can take longer
while the service wakes up.

## Free-tier limitations

- Render Free services sleep after inactivity.
- Render's filesystem is temporary.
- Do not store uploaded files, backups, model weights, or durable RAG indexes
  only on Render's local disk.
- Neon stores database metadata, but it is not object storage for large files.
- Ollama and large model downloads should remain local or use a separate GPU
  service.
- Add S3/R2-compatible object storage and paid persistent infrastructure before
  treating the deployment as production-critical.

## Security checklist

- Use HTTPS only.
- Keep `DJANGO_SECRET_KEY` stable and private.
- Rotate Neon credentials if they are exposed.
- Rotate connector tokens from the Connector panel if necessary.
- Keep `DJANGO_DEBUG=false`.
- Review Render logs for accidental secrets before sharing them.
- Back up Neon data and test restore procedures.
- Use `hosted` mode when local tools must remain unavailable.
