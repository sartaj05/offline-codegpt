"""Safe polling connector for Syntax Local AI Hybrid Mode.

The connector makes outbound HTTPS requests only. The server cannot open a
socket on the user's machine. Commands are delivered only after an explicit
approval in the hosted UI, and this client supports a small allowlist of
read-oriented operations.
"""

import argparse
import difflib
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
        started = time.perf_counter()
        response = requests.get(api_url(ollama_url, "/api/tags"), timeout=10)
        response.raise_for_status()
        models = [item.get("name") for item in response.json().get("models", []) if item.get("name")]
        return {"runtime": "ollama", "models": models, "latency_ms": round((time.perf_counter() - started) * 1000)}
    if operation == "ollama.generate":
        prompt = str(payload.get("prompt", "")).strip()
        code = str(payload.get("code", "")).strip()
        model = str(payload.get("model", "qwen2.5-coder:1.5b")).strip() or "qwen2.5-coder:1.5b"
        combined = prompt + ("\n\nCode:\n" + code if code else "")
        if not combined:
            raise ValueError("The local generation request is empty")
        started = time.perf_counter()
        response = requests.post(api_url(ollama_url, "/api/generate"), json={"model": model, "prompt": combined[:100_000], "stream": False}, timeout=300)
        response.raise_for_status()
        body = response.json()
        return {"model": model, "response": str(body.get("response", ""))[:100_000], "latency_ms": round((time.perf_counter() - started) * 1000)}
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
    if operation == "patch.preview":
        path = safe_path(workspace, payload.get("path", ""))
        if not path.is_file():
            raise ValueError("Patch target does not exist")
        original = path.read_text(encoding="utf-8", errors="replace")
        updated = str(payload.get("new_content", ""))
        if len(updated.encode("utf-8")) > 1_000_000:
            raise ValueError("Patch content is limited to 1 MB")
        diff = "".join(difflib.unified_diff(
            original.splitlines(keepends=True),
            updated.splitlines(keepends=True),
            fromfile=str(payload.get("path", "file")) + " (current)",
            tofile=str(payload.get("path", "file")) + " (proposed)",
            n=3,
        ))
        return {"path": path.relative_to(workspace).as_posix(), "changed": original != updated, "original": original, "updated": updated, "diff": diff}
    if operation == "patch.apply":
        path = safe_path(workspace, payload.get("path", ""))
        if not path.is_file():
            raise ValueError("Patch target does not exist")
        original = path.read_text(encoding="utf-8", errors="replace")
        expected = payload.get("expected_content")
        if expected is not None and original != str(expected):
            raise ValueError("Patch target changed since it was previewed")
        updated = str(payload.get("new_content", ""))
        if len(updated.encode("utf-8")) > 1_000_000:
            raise ValueError("Patch content is limited to 1 MB")
        path.write_text(updated, encoding="utf-8")
        return {"path": path.relative_to(workspace).as_posix(), "original": original, "updated": updated, "changed": original != updated}
    if operation == "patch.undo":
        path = safe_path(workspace, payload.get("path", ""))
        if not path.is_file():
            raise ValueError("Patch target does not exist")
        current = path.read_text(encoding="utf-8", errors="replace")
        expected = str(payload.get("expected_content", ""))
        if expected and current != expected:
            raise ValueError("Patch target changed after it was applied")
        original = str(payload.get("original_content", ""))
        if len(original.encode("utf-8")) > 1_000_000:
            raise ValueError("Patch content is limited to 1 MB")
        path.write_text(original, encoding="utf-8")
        return {"path": path.relative_to(workspace).as_posix(), "restored": True, "content": original}
    raise ValueError("Unsupported operation")


def register(session, server_url, pairing_code, name):
    response = session.post(
        api_url(server_url, "/api/connector/register/"),
        json={
            "pairing_code": pairing_code,
            "name": name,
            "capabilities": ["ollama.health", "workspace.list", "file.read", "git.status", "patch.preview", "patch.apply", "patch.undo"],
        },
        timeout=20,
    )
    response.raise_for_status()
    payload = response.json()
    print(json.dumps({"connector": payload.get("connector"), "token": payload.get("token")}, indent=2))
    return payload["token"]


