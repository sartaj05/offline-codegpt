import hashlib
import json
from datetime import datetime, timezone

from .dependencies import inventory_dependencies


def _digest(value):
    return hashlib.sha256(value.encode("utf-8", errors="ignore")).hexdigest()


def generate_provenance(files, artifact_name="local-artifact", commit="unknown", builder="Syntax Local AI"):
    files = files or []
    subjects = []
    for item in files[:100]:
        filename = str(item.get("filename") or "untitled")
        content = str(item.get("content") or "")
        subjects.append({"name": filename, "digest": {"sha256": _digest(content)}})
    dependencies = inventory_dependencies(files)
    materials = [
        {
            "uri": f"pkg:{item['manager']}/{item['name']}@{item['version']}",
            "digest": {"sha256": _digest(f"{item['name']}@{item['version']}")},
        }
        for item in dependencies
    ]
    statement = {
        "predicateType": "https://slsa.dev/provenance/v1",
        "subject": [{"name": artifact_name, "digest": {"sha256": _digest(json.dumps(subjects, sort_keys=True))}}],
        "predicate": {
            "buildDefinition": {
                "buildType": "https://syntax-local-ai.dev/build/offline",
                "externalParameters": {"commit": commit, "builder": builder},
                "resolvedDependencies": materials,
            },
            "runDetails": {
                "builder": {"id": "local://syntax-local-ai"},
                "metadata": {"invocationId": _digest(artifact_name + commit), "startedOn": datetime.now(timezone.utc).isoformat()},
            },
        },
    }
    return json.dumps(statement, indent=2)


def verify_provenance(document):
    try:
        data = json.loads(document)
    except (TypeError, ValueError):
        return {"valid": False, "checks": [{"name": "JSON", "passed": False, "detail": "Invalid JSON."}]}
    checks = [
        {"name": "Predicate type", "passed": bool(data.get("predicateType")), "detail": "Provenance predicate is present."},
        {"name": "Subject digest", "passed": bool(data.get("subject") and data["subject"][0].get("digest", {}).get("sha256")), "detail": "Artifact digest is present."},
        {"name": "Build definition", "passed": bool(data.get("predicate", {}).get("buildDefinition")), "detail": "Build metadata is present."},
        {"name": "Builder identity", "passed": bool(data.get("predicate", {}).get("runDetails", {}).get("builder", {}).get("id")), "detail": "Builder identity is present."},
    ]
    return {"valid": all(check["passed"] for check in checks), "checks": checks}
