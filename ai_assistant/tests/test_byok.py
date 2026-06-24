"""
test_byok.py — Tests for the BYOK (Bring Your Own Key) implementation.

Covers the BYOK-specific paths that test_ai_router.py does not:
  * Fernet encryption round-trip (_encrypt_key / _decrypt_key / _get_fernet)
  * The 5-step provider-resolution chain (_resolve_provider)
  * validate_api_key()
  * complete() response normalisation across providers
  * The OrganizationAISettings / UserAISettings models

All external AI SDK calls are mocked — no API keys or network calls are needed.
The encryption tests rely on AI_KEY_ENCRYPTION_KEY being set in test_settings.py.

Run with:
    python manage.py test ai_assistant.tests.test_byok --settings=kanban_board.test_settings
"""

from unittest.mock import patch

from cryptography.fernet import Fernet, InvalidToken
from django.contrib.auth.models import User
from django.core.exceptions import ImproperlyConfigured
from django.test import SimpleTestCase, TestCase, override_settings

from accounts.models import Organization, UserProfile
from ai_assistant.models import OrganizationAISettings, UserAISettings
from ai_assistant.utils.ai_router import AIRouter, AIProviderError
from kanban.models import Workspace


# A valid, throwaway Fernet key used by the encryption tests that override the
# setting explicitly (so they don't depend on test_settings global value).
_TEST_FERNET_KEY = Fernet.generate_key().decode()


# ===========================================================================
# Encryption round-trip
# ===========================================================================

@override_settings(AI_KEY_ENCRYPTION_KEY=_TEST_FERNET_KEY)
class TestEncryption(SimpleTestCase):
    """_encrypt_key / _decrypt_key / _get_fernet."""

    def setUp(self):
        self.router = AIRouter()

    def test_round_trip_returns_original(self):
        raw = "sk-super-secret-key-1234"
        encrypted = self.router._encrypt_key(raw)
        self.assertEqual(self.router._decrypt_key(encrypted), raw)

    def test_ciphertext_differs_from_plaintext(self):
        raw = "sk-super-secret-key-1234"
        encrypted = self.router._encrypt_key(raw)
        self.assertNotEqual(encrypted, raw)
        self.assertNotIn(raw, encrypted)

    def test_encryption_is_non_deterministic(self):
        # Fernet embeds a timestamp + random IV, so two encryptions differ
        # but both decrypt back to the same plaintext.
        raw = "sk-super-secret-key-1234"
        a = self.router._encrypt_key(raw)
        b = self.router._encrypt_key(raw)
        self.assertNotEqual(a, b)
        self.assertEqual(self.router._decrypt_key(a), self.router._decrypt_key(b))

    def test_decrypt_corrupted_ciphertext_raises(self):
        with self.assertRaises(InvalidToken):
            self.router._decrypt_key("not-a-valid-fernet-token")

    def test_decrypt_with_different_key_raises(self):
        encrypted = self.router._encrypt_key("sk-key")
        other_key = Fernet.generate_key().decode()
        with override_settings(AI_KEY_ENCRYPTION_KEY=other_key):
            with self.assertRaises(InvalidToken):
                self.router._decrypt_key(encrypted)


class TestEncryptionMisconfigured(SimpleTestCase):
    """Encryption helpers when AI_KEY_ENCRYPTION_KEY is missing."""

    @override_settings(AI_KEY_ENCRYPTION_KEY='')
    def test_missing_key_raises_improperly_configured(self):
        router = AIRouter()
        with self.assertRaises(ImproperlyConfigured):
            router._encrypt_key("sk-key")
        with self.assertRaises(ImproperlyConfigured):
            router._decrypt_key("anything")


# ===========================================================================
# Provider resolution (_resolve_provider) — the heart of BYOK
# ===========================================================================

