"""Offline coding-workspace services.

These helpers deliberately use local parsing and subprocess contracts only. They
do not send source code to a remote service, which keeps the coding workspace
usable while the app is in offline mode.
"""

import ast
import difflib
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
