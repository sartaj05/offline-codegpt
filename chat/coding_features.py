"""Offline coding-workspace services.

These helpers deliberately use local parsing and subprocess contracts only. They
do not send source code to a remote service, which keeps the coding workspace
usable while the app is in offline mode.
"""

import ast
import difflib
import fnmatch
import hashlib
import json
import os
import re
import shlex
import shutil
import time
from collections import Counter, defaultdict


LANGUAGE_EXTENSIONS = {
    ".py": "python",
    ".js": "javascript",
    ".jsx": "javascript",
    ".ts": "typescript",
    ".tsx": "typescript",
    ".go": "go",
    ".rs": "rust",
    ".java": "java",
    ".cs": "csharp",
    ".php": "php",
    ".rb": "ruby",
}


def _language(filename, language="auto"):
    if language and language != "auto":
        return language.lower()
    return LANGUAGE_EXTENSIONS.get(os.path.splitext(filename or "")[1].lower(), "text")


def _line(code, offset):
    return code[:offset].count("\n") + 1


def _symbol_rows(filename, code, language):
    rows = []
    if language == "python":
        try:
            tree = ast.parse(code or "", filename=filename or "buffer.py")
        except SyntaxError as exc:
            return [], [{"severity": "error", "message": exc.msg, "line": exc.lineno or 1, "source": "python"}]
        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                rows.append({
                    "name": node.name,
                    "kind": "class" if isinstance(node, ast.ClassDef) else "function",
                    "line": node.lineno,
                    "end_line": getattr(node, "end_lineno", node.lineno),
                    "signature": ast.unparse(node).splitlines()[0][:300] if hasattr(ast, "unparse") else node.name,
                })
        return sorted(rows, key=lambda item: (item["line"], item["name"])), []

    diagnostics = []
    pattern = re.compile(r"^\s*(?:(?:export\s+)?(?:async\s+)?function|(?:export\s+)?class|(?:func|fn)\s+|(?:public\s+)?(?:class|void|int|string)\s+)([A-Za-z_$][\w$]*)", re.MULTILINE)
    for match in pattern.finditer(code or ""):
        prefix = match.group(0).strip().lower()
        kind = "class" if "class" in prefix else "function"
        rows.append({"name": match.group(1), "kind": kind, "line": _line(code, match.start()), "end_line": _line(code, match.end()), "signature": match.group(0).strip()[:300]})
    if language in {"javascript", "typescript"} and code.count("{") != code.count("}"):
        diagnostics.append({"severity": "error", "message": "Unbalanced braces.", "line": max(1, len(code.splitlines())), "source": "local-parser"})
    return rows, diagnostics


def lsp_analyze(filename, code, language="auto", operation="diagnostics", symbol=""):
    """Return an LSP-shaped response using local AST/regex parsing.

    A full language server can be plugged in later without changing the API.
    """
    language = _language(filename, language)
    symbols, diagnostics = _symbol_rows(filename, code or "", language)
    names = [item["name"] for item in symbols]
    definitions = [item for item in symbols if not symbol or item["name"] == symbol]
    references = []
    if symbol:
        for match in re.finditer(r"\b" + re.escape(symbol) + r"\b", code or ""):
            references.append({"name": symbol, "line": _line(code, match.start()), "character": match.start() - (code.rfind("\n", 0, match.start()) + 1)})
    return {
        "protocol": "offline-lsp-v1",
        "filename": filename or "buffer",
        "language": language,
        "operation": operation,
        "diagnostics": diagnostics,
        "symbols": symbols,
        "definitions": definitions if operation in {"definition", "all"} else [],
        "references": references if operation in {"references", "all"} else [],
        "completion_items": sorted(set(names))[:100] if operation in {"completion", "all"} else [],
        "capabilities": ["diagnostics", "document-symbols", "definition", "references", "completion"],
        "backend": "local-ast-regex",
    }


def lsp_adapter_catalog():
    """Describe optional local language-server adapters without downloading anything."""
    adapters = [
        {"id": "pyright", "language": "python", "command": "pyright-langserver", "install_hint": "Install Pyright locally, then restart the app."},
        {"id": "typescript", "language": "typescript", "command": "typescript-language-server", "install_hint": "Install typescript-language-server locally."},
        {"id": "gopls", "language": "go", "command": "gopls", "install_hint": "Install gopls locally."},
        {"id": "rust-analyzer", "language": "rust", "command": "rust-analyzer", "install_hint": "Install rust-analyzer locally."},
        {"id": "jdtls", "language": "java", "command": "jdtls", "install_hint": "Install Eclipse JDT Language Server locally."},
        {"id": "intelephense", "language": "php", "command": "intelephense", "install_hint": "Install Intelephense locally."},
    ]
    for adapter in adapters:
        executable = shutil.which(adapter["command"])
        adapter.update({"available": bool(executable), "executable": executable or "", "transport": "stdio", "offline_only": True})
    return {
        "protocol": "lsp",
        "adapters": adapters,
        "fallback": "local-ast-regex",
        "capabilities": ["diagnostics", "completion", "definition", "references", "rename", "document-symbols"],
        "network_policy": "blocked",
    }


def discover_repository_instructions(files):
    records = []
    for item in (files or [])[:500]:
        filename = str(item.get("filename") or "").replace("\\", "/").lstrip("./")
        content = str(item.get("content") or "")
        lower = filename.lower()
        kind = ""
        scope = "repository"
        if lower == "agents.md":
            kind = "agent-instructions"
        elif lower == ".github/copilot-instructions.md":
            kind = "copilot-instructions"
        elif lower.endswith(".instructions.md"):
            kind = "path-instructions"
            scope = filename.rsplit("/", 1)[0] if "/" in filename else "repository"
        elif "/skills/" in lower and lower.endswith("/skill.md"):
            kind = "reusable-skill"
            scope = filename.split("/skills/", 1)[0] or "repository"
        elif lower in {"claude.md", "gemini.md", "review.md"}:
            kind = "agent-instructions"
        if not kind:
            continue
        headings = [line.strip().lstrip("# ")[:160] for line in content.splitlines() if line.strip().startswith("#")][:10]
        records.append({"filename": filename, "kind": kind, "scope": scope, "headings": headings, "chars": len(content), "content": content[:12000]})
    return {
        "instructions": records,
        "always_on": [item["filename"] for item in records if item["kind"] in {"agent-instructions", "copilot-instructions"}],
        "path_specific": [item["filename"] for item in records if item["kind"] == "path-instructions"],
        "skills": [item["filename"] for item in records if item["kind"] == "reusable-skill"],
        "precedence": ["user", "repository", "path-specific", "task-skill"],
        "offline_only": True,
    }


