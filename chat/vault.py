import base64
import hashlib
import json

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
