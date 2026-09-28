import re


def _symbols(filename, content):
    found = []
    patterns = [
        r"^\s*(?:async\s+)?def\s+([A-Za-z_]\w*)",
        r"^\s*class\s+([A-Za-z_]\w*)",
        r"^\s*(?:export\s+)?function\s+([A-Za-z_]\w*)",
        r"^\s*(?:export\s+)?(?:const|let|var)\s+([A-Za-z_]\w*)\s*=",
    ]
    for line in (content or "").splitlines():
        for pattern in patterns:
            match = re.search(pattern, line)
            if match:
                found.append(match.group(1))
                break
    return found[:40]


def generate_documentation(files, doc_type="readme", project_name="Local project", change_summary=""):
    files = files or []
    project_name = (project_name or "Local project").strip()[:120]
    file_lines = []
    symbol_lines = []
    for item in files[:100]:
        filename = str(item.get("filename") or "untitled").replace("\n", "")
        content = str(item.get("content") or "")
        file_lines.append(f"- {filename} ({len(content)} characters)")
        symbols = _symbols(filename, content)
        if symbols:
            symbol_lines.append(f"- {filename}: " + ", ".join(symbols))

    if doc_type == "api":
        return (
            f"# {project_name} API reference\n\n"
            "Generated from the indexed local source files.\n\n"
            "## Discovered modules and symbols\n\n"
            + ("\n".join(symbol_lines) or "No public functions, classes, or handlers were detected.")
            + "\n\n## Maintenance notes\n\n"
            "- Review request and response shapes against the current implementation.\n"
            "- Add examples for the most important endpoints.\n"
        )
    if doc_type == "changelog":
        summary = change_summary.strip() or "Initial local documentation snapshot."
        return (
            f"# Changelog\n\n## Unreleased\n\n"
            f"- {summary}\n"
            "- Documentation generated from the current project workspace.\n"
        )
    if doc_type == "onboarding":
        return (
            f"# {project_name} developer onboarding\n\n"
            "## Project map\n\n"
            + ("\n".join(file_lines) or "- No files supplied yet.")
            + "\n\n## First setup\n\n"
            "1. Create the local environment and install project dependencies.\n"
            "2. Configure local environment variables without committing secrets.\n"
            "3. Start the development server and run the test suite.\n"
            "4. Open a small branch, make a focused change, and review the diff.\n\n"
            "## Working agreement\n\n"
            "- Keep changes small and covered by tests.\n"
            "- Run the local security scan before committing.\n"
            "- Record important architecture decisions near the code they explain.\n"
        )
    return (
        f"# {project_name}\n\n"
        "## Overview\n\n"
        "A local project documented from the current Syntax Local AI workspace.\n\n"
        "## Project files\n\n"
        + ("\n".join(file_lines) or "- No files supplied yet.")
        + "\n\n## Main symbols\n\n"
        + ("\n".join(symbol_lines) or "No symbols were detected yet.")
        + "\n\n## Development\n\n"
        "Run the project tests before committing changes. Keep secrets in local environment configuration.\n"
    )