@override_settings(
    AI_KEY_ENCRYPTION_KEY=_TEST_FERNET_KEY,
    GEMINI_API_KEY='platform-gemini',
    OPENAI_API_KEY='platform-openai',
    ANTHROPIC_API_KEY='platform-anthropic',
)
class TestResolveProvider(TestCase):
    """Drive every branch of the 5-step resolution chain."""

    def setUp(self):
        self.router = AIRouter()
        self.creator = User.objects.create_user('creator', password='x')
        self.org = Organization.objects.create(name='Acme', created_by=self.creator)
        self.workspace = Workspace.objects.create(
            name='Acme WS', organization=self.org, created_by=self.creator,
        )

    # -- helpers --------------------------------------------------------

    def _make_user(self, username, *, org=None, is_admin=False):
        user = User.objects.create_user(username, password='x')
        # When the user belongs to the org, point their active workspace at the
        # test workspace so workspace-scoped AI settings resolve.
        UserProfile.objects.create(
            user=user, organization=org, is_admin=is_admin,
            active_workspace=self.workspace if org else None,
        )
        return user

    def _encrypt(self, raw):
        return self.router._encrypt_key(raw)

    # -- Step 5: no settings at all -> Gemini fallback ------------------

    def test_no_settings_falls_back_to_gemini(self):
        user = self._make_user('plain')
        provider, key, is_byok, model = self.router._resolve_provider(user)
        self.assertEqual(provider, 'gemini')
        self.assertEqual(key, 'platform-gemini')
        self.assertFalse(is_byok)
        self.assertIsNone(model)

    def test_user_without_profile_falls_back_to_gemini(self):
        user = User.objects.create_user('noprofile', password='x')
        provider, key, is_byok, model = self.router._resolve_provider(user)
        self.assertEqual(provider, 'gemini')
        self.assertFalse(is_byok)

    # -- Step 1: personal BYOK always wins ------------------------------

    def test_personal_byok_takes_precedence(self):
        user = self._make_user('byok-user', org=self.org)
        UserAISettings.objects.create(
            user=user,
            byok_provider='openai',
            encrypted_api_key=self._encrypt('sk-user-openai'),
            byok_model='gpt-4o',
        )
        # Even with an org BYOK present, the personal key must win.
        OrganizationAISettings.objects.create(
            workspace=self.workspace,
            byok_provider='anthropic',
            encrypted_api_key=self._encrypt('sk-org-anthropic'),
        )
        provider, key, is_byok, model = self.router._resolve_provider(user)
        self.assertEqual(provider, 'openai')
        self.assertEqual(key, 'sk-user-openai')
        self.assertTrue(is_byok)
        self.assertEqual(model, 'gpt-4o')

    def test_personal_byok_corrupted_key_raises_provider_error(self):
        user = self._make_user('byok-bad', org=self.org)
        UserAISettings.objects.create(
            user=user,
            byok_provider='openai',
            encrypted_api_key='garbage-not-fernet',
        )
        with self.assertRaises(AIProviderError) as ctx:
            self.router._resolve_provider(user)
        self.assertEqual(ctx.exception.provider, 'openai')

    # -- Step 2: provider_override, gated by permission -----------------

    def test_override_respected_for_org_admin(self):
        user = self._make_user('admin', org=self.org, is_admin=True)
        UserAISettings.objects.create(user=user, provider_override='anthropic')
        provider, key, is_byok, model = self.router._resolve_provider(user)
        self.assertEqual(provider, 'anthropic')
        self.assertEqual(key, 'platform-anthropic')
        self.assertFalse(is_byok)

    def test_override_respected_when_org_allows(self):
        OrganizationAISettings.objects.create(
            workspace=self.workspace, provider='gemini',
            allow_user_provider_override=True,
        )
        user = self._make_user('member', org=self.org)
        UserAISettings.objects.create(user=user, provider_override='openai')
        provider, key, _, _ = self.router._resolve_provider(user)
        self.assertEqual(provider, 'openai')
        self.assertEqual(key, 'platform-openai')

    def test_override_ignored_when_not_permitted(self):
        # Org default is gemini, overrides NOT allowed, user is not admin.
        OrganizationAISettings.objects.create(
            workspace=self.workspace, provider='gemini',
            allow_user_provider_override=False,
        )
        user = self._make_user('member', org=self.org)
        UserAISettings.objects.create(user=user, provider_override='openai')
        provider, key, _, _ = self.router._resolve_provider(user)
        # Falls through to org provider (Step 4) -> gemini platform key.
        self.assertEqual(provider, 'gemini')
        self.assertEqual(key, 'platform-gemini')

    # -- Step 3: org BYOK -----------------------------------------------

    def test_org_byok_used_when_no_user_settings(self):
        OrganizationAISettings.objects.create(
            workspace=self.workspace,
            provider='gemini',
            byok_provider='anthropic',
            encrypted_api_key=self._encrypt('sk-org-anthropic'),
            byok_model='claude-sonnet-4-6',
        )
        user = self._make_user('member', org=self.org)
        provider, key, is_byok, model = self.router._resolve_provider(user)
        self.assertEqual(provider, 'anthropic')
        self.assertEqual(key, 'sk-org-anthropic')
        self.assertTrue(is_byok)
        self.assertEqual(model, 'claude-sonnet-4-6')

    # -- Step 4: org provider + platform key ----------------------------

    def test_org_provider_platform_key(self):
        OrganizationAISettings.objects.create(
            workspace=self.workspace, provider='openai',
        )
        user = self._make_user('member', org=self.org)
        provider, key, is_byok, _ = self.router._resolve_provider(user)
        self.assertEqual(provider, 'openai')
        self.assertEqual(key, 'platform-openai')
        self.assertFalse(is_byok)

    # -- Background task path (user=None) -------------------------------

    def test_background_task_no_org_settings_falls_back_to_gemini(self):
        provider, key, is_byok, _ = self.router._resolve_provider(None)
        self.assertEqual(provider, 'gemini')
        self.assertEqual(key, 'platform-gemini')
        self.assertFalse(is_byok)

    def test_background_task_never_uses_another_workspaces_byok(self):
        # TENANT ISOLATION: a user-less background task has no workspace context,
        # so it must NEVER pick up some workspace's BYOK key/provider. Even with a
        # workspace BYOK configured, the background path uses the platform key.
        OrganizationAISettings.objects.create(
            workspace=self.workspace,
            provider='gemini',
            byok_provider='openai',
            encrypted_api_key=self._encrypt('sk-org-openai'),
        )
        provider, key, is_byok, _ = self.router._resolve_provider(None)
        self.assertEqual(provider, 'gemini')
        self.assertEqual(key, 'platform-gemini')
        self.assertFalse(is_byok)


