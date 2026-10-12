"""Persistent polling indexer shared by the API and the local watcher command."""

import hashlib
import os
import time
from pathlib import Path

from django.utils import timezone

from .models import KnowledgeDocument, WorkspaceFileState
from .views import (
    IGNORED_WORKSPACE_DIRECTORIES,
    MAX_FILE_BYTES,
    MAX_PROJECT_FILES,
    WATCHABLE_WORKSPACE_EXTENSIONS,
    _extract_document_text,
    _safe_filename,
    _save_knowledge_document,
)


def scan_workspace(workspace):
    root = Path(workspace.root_path).resolve()
    workspace.status = "scanning"
    workspace.save(update_fields=["status", "updated_at"])
    now = timezone.now()
    files_seen = indexed_count = skipped_count = 0
    errors = []
    seen_paths = set()
    try:
        if not root.is_dir():
            raise OSError(f"Workspace folder does not exist: {root}")
        candidates = []
        for current_root, directories, filenames in os.walk(root):
            directories[:] = [name for name in directories if name not in IGNORED_WORKSPACE_DIRECTORIES]
            for filename in filenames:
                path = Path(current_root) / filename
                if path.suffix.lower() in WATCHABLE_WORKSPACE_EXTENSIONS:
                    candidates.append(path)
        for path in sorted(candidates)[:MAX_PROJECT_FILES]:
            relative_name = _safe_filename(path.relative_to(root).as_posix())
            seen_paths.add(relative_name)
            files_seen += 1
            state, _ = WorkspaceFileState.objects.get_or_create(workspace=workspace, relative_path=relative_name)
            try:
                stat = path.stat()
                state.size_bytes = stat.st_size
                state.mtime_ns = stat.st_mtime_ns
                state.active = True
                state.last_seen_at = now
                state.last_error = ""
                if stat.st_size > MAX_FILE_BYTES:
                    skipped_count += 1
                    state.last_error = f"File exceeds {MAX_FILE_BYTES} byte limit."
                    state.save()
                    continue
                text = _extract_document_text(relative_name, path.read_bytes())
                digest = hashlib.sha256(text.encode("utf-8")).hexdigest()
                if state.content_hash == digest and state.last_indexed_at:
                    skipped_count += 1
                    state.save(update_fields=["size_bytes", "mtime_ns", "active", "last_error", "last_seen_at"])
                    continue
                _save_knowledge_document(relative_name, text, "project", workspace.owner)
                state.content_hash = digest
                state.last_indexed_at = now
                state.save()
                indexed_count += 1
            except (OSError, ValueError, UnicodeError) as exc:
                state.active = True
                state.last_seen_at = now
                state.last_error = str(exc)[:300]
                state.save()
                errors.append(f"{relative_name}: {str(exc)[:240]}")

        stale = WorkspaceFileState.objects.filter(workspace=workspace, active=True).exclude(relative_path__in=seen_paths)
        stale_paths = list(stale.values_list("relative_path", flat=True))
        stale.update(active=False, last_seen_at=now, last_error="File was removed from the workspace.")
        if stale_paths:
            KnowledgeDocument.objects.filter(owner=workspace.owner, source_type="project", filename__in=stale_paths).update(is_active=False)
        workspace.status = "ready" if not errors else "error"
    except OSError as exc:
        errors.append(str(exc)[:240])
        workspace.status = "error"
    workspace.files_seen = files_seen
    workspace.indexed_count = indexed_count
    workspace.skipped_count = skipped_count
    workspace.error_count = len(errors)
    workspace.errors = errors[-50:]
    workspace.last_scan_at = now
    workspace.save(update_fields=["status", "files_seen", "indexed_count", "skipped_count", "error_count", "errors", "last_scan_at", "updated_at"])
    return workspace


def watch_workspace(workspace, interval=2.0, stop_event=None, on_scan=None):
    while True:
        result = scan_workspace(workspace)
        if on_scan:
            on_scan(result)
        if stop_event is not None and stop_event.is_set():
            return result
        time.sleep(max(0.5, float(interval)))
