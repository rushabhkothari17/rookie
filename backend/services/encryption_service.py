"""
Field-level encryption for sensitive integration secrets stored in MongoDB.

Uses Fernet (AES-128-CBC + HMAC-SHA256) from the `cryptography` library.
The key is sourced from the ENCRYPTION_KEY environment variable — it must be
a valid URL-safe base64-encoded 32-byte key (generate with Fernet.generate_key()).

Encrypted values are prefixed with "enc:" so the app can safely handle both
legacy plaintext values and newly encrypted ones during migration windows.
"""
from __future__ import annotations

import os
from typing import Any, Dict, Optional

from cryptography.fernet import Fernet, InvalidToken

# Set of app_settings keys that must be encrypted at rest
SENSITIVE_KEYS: frozenset[str] = frozenset({
    "resend_api_key",
    "stripe_secret_key",
    "stripe_publishable_key",
    "gocardless_access_token",
    "gocardless_webhook_secret",
    "stripe_webhook_secret",
    "zoho_client_secret",
})

# Fields within oauth_connections.credentials that are sensitive
SENSITIVE_CREDENTIAL_FIELDS: frozenset[str] = frozenset({
    "api_key",
    "access_token",
    "client_secret",
    "refresh_token",
    "private_key",
    "secret_key",
    "password",
})

_PREFIX = "enc:"
_fernet: Optional[Fernet] = None


def _get_fernet() -> Fernet:
    global _fernet
    if _fernet is None:
        key = os.environ.get("ENCRYPTION_KEY", "")
        if not key:
            raise RuntimeError(
                "ENCRYPTION_KEY is not set. "
                "Generate one with: python3 -c \"from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())\""
            )
        _fernet = Fernet(key.encode())
    return _fernet


def encrypt_secret(value: str) -> str:
    """Encrypt a plaintext secret. Returns a string prefixed with 'enc:'."""
    if not value:
        return value
    if value.startswith(_PREFIX):
        return value  # already encrypted
    token = _get_fernet().encrypt(value.encode()).decode()
    return f"{_PREFIX}{token}"


def decrypt_secret(value: str) -> str:
    """Decrypt an encrypted secret. Handles both enc: prefixed and legacy plaintext values."""
    if not value:
        return value
    if not value.startswith(_PREFIX):
        return value  # legacy plaintext — return as-is (migration path)
    try:
        return _get_fernet().decrypt(value[len(_PREFIX):].encode()).decode()
    except (InvalidToken, Exception):
        # If decryption fails, return empty string rather than leaking anything
        return ""


def is_sensitive_key(key: str) -> bool:
    return key in SENSITIVE_KEYS


def encrypt_credentials(creds: Dict[str, Any]) -> Dict[str, Any]:
    """Encrypt all sensitive fields in an oauth_connections credentials dict."""
    return {
        k: encrypt_secret(v) if k in SENSITIVE_CREDENTIAL_FIELDS and isinstance(v, str) else v
        for k, v in creds.items()
    }


def decrypt_credentials(creds: Dict[str, Any]) -> Dict[str, Any]:
    """Decrypt all sensitive fields from an oauth_connections credentials dict."""
    return {
        k: decrypt_secret(v) if k in SENSITIVE_CREDENTIAL_FIELDS and isinstance(v, str) else v
        for k, v in creds.items()
    }
