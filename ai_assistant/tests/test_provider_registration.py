"""
test_provider_registration.py — guard against orphaned Spectra providers.

Every ``*_provider.py`` module under ``ai_assistant/utils/context_providers/``
defines a ``BaseContextProvider`` subclass and calls ``registry.register(...)``
at import time. If a module is left out of ``_auto_register()`` (as the Forms
provider was before July 2026), it never imports, never registers, and the
feature becomes invisible to Spectra with no error.

This test imports each provider module and asserts its provider ended up in the
registry, so a future provider can't be silently orphaned the same way.

Run with:
    python manage.py test ai_assistant.tests.test_provider_registration
"""

import importlib
import inspect
import pkgutil

from django.test import SimpleTestCase

from ai_assistant.utils import context_providers as cp_pkg
from ai_assistant.utils.context_providers import registry
from ai_assistant.utils.context_providers.base import BaseContextProvider


def _all_provider_module_names():
    """Names of every ``*_provider`` module in the context_providers package."""
    return sorted(
        name
        for _, name, ispkg in pkgutil.iter_modules(cp_pkg.__path__)
        if not ispkg and name.endswith('_provider')
    )


class ProviderRegistrationTests(SimpleTestCase):
    def test_every_provider_module_is_registered(self):
        """Import each *_provider module and confirm its provider registered."""
        registered_names = set(registry.providers.keys())
        missing = []

        for mod_name in _all_provider_module_names():
            module = importlib.import_module(
                f'{cp_pkg.__name__}.{mod_name}'
            )
            # Find the concrete BaseContextProvider subclass defined here.
            provider_classes = [
                obj
                for _, obj in inspect.getmembers(module, inspect.isclass)
                if issubclass(obj, BaseContextProvider)
                and obj is not BaseContextProvider
                and obj.__module__ == module.__name__
            ]
            self.assertTrue(
                provider_classes,
                f'{mod_name} defines no BaseContextProvider subclass',
            )
            for cls in provider_classes:
                if cls.PROVIDER_NAME not in registered_names:
                    missing.append(f'{mod_name}:{cls.PROVIDER_NAME}')

        self.assertFalse(
            missing,
            'Provider module(s) not wired into _auto_register() — they will '
            f'never load and their feature is invisible to Spectra: {missing}',
        )

    def test_forms_provider_registered(self):
        """Explicit regression guard for the Forms orphan bug (July 2026)."""
        self.assertIn('Forms', registry.providers)