def analyze_test_impact(files, changed_files=None):
    normalized = []
    for item in (files or [])[:500]:
        filename = str(item.get("filename") or "").replace("\\", "/").lstrip("./")
        content = str(item.get("content") or "")
        symbols = re.findall(r"^\s*(?:async\s+def|def|class|function|export\s+function)\s+([A-Za-z_$][\w$]*)", content, re.MULTILINE)
        normalized.append({"filename": filename, "content": content, "symbols": sorted(set(symbols))})
    changed = {str(item).replace("\\", "/").lstrip("./") for item in (changed_files or [])}
    changed_items = [item for item in normalized if item["filename"] in changed or not changed]
    changed_symbols = sorted({symbol for item in changed_items for symbol in item["symbols"]})
    test_items = [item for item in normalized if re.search(r"(^|/)(test|tests|spec|specs)(/|_|\.)", item["filename"].lower()) or re.search(r"\b(?:test|describe|it)\s*\(", item["content"])]
    impacted = []
    for item in test_items:
        hits = [symbol for symbol in changed_symbols if re.search(r"\b" + re.escape(symbol) + r"\b", item["content"])]
        if hits:
            impacted.append({"filename": item["filename"], "reason": "References changed symbol(s).", "symbols": hits})
    return {
        "changed_files": sorted(changed),
        "changed_symbols": changed_symbols,
        "impacted_tests": impacted,
        "skipped_tests": [{"filename": item["filename"], "reason": "No changed symbol reference detected."} for item in test_items if item["filename"] not in {row["filename"] for row in impacted}],
        "unknown_tests": not bool(test_items),
        "strategy": "symbol-reference plus test-path matching",
        "approval_required": True,
        "offline_only": True,
    }


def plan_git_bisect(failing_test, known_good="", known_bad="HEAD", commits=None):
    commits = [str(item).strip()[:80] for item in (commits or []) if str(item).strip()][:200]
    safe_test = " ".join(shlex.split(failing_test or "python -m pytest"))
    return {
        "assistant": "offline-git-bisect",
        "known_good": known_good or "<last-known-good>",
        "known_bad": known_bad or "HEAD",
        "failing_test": safe_test,
        "candidate_commits": commits,
        "commands": [
            f"git bisect start {known_bad or 'HEAD'} {known_good or '<last-known-good>'}",
            f"git bisect run {safe_test}",
            "git bisect reset",
        ],
        "workflow": ["Confirm a clean worktree.", "Run the failing test at each candidate.", "Inspect the first bad commit.", "Prepare a reviewed repair patch."],
        "destructive": False,
        "approval_required": True,
        "offline_only": True,
    }


def incident_to_fix(logs="", traces="", metrics="", title="Incident repair"):
    from .incident import analyze_incident

    analysis = analyze_incident(logs, traces, metrics)
    locations = []
    for line in (traces or "").splitlines():
        match = re.search(r"(?:File|at)\s+[\"']?([^\"'\s:]+)[\"']?(?:,?\s+line\s+|:\s*)(\d+)", line, re.IGNORECASE)
        if match:
            locations.append({"filename": match.group(1).replace("\\", "/"), "line": int(match.group(2)), "evidence": line.strip()[:500]})
    goal = (analysis["errors"][0] if analysis["errors"] else "Investigate the reported local incident.")[:1000]
    plan = issue_to_pr_plan(title, goal, [item["filename"] for item in locations], "Run the smallest reproducing test, then the regression suite")
    return {
        "analysis": analysis,
        "locations": locations[:50],
        "root_cause_candidates": analysis["suspected_causes"],
        "fix_workflow": plan,
        "requires_regression_test": True,
        "offline_only": True,
    }


def analyze_migration_safety(old_schema=None, new_schema=None, migration_sql=""):
    old_schema = old_schema if isinstance(old_schema, dict) else {}
    new_schema = new_schema if isinstance(new_schema, dict) else {}
    old_tables = old_schema.get("tables") or {}
    new_tables = new_schema.get("tables") or {}
    findings = []
    for table in sorted(set(old_tables) - set(new_tables)):
        findings.append({"severity": "critical", "kind": "drop-table", "table": table, "message": "Table removal can cause irreversible data loss."})
    for table in sorted(set(old_tables) & set(new_tables)):
        old_columns = old_tables[table].get("columns", {}) if isinstance(old_tables[table], dict) else {}
        new_columns = new_tables[table].get("columns", {}) if isinstance(new_tables[table], dict) else {}
        for column in sorted(set(old_columns) - set(new_columns)):
            findings.append({"severity": "high", "kind": "drop-column", "table": table, "column": column, "message": "Column removal can cause data loss."})
        for column in sorted(set(new_columns) - set(old_columns)):
            definition = new_columns[column] if isinstance(new_columns[column], dict) else {}
            if definition.get("required") and not definition.get("default"):
                findings.append({"severity": "high", "kind": "required-column", "table": table, "column": column, "message": "Adding a required column without a default may fail on existing rows."})
    sql_lines = [line.strip() for line in (migration_sql or "").splitlines() if line.strip()]
    for line in sql_lines:
        upper = line.upper()
        if re.search(r"\bDROP\s+(TABLE|COLUMN)\b", upper):
            findings.append({"severity": "critical", "kind": "destructive-sql", "message": line[:500]})
        elif "ALTER COLUMN" in upper and "TYPE" in upper:
            findings.append({"severity": "high", "kind": "type-change", "message": line[:500]})
    return {
        "safe": not any(item["severity"] in {"critical", "high"} for item in findings),
        "findings": findings,
        "dry_run": {"statements": sql_lines, "statement_count": len(sql_lines), "executed": False},
        "rollback_guidance": ["Back up affected tables before applying changes.", "Use expand/contract for required fields and type changes.", "Keep a tested reverse migration for every destructive operation."],
        "approval_required": True,
        "offline_only": True,
    }


def plan_dependency_upgrades(files, catalog=None):
    catalog = catalog if isinstance(catalog, dict) else {}
    dependencies = []
    for item in (files or [])[:100]:
        filename = str(item.get("filename") or "").replace("\\", "/")
        content = str(item.get("content") or "")
        if filename.lower().endswith(("requirements.txt", "requirements-dev.txt")):
            for line in content.splitlines():
                match = re.match(r"^\s*([A-Za-z0-9_.-]+)\s*(==|~=|>=|<=|>|<)?\s*([^;\s]+)?", line)
                if match and not line.strip().startswith("#"):
                    name, operator, version = match.groups()
                    dependencies.append({"name": name, "current": version or "unversioned", "operator": operator or "", "source": filename, "manager": "pip"})
        elif filename.lower().endswith("package.json"):
            try:
                data = json.loads(content)
            except (TypeError, ValueError, json.JSONDecodeError):
                data = {}
            for group in ("dependencies", "devDependencies"):
                for name, version in (data.get(group) or {}).items():
                    dependencies.append({"name": name, "current": str(version), "operator": "", "source": filename, "manager": "npm", "group": group})
    updates = []
    for dependency in dependencies:
        proposal = catalog.get(dependency["name"])
        if not proposal:
            continue
        target = str(proposal.get("version") if isinstance(proposal, dict) else proposal)
        if target and target != dependency["current"]:
            updates.append({"dependency": dependency, "target": target, "advisories": (proposal.get("advisories", []) if isinstance(proposal, dict) else []), "tests_required": ["install or lock resolution", "unit tests", "local CI", "security scan"]})
    return {
        "bot": "offline-dependency-upgrade",
        "dependencies": dependencies,
        "updates": updates,
        "catalog_entries": len(catalog),
        "patches_are_preview_only": True,
        "rollback": "Restore the lockfile and dependency manifest from the reviewed patch.",
        "network_policy": "blocked",
        "offline_only": True,
    }


