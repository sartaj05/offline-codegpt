import re


def _lines(value):
    return [line.strip() for line in (value or "").splitlines() if line.strip()]


def analyze_incident(logs="", traces="", metrics=""):
    log_lines = _lines(logs)
    trace_lines = _lines(traces)
    metric_lines = _lines(metrics)
    timeline = []
    errors = []
    warnings = []
    for index, line in enumerate(log_lines, start=1):
        lower = line.lower()
        severity = "error" if re.search(r"\b(error|fatal|failed|exception|traceback)\b", lower) else "warning" if "warn" in lower else "info"
        timeline.append({"source": "log", "line": index, "severity": severity, "message": line[:500]})
        if severity == "error":
            errors.append(line[:500])
        elif severity == "warning":
            warnings.append(line[:500])
    for index, line in enumerate(trace_lines, start=1):
        timeline.append({"source": "trace", "line": index, "severity": "trace", "message": line[:500]})
    for index, line in enumerate(metric_lines, start=1):
        timeline.append({"source": "metric", "line": index, "severity": "metric", "message": line[:500]})

    combined = "\n".join(log_lines + trace_lines + metric_lines).lower()
    causes = []
    actions = []
    if "connection refused" in combined or "timeout" in combined:
        causes.append("A dependent service or network path is unavailable.")
        actions.append("Check service health, DNS, ports, timeouts, and recent deployment changes.")
    if "out of memory" in combined or "memoryerror" in combined:
        causes.append("The process exceeded its memory budget.")
        actions.append("Inspect memory limits, payload size, and worker concurrency before restarting.")
    if "permission denied" in combined or "unauthorized" in combined or "forbidden" in combined:
        causes.append("An identity, role, or file-permission change may be blocking the operation.")
        actions.append("Review the actor, changed permissions, and least-privilege policy.")
    if "database" in combined and ("locked" in combined or "deadlock" in combined or "connection" in combined):
        causes.append("Database contention or connection-pool pressure is likely.")
        actions.append("Inspect pool saturation, lock waits, transaction duration, and recent schema changes.")
    if not causes and errors:
        causes.append("The first error in the timeline is the best candidate for the primary failure.")
        actions.append("Reproduce the first error with the same build, configuration, and input.")
    if not actions:
        actions.append("Add structured logs and trace identifiers, then reproduce the issue under observation.")
    summary = "No error lines detected." if not errors else f"{len(errors)} error(s), {len(warnings)} warning(s), and {len(timeline)} total event(s) found."
    postmortem = (
        "# Incident postmortem draft\n\n"
        "## Summary\n\n" + summary + "\n\n"
        "## Suspected causes\n\n" + "\n".join(f"- {item}" for item in causes) + "\n\n"
        "## Immediate actions\n\n" + "\n".join(f"- {item}" for item in actions) + "\n\n"
        "## Follow-up\n\n- Confirm the root cause with a reproducible test.\n- Add a regression check and update the runbook.\n"
    )
    return {
        "summary": summary,
        "timeline": timeline[:200],
        "errors": errors[:50],
        "warnings": warnings[:50],
        "suspected_causes": causes,
        "recommended_actions": actions,
        "postmortem": postmortem,
    }
