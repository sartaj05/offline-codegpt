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
