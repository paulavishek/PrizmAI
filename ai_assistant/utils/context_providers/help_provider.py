"""
Feature Guide Context Provider — gives Spectra product knowledge about PrizmAI
itself so it can (a) explain what a feature does and (b) act as an onboarding
advisor that recommends the right feature for a user's problem.

Unlike every other provider, this one serves **no board data** — it returns
static product knowledge read from ``data/features_reference.md``. Because of
that:

- ``_check_access`` is overridden to always allow: product knowledge is not
  board-scoped, so it should answer even on the welcome screen (no active board)
  or when the user lacks read access to the current board. No board data leaks.
- The always-on summary is a single line, so normal data queries pay almost no
  token cost. The full feature reference loads only when the context router
  matches this provider's FEATURE_TAGS (a help/guide query), and even then the
  detail is scoped to the entries relevant to the query plus a compact index.

Created: June 2026 — Spectra Feature-Guide / Onboarding-Advisor capability.
"""

import logging
import re
from pathlib import Path

from .base import BaseContextProvider
from . import registry

logger = logging.getLogger(__name__)

_FEATURES_FILE = Path(__file__).resolve().parent / 'data' / 'features_reference.md'


def _load_entries():
    """
    Parse the feature reference markdown once into a list of
    ``(feature_name, entry_text)`` tuples, in document order.

    Entries are the ``### Feature Name`` blocks; the ``## Section`` headers and
    the document preamble are skipped (they carry no per-feature content).
    """
    try:
        text = _FEATURES_FILE.read_text(encoding='utf-8')
    except OSError:
        logger.error('Feature reference file missing: %s', _FEATURES_FILE)
        return []

    entries = []
    # Split on level-3 headings; keep the heading with its body.
    chunks = re.split(r'\n(?=### )', text)
    for chunk in chunks:
        chunk = chunk.strip()
        if not chunk.startswith('### '):
            continue
        name = chunk.split('\n', 1)[0][4:].strip()
        entries.append((name, chunk))
    return entries


# Parse once at import — the file is static product knowledge.
_ENTRIES = _load_entries()
_INDEX = ', '.join(name for name, _ in _ENTRIES)

# Stop-words stripped from queries before keyword matching so generic help
# phrasing ("how do i use the ... feature") doesn't match every entry.
_STOPWORDS = {
    'what', 'does', 'do', 'how', 'the', 'a', 'an', 'is', 'are', 'to', 'for',
    'in', 'on', 'of', 'i', 'me', 'my', 'we', 'use', 'using', 'with', 'and',
    'or', 'this', 'that', 'feature', 'features', 'tool', 'tools', 'help',
    'about', 'tell', 'explain', 'which', 'should', 'can', 'where', 'find',
    'work', 'works', 'used', 'when', 'stuck', 'get', 'getting', 'started',
    'prizmai', 'spectra',
}


def _match_entries(query):
    """Return entries whose name/body matches meaningful words in the query."""
    if not query:
        return []
    words = [
        w for w in re.findall(r"[a-z0-9\-']+", query.lower())
        if len(w) > 2 and w not in _STOPWORDS
    ]
    if not words:
        return []

    matched = []
    for name, body in _ENTRIES:
        haystack = body.lower()
        name_lower = name.lower()
        # Score by word hits; matches on the feature name count double.
        score = 0
        for w in words:
            if w in name_lower:
                score += 2
            elif w in haystack:
                score += 1
        if score:
            matched.append((score, name, body))

    matched.sort(key=lambda t: t[0], reverse=True)
    # Cap to keep the detail block bounded even on broad queries.
    return [(name, body) for _, name, body in matched[:6]]


class FeatureGuideContextProvider(BaseContextProvider):
    PROVIDER_NAME = 'PrizmAI Feature Guide'
    FEATURE_TAGS = [
        # Help / onboarding intents
        'how do', 'how to', 'how does', 'what does', 'what is', 'where is',
        'where do i', 'can i', 'feature', 'features', 'help', 'guide',
        'tutorial', 'get started', 'getting started', 'onboarding',
        # Advisor intents (problem -> feature)
        'which feature', 'what should i use', 'recommend a feature',
        "i'm stuck", 'im stuck', 'stuck', 'what tool',
        # Key feature names so name-drop queries route here
        'pre-mortem', 'premortem', 'shadow board', 'gantt', 'stress test',
        'what-if', 'scope autopsy', 'prizmbrief', 'retrospective',
        'focus today', 'decision center', 'discovery', 'knowledge base',
        'task aging', 'aging alerts', 'aging badge', 'configure aging',
    ]

    def _check_access(self, board, user, is_demo_mode=False):
        """
        Always allow for authenticated users — this provider returns static
        product knowledge only (no board data), so it should answer regardless
        of active board or board-level read permissions.
        """
        return bool(user and user.is_authenticated)

    def _get_summary_impl(self, board, user, is_demo_mode=False):
        return (
            'ℹ️ **Feature help:** I can explain any PrizmAI feature and '
            'recommend the right tool for what you\'re trying to do — ask '
            '"what does X do?" or "I\'m stuck, which feature helps?"\n'
        )

    def _get_detail_impl(self, board, user, query='', is_demo_mode=False):
        if not _ENTRIES:
            return None

        header = (
            '**📖 PrizmAI Feature Guide** (authoritative — only describe '
            'features listed here; never invent features or navigation paths):\n'
            f'_All features: {_INDEX}_\n'
        )

        matched = _match_entries(query)
        if matched:
            body = '\n\n'.join(text for _, text in matched)
            return f'{header}\n{body}\n'

        # No specific feature matched — give the index and an advisor nudge so
        # Spectra can still recommend something from the goal the user states.
        return (
            f'{header}\n'
            'No specific feature matched the question. If the user described a '
            'goal or problem, recommend the single most relevant feature above '
            'and tell them where to find it. If they just asked broadly, offer '
            'to point them to a feature once they describe what they want to '
            'accomplish.\n'
        )


registry.register(FeatureGuideContextProvider())
