"""Next-generation offline coding workspace planners.

These services accept repository metadata supplied by the local UI or IDE
extension. They intentionally produce reviewable plans and metadata rather
than silently editing files or executing commands.
"""

import hashlib
import json
import os
import re
from collections import Counter, defaultdict, deque


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


def inline_completion(filename, code, prefix="", suffix="", language="auto", limit=8):
    """Generate safe, local completion candidates from the current buffer."""
    code = str(code or "")
    prefix = str(prefix or "")[-1000:]
    suffix = str(suffix or "")[:1000]
    language = str(language or "auto").lower()
    if language == "auto":
        language = {".py": "python", ".js": "javascript", ".ts": "typescript", ".tsx": "typescript"}.get(os.path.splitext(filename or "")[1].lower(), "text")
    identifiers = re.findall(r"\b[A-Za-z_$][A-Za-z0-9_$]{2,}\b", code)
    identifiers = list(dict.fromkeys(identifiers))
    current = re.search(r"[A-Za-z_$][A-Za-z0-9_$]*$", prefix)
    fragment = current.group(0) if current else ""
    candidates = [item for item in identifiers if item != fragment and (not fragment or item.lower().startswith(fragment.lower()))]
    definitions = re.findall(r"(?:def|function|class|func|fn)\s+([A-Za-z_$][A-Za-z0-9_$]*)", code)
    candidates = list(dict.fromkeys(definitions + candidates))
    items = []
    for item in candidates[: max(1, min(int(limit or 8), 20))]:
        replacement = item[len(fragment):] if fragment else item
        items.append({"label": item, "insert_text": replacement, "kind": "symbol", "source": "local-buffer"})
    if not items and language == "python" and prefix.rstrip().endswith("def "):
        items.append({"label": "new_function", "insert_text": "new_function():\n    pass", "kind": "snippet", "source": "local-snippet"})
    return {
        "filename": filename or "buffer",
        "language": language,
        "items": items,
        "is_incomplete": len(candidates) > len(items),
        "trigger": "manual-or-debounced",
        "privacy": {"source_sent_remote": False, "cache": "memory-only"},
        "offline_only": True,
    }


def plan_background_tasks(tasks, resume_state=None, max_workers=1):
    """Normalize long-running local coding work into resumable task records."""
    tasks = tasks if isinstance(tasks, list) else []
    resume_state = resume_state if isinstance(resume_state, dict) else {}
    try:
        max_workers = max(1, min(int(max_workers), 8))
    except (TypeError, ValueError):
        max_workers = 1
    normalized = []
    for index, item in enumerate(tasks[:100]):
        if not isinstance(item, dict):
            continue
        task_id = str(item.get("id") or f"task-{index + 1}")[:100]
        steps = [str(step)[:300] for step in (item.get("steps") or [])][:50]
        saved = resume_state.get(task_id) if isinstance(resume_state.get(task_id), dict) else {}
        step_index = max(0, min(int(saved.get("step_index", 0) or 0), len(steps)))
        status = str(saved.get("status") or item.get("status") or "queued")
        if status not in {"queued", "running", "paused", "failed", "completed", "cancelled"}:
            status = "queued"
        normalized.append({
            "id": task_id,
            "title": str(item.get("title") or task_id)[:200],
            "steps": steps,
            "step_index": step_index,
            "next_step": steps[step_index] if step_index < len(steps) else None,
            "status": status,
            "checkpoint": _json_hash({"id": task_id, "step_index": step_index, "steps": steps})[:16],
            "approval_required": bool(item.get("approval_required", True)),
        })
    running = [item["id"] for item in normalized if item["status"] == "running"]
    return {
        "tasks": normalized,
        "queue": [item["id"] for item in normalized if item["status"] == "queued"],
        "running": running[:max_workers],
        "deferred": running[max_workers:],
        "max_workers": max_workers,
        "recovery": {"checkpointed": True, "resume_after_restart": True, "requires_review_on_failure": True},
        "execution": "approval-gated-local-worker",
        "offline_only": True,
    }