def analyze_generated_sync(files, manifest=None):
    manifest = manifest if isinstance(manifest, dict) else {}
    by_name = {str(item.get("filename") or "").replace("\\", "/"): str(item.get("content") or "") for item in (files or [])}
    stale = []
    missing = []
    for generated, config in manifest.items():
        config = config if isinstance(config, dict) else {"sources": config if isinstance(config, list) else []}
        sources = [str(source).replace("\\", "/") for source in (config.get("sources") or [])]
        source_blob = "\n".join(by_name.get(source, "") for source in sources)
        source_hash = hashlib.sha256(source_blob.encode("utf-8")).hexdigest()[:16]
        recorded = str(config.get("source_hash") or "")
        if generated not in by_name:
            missing.append({"generated": generated, "sources": sources, "source_hash": source_hash})
        elif recorded and recorded != source_hash:
            stale.append({"generated": generated, "sources": sources, "recorded_hash": recorded, "current_hash": source_hash})
    generated_markers = [filename for filename, content in by_name.items() if "@generated" in content.lower() or "do not edit" in content.lower()]
    return {
        "generated_files": generated_markers,
        "stale": stale,
        "missing": missing,
        "up_to_date": not stale and not missing,
        "regeneration_plan": [{"generated": item["generated"], "action": "regenerate", "sources": item["sources"]} for item in stale + missing],
        "supported_outputs": ["clients", "types", "serializers", "migrations", "documentation"],
        "approval_required": True,
        "offline_only": True,
    }


def mutation_test_plan(code, language="python", results=None):
    results = results if isinstance(results, dict) else {}
    replacements = [("==", "!="), ("!=", "=="), (" + ", " - "), (" - ", " + "), (" > ", " >= "), (" < ", " <= ")]
    mutants = []
    for index, (source, target) in enumerate(replacements, start=1):
        position = code.find(source)
        if position < 0:
            continue
        mutated = code[:position] + target + code[position + len(source):]
        mutant_id = f"M{index:03d}"
        status = str(results.get(mutant_id, "untested"))
        mutants.append({"id": mutant_id, "operator": f"{source.strip()} -> {target.strip()}", "offset": position, "status": status, "code": mutated})
    killed = sum(item["status"] == "killed" for item in mutants)
    survived = sum(item["status"] == "survived" for item in mutants)
    score = round((killed / (killed + survived)) * 100, 2) if killed + survived else None
    return {
        "runner": "offline-mutation-plan",
        "language": language,
        "mutants": mutants,
        "killed": killed,
        "survived": survived,
        "untested": len(mutants) - killed - survived,
        "mutation_score": score,
        "weak_test_targets": [item["id"] for item in mutants if item["status"] == "survived"],
        "execution": "Run each approved mutant through the guarded local test runner.",
        "approval_required": True,
        "offline_only": True,
    }


def fingerprint_workspace_environment(files, hardware=None):
    hardware = hardware if isinstance(hardware, dict) else {}
    names = {str(item.get("filename") or "").replace("\\", "/") for item in (files or [])}
    manifests = []
    if "requirements.txt" in {name.lower() for name in names} or any(name.endswith("pyproject.toml") for name in names):
        manifests.append({"ecosystem": "python", "manager": "pip/uv", "lockfiles": [name for name in names if name.endswith(("requirements.lock", "poetry.lock", "uv.lock"))]})
    if any(name.endswith("package.json") for name in names):
        manifests.append({"ecosystem": "javascript", "manager": "npm/pnpm/yarn", "lockfiles": [name for name in names if name.endswith(("package-lock.json", "pnpm-lock.yaml", "yarn.lock"))]})
    if any(name.endswith("Cargo.toml") for name in names):
        manifests.append({"ecosystem": "rust", "manager": "cargo", "lockfiles": [name for name in names if name.endswith("Cargo.lock")]})
    toolchain_files = [name for name in names if name.endswith((".tool-versions", ".python-version", ".nvmrc", "rust-toolchain.toml", "Dockerfile", "devcontainer.json"))]
    env_keys = sorted({match.group(1) for item in (files or []) for match in [re.search(r"^\s*([A-Z][A-Z0-9_]{2,})\s*=", str(item.get("content") or ""), re.MULTILINE)] if match and not re.search(r"(SECRET|KEY|TOKEN|PASSWORD|PASSWD|PRIVATE)", match.group(1), re.IGNORECASE)})
    return {
        "fingerprint": "offline-workspace-environment-v1",
        "manifests": manifests,
        "toolchain_files": toolchain_files,
        "environment_keys": env_keys,
        "hardware_requirements": hardware,
        "reproducibility_checks": [
            "Pin interpreter and compiler versions.",
            "Commit or verify lockfiles for every package manager.",
            "Keep local environment secrets outside the generated manifest.",
            "Run the same local CI pipeline inside the selected environment.",
        ],
        "generated_manifest": {"manifests": manifests, "toolchain_files": toolchain_files, "environment_keys": env_keys, "hardware": hardware},
        "secrets_included": False,
        "offline_only": True,
    }


def dap_session_plan(language="python", program="", cwd="", breakpoints=None, exception_breakpoints=True):
    adapters = {
        "python": {"id": "debugpy", "command": "python -m debugpy.adapter"},
        "javascript": {"id": "js-debug", "command": "js-debug-adapter"},
        "typescript": {"id": "js-debug", "command": "js-debug-adapter"},
        "go": {"id": "delve", "command": "dlv dap"},
        "rust": {"id": "codelldb", "command": "codelldb"},
        "java": {"id": "java-debug", "command": "java-debug-adapter"},
    }
    language = (language or "python").lower()
    adapter = adapters.get(language, {"id": "custom", "command": "configure a local DAP adapter"})
    points = []
    for item in (breakpoints or [])[:100]:
        try:
            line = max(1, int(item.get("line", 1))) if isinstance(item, dict) else max(1, int(item))
        except (TypeError, ValueError):
            continue
        points.append({"file": item.get("file", "") if isinstance(item, dict) else "", "line": line, "verified": False})
    return {
        "protocol": "debug-adapter-protocol",
        "version": "1.71",
        "adapter": adapter,
        "program": str(program or "")[:500],
        "cwd": str(cwd or "")[:500],
        "breakpoints": points,
        "exception_breakpoints": bool(exception_breakpoints),
        "capabilities": ["initialize", "launch", "attach", "setBreakpoints", "stackTrace", "scopes", "variables", "evaluate", "next", "stepIn", "stepOut", "continue", "pause", "disconnect"],
        "approval_required": True,
        "network_policy": "blocked",
        "offline_only": True,
    }


def route_codeowners(codeowners_text, changed_files, approvals=None):
    approvals = approvals if isinstance(approvals, dict) else {}
    rules = []
    for line in (codeowners_text or "").splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        parts = line.split()
        if len(parts) < 2:
            continue
        rules.append((parts[0], parts[1:]))
    routed = []
    for raw_path in (changed_files or [])[:500]:
        path = str(raw_path).replace("\\", "/").lstrip("/")
        owners = []
        matched_pattern = ""
        for pattern, candidates in rules:
            normalized = pattern.lstrip("/")
            if fnmatch.fnmatch(path, normalized) or fnmatch.fnmatch(path, normalized.replace("/**", "/*")):
                owners = candidates
                matched_pattern = pattern
        approved = [owner for owner in owners if approvals.get(owner) in {True, "true", "1", "approved"}]
        routed.append({"path": path, "pattern": matched_pattern, "owners": owners, "approved": approved, "missing": [owner for owner in owners if owner not in approved], "blocked": bool(owners) and not approved})
    required = sorted({owner for item in routed for owner in item["owners"]})
    approved = sorted({owner for item in routed for owner in item["approved"]})
    return {
        "files": routed,
        "required_owners": required,
        "approved_owners": approved,
        "missing_owners": sorted(set(required) - set(approved)),
        "ready": not any(item["blocked"] for item in routed),
        "rules_count": len(rules),
        "approval_required": True,
        "offline_only": True,
    }


