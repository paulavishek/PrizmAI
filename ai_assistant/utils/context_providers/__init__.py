"""
Spectra Context Provider Registry — auto-discovers and orchestrates providers.

Usage in chatbot_service.py::

    from ai_assistant.utils.context_providers import registry

    # Always-on compact summaries (~50-100 lines, every query)
    summaries = registry.get_all_summaries(board, user, is_demo_mode)

    # Detailed context for relevant providers (router decides which)
    details = registry.get_relevant_details(board, user, query, is_demo_mode)

Created: April 16, 2026
"""

import logging
from .base import BaseContextProvider

logger = logging.getLogger(__name__)


class ContextProviderRegistry:
    """
    Central registry of all Spectra context providers.

    Providers register themselves at import time via ``register()``.
    The registry provides two main entry points:

    1. ``get_all_summaries()`` — compact summaries from ALL providers
    2. ``get_relevant_details()`` — full detail from matched providers
    """

    def __init__(self):
        self._providers: dict[str, BaseContextProvider] = {}

    def register(self, provider: BaseContextProvider):
        """Register a provider instance.  Replaces existing if same name."""
        name = provider.PROVIDER_NAME
        if not name:
            raise ValueError(
                f'{provider.__class__.__name__} must define PROVIDER_NAME'
            )
        self._providers[name] = provider
        logger.debug('Registered context provider: %s', name)

    @property
    def providers(self) -> dict[str, BaseContextProvider]:
        return dict(self._providers)

    def get_all_tags(self) -> dict[str, list[str]]:
        """Return {provider_name: [tags]} for the router."""
        return {
            name: p.FEATURE_TAGS
            for name, p in self._providers.items()
        }

    # ── Main API ────────────────────────────────────────────────────────

    def get_all_summaries(self, board, user, is_demo_mode=False):
        """
        Collect compact summaries from ALL registered providers.

        Returns a single string of ~50-100 lines giving Spectra baseline
        awareness of every feature.  Errors in individual providers are
        caught and reported inline (never crash the whole response).
        """
        parts = []
        for name, provider in self._providers.items():
            try:
                summary = provider.get_summary(board, user, is_demo_mode)
                if summary and summary.strip():
                    parts.append(summary.strip())
            except Exception as e:
                logger.warning('Provider %s summary error: %s', name, e)
                parts.append(f'⚠️ {name} data temporarily unavailable.')
        if not parts:
            return ''
        return (
            '**📊 Feature Summaries (use these numbers — do NOT recount):**\n'
            + '\n'.join(parts)
            + '\n'
        )

    def get_relevant_details(
        self, board, user, query, provider_names, is_demo_mode=False
    ):
        """
        Collect detailed context from the specified providers.

        ``provider_names`` is a list of provider names chosen by the
        context router.  Only those providers are queried for full detail.
        """
        parts = []
        for name in provider_names:
            provider = self._providers.get(name)
            if not provider:
                logger.warning('Router requested unknown provider: %s', name)
                continue
            try:
                detail = provider.get_detail(
                    board, user, query, is_demo_mode
                )
                if detail and detail.strip():
                    parts.append(detail.strip())
            except Exception as e:
                logger.warning('Provider %s detail error: %s', name, e)
                parts.append(f'⚠️ {name} detailed data temporarily unavailable.')
        if not parts:
            return ''
        return '\n\n'.join(parts) + '\n'


# ── Module-level singleton ──────────────────────────────────────────────────
registry = ContextProviderRegistry()


def _auto_register():
    """Import all provider modules so they self-register."""
    from . import (  # noqa: F401
        board_provider,
        hierarchy_provider,
        analytics_provider,
        time_tracking_provider,
        calendar_provider,
        communication_provider,
        decisions_provider,
        wiki_provider,
        risk_provider,
        budget_provider,
        retrospective_provider,
        automation_provider,
        commitment_provider,
        cemetery_provider,
        aggregate_provider,
    )


_auto_register()
