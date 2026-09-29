import re


def _safe_project_name(value):
    return re.sub(r"[^a-z0-9-]", "-", (value or "syntax-local").strip().lower()).strip("-")[:50] or "syntax-local"


def generate_deployment_kit(project_name="syntax-local", port=8000, health_path="/", strategy="rolling"):
    name = _safe_project_name(project_name)
    try:
        port = min(65535, max(1, int(port)))
    except (TypeError, ValueError):
        raise ValueError("Port must be a number between 1 and 65535.")
    health_path = health_path.strip() or "/"
    if not health_path.startswith("/") or len(health_path) > 120:
        raise ValueError("Health path must start with / and be at most 120 characters.")
    compose = f'''services:
  app:
    build: .
    ports:
      - "{port}:{port}"
    env_file:
      - .env
    restart: unless-stopped
    healthcheck:
      test: ["CMD", "python", "-c", "import urllib.request; urllib.request.urlopen('http://localhost:{port}{health_path}')"]
      interval: 30s
      timeout: 5s
      retries: 3
'''
    deployment = f'''apiVersion: apps/v1
kind: Deployment
metadata:
  name: {name}
spec:
  replicas: 2
  strategy:
    type: {"Recreate" if strategy == "recreate" else "RollingUpdate"}
  selector:
    matchLabels:
      app: {name}
  template:
    metadata:
      labels:
        app: {name}
    spec:
      containers:
        - name: app
          image: {name}:latest
          ports:
            - containerPort: {port}
          envFrom:
            - secretRef:
                name: {name}-env
          readinessProbe:
            httpGet:
              path: {health_path}
              port: {port}
            initialDelaySeconds: 10
            periodSeconds: 15
          livenessProbe:
            httpGet:
              path: {health_path}
              port: {port}
            initialDelaySeconds: 30
            periodSeconds: 30
'''
    service = f'''apiVersion: v1
kind: Service
metadata:
  name: {name}
spec:
  selector:
    app: {name}
  ports:
    - port: 80
      targetPort: {port}
  type: ClusterIP
'''
    backup = f'''#!/usr/bin/env bash
set -euo pipefail
mkdir -p backups
stamp=$(date +%Y%m%d-%H%M%S)
docker compose exec -T app python manage.py dumpdata --indent 2 > "backups/{name}-$stamp.json"
echo "Backup written to backups/{name}-$stamp.json"
'''
    rollback = f'''#!/usr/bin/env bash
set -euo pipefail
image="${{1:-{name}:previous}}"
docker compose pull || true
docker compose up -d --no-deps --force-recreate app
echo "Rollback completed. Verify {health_path} before reopening traffic."
'''
    return {
        "project": name,
        "strategy": strategy if strategy in {"rolling", "recreate"} else "rolling",
        "files": {
            "docker-compose.deploy.yml": compose,
            f"k8s/{name}-deployment.yml": deployment,
            f"k8s/{name}-service.yml": service,
            "scripts/backup.sh": backup,
            "scripts/rollback.sh": rollback,
        },
        "checklist": [
            "Create production secrets outside the generated files.",
            "Apply the Kubernetes Secret or .env values through your secret manager.",
            f"Verify the health endpoint {health_path} after deployment.",
            "Keep the previous image available before starting a rollback.",
        ],
    }


def validate_deployment_environment(content):
    lines = [line.strip() for line in (content or "").splitlines() if line.strip() and not line.lstrip().startswith("#")]
    keys = []
    warnings = []
    for line in lines:
        if "=" not in line:
            warnings.append(f"Invalid environment line: {line[:120]}")
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        keys.append(key)
        if not value.strip():
            warnings.append(f"{key} is empty.")
        if any(word in key.upper() for word in ("SECRET", "TOKEN", "PASSWORD", "PRIVATE_KEY")) and value.strip() and not value.strip().startswith("${"):
            warnings.append(f"{key} contains a literal secret; move it to a secret manager.")
    return {"valid": not warnings, "variables": sorted(set(keys)), "warnings": warnings[:50]}