def plan_merge_queue(entries):
    entries = [item for item in (entries or [])[:200] if isinstance(item, dict) and item.get("id")]
    by_id = {str(item["id"]): item for item in entries}
    dependencies = {key: {str(dep) for dep in (value.get("depends_on") or []) if str(dep) in by_id} for key, value in by_id.items()}
    order = []
    direct_blocked = {key for key, item in by_id.items() if item.get("conflict") or item.get("conflicts") or item.get("checks_passed") is False}
    remaining = set(by_id) - direct_blocked
    cycles = []
    while remaining:
        ready = sorted(item for item in remaining if not dependencies[item] & remaining and not dependencies[item] & direct_blocked)
        if not ready:
            cycles.append(sorted(remaining))
            break
        order.extend(ready)
        remaining -= set(ready)
    blocked = []
    for key, item in by_id.items():
        reasons = []
        if item.get("conflict") or item.get("conflicts"):
            reasons.append("conflict")
        if item.get("checks_passed") is False:
            reasons.append("checks-failed")
        if key in direct_blocked:
            pass
        elif dependencies[key] & direct_blocked:
            reasons.append("blocked-dependency")
        elif dependencies[key] & remaining or any(key in cycle for cycle in cycles):
            reasons.append("dependency-cycle-or-blocked")
        if reasons:
            blocked.append({"id": key, "reasons": reasons})
    return {
        "queue": [{"id": key, "position": index + 1, "depends_on": sorted(dependencies[key])} for index, key in enumerate(order)],
        "blocked": blocked,
        "cycles": cycles,
        "ready": not blocked and not cycles,
        "strategy": "topological stacked-pr ordering",
        "approval_required": True,
        "offline_only": True,
    }


def analyze_taint_flow(files):
    source_patterns = [r"request\.(GET|POST|args|params)", r"input\s*\(", r"sys\.argv", r"os\.environ", r"location\.(search|hash)"]
    sink_patterns = [
        ("sql", r"(?:execute|executemany|cursor)\s*\([^)]*(?:\+|%|format\(|f[\"'])"),
        ("shell", r"(?:os\.system|subprocess\.(?:run|Popen|call)|child_process\.exec)\s*\("),
        ("file", r"(?:open|writeFile|readFile)\s*\("),
        ("html", r"(?:innerHTML|outerHTML|document\.write)\s*[=\(]"),
    ]
    findings = []
    for item in (files or [])[:200]:
        filename = str(item.get("filename") or "buffer").replace("\\", "/")
        content = str(item.get("content") or "")
        tainted = set()
        for line_number, line in enumerate(content.splitlines(), start=1):
            if any(re.search(pattern, line, re.IGNORECASE) for pattern in source_patterns):
                assignment = re.search(r"\b([A-Za-z_]\w*)\s*=", line)
                if assignment:
                    tainted.add(assignment.group(1))
            for kind, pattern in sink_patterns:
                if re.search(pattern, line, re.IGNORECASE) and (tainted or any(re.search(r"\b" + re.escape(name) + r"\b", line) for name in tainted)):
                    findings.append({"filename": filename, "line": line_number, "category": kind, "severity": "high", "message": f"Potential tainted data flow reaches {kind} sink.", "evidence": line.strip()[:500]})
        for name in tainted:
            for line_number, line in enumerate(content.splitlines(), start=1):
                if name in line and any(re.search(pattern, line, re.IGNORECASE) for _, pattern in sink_patterns):
                    if not any(item["filename"] == filename and item["line"] == line_number for item in findings):
                        findings.append({"filename": filename, "line": line_number, "category": "dataflow", "severity": "medium", "message": f"Review flow of input-derived variable {name}.", "evidence": line.strip()[:500]})
    return {
        "findings": findings[:200],
        "sources_checked": source_patterns,
        "sinks_checked": [kind for kind, _ in sink_patterns],
        "safe": not any(item["severity"] == "high" for item in findings),
        "engine": "offline-source-sink-analysis",
        "offline_only": True,
    }


def detect_flaky_tests(runs):
    grouped = defaultdict(list)
    for run in (runs or [])[:2000]:
        if not isinstance(run, dict) or not run.get("name"):
            continue
        grouped[str(run["name"])].append(run)
    tests = []
    for name, samples in sorted(grouped.items()):
        passed = sum(str(item.get("status", "")).lower() in {"pass", "passed", "ok", "success"} for item in samples)
        failed = sum(str(item.get("status", "")).lower() in {"fail", "failed", "error"} for item in samples)
        total = len(samples)
        failure_rate = round(failed / total, 3) if total else 0
        flaky = total >= 3 and passed > 0 and failed > 0
        tests.append({"name": name, "runs": total, "passed": passed, "failed": failed, "failure_rate": failure_rate, "flaky": flaky, "avg_duration_ms": round(sum(float(item.get("duration_ms", 0) or 0) for item in samples) / total, 2) if total else 0})
    flaky_tests = [item for item in tests if item["flaky"]]
    return {
        "tests": tests,
        "flaky_tests": flaky_tests,
        "quarantine_candidates": [{"name": item["name"], "reason": "Mixed outcomes across repeated local runs.", "requires_owner_review": True} for item in flaky_tests],
        "policy": "Do not silently ignore a flaky test; quarantine only with an owner, expiry date, and follow-up issue.",
        "offline_only": True,
    }


def generate_fuzz_cases(code, language="python", seed_inputs=None):
    code = str(code or "")
    seed_inputs = seed_inputs if isinstance(seed_inputs, list) else []
    signatures = re.findall(r"(?:def|function)\s+([A-Za-z_]\w*)\s*\(([^)]*)\)", code)
    target = signatures[0][0] if signatures else "target_function"
    parameters = [item.strip().split("=", 1)[0].strip() for item in (signatures[0][1].split(",") if signatures else []) if item.strip()]
    cases = [{"name": "empty-input", "args": ["" for _ in parameters]}, {"name": "null-input", "args": [None for _ in parameters]}, {"name": "boundary-numbers", "args": [0, -1, 1, 2**31 - 1][:len(parameters)]}, {"name": "unicode-input", "args": ["\u0000\U0001f600\u00e9" for _ in parameters]}, {"name": "large-input", "args": ["x" * 4096 for _ in parameters]}]
    cases.extend({"name": f"seed-{index + 1}", "args": value if isinstance(value, list) else [value]} for index, value in enumerate(seed_inputs[:20]))
    return {
        "runner": "offline-property-fuzz",
        "target": target,
        "parameters": parameters,
        "cases": cases,
        "property_checks": ["no unexpected exception", "stable output for repeated input", "boundary values are handled", "input size limits are enforced"],
        "shrinking": ["remove arguments", "reduce strings by half", "move numbers toward zero", "retain the smallest failing case"],
        "approval_required": True,
        "offline_only": True,
    }


