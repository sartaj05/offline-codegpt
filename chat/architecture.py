import re


def _module_name(filename):
    return filename.replace("\\", "/").rsplit("/", 1)[-1].rsplit(".", 1)[0]


def analyze_architecture(files):
    files = files or []
    names = [str(item.get("filename") or "untitled") for item in files]
    modules = {_module_name(name): name for name in names}
    nodes = []
    edges = []
    symbols = []
    routes = []
    for item in files:
        filename = str(item.get("filename") or "untitled")
        content = str(item.get("content") or "")
        module = _module_name(filename)
        nodes.append({"id": filename, "module": module, "lines": len(content.splitlines())})
        for match in re.finditer(r"^\s*(?:from|import)\s+([A-Za-z0-9_./-]+)", content, re.MULTILINE):
            imported = match.group(1).split(".")[0].strip("./")
            target = modules.get(imported)
            if target and target != filename:
                edges.append({"from": filename, "to": target, "kind": "import"})
        for match in re.finditer(r"^\s*(?:async\s+def|def|class|function)\s+([A-Za-z_]\w*)", content, re.MULTILINE):
            symbols.append({"file": filename, "name": match.group(1)})
        for match in re.finditer(r"\b(?:path|route)\s*\(\s*[\"']([^\"']+)", content):
            routes.append({"file": filename, "route": match.group(1)})

    adjacency = {}
    for edge in edges:
        adjacency.setdefault(edge["from"], []).append(edge["to"])
    cycles = []

    def visit(node, stack):
        if node in stack:
            cycle = stack[stack.index(node):] + [node]
            if cycle not in cycles:
                cycles.append(cycle)
            return
        for target in adjacency.get(node, []):
            visit(target, stack + [node])

    for node in names:
        visit(node, [])
    return {
        "summary": f"{len(nodes)} module(s), {len(edges)} relationship(s), {len(symbols)} symbol(s).",
        "nodes": nodes,
        "edges": edges,
        "symbols": symbols[:200],
        "routes": routes[:100],
        "cycles": cycles[:50],
        "warnings": ["Circular dependencies detected." if cycles else "No circular dependencies detected."],
    }
