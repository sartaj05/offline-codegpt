import ast
import hashlib
import json
import re
import sqlite3
import time
from pathlib import PurePosixPath

import requests

from django.http import HttpResponse, JsonResponse, StreamingHttpResponse
from django.shortcuts import get_object_or_404, render
from django.views.decorators.http import require_POST

from .models import (
    ChatMessage,
    ChatSession,
    KnowledgeChunk,
    KnowledgeDocument,
    LocalModelConfig,
)


OLLAMA_BASE_URL = "http://127.0.0.1:11434"
OLLAMA_URL = f"{OLLAMA_BASE_URL}/api/generate"
DEFAULT_MODEL = "qwen2.5-coder:1.5b"
MAX_PROJECT_FILES = 100
MAX_FILE_BYTES = 1_000_000
CHUNK_SIZE = 2_000


def _available_models():
    names = list(
        LocalModelConfig.objects.filter(is_active=True)
        .order_by("-is_default", "name")
        .values_list("name", flat=True)
    )

    if DEFAULT_MODEL not in names:
        names.insert(0, DEFAULT_MODEL)

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


def _save_knowledge_document(filename, file_text, source_type):
    content_hash = hashlib.sha256(file_text.encode("utf-8")).hexdigest()
    document, _ = KnowledgeDocument.objects.update_or_create(
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


def _search_knowledge(query, limit=8):
    terms = list(dict.fromkeys(re.findall(r"[a-zA-Z0-9_]{2,}", query.lower())))
    if not terms:
        return []

    matches = []
    chunks = KnowledgeChunk.objects.filter(
        document__is_active=True,
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


def index(request):
    sessions = ChatSession.objects.order_by("-updated_at")[:30]
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


def knowledge_search(request):
    query = request.GET.get("q", "").strip()
    return JsonResponse({
        "success": True,
        "query": query,
        "results": _search_knowledge(query),
    })


def session_messages(request, session_id):
    session = get_object_or_404(ChatSession, id=session_id)
    messages = [
        {
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


def _session_markdown(session):
    lines = [
        f"# {session.title}",
        "",
        f"- Model: `{session.model_name}`",
        f"- Created: {session.created_at:%Y-%m-%d %H:%M}",
        "",
    ]
    for message in session.messages.order_by("created_at"):
        label = "You" if message.role == "user" else "Offline CodeGPT"
        lines.extend([f"## {label}", "", message.content, ""])
    return "\\n".join(lines)


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
    content = "\\n".join(content_lines).encode("latin-1", errors="replace")

    objects = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Resources << /Font << /F1 4 0 R >> >> /Contents 5 0 R >>",
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
        b"<< /Length " + str(len(content)).encode() + b" >>\\nstream\\n" + content + b"\\nendstream",
    ]
    pdf = b"%PDF-1.4\\n%\\xe2\\xe3\\xcf\\xd3\\n"
    offsets = [0]
    for index, obj in enumerate(objects, start=1):
        offsets.append(len(pdf))
        pdf += f"{index} 0 obj\\n".encode() + obj + b"\\nendobj\\n"
    xref_offset = len(pdf)
    pdf += f"xref\\n0 {len(objects) + 1}\\n".encode()
    pdf += b"0000000000 65535 f \\n"
    pdf += b"".join(f"{offset:010d} 00000 n \\n".encode() for offset in offsets[1:])
    pdf += f"trailer\\n<< /Size {len(objects) + 1} /Root 1 0 R >>\\nstartxref\\n{xref_offset}\\n%%EOF".encode()
    return pdf


def export_session(request, session_id):
    session = get_object_or_404(ChatSession, id=session_id)
    export_format = request.GET.get("format", "markdown").lower()
    filename = f"offline-codegpt-{session.id}"

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
                "stdout": "\\n".join(output) or "SQL completed without rows.",
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


@require_POST
def ask_code(request):
    prompt = request.POST.get("prompt", "").strip()
    language = request.POST.get("language", "auto").strip()
    code = request.POST.get("code", "").strip()
    session_id = request.POST.get("session_id", "").strip()
    requested_model = request.POST.get("model", "").strip()

    uploaded_files = request.FILES.getlist("files")
    single_file = request.FILES.get("file")
    if single_file and not uploaded_files:
        uploaded_files = [single_file]

    if len(uploaded_files) > MAX_PROJECT_FILES:
        return JsonResponse({
            "success": False,
            "error": f"Please upload no more than {MAX_PROJECT_FILES} files at once.",
        }, status=400)

    uploaded_code_parts = []
    uploaded_filenames = []

    for uploaded_file in uploaded_files:
        filename = _safe_filename(uploaded_file.name)
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
            if "\\x00" in file_text:
                continue

            source_type = "project" if "/" in filename else "upload"
            _save_knowledge_document(filename, file_text, source_type)
            uploaded_code_parts.append(
                f"\n\n===== FILE: {filename} =====\n{file_text}"
            )
        except Exception as ex:
            uploaded_code_parts.append(
                f"\n\n===== FILE: {filename} =====\n"
                f"Unable to read file: {str(ex)}"
            )

    uploaded_code = "\n".join(uploaded_code_parts)
    final_code = uploaded_code.strip() if uploaded_code.strip() else code

    if not prompt and not final_code:
        return JsonResponse({
            "success": False,
            "error": "Please enter prompt or upload/paste code.",
        }, status=400)

    if session_id:
        session = get_object_or_404(ChatSession, id=session_id)
        model_name = requested_model or session.model_name or DEFAULT_MODEL
        if session.model_name != model_name:
            session.model_name = model_name
            session.save(update_fields=["model_name", "updated_at"])
    else:
        title = prompt[:60] if prompt else uploaded_filenames[0][:60]
        model_name = requested_model or DEFAULT_MODEL
        session = ChatSession.objects.create(title=title, model_name=model_name)

    user_message_parts = []
    if prompt:
        user_message_parts.append(f"Prompt:\n{prompt}")
    if uploaded_filenames:
        user_message_parts.append("Uploaded Files:\n" + "\n".join(uploaded_filenames))
    if final_code:
        user_message_parts.append(f"Code:\n{final_code[:6000]}")

    ChatMessage.objects.create(
        session=session,
        role="user",
        content="\n\n".join(user_message_parts),
        filename=", ".join(uploaded_filenames),
        model_name=model_name,
    )

    max_code_chars = 24_000
    truncated_note = ""
    if len(final_code) > max_code_chars:
        final_code = final_code[:max_code_chars]
        truncated_note = "\n\nNote: the uploaded code was truncated for the local model."

    relevant_chunks = _search_knowledge(prompt or code)
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
            json={"model": model_name, "prompt": full_prompt, "stream": True},
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