def analyze_consumer_contracts(provider_endpoints, consumer_contracts):
    def normalize(item):
        if isinstance(item, str):
            parts = item.split(None, 1)
            return (parts[0].lower(), parts[1].rstrip("/") or "/") if len(parts) == 2 else ("get", item.rstrip("/") or "/")
        return (str(item.get("method", "get")).lower(), str(item.get("path", "/")).rstrip("/") or "/")

    provider = {normalize(item) for item in (provider_endpoints or [])}
    consumers = []
    for contract in (consumer_contracts or [])[:500]:
        item = normalize(contract)
        consumers.append({"consumer": contract.get("consumer", "unknown") if isinstance(contract, dict) else "unknown", "method": item[0].upper(), "path": item[1], "present": item in provider})
    missing = [item for item in consumers if not item["present"]]
    unused = [{"method": method.upper(), "path": path} for method, path in sorted(provider - {(item["method"].lower(), item["path"]) for item in consumers})]
    return {
        "provider_endpoints": [{"method": method.upper(), "path": path} for method, path in sorted(provider)],
        "consumer_contracts": consumers,
        "missing_provider_endpoints": missing,
        "unused_provider_endpoints": unused,
        "compatible": not missing,
        "test_plan": ["Run each consumer contract against the local provider.", "Validate status, schema, and error responses.", "Block release when a required contract is missing."],
        "offline_only": True,
    }


def build_provenance(files, metadata=None, signing_secret=""):
    metadata = metadata if isinstance(metadata, dict) else {}
    subjects = []
    for item in sorted((files or [])[:1000], key=lambda value: str(value.get("filename", ""))):
        filename = str(item.get("filename") or "").replace("\\", "/")
        content = str(item.get("content") or "").encode("utf-8")
        subjects.append({"name": filename, "sha256": hashlib.sha256(content).hexdigest(), "size": len(content)})
    payload = {"format": "offline-provenance-v1", "subjects": subjects, "metadata": {key: str(value)[:500] for key, value in metadata.items() if "secret" not in key.lower() and "token" not in key.lower()}}
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    attestation = {**payload, "subject_digest": hashlib.sha256(canonical.encode("utf-8")).hexdigest(), "signature": hashlib.sha256(((signing_secret or "unsigned") + canonical).encode("utf-8")).hexdigest()}
    return {"attestation": attestation, "verification": {"signed": bool(signing_secret), "algorithm": "sha256-local", "verified": True}, "offline_only": True}


def verify_provenance(attestation, signing_secret=""):
    if not isinstance(attestation, dict):
        return {"valid": False, "error": "Attestation must be a JSON object."}
    payload = {"format": attestation.get("format"), "subjects": attestation.get("subjects", []), "metadata": attestation.get("metadata", {})}
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    digest_valid = hashlib.sha256(canonical.encode("utf-8")).hexdigest() == attestation.get("subject_digest")
    signature_valid = hashlib.sha256(((signing_secret or "unsigned") + canonical).encode("utf-8")).hexdigest() == attestation.get("signature")
    return {"valid": digest_valid and signature_valid, "digest_valid": digest_valid, "signature_valid": signature_valid, "subjects": len(payload["subjects"]), "offline_only": True}


def resolve_merge_conflicts(content, strategy="review"):
    lines = (content or "").splitlines(True)
    conflicts = []
    resolved = []
    index = 0
    while index < len(lines):
        if not lines[index].startswith("<<<<<<<"):
            resolved.append(lines[index])
            index += 1
            continue
        start = index + 1
        separator = next((pos for pos in range(start, len(lines)) if lines[pos].startswith("=======")), None)
        end = next((pos for pos in range((separator or start) + 1, len(lines)) if lines[pos].startswith(">>>>>>>")), None)
        if separator is None or end is None:
            return {"success": False, "error": "Unterminated merge conflict marker."}
        ours = lines[start:separator]
        theirs = lines[separator + 1:end]
        conflict = {"index": len(conflicts) + 1, "ours": "".join(ours), "theirs": "".join(theirs), "start_line": start + 1, "end_line": end + 1}
        conflicts.append(conflict)
        if strategy == "ours":
            resolved.extend(ours)
        elif strategy == "theirs":
            resolved.extend(theirs)
        else:
            resolved.extend(lines[index:end + 1])
        index = end + 1
    return {
        "success": True,
        "conflict_count": len(conflicts),
        "conflicts": conflicts,
        "strategy": strategy if strategy in {"review", "ours", "theirs"} else "review",
        "resolved_content": "".join(resolved),
        "clean": not conflicts,
        "approval_required": bool(conflicts),
        "rerun_tests_after_resolution": bool(conflicts),
        "offline_only": True,
    }


def plan_release(current_version="0.1.0", commits=None, changes=None, migration_required=False):
    commits = [str(item) for item in (commits or [])[:500]]
    changes = changes if isinstance(changes, list) else []
    breaking = any("BREAKING CHANGE" in item or re.match(r"^\w+!:", item) for item in commits)
    features = sum(bool(re.match(r"^(feat|feature)(\(|:)", item, re.IGNORECASE)) for item in commits)
    fixes = sum(bool(re.match(r"^(fix|bugfix)(\(|:)", item, re.IGNORECASE)) for item in commits)
    try:
        major, minor, patch = [int(part) for part in str(current_version).split(".")[:3]]
    except (TypeError, ValueError):
        major, minor, patch = 0, 1, 0
    if breaking:
        major += 1
        minor = patch = 0
        bump = "major"
    elif features:
        minor += 1
        patch = 0
        bump = "minor"
    else:
        patch += 1
        bump = "patch"
    sections = {"Breaking changes": [], "Features": [], "Fixes": [], "Other": []}
    for item in commits + [str(value) for value in changes]:
        if "BREAKING CHANGE" in item or re.match(r"^\w+!:", item):
            sections["Breaking changes"].append(item)
        elif re.match(r"^(feat|feature)(\(|:)", item, re.IGNORECASE):
            sections["Features"].append(item)
        elif re.match(r"^(fix|bugfix)(\(|:)", item, re.IGNORECASE):
            sections["Fixes"].append(item)
        else:
            sections["Other"].append(item)
    changelog = [f"## {major}.{minor}.{patch}", ""]
    for heading, entries in sections.items():
        if entries:
            changelog.extend([f"### {heading}", ""] + [f"- {entry}" for entry in entries] + [""])
    checklist = ["Run local CI.", "Run security/SBOM checks.", "Verify migration safety.", "Verify build provenance.", "Review CODEOWNERS approvals.", "Create a rollback plan."]
    if migration_required:
        checklist.insert(2, "Apply and verify migrations in a disposable local database.")
    return {
        "current_version": current_version,
        "next_version": f"{major}.{minor}.{patch}",
        "bump": bump,
        "counts": {"breaking": int(breaking), "features": features, "fixes": fixes},
        "changelog": "\n".join(changelog).strip() + "\n",
        "release_checklist": checklist,
        "candidate_validation": ["Run tests twice to check flakiness.", "Verify artifact attestation.", "Review generated-code synchronization.", "Confirm consumer contracts."],
        "approval_required": True,
        "offline_only": True,
    }


def _safe_identifier(value):
    return bool(re.fullmatch(r"[A-Za-z_$][\w$]*", value or ""))


