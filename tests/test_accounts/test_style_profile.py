"""
Tests for the AI response-style profile directive builder
=========================================================

Locks the core invariant: an all-default profile (and any None input) produces
NO directive, so prompts stay byte-identical to pre-feature behavior. Also
verifies that set preferences surface the expected tokens.

The builder is a pure function over duck-typed attributes, so these tests use
lightweight stubs and do not touch the database.
"""

from types import SimpleNamespace

from django.test import SimpleTestCase

from accounts.style_profile import build_ai_style_directive, directive_for_user


def _profile(**overrides):
    """A stub with the same attributes build_ai_style_directive reads."""
    base = dict(
        response_tone='default',
        response_length='default',
        response_structure='default',
        custom_ai_instructions='',
    )
    base.update(overrides)
    return SimpleNamespace(**base)


class BuildAIStyleDirectiveTests(SimpleTestCase):

    def test_none_profile_returns_empty(self):
        self.assertEqual(build_ai_style_directive(None), '')

    def test_all_default_returns_empty(self):
        self.assertEqual(build_ai_style_directive(_profile()), '')

    def test_blank_custom_instructions_ignored(self):
        self.assertEqual(build_ai_style_directive(_profile(custom_ai_instructions='   ')), '')

    def test_tone_only(self):
        out = build_ai_style_directive(_profile(response_tone='executive'))
        self.assertIn('USER FORMATTING PREFERENCES', out)
        self.assertIn('Executive', out)
        # Untouched dimensions must not leak in.
        self.assertNotIn('Length:', out)
        self.assertNotIn('Structure:', out)

    def test_all_dimensions_and_custom(self):
        out = build_ai_style_directive(_profile(
            response_tone='formal',
            response_length='brief',
            response_structure='bullets',
            custom_ai_instructions='Always start with a one-line TL;DR.',
        ))
        self.assertIn('Formal', out)
        self.assertIn('Brief', out)
        self.assertIn('bullet', out.lower())
        self.assertIn('Always start with a one-line TL;DR.', out)
        # Guardrail wording must be present so it never overrides output format.
        self.assertIn('unless they conflict', out.lower())

    def test_custom_instructions_truncated(self):
        long_text = 'x' * 5000
        out = build_ai_style_directive(_profile(custom_ai_instructions=long_text))
        # Should be capped well below the raw input length.
        self.assertLess(len(out), 1000)


class DirectiveForUserTests(SimpleTestCase):

    def test_none_user_returns_empty(self):
        self.assertEqual(directive_for_user(None), '')

    def test_unauthenticated_user_returns_empty(self):
        anon = SimpleNamespace(is_authenticated=False, profile=_profile(response_tone='formal'))
        self.assertEqual(directive_for_user(anon), '')

    def test_user_without_profile_returns_empty(self):
        user = SimpleNamespace(is_authenticated=True)  # no .profile attribute
        self.assertEqual(directive_for_user(user), '')

    def test_authenticated_user_with_prefs(self):
        user = SimpleNamespace(is_authenticated=True, profile=_profile(response_tone='conversational'))
        out = directive_for_user(user)
        self.assertIn('Conversational', out)
