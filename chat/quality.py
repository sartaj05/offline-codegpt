import ast
import re


def _finding(category, severity, message, line=None):
    return {
        "category": category,
        "severity": severity,
        "message": message,
        "line": line,
    }


def _python_findings(code):
    findings = []
    try:
        tree = ast.parse(code)
    except SyntaxError as ex:
        return [_finding("bug", "error", f"Syntax error: {ex.msg}", ex.lineno)]

    for node in ast.walk(tree):
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
            if node.func.id in {"eval", "exec"}:
                findings.append(_finding("security", "high", f"Avoid dynamic {node.func.id}(); it can execute untrusted input.", node.lineno))
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
            if node.func.attr in {"system", "popen"}:
                findings.append(_finding("security", "high", f"Review os.{node.func.attr}() for command injection risk.", node.lineno))
        if isinstance(node, ast.ExceptHandler) and node.type is None:
            findings.append(_finding("lint", "medium", "Bare except catches errors too broadly.", node.lineno))
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            if len(node.body) > 35:
                findings.append(_finding("lint", "medium", f"Function {node.name} is long; consider splitting it.", node.lineno))

    return findings


def _text_findings(code, language):
    findings = []
    lines = code.splitlines()
    for number, line in enumerate(lines, start=1):
        if len(line) > 100:
            findings.append(_finding("lint", "low", "Line exceeds 100 characters.", number))
        if line.rstrip() != line:
            findings.append(_finding("lint", "low", "Trailing whitespace.", number))
        if re.search(r"\\b(TODO|FIXME)\\b", line, re.IGNORECASE):
            findings.append(_finding("bug", "low", "Unresolved TODO/FIXME marker.", number))

    if language in {"javascript", "js", "typescript", "ts"}:
        patterns = [
            (r"\\beval\\s*\\(", "high", "Avoid eval(); it can execute untrusted input."),
            (r"\\.innerHTML\\s*=", "medium", "Review innerHTML assignment for XSS risk."),
            (r"document\\.write\\s*\\(", "medium", "document.write() can replace the document unexpectedly."),
            (r"(^|[^=])==([^=]|$)", "low", "Prefer strict equality (===) where appropriate."),
        ]
        for pattern, severity, message in patterns:
            for match in re.finditer(pattern, code, re.MULTILINE):
                line = code[:match.start()].count("\\n") + 1
                category = "security" if severity in {"high", "medium"} else "lint"
                findings.append(_finding(category, severity, message, line))

    if language == "sql" and re.search(r"SELECT\\s+\\*", code, re.IGNORECASE):
        findings.append(_finding("lint", "low", "Select explicit columns instead of SELECT * where possible."))

    return findings


def _test_template(code, language):
    if language in {"python", "py", "auto"}:
        names = re.findall(r"(?:def|class)\\s+([A-Za-z_]\\w*)", code)
        target = names[0] if names else "your_function"
        return f"from {target} import {target}\\n\\n\\ndef test_{target}_happy_path():\\n    # Arrange\\n    # Act\\n    result = {target}(...)\\n    # Assert\\n    assert result is not None\\n"
    if language in {"javascript", "js", "typescript", "ts"}:
        return "describe('module behavior', () => {\\n  test('handles the happy path', () => {\\n    // Arrange\\n    // Act\\n    // Assert\\n  });\\n});\\n"
    if language == "sql":
        return "-- Add a fixture, run the query, and assert expected rows.\\n"
    return "# Add Arrange / Act / Assert cases for the main behavior.\\n"


def analyze_code_quality(code, language="auto", mode="all"):
    normalized = language.lower()
    findings = []
    if normalized in {"python", "py", "auto"}:
        findings.extend(_python_findings(code))
    findings.extend(_text_findings(code, normalized))

    if mode in {"security", "bugs", "lint"}:
        category = "security" if mode == "security" else "bug" if mode == "bugs" else "lint"
        findings = [finding for finding in findings if finding["category"] == category]

    summary = "No issues found." if not findings else f"Found {len(findings)} issue(s)."
    return {
        "summary": summary,
        "findings": findings,
        "test_template": _test_template(code, normalized) if mode in {"all", "tests"} else "",
    }