def plan_agent_orchestration(goal, agents, tasks):
    """Build dependency-aware specialist-agent waves without starting agents."""
    agents = agents if isinstance(agents, list) else []
    tasks = tasks if isinstance(tasks, list) else []
    allowed_agents = {str(item.get("name")): item for item in agents if isinstance(item, dict) and item.get("name")}
    rows = {}
    for index, item in enumerate(tasks[:100]):
        if not isinstance(item, dict):
            continue
        task_id = str(item.get("id") or f"step-{index + 1}")[:100]
        depends = [str(dep)[:100] for dep in (item.get("depends_on") or []) if str(dep)[:100] != task_id]
        agent_name = str(item.get("agent") or "general")[:100]
        rows[task_id] = {
            "id": task_id,
            "title": str(item.get("title") or task_id)[:200],
            "agent": agent_name,
            "depends_on": depends,
            "known_agent": agent_name in allowed_agents,
            "approval_required": True,
        }
    indegree = {task_id: sum(1 for dep in row["depends_on"] if dep in rows) for task_id, row in rows.items()}
    outgoing = defaultdict(list)
    for task_id, row in rows.items():
        for dep in row["depends_on"]:
            if dep in rows:
                outgoing[dep].append(task_id)
    waves = []
    ready = sorted(task_id for task_id, degree in indegree.items() if degree == 0)
    processed = set()
    while ready:
        wave = list(ready)
        waves.append([rows[task_id] for task_id in wave])
        ready = []
        for task_id in wave:
            processed.add(task_id)
            for child in outgoing[task_id]:
                indegree[child] -= 1
                if indegree[child] == 0:
                    ready.append(child)
        ready.sort()
    cycle = sorted(set(rows) - processed)
    return {
        "goal": str(goal or "")[:1000],
        "agents": [{"name": str(item.get("name")), "role": str(item.get("role") or "general"), "tools": item.get("tools") or []} for item in agents if isinstance(item, dict) and item.get("name")],
        "waves": waves,
        "cycle": cycle,
        "valid": not cycle and bool(rows),
        "merge_policy": "review-each-agent-output-before-integration",
        "approval_required": True,
        "offline_only": True,
    }


def prepare_task_replay(record, current=None):
    """Create a local replay manifest from a prior coding-task record."""
    record = record if isinstance(record, dict) else {}
    current = current if isinstance(current, dict) else {}
    files = record.get("files") if isinstance(record.get("files"), list) else []
    tool_calls = record.get("tool_calls") if isinstance(record.get("tool_calls"), list) else []
    file_hashes = [{"filename": _filename(item), "sha256": _json_hash(str((item or {}).get("content") or ""))} for item in files if isinstance(item, dict)]
    tool_hashes = [{"name": str((item or {}).get("name") or "")[:120], "input_hash": _json_hash((item or {}).get("arguments") or {})[:16]} for item in tool_calls if isinstance(item, dict)]
    manifest = {
        "schema": "offline-coding-replay-v1",
        "prompt_hash": _json_hash(record.get("prompt") or ""),
        "files": file_hashes,
        "tool_calls": tool_hashes,
        "model": str(record.get("model") or "local-default")[:120],
        "runtime": str(record.get("runtime") or "local")[:80],
        "settings_hash": _json_hash(record.get("settings") or {}),
    }
    mismatches = []
    if current:
        if current.get("model") and current.get("model") != manifest["model"]:
            mismatches.append("model")
        if current.get("runtime") and current.get("runtime") != manifest["runtime"]:
            mismatches.append("runtime")
        current_files = {_filename(item): _json_hash(str((item or {}).get("content") or "")) for item in (current.get("files") or []) if isinstance(item, dict)}
        for item in file_hashes:
            if item["filename"] in current_files and current_files[item["filename"]] != item["sha256"]:
                mismatches.append(f"file:{item['filename']}")
    return {
        "manifest": manifest,
        "replay_id": _json_hash(manifest)[:20],
        "mismatches": sorted(set(mismatches)),
        "replayable": not mismatches and bool(manifest["prompt_hash"]),
        "redaction": {"prompt_contents_stored": False, "tool_arguments_stored": False, "secrets_removed": True},
        "workflow": ["Load exact local files", "Confirm model/runtime", "Replay read-only steps", "Approve writes", "Compare tests and diff"],
        "offline_only": True,
    }


