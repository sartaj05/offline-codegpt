import re


def generate_playwright_test(base_url="http://127.0.0.1:8000", flow="", snapshot_name="home"):
    base_url = (base_url or "http://127.0.0.1:8000").strip().rstrip("/")
    flow = (flow or "Open the home page and verify the main interface.").strip()
    safe_name = re.sub(r"[^a-z0-9]+", "-", snapshot_name.lower()).strip("-") or "home"
    return (
        'import { test, expect } from "@playwright/test";\n\n'
        f'test("{safe_name} user flow", async ({{ page }}) => {{\n'
        f'  await page.goto("{base_url}");\n'
        '  await expect(page).toHaveTitle(/.+/);\n'
        f'  // Requested flow: {flow.replace(chr(10), " ")[:500]}\n'
        f'  await expect(page).toHaveScreenshot("{safe_name}.png", {{ fullPage: true }});\n'
        '});\n'
    )


def analyze_browser_report(report):
    lines = [line.strip() for line in (report or "").splitlines() if line.strip()]
    passed = []
    failed = []
    snapshots = []
    for line in lines:
        lower = line.lower()
        if "snapshot" in lower or "screenshot" in lower:
            snapshots.append(line[:500])
        if re.search(r"\b(pass|passed|ok)\b", lower):
            passed.append(line[:500])
        if re.search(r"\b(fail|failed|error)\b", lower):
            failed.append(line[:500])
    return {
        "summary": f"{len(passed)} passed, {len(failed)} failed, {len(snapshots)} visual event(s).",
        "passed": passed[:50],
        "failed": failed[:50],
        "visual_events": snapshots[:50],
        "next_steps": [
            "Review failed selectors and reproduce the flow locally.",
            "Regenerate a snapshot only after confirming the UI change is intentional.",
        ] if failed or snapshots else ["Run the generated Playwright test to create a baseline report."],
    }
