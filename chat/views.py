import json

import requests

from django.http import JsonResponse, StreamingHttpResponse
from django.shortcuts import render, get_object_or_404
from django.views.decorators.http import require_POST

from .models import ChatSession, ChatMessage, LocalModelConfig


OLLAMA_BASE_URL = "http://127.0.0.1:11434"
OLLAMA_URL = f"{OLLAMA_BASE_URL}/api/generate"
DEFAULT_MODEL = "qwen2.5-coder:1.5b"


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
    """Serialize one newline-delimited JSON event for the chat client."""
    return json.dumps(payload, ensure_ascii=False) + "\n"


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
            "created_at": msg.created_at.strftime("%d-%m-%Y %H:%M")
        }
        for msg in session.messages.order_by("created_at")
    ]

    return JsonResponse({
        "success": True,
        "session_id": session.id,
        "title": session.title,
        "messages": messages
    })


@require_POST
def ask_code(request):
    prompt = request.POST.get("prompt", "").strip()
    language = request.POST.get("language", "auto").strip()
    code = request.POST.get("code", "").strip()
    session_id = request.POST.get("session_id", "").strip()
    requested_model = request.POST.get("model", "").strip()

    uploaded_files = request.FILES.getlist("files")

    # Support old frontend also if it sends single file as "file"
    single_file = request.FILES.get("file")
    if single_file and not uploaded_files:
        uploaded_files = [single_file]

    uploaded_code_parts = []
    uploaded_filenames = []

    for uploaded_file in uploaded_files:
        uploaded_filenames.append(uploaded_file.name)

        try:
            raw_content = uploaded_file.read()
            file_text = raw_content.decode("utf-8", errors="ignore")

            uploaded_code_parts.append(
                f"\n\n===== FILE: {uploaded_file.name} =====\n"
                f"{file_text}"
            )

        except Exception as ex:
            uploaded_code_parts.append(
                f"\n\n===== FILE: {uploaded_file.name} =====\n"
                f"Unable to read file: {str(ex)}"
            )

    uploaded_code = "\n".join(uploaded_code_parts)

    if uploaded_code.strip():
        final_code = uploaded_code.strip()
    else:
        final_code = code

    if not prompt and not final_code:
        return JsonResponse({
            "success": False,
            "error": "Please enter prompt or upload/paste code."
        }, status=400)

    # Create new session or use existing session
    if session_id:
        session = get_object_or_404(ChatSession, id=session_id)
        model_name = requested_model or session.model_name or DEFAULT_MODEL
        if session.model_name != model_name:
            session.model_name = model_name
            session.save(update_fields=["model_name", "updated_at"])
    else:
        if prompt:
            title = prompt[:60]
        elif uploaded_filenames:
            title = uploaded_filenames[0][:60]
        else:
            title = "New Chat"

        model_name = requested_model or DEFAULT_MODEL
        session = ChatSession.objects.create(title=title, model_name=model_name)

    user_message_parts = []

    if prompt:
        user_message_parts.append(f"Prompt:\n{prompt}")

    if uploaded_filenames:
        user_message_parts.append(
            "Uploaded Files:\n" + "\n".join(uploaded_filenames)
        )

    if final_code:
        user_message_parts.append(f"Code:\n{final_code[:6000]}")

    user_message = "\n\n".join(user_message_parts)

    ChatMessage.objects.create(
        session=session,
        role="user",
        content=user_message,
        filename=", ".join(uploaded_filenames)
    )

    # Limit code size for small local model
    max_code_chars = 24000
    truncated_note = ""

    if len(final_code) > max_code_chars:
        final_code = final_code[:max_code_chars]
        truncated_note = (
            "\n\nNote: Uploaded files/code were very large, "
            "so only the first part was sent to the local model."
        )

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
            json={
                "model": model_name,
                "prompt": full_prompt,
                "stream": True
            },
            timeout=(10, 300),
            stream=True,
        )

        if response.status_code != 200:
            return JsonResponse({
                "success": False,
                "error": response.text
            }, status=500)

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
                yield _event({
                    "type": "error",
                    "error": f"Unable to read the model stream: {str(ex)}",
                })

        streaming_response = StreamingHttpResponse(
            stream_answer(),
            content_type="application/x-ndjson",
        )
        streaming_response["Cache-Control"] = "no-cache"
        return streaming_response

    except requests.exceptions.ConnectionError:
        return JsonResponse({
            "success": False,
            "error": "Ollama is not running. Start Ollama first."
        }, status=500)

    except requests.exceptions.Timeout:
        return JsonResponse({
            "success": False,
            "error": "Model response timeout. Try smaller files or smaller prompt."
        }, status=500)

    except Exception as ex:
        return JsonResponse({
            "success": False,
            "error": f"Unexpected error: {str(ex)}"
        }, status=500)