def assess_change_risk(files, changed_files=None, relations=None, tests=None, security_paths=None):
    """Score local patch risk and explain the affected-file blast radius."""
    files = files if isinstance(files, list) else []
    changed = sorted({str(item).replace("\\", "/").lstrip("./") for item in (changed_files or [])})
    relations = relations if isinstance(relations, dict) else {}
    tests = [str(item).replace("\\", "/").lstrip("./") for item in (tests or [])]
    security_paths = [str(item).lower().replace("\\", "/") for item in (security_paths or ["auth", "security", "secret", ".env", "permission"])]
    file_names = {_filename(item) for item in files if isinstance(item, dict)}
    affected = set(changed)
    frontier = deque(changed)
    while frontier and len(affected) < 500:
        source = frontier.popleft()
        for dependent in relations.get(source, []) if isinstance(relations.get(source), list) else []:
            dependent = str(dependent).replace("\\", "/").lstrip("./")
            if dependent not in affected:
                affected.add(dependent)
                frontier.append(dependent)
    findings = []
    score = min(25, len(changed) * 4) + min(25, max(0, len(affected) - len(changed)) * 3)
    for filename in changed:
        lower = filename.lower()
        if any(token in lower for token in security_paths):
            score += 20
            findings.append({"severity": "high", "kind": "security-sensitive", "filename": filename})
        if re.search(r"(^|/)(migrations?|schema)(/|[._-])", lower):
            score += 15
            findings.append({"severity": "high", "kind": "schema-change", "filename": filename})
        if lower.endswith((".json", ".yaml", ".yml")) and ("api" in lower or "openapi" in lower):
            score += 10
            findings.append({"severity": "medium", "kind": "contract-change", "filename": filename})
    if not tests:
        score += 15
        findings.append({"severity": "medium", "kind": "no-test-evidence", "message": "No affected test list was supplied."})
    score = min(100, score)
    level = "low" if score < 25 else "medium" if score < 50 else "high" if score < 75 else "critical"
    return {
        "score": score,
        "level": level,
        "changed_files": changed,
        "affected_files": sorted(affected | (file_names & affected)),
        "blast_radius": max(0, len(affected) - len(changed)),
        "findings": findings,
        "test_requirements": sorted(set(tests)) or ["Run the affected test suite before merge."],
        "approval_required": level in {"high", "critical"} or any(
            item.get("kind") in {"security-sensitive", "schema-change"} for item in findings
        ),
        "offline_only": True,
    }


def analyze_offline_dependencies(files, catalog=None):
    """Inspect local manifests against an imported package catalog only."""
    files = files if isinstance(files, list) else []
    catalog = catalog if isinstance(catalog, dict) else {}
    packages = []
    for item in files[:500]:
        name = _filename(item)
        content = str((item or {}).get("content") or "")
        base = os.path.basename(name).lower()
        if base in {"requirements.txt", "requirements-dev.txt"}:
            for line in content.splitlines():
                match = re.match(r"^\s*([A-Za-z0-9_.-]+)\s*(==|~=|>=|<=|>|<)?\s*([^;\s#]+)?", line)
                if match and not line.lstrip().startswith("#"):
                    packages.append({"name": match.group(1), "constraint": (match.group(2) or "") + (match.group(3) or ""), "manager": "pip", "manifest": name})
        elif base == "package.json":
            try:
                data = json.loads(content)
                for section in ("dependencies", "devDependencies", "peerDependencies"):
                    for package, constraint in (data.get(section) or {}).items():
                        packages.append({"name": package, "constraint": str(constraint), "manager": "npm", "manifest": name, "section": section})
            except (TypeError, ValueError, json.JSONDecodeError):
                pass
        elif base == "cargo.toml":
            in_deps = False
            for line in content.splitlines():
                if line.strip().startswith("["):
                    in_deps = line.strip() in {"[dependencies]", "[dev-dependencies]"}
                elif in_deps and "=" in line:
                    package, constraint = line.split("=", 1)
                    packages.append({"name": package.strip(), "constraint": constraint.strip().strip('"'), "manager": "cargo", "manifest": name})
    available, missing, advisories, license_flags = [], [], [], []
    for package in packages:
        entry = catalog.get(package["name"]) or catalog.get(f"{package['name']}@{package['constraint']}")
        if not isinstance(entry, dict):
            missing.append(package)
            continue
        result = {**package, "available_version": str(entry.get("version") or ""), "license": str(entry.get("license") or "UNKNOWN")}
        available.append(result)
        for advisory in entry.get("advisories") or []:
            advisories.append({"package": package["name"], **(advisory if isinstance(advisory, dict) else {"id": str(advisory)})})
        if result["license"].upper() in {"GPL-3.0", "AGPL-3.0", "UNKNOWN"}:
            license_flags.append({"package": package["name"], "license": result["license"]})
    return {
        "packages": packages,
        "available": available,
        "missing_from_catalog": missing,
        "advisories": advisories,
        "license_flags": license_flags,
        "catalog_source": "imported-local-catalog",
        "network_used": False,
        "approval_required_for_install": True,
        "offline_only": True,
    }


