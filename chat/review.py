from .quality import analyze_code_quality
from .security import scan_files


SEVERITY_PENALTIES = {
    "critical": 35,
    "high": 25,
    "error": 20,
    "medium": 12,
    "low": 4,
}


def review_gate(files, language="auto", diff="", tests=""):
    files = files or []
    quality_findings = []
    for item in files:
        result = analyze_code_quality(
            str(item.get("content") or ""),
            language,
            "all",
        )
        for finding in result["findings"]:
            finding = dict(finding)
            finding["filename"] = item.get("filename", "editor-buffer")
            quality_findings.append(finding)

    security = scan_files(files)
    security_findings = security["findings"]
    findings = [
        {
            "source": "quality",
            "severity": item["severity"],
            "message": item["message"],
            "filename": item.get("filename", "editor-buffer"),
            "line": item.get("line"),
        }
        for item in quality_findings
    ] + [
        {
            "source": "security",
            "severity": item["severity"],
            "message": item["message"],
            "filename": item.get("filename", "editor-buffer"),
            "line": item.get("line"),
        }
        for item in security_findings
    ]
    score = max(0, 100 - sum(SEVERITY_PENALTIES.get(item["severity"], 5) for item in findings))
    checks = [
        {"name": "Diff supplied", "passed": bool(diff.strip()), "detail": f"{len(diff.splitlines())} diff line(s) reviewed."},
        {"name": "Tests supplied", "passed": bool(tests.strip()), "detail": "Test evidence supplied." if tests.strip() else "Add or run tests before merging."},
        {"name": "Quality scan", "passed": not quality_findings, "detail": f"{len(quality_findings)} quality finding(s)."},
        {"name": "Security scan", "passed": not security_findings, "detail": f"{len(security_findings)} security finding(s)."},
    ]
    blocking = any(item["severity"] in {"critical", "high", "error"} for item in findings)
    ready = bool(files) and not blocking and bool(tests.strip()) and score >= 80
    return {
        "ready": ready,
        "score": score,
        "summary": "Ready to merge." if ready else "Changes need review before merging.",
        "checks": checks,
        "findings": findings[:100],
        "diff_lines": len(diff.splitlines()),
    }