def report_progress(session, server_url, command_id, progress, checkpoint=None):
    try:
        response = session.post(
            api_url(server_url, f"/api/connector/progress/{command_id}/"),
            json={"progress": progress, "checkpoint": checkpoint or {}},
            timeout=20,
        )
        response.raise_for_status()
        return True
    except requests.RequestException:
        return False


def load_queue(queue_file):
    if not queue_file or not queue_file.exists():
        return []
    try:
        value = json.loads(queue_file.read_text(encoding="utf-8"))
    except (OSError, ValueError, json.JSONDecodeError):
        return []
    return value if isinstance(value, list) else []


def save_queue(queue_file, entries):
    queue_file.parent.mkdir(parents=True, exist_ok=True)
    temporary = queue_file.with_suffix(queue_file.suffix + ".tmp")
    temporary.write_text(json.dumps(entries[-500:], indent=2), encoding="utf-8")
    temporary.replace(queue_file)


def queue_result(queue_file, command_id, body):
    entries = load_queue(queue_file)
    entry = {"command_id": str(command_id), "body": body}
    entries = [item for item in entries if item.get("command_id") != str(command_id)]
    entries.append(entry)
    save_queue(queue_file, entries)


def flush_queue(session, server_url, queue_file):
    entries = load_queue(queue_file)
    remaining = []
    for entry in entries:
        try:
            response = session.post(
                api_url(server_url, f"/api/connector/result/{entry['command_id']}/"),
                json=entry.get("body", {}),
                timeout=30,
            )
            response.raise_for_status()
        except (KeyError, requests.RequestException):
            remaining.append(entry)
            if isinstance(entry, dict) and entry.get("command_id"):
                remaining.extend(item for item in entries[entries.index(entry) + 1:] if item not in remaining)
            break
    if remaining:
        save_queue(queue_file, remaining)
    elif queue_file.exists():
        queue_file.unlink()
    return len(entries) - len(remaining)


def post_result_or_queue(session, server_url, queue_file, command_id, body):
    try:
        response = session.post(
            api_url(server_url, f"/api/connector/result/{command_id}/"),
            json=body,
            timeout=30,
        )
        response.raise_for_status()
        return True
    except requests.ConnectionError:
        queue_result(queue_file, command_id, body)
        return False
    except requests.Timeout:
        queue_result(queue_file, command_id, body)
        return False


def run(args):
    server_url = args.server_url.rstrip("/")
    workspace = safe_workspace(args.workspace)
    queue_file = Path(args.queue_file).expanduser().resolve()
    session = requests.Session()
    token = args.token
    if not token:
        if not args.pairing_code:
            raise ValueError("Provide --token or the one-time --pairing-code")
        token = register(session, server_url, args.pairing_code, args.name)
        print("Save the token locally and use --token for future runs.")
    session.headers.update({"Authorization": "Bearer " + token})
    while True:
        flush_queue(session, server_url, queue_file)
        try:
            response = session.get(api_url(server_url, "/api/connector/poll/"), timeout=30)
            response.raise_for_status()
        except requests.RequestException as exc:
            if args.once:
                print(f"Connector offline; queued results remain in {queue_file}: {exc}")
                return
            time.sleep(max(2, args.interval))
            continue
        commands = response.json().get("commands", [])
        for command in commands:
            try:
                report_progress(session, server_url, command["id"], 5, {"phase": "started", "operation": command["operation"]})
                result = execute_command(command, workspace, args.ollama_url)
                report_progress(session, server_url, command["id"], 95, {"phase": "result_ready"})
                body = {"status": "completed", "result": result}
            except Exception as exc:  # The error is returned to the approving user.
                body = {"status": "failed", "error": str(exc)[:2_000], "result": {}}
            post_result_or_queue(session, server_url, queue_file, command["id"], body)
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
    parser.add_argument("--queue-file", default=".syntax-local-connector-queue.json", help="Local durable result queue file")
    parser.add_argument("--interval", type=int, default=5)
    parser.add_argument("--once", action="store_true", help="Poll once and exit")
    args = parser.parse_args()
    run(args)


if __name__ == "__main__":
    main()