def plan_dev_environment(files, hardware=None, commands=None):
    """Build a safe reproducible-environment plan from local repository files."""
    files = files if isinstance(files, list) else []
    hardware = hardware if isinstance(hardware, dict) else {}
    supplied_commands = [str(item)[:300] for item in (commands or []) if str(item).strip()][:30]
    names = {_filename(item) for item in files if isinstance(item, dict)}
    lower_names = {name.lower() for name in names}
    ecosystems = []
    if any(name.endswith(("requirements.txt", "pyproject.toml", "poetry.lock")) for name in lower_names):
        ecosystems.append("python")
    if any(name.endswith(("package.json", "package-lock.json", "pnpm-lock.yaml", "yarn.lock")) for name in lower_names):
        ecosystems.append("node")
    if any(name.endswith(("cargo.toml", "cargo.lock")) for name in lower_names):
        ecosystems.append("rust")
    if any(name.endswith(("go.mod", "go.sum")) for name in lower_names):
        ecosystems.append("go")
    if any(name.endswith(("dockerfile", "docker-compose.yml", "docker-compose.yaml")) for name in lower_names):
        ecosystems.append("container")
    setup = []
    if "python" in ecosystems:
        setup.append("python -m venv .venv")
        setup.append("python -m pip install --requirement requirements.txt")
    if "node" in ecosystems:
        setup.append("npm ci")
    if "rust" in ecosystems:
        setup.append("cargo build --locked")
    if "go" in ecosystems:
        setup.append("go mod download")
    if "container" in ecosystems or ".devcontainer/devcontainer.json" in lower_names:
        setup.append("docker compose build")
    env_names = set()
    for item in files:
        content = str((item or {}).get("content") or "")
        env_names.update(re.findall(r"\b[A-Z][A-Z0-9_]{2,}\b", content))
    secret_like = sorted(name for name in env_names if any(token in name.lower() for token in ("key", "token", "secret", "password")))
    return {
        "ecosystems": sorted(set(ecosystems)),
        "detected_files": sorted(names),
        "setup_commands": supplied_commands or setup,
        "required_lockfiles": sorted(name for name in names if name.lower().endswith((".lock", "-lock.json", "lock.yaml", "lock.yml"))),
        "environment_variables": sorted(env_names - set(secret_like)),
        "secret_variables_redacted": secret_like,
        "hardware": {key: str(value)[:120] for key, value in hardware.items() if not any(token in key.lower() for token in ("secret", "token", "password", "key"))},
        "execution": "preview-only-until-approved",
        "offline_only": True,
    }


def analyze_git_archaeology(commits, blame=None, changed_files=None):
    """Summarize local Git history, ownership, and change hotspots."""
    commits = commits if isinstance(commits, list) else []
    blame = blame if isinstance(blame, list) else []
    changed = {str(item).replace("\\", "/").lstrip("./") for item in (changed_files or [])}
    file_counts = Counter()
    file_messages = defaultdict(list)
    authors = Counter()
    for commit in commits[:1000]:
        if not isinstance(commit, dict):
            continue
        author = str(commit.get("author") or "unknown")[:120]
        authors[author] += 1
        message = str(commit.get("message") or "")[:300]
        for filename in commit.get("files") or []:
            filename = str(filename).replace("\\", "/").lstrip("./")
            file_counts[filename] += 1
            if message:
                file_messages[filename].append(message)
    ownership = defaultdict(Counter)
    for row in blame[:5000]:
        if not isinstance(row, dict):
            continue
        filename = str(row.get("filename") or "").replace("\\", "/").lstrip("./")
        ownership[filename][str(row.get("author") or "unknown")[:120]] += 1
    hotspots = [{"filename": filename, "changes": count, "recent_messages": file_messages[filename][-5:]} for filename, count in file_counts.most_common(50)]
    explanations = []
    for filename in sorted(changed):
        messages = file_messages.get(filename) or []
        reason = messages[-1] if messages else "No local commit message was supplied for this file."
        explanations.append({
            "filename": filename,
            "likely_reason": reason,
            "owners": [{"author": author, "lines": count} for author, count in ownership.get(filename, {}).most_common(5)],
            "history_count": file_counts.get(filename, 0),
        })
    return {
        "hotspots": hotspots,
        "changed_file_explanations": explanations,
        "top_authors": [{"author": author, "commits": count} for author, count in authors.most_common(20)],
        "commit_count": len(commits),
        "blame_rows": len(blame),
        "remote_provider_used": False,
        "offline_only": True,
    }
