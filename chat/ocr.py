"""Local OCR helpers for scanned PDFs and image batches."""

import base64
import os

import requests

try:
    import fitz
except ImportError:
    fitz = None


def _render_pdf_pages(raw_content, max_pages=5):
    if fitz is None:
        raise ValueError("Scanned PDF OCR requires the PyMuPDF package.")
    document = fitz.open(stream=raw_content, filetype="pdf")
    images = []
    for page_index in range(min(max_pages, document.page_count)):
        page = document.load_page(page_index)
        pixmap = page.get_pixmap(matrix=fitz.Matrix(1.5, 1.5), alpha=False)
        images.append((page_index + 1, base64.b64encode(pixmap.tobytes("png")).decode("ascii")))
    return images


def transcribe_images(images, base_url=None, runtime="ollama", model=None):
    if not images:
        return ""
    base_url = (base_url or os.environ.get("LOCAL_AI_OCR_URL", "http://127.0.0.1:11434")).rstrip("/")
    model = model or os.environ.get("OLLAMA_VISION_MODEL", "llava:latest")
    prompt = "Transcribe all visible text exactly. Preserve headings, line breaks, tables, and code. Return only the transcription."
    if runtime == "ollama":
        response = requests.post(
            f"{base_url}/api/generate",
            json={"model": model, "prompt": prompt, "images": [image for _, image in images], "stream": False},
            timeout=(10, 300),
        )
        response.raise_for_status()
        return str(response.json().get("response", "")).strip()
    content = [{"type": "text", "text": prompt}]
    for _, image in images:
        content.append({"type": "image_url", "image_url": {"url": f"data:image/png;base64,{image}"}})
    response = requests.post(
        f"{base_url}/v1/chat/completions",
        json={"model": model, "messages": [{"role": "user", "content": content}], "stream": False},
        timeout=(10, 300),
    )
    response.raise_for_status()
    payload = response.json()
    return str((payload.get("choices") or [{}])[0].get("message", {}).get("content", "")).strip()


def ocr_scanned_pdf(raw_content, base_url=None, runtime="ollama", model=None, max_pages=None):
    images = _render_pdf_pages(raw_content, max_pages=max_pages or int(os.environ.get("LOCAL_OCR_MAX_PAGES", "5")))
    text = transcribe_images(images, base_url=base_url, runtime=runtime, model=model)
    if not text:
        return ""
    return "\n\n".join(f"[Page {page_number}]\n{text}" for page_number, _ in images)