# ===========================================================================
# validate_api_key
# ===========================================================================

@override_settings(AI_KEY_ENCRYPTION_KEY=_TEST_FERNET_KEY)
class TestValidateApiKey(SimpleTestCase):

    def setUp(self):
        self.router = AIRouter()

    def test_valid_key_returns_true(self):
        with patch.object(self.router, '_call_openai', return_value={'text': 'Hi'}) as m:
            self.assertTrue(self.router.validate_api_key('openai', 'sk-key'))
            m.assert_called_once()

    def test_failed_call_returns_false(self):
        with patch.object(self.router, '_call_anthropic',
                          side_effect=AIProviderError('anthropic', ValueError('bad key'))):
            self.assertFalse(self.router.validate_api_key('anthropic', 'sk-bad'))

    def test_unknown_provider_returns_false(self):
        self.assertFalse(self.router.validate_api_key('cohere', 'key'))

    def test_custom_model_threaded_through(self):
        with patch.object(self.router, '_call_gemini', return_value={'text': 'Hi'}) as m:
            self.router.validate_api_key('gemini', 'key', model='gemini-2.5-pro')
            _, kwargs = m.call_args
            self.assertEqual(kwargs.get('model_override'), 'gemini-2.5-pro')


# ===========================================================================
# complete() — routing + normalisation
# ===========================================================================

@override_settings(AI_KEY_ENCRYPTION_KEY=_TEST_FERNET_KEY)
class TestCompleteNormalisation(SimpleTestCase):

    def setUp(self):
        self.router = AIRouter()

    def _resolve(self, provider, is_byok=False):
        return patch.object(
            self.router, '_resolve_provider',
            return_value=(provider, 'the-key', is_byok, None),
        )

    def test_normalised_keys_present(self):
        with self._resolve('openai', is_byok=True), \
             patch.object(self.router, '_call_openai',
                          return_value={'text': 'Answer', 'model': 'gpt-4o', 'tokens_used': 42}):
            result = self.router.complete('hi', user=None)
        self.assertEqual(
            set(result.keys()),
            {'text', 'provider', 'model', 'used_byok', 'tokens_used'},
        )
        self.assertEqual(result['text'], 'Answer')
        self.assertEqual(result['provider'], 'openai')
        self.assertEqual(result['model'], 'gpt-4o')
        self.assertTrue(result['used_byok'])
        self.assertEqual(result['tokens_used'], 42)

    def test_provider_error_propagates(self):
        with self._resolve('anthropic'), \
             patch.object(self.router, '_call_anthropic',
                          side_effect=AIProviderError('anthropic', ValueError('boom'))):
            with self.assertRaises(AIProviderError):
                self.router.complete('hi', user=None)

    def test_generic_exception_wrapped_as_provider_error(self):
        with self._resolve('gemini'), \
             patch.object(self.router, '_call_gemini', side_effect=RuntimeError('socket died')):
            with self.assertRaises(AIProviderError) as ctx:
                self.router.complete('hi', user=None)
            self.assertEqual(ctx.exception.provider, 'gemini')

    def test_empty_text_raises_provider_error(self):
        with self._resolve('gemini'), \
             patch.object(self.router, '_call_gemini',
                          return_value={'text': '', 'model': 'g', 'tokens_used': 0}):
            with self.assertRaises(AIProviderError):
                self.router.complete('hi', user=None)