def preview_refactor(filename, code, operation="rename", old_name="", new_name="", language="auto"):
    language = _language(filename, language)
    if operation != "rename":
        return {"success": False, "error": "Supported refactor operation: rename."}
    if not _safe_identifier(old_name) or not _safe_identifier(new_name):
        return {"success": False, "error": "Names must be valid identifiers."}
    if old_name == new_name:
        return {"success": False, "error": "The new name must be different."}
    if language == "python":
        try:
            ast.parse(code or "", filename=filename or "buffer.py")
        except SyntaxError as exc:
            return {"success": False, "error": f"Cannot refactor invalid Python: {exc.msg}.", "line": exc.lineno}
    pattern = re.compile(r"\b" + re.escape(old_name) + r"\b")
    updated, count = pattern.subn(new_name, code or "")
    diff = "".join(difflib.unified_diff((code or "").splitlines(True), updated.splitlines(True), fromfile=filename or "before", tofile=filename or "after"))
    return {"success": True, "operation": operation, "filename": filename or "buffer", "old_name": old_name, "new_name": new_name, "replacements": count, "changed": updated != code, "content": updated, "diff": diff, "approval_required": True}


def refactor_workspace(files, operation="rename", old_name="", new_name=""):
    """Preview a coordinated rename across a set of local file buffers."""
    if not _safe_identifier(old_name) or not _safe_identifier(new_name):
        return {"success": False, "error": "Names must be valid identifiers."}
    changes = []
    total = 0
    for item in (files or [])[:100]:
        filename = str(item.get("filename") or "buffer")[:300]
        result = preview_refactor(filename, str(item.get("content") or ""), operation, old_name, new_name)
        if not result.get("success"):
            return result
        if result["changed"]:
            changes.append(result)
            total += result["replacements"]
    return {"success": True, "operation": operation, "old_name": old_name, "new_name": new_name, "files_changed": len(changes), "replacements": total, "changes": changes, "approval_required": True, "rollback_supported": True}


def issue_to_pr_plan(title, description, files=None, test_command=""):
    title = (title or "Untitled coding task").strip()[:200]
    description = (description or "").strip()[:10000]
    files = [str(item).replace("\\", "/")[:300] for item in (files or []) if str(item).strip()][:50]
    return {
        "title": title,
        "goal": description,
        "workflow": [
            {"id": "inspect", "kind": "read", "title": "Inspect repository context", "approval_required": False},
            {"id": "plan", "kind": "plan", "title": "Build an implementation plan", "approval_required": True},
            {"id": "edit", "kind": "write", "title": "Apply reviewed code changes in an isolated worktree", "approval_required": True},
            {"id": "test", "kind": "test", "title": test_command or "Detect and run the project test command", "approval_required": True},
            {"id": "review", "kind": "review", "title": "Run local quality and security review", "approval_required": True},
            {"id": "pr", "kind": "artifact", "title": "Prepare a pull-request summary", "approval_required": True},
        ],
        "files_in_scope": files,
        "isolation": "agent-worktree",
        "offline_only": True,
    }


def review_pull_request(files, diff="", tests="", language="auto"):
    """Run the existing local review gate and attach diff-aware comments."""
    from .review import review_gate

    gate = review_gate(files or [], language, diff, tests)
    comments = []
    current_file = ""
    new_line = 0
    for raw in (diff or "").splitlines():
        if raw.startswith("+++ b/"):
            current_file = raw[6:].strip()
        elif raw.startswith("@@"):
            match = re.search(r"\+(\d+)", raw)
            new_line = int(match.group(1)) if match else 0
        elif raw.startswith("+") and not raw.startswith("+++"):
            for finding in gate["findings"]:
                if finding.get("filename") == current_file and finding.get("line") == new_line:
                    comments.append({"path": current_file, "line": new_line, "severity": finding["severity"], "body": finding["message"], "source": finding["source"]})
            new_line += 1
        elif not raw.startswith("-") and raw and not raw.startswith("\\"):
            new_line += 1
    return {
        "ready": gate["ready"],
        "score": gate["score"],
        "summary": gate["summary"],
        "checks": gate["checks"],
        "findings": gate["findings"],
        "comments": comments,
        "diff_lines": gate["diff_lines"],
        "review_fingerprint": __import__("hashlib").sha256((diff or "").encode("utf-8")).hexdigest()[:16],
        "rerun_required_after_push": True,
    }


def discover_local_ci(files):
    """Build a deterministic offline CI plan from repository manifests."""
    names = {str(item.get("filename") or "").replace("\\", "/").lower() for item in (files or [])}
    commands = []
    if "requirements.txt" in names or "pyproject.toml" in names or "manage.py" in names:
        commands.extend([
            {"id": "python-compile", "stage": "lint", "command": "python -m compileall -q ."},
            {"id": "python-tests", "stage": "test", "command": "python manage.py test" if "manage.py" in names else "python -m pytest"},
        ])
    if "package.json" in names:
        commands.extend([
            {"id": "npm-lint", "stage": "lint", "command": "npm run lint --if-present"},
            {"id": "npm-tests", "stage": "test", "command": "npm test -- --runInBand"},
            {"id": "npm-build", "stage": "build", "command": "npm run build --if-present"},
        ])
    if "cargo.toml" in names:
        commands.extend([
            {"id": "cargo-check", "stage": "lint", "command": "cargo check"},
            {"id": "cargo-test", "stage": "test", "command": "cargo test"},
        ])
    if not commands:
        commands = [{"id": "manual-test", "stage": "test", "command": "Select a local test command before running."}]
    return {
        "runner": "offline-local-ci",
        "commands": commands,
        "stages": sorted({item["stage"] for item in commands}),
        "approval_required": True,
        "network_policy": "blocked",
        "artifact_formats": ["json", "junit", "coverage", "sarif"],
        "cache": "local-only",
    }


def security_sbom_report(files, advisory_snapshot=None):
    """Return local findings plus SARIF and optional imported advisory matches."""
    from .security import scan_files

    report = scan_files(files or [])
    snapshot = advisory_snapshot if isinstance(advisory_snapshot, dict) else {}
    advisory_matches = []
    for dependency in report["dependencies"]:
        key = f"{dependency['name']}@{dependency['version']}"
        if key in snapshot:
            advisory_matches.append({"dependency": dependency, "advisories": snapshot[key]})
    rules = []
    results = []
    for finding in report["findings"]:
        rule_id = finding.get("rule", "local-security")
        if rule_id not in {item["id"] for item in rules}:
            rules.append({"id": rule_id, "shortDescription": {"text": finding["message"][:120]}, "properties": {"severity": finding["severity"]}})
        location = {"physicalLocation": {"artifactLocation": {"uri": finding.get("filename", "buffer")}}}
        if finding.get("line"):
            location["physicalLocation"]["region"] = {"startLine": finding["line"]}
        results.append({"ruleId": rule_id, "level": "error" if finding["severity"] in {"critical", "high"} else "warning", "message": {"text": finding["message"]}, "locations": [location]})
    sarif = {
        "$schema": "https://json.schemastore.org/sarif-2.1.0.json",
        "version": "2.1.0",
        "runs": [{"tool": {"driver": {"name": "Offline CodeGPT Security", "rules": rules}}, "results": results}],
    }
    return {
        "summary": report["summary"],
        "findings": report["findings"],
        "dependencies": report["dependencies"],
        "licenses": report["licenses"],
        "sbom": report["sbom"],
        "sarif": sarif,
        "advisory_matches": advisory_matches,
        "advisory_source": "imported-local-snapshot" if snapshot else "none",
        "offline_only": True,
        "limitations": report["limitations"],
    }


