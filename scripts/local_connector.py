"""Safe polling connector for Syntax Local AI Hybrid Mode.

The connector makes outbound HTTPS requests only. The server cannot open a
socket on the user's machine. Commands are delivered only after an explicit
approval in the hosted UI, and this client supports a small allowlist of
read-oriented operations.
"""

import argparse
import json
import subprocess
import time
from pathlib import Path

import requests


def api_url(server_url, path):
    return server_url.rstrip("/") + path


def safe_workspace(workspace):
    if not workspace:
        return None
    root = Path(workspace).expanduser().resolve()
    if not root.is_dir():
        raise ValueError("--workspace must be an existing directory")
    return root


def safe_path(root, relative_path):
    if root is None:
        raise ValueError("This operation requires --workspace")
    candidate = (root / str(relative_path)).resolve()
    if candidate != root and root not in candidate.parents:
        raise ValueError("Requested path is outside the configured workspace")
    return candidate


def execute_command(command, workspace, ollama_url):
    operation = command["operation"]
    payload = command.get("payload") or {}
    if operation == "ollama.health":
        response = requests.get(api_url(ollama_url, "/api/tags"), timeout=10)
        response.raise_for_status()
        models = [item.get("name") for item in response.json().get("models", []) if item.get("name")]
        return {"runtime": "ollama", "models": models}
    if operation == "ollama.generate":
        prompt = str(payload.get("prompt", "")).strip()
        code = str(payload.get("code", "")).strip()
        model = str(payload.get("model", "qwen2.5-coder:1.5b")).strip() or "qwen2.5-coder:1.5b"
        combined = prompt + ("\n\nCode:\n" + code if code else "")
        if not combined:
            raise ValueError("The local generation request is empty")
        response = requests.post(api_url(ollama_url, "/api/generate"), json={"model": model, "prompt": combined[:100_000], "stream": False}, timeout=300)
        response.raise_for_status()
        body = response.json()
        return {"model": model, "response": str(body.get("response", ""))[:100_000]}
    if operation == "workspace.list":
        root = workspace
        files = []
        for item in root.rglob("*"):
            if not item.is_file() or any(part in {".git", ".venv", "venv", "node_modules", "__pycache__"} for part in item.parts):
                continue
            files.append(item.relative_to(root).as_posix())
            if len(files) >= 500:
                break
        return {"root": str(root), "files": files, "truncated": len(files) >= 500}
    if operation == "workspace.snapshot":
        root = workspace
        files = []
        ignored = {".git", ".venv", "venv", "node_modules", "__pycache__", "staticfiles", ".pytest_cache"}
        extensions = {".py", ".js", ".ts", ".tsx", ".jsx", ".java", ".cs", ".php", ".sql", ".html", ".css", ".json", ".md", ".txt", ".yaml", ".yml", ".toml", ".ini", ".sh", ".ps1"}
        for item in root.rglob("*"):
            if len(files) >= 100 or not item.is_file() or item.suffix.lower() not in extensions or any(part in ignored for part in item.parts):
                continue
            if item.stat().st_size > 200_000:
                continue
            files.append({"path": item.relative_to(root).as_posix(), "content": item.read_text(encoding="utf-8", errors="replace")})
        git = subprocess.run(["git", "status", "--short"], cwd=str(root), capture_output=True, text=True, timeout=20, check=False)
        return {"root": str(root), "files": files, "git_status": git.stdout[:20_000], "truncated": len(files) >= 100}
    if operation == "file.read":
        path = safe_path(workspace, payload.get("path", ""))
        if not path.is_file():
            raise ValueError("Requested file does not exist")
        if path.stat().st_size > 1_000_000:
            raise ValueError("File reads are limited to 1 MB")
        return {"path": path.relative_to(workspace).as_posix(), "content": path.read_text(encoding="utf-8", errors="replace")}
    if operation == "git.status":
        result = subprocess.run(
            ["git", "status", "--short"],
            cwd=str(workspace),
            capture_output=True,
            text=True,
            timeout=20,
            check=False,
        )
        return {"returncode": result.returncode, "stdout": result.stdout[:20_000], "stderr": result.stderr[:2_000]}
    raise ValueError("Unsupported operation")


def register(session, server_url, pairing_code, name):
    response = session.post(
        api_url(server_url, "/api/connector/register/"),
        json={
            "pairing_code": pairing_code,
            "name": name,
            "capabilities": ["ollama.health", "workspace.list", "file.read", "git.status"],
        },
        timeout=20,
    )
    response.raise_for_status()
    payload = response.json()
    print(json.dumps({"connector": payload.get("connector"), "token": payload.get("token")}, indent=2))
    return payload["token"]


def report_progress(session, server_url, command_id, progress, checkpoint=None):
    response = session.post(
        api_url(server_url, f"/api/connector/progress/{command_id}/"),
        json={"progress": progress, "checkpoint": checkpoint or {}},
        timeout=20,
    )
    response.raise_for_status()


def run(args):
    server_url = args.server_url.rstrip("/")
    workspace = safe_workspace(args.workspace)
    session = requests.Session()
    token = args.token
    if not token:
        if not args.pairing_code:
            raise ValueError("Provide --token or the one-time --pairing-code")
        token = register(session, server_url, args.pairing_code, args.name)
        print("Save the token locally and use --token for future runs.")
    session.headers.update({"Authorization": "Bearer " + token})
    while True:
        response = session.get(api_url(server_url, "/api/connector/poll/"), timeout=30)
        response.raise_for_status()
        commands = response.json().get("commands", [])
        for command in commands:
            try:
                report_progress(session, server_url, command["id"], 5, {"phase": "started", "operation": command["operation"]})
                result = execute_command(command, workspace, args.ollama_url)
                report_progress(session, server_url, command["id"], 95, {"phase": "result_ready"})
                body = {"status": "completed", "result": result}
            except Exception as exc:  # The error is returned to the approving user.
                body = {"status": "failed", "error": str(exc)[:2_000], "result": {}}
            session.post(api_url(server_url, f"/api/connector/result/{command['id']}/"), json=body, timeout=30).raise_for_status()
        if args.once:
            return
        time.sleep(max(2, args.interval))


def main():
    parser = argparse.ArgumentParser(description="Run the safe Syntax Local AI hybrid connector.")
    parser.add_argument("--server-url", required=True, help="HTTPS URL of the hosted Syntax Local AI app")
    parser.add_argument("--pairing-code", help="One-time code generated by the Hybrid Connector panel")
    parser.add_argument("--token", help="Stored connector token")
    parser.add_argument("--name", default="My local connector")
    parser.add_argument("--workspace", help="Allowed local project folder")
    parser.add_argument("--ollama-url", default="http://127.0.0.1:11434")
    parser.add_argument("--interval", type=int, default=5)
    parser.add_argument("--once", action="store_true", help="Poll once and exit")
    args = parser.parse_args()
    run(args)


if __name__ == "__main__":
    main()
