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
        awareness of every feature.  Individual provider errors are already
        caught in ``BaseContextProvider.get_summary`` and converted into an
        explicit "data temporarily unavailable" line; the registry trusts
        that contract and just concatenates the returned strings.
        """
        parts = []
        for provider in self._providers.values():
            summary = provider.get_summary(board, user, is_demo_mode)
            if summary and summary.strip():
                parts.append(summary.strip())
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
        Provider errors are handled at the base-class level.
        """
        parts = []
        for name in provider_names:
            provider = self._providers.get(name)
            if not provider:
                logger.warning('Router requested unknown provider: %s', name)
                continue
            detail = provider.get_detail(board, user, query, is_demo_mode)
            if detail and detail.strip():
                parts.append(detail.strip())
        if not parts:
            return ''
        return '\n\n'.join(parts) + '\n'


# ── Module-level singleton ──────────────────────────────────────────────────
registry = ContextProviderRegistry()


def get_cached_summaries(user, board, is_demo_mode=False, ttl=60):
    """
    Return ``(summaries_str, cache_hit_bool)``.

    Summaries are cached per (user_id, board_id, is_demo_mode) for `ttl`
    seconds. Cache invalidation: see ai_assistant/signals.py — Task /
    Column / Board / AccessRequest / BoardStatusReport / TaskActivity
    changes bust the relevant board's entries (cross-board entries are
    busted on any board change).
    """
    try:
        from kanban_board.ai_cache import ai_cache_manager
    except Exception:
        return registry.get_all_summaries(board, user, is_demo_mode), False

    if board:
        op = f'spectra_summaries_board_{board.id}'
    else:
        op = 'spectra_summaries_cross_board'

    user_id = getattr(user, 'id', None) or 'anon'
    cache_payload = f'user={user_id}:demo={int(bool(is_demo_mode))}'

    try:
        cached = ai_cache_manager.get(
            prompt=cache_payload, operation=op, context_hash=None,
        )
    except Exception:
        cached = None

    if cached is not None:
        return cached, True

    summaries = registry.get_all_summaries(board, user, is_demo_mode)

    try:
        ai_cache_manager.set(
            prompt=cache_payload, result=summaries, operation=op,
            context_hash=None, ttl=ttl,
        )
    except Exception:
        pass

    return summaries, False


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
        # ── Coverage-gap providers added April 2026 ──
        requirements_provider,
        stakeholder_provider,
        custom_fields_provider,
        resource_leveling_provider,
        scope_provider,
        risk_scenarios_provider,
        discovery_provider,
        access_provider,
        knowledge_base_provider,
        # ── Spectra v2 providers (May 2026) ──
        activity_provider,
        coach_provider,
        memory_provider,
        status_report_provider,
        integrations_provider,
        comments_provider,
        files_provider,
        skill_dev_provider,
        briefs_provider,
        # ── May 2026: Conflicts + Shadow Board coverage gaps ──
        conflicts_provider,
        shadow_board_provider,
    )


_auto_register()