def browser_debug_plan(base_url, flow, report="", snapshot_name="workspace"):
    from .browser_testing import analyze_browser_report, generate_playwright_test

    analysis = analyze_browser_report(report)
    return {
        "runner": "local-playwright",
        "base_url": (base_url or "http://127.0.0.1:8000").strip().rstrip("/"),
        "test_code": generate_playwright_test(base_url, flow, snapshot_name),
        "report": analysis,
        "repair_loop": [
            "Run the generated test in the local browser.",
            "Capture console, network, screenshot, and trace evidence.",
            "Review the suggested patch before applying it.",
            "Re-run the test and update the visual baseline only after approval.",
        ],
        "artifacts": ["trace.zip", "screenshot.png", "console.log", "network.json"],
        "network_policy": "local-target-only",
        "approval_required_for_patch": True,
    }


def evolve_api_contract(old_spec, new_spec):
    def endpoints(spec):
        output = {}
        for path, operations in (spec.get("paths") or {}).items():
            for method, operation in (operations or {}).items():
                if method.lower() in {"get", "post", "put", "patch", "delete", "options", "head"}:
                    output[(method.lower(), path.rstrip("/") or "/")] = operation or {}
        return output

    before = endpoints(old_spec if isinstance(old_spec, dict) else {})
    after = endpoints(new_spec if isinstance(new_spec, dict) else {})
    removed = sorted(set(before) - set(after))
    added = sorted(set(after) - set(before))
    changed = []
    for endpoint in sorted(set(before) & set(after)):
        old_parameters = {(item.get("name"), item.get("in"), bool(item.get("required"))) for item in before[endpoint].get("parameters", [])}
        new_parameters = {(item.get("name"), item.get("in"), bool(item.get("required"))) for item in after[endpoint].get("parameters", [])}
        new_required = sorted(item[0] for item in new_parameters - old_parameters if item[2])
        if new_required:
            changed.append({"method": endpoint[0].upper(), "path": endpoint[1], "new_required_parameters": new_required})
    breaking = [{"method": method.upper(), "path": path, "reason": "Endpoint removed."} for method, path in removed]
    breaking.extend({"method": item["method"], "path": item["path"], "reason": "New required parameter."} for item in changed)
    return {
        "breaking": breaking,
        "removed": [{"method": method.upper(), "path": path} for method, path in removed],
        "added": [{"method": method.upper(), "path": path} for method, path in added],
        "changed": changed,
        "safe_to_release": not breaking,
        "suggestions": [
            "Generate a migration note for removed endpoints.",
            "Regenerate typed clients and contract tests for added endpoints.",
            "Add compatibility tests for every new required parameter.",
        ],
        "offline_only": True,
    }


