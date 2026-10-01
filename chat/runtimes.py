"""Common local runtime adapter for Ollama and OpenAI-compatible servers."""

import base64

import requests


RUNTIME_CHOICES = {
    "ollama": "Ollama",
    "lmstudio": "LM Studio",
    "llamacpp": "llama.cpp",
}


class LocalRuntimeAdapter:
    def __init__(self, runtime="ollama", base_url="http://127.0.0.1:11434"):
        self.runtime = runtime if runtime in RUNTIME_CHOICES else "ollama"
        self.base_url = str(base_url or "http://127.0.0.1:11434").rstrip("/")

    @property
    def label(self):
        return RUNTIME_CHOICES[self.runtime]

    def models(self):
        if self.runtime == "ollama":
            response = requests.get(f"{self.base_url}/api/tags", timeout=3)
            if not response.ok:
                return []
            return response.json().get("models", [])
        response = requests.get(f"{self.base_url}/v1/models", timeout=3)
        if not response.ok:
            return []
        return [{"name": item.get("id", "")} for item in response.json().get("data", []) if item.get("id")]

    def embeddings(self, texts, model):
        if self.runtime == "ollama":
            response = requests.post(
                f"{self.base_url}/api/embed",
                json={"model": model, "input": texts},
                timeout=(5, 60),
            )
            if getattr(response, "status_code", 200) >= 400:
                return []
            payload = response.json()
            embeddings = payload.get("embeddings") or []
            return embeddings if embeddings else ([payload["embedding"]] if payload.get("embedding") else [])
        response = requests.post(
            f"{self.base_url}/v1/embeddings",
            json={"model": model, "input": texts},
            timeout=(5, 60),
        )
        if getattr(response, "status_code", 200) >= 400:
            return []
        return [item.get("embedding", []) for item in response.json().get("data", [])]

    def generate(self, model, prompt, images=None, options=None):
        options = options or {}
        if self.runtime == "ollama":
            payload = {
                "model": model,
                "prompt": prompt,
                "stream": True,
                "options": options,
            }
            if images:
                payload["images"] = images
            return requests.post(
                f"{self.base_url}/api/generate",
                json=payload,
                timeout=(10, 300),
                stream=True,
            ), "ollama"

        content = [{"type": "text", "text": prompt}]
        for image in images or []:
            content.append({"type": "image_url", "image_url": {"url": f"data:image/png;base64,{image}"}})
        payload = {
            "model": model,
            "messages": [{"role": "user", "content": content}],
            "stream": True,
            "temperature": options.get("temperature", 0.2),
            "top_p": options.get("top_p", 0.9),
            "max_tokens": max(256, int(options.get("num_ctx", 8192) // 4)),
        }
        return requests.post(
            f"{self.base_url}/v1/chat/completions",
            json=payload,
            timeout=(10, 300),
            stream=True,
        ), "openai"

    def warmup(self, model):
        response, protocol = self.generate(model, "Reply with READY.", options={"temperature": 0, "top_p": 1, "num_ctx": 1024})
        if response.status_code != 200:
            return False, protocol, response.text[:500]
        for _ in response.iter_lines(decode_unicode=True):
            pass
        return True, protocol, "Model warmed up."


def get_runtime_adapter(runtime, base_url):
    return LocalRuntimeAdapter(runtime, base_url)
