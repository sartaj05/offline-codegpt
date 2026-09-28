import ast
import base64
import hashlib
import json
import os
import re
import sqlite3
import time
import uuid
from pathlib import PurePosixPath

import requests

from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from django.db.models import Count, Min
from django.http import HttpResponse, JsonResponse, StreamingHttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from .models import (
    ChatMessage,
    ChatSession,
    ConversationRevision,
    KnowledgeChunk,
    KnowledgeDocument,
    LocalModelConfig,
)
from .quality import analyze_code_quality


OLLAMA_BASE_URL = "http://127.0.0.1:11434"
OLLAMA_URL = f"{OLLAMA_BASE_URL}/api/generate"
DEFAULT_MODEL = "qwen2.5-coder:1.5b"
VISION_MODEL = os.environ.get("OLLAMA_VISION_MODEL", "llava:latest")
MAX_PROJECT_FILES = 100
MAX_FILE_BYTES = 1_000_000
MAX_IMAGE_BYTES = 5_000_000
CHUNK_SIZE = 2_000
MAX_EXECUTION_CHARS = 20_000


def _available_models():
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
        response = requests.get(f"{OLLAMA_BASE_URL}/api/tags", timeout=3)
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
        ChatSession.objects.filter(owner=request.user).order_by("-updated_at")[:30]
        if request.user.is_authenticated
        else ChatSession.objects.none()
    )
    return render(request, "chat/index.html", {
        "sessions": sessions,
        "models": _available_models(),
        "default_model": DEFAULT_MODEL,
    })


def model_list(request):
    return JsonResponse({
        "success": True,
        "models": _available_models(),
        "default_model": DEFAULT_MODEL,
    })


@login_required(login_url="/login/")
def knowledge_search(request):
    query = request.GET.get("q", "").strip()
    return JsonResponse({
        "success": True,
        "query": query,
        "results": _search_knowledge(query, owner=request.user),
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

    started = time.perf_counter()
    if language in ("auto", "py", "python"):
        try:
            ast.parse(code)
            return JsonResponse({
                "success": True,
                "stdout": "Python syntax is valid. Execution is disabled in safe local mode.",
                "stderr": "",
                "duration_ms": round((time.perf_counter() - started) * 1000),
            })
        except SyntaxError as ex:
            return JsonResponse({
                "success": False,
                "stdout": "",
                "stderr": f"Line {ex.lineno}: {ex.msg}",
                "duration_ms": round((time.perf_counter() - started) * 1000),
            })

    if language in ("js", "javascript", "node"):
        valid, error = _javascript_check(code)
        return JsonResponse({
            "success": valid,
            "stdout": "JavaScript structure looks valid. Execution is disabled in safe local mode." if valid else "",
            "stderr": error,
            "duration_ms": round((time.perf_counter() - started) * 1000),
        })

    if language == "sql":
        try:
            connection = sqlite3.connect(":memory:")
            cursor = connection.cursor()
            output = []
            for statement in (part.strip() for part in code.split(";") if part.strip()):
                cursor.execute(statement)
                if cursor.description:
                    output.append(" | ".join(column[0] for column in cursor.description))
                    output.extend(" | ".join(str(value) for value in row) for row in cursor.fetchall())
            connection.close()
            return JsonResponse({
                "success": True,
                "stdout": "\n".join(output) or "SQL completed without rows.",
                "stderr": "",
                "duration_ms": round((time.perf_counter() - started) * 1000),
            })
        except sqlite3.Error as ex:
            return JsonResponse({
                "success": False,
                "stdout": "",
                "stderr": str(ex),
                "duration_ms": round((time.perf_counter() - started) * 1000),
            })

    return JsonResponse({
        "success": False,
        "error": "Safe checks support Python, JavaScript, and in-memory SQL.",
    }, status=400)


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
    revision_branch_id = None
    if session_id:
        session = get_object_or_404(ChatSession, id=session_id, owner=owner)
        model_name = requested_model or session.model_name or DEFAULT_MODEL
        if image_data and model_name == DEFAULT_MODEL:
            model_name = VISION_MODEL
        if session.model_name != model_name:
            session.model_name = model_name
            session.save(update_fields=["model_name", "updated_at"])
    else:
        title = prompt[:60] if prompt else (
            uploaded_filenames[0][:60] if uploaded_filenames else "New Chat"
        )
        model_name = requested_model or DEFAULT_MODEL
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
        f"===== PROJECT CONTEXT: {item['filename']} (chunk {item['chunk_index']}) =====\n"
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

    try:
        response = requests.post(
            OLLAMA_URL,
            json={
                "model": model_name,
                "prompt": full_prompt,
                "stream": True,
                **({"images": image_data} if image_data else {}),
            },
            timeout=(10, 300),
            stream=True,
        )
        if response.status_code != 200:
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
                session.save(update_fields=["updated_at"])
                yield _event({
                    "type": "complete",
                    "session_id": session.id,
                    "title": session.title,
                    "model": model_name,
                    "user_message_id": user_message.id,
                    "revision_branch_id": str(revision_branch_id) if revision_branch_id else "",
                    "answer": answer,
                })
            except Exception as ex:
                yield _event({"type": "error", "error": str(ex)})

        streaming_response = StreamingHttpResponse(
            stream_answer(),
            content_type="application/x-ndjson",
        )
        streaming_response["Cache-Control"] = "no-cache"
        return streaming_response
    except requests.exceptions.ConnectionError:
        return JsonResponse({
            "success": False,
            "error": "Ollama is not running. Start Ollama first.",
        }, status=500)
    except requests.exceptions.Timeout:
        return JsonResponse({
            "success": False,
            "error": "Model response timeout. Try smaller files or a smaller prompt.",
        }, status=500)
    except Exception as ex:
        return JsonResponse({"success": False, "error": str(ex)}, status=500)
