import base64
import hashlib
import json
import re

from cryptography.fernet import Fernet
from django.conf import settings

from .models import WorkspaceMembership


def _fernet():
    key = hashlib.sha256((settings.SECRET_KEY + ":syntax-local-vault").encode("utf-8")).digest()
    return Fernet(base64.urlsafe_b64encode(key))


def encrypt_secret(value):
    return _fernet().encrypt(value.encode("utf-8")).decode("ascii")


def decrypt_secret(ciphertext):
    return _fernet().decrypt(ciphertext.encode("ascii")).decode("utf-8")


def encrypt_blob(value):
    return b"SYNTAX-LOCAL-ENCRYPTED-1\n" + _fernet().encrypt(value)


def decrypt_blob(value):
    prefix = b"SYNTAX-LOCAL-ENCRYPTED-1\n"
    if not value.startswith(prefix):
        return value
    return _fernet().decrypt(value[len(prefix):])


def workspace_for_user(user):
    membership = WorkspaceMembership.objects.filter(user=user).select_related("workspace").order_by("workspace_id").first()
    return membership.workspace if membership else None


def mask_sensitive_text(user, text):
    workspace = workspace_for_user(user)
    if not workspace:
        return text
    from .models import SecretVaultItem
    masked = str(text)
    for item in SecretVaultItem.objects.filter(workspace=workspace):
        try:
            value = decrypt_secret(item.ciphertext)
        except Exception:
            continue
        if value:
            masked = masked.replace(value, "[REDACTED:" + item.name + "]")
    return masked


def mask_json(user, value):
    if isinstance(value, dict):
        return {key: mask_json(user, item) for key, item in value.items()}
    if isinstance(value, list):
        return [mask_json(user, item) for item in value]
    if isinstance(value, str):
        return mask_sensitive_text(user, value)
    return value


def redact_sensitive_text(user, text):
    """Mask vault values and common secret formats before model-facing use."""
    from .models import PrivacyPreference
    preference = PrivacyPreference.objects.filter(user=user).first() if user and getattr(user, "is_authenticated", False) else None
    if preference and not preference.redact_secrets:
        return str(text)
    masked = mask_sensitive_text(user, str(text)) if user else str(text)
    patterns = [
        (r"(?i)(authorization\s*:\s*bearer\s+)[A-Za-z0-9._~+/=-]+", r"\1[REDACTED_TOKEN]"),
        (r"(?i)\b(sk-[A-Za-z0-9_-]{16,}|gh[pousr]_[A-Za-z0-9_]{16,})\b", "[REDACTED_API_KEY]"),
        (r"\beyJ[A-Za-z0-9_-]{20,}\.[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+\b", "[REDACTED_JWT]"),
        (r"-----BEGIN [A-Z ]+ PRIVATE KEY-----[\s\S]*?-----END [A-Z ]+ PRIVATE KEY-----", "[REDACTED_PRIVATE_KEY]"),
        (r"(?i)(\b(?:password|passwd|secret|token|api[_-]?key)\s*[:=]\s*)([^\s,;]+)", r"\1[REDACTED_SECRET]"),
    ]
    for pattern, replacement in patterns:
        masked = re.sub(pattern, replacement, masked)
    return masked
