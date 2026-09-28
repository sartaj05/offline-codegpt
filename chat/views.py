import ast
import base64
import difflib
import hashlib
import json
import os
import re
import sqlite3
import subprocess
import time
import uuid
from pathlib import PurePosixPath
from urllib.parse import quote, urlparse

import requests

from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from django.db.models import Count, Min, Q
from django.http import HttpResponse, JsonResponse, StreamingHttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_GET, require_http_methods, require_POST
from django.views.decorators.csrf import csrf_exempt

from .models import (
    ChatMessage,
    ChatSession,
    ConversationRevision,
    KnowledgeChunk,
    KnowledgeDocument,
    LocalModelConfig,
    McpConnector,
    McpToolCall,
    AgentTask,
    AiEvent,
    AuditEvent,
    UserOllamaSettings,
    Workspace,
    WorkspaceMembership,
    WorkspacePolicy,
    EvaluationTask,
    EvaluationRun,
)
from .quality import analyze_code_quality
from .sandbox import run_sandboxed_code
from .security import scan_files
from .devops import analyze_logs, generate_artifact
from .documentation import generate_documentation
from .dependencies import analyze_dependencies
from .browser_testing import analyze_browser_report, generate_playwright_test
from .model_router import route_model
from .devcontainer import generate_devcontainer
from .incident import analyze_incident
from .architecture import analyze_architecture
from .api_contract import analyze_api_contract
from .provenance import generate_provenance, verify_provenance
from .review import review_gate


OLLAMA_BASE_URL = "http://127.0.0.1:11434"
OLLAMA_URL = f"{OLLAMA_BASE_URL}/api/generate"
DEFAULT_MODEL = "qwen2.5-coder:1.5b"
VISION_MODEL = os.environ.get("OLLAMA_VISION_MODEL", "llava:latest")
MAX_PROJECT_FILES = 100
MAX_FILE_BYTES = 1_000_000
MAX_IMAGE_BYTES = 5_000_000
CHUNK_SIZE = 2_000
MAX_EXECUTION_CHARS = 20_000
MAX_TEST_CHARS = 20_000
MAX_GIT_OUTPUT_CHARS = 50_000


def _agent_plan(goal):
    plan = [
        {
            "title": "Inspect project context",
            "description": "Read indexed files and relevant project history.",
            "kind": "read",
            "requires_approval": False,
            "approved": True,
            "completed": False,
        },
        {
            "title": "Prepare file changes",
            "description": "Propose edits for the files related to this task.",
            "kind": "file_write",
            "requires_approval": True,
            "approved": False,
            "completed": False,
        },
        {
            "title": "Run guarded tests",
            "description": "Execute the project test command inside the guarded workspace.",
            "kind": "execute",
            "requires_approval": True,
            "approved": False,
            "completed": False,
        },
        {
            "title": "Review Git changes",
            "description": "Inspect the resulting diff and changed files.",
            "kind": "git_read",
            "requires_approval": False,
            "approved": True,
            "completed": False,
        },
        {
            "title": "Create a Git commit",
            "description": "Prepare a commit only after explicit user approval.",
            "kind": "git_write",
            "requires_approval": True,
            "approved": False,
            "completed": False,
        },
    ]
    return plan


def _agent_payload(task):
    completed = sum(1 for step in task.plan if step.get("completed"))
    return {
        "id": task.id,
        "title": task.title,
        "goal": task.goal,
        "status": task.status,
        "plan": task.plan,
        "current_step": task.current_step,
        "progress": completed,
        "total_steps": len(task.plan),
        "result": task.result,
        "control_state": task.control_state,
        "logs": task.logs,
        "retry_count": task.retry_count,
        "source_branch": task.source_branch,
        "created_at": task.created_at.strftime("%d-%m-%Y %H:%M"),
    }


