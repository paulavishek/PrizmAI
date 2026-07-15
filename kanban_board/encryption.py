"""
encryption.py — Shared symmetric-secret encryption for PrizmAI.

Single source of truth for encrypting secrets at rest (third-party API tokens,
BYOK AI keys, etc.) using Fernet, keyed off ``settings.AI_KEY_ENCRYPTION_KEY``.

This module was extracted from ``AIRouter`` so any feature that stores a secret
(e.g. a Jira/Trello/Asana API token) can reuse the exact same, security-reviewed
encryption instead of hand-rolling its own or storing plaintext.

Rules for callers:
  - Call ``encrypt_secret()`` immediately before persisting a raw secret. Never
    store the raw value in a database column or write it to a log.
  - Call ``decrypt_secret()`` only in memory, immediately before using the secret
    to talk to the external service. Never log or persist the decrypted result.

To generate a valid key:
    from cryptography.fernet import Fernet
    print(Fernet.generate_key().decode())
Add it to your .env as ``AI_KEY_ENCRYPTION_KEY``.
"""

from django.conf import settings
from django.core.exceptions import ImproperlyConfigured


def get_fernet():
    """
    Return a ``Fernet`` instance built from ``settings.AI_KEY_ENCRYPTION_KEY``.

    Raises:
        ImproperlyConfigured: If the key is missing or empty.
    """
    from cryptography.fernet import Fernet

    key = getattr(settings, 'AI_KEY_ENCRYPTION_KEY', None)
    if not key:
        raise ImproperlyConfigured(
            "AI_KEY_ENCRYPTION_KEY is not set in Django settings. "
            "Generate a Fernet key with: "
            "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode()) "
            "and add it to your .env file as AI_KEY_ENCRYPTION_KEY."
        )
    if isinstance(key, str):
        key = key.encode()
    return Fernet(key)


def encrypt_secret(raw_value: str) -> str:
    """
    Encrypt a plain-text secret using Fernet. Call before saving to the database.

    Args:
        raw_value: The plain-text secret (API key/token) entered by the user.

    Returns:
        Fernet-encrypted string, safe to store in a database column.

    Raises:
        ImproperlyConfigured: If AI_KEY_ENCRYPTION_KEY is not configured.
    """
    f = get_fernet()
    return f.encrypt(raw_value.encode()).decode()


def decrypt_secret(encrypted_value: str) -> str:
    """
    Decrypt a Fernet-encrypted secret back to plain text. Call only in memory,
    immediately before using it — never log or persist the result.

    Args:
        encrypted_value: The encrypted string from the database.

    Returns:
        The plain-text secret.

    Raises:
        ImproperlyConfigured: If AI_KEY_ENCRYPTION_KEY is not configured.
        cryptography.fernet.InvalidToken: If the ciphertext is corrupt or the
            encryption key has changed since it was stored.
    """
    f = get_fernet()
    return f.decrypt(encrypted_value.encode()).decode()