# ===========================================================================
# Models — encrypted storage, masking, no plaintext leakage
# ===========================================================================

@override_settings(AI_KEY_ENCRYPTION_KEY=_TEST_FERNET_KEY)
class TestSettingsModels(TestCase):

    def setUp(self):
        self.router = AIRouter()
        self.creator = User.objects.create_user('creator', password='x')
        self.org = Organization.objects.create(name='Acme', created_by=self.creator)
        self.workspace = Workspace.objects.create(
            name='Acme WS', organization=self.org, created_by=self.creator,
        )

    def test_user_settings_never_stores_plaintext(self):
        raw = 'sk-plaintext-should-never-appear'
        user = User.objects.create_user('u', password='x')
        settings_obj = UserAISettings.objects.create(
            user=user,
            byok_provider='openai',
            encrypted_api_key=self.router._encrypt_key(raw),
            key_last_four='••••' + raw[-4:],
        )
        settings_obj.refresh_from_db()
        self.assertNotIn(raw, settings_obj.encrypted_api_key)
        self.assertEqual(self.router._decrypt_key(settings_obj.encrypted_api_key), raw)
        self.assertEqual(settings_obj.key_last_four, '••••pear')

    def test_org_settings_defaults(self):
        s = OrganizationAISettings.objects.create(workspace=self.workspace)
        self.assertEqual(s.provider, 'gemini')
        self.assertFalse(s.allow_user_provider_override)
        self.assertIsNone(s.encrypted_api_key)

    def test_user_settings_default_inherit(self):
        user = User.objects.create_user('u2', password='x')
        s = UserAISettings.objects.create(user=user)
        self.assertEqual(s.provider_override, 'inherit')
        self.assertIsNone(s.encrypted_api_key)


# ===========================================================================
# View / form integration — user profile (accounts.views.profile_view)
# ===========================================================================

@override_settings(AI_KEY_ENCRYPTION_KEY=_TEST_FERNET_KEY)
class TestUserAISettingsView(TestCase):
    """POST flow for a user saving / removing a personal BYOK key."""

    def setUp(self):
        from django.urls import reverse
        self.url = reverse('profile')
        self.creator = User.objects.create_user('creator', password='x')
        self.org = Organization.objects.create(name='Acme', created_by=self.creator)
        self.workspace = Workspace.objects.create(
            name='Acme WS', organization=self.org, created_by=self.creator,
        )
        self.user = User.objects.create_user('member', password='x')
        UserProfile.objects.create(
            user=self.user, organization=self.org, is_admin=False,
            active_workspace=self.workspace,
        )
        self.router = AIRouter()

    def test_save_personal_byok_key_when_valid(self):
        self.client.force_login(self.user)
        with patch('ai_assistant.utils.ai_router.AIRouter.validate_api_key', return_value=True):
            resp = self.client.post(self.url, {
                'form_type': 'user_ai_settings',
                'provider_override': 'inherit',
                'byok_provider': 'openai',
                'raw_api_key': 'sk-user-secret-1234',
                'byok_model': '',
                'remove_byok_key': '',
            })
        self.assertEqual(resp.status_code, 302)
        s = UserAISettings.objects.get(user=self.user)
        self.assertEqual(s.byok_provider, 'openai')
        self.assertIsNotNone(s.encrypted_api_key)
        self.assertNotIn('sk-user-secret-1234', s.encrypted_api_key)
        self.assertEqual(self.router._decrypt_key(s.encrypted_api_key), 'sk-user-secret-1234')
        self.assertEqual(s.key_last_four, '••••1234')
        self.assertIsNotNone(s.key_validated_at)

    def test_invalid_key_is_not_stored(self):
        self.client.force_login(self.user)
        with patch('ai_assistant.utils.ai_router.AIRouter.validate_api_key', return_value=False):
            resp = self.client.post(self.url, {
                'form_type': 'user_ai_settings',
                'provider_override': 'inherit',
                'byok_provider': 'openai',
                'raw_api_key': 'sk-bad',
                'byok_model': '',
                'remove_byok_key': '',
            })
        self.assertEqual(resp.status_code, 200)
        # A settings row may exist (get_or_create) but the key must NOT be stored.
        s = UserAISettings.objects.filter(user=self.user).first()
        if s is not None:
            self.assertIsNone(s.encrypted_api_key)

    def test_remove_key_clears_stored_key(self):
        UserAISettings.objects.create(
            user=self.user,
            byok_provider='openai',
            encrypted_api_key=self.router._encrypt_key('sk-existing-9999'),
            key_last_four='••••9999',
        )
        self.client.force_login(self.user)
        resp = self.client.post(self.url, {
            'form_type': 'user_ai_settings',
            'provider_override': 'inherit',
            'byok_provider': '',
            'raw_api_key': '',
            'byok_model': '',
            'remove_byok_key': 'on',
        })
        self.assertEqual(resp.status_code, 302)
        s = UserAISettings.objects.get(user=self.user)
        self.assertIsNone(s.encrypted_api_key)
        self.assertIsNone(s.byok_provider)
        self.assertIsNone(s.key_last_four)

    def test_provider_override_forbidden_when_not_permitted(self):
        # Org disallows overrides and user is not an admin → 403.
        OrganizationAISettings.objects.create(
            workspace=self.workspace, provider='gemini',
            allow_user_provider_override=False,
        )
        self.client.force_login(self.user)
        resp = self.client.post(self.url, {
            'form_type': 'user_ai_settings',
            'provider_override': 'openai',
            'byok_provider': '',
            'raw_api_key': '',
            'byok_model': '',
            'remove_byok_key': '',
        })
        self.assertEqual(resp.status_code, 403)


