"""
CREDENTIAL VAULT — SECURE ENCRYPTED STORAGE FOR INTEGRATION CREDENTIALS

Uses standard authenticated encryption (AES-256-GCM via cryptography).
Ensures credentials (OAuth tokens, API keys) are never stored in plaintext,
never logged, never placed into RAG/Memory, and never exposed in API responses.
"""

import base64
import hashlib
import json
import logging
import os
from typing import Any, Dict, Optional

from cryptography.hazmat.primitives.ciphers.aead import AESGCM

from backend.app.core.config import settings

logger = logging.getLogger(__name__)


def _get_master_key() -> bytes:
    """
    Derive a 256-bit (32-byte) AES key from the configured secret.
    Precedence:
    1. settings.integration_secret_key (if configured)
    2. settings.jwt_secret_key (centralized system secret)
    """
    raw_secret = getattr(settings, "integration_secret_key", None) or settings.jwt_secret_key
    if not raw_secret:
        raise RuntimeError("CredentialVault: No secret key configured for credential encryption.")
    return hashlib.sha256(raw_secret.encode("utf-8")).digest()


def encrypt_credentials(data: Dict[str, Any]) -> str:
    """
    Encrypt a dictionary of credentials into a base64-encoded AES-GCM payload.
    Format: base64( 12-byte-nonce + ciphertext-with-auth-tag )
    """
    key = _get_master_key()
    aesgcm = AESGCM(key)
    nonce = os.urandom(12)  # Standard 96-bit nonce for AES-GCM
    plaintext = json.dumps(data).encode("utf-8")
    ciphertext = aesgcm.encrypt(nonce, plaintext, None)
    payload = nonce + ciphertext
    return base64.urlsafe_b64encode(payload).decode("utf-8")


def decrypt_credentials(encrypted_token: str) -> Dict[str, Any]:
    """
    Decrypt a base64-encoded AES-GCM payload into a dictionary of credentials.
    Raises ValueError on tampering, corruption, or key mismatch.
    """
    if not encrypted_token:
        return {}
    try:
        payload = base64.urlsafe_b64decode(encrypted_token.encode("utf-8"))
        if len(payload) < 28:  # 12 bytes nonce + 16 bytes auth tag minimum
            raise ValueError("Invalid encrypted payload length.")
        nonce = payload[:12]
        ciphertext = payload[12:]
        key = _get_master_key()
        aesgcm = AESGCM(key)
        plaintext = aesgcm.decrypt(nonce, ciphertext, None)
        return json.loads(plaintext.decode("utf-8"))
    except Exception as exc:
        logger.error("CredentialVault: Failed to decrypt credential payload (security check failed).")
        raise ValueError("Failed to decrypt integration credentials.") from exc


def mask_credential_string(val: Optional[str]) -> str:
    """
    Safely mask a credential string for display (e.g. 'sk-****1234' or '****').
    """
    if not val:
        return "********"
    s = str(val).strip()
    if len(s) <= 6:
        return "********"
    return f"{s[:3]}****{s[-4:]}"
