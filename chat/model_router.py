import re


def _size_score(name):
    match = re.search(r"(\d+(?:\.\d+)?)b", name.lower())
    return float(match.group(1)) if match else 1.0


def route_model(task, models, memory_gb=0, gpu=False):
    task = (task or "").lower()
    available = [str(model).strip() for model in (models or []) if str(model).strip()]
    if not available:
        available = ["qwen2.5-coder:1.5b"]
    scored = []
    for model in available:
        lower = model.lower()
        score = 0
        reasons = []
        if any(word in task for word in ("image", "screenshot", "visual", "diagram")) and any(word in lower for word in ("vision", "llava", "qwen2-vl")):
            score += 80
            reasons.append("visual task")
        if any(word in task for word in ("code", "debug", "refactor", "test", "python", "javascript", "sql")) and any(word in lower for word in ("coder", "code", "deepseek", "qwen")):
            score += 70
            reasons.append("coding task")
        if any(word in task for word in ("architecture", "design", "review", "complex")):
            score += min(35, int(_size_score(lower) * 5))
            reasons.append("complex reasoning")
        if any(word in task for word in ("quick", "simple", "summarize", "small")):
            if _size_score(lower) <= 4:
                score += 30
                reasons.append("fast model")
        if memory_gb and _size_score(lower) > max(2, memory_gb / 2):
            score -= 45
            reasons.append("hardware fit penalty")
        if not gpu and _size_score(lower) > 7:
            score -= 20
            reasons.append("CPU-friendly preference")
        scored.append({"model": model, "score": score, "reasons": reasons or ["general purpose"]})
    scored.sort(key=lambda item: (item["score"], item["model"]), reverse=True)
    selected = scored[0]
    return {
        "selected_model": selected["model"],
        "reason": ", ".join(selected["reasons"]),
        "candidates": scored,
        "hardware": {"memory_gb": memory_gb, "gpu": gpu},
    }
