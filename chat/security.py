import json
import re


MAX_CODING_PAYLOAD_BYTES = 250_000
_PATH_KEYS = {"filename", "filepath", "path", "file", "cwd", "directory", "worktree"}
_SECRET_KEYS = {"api_key", "apikey", "authorization", "password", "passwd", "private_key", "secret", "token"}


def _safe_relative_path(value):
    normalized = str(value or "").replace("\\", "/").strip()
    if not normalized or normalized.startswith("/") or re.match(r"^[A-Za-z]:", normalized):
        return False
    return all(part not in {"..", ""} for part in normalized.split("/"))


def _redact_coding_string(value):
    masked = str(value)
    replacements = [
        (r"(?i)(authorization\s*:\s*bearer\s+)[A-Za-z0-9._~+/=-]+", r"\1[REDACTED_TOKEN]"),
        (r"(?i)\b(sk-[A-Za-z0-9_-]{16,}|gh[pousr]_[A-Za-z0-9_-]{16,})\b", "[REDACTED_API_KEY]"),
        (r"-----BEGIN [A-Z ]+ PRIVATE KEY-----[\s\S]*?-----END [A-Z ]+ PRIVATE KEY-----", "[REDACTED_PRIVATE_KEY]"),
        (r"(?i)(\b(?:password|passwd|secret|token|api[_-]?key)\s*[:=]\s*)([^\s,;]+)", r"\1[REDACTED_SECRET]"),
    ]
    for pattern, replacement in replacements:
        masked = re.sub(pattern, replacement, masked)
    return masked


def sanitize_coding_payload(value, max_bytes=MAX_CODING_PAYLOAD_BYTES):
    """Validate local paths and redact secrets before coding data is persisted or echoed."""
    try:
        encoded = json.dumps(value, ensure_ascii=False).encode("utf-8")
    except (TypeError, ValueError) as exc:
        raise ValueError("Coding payload must contain JSON-compatible values.") from exc
    if len(encoded) > max_bytes:
        raise ValueError(f"Coding payload exceeds the {max_bytes:,}-byte safety limit.")

    def visit(item, key=None):
        if isinstance(item, dict):
            clean = {}
            for raw_key, raw_value in item.items():
                name = str(raw_key)
                normalized_key = re.sub(r"[^a-z0-9]", "", name.lower())
                if normalized_key in {re.sub(r"[^a-z0-9]", "", candidate) for candidate in _SECRET_KEYS}:
                    clean[name] = "[REDACTED_SECRET]"
                    continue
                if name.lower() in _PATH_KEYS and isinstance(raw_value, str) and not _safe_relative_path(raw_value):
                    raise ValueError(f"Unsafe relative path in '{name}'.")
                clean[name] = visit(raw_value, name)
            return clean
        if isinstance(item, list):
            if len(item) > 500:
                raise ValueError("Coding payload contains too many list items.")
            return [visit(child, key) for child in item]
        if isinstance(item, str):
            return _redact_coding_string(item)
        return item

    return visit(value)


def redact_coding_response(text):
    """Always mask common credentials in coding API responses and audit text."""
    masked = str(text)
    for pattern, replacement in (
        (r"(?i)(authorization\s*:\s*bearer\s+)[A-Za-z0-9._~+/=-]+", r"\1[REDACTED_TOKEN]"),
        (r"(?i)\b(sk-[A-Za-z0-9_-]{16,}|gh[pousr]_[A-Za-z0-9_-]{16,})\b", "[REDACTED_API_KEY]"),
        (r"-----BEGIN [A-Z ]+ PRIVATE KEY-----[\s\S]*?-----END [A-Z ]+ PRIVATE KEY-----", "[REDACTED_PRIVATE_KEY]"),
        (r"(?i)(\b(?:password|passwd|secret|token|api[_-]?key)\s*[:=]\s*)([^\s,;]+)", r"\1[REDACTED_SECRET]"),
    ):
        masked = re.sub(pattern, replacement, masked)
    return masked


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
