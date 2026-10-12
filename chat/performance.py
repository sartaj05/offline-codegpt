"""Read-only performance measurements for large local repositories."""

import hashlib
import os
import time
import tracemalloc
from pathlib import Path


WATCHABLE_EXTENSIONS = {".py", ".js", ".ts", ".tsx", ".jsx", ".java", ".cs", ".php", ".sql", ".html", ".css", ".json", ".md", ".txt", ".pdf", ".docx", ".yaml", ".yml", ".toml", ".ini", ".sh", ".ps1"}
IGNORED_DIRECTORIES = {".git", ".venv", "venv", "node_modules", "__pycache__", "staticfiles", ".pytest_cache"}
MAX_FILE_BYTES = 1_000_000


def benchmark_repository(root, max_files=10000):
    root = Path(root).resolve()
    max_files = max(1, min(int(max_files), 100000))
    started = time.perf_counter()
    tracemalloc.start()
    files_seen = readable_files = skipped_files = error_count = total_bytes = hashed_bytes = 0
    candidates = []
    errors = []
    try:
        if not root.is_dir():
            raise OSError(f"Repository folder does not exist: {root}")
        for current_root, directories, filenames in os.walk(root):
            directories[:] = [name for name in directories if name not in IGNORED_DIRECTORIES]
            for filename in filenames:
                path = Path(current_root) / filename
                if path.suffix.lower() in WATCHABLE_EXTENSIONS:
                    candidates.append(path)
        truncated = len(candidates) > max_files
        for path in sorted(candidates)[:max_files]:
            files_seen += 1
            try:
                size = path.stat().st_size
                total_bytes += size
                if size > MAX_FILE_BYTES:
                    skipped_files += 1
                    continue
                content = path.read_bytes()
                hashlib.sha256(content).hexdigest()
                readable_files += 1
                hashed_bytes += len(content)
            except (OSError, ValueError) as exc:
                error_count += 1
                errors.append(f"{path.name}: {str(exc)[:180]}")
    except OSError as exc:
        error_count += 1
        errors.append(str(exc)[:180])
        truncated = False
    current, peak = tracemalloc.get_traced_memory()
    tracemalloc.stop()
    duration_ms = round((time.perf_counter() - started) * 1000)
    seconds = max(duration_ms / 1000, 0.001)
    return {
        "success": error_count == 0,
        "root": str(root),
        "files_discovered": len(candidates),
        "files_seen": files_seen,
        "readable_files": readable_files,
        "skipped_files": skipped_files,
        "truncated": truncated,
        "error_count": error_count,
        "errors": errors[:20],
        "total_bytes": total_bytes,
        "hashed_bytes": hashed_bytes,
        "duration_ms": duration_ms,
        "files_per_second": round(files_seen / seconds, 2),
        "mb_per_second": round((hashed_bytes / (1024 * 1024)) / seconds, 2),
        "peak_memory_bytes": peak,
        "recommendation": "Increase max_files or split the workspace into collections." if truncated else "Repository completed within the selected file limit.",
    }
