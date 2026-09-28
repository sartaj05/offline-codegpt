import json
import re


METHODS = {"get", "post", "put", "patch", "delete", "options", "head"}


def _normal_path(path):
    path = re.sub(r"<[^>]+>", "{id}", path)
    path = path.strip()
    if not path.startswith("/"):
        path = "/" + path
    return path.rstrip("/") or "/"


def _code_endpoints(code):
    endpoints = set()
    for match in re.finditer(
        r"(?:path|route)\s*\(\s*[\"']([^\"']+)[\"']|"
        r"@\w+\.(?:route|get|post|put|delete)\s*\(\s*[\"']([^\"']+)",
        code or "",
    ):
        path = match.group(1) or match.group(2)
        method_match = re.search(r"@\w+\.(get|post|put|delete)", match.group(0), re.IGNORECASE)
        endpoints.add((method_match.group(1).lower() if method_match else "get", _normal_path(path)))
    return sorted(endpoints)


def _spec_endpoints(spec):
    endpoints = set()
    if not isinstance(spec, dict):
        return []
    for path, operations in (spec.get("paths") or {}).items():
        for method in operations:
            if method.lower() in METHODS:
                endpoints.add((method.lower(), _normal_path(path)))
    return sorted(endpoints)


def analyze_api_contract(spec_text="", code=""):
    try:
        spec = json.loads(spec_text) if spec_text.strip() else {}
    except (TypeError, ValueError):
        return {"error": "The OpenAPI document is not valid JSON."}
    spec_endpoints = set(_spec_endpoints(spec))
    code_endpoints = set(_code_endpoints(code))
    undocumented = sorted(code_endpoints - spec_endpoints)
    stale = sorted(spec_endpoints - code_endpoints) if code_endpoints else []
    suggested = {"openapi": "3.0.3", "info": {"title": "Local API", "version": "0.1.0"}, "paths": {}}
    for method, path in sorted(spec_endpoints | code_endpoints):
        suggested["paths"].setdefault(path, {})[method] = {
            "responses": {"200": {"description": "Successful response"}},
        }
    return {
        "summary": f"{len(code_endpoints)} implemented endpoint(s), {len(spec_endpoints)} documented endpoint(s).",
        "implemented": [{"method": method.upper(), "path": path} for method, path in sorted(code_endpoints)],
        "documented": [{"method": method.upper(), "path": path} for method, path in sorted(spec_endpoints)],
        "undocumented": [{"method": method.upper(), "path": path} for method, path in undocumented],
        "stale_documentation": [{"method": method.upper(), "path": path} for method, path in stale],
        "breaking_risks": [
            "Undocumented endpoint detected; add it to the contract before release.",
        ] * bool(undocumented),
        "suggested_openapi": json.dumps(suggested, indent=2),
    }
