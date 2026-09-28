# Syntax Local AI

Syntax Local AI is a private Django web app that lets you upload or paste code and ask a local Ollama model for explanations, debugging help, optimization suggestions, and refactoring ideas.

## Features

- Local coding assistance through Ollama
- Chat history stored in SQLite
- Upload one or more source files
- Paste code directly into the composer
- Language selection with auto-detect support
- No cloud AI API required
- Streamed responses from local Ollama models
- Multiple model selection and project-folder upload
- Local project search with retrieval-augmented context
- Offline syntax highlighting, copy, and Markdown download controls
- Markdown, JSON, and PDF chat export
- User accounts with per-user chat and knowledge ownership
- Safe Python/JavaScript syntax checks and in-memory SQL execution
- Offline linting, security checks, bug heuristics, and test templates

## Requirements

- Python 3.10+
- Django 5.2+
- Ollama with the `qwen2.5-coder:1.5b` model

## Setup

```powershell
python -m venv venv
.\venv\Scripts\Activate.ps1
pip install -r requirements.txt
Copy-Item .env.example .env
python manage.py migrate
ollama pull qwen2.5-coder:1.5b
ollama pull llava:latest
python manage.py runserver
```

Open <http://127.0.0.1:8000/> in your browser.

The app expects Ollama at `http://127.0.0.1:11434`. Start Ollama before sending a request.

Create an account from the sign-up page before using the chat. Python and JavaScript are syntax-checked without execution; SQL runs only against an in-memory SQLite database. This keeps the local web app from executing arbitrary submitted programs on the host.

## Project layout

```text
chat/                  Django chat app and local-model integration
offline_codegpt/       Django project configuration
static/chat/           Frontend JavaScript and CSS
templates/chat/        Chat page template
```