# ===========================================================================
# View / form integration — org settings (kanban.views.workspace_preset_settings)
# ===========================================================================

@override_settings(AI_KEY_ENCRYPTION_KEY=_TEST_FERNET_KEY)
class TestOrgAISettingsView(TestCase):
    """POST flow for an Org Admin saving an organisation BYOK key."""

    def setUp(self):
        from django.urls import reverse
        self.url = reverse('workspace_preset_settings')
        # Admin is the org creator → is_user_org_admin() returns True.
        self.admin = User.objects.create_user('admin', password='x')
        self.org = Organization.objects.create(name='Acme', created_by=self.admin)
        self.workspace = Workspace.objects.create(
            name='Acme WS', organization=self.org, created_by=self.admin,
        )
        UserProfile.objects.create(
            user=self.admin, organization=self.org, is_admin=True,
            active_workspace=self.workspace,
        )
        # A plain member who is NOT an admin.
        self.member = User.objects.create_user('member', password='x')
        UserProfile.objects.create(
            user=self.member, organization=self.org, is_admin=False,
            active_workspace=self.workspace,
        )
        self.router = AIRouter()

    def test_admin_saves_org_byok_key(self):
        self.client.force_login(self.admin)
        with patch('ai_assistant.utils.ai_router.AIRouter.validate_api_key', return_value=True):
            resp = self.client.post(self.url, {
                'form_type': 'ai_settings',
                'provider': 'gemini',
                'allow_user_provider_override': '',
                'byok_provider': 'anthropic',
                'raw_api_key': 'sk-org-secret-5678',
                'byok_model': '',
                'remove_byok_key': '',
            })
        self.assertEqual(resp.status_code, 302)
        s = OrganizationAISettings.objects.get(workspace=self.workspace)
        self.assertEqual(s.byok_provider, 'anthropic')
        self.assertEqual(self.router._decrypt_key(s.encrypted_api_key), 'sk-org-secret-5678')
        self.assertEqual(s.key_last_four, '••••5678')
        self.assertIsNotNone(s.key_validated_at)

    def test_non_admin_cannot_save_org_settings(self):
        self.client.force_login(self.member)
        resp = self.client.post(self.url, {
            'form_type': 'ai_settings',
            'provider': 'openai',
            'allow_user_provider_override': 'on',
            'byok_provider': '',
            'raw_api_key': '',
            'byok_model': '',
            'remove_byok_key': '',
        })
        # Non-admins are redirected to the dashboard before any change is made.
        self.assertEqual(resp.status_code, 302)
        self.assertFalse(OrganizationAISettings.objects.filter(workspace=self.workspace).exists())