def _run_git(args):
    project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    try:
        return subprocess.run(
            ["git", "-C", project_root, *args],
            capture_output=True,
            text=True,
            timeout=15,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        return None, str(exc)


def _git_path_is_safe(path):
    normalized = str(path or "").replace("\\", "/")
    parsed = PurePosixPath(normalized)
    return bool(normalized) and not parsed.is_absolute() and ".." not in parsed.parts


@login_required(login_url="/login/")
def git_status(request):
    branch_result = _run_git(["rev-parse", "--abbrev-ref", "HEAD"])
    status_result = _run_git(["status", "--short"])
    if isinstance(branch_result, tuple) or isinstance(status_result, tuple):
        error = branch_result[1] if isinstance(branch_result, tuple) else status_result[1]
        return JsonResponse({"success": False, "error": "Git is unavailable: " + error}, status=503)
    if branch_result.returncode != 0 or status_result.returncode != 0:
        return JsonResponse({"success": False, "error": (status_result.stderr or branch_result.stderr).strip()}, status=503)

    files = []
    for line in status_result.stdout.splitlines():
        if len(line) < 3:
            continue
        path = line[3:]
        if " -> " in path:
            path = path.split(" -> ", 1)[1]
        files.append({"status": line[:2].strip() or "??", "path": path})
    return JsonResponse({
        "success": True,
        "branch": branch_result.stdout.strip() or "detached",
        "files": files,
        "raw": status_result.stdout,
    })


@login_required(login_url="/login/")
def git_diff(request):
    result = _run_git(["diff", "HEAD", "--"])
    if isinstance(result, tuple):
        return JsonResponse({"success": False, "error": "Git is unavailable: " + result[1]}, status=503)
    if result.returncode != 0:
        return JsonResponse({"success": False, "error": result.stderr.strip()}, status=503)
    return JsonResponse({"success": True, "diff": result.stdout[:MAX_GIT_OUTPUT_CHARS]})


@login_required(login_url="/login/")
@require_POST
def git_stage(request):
    paths = request.POST.getlist("paths")
    if not paths:
        paths = [request.POST.get("path", "").strip()] if request.POST.get("path") else []
    if any(not _git_path_is_safe(path) for path in paths):
        return JsonResponse({"success": False, "error": "One or more Git paths are invalid."}, status=400)
    result = _run_git(["add", "--", *paths] if paths else ["add", "-A"])
    if isinstance(result, tuple):
        return JsonResponse({"success": False, "error": "Git is unavailable: " + result[1]}, status=503)
    if result.returncode != 0:
        return JsonResponse({"success": False, "error": result.stderr.strip()}, status=400)
    return JsonResponse({"success": True, "staged": paths or ["all changes"]})


@login_required(login_url="/login/")
@require_POST
def git_commit(request):
    message = request.POST.get("message", "").strip()
    if not message:
        return JsonResponse({"success": False, "error": "Enter a commit message."}, status=400)
    if len(message) > 200:
        return JsonResponse({"success": False, "error": "Commit messages are limited to 200 characters."}, status=400)
    result = _run_git(["commit", "-m", message])
    if isinstance(result, tuple):
        return JsonResponse({"success": False, "error": "Git is unavailable: " + result[1]}, status=503)
    if result.returncode != 0:
        return JsonResponse({"success": False, "error": (result.stderr or result.stdout).strip()}, status=400)
    return JsonResponse({"success": True, "output": result.stdout.strip()})


def _remote_connection(request):
    return request.session.get("remote_git", {})


def _remote_headers(connection):
    token = connection.get("token", "")
    if connection.get("provider") == "gitlab":
        return {"PRIVATE-TOKEN": token, "Accept": "application/json"}
    return {"Authorization": "Bearer " + token, "Accept": "application/vnd.github+json"}


def _remote_request(request, method, url, **kwargs):
    connection = _remote_connection(request)
    if not connection.get("token"):
        return None, JsonResponse({"success": False, "error": "Connect a GitHub or GitLab token first."}, status=400)
    headers = _remote_headers(connection)
    headers.update(kwargs.pop("headers", {}))
    try:
        response = requests.request(method, url, headers=headers, timeout=20, **kwargs)
    except requests.RequestException as exc:
        return None, JsonResponse({"success": False, "error": "Remote provider unavailable: " + str(exc)}, status=503)
    if not response.ok:
        return None, JsonResponse({"success": False, "error": response.text[:1000]}, status=400)
    return response, None


@login_required(login_url="/login/")
@require_http_methods(["GET", "POST"])
def remote_git_settings(request):
    connection = _remote_connection(request)
    if request.method == "POST":
        provider = request.POST.get("provider", "").strip().lower()
        if provider not in {"github", "gitlab"}:
            return JsonResponse({"success": False, "error": "Choose GitHub or GitLab."}, status=400)
        token = request.POST.get("token", "").strip()
        if token:
            connection["token"] = token
        connection["provider"] = provider
        connection["repository"] = request.POST.get("repository", "").strip()[:200]
        request.session["remote_git"] = connection
        request.session.modified = True
    return JsonResponse({
        "success": True,
        "provider": connection.get("provider", "github"),
        "repository": connection.get("repository", ""),
        "token_set": bool(connection.get("token")),
    })


@login_required(login_url="/login/")
@require_GET
def remote_repositories(request):
    connection = _remote_connection(request)
    if connection.get("provider") == "gitlab":
        url = "https://gitlab.com/api/v4/projects?membership=true&per_page=100"
    else:
        url = "https://api.github.com/user/repos?per_page=100&sort=updated"
    response, error = _remote_request(request, "GET", url)
    if error:
        return error
    items = response.json()
    repositories = [
        {
            "name": item.get("full_name") or item.get("path_with_namespace"),
            "id": item.get("id"),
            "url": item.get("html_url") or item.get("web_url"),
        }
        for item in items
    ]
    return JsonResponse({"success": True, "repositories": repositories})


@login_required(login_url="/login/")
@require_GET
def remote_issues(request):
    connection = _remote_connection(request)
    repository = request.GET.get("repository", connection.get("repository", "")).strip()
    if not repository:
        return JsonResponse({"success": False, "error": "Choose a repository first."}, status=400)
    if connection.get("provider") == "gitlab":
        url = "https://gitlab.com/api/v4/projects/" + quote(repository, safe="") + "/issues?state=opened&per_page=30"
    else:
        url = f"https://api.github.com/repos/{repository}/issues?state=open&per_page=30"
    response, error = _remote_request(request, "GET", url)
    if error:
        return error
    return JsonResponse({"success": True, "issues": [
        {"id": item.get("iid") or item.get("number"), "title": item.get("title"), "url": item.get("html_url") or item.get("web_url")}
        for item in response.json()
        if not item.get("pull_request")
    ]})


@login_required(login_url="/login/")
@require_POST
def remote_pull_request(request):
    connection = _remote_connection(request)
    repository = request.POST.get("repository", connection.get("repository", "")).strip()
    title = request.POST.get("title", "").strip()
    body = request.POST.get("body", "").strip()
    head = request.POST.get("head", "").strip()
    base = request.POST.get("base", "main").strip() or "main"
    if not repository or not title or not head:
        return JsonResponse({"success": False, "error": "Repository, title, and source branch are required."}, status=400)
    if connection.get("provider") == "gitlab":
        url = "https://gitlab.com/api/v4/projects/" + quote(repository, safe="") + "/merge_requests"
        payload = {"source_branch": head, "target_branch": base, "title": title, "description": body}
    else:
        url = f"https://api.github.com/repos/{repository}/pulls"
        payload = {"head": head, "base": base, "title": title, "body": body, "draft": True}
    response, error = _remote_request(request, "POST", url, json=payload)
    if error:
        return error
    data = response.json()
    return JsonResponse({"success": True, "url": data.get("html_url") or data.get("web_url"), "number": data.get("number") or data.get("iid")})


@csrf_exempt
@require_POST
def cli_ask(request):
    if request.META.get("REMOTE_ADDR") not in {"127.0.0.1", "::1", "localhost"}:
        return JsonResponse({"success": False, "error": "CLI access is limited to the local machine."}, status=403)
    return ask_code(request)


def _user_ollama_settings(user):
    return UserOllamaSettings.objects.get_or_create(user=user)[0]


def _safe_ollama_url(value):
    parsed = urlparse(str(value or "").strip())
    if parsed.scheme not in ("http", "https") or not parsed.hostname:
        return None
    if parsed.hostname not in ("127.0.0.1", "localhost", "::1"):
        return None
    return f"{parsed.scheme}://{parsed.netloc}".rstrip("/")


def _available_models(base_url=OLLAMA_BASE_URL):
    names = list(
        LocalModelConfig.objects.filter(is_active=True)
        .order_by("-is_default", "name")
        .values_list("name", flat=True)
    )

    if DEFAULT_MODEL not in names:
        names.insert(0, DEFAULT_MODEL)
    if VISION_MODEL not in names:
        names.append(VISION_MODEL)

    try:
        response = requests.get(f"{base_url}/api/tags", timeout=3)
        if response.ok:
            for item in response.json().get("models", []):
                name = item.get("name")
                if name and name not in names:
                    names.append(name)
    except (requests.RequestException, ValueError):
        pass

    return names


def _event(payload):
    return json.dumps(payload, ensure_ascii=False) + "\n"


def _safe_filename(name):
    path = PurePosixPath(str(name).replace("\\", "/"))
    safe_parts = [part for part in path.parts if part not in ("", ".", "..")]
    return "/".join(safe_parts) or "uploaded-file"


def _language_for_filename(filename):
    extension = PurePosixPath(filename).suffix.lower().lstrip(".")
    return {
        "py": "python",
        "js": "javascript",
        "ts": "typescript",
        "jsx": "javascript",
        "tsx": "typescript",
        "html": "html",
        "css": "css",
        "sql": "sql",
        "java": "java",
        "cs": "csharp",
        "php": "php",
        "json": "json",
        "md": "markdown",
    }.get(extension, "auto")


def _save_knowledge_document(filename, file_text, source_type, owner):
    content_hash = hashlib.sha256(file_text.encode("utf-8")).hexdigest()
    document, _ = KnowledgeDocument.objects.update_or_create(
        owner=owner,
        content_hash=content_hash,
        defaults={
            "title": PurePosixPath(filename).name,
            "filename": filename,
            "file_extension": PurePosixPath(filename).suffix.lower(),
            "source_type": source_type,
            "language": _language_for_filename(filename),
            "original_text": file_text,
            "file_size_bytes": len(file_text.encode("utf-8")),
            "is_active": True,
        },
    )
    document.chunks.all().delete()
    KnowledgeChunk.objects.bulk_create([
        KnowledgeChunk(
            document=document,
            chunk_index=index,
            content=file_text[start:start + CHUNK_SIZE],
            language=document.language,
        )
        for index, start in enumerate(range(0, len(file_text), CHUNK_SIZE))
    ])
    return document


def _search_knowledge(query, limit=8, owner=None):
    terms = list(dict.fromkeys(re.findall(r"[a-zA-Z0-9_]{2,}", query.lower())))
    if not terms:
        return []

    matches = []
    chunks = KnowledgeChunk.objects.filter(
        document__is_active=True,
        document__owner=owner,
    ).select_related("document")

    for chunk in chunks:
        content = chunk.content.lower()
        filename = (chunk.document.filename or "").lower()
        score = sum(content.count(term) for term in terms)
        score += 3 * sum(filename.count(term) for term in terms)
        if score:
            matches.append((score, chunk))

        matches.sort(key=lambda item: item[0], reverse=True)
    return [
        {
            "filename": chunk.document.filename,
            "language": chunk.language,
            "chunk_index": chunk.chunk_index,
            "content": chunk.content,
            "score": score,
            "line_start": (
                chunk.document.original_text[:max(
                    chunk.document.original_text.find(chunk.content),
                    0,
                )].count("\n") + 1
            ),
            "line_end": (
                chunk.document.original_text[:max(
                    chunk.document.original_text.find(chunk.content),
                    0,
                )].count("\n") + chunk.content.count("\n") + 1
            ),
        }
        for score, chunk in matches[:limit]
    ]


def signup(request):
    if request.user.is_authenticated:
        return redirect("chat_home")
    if request.method == "POST":
        username = request.POST.get("username", "").strip()
        password = request.POST.get("password", "")
        confirmation = request.POST.get("confirmation", "")
        if not username or not password:
            return render(request, "chat/signup.html", {"error": "Username and password are required."})
        if password != confirmation:
            return render(request, "chat/signup.html", {"error": "Passwords do not match."})
        if User.objects.filter(username=username).exists():
            return render(request, "chat/signup.html", {"error": "That username is already in use."})
        user = User.objects.create_user(username=username, password=password)
        login(request, user)
        return redirect("chat_home")
    return render(request, "chat/signup.html")


def login_view(request):
    if request.user.is_authenticated:
        return redirect("chat_home")
    if request.method == "POST":
        user = authenticate(
            request,
            username=request.POST.get("username", "").strip(),
            password=request.POST.get("password", ""),
        )
        if user is not None:
            login(request, user)
            return redirect("chat_home")
        return render(request, "chat/login.html", {"error": "Invalid username or password."})
    return render(request, "chat/login.html")


@require_POST
def logout_view(request):
    logout(request)
    return redirect("chat_home")


def index(request):
    sessions = (
        ChatSession.objects.filter(owner=request.user, is_archived=False)
        .order_by("-is_pinned", "-updated_at")[:30]
        if request.user.is_authenticated
        else ChatSession.objects.none()
    )
    user_settings = _user_ollama_settings(request.user) if request.user.is_authenticated else None
    server_url = user_settings.server_url if user_settings else OLLAMA_BASE_URL
    default_model = user_settings.default_model if user_settings else DEFAULT_MODEL
    return render(request, "chat/index.html", {
        "sessions": sessions,
        "models": _available_models(server_url),
        "default_model": default_model,
        "ollama_settings": user_settings,
    })


def model_list(request):
    user_settings = _user_ollama_settings(request.user) if request.user.is_authenticated else None
    server_url = user_settings.server_url if user_settings else OLLAMA_BASE_URL
    default_model = user_settings.default_model if user_settings else DEFAULT_MODEL
    return JsonResponse({
        "success": True,
        "models": _available_models(server_url),
        "default_model": default_model,
    })


def _ollama_settings_payload(settings):
    return {
        "server_url": settings.server_url,
        "default_model": settings.default_model,
        "temperature": settings.temperature,
        "top_p": settings.top_p,
        "max_context_chars": settings.max_context_chars,
    }


@login_required(login_url="/login/")
@require_http_methods(["GET", "POST"])
def ollama_settings(request):
    settings = _user_ollama_settings(request.user)
    if request.method == "POST":
        server_url = _safe_ollama_url(request.POST.get("server_url", settings.server_url))
        if not server_url:
            return JsonResponse({"success": False, "error": "Use a local Ollama URL such as http://127.0.0.1:11434."}, status=400)
        try:
            temperature = min(max(float(request.POST.get("temperature", settings.temperature)), 0), 2)
            top_p = min(max(float(request.POST.get("top_p", settings.top_p)), 0), 1)
            max_context_chars = min(max(int(request.POST.get("max_context_chars", settings.max_context_chars)), 4000), 100000)
        except (TypeError, ValueError):
            return JsonResponse({"success": False, "error": "Temperature, top-p, and context must be valid numbers."}, status=400)
        settings.server_url = server_url
        settings.default_model = request.POST.get("default_model", settings.default_model).strip()[:100] or DEFAULT_MODEL
        settings.temperature = temperature
        settings.top_p = top_p
        settings.max_context_chars = max_context_chars
        settings.save()
    return JsonResponse({
        "success": True,
        "settings": _ollama_settings_payload(settings),
        "models": _available_models(settings.server_url),
    })


@login_required(login_url="/login/")
@require_POST
def ollama_model_action(request):
    settings = _user_ollama_settings(request.user)
    action = request.POST.get("action", "").strip().lower()
    name = request.POST.get("name", "").strip()
    if not name or len(name) > 100:
        return JsonResponse({"success": False, "error": "Enter a valid model name."}, status=400)
    try:
        if action == "pull":
            response = requests.post(
                f"{settings.server_url}/api/pull",
                json={"name": name, "stream": False},
                timeout=(10, 300),
            )
        elif action == "delete":
            response = requests.delete(
                f"{settings.server_url}/api/delete",
                json={"name": name},
                timeout=(10, 30),
            )
        else:
            return JsonResponse({"success": False, "error": "Use pull or delete."}, status=400)
    except requests.RequestException as exc:
        return JsonResponse({"success": False, "error": "Ollama is unavailable: " + str(exc)}, status=503)
    if not response.ok:
        return JsonResponse({"success": False, "error": response.text}, status=400)
    return JsonResponse({"success": True, "models": _available_models(settings.server_url)})


@login_required(login_url="/login/")
def session_list(request):
    query = request.GET.get("q", "").strip()
    sessions = ChatSession.objects.filter(
        owner=request.user,
        is_archived=False,
    )
    if query:
        sessions = sessions.filter(
            Q(title__icontains=query) | Q(messages__content__icontains=query)
        ).distinct()
    sessions = sessions.order_by("-is_pinned", "-updated_at")[:100]
    return JsonResponse({
        "success": True,
        "sessions": [
            {
                "id": session.id,
                "title": session.title,
                "is_pinned": session.is_pinned,
                "tags": [tag.strip() for tag in session.tags.split(",") if tag.strip()],
                "updated_at": session.updated_at.strftime("%d-%m-%Y %H:%M"),
            }
            for session in sessions
        ],
    })


@login_required(login_url="/login/")
@require_POST
def manage_session(request, session_id):
    session = get_object_or_404(ChatSession, id=session_id, owner=request.user)
    action = request.POST.get("action", "").strip().lower()

    if action == "rename":
        title = request.POST.get("title", "").strip()[:200]
        if not title:
            return JsonResponse({"success": False, "error": "A chat title is required."}, status=400)
        session.title = title
    elif action == "tag":
        tags = request.POST.get("tags", "")
        session.tags = ",".join(dict.fromkeys(
            tag.strip()[:40] for tag in tags.split(",") if tag.strip()
        ))[:300]
    elif action == "pin":
        session.is_pinned = not session.is_pinned
    elif action == "archive":
        session.is_archived = True
    elif action == "delete":
        session.delete()
        return JsonResponse({"success": True, "deleted": True})
    else:
        return JsonResponse({"success": False, "error": "Unsupported chat action."}, status=400)

    session.save()
    return JsonResponse({
        "success": True,
        "id": session.id,
        "title": session.title,
        "is_pinned": session.is_pinned,
        "tags": [tag.strip() for tag in session.tags.split(",") if tag.strip()],
    })


@login_required(login_url="/login/")
def knowledge_search(request):
    query = request.GET.get("q", "").strip()
    return JsonResponse({
        "success": True,
        "query": query,
        "results": _search_knowledge(query, owner=request.user),
    })


@login_required(login_url="/login/")
def project_documents(request):
    documents = (
        KnowledgeDocument.objects.filter(owner=request.user, is_active=True)
        .order_by("filename")
    )
    return JsonResponse({
        "success": True,
        "documents": [
            {
                "id": document.id,
                "filename": document.filename or document.title,
                "language": document.language,
                "size_bytes": document.file_size_bytes,
                "chunks": document.chunks.count(),
                "uploaded_at": document.uploaded_at.strftime("%d-%m-%Y %H:%M"),
            }
            for document in documents
        ],
    })


@login_required(login_url="/login/")
@require_http_methods(["DELETE"])
def project_document_delete(request, document_id):
    document = get_object_or_404(
        KnowledgeDocument,
        id=document_id,
        owner=request.user,
    )
    document.delete()
    return JsonResponse({"success": True, "deleted_id": document_id})


@login_required(login_url="/login/")
@require_http_methods(["GET", "POST"])
def project_document_content(request, document_id):
    document = get_object_or_404(
        KnowledgeDocument,
        id=document_id,
        owner=request.user,
    )
    if request.method == "GET":
        return JsonResponse({
            "success": True,
            "document": {
                "id": document.id,
                "filename": document.filename or document.title,
                "language": document.language,
                "content": document.original_text,
            },
        })

    content = request.POST.get("content", "")
    if len(content.encode("utf-8")) > MAX_FILE_BYTES:
        return JsonResponse({"success": False, "error": "Saved files are limited to 1 MB."}, status=400)
    document.original_text = content
    document.file_size_bytes = len(content.encode("utf-8"))
    document.content_hash = hashlib.sha256(content.encode("utf-8")).hexdigest()
    document.save(update_fields=["original_text", "file_size_bytes", "content_hash"])
    document.chunks.all().delete()
    KnowledgeChunk.objects.bulk_create([
        KnowledgeChunk(
            document=document,
            chunk_index=index,
            content=content[start:start + CHUNK_SIZE],
            language=document.language,
        )
        for index, start in enumerate(range(0, len(content), CHUNK_SIZE))
    ])
    return JsonResponse({
        "success": True,
        "document_id": document.id,
        "chunks": document.chunks.count(),
        "saved_at": document.uploaded_at.strftime("%d-%m-%Y %H:%M"),
    })


@login_required(login_url="/login/")
@require_POST
def project_document_reindex(request, document_id):
    document = get_object_or_404(
        KnowledgeDocument,
        id=document_id,
        owner=request.user,
    )
    document.chunks.all().delete()
    KnowledgeChunk.objects.bulk_create([
        KnowledgeChunk(
            document=document,
            chunk_index=index,
            content=document.original_text[start:start + CHUNK_SIZE],
            language=document.language,
        )
        for index, start in enumerate(range(0, len(document.original_text), CHUNK_SIZE))
    ])
    return JsonResponse({
        "success": True,
        "document_id": document.id,
        "chunks": document.chunks.count(),
    })


def session_messages(request, session_id):
    owner = request.user if request.user.is_authenticated else None
    session = get_object_or_404(ChatSession, id=session_id, owner=owner)
    messages = [
        {
            "id": msg.id,
            "role": msg.role,
            "content": msg.content,
            "filename": msg.filename,
            "created_at": msg.created_at.strftime("%d-%m-%Y %H:%M"),
        }
        for msg in session.messages.order_by("created_at")
    ]
    return JsonResponse({
        "success": True,
        "session_id": session.id,
        "title": session.title,
        "model": session.model_name,
        "messages": messages,
    })


@login_required(login_url="/login/")
def session_revisions(request, session_id):
    session = get_object_or_404(ChatSession, id=session_id, owner=request.user)
    revisions = [
        {
            "branch_id": str(branch_id),
            "created_at": created_at.strftime("%d-%m-%Y %H:%M"),
            "messages": count,
        }
        for branch_id, created_at, count in (
            ConversationRevision.objects.filter(session=session)
            .values("branch_id")
            .annotate(
                created_at=Min("created_at"),
                count=Count("id"),
            )
            .values_list("branch_id", "created_at", "count")
            .order_by("-created_at")
        )
    ]
    return JsonResponse({"success": True, "revisions": revisions})


def _session_markdown(session):
    lines = [
        f"# {session.title}",
        "",
        f"- Model: `{session.model_name}`",
        f"- Created: {session.created_at:%Y-%m-%d %H:%M}",
        "",
    ]
    for message in session.messages.order_by("created_at"):
        label = "You" if message.role == "user" else "Syntax Local AI"
        lines.extend([f"## {label}", "", message.content, ""])
    return "\n".join(lines)


def _pdf_escape(value):
    return value.replace("\\", "\\\\").replace("(", "\\\\(").replace(")", "\\\\)")


def _session_pdf(session):
    text = _session_markdown(session).encode("latin-1", errors="replace").decode("latin-1")
    lines = []
    for paragraph in text.splitlines():
        while len(paragraph) > 95:
            lines.append(paragraph[:95])
            paragraph = paragraph[95:]
        lines.append(paragraph)

    content_lines = ["BT", "/F1 10 Tf", "50 760 Td"]
    for line in lines[:65]:
        content_lines.append(f"({_pdf_escape(line)}) Tj")
        content_lines.append("0 -11 Td")
    content_lines.append("ET")
    content = "\n".join(content_lines).encode("latin-1", errors="replace")

    objects = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Resources << /Font << /F1 4 0 R >> >> /Contents 5 0 R >>",
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
        b"<< /Length " + str(len(content)).encode() + b" >>\nstream\n" + content + b"\nendstream",
    ]
    pdf = b"%PDF-1.4\n%\\xe2\\xe3\\xcf\\xd3\n"
    offsets = [0]
    for index, obj in enumerate(objects, start=1):
        offsets.append(len(pdf))
        pdf += f"{index} 0 obj\n".encode() + obj + b"\nendobj\n"
    xref_offset = len(pdf)
    pdf += f"xref\n0 {len(objects) + 1}\n".encode()
    pdf += b"0000000000 65535 f \n"
    pdf += b"".join(f"{offset:010d} 00000 n \n".encode() for offset in offsets[1:])
    pdf += f"trailer\n<< /Size {len(objects) + 1} /Root 1 0 R >>\nstartxref\n{xref_offset}\n%%EOF".encode()
    return pdf


