"""
test_encryption.py — Tests for the shared secret-encryption module
(``kanban_board.encryption``).

This module is the single source of truth for encrypting secrets at rest
(third-party API tokens, BYOK AI keys). AIRouter's _encrypt_key/_decrypt_key
delegate to it, so these tests cover the primitive directly.

Run with:
    pytest tests/test_encryption.py
"""

from cryptography.fernet import Fernet, InvalidToken
from django.core.exceptions import ImproperlyConfigured
from django.test import SimpleTestCase, override_settings

from kanban_board.encryption import encrypt_secret, decrypt_secret, get_fernet


_TEST_FERNET_KEY = Fernet.generate_key().decode()


@override_settings(AI_KEY_ENCRYPTION_KEY=_TEST_FERNET_KEY)
class TestSharedEncryption(SimpleTestCase):

    def test_round_trip_returns_original(self):
        raw = "atlassian-api-token-abc123"
        self.assertEqual(decrypt_secret(encrypt_secret(raw)), raw)

    def test_ciphertext_hides_plaintext(self):
        raw = "atlassian-api-token-abc123"
        encrypted = encrypt_secret(raw)
        self.assertNotEqual(encrypted, raw)
        self.assertNotIn(raw, encrypted)

    def test_encryption_is_non_deterministic(self):
        raw = "atlassian-api-token-abc123"
        first = encrypt_secret(raw)
        second = encrypt_secret(raw)
        self.assertNotEqual(first, second)
        self.assertEqual(decrypt_secret(first), raw)
        self.assertEqual(decrypt_secret(second), raw)

    def test_tampered_ciphertext_raises(self):
        encrypted = encrypt_secret("secret")
        tampered = encrypted[:-4] + "AAAA"
        with self.assertRaises(InvalidToken):
            decrypt_secret(tampered)

    def test_get_fernet_returns_usable_instance(self):
        f = get_fernet()
        self.assertEqual(f.decrypt(f.encrypt(b"x")), b"x")

    def test_unicode_secret_round_trips(self):
        raw = "tökén-ünïcodé-🔑"
        self.assertEqual(decrypt_secret(encrypt_secret(raw)), raw)


class TestEncryptionRequiresKey(SimpleTestCase):

    @override_settings(AI_KEY_ENCRYPTION_KEY="")
    def test_missing_key_raises_improperly_configured(self):
        with self.assertRaises(ImproperlyConfigured):
            encrypt_secret("secret")
