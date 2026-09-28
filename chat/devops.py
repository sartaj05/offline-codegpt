import re


def _project_language(code, filenames):
    names = " ".join(filenames or []).lower()
    if "requirements.txt" in names or "pyproject.toml" in names or re.search(r"\b(def|import)\s+\w+", code):
        return "python"
    if "package.json" in names or "node_modules" in names or re.search(r"\b(const|let|function)\b", code):
        return "javascript"
    return "generic"


def generate_artifact(kind, code="", filenames=None):
    filenames = filenames or []
    language = _project_language(code, filenames)
    if kind == "dockerfile":
        if language == "python":
            return (
                "FROM python:3.12-slim\n"
                "WORKDIR /app\n"
                "ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1\n"
                "COPY requirements.txt ./\n"
                "RUN pip install --no-cache-dir -r requirements.txt\n"
                "COPY . .\n"
                "EXPOSE 8000\n"
                "CMD [\"python\", \"manage.py\", \"runserver\", \"0.0.0.0:8000\"]\n"
            )
        if language == "javascript":
            return (
                "FROM node:22-alpine\n"
                "WORKDIR /app\n"
                "COPY package*.json ./\n"
                "RUN npm ci --omit=dev\n"
                "COPY . .\n"
                "EXPOSE 3000\n"
                "CMD [\"npm\", \"start\"]\n"
            )
        return "FROM ubuntu:24.04\nWORKDIR /app\nCOPY . .\nCMD [\"sh\"]\n"
    if kind == "compose":
        return (
            "services:\n"
            "  app:\n"
            "    build: .\n"
            "    ports:\n"
            "      - \"8000:8000\"\n"
            "    env_file:\n"
            "      - .env\n"
            "    restart: unless-stopped\n"
        )
    if kind == "github-actions":
        return (
            "name: CI\n\n"
            "on:\n"
            "  push:\n"
            "  pull_request:\n\n"
            "jobs:\n"
            "  test:\n"
            "    runs-on: ubuntu-latest\n"
            "    steps:\n"
            "      - uses: actions/checkout@v4\n"
            "      - name: Set up Python\n"
            "        uses: actions/setup-python@v5\n"
            "        with:\n"
            "          python-version: '3.12'\n"
            "      - run: pip install -r requirements.txt\n"
            "      - run: python manage.py test\n"
        )
    if kind == "gitlab-ci":
        return (
            "image: python:3.12-slim\n\n"
            "stages:\n"
            "  - test\n\n"
            "test:\n"
            "  stage: test\n"
            "  script:\n"
            "    - pip install -r requirements.txt\n"
            "    - python manage.py test\n"
        )
    raise ValueError("Unsupported DevOps artifact type.")


def analyze_logs(log_text):
    lines = [line.strip() for line in (log_text or "").splitlines() if line.strip()]
    findings = []
    for index, line in enumerate(lines, start=1):
        lower = line.lower()
        if "traceback" in lower or "exception" in lower or "error" in lower or "failed" in lower:
            findings.append({"line": index, "severity": "error", "message": line[:500]})
        elif "warning" in lower or "deprecated" in lower:
            findings.append({"line": index, "severity": "warning", "message": line[:500]})
    text = (log_text or "").lower()
    recommendations = []
    if "connection refused" in text or "timeout" in text:
        recommendations.append("Check service health, port bindings, DNS, and network policy.")
    if "permission denied" in text:
        recommendations.append("Check the runtime user, mounted-volume ownership, and file permissions.")
    if "module not found" in text or "no module named" in text:
        recommendations.append("Verify dependency installation and lockfile/package versions.")
    if "out of memory" in text or "memoryerror" in text:
        recommendations.append("Inspect memory limits and reduce worker concurrency or payload size.")
    if not recommendations and findings:
        recommendations.append("Inspect the first error in context, then reproduce it with the same environment variables.")
    return {
        "summary": f"{len(findings)} finding(s) across {len(lines)} log line(s).",
        "findings": findings[:50],
        "recommendations": recommendations,
    }