@login_required(login_url="/login/")
def export_session(request, session_id):
    session = get_object_or_404(ChatSession, id=session_id, owner=request.user)
    export_format = request.GET.get("format", "markdown").lower()
    filename = f"syntax-local-ai-{session.id}"

    if export_format in ("md", "markdown"):
        response = HttpResponse(_session_markdown(session), content_type="text/markdown")
        response["Content-Disposition"] = f'attachment; filename="{filename}.md"'
        return response

    if export_format == "json":
        payload = {
            "session_id": session.id,
            "title": session.title,
            "model": session.model_name,
            "messages": list(session.messages.order_by("created_at").values(
                "role", "content", "filename", "model_name", "created_at"
            )),
        }
        response = HttpResponse(
            json.dumps(payload, default=str, indent=2),
            content_type="application/json",
        )
        response["Content-Disposition"] = f'attachment; filename="{filename}.json"'
        return response

    if export_format == "pdf":
        response = HttpResponse(_session_pdf(session), content_type="application/pdf")
        response["Content-Disposition"] = f'attachment; filename="{filename}.pdf"'
        return response

    return JsonResponse({"success": False, "error": "Unsupported export format."}, status=400)


def _javascript_check(code):
    sanitized = re.sub(r"(['\"]).*?\\1", "", code, flags=re.DOTALL)
    stack = []
    pairs = {")": "(", "]": "[", "}": "{",
    }
    for character in sanitized:
        if character in "([{":
            stack.append(character)
        elif character in pairs:
            if not stack or stack.pop() != pairs[character]:
                return False, "Unbalanced JavaScript brackets."
    return (not stack), "Unbalanced JavaScript brackets." if stack else ""


