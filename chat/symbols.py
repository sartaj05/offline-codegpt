import ast
import re


def extract_symbols(filename, text):
    symbols = []
    language = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
    if language == "py":
        try:
            tree = ast.parse(text)
        except SyntaxError:
            tree = None
        if tree:
            for node in ast.walk(tree):
                if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                    kind = "class" if isinstance(node, ast.ClassDef) else "function"
                    symbols.append({
                        "name": node.name,
                        "kind": kind,
                        "line_start": node.lineno,
                        "line_end": getattr(node, "end_lineno", node.lineno),
                        "signature": ast.unparse(node.args) if kind == "function" and hasattr(ast, "unparse") else node.name,
                    })
            for node in tree.body:
                if isinstance(node, (ast.Import, ast.ImportFrom)):
                    names = [item.name for item in getattr(node, "names", [])]
                    symbols.append({"name": ", ".join(names)[:240], "kind": "import", "line_start": node.lineno, "line_end": node.lineno, "signature": "import"})
            return symbols
    patterns = [
        ("class", r"\bclass\s+([A-Za-z_$][\w$]*)"),
        ("function", r"\b(?:function|def)\s+([A-Za-z_$][\w$]*)\s*\("),
        ("function", r"\b([A-Za-z_$][\w$]*)\s*=\s*\([^\n]*\)\s*=>"),
        ("import", r"^\s*(?:import|from)\s+([^;\n]+)"),
    ]
    lines = text.splitlines()
    for kind, pattern in patterns:
        for index, line in enumerate(lines, start=1):
            match = re.search(pattern, line)
            if match:
                symbols.append({"name": match.group(1).strip()[:240], "kind": kind, "line_start": index, "line_end": index, "signature": line.strip()[:500]})
    return symbols[:500]
