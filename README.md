# Offline CodeGPT

Offline CodeGPT is a Django web app that lets you upload or paste code and ask a local Ollama model for explanations, debugging help, optimization suggestions, and refactoring ideas.

## Features

- Local coding assistance through Ollama
- Chat history stored in SQLite
- Upload one or more source files
- Paste code directly into the composer
- Language selection with auto-detect support
- No cloud AI API required

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
python manage.py runserver
```

Open <http://127.0.0.1:8000/> in your browser.

The app expects Ollama at `http://127.0.0.1:11434`. Start Ollama before sending a request.

## Project layout

```text
chat/                  Django chat app and local-model integration
offline_codegpt/       Django project configuration
static/chat/           Frontend JavaScript and CSS
templates/chat/        Chat page template
```
