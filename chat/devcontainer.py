import json


def generate_devcontainer(files, project_name="Syntax Local AI"):
    names = {str(item.get("filename") or "").lower() for item in (files or [])}
    has_node = "package.json" in names or any(name.endswith((".js", ".ts", ".tsx")) for name in names)
    has_python = (
        "requirements.txt" in names
        or "pyproject.toml" in names
        or any(name.endswith(".py") for name in names)
    )
    if has_node:
        image = "mcr.microsoft.com/devcontainers/javascript-node:1-22-bookworm"
        command = "npm install"
        features = {
            "ghcr.io/devcontainers/features/docker-in-docker:2": {},
        }
    elif has_python:
        image = "mcr.microsoft.com/devcontainers/python:1-3.12-bookworm"
        command = "pip install -r requirements.txt" if "requirements.txt" in names else "python -m pip install --upgrade pip"
        features = {
            "ghcr.io/devcontainers/features/docker-in-docker:2": {},
        }
    else:
        image = "mcr.microsoft.com/devcontainers/base:ubuntu"
        command = ""
        features = {}
    config = {
        "name": project_name or "Local project",
        "image": image,
        "features": features,
        "forwardPorts": [8000, 3000],
        "postCreateCommand": command,
        "customizations": {
            "vscode": {
                "extensions": [
                    "eamodio.gitlens",
                    "ms-azuretools.vscode-docker",
                ],
            },
        },
        "remoteEnv": {
            "PYTHONDONTWRITEBYTECODE": "1",
        },
    }
    return json.dumps(config, indent=2)
