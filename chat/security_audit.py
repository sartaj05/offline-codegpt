"""Read-only local audit for high-risk coding and tool execution boundaries."""

import ast
from pathlib import Path


def _call_name(node):
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        parent = _call_name(node.value)
        return f"{parent}.{node.attr}" if parent else node.attr
    return ""


def audit_project(root):
    root = Path(root).resolve()
    findings = []
    scanned = 0
    for path in sorted(root.rglob("*.py")):
        if any(part in {".git", "venv", ".venv", "__pycache__", "staticfiles"} for part in path.parts):
            continue
        scanned += 1
        try:
            tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        except (OSError, UnicodeDecodeError, SyntaxError) as exc:
            findings.append({"severity": "high", "category": "syntax", "file": str(path.relative_to(root)), "message": str(exc)[:240]})
            continue
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue
            name = _call_name(node.func)
            shell_true = any(keyword.arg == "shell" and isinstance(keyword.value, ast.Constant) and keyword.value.value is True for keyword in node.keywords)
            if name in {"os.system", "os.popen", "subprocess.Popen", "subprocess.run", "subprocess.call", "subprocess.check_call", "subprocess.check_output"} and shell_true:
                findings.append({"severity": "high", "category": "shell", "file": str(path.relative_to(root)), "line": node.lineno, "message": "Shell-enabled process execution requires an explicit reviewed boundary."})
            elif name in {"eval", "exec"}:
                findings.append({"severity": "high", "category": "code-execution", "file": str(path.relative_to(root)), "line": node.lineno, "message": "Dynamic code execution requires an explicit reviewed boundary."})
            elif name in {"os.system", "os.popen"}:
                findings.append({"severity": "medium", "category": "shell", "file": str(path.relative_to(root)), "line": node.lineno, "message": "Direct shell execution should remain behind the sandbox and audit log."})

    required_boundaries = {
        "coding_security_middleware": (root / "chat" / "middleware.py").exists(),
        "payload_sanitizer": "sanitize_coding_payload" in (root / "chat" / "security.py").read_text(encoding="utf-8"),
        "sandbox_runner": (root / "chat" / "sandbox.py").exists(),
        "tool_policy": "ToolSecurityPolicy" in (root / "chat" / "models.py").read_text(encoding="utf-8"),
    }
    for name, present in required_boundaries.items():
        if not present:
            findings.append({"severity": "high", "category": "boundary", "file": "", "message": f"Required security boundary is missing: {name}."})
    return {
        "success": not any(item["severity"] == "high" for item in findings),
        "root": str(root),
        "scanned_files": scanned,
        "findings": findings[:200],
        "summary": {severity: sum(item["severity"] == severity for item in findings) for severity in ("high", "medium", "low")},
        "scope": "read-only static audit; review all findings before production use",
    }