@login_required(login_url="/login/")
@require_POST
def execute_code(request):
    language = request.POST.get("language", "python").strip().lower()
    code = request.POST.get("code", "")
    if not code.strip():
        return JsonResponse({"success": False, "error": "Enter code to check."}, status=400)
    if len(code) > MAX_EXECUTION_CHARS:
        return JsonResponse({
            "success": False,
            "error": f"Code checking is limited to {MAX_EXECUTION_CHARS} characters.",
        }, status=400)

    return JsonResponse(run_sandboxed_code(language, code))


@login_required(login_url="/login/")
@require_POST
def agent_plan(request):
    goal = request.POST.get("goal", "").strip()
    if not goal:
        return JsonResponse({"success": False, "error": "Describe the task for the agent."}, status=400)
    if len(goal) > 4000:
        return JsonResponse({"success": False, "error": "Agent goals are limited to 4,000 characters."}, status=400)
    task = AgentTask.objects.create(
        owner=request.user,
        title=goal[:80],
        goal=goal,
        plan=_agent_plan(goal),
    )
    return JsonResponse({"success": True, "task": _agent_payload(task)})


@login_required(login_url="/login/")
@require_http_methods(["GET", "POST"])
def agent_task(request, task_id):
    task = get_object_or_404(AgentTask, id=task_id, owner=request.user)
    if request.method == "GET":
        return JsonResponse({"success": True, "task": _agent_payload(task)})

    action = request.POST.get("action", "").strip().lower()
    try:
        step_index = int(request.POST.get("step", task.current_step))
    except (TypeError, ValueError):
        return JsonResponse({"success": False, "error": "Invalid plan step."}, status=400)
    if action == "undo":
        task.plan = _agent_plan(task.goal)
        task.current_step = 0
        task.status = "planned"
        task.result = "Task reset. No approved actions remain."
        task.control_state = "ready"
        task.logs = []
        task.retry_count = 0
    elif action in {"approve", "reject", "complete"}:
        if step_index < 0 or step_index >= len(task.plan):
            return JsonResponse({"success": False, "error": "Plan step does not exist."}, status=400)
        step = task.plan[step_index]
        if action == "approve":
            step["approved"] = True
            task.status = "running"
            task.current_step = step_index
            task.result = "Step approved. Review the proposed action before execution."
        elif action == "reject":
            step["approved"] = False
            task.status = "blocked"
            task.result = "Step rejected. The agent is paused until the plan is reset."
        else:
            if step.get("requires_approval") and not step.get("approved"):
                return JsonResponse({"success": False, "error": "Approve this step before marking it complete."}, status=400)
            step["completed"] = True
            task.current_step = min(step_index + 1, len(task.plan) - 1)
            task.status = "completed" if all(item.get("completed") for item in task.plan) else "running"
            task.result = "Step completed."
    else:
        return JsonResponse({"success": False, "error": "Use approve, reject, complete, or undo."}, status=400)
    task.save(update_fields=["plan", "current_step", "status", "result", "control_state", "logs", "retry_count", "updated_at"])
    return JsonResponse({"success": True, "task": _agent_payload(task)})


@login_required(login_url="/login/")
@require_POST
def agent_run(request, task_id):
    task = get_object_or_404(AgentTask, id=task_id, owner=request.user)
    if task.control_state == "cancelled":
        return JsonResponse({"success": False, "error": "This task was cancelled."}, status=400)
    if any(step.get("requires_approval") and not step.get("approved") for step in task.plan):
        return JsonResponse({"success": False, "error": "Approve protected plan steps before running the task."}, status=400)
    code = request.POST.get("code", "").strip()
    test_code = request.POST.get("test_code", "").strip()
    branch = request.POST.get("branch", "").strip()
    logs = list(task.logs or [])
    logs.append({"message": "Run started. Protected actions remain approval-gated.", "level": "info"})
    task.status = "running"
    task.control_state = "running"
    task.retry_count += 1
    if branch:
        task.source_branch = branch[:200]
        logs.append({"message": "Branch requested: " + task.source_branch, "level": "info"})
    if code:
        scan = scan_files([{"filename": "agent-buffer", "content": code}])
        logs.append({"message": scan["summary"], "level": "warning" if scan["findings"] else "info"})
    if test_code:
        result = run_sandboxed_code("python", code + "\n\n" + test_code)
        logs.append({"message": "Guarded tests " + ("passed." if result["success"] else "failed."), "level": "info" if result["success"] else "error"})
    logs.append({"message": "Run paused after safe checks. Apply file patches and Git writes explicitly.", "level": "info"})
    task.logs = logs[-50:]
    task.result = logs[-1]["message"]
    task.save(update_fields=["status", "control_state", "retry_count", "source_branch", "logs", "result", "updated_at"])
    return JsonResponse({"success": True, "task": _agent_payload(task)})


@login_required(login_url="/login/")
@require_POST
def agent_control(request, task_id):
    task = get_object_or_404(AgentTask, id=task_id, owner=request.user)
    action = request.POST.get("action", "").strip().lower()
    if action == "pause":
        task.control_state = "paused"
        task.result = "Task paused by user."
    elif action == "resume":
        task.control_state = "running"
        task.status = "running"
        task.result = "Task resumed. Review the next protected action."
    elif action == "retry":
        task.control_state = "ready"
        task.status = "planned"
        task.result = "Task ready for another approved run."
    elif action == "cancel":
        task.control_state = "cancelled"
        task.status = "blocked"
        task.result = "Task cancelled by user."
    else:
        return JsonResponse({"success": False, "error": "Use pause, resume, retry, or cancel."}, status=400)
    task.logs = [*(task.logs or []), {"message": task.result, "level": "warning" if action in {"pause", "cancel"} else "info"}][-50:]
    task.save(update_fields=["control_state", "status", "result", "logs", "updated_at"])
    return JsonResponse({"success": True, "task": _agent_payload(task)})


@login_required(login_url="/login/")
@require_GET
def ai_observability(request):
    events = list(AiEvent.objects.filter(owner=request.user).order_by("-created_at")[:100])
    total = len(events)
    successful = sum(1 for event in events if event.success)
    durations = [event.duration_ms for event in events if event.duration_ms]
    return JsonResponse({
        "success": True,
        "summary": {
            "events": total,
            "successful": successful,
            "failed": total - successful,
            "success_rate": round((successful / total) * 100, 1) if total else 0,
            "average_duration_ms": round(sum(durations) / len(durations)) if durations else 0,
            "input_chars": sum(event.input_chars for event in events),
            "output_chars": sum(event.output_chars for event in events),
        },
        "events": [
            {
                "id": event.id,
                "type": event.event_type,
                "model": event.model_name,
                "duration_ms": event.duration_ms,
                "input_chars": event.input_chars,
                "output_chars": event.output_chars,
                "success": event.success,
                "metadata": event.metadata,
                "created_at": event.created_at.isoformat(),
            }
            for event in events
        ],
    })


def _evaluation_task_payload(task):
    return {
        "id": task.id,
        "name": task.name,
        "prompt": task.prompt,
        "code": task.code,
        "expected_output": task.expected_output,
        "language": task.language,
        "tags": [tag.strip() for tag in task.tags.split(",") if tag.strip()],
        "is_active": task.is_active,
        "created_at": task.created_at.isoformat(),
        "updated_at": task.updated_at.isoformat(),
    }


@login_required(login_url="/login/")
@require_http_methods(["GET", "POST"])
def evaluation_tasks(request):
    if request.method == "POST":
        name = request.POST.get("name", "").strip()[:160]
        prompt = request.POST.get("prompt", "").strip()
        if not name or not prompt:
            return JsonResponse({"success": False, "error": "Task name and prompt are required."}, status=400)
        task = EvaluationTask.objects.create(
            owner=request.user,
            name=name,
            prompt=prompt,
            code=request.POST.get("code", ""),
            expected_output=request.POST.get("expected_output", ""),
            language=request.POST.get("language", "auto").strip()[:50] or "auto",
            tags=request.POST.get("tags", "").strip()[:300],
        )
        return JsonResponse({"success": True, "task": _evaluation_task_payload(task)}, status=201)
    query = request.GET.get("q", "").strip()
    tasks = EvaluationTask.objects.filter(owner=request.user)
    if query:
        tasks = tasks.filter(Q(name__icontains=query) | Q(prompt__icontains=query) | Q(tags__icontains=query))
    return JsonResponse({"success": True, "tasks": [_evaluation_task_payload(task) for task in tasks[:100]]})


