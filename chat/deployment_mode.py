"""Deployment-mode policy shared by the UI and API views."""

from django.conf import settings


MODE_LABELS = {
    "offline": "Offline Local",
    "hosted": "Hosted",
    "hybrid": "Hybrid Local Connector",
}


def current_mode():
    return getattr(settings, "DEPLOYMENT_MODE", "offline")


def mode_capabilities():
    mode = current_mode()
    if mode == "offline":
        return {
            "local_runtime": True,
            "local_files": True,
            "local_git": True,
            "local_tools": True,
            "network_required": False,
            "connector_required": False,
        }
    if mode == "hybrid":
        return {
            "local_runtime": True,
            "local_files": True,
            "local_git": True,
            "local_tools": True,
            "network_required": True,
            "connector_required": True,
        }
    return {
        "local_runtime": False,
        "local_files": False,
        "local_git": False,
        "local_tools": False,
        "network_required": True,
        "connector_required": False,
    }


def mode_payload():
    mode = current_mode()
    database_engine = settings.DATABASES["default"].get("ENGINE", "")
    return {
        "key": mode,
        "label": MODE_LABELS.get(mode, mode.title()),
        "description": {
            "offline": "SQLite, local Ollama, local files, and Git; no network required.",
            "hosted": "Render and Neon; cloud authentication with local tools disabled.",
            "hybrid": "Hosted UI and database with an approved local connector.",
        }.get(mode, "Configured deployment mode."),
        "capabilities": mode_capabilities(),
        "database": "sqlite" if "sqlite" in database_engine else "postgresql",
    }
