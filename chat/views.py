import hashlib
import json
from pathlib import PurePosixPath

import requests

from django.http import JsonResponse, StreamingHttpResponse
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
    return json.dumps(payload, ensure_ascii=False) + "\\n"


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
                    f"\\n\\n===== FILE: {filename} =====\\n"
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
                f"\\n\\n===== FILE: {filename} =====\\n{file_text}"
            )
        except Exception as ex:
            uploaded_code_parts.append(
                f"\\n\\n===== FILE: {filename} =====\\n"
                f"Unable to read file: {str(ex)}"
            )

    uploaded_code = "\\n".join(uploaded_code_parts)
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
        user_message_parts.append(f"Prompt:\\n{prompt}")
    if uploaded_filenames:
        user_message_parts.append("Uploaded Files:\\n" + "\\n".join(uploaded_filenames))
    if final_code:
        user_message_parts.append(f"Code:\\n{final_code[:6000]}")

    ChatMessage.objects.create(
        session=session,
        role="user",
        content="\\n\\n".join(user_message_parts),
        filename=", ".join(uploaded_filenames),
        model_name=model_name,
    )

    max_code_chars = 24_000
    truncated_note = ""
    if len(final_code) > max_code_chars:
        final_code = final_code[:max_code_chars]
        truncated_note = "\\n\\nNote: the uploaded code was truncated for the local model."

    full_prompt = f"""
You are a fully offline coding assistant running locally.

Language:
{language}

User task:
{prompt}

Uploaded files:
{", ".join(uploaded_filenames)}

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