def profile_code_performance(files, benchmark=None):
    rows = []
    for item in (files or [])[:100]:
        filename = str(item.get("filename") or "buffer")[:300]
        content = str(item.get("content") or "")
        lines = content.splitlines()
        loops = len(re.findall(r"\b(for|while)\b", content))
        calls = len(re.findall(r"\b[A-Za-z_]\w*\s*\(", content))
        sql_queries = len(re.findall(r"\b(select|insert|update|delete)\b", content, re.IGNORECASE))
        score = min(100, 20 + len(lines) // 10 + loops * 5 + sql_queries * 8)
        rows.append({"filename": filename, "lines": len(lines), "loops": loops, "calls": calls, "sql_queries": sql_queries, "complexity_signal": score})
    measurements = benchmark if isinstance(benchmark, list) else []
    before = sum(float(item.get("duration_ms", 0) or 0) for item in measurements if item.get("phase") == "before")
    after = sum(float(item.get("duration_ms", 0) or 0) for item in measurements if item.get("phase") == "after")
    delta = round(((after - before) / before) * 100, 2) if before else None
    hotspots = sorted(rows, key=lambda item: (-item["complexity_signal"], -item["lines"]))[:10]
    return {
        "profiler": "offline-static-and-benchmark",
        "files": rows,
        "hotspots": hotspots,
        "benchmark": {"before_ms": before, "after_ms": after, "delta_percent": delta, "samples": len(measurements)},
        "optimization_suggestions": [
            "Measure a baseline before applying a code change.",
            "Prioritize high-signal loops and database query sites.",
            "Run the same benchmark after the patch and keep the change only when tests still pass.",
        ],
        "patch_approval_required": True,
        "offline_only": True,
    }


def orchestrate_monorepo(files, changed_files=None):
    changed = {str(item).replace("\\", "/").lstrip("./") for item in (changed_files or [])}
    packages = []
    for item in (files or [])[:500]:
        filename = str(item.get("filename") or "").replace("\\", "/").lstrip("./")
        content = str(item.get("content") or "")
        if filename.endswith("package.json"):
            try:
                data = json.loads(content)
            except (TypeError, ValueError, json.JSONDecodeError):
                data = {}
            root = filename.rsplit("/", 1)[0] if "/" in filename else "."
            packages.append({"name": data.get("name") or root, "root": root, "manager": "npm", "scripts": sorted((data.get("scripts") or {}).keys()), "dependencies": sorted((data.get("dependencies") or {}).keys())})
        elif filename.endswith("pyproject.toml"):
            root = filename.rsplit("/", 1)[0] if "/" in filename else "."
            packages.append({"name": root, "root": root, "manager": "python", "scripts": ["test", "lint"], "dependencies": []})
        elif filename.endswith("Cargo.toml"):
            root = filename.rsplit("/", 1)[0] if "/" in filename else "."
            packages.append({"name": root, "root": root, "manager": "cargo", "scripts": ["check", "test"], "dependencies": []})
    affected = []
    for package in packages:
        root = package["root"]
        if not changed or root == "." or any(path == root or path.startswith(root + "/") for path in changed):
            affected.append(package["name"])
    tasks = []
    for package in packages:
        if package["name"] not in affected:
            continue
        if package["manager"] == "npm":
            tasks.extend([{"package": package["name"], "stage": "lint", "command": "npm run lint --if-present", "cwd": package["root"]}, {"package": package["name"], "stage": "test", "command": "npm test -- --runInBand", "cwd": package["root"]}])
        elif package["manager"] == "cargo":
            tasks.extend([{"package": package["name"], "stage": "check", "command": "cargo check", "cwd": package["root"]}, {"package": package["name"], "stage": "test", "command": "cargo test", "cwd": package["root"]}])
        else:
            tasks.extend([{"package": package["name"], "stage": "lint", "command": "python -m compileall -q .", "cwd": package["root"]}, {"package": package["name"], "stage": "test", "command": "python -m pytest", "cwd": package["root"]}])
    return {
        "orchestrator": "offline-affected-task-graph",
        "packages": packages,
        "changed_files": sorted(changed),
        "affected_packages": affected,
        "tasks": tasks,
        "cache": "local-content-hash",
        "approval_required": True,
        "network_policy": "blocked",
        "offline_only": True,
    }


def evaluate_agent_hook(event, tool_name, tool_args=None, policies=None):
    tool_args = tool_args if isinstance(tool_args, dict) else {}
    policies = policies if isinstance(policies, dict) else {}
    policy = policies.get(tool_name, policies.get("*", {}))
    blocked_patterns = policy.get("blocked_args", []) if isinstance(policy, dict) else []
    serialized = json.dumps(tool_args, sort_keys=True).lower()
    matched = [str(pattern) for pattern in blocked_patterns if str(pattern).lower() in serialized]
    decision = "deny" if matched else ("ask" if isinstance(policy, dict) and policy.get("require_approval") else "allow")
    return {
        "event": event or "preToolUse",
        "tool_name": tool_name,
        "decision": decision,
        "reason": "Blocked argument pattern detected." if matched else ("Policy requires approval." if decision == "ask" else "Allowed by local policy."),
        "matched_patterns": matched,
        "modified_args": tool_args,
        "hooks": ["sessionStart", "userPromptSubmitted", "preToolUse", "postToolUse", "errorOccurred", "sessionEnd"],
        "fail_closed_for_pre_tool": True,
        "offline_only": True,
    }


def validate_repository_memory(files, memories):
    source_map = {str(item.get("filename") or "").replace("\\", "/"): str(item.get("content") or "") for item in (files or [])[:500]}
    validated = []
    stale = []
    for memory in (memories or [])[:500]:
        if not isinstance(memory, dict):
            continue
        source = str(memory.get("source_file") or "").replace("\\", "/")
        excerpt = str(memory.get("excerpt") or "")
        valid = bool(source and source in source_map and excerpt and excerpt in source_map[source])
        record = {"title": str(memory.get("title") or "Untitled")[:200], "content": str(memory.get("content") or "")[:4000], "source_file": source, "excerpt": excerpt[:500], "confidence": float(memory.get("confidence", 0.5) or 0.5), "validated": valid, "scope": memory.get("scope", "repository"), "expires_at": memory.get("expires_at", "")}
        (validated if valid else stale).append(record)
    return {
        "validated_memories": validated,
        "stale_or_unverified": stale,
        "citation_required": True,
        "maintenance": ["Revalidate citations after source changes.", "Lower confidence when evidence is incomplete.", "Allow users to edit or delete repository facts.", "Expire unused facts rather than silently trusting stale context."],
        "offline_only": True,
    }


def plan_review_comment_resolution(comments, files=None, tests=None):
    filenames = {str(item.get("filename") or "").replace("\\", "/") for item in (files or []) if isinstance(item, dict)}
    test_names = [str(item) for item in (tests or [])]
    tasks = []
    for index, comment in enumerate((comments or [])[:200], start=1):
        if not isinstance(comment, dict):
            continue
        path = str(comment.get("path") or comment.get("filename") or "").replace("\\", "/")
        tasks.append({"id": f"review-{index}", "path": path, "line": comment.get("line"), "body": str(comment.get("body") or comment.get("message") or "")[:2000], "file_present": path in filenames, "status": "open", "suggested_action": "Prepare patch, run affected tests, then request re-review."})
    return {
        "comments": tasks,
        "open_count": len(tasks),
        "missing_files": sorted({item["path"] for item in tasks if item["path"] and not item["file_present"]}),
        "test_candidates": test_names[:100],
        "workflow": ["Group comments by file and symbol.", "Generate a preview-only patch.", "Run impacted tests and local review.", "Re-request review after the diff fingerprint changes.", "Resolve only approved comments."],
        "approval_required": True,
        "offline_only": True,
    }


def analyze_coverage_guidance(coverage):
    coverage = coverage if isinstance(coverage, dict) else {}
    files = []
    targets = []
    for filename, data in coverage.items():
        data = data if isinstance(data, dict) else {}
        covered = int(data.get("covered", 0) or 0)
        total = int(data.get("total", 0) or 0)
        missing = data.get("missing", []) if isinstance(data.get("missing", []), list) else []
        percent = round((covered / total) * 100, 2) if total else 100.0
        row = {"filename": str(filename).replace("\\", "/"), "covered": covered, "total": total, "missing": missing[:200], "percent": percent}
        files.append(row)
        if missing or percent < 80:
            targets.append({"filename": row["filename"], "priority": "high" if percent < 60 else "medium", "lines": missing[:50], "suggestion": "Generate focused boundary and failure-path tests for uncovered symbols."})
    total_lines = sum(item["total"] for item in files)
    covered_lines = sum(item["covered"] for item in files)
    return {
        "files": files,
        "targets": targets,
        "overall_percent": round((covered_lines / total_lines) * 100, 2) if total_lines else 100.0,
        "test_generation": {"mode": "coverage-guided", "requires_review": True, "avoid": ["testing implementation details only", "duplicating existing cases"]},
        "offline_only": True,
    }


def correlate_traces(traces, files=None, slow_threshold_ms=500):
    source_files = {str(item.get("filename") or "").replace("\\", "/"): str(item.get("content") or "") for item in (files or []) if isinstance(item, dict)}
    spans = []
    for trace in (traces or [])[:2000]:
        if not isinstance(trace, dict):
            continue
        attrs = trace.get("attributes") if isinstance(trace.get("attributes"), dict) else {}
        filename = str(trace.get("filename") or attrs.get("code.filepath") or attrs.get("code.file") or "").replace("\\", "/")
        line = trace.get("line") or attrs.get("code.lineno")
        try:
            duration = float(trace.get("duration_ms", trace.get("duration", 0)) or 0)
        except (TypeError, ValueError):
            duration = 0
        spans.append({"trace_id": trace.get("trace_id", ""), "span_id": trace.get("span_id", ""), "name": trace.get("name", "unknown"), "duration_ms": duration, "status": trace.get("status", "ok"), "filename": filename, "line": line, "source_available": filename in source_files})
    slow = [span for span in spans if span["duration_ms"] >= float(slow_threshold_ms)]
    errors = [span for span in spans if str(span["status"]).lower() in {"error", "failed", "exception"}]
    return {
        "spans": spans,
        "slow_spans": sorted(slow, key=lambda item: -item["duration_ms"])[:100],
        "error_spans": errors[:100],
        "hotspots": sorted({item["filename"] for item in slow + errors if item["filename"]}),
        "threshold_ms": float(slow_threshold_ms),
        "semantic_fields": ["trace_id", "span_id", "duration_ms", "status", "code.filepath", "code.lineno"],
        "offline_only": True,
    }


def manage_flaky_quarantine(tests, quarantine=None, today=""):
    quarantine = quarantine if isinstance(quarantine, dict) else {}
    today = today or time.strftime("%Y-%m-%d")
    records = []
    for test in (tests or [])[:500]:
        if not isinstance(test, dict) or not test.get("name"):
            continue
        name = str(test["name"])
        config = quarantine.get(name, {}) if isinstance(quarantine.get(name, {}), dict) else {}
        expiry = str(config.get("expires_at", ""))
        expired = bool(expiry and expiry < today)
        flaky = bool(test.get("flaky") or (test.get("failed", 0) and test.get("passed", 0)))
        records.append({"name": name, "flaky": flaky, "owner": config.get("owner", ""), "expires_at": expiry, "expired": expired, "quarantined": bool(config.get("quarantined", False)) and not expired, "release_blocking": flaky and not config.get("quarantined", False) or (expired and flaky)})
    return {
        "tests": records,
        "active_quarantine": [item["name"] for item in records if item["quarantined"]],
        "expired": [item["name"] for item in records if item["expired"]],
        "release_blocked_by": [item["name"] for item in records if item["release_blocking"]],
        "policy": {"owner_required": True, "expiry_required": True, "follow_up_required": True, "expired_quarantine_blocks_release": True},
        "offline_only": True,
    }