@login_required(login_url="/login/")
@require_http_methods(["POST", "DELETE"])
def evaluation_task_detail(request, task_id):
    task = get_object_or_404(EvaluationTask, id=task_id, owner=request.user)
    if request.method == "DELETE":
        task.delete()
        return JsonResponse({"success": True, "deleted": task_id})
    task.name = request.POST.get("name", task.name).strip()[:160] or task.name
    task.prompt = request.POST.get("prompt", task.prompt).strip() or task.prompt
    task.code = request.POST.get("code", task.code)
    task.expected_output = request.POST.get("expected_output", task.expected_output)
    task.language = request.POST.get("language", task.language).strip()[:50] or "auto"
    task.tags = request.POST.get("tags", task.tags).strip()[:300]
    task.is_active = request.POST.get("is_active", "true").lower() not in {"false", "0", "off"}
    task.save()
    return JsonResponse({"success": True, "task": _evaluation_task_payload(task)})


def _evaluation_run_payload(run):
    return {
        "id": run.id,
        "task_id": run.task_id,
        "model_name": run.model_name,
        "response": run.response,
        "status": run.status,
        "duration_ms": run.duration_ms,
        "input_chars": run.input_chars,
        "output_chars": run.output_chars,
        "metadata": run.metadata,
        "created_at": run.created_at.isoformat(),
    }


