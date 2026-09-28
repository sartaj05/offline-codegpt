import json
import re


SECRET_PATTERNS = [
    ("secret-generic", "high", re.compile(r"""(?i)\b(api[_-]?key|secret|token|password)\b\s*[:=]\s*['"][^'"]{8,}""")),
    ("aws-access-key", "critical", re.compile(r"\bAKIA[0-9A-Z]{16}\b")),
    ("github-token", "critical", re.compile(r"\bgh[pousr]_[A-Za-z0-9_]{20,}\b")),
    ("private-key", "critical", re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----")),
    ("jwt", "high", re.compile(r"\beyJ[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}\b")),
]


def _finding(rule, severity, message, filename, line):
    return {
        "rule": rule,
        "severity": severity,
        "message": message,
        "filename": filename,
        "line": line,
    }


def _source_findings(filename, code):
    findings = []
    for line_number, line in enumerate(code.splitlines(), 1):
        for rule, severity, pattern in SECRET_PATTERNS:
            if pattern.search(line):
                findings.append(_finding(rule, severity, "Potential credential or secret detected.", filename, line_number))
        if re.search(r"(?i)\b(eval|exec)\s*\(", line):
            findings.append(_finding("dynamic-execution", "high", "Dynamic code execution can execute untrusted input.", filename, line_number))
        if re.search(r"(?i)\bos\.system\s*\(|\bsubprocess\.(run|popen|call)\s*\(", line):
            findings.append(_finding("command-execution", "high", "Review command execution for injection and privilege risks.", filename, line_number))
        if re.search(r"(?i)\.innerHTML\s*=", line):
            findings.append(_finding("xss-innerhtml", "medium", "Assigning untrusted content to innerHTML can create XSS.", filename, line_number))
        if re.search(r"(?i)(select|update|delete|insert).*[+%]\s*[^'\"]", line):
            findings.append(_finding("sql-concatenation", "high", "SQL string concatenation may allow injection; use parameters.", filename, line_number))
    return findings


def _dependency_inventory(filename, content):
    components = []
    lower = filename.lower()
    if lower.endswith(("requirements.txt", "requirements-dev.txt")):
        for line in content.splitlines():
            line = line.strip()
            if not line or line.startswith("#") or line.startswith("-"):
                continue
            match = re.match(r"([A-Za-z0-9_.-]+)\s*(==|>=|<=|~=|>|<)?\s*([A-Za-z0-9_.-]+)?", line)
            if match:
                name, operator, version = match.groups()
                components.append({
                    "name": name,
                    "version": version or "unversioned",
                    "pinned": operator == "==",
                    "source": filename,
                })
    elif lower.endswith("package.json"):
        try:
            data = json.loads(content)
        except (TypeError, ValueError):
            return []
        for group in ("dependencies", "devDependencies"):
            for name, version in data.get(group, {}).items():
                components.append({
                    "name": name,
                    "version": version,
                    "pinned": bool(re.fullmatch(r"[=~^]?\\d+(?:\\.\\d+){1,2}", str(version))),
                    "source": filename,
                })
    return components


def scan_files(files):
    findings = []
    components = []
    licenses = []
    for item in files:
        filename = str(item.get("filename") or "editor-buffer")
        content = str(item.get("content") or "")
        findings.extend(_source_findings(filename, content))
        components.extend(_dependency_inventory(filename, content))
        license_match = re.search(r"SPDX-License-Identifier:\s*([A-Za-z0-9.+-]+)", content)
        licenses.append({
            "filename": filename,
            "license": license_match.group(1) if license_match else "UNKNOWN",
        })
    for component in components:
        if not component["pinned"]:
            findings.append(_finding(
                "unpinned-dependency",
                "medium",
                f"Dependency {component['name']} is not pinned to an exact version.",
                component["source"],
                None,
            ))
    sbom = {
        "bomFormat": "SPDX",
        "spdxVersion": "SPDX-2.3",
        "name": "Syntax Local AI scan",
        "packages": [
            {
                "name": component["name"],
                "versionInfo": component["version"],
                "downloadLocation": "NOASSERTION",
            }
            for component in components
        ],
    }
    return {
        "summary": "No local security findings." if not findings else f"Found {len(findings)} security finding(s).",
        "findings": findings,
        "dependencies": components,
        "licenses": licenses,
        "sbom": sbom,
        "limitations": "Offline scan: dependency CVE freshness is not verified without an online advisory database.",
    }
