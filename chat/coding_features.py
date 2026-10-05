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