@login_required(login_url="/login/")
@require_POST
def evaluation_run(request, task_id):
    task = get_object_or_404(EvaluationTask, id=task_id, owner=request.user, is_active=True)
    settings = _user_ollama_settings(request.user)
    model_name = request.POST.get("model", "").strip()[:100] or settings.default_model
    evaluation_prompt = (
        "You are being evaluated as a local coding assistant.\n"
        f"Language: {task.language}\n"
        f"Task: {task.prompt}\n"
        f"Code fixture:\n{task.code}\n"
        "Return a practical answer with corrected code when appropriate."
    )
    run = EvaluationRun.objects.create(
        owner=request.user,
        task=task,
        model_name=model_name,
        input_chars=len(evaluation_prompt),
    )
    started = time.perf_counter()
    try:
        response = requests.post(
            f"{settings.server_url}/api/generate",
            json={
                "model": model_name,
                "prompt": evaluation_prompt,
                "stream": False,
                "options": {
                    "temperature": settings.temperature,
                    "top_p": settings.top_p,
                    "num_ctx": max(512, settings.max_context_chars // 4),
                },
            },
            timeout=(10, 300),
        )
        duration_ms = round((time.perf_counter() - started) * 1000)
        run.duration_ms = duration_ms
        if not response.ok:
            run.status = "failed"
            run.response = response.text[:4000]
            run.metadata = {"status_code": response.status_code}
        else:
            payload = response.json()
            run.response = str(payload.get("response", "")).strip()
            run.output_chars = len(run.response)
            run.status = "completed"
            run.metadata = {"done": payload.get("done", True)}
    except (requests.RequestException, ValueError) as exc:
        run.duration_ms = round((time.perf_counter() - started) * 1000)
        run.status = "failed"
        run.response = str(exc)
        run.metadata = {"error": str(exc)}
    run.save(update_fields=["status", "response", "duration_ms", "output_chars", "metadata"])
    AiEvent.objects.create(
        owner=request.user,
        event_type="evaluation",
        model_name=model_name,
        duration_ms=run.duration_ms,
        input_chars=run.input_chars,
        output_chars=run.output_chars,
        success=run.status == "completed",
        metadata={"task_id": task.id, "run_id": run.id},
    )
    return JsonResponse({"success": run.status == "completed", "run": _evaluation_run_payload(run)}, status=200 if run.status == "completed" else 502)


def _workspace_for_user(user):
    membership = (
        WorkspaceMembership.objects.filter(user=user)
        .select_related("workspace")
        .order_by("workspace_id")
        .first()
    )
    if membership:
        return membership.workspace
    workspace = Workspace.objects.create(owner=user, name=f"{user.username}'s workspace")
    WorkspaceMembership.objects.create(workspace=workspace, user=user, role="admin")
    AuditEvent.objects.create(
        actor=user,
        workspace=workspace,
        event_type="workspace.created",
        details={"name": workspace.name},
    )
    return workspace


def _workspace_membership(user, workspace):
    return WorkspaceMembership.objects.filter(user=user, workspace=workspace).first()


def _workspace_payload(workspace):
    members = (
        WorkspaceMembership.objects.filter(workspace=workspace)
        .select_related("user")
        .order_by("user__username")
    )
    audits = (
        AuditEvent.objects.filter(workspace=workspace)
        .select_related("actor")
        .order_by("-created_at")[:50]
    )
    return {
        "id": workspace.id,
        "name": workspace.name,
        "owner": workspace.owner.username,
        "members": [
            {"id": member.id, "username": member.user.username, "role": member.role}
            for member in members
        ],
        "audit": [
            {
                "event_type": event.event_type,
                "actor": event.actor.username if event.actor else "system",
                "details": event.details,
                "created_at": event.created_at.isoformat(),
            }
            for event in audits
        ],
    }


@login_required(login_url="/login/")
@require_http_methods(["GET", "POST"])
def workspace_api(request):
    workspace = None
    workspace_id = (
        request.POST.get("workspace_id")
        or request.GET.get("workspace_id")
        or request.session.get("workspace_id")
    )
    if workspace_id:
        try:
            candidate = get_object_or_404(Workspace, id=int(workspace_id))
            if _workspace_membership(request.user, candidate):
                workspace = candidate
        except (TypeError, ValueError):
            workspace = None
    if workspace is None:
        workspace = _workspace_for_user(request.user)
    membership = _workspace_membership(request.user, workspace)
    if not membership:
        return JsonResponse({"success": False, "error": "You are not a workspace member."}, status=403)
    request.session["workspace_id"] = workspace.id

    if request.method == "POST":
        action = request.POST.get("action", "").strip().lower()
        if action == "create":
            name = request.POST.get("name", "").strip()[:120]
            if not name:
                return JsonResponse({"success": False, "error": "Workspace name is required."}, status=400)
            workspace = Workspace.objects.create(owner=request.user, name=name)
            WorkspaceMembership.objects.create(workspace=workspace, user=request.user, role="admin")
            AuditEvent.objects.create(actor=request.user, workspace=workspace, event_type="workspace.created", details={"name": name})
            request.session["workspace_id"] = workspace.id
        elif action == "add_member":
            if membership.role != "admin":
                return JsonResponse({"success": False, "error": "Only workspace admins can manage members."}, status=403)
            username = request.POST.get("username", "").strip()
            role = request.POST.get("role", "developer").strip()
            if role not in dict(WorkspaceMembership.ROLE_CHOICES):
                return JsonResponse({"success": False, "error": "Invalid workspace role."}, status=400)
            target = get_object_or_404(User, username=username)
            member, _ = WorkspaceMembership.objects.update_or_create(
                workspace=workspace,
                user=target,
                defaults={"role": role},
            )
            AuditEvent.objects.create(
                actor=request.user,
                workspace=workspace,
                event_type="member.role_changed",
                details={"username": target.username, "role": member.role},
            )
        elif action == "set_role":
            if membership.role != "admin":
                return JsonResponse({"success": False, "error": "Only workspace admins can manage roles."}, status=403)
            member = get_object_or_404(WorkspaceMembership, id=request.POST.get("member_id"), workspace=workspace)
            role = request.POST.get("role", "").strip()
            if role not in dict(WorkspaceMembership.ROLE_CHOICES):
                return JsonResponse({"success": False, "error": "Invalid workspace role."}, status=400)
            member.role = role
            member.save(update_fields=["role"])
            AuditEvent.objects.create(actor=request.user, workspace=workspace, event_type="member.role_changed", details={"username": member.user.username, "role": role})
        elif action == "remove_member":
            if membership.role != "admin":
                return JsonResponse({"success": False, "error": "Only workspace admins can remove members."}, status=403)
            member = get_object_or_404(WorkspaceMembership, id=request.POST.get("member_id"), workspace=workspace)
            if member.user_id == workspace.owner_id:
                return JsonResponse({"success": False, "error": "The workspace owner cannot be removed."}, status=400)
            username = member.user.username
            member.delete()
            AuditEvent.objects.create(actor=request.user, workspace=workspace, event_type="member.removed", details={"username": username})
        elif action not in {"", "switch"}:
            return JsonResponse({"success": False, "error": "Unsupported workspace action."}, status=400)

    return JsonResponse({"success": True, "workspace": _workspace_payload(workspace)})


def _policy_payload(policy, membership):
    return {
        "identity": {
            "username": membership.user.username,
            "role": membership.role,
            "authentication": "local Django account",
        },
        "policy": {
            "require_approval_for_git": policy.require_approval_for_git,
            "require_approval_for_tools": policy.require_approval_for_tools,
            "require_approval_for_deploy": policy.require_approval_for_deploy,
            "require_tests": policy.require_tests,
            "allow_external_connectors": policy.allow_external_connectors,
            "audit_retention_days": policy.audit_retention_days,
        },
    }


@login_required(login_url="/login/")
@require_http_methods(["GET", "POST"])
def identity_policy_api(request):
    workspace = _workspace_for_user(request.user)
    membership = _workspace_membership(request.user, workspace)
    if not membership:
        return JsonResponse({"success": False, "error": "You are not a workspace member."}, status=403)
    policy, _ = WorkspacePolicy.objects.get_or_create(workspace=workspace)
    if request.method == "POST":
        if membership.role != "admin":
            return JsonResponse({"success": False, "error": "Only workspace admins can change policy."}, status=403)
        for field in (
            "require_approval_for_git",
            "require_approval_for_tools",
            "require_approval_for_deploy",
            "require_tests",
            "allow_external_connectors",
        ):
            setattr(policy, field, request.POST.get(field, "false").lower() in {"1", "true", "yes", "on"})
        try:
            policy.audit_retention_days = min(3650, max(7, int(request.POST.get("audit_retention_days", "90"))))
        except (TypeError, ValueError):
            return JsonResponse({"success": False, "error": "Audit retention must be a number of days."}, status=400)
        policy.save()
        AuditEvent.objects.create(
            actor=request.user,
            workspace=workspace,
            event_type="policy.updated",
            details=_policy_payload(policy, membership)["policy"],
        )
    return JsonResponse({"success": True, "workspace": workspace.name, **_policy_payload(policy, membership)})


@login_required(login_url="/login/")
@require_POST
def devops_generate(request):
    kind = request.POST.get("kind", "dockerfile").strip()
    code = request.POST.get("code", "")[:30_000]
    filenames = request.POST.getlist("filenames")
    try:
        artifact = generate_artifact(kind, code, filenames)
    except ValueError as exc:
        return JsonResponse({"success": False, "error": str(exc)}, status=400)
    return JsonResponse({
        "success": True,
        "kind": kind,
        "artifact": artifact,
        "checklist": [
            "Review exposed ports and runtime command.",
            "Move secrets to environment variables or a secret manager.",
            "Run the generated CI job and security scan before deployment.",
        ],
    })


@login_required(login_url="/login/")
@require_POST
def devops_logs(request):
    logs = request.POST.get("logs", "")[:50_000]
    return JsonResponse({"success": True, **analyze_logs(logs)})


@login_required(login_url="/login/")
@require_POST
def documentation_generate(request):
    doc_type = request.POST.get("doc_type", "readme").strip()
    project_name = request.POST.get("project_name", "Local project")
    code = request.POST.get("code", "")[:30_000]
    filename = request.POST.get("filename", "current-code")
    change_summary = request.POST.get("change_summary", "")[:2_000]
    files = [{"filename": filename, "content": code}]
    raw_files = request.POST.get("files_json", "")
    if raw_files:
        try:
            parsed_files = json.loads(raw_files)
            if isinstance(parsed_files, list):
                files.extend(item for item in parsed_files[:100] if isinstance(item, dict))
        except (TypeError, ValueError):
            return JsonResponse({"success": False, "error": "files_json must be a JSON array."}, status=400)
    if doc_type not in {"readme", "api", "changelog", "onboarding"}:
        return JsonResponse({"success": False, "error": "Unsupported documentation type."}, status=400)
    markdown = generate_documentation(files, doc_type, project_name, change_summary)
    return JsonResponse({"success": True, "doc_type": doc_type, "markdown": markdown[:60_000]})


@login_required(login_url="/login/")
@require_POST
def review_gate_api(request):
    code = request.POST.get("code", "")[:30_000]
    filename = request.POST.get("filename", "editor-buffer")
    language = request.POST.get("language", "auto").strip().lower()
    diff = request.POST.get("diff", "")
    tests = request.POST.get("tests", "")
    files = [{"filename": filename, "content": code}] if code else []
    raw_files = request.POST.get("files_json", "")
    if raw_files:
        try:
            parsed = json.loads(raw_files)
            if not isinstance(parsed, list) or len(parsed) > MAX_PROJECT_FILES:
                raise ValueError("invalid file list")
            files = [
                {"filename": _safe_filename(item.get("filename", "uploaded-file")), "content": str(item.get("content", ""))}
                for item in parsed if isinstance(item, dict)
            ]
        except (TypeError, ValueError, json.JSONDecodeError):
            return JsonResponse({"success": False, "error": "Invalid review file list."}, status=400)
    if not files:
        return JsonResponse({"success": False, "error": "Provide code or project files to review."}, status=400)
    return JsonResponse({"success": True, **review_gate(files, language, diff, tests)})


@login_required(login_url="/login/")
@require_POST
def dependencies_analyze(request):
    filename = request.POST.get("filename", "requirements.txt")
    content = request.POST.get("content", "")[:30_000]
    files = [{"filename": filename, "content": content}]
    raw_files = request.POST.get("files_json", "")
    if raw_files:
        try:
            parsed = json.loads(raw_files)
            if not isinstance(parsed, list) or len(parsed) > MAX_PROJECT_FILES:
                raise ValueError("invalid dependency file list")
            files = [
                {"filename": _safe_filename(item.get("filename", "manifest")), "content": str(item.get("content", ""))}
                for item in parsed if isinstance(item, dict)
            ]
        except (TypeError, ValueError, json.JSONDecodeError):
            return JsonResponse({"success": False, "error": "Invalid dependency file list."}, status=400)
    return JsonResponse({"success": True, **analyze_dependencies(files)})


@login_required(login_url="/login/")
@require_POST
def browser_test_generate(request):
    return JsonResponse({
        "success": True,
        "test_code": generate_playwright_test(
            request.POST.get("base_url"),
            request.POST.get("flow"),
            request.POST.get("snapshot_name", "home"),
        ),
        "command": "npx playwright test --update-snapshots",
    })


@login_required(login_url="/login/")
@require_POST
def browser_test_report(request):
    return JsonResponse({"success": True, **analyze_browser_report(request.POST.get("report", "")[:50_000])})


@login_required(login_url="/login/")
@require_POST
def model_route(request):
    raw_models = request.POST.get("models_json", "[]")
    try:
        models = json.loads(raw_models)
        if not isinstance(models, list):
            raise ValueError("models must be a list")
    except (TypeError, ValueError, json.JSONDecodeError):
        return JsonResponse({"success": False, "error": "models_json must be a JSON array."}, status=400)
    try:
        memory_gb = max(0, float(request.POST.get("memory_gb", "0") or 0))
    except (TypeError, ValueError):
        memory_gb = 0
    gpu = request.POST.get("gpu", "").lower() in {"1", "true", "yes", "on"}
    return JsonResponse({
        "success": True,
        **route_model(request.POST.get("task", ""), models, memory_gb, gpu),
    })


@login_required(login_url="/login/")
@require_POST
def devcontainer_generate(request):
    project_name = request.POST.get("project_name", "Syntax Local AI")
    files = []
    raw_files = request.POST.get("files_json", "")
    if raw_files:
        try:
            parsed = json.loads(raw_files)
            if not isinstance(parsed, list) or len(parsed) > MAX_PROJECT_FILES:
                raise ValueError("invalid file list")
            files = [item for item in parsed if isinstance(item, dict)]
        except (TypeError, ValueError, json.JSONDecodeError):
            return JsonResponse({"success": False, "error": "Invalid project file list."}, status=400)
    filename = request.POST.get("filename", "")
    if filename:
        files.append({"filename": filename, "content": request.POST.get("code", "")})
    return JsonResponse({
        "success": True,
        "config": generate_devcontainer(files, project_name),
        "path": ".devcontainer/devcontainer.json",
        "notes": [
            "Review forwarded ports for your application.",
            "Keep secrets outside the container configuration.",
            "Use the same container definition in local development and CI.",
        ],
    })


@login_required(login_url="/login/")
@require_POST
def incident_analyze(request):
    return JsonResponse({
        "success": True,
        **analyze_incident(
            request.POST.get("logs", "")[:50_000],
            request.POST.get("traces", "")[:30_000],
            request.POST.get("metrics", "")[:20_000],
        ),
    })


@login_required(login_url="/login/")
@require_POST
def architecture_analyze(request):
    raw_files = request.POST.get("files_json", "")
    try:
        files = json.loads(raw_files or "[]")
        if not isinstance(files, list) or len(files) > MAX_PROJECT_FILES:
            raise ValueError("invalid architecture file list")
    except (TypeError, ValueError, json.JSONDecodeError):
        return JsonResponse({"success": False, "error": "files_json must be a JSON array."}, status=400)
    files = [
        {"filename": _safe_filename(item.get("filename", "untitled")), "content": str(item.get("content", ""))}
        for item in files if isinstance(item, dict)
    ]
    return JsonResponse({"success": True, **analyze_architecture(files)})


@login_required(login_url="/login/")
@require_POST
def api_contract_analyze(request):
    result = analyze_api_contract(
        request.POST.get("spec", "")[:50_000],
        request.POST.get("code", "")[:50_000],
    )
    if result.get("error"):
        return JsonResponse({"success": False, "error": result["error"]}, status=400)
    return JsonResponse({"success": True, **result})


@login_required(login_url="/login/")
@require_POST
def provenance_generate(request):
    raw_files = request.POST.get("files_json", "[]")
    try:
        files = json.loads(raw_files)
        if not isinstance(files, list) or len(files) > MAX_PROJECT_FILES:
            raise ValueError("invalid provenance file list")
    except (TypeError, ValueError, json.JSONDecodeError):
        return JsonResponse({"success": False, "error": "files_json must be a JSON array."}, status=400)
    return JsonResponse({
        "success": True,
        "provenance": generate_provenance(
            [item for item in files if isinstance(item, dict)],
            request.POST.get("artifact_name", "local-artifact"),
            request.POST.get("commit", "unknown"),
        ),
    })


@login_required(login_url="/login/")
@require_POST
def provenance_verify(request):
    return JsonResponse({"success": True, **verify_provenance(request.POST.get("provenance", "")[:100_000])})


def _mcp_tools():
    return [
        {"name": "project.search", "description": "Search indexed project code.", "write": False},
        {"name": "git.status", "description": "Read local Git status.", "write": False},
        {"name": "git.diff", "description": "Read the local Git diff.", "write": False},
        {"name": "sandbox.run", "description": "Run code in the guarded sandbox.", "write": False, "approval_required": True},
        {"name": "git.stage", "description": "Stage selected local Git paths.", "write": True, "approval_required": True},
        {"name": "git.commit", "description": "Create a local Git commit.", "write": True, "approval_required": True},
    ]


def _mcp_call(user, tool_name, arguments):
    tool = next((item for item in _mcp_tools() if item["name"] == tool_name), None)
    if not tool:
        return False, {}, "Unknown MCP tool."
    if tool.get("approval_required") and not arguments.get("approved"):
        return False, {}, "This tool requires explicit approved=true."
    try:
        if tool_name == "project.search":
            return True, {"results": _search_knowledge(str(arguments.get("query", "")), owner=user)}, ""
        if tool_name == "sandbox.run":
            result = run_sandboxed_code(
                str(arguments.get("language", "python")),
                str(arguments.get("code", "")),
            )
            return result["success"], result, result.get("stderr", "")
        if tool_name == "git.status":
            result = _run_git(["status", "--short"])
            if isinstance(result, tuple):
                return False, {}, result[1]
            return result.returncode == 0, {"raw": result.stdout}, result.stderr.strip()
        if tool_name == "git.diff":
            result = _run_git(["diff", "HEAD", "--"])
            if isinstance(result, tuple):
                return False, {}, result[1]
            return result.returncode == 0, {"diff": result.stdout[:MAX_GIT_OUTPUT_CHARS]}, result.stderr.strip()
        if tool_name == "git.stage":
            paths = arguments.get("paths") or []
            if not isinstance(paths, list) or any(not _git_path_is_safe(path) for path in paths):
                return False, {}, "Invalid Git paths."
            result = _run_git(["add", "--", *paths] if paths else ["add", "-A"])
            if isinstance(result, tuple):
                return False, {}, result[1]
            return result.returncode == 0, {"staged": paths or ["all changes"]}, result.stderr.strip()
        if tool_name == "git.commit":
            message = str(arguments.get("message", "")).strip()
            if not message or len(message) > 200:
                return False, {}, "Commit message is required and limited to 200 characters."
            result = _run_git(["commit", "-m", message])
            if isinstance(result, tuple):
                return False, {}, result[1]
            return result.returncode == 0, {"output": result.stdout}, (result.stderr or result.stdout).strip()
    except (TypeError, ValueError) as exc:
        return False, {}, str(exc)
    return False, {}, "MCP tool is not implemented."


def _mcp_log(user, tool_name, arguments, success, error):
    McpToolCall.objects.create(
        owner=user,
        tool_name=tool_name,
        arguments=arguments,
        success=success,
        error=error[:2000],
    )


def _mcp_connector_payload(connector):
    return {
        "id": connector.id,
        "name": connector.name,
        "connector_type": connector.connector_type,
        "config": connector.config,
        "enabled": connector.enabled,
        "allow_write": connector.allow_write,
    }


@login_required(login_url="/login/")
@require_http_methods(["GET", "POST"])
def mcp_connectors(request):
    if request.method == "POST":
        name = request.POST.get("name", "").strip()
        connector_type = request.POST.get("connector_type", "custom").strip()
        if not name or connector_type not in dict(McpConnector.CONNECTOR_TYPES):
            return JsonResponse({"success": False, "error": "Connector name and type are required."}, status=400)
        try:
            config = json.loads(request.POST.get("config", "{}"))
            if not isinstance(config, dict):
                raise ValueError
        except (TypeError, ValueError, json.JSONDecodeError):
            return JsonResponse({"success": False, "error": "Connector config must be a JSON object."}, status=400)
        connector = McpConnector.objects.create(
            owner=request.user,
            name=name[:120],
            connector_type=connector_type,
            config=config,
            allow_write=request.POST.get("allow_write") == "true",
        )
        return JsonResponse({"success": True, "connector": _mcp_connector_payload(connector)})
    return JsonResponse({
        "success": True,
        "connectors": [
            _mcp_connector_payload(item)
            for item in McpConnector.objects.filter(owner=request.user).order_by("name")
        ],
        "tools": _mcp_tools(),
        "recent_calls": list(
            McpToolCall.objects.filter(owner=request.user).order_by("-created_at")[:20].values(
                "tool_name", "success", "error", "created_at"
            )
        ),
    })


@login_required(login_url="/login/")
@require_http_methods(["DELETE"])
def mcp_connector_delete(request, connector_id):
    connector = get_object_or_404(McpConnector, id=connector_id, owner=request.user)
    connector.delete()
    return JsonResponse({"success": True, "deleted_id": connector_id})


@login_required(login_url="/login/")
@require_POST
def mcp_rpc(request):
    try:
        payload = json.loads(request.body or "{}")
    except (TypeError, ValueError, json.JSONDecodeError):
        return JsonResponse({"jsonrpc": "2.0", "error": {"code": -32700, "message": "Invalid JSON."}}, status=400)
    request_id = payload.get("id")
    method = payload.get("method")
    if method == "tools/list":
        result = {"tools": _mcp_tools()}
    elif method == "tools/call":
        params = payload.get("params") or {}
        tool_name = params.get("name", "")
        arguments = params.get("arguments") or {}
        success, result, error = _mcp_call(request.user, tool_name, arguments)
        _mcp_log(request.user, tool_name, arguments, success, error)
        if not success:
            return JsonResponse({"jsonrpc": "2.0", "id": request_id, "error": {"code": -32000, "message": error}}, status=400)
        result = {"content": [{"type": "text", "text": json.dumps(result, ensure_ascii=False)}]}
    else:
        return JsonResponse({"jsonrpc": "2.0", "id": request_id, "error": {"code": -32601, "message": "Method not found."}}, status=400)
    return JsonResponse({"jsonrpc": "2.0", "id": request_id, "result": result})


@login_required(login_url="/login/")
@require_POST
def quality_analyze(request):
    code = request.POST.get("code", "")
    language = request.POST.get("language", "auto").strip().lower()
    mode = request.POST.get("mode", "all").strip().lower()
    if not code.strip():
        return JsonResponse({"success": False, "error": "Enter code to analyze."}, status=400)
    if len(code) > MAX_EXECUTION_CHARS:
        return JsonResponse({"success": False, "error": "Analysis input is too large."}, status=400)
    return JsonResponse({"success": True, **analyze_code_quality(code, language, mode)})


@login_required(login_url="/login/")
@require_POST
def security_scan(request):
    code = request.POST.get("code", "")
    filename = request.POST.get("filename", "editor-buffer")
    files = [{"filename": filename, "content": code}] if code else []
    raw_files = request.POST.get("files", "")
    if raw_files:
        try:
            submitted = json.loads(raw_files)
            if not isinstance(submitted, list) or len(submitted) > MAX_PROJECT_FILES:
                raise ValueError("invalid file list")
            files = [
                {"filename": _safe_filename(item.get("filename", "uploaded-file")), "content": str(item.get("content", ""))}
                for item in submitted
            ]
        except (TypeError, ValueError, json.JSONDecodeError):
            return JsonResponse({"success": False, "error": "Invalid security scan file list."}, status=400)
    if not files or sum(len(item["content"]) for item in files) > MAX_TEST_CHARS:
        return JsonResponse({"success": False, "error": "Provide code or a project smaller than 20,000 characters."}, status=400)
    return JsonResponse({"success": True, **scan_files(files)})


@login_required(login_url="/login/")
@require_POST
def generate_tests(request):
    code = request.POST.get("code", "")
    language = request.POST.get("language", "auto").strip().lower()
    if not code.strip():
        return JsonResponse({"success": False, "error": "Enter code before generating tests."}, status=400)
    if len(code) > MAX_TEST_CHARS:
        return JsonResponse({"success": False, "error": "Test generation input is too large."}, status=400)
    result = analyze_code_quality(code, language, "tests")
    return JsonResponse({"success": True, "test_code": result["test_template"], "summary": "Editable test scaffold generated."})


@login_required(login_url="/login/")
@require_POST
def run_tests(request):
    code = request.POST.get("code", "")
    test_code = request.POST.get("test_code", "")
    language = request.POST.get("language", "python").strip().lower()
    if not code.strip() or not test_code.strip():
        return JsonResponse({"success": False, "error": "Provide source code and test code."}, status=400)
    if len(code) + len(test_code) > MAX_TEST_CHARS:
        return JsonResponse({"success": False, "error": "Combined test input is too large."}, status=400)
    result = run_sandboxed_code(language, code.rstrip() + "\n\n" + test_code.lstrip())
    return JsonResponse({
        "success": result["success"],
        "result": result,
        "summary": "Tests passed." if result["success"] else "Tests failed.",
    })


@login_required(login_url="/login/")
@require_POST
def preview_patch(request):
    original = request.POST.get("original", "")
    updated = request.POST.get("updated", "")
    filename = request.POST.get("filename", "editor-buffer")
    diff = "".join(difflib.unified_diff(
        original.splitlines(keepends=True),
        updated.splitlines(keepends=True),
        fromfile=filename + " (current)",
        tofile=filename + " (proposed)",
        n=3,
    ))
    return JsonResponse({
        "success": True,
        "changed": original != updated,
        "diff": diff or "No changes detected.",
    })


@require_POST
def ask_code(request):
    prompt = request.POST.get("prompt", "").strip()
    language = request.POST.get("language", "auto").strip()
    code = request.POST.get("code", "").strip()
    session_id = request.POST.get("session_id", "").strip()
    edit_message_id = request.POST.get("edit_message_id", "").strip()
    requested_model = request.POST.get("model", "").strip()

    uploaded_files = request.FILES.getlist("files")
    image_files = request.FILES.getlist("images")
    relative_paths = request.POST.getlist("file_paths")
    single_file = request.FILES.get("file")
    if single_file and not uploaded_files:
        uploaded_files = [single_file]

    if (uploaded_files or image_files) and not request.user.is_authenticated:
        return JsonResponse({
            "success": False,
            "login_required": True,
            "error": "Create a free account or sign in to upload files and images.",
        }, status=403)

    if len(uploaded_files) > MAX_PROJECT_FILES:
        return JsonResponse({
            "success": False,
            "error": f"Please upload no more than {MAX_PROJECT_FILES} files at once.",
        }, status=400)

    uploaded_code_parts = []
    uploaded_filenames = []
    image_data = []
    image_filenames = []

    for index, uploaded_file in enumerate(uploaded_files):
        submitted_path = relative_paths[index] if index < len(relative_paths) else uploaded_file.name
        filename = _safe_filename(submitted_path)
        uploaded_filenames.append(filename)

        try:
            if uploaded_file.size > MAX_FILE_BYTES:
                uploaded_code_parts.append(
                    f"\n\n===== FILE: {filename} =====\n"
                    f"Skipped because it is larger than {MAX_FILE_BYTES // 1_000_000} MB."
                )
                continue

            raw_content = uploaded_file.read()
            file_text = raw_content.decode("utf-8", errors="ignore")
            if "\x00" in file_text:
                continue

            source_type = "project" if "/" in filename else "upload"
            _save_knowledge_document(filename, file_text, source_type, request.user)
            uploaded_code_parts.append(
                f"\n\n===== FILE: {filename} =====\n{file_text}"
            )
        except Exception as ex:
            uploaded_code_parts.append(
                f"\n\n===== FILE: {filename} =====\n"
                f"Unable to read file: {str(ex)}"
            )

    for image_file in image_files:
        if image_file.size > MAX_IMAGE_BYTES:
            return JsonResponse({
                "success": False,
                "error": f"Image {image_file.name} is larger than 5 MB.",
            }, status=400)
        if not image_file.content_type.startswith("image/"):
            return JsonResponse({
                "success": False,
                "error": f"{image_file.name} is not a supported image.",
            }, status=400)
        image_filenames.append(_safe_filename(image_file.name))
        image_data.append(base64.b64encode(image_file.read()).decode("ascii"))
    uploaded_code = "\n".join(uploaded_code_parts)
    final_code = uploaded_code.strip() if uploaded_code.strip() else code

    if image_data and not prompt and not final_code:
        prompt = "Describe this image and explain any visible code or error."
    if not prompt and not final_code:
        return JsonResponse({
            "success": False,
            "error": "Please enter prompt or upload/paste code.",
        }, status=400)

    owner = request.user if request.user.is_authenticated else None
    user_settings = _user_ollama_settings(request.user) if owner else None
    ollama_base_url = user_settings.server_url if user_settings else OLLAMA_BASE_URL
    configured_default_model = user_settings.default_model if user_settings else DEFAULT_MODEL
    revision_branch_id = None
    if session_id:
        session = get_object_or_404(ChatSession, id=session_id, owner=owner)
        model_name = requested_model or session.model_name or configured_default_model
        if image_data and model_name == DEFAULT_MODEL:
            model_name = VISION_MODEL
        if session.model_name != model_name:
            session.model_name = model_name
            session.save(update_fields=["model_name", "updated_at"])
    else:
        title = prompt[:60] if prompt else (
            uploaded_filenames[0][:60] if uploaded_filenames else "New Chat"
        )
        model_name = requested_model or configured_default_model
        if image_data and model_name == DEFAULT_MODEL:
            model_name = VISION_MODEL
        session = ChatSession.objects.create(
            owner=owner,
            title=title,
            model_name=model_name,
        )

    if edit_message_id:
        if not session_id:
            return JsonResponse({"success": False, "error": "An existing chat is required to edit a message."}, status=400)
        target = get_object_or_404(
            ChatMessage,
            id=edit_message_id,
            session=session,
            role="user",
        )
        revision_branch_id = uuid.uuid4()
        previous_messages = ChatMessage.objects.filter(
            session=session,
            id__gte=target.id,
        ).order_by("id")
        ConversationRevision.objects.bulk_create([
            ConversationRevision(
                session=session,
                source_message_id=message.id,
                branch_id=revision_branch_id,
                role=message.role,
                content=message.content,
                model_name=message.model_name,
            )
            for message in previous_messages
        ])
        previous_messages.delete()

    user_message_parts = []
    if prompt:
        user_message_parts.append(f"Prompt:\n{prompt}")
    if uploaded_filenames:
        user_message_parts.append("Uploaded Files:\n" + "\n".join(uploaded_filenames))
    if image_filenames:
        user_message_parts.append("Uploaded Images:\n" + "\n".join(image_filenames))
    if final_code:
        user_message_parts.append(f"Code:\n{final_code[:6000]}")

    user_message = ChatMessage.objects.create(
        session=session,
        role="user",
        content="\n\n".join(user_message_parts),
        filename=", ".join(uploaded_filenames + image_filenames),
        model_name=model_name,
    )

    max_code_chars = 24_000
    truncated_note = ""
    if len(final_code) > max_code_chars:
        final_code = final_code[:max_code_chars]
        truncated_note = "\n\nNote: the uploaded code was truncated for the local model."

    relevant_chunks = _search_knowledge(prompt or code, owner=owner)
    knowledge_context = "\n\n".join(
        f"===== PROJECT CONTEXT: {item['filename']}:{item['line_start']}-{item['line_end']} =====\n"
        f"{item['content']}"
        for item in relevant_chunks
    )

    full_prompt = f"""
You are a fully offline coding assistant running locally.

Language:
{language}

User task:
{prompt}

Uploaded files:
{", ".join(uploaded_filenames)}

Relevant project context:
{knowledge_context or "No matching project context found."}

Code:
{final_code}

{truncated_note}

Instructions:
1. Understand all uploaded files together.
2. Explain clearly.
3. If there is an error, show the exact problem.
4. Give corrected code where required.
5. Mention which file needs change.
6. Keep answer practical.
7. Do not say you need internet.
"""

    ai_event = None
    event_started = time.perf_counter()
    try:
        ai_event = AiEvent.objects.create(
            owner=owner,
            event_type="chat",
            model_name=model_name,
            input_chars=len(full_prompt),
        )
        response = requests.post(
            f"{ollama_base_url}/api/generate",
            json={
                "model": model_name,
                "prompt": full_prompt,
                "stream": True,
                "options": {
                    "temperature": user_settings.temperature if user_settings else 0.2,
                    "top_p": user_settings.top_p if user_settings else 0.9,
                    "num_ctx": max(512, (user_settings.max_context_chars if user_settings else 24000) // 4),
                },
                **({"images": image_data} if image_data else {}),
            },
            timeout=(10, 300),
            stream=True,
        )
        if response.status_code != 200:
            ai_event.success = False
            ai_event.duration_ms = round((time.perf_counter() - event_started) * 1000)
            ai_event.metadata = {"status_code": response.status_code, "error": response.text[:500]}
            ai_event.save(update_fields=["success", "duration_ms", "metadata"])
            return JsonResponse({"success": False, "error": response.text}, status=500)

        def stream_answer():
            answer_parts = []
            try:
                for raw_line in response.iter_lines(decode_unicode=True):
                    if not raw_line:
                        continue
                    data = json.loads(raw_line)
                    token = data.get("response", "")
                    if token:
                        answer_parts.append(token)
                        yield _event({"type": "token", "token": token})
                    if data.get("done"):
                        break

                answer = "".join(answer_parts).strip()
                ChatMessage.objects.create(
                    session=session,
                    role="assistant",
                    content=answer,
                    model_name=model_name,
                )
                ai_event.duration_ms = round((time.perf_counter() - event_started) * 1000)
                ai_event.output_chars = len(answer)
                ai_event.metadata = {
                    "sources": len(relevant_chunks),
                    "images": len(image_data),
                    "session_id": session.id,
                }
                ai_event.save(update_fields=["duration_ms", "output_chars", "metadata"])
                session.save(update_fields=["updated_at"])
                yield _event({
                    "type": "complete",
                    "session_id": session.id,
                    "title": session.title,
                    "model": model_name,
                    "user_message_id": user_message.id,
                    "revision_branch_id": str(revision_branch_id) if revision_branch_id else "",
                    "sources": [
                        {
                            "filename": item["filename"],
                            "language": item["language"],
                            "line_start": item["line_start"],
                            "line_end": item["line_end"],
                            "content": item["content"],
                        }
                        for item in relevant_chunks
                    ],
                    "answer": answer,
                })
            except Exception as ex:
                if ai_event:
                    ai_event.success = False
                    ai_event.duration_ms = round((time.perf_counter() - event_started) * 1000)
                    ai_event.metadata = {"error": str(ex)[:500]}
                    ai_event.save(update_fields=["success", "duration_ms", "metadata"])
                yield _event({"type": "error", "error": str(ex)})

        streaming_response = StreamingHttpResponse(
            stream_answer(),
            content_type="application/x-ndjson",
        )
        streaming_response["Cache-Control"] = "no-cache"
        return streaming_response
    except requests.exceptions.ConnectionError:
        if ai_event:
            ai_event.success = False
            ai_event.duration_ms = round((time.perf_counter() - event_started) * 1000)
            ai_event.metadata = {"error": "Ollama is not running"}
            ai_event.save(update_fields=["success", "duration_ms", "metadata"])
        return JsonResponse({
            "success": False,
            "error": "Ollama is not running. Start Ollama first.",
        }, status=500)
    except requests.exceptions.Timeout:
        if ai_event:
            ai_event.success = False
            ai_event.duration_ms = round((time.perf_counter() - event_started) * 1000)
            ai_event.metadata = {"error": "Model response timeout"}
            ai_event.save(update_fields=["success", "duration_ms", "metadata"])
        return JsonResponse({
            "success": False,
            "error": "Model response timeout. Try smaller files or a smaller prompt.",
        }, status=500)
    except Exception as ex:
        if ai_event:
            ai_event.success = False
            ai_event.duration_ms = round((time.perf_counter() - event_started) * 1000)
            ai_event.metadata = {"error": str(ex)[:500]}
            ai_event.save(update_fields=["success", "duration_ms", "metadata"])
        return JsonResponse({"success": False, "error": str(ex)}, status=500)
