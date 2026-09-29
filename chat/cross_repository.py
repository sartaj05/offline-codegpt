import re


def analyze_cross_repository(repositories):
    repositories = repositories or []
    normalized = []
    for repository in repositories[:20]:
        name = str(repository.get("name") or "repository").strip()[:120]
        files = repository.get("files") or []
        normalized.append({
            "name": name,
            "files": [
                {"filename": str(item.get("filename") or "untitled")[:300], "content": str(item.get("content") or "")[:100000]}
                for item in files[:100]
            ],
        })

    nodes = []
    edges = []
    module_targets = {}
    for repository in normalized:
        for item in repository["files"]:
            filename = item["filename"].replace(chr(92), "/")
            node_id = repository["name"] + "/" + filename
            module_targets.setdefault(filename.rsplit("/", 1)[-1].rsplit(".", 1)[0], []).append((repository["name"], node_id))
            nodes.append({"id": node_id, "repository": repository["name"], "filename": filename, "lines": len(item["content"].splitlines())})

    for repository in normalized:
        for item in repository["files"]:
            filename = item["filename"].replace(chr(92), "/")
            source_id = repository["name"] + "/" + filename
            for line in item["content"].splitlines():
                match = re.search(r"(?:from|import)[ ]+([A-Za-z0-9_./-]+)", line.strip())
                if not match:
                    continue
                module = match.group(1).split(".")[0].strip("./")
                for target_repo, target_id in module_targets.get(module, []):
                    if target_id != source_id:
                        edges.append({
                            "from": source_id,
                            "to": target_id,
                            "from_repository": repository["name"],
                            "to_repository": target_repo,
                            "cross_repository": target_repo != repository["name"],
                            "kind": "import",
                        })

    cross_edges = [edge for edge in edges if edge["cross_repository"]]
    impacts = []
    for repository in normalized:
        incoming = sum(1 for edge in cross_edges if edge["to_repository"] == repository["name"])
        outgoing = sum(1 for edge in cross_edges if edge["from_repository"] == repository["name"])
        impacts.append({
            "repository": repository["name"],
            "incoming_dependencies": incoming,
            "outgoing_dependencies": outgoing,
            "risk": "high" if incoming + outgoing >= 5 else ("medium" if incoming + outgoing else "low"),
        })
    return {
        "summary": f"{len(normalized)} repos, {len(nodes)} files, {len(cross_edges)} cross-repository relationship(s).",
        "repositories": [{"name": repository["name"], "files": len(repository["files"])} for repository in normalized],
        "nodes": nodes[:500],
        "edges": edges[:500],
        "cross_edges": cross_edges[:500],
        "impacts": sorted(impacts, key=lambda item: (-item["incoming_dependencies"] - item["outgoing_dependencies"], item["repository"])),
        "warnings": ["Cross-repository dependencies detected." if cross_edges else "No cross-repository dependencies detected."],
    }
