"""Next-generation offline coding workspace planners.

These services accept repository metadata supplied by the local UI or IDE
extension. They intentionally produce reviewable plans and metadata rather
than silently editing files or executing commands.
"""

import hashlib
import json
import os
import re
from collections import defaultdict, deque


def _filename(item):
    return str((item or {}).get("filename") or "").replace("\\", "/").lstrip("./")


def _json_hash(value):
    payload = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def plan_custom_agents(files, agents=None, task=""):
    """Discover repository instructions and select local agent profiles."""
    files = files if isinstance(files, list) else []
    agents = agents if isinstance(agents, list) else []
    instructions = []
    skills = []
    for item in files[:500]:
        name = _filename(item)
        lower = name.lower()
        content = str((item or {}).get("content") or "")
        if lower in {"agents.md", "claude.md", "gemini.md", "review.md", ".github/copilot-instructions.md"}:
            instructions.append({"filename": name, "kind": "repository", "chars": len(content)})
        if "/skills/" in lower and lower.endswith("/skill.md"):
            skills.append({"filename": name, "name": os.path.basename(os.path.dirname(name))})
    profiles = []
    for item in agents[:100]:
        if not isinstance(item, dict) or not str(item.get("name") or "").strip():
            continue
        tools = sorted({str(tool)[:80] for tool in (item.get("tools") or [])})
        profiles.append({
            "name": str(item["name"])[:120],
            "description": str(item.get("description") or "")[:500],
            "tools": tools,
            "skills": sorted({str(skill)[:120] for skill in (item.get("skills") or [])}),
            "include_repository_instructions": bool(item.get("include_repository_instructions", True)),
            "approval_mode": str(item.get("approval_mode") or "confirm-writes"),
        })
    text = str(task or "").lower()
    selected = None
    keywords = {
        "test": "tester", "review": "reviewer", "security": "security", "document": "documentation",
        "frontend": "frontend", "backend": "backend", "database": "database",
    }
    for needle, wanted in keywords.items():
        if needle in text:
            selected = next((item for item in profiles if wanted in item["name"].lower()), None)
            if selected:
                break
    return {
        "profiles": profiles,
        "selected_profile": selected,
        "repository_instructions": instructions,
        "skills": skills,
        "precedence": ["user", "repository", "path-specific", "agent-skill", "task"],
        "approval_required_for": ["file-write", "shell", "git-write", "dependency-install"],
        "offline_only": True,
        "task_fingerprint": _json_hash({"task": task, "files": [_filename(item) for item in files]}),
    }


def plan_ide_integration(files, editor="vscode", runtime="local"):
    """Return a local IDE integration manifest without installing extensions."""
    files = files if isinstance(files, list) else []
    extensions = sorted({os.path.splitext(_filename(item))[1].lower() for item in files if os.path.splitext(_filename(item))[1]})
    languages = sorted({
        {".py": "python", ".js": "javascript", ".ts": "typescript", ".tsx": "typescript",
         ".go": "go", ".rs": "rust", ".java": "java", ".php": "php"}.get(ext, "text")
        for ext in extensions
    })
    editor = str(editor or "vscode").lower()
    return {
        "editor": editor if editor in {"vscode", "jetbrains"} else "vscode",
        "runtime": runtime if runtime in {"local", "ollama", "lmstudio", "llamacpp"} else "local",
        "languages": languages,
        "workspace_extensions": extensions,
        "commands": [
            "offlineCodeGPT.askSelection", "offlineCodeGPT.explainSymbol",
            "offlineCodeGPT.generateTests", "offlineCodeGPT.reviewPatch",
            "offlineCodeGPT.runApprovedTask",
        ],
        "capabilities": ["inline-chat", "diagnostics", "symbol-context", "reviewed-patches", "test-runner", "local-model-picker"],
        "api_contract": {
            "ask": "/api/cli/ask/",
            "coding": "/api/coding/",
            "streaming": True,
            "authorization": "same-device-session",
        },
        "permission_prompts": ["write files", "run tests", "run shell", "apply Git changes"],
        "network_policy": "localhost-only",
        "offline_only": True,
    }
