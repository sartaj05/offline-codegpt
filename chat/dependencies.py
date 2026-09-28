import json
import re


def _requirement_name_version(line):
    match = re.match(r"^\s*([A-Za-z0-9_.-]+)\s*(==|~=|>=|<=|>|<)?\s*([^;\s]+)?", line)
    if not match:
        return None
    name, operator, version = match.groups()
    return {
        "name": name,
        "version": version or "unversioned",
        "operator": operator or "",
        "pinned": operator == "==",
    }


def inventory_dependencies(files):
    dependencies = []
    for item in files or []:
        filename = str(item.get("filename") or "")
        content = str(item.get("content") or "")
        lower = filename.lower()
        if lower.endswith(("requirements.txt", "requirements-dev.txt")):
            for line in content.splitlines():
                if line.strip() and not line.lstrip().startswith(("#", "-")):
                    parsed = _requirement_name_version(line)
                    if parsed:
                        parsed.update({"manager": "pip", "source": filename})
                        dependencies.append(parsed)
        elif lower.endswith("package.json"):
            try:
                package = json.loads(content)
            except (TypeError, ValueError):
                continue
            for group in ("dependencies", "devDependencies"):
                for name, version in package.get(group, {}).items():
                    value = str(version)
                    dependencies.append({
                        "name": name,
                        "version": value,
                        "operator": value[:1] if value[:1] in "=~^><*" else "",
                        "pinned": bool(re.fullmatch(r"=\d+(?:\.\d+){1,2}", value)),
                        "manager": "npm",
                        "source": filename,
                        "group": group,
                    })
    return dependencies


def analyze_dependencies(files):
    dependencies = inventory_dependencies(files)
    findings = []
    upgrade_plan = []
    for item in dependencies:
        version = item["version"].lower()
        if not item["pinned"] or version in {"latest", "*", "unversioned"}:
            findings.append({
                "severity": "medium",
                "package": item["name"],
                "message": "Use an exact version before production release.",
                "source": item["source"],
            })
            upgrade_plan.append(f"Pin {item['name']} ({item['manager']}) to a tested exact version.")
        elif item.get("operator") in {">", ">="}:
            upgrade_plan.append(f"Test the allowed range for {item['name']} before upgrading.")
    if not dependencies:
        findings.append({
            "severity": "info",
            "package": "",
            "message": "No supported dependency manifest was detected.",
            "source": "",
        })
    return {
        "summary": f"{len(dependencies)} dependency(ies), {len(findings)} finding(s).",
        "dependencies": dependencies,
        "findings": findings,
        "upgrade_plan": upgrade_plan,
        "limitations": "Offline analysis checks manifest hygiene only; it does not query live vulnerability advisories.",
    }
