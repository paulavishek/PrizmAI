"""
Single source of truth for column *status* semantics.

Historically, every feature that needed to know "is this the Done / To Do /
In Progress / Review / Blocked column?" guessed from the column's display-name
text with an inline ``'done' in name.lower()`` check. That logic was duplicated
across ~34 call sites in 5 apps and was inconsistent (some recognised
"finished"/"closed", the core progress signal did not). Renaming the "Done"
column to "Finished"/"Achieved" silently broke completion tracking everywhere.

This module centralises that logic. Detection prefers an explicit structural
marker (``Column.column_type``) and falls back to a broadened keyword heuristic
on the name when the type is left on "auto" (empty string).

Import from here — do not re-implement the substring checks inline.
"""

import re
from functools import reduce
from operator import or_

from django.db.models import Q

# ── Canonical column types ──────────────────────────────────────────────────
TODO = 'todo'
IN_PROGRESS = 'in_progress'
REVIEW = 'review'
DONE = 'done'
BLOCKED = 'blocked'
OTHER = 'other'

# Choices for the Column.column_type field. '' == "auto (derive from name)".
COLUMN_TYPE_CHOICES = [
    ('', 'Auto (detect from name)'),
    (TODO, 'To Do'),
    (IN_PROGRESS, 'In Progress'),
    (REVIEW, 'Review'),
    (DONE, 'Done'),
    (BLOCKED, 'Blocked'),
    (OTHER, 'Other'),
]

# ── Keyword heuristics (case-insensitive substring match) ────────────────────
# Broadened from the historical {'done','complete'} so common rename choices
# ("Finished", "Achieved", "Shipped", ...) keep working without an explicit type.
DONE_KEYWORDS = (
    'done', 'complete', 'completed', 'finished', 'achieved', 'closed',
    'resolved', 'shipped', 'delivered', 'released', 'deployed',
)
BLOCKED_KEYWORDS = ('block', 'stall', 'stuck', 'hold', 'waiting', 'impediment')
REVIEW_KEYWORDS = ('review', 'qa', 'testing', 'approval', 'verify', 'validate')
IN_PROGRESS_KEYWORDS = ('in progress', 'in-progress', 'doing', 'wip', 'active', 'working')
TODO_KEYWORDS = ('to do', 'to-do', 'todo', 'backlog', 'new', 'ideas', 'not started', 'planned')

# Precedence: the first category whose keywords match (and aren't negated,
# see NEGATION_CUES below) wins. Interim/workflow states are checked before
# the final Done state, so "Done - Needs Review" resolves to review, and
# Blocked is checked early so "Blocked / on hold" resolves to blocked. Todo
# stays last — its keywords ("new", "planned", ...) are the least specific.
_PRECEDENCE = (
    (BLOCKED, BLOCKED_KEYWORDS),
    (REVIEW, REVIEW_KEYWORDS),
    (IN_PROGRESS, IN_PROGRESS_KEYWORDS),
    (DONE, DONE_KEYWORDS),
    (TODO, TODO_KEYWORDS),
)

# ── Regex matching (word-boundary aware, negation-aware) ─────────────────────
# A plain `kw in name.lower()` substring check has two failure modes:
#  1. False negatives on unlisted synonyms ("Wrapped Up" isn't in DONE_KEYWORDS).
#  2. False positives when the keyword appears as part of another word or is
#     itself negated: "Blockade"/"Unblocked" contain "block"; "Undone"/
#     "Not Done Yet" contain "done". Word-boundary matching alone already
#     fixes concatenated forms ("Undone", "Blockade") since `\b` never fires
#     between two word characters. It does NOT fix a negation cue that's
#     space/hyphen-separated from the keyword ("Not Done", "Non-Done") — a
#     hyphen or space is itself a word-boundary, so the keyword still matches
#     on its own. NEGATION_CUES below catches that second case.
#
# Some keywords ("block", "stall", "review", "verify", "validate") are bare
# stems the old substring check relied on to also catch their inflections
# ("Blocked", "Blocking", "Reviewed", ...). A strict `\bblock\b` rejects
# "Blocked" outright (no boundary between "block" and "-ed"), which would be
# a regression, not a fix. _INFLECTION_SUFFIXES allows exactly those endings
# — not a bare `\w*`, which would let "blockade" match again.
NEGATION_CUES = ('not', 'non', 'never', 'no longer', 'no')
_INFLECTION_SUFFIXES = ('s', 'd', 'ed', 'ing')

_KEYWORD_PATTERNS = {}
_NEGATION_PATTERNS = {}


def _keyword_fragment(kw):
    escaped = re.escape(kw)
    if ' ' in kw or '-' in kw:
        return escaped  # multi-word phrase ("in progress") — no suffix.
    suffix_alt = '|'.join(_INFLECTION_SUFFIXES)
    return f'{escaped}(?:{suffix_alt})?'


def _compile_keyword_patterns():
    cue_alt = '|'.join(re.escape(c) for c in NEGATION_CUES)
    for _category, keywords in _PRECEDENCE:
        for kw in keywords:
            if kw in _KEYWORD_PATTERNS:
                continue
            fragment = _keyword_fragment(kw)
            _KEYWORD_PATTERNS[kw] = re.compile(r'\b' + fragment + r'\b', re.IGNORECASE)
            # Negation cue, then up to two filler words, then the keyword —
            # separated by spaces and/or hyphens ("Not Done", "Non-Done",
            # "No Longer Blocked").
            _NEGATION_PATTERNS[kw] = re.compile(
                r'\b(?:' + cue_alt + r')\b'
                r'(?:[\s\-]+\w+){0,2}[\s\-]+'
                r'\b' + fragment + r'\b',
                re.IGNORECASE,
            )


_compile_keyword_patterns()

# Back-compat: `ai_assistant` imported this frozenset directly. Kept as an alias
# (exact-name membership) so existing imports keep working; new code should use
# the predicates below, which also match "Done ✅" / "All Done".
DONE_COLUMN_NAMES = frozenset({
    'done', 'completed', 'complete', 'closed', 'finished', 'resolved',
})


def classify_column_name(name):
    """Return the status category derived purely from a column *name* string.

    Returns one of TODO / IN_PROGRESS / REVIEW / DONE / BLOCKED / OTHER.

    Matching is word-boundary aware (so "Blockade" doesn't trigger Blocked)
    and negation-aware (so "Not Done Yet" doesn't trigger Done). Negation only
    cancels the specific keyword it negates — an unrelated positive keyword
    elsewhere in the same name still wins, e.g. "In Progress, Not Blocked"
    resolves to in_progress, not other.
    """
    low = (name or '').lower()
    if not low:
        return OTHER
    for category, keywords in _PRECEDENCE:
        for kw in keywords:
            if _NEGATION_PATTERNS[kw].search(low):
                continue
            if _KEYWORD_PATTERNS[kw].search(low):
                return category
    return OTHER


def _resolve(col_or_name):
    """Resolve any accepted input to a status category string.

    Accepts a ``Column`` instance (prefers its explicit ``column_type``, falls
    back to name heuristic) or a plain name string.
    """
    if col_or_name is None:
        return OTHER
    # Column instance: honour the explicit structural marker first.
    column_type = getattr(col_or_name, 'column_type', None)
    if column_type is not None:  # it's a Column-like object
        if column_type:
            return column_type
        return classify_column_name(getattr(col_or_name, 'name', ''))
    # Plain string name.
    return classify_column_name(col_or_name)


def is_done_column(col_or_name):
    """True if the column is a completion column. Accepts a Column or a name."""
    return _resolve(col_or_name) == DONE


def is_todo_column(col_or_name):
    return _resolve(col_or_name) == TODO


def is_in_progress_column(col_or_name):
    return _resolve(col_or_name) == IN_PROGRESS


def is_review_column(col_or_name):
    return _resolve(col_or_name) == REVIEW


def is_blocked_column(col_or_name):
    return _resolve(col_or_name) == BLOCKED


# ── ORM Q-builders (for .filter()/.exclude() on querysets of Task/Column) ─────
_KEYWORDS_BY_TYPE = {
    DONE: DONE_KEYWORDS,
    BLOCKED: BLOCKED_KEYWORDS,
    REVIEW: REVIEW_KEYWORDS,
    IN_PROGRESS: IN_PROGRESS_KEYWORDS,
    TODO: TODO_KEYWORDS,
}


def column_type_q(category, field='column'):
    """Build a Q matching rows whose column has the given status category.

    Matches an explicit ``column_type == category`` OR (auto/empty type AND the
    name heuristic). ``field`` is the relation path to the Column from the model
    being queried: ``'column'`` for Task, or ``''`` when querying Column itself.

    Uses the same word-boundary + negation-aware regexes as
    ``classify_column_name`` (via ``name__iregex``, supported on SQLite through
    Django's Python-``re``-backed REGEXP function, and natively on Postgres),
    so a column named "Undone" or "Not Done Yet" is not matched by
    ``column_type_q('done')`` — kept consistent with ``Column.is_done()``.

    Example: ``Task.objects.filter(column_type_q('done'))``.
    """
    prefix = f'{field}__' if field else ''
    explicit = Q(**{f'{prefix}column_type': category})
    keywords = _KEYWORDS_BY_TYPE.get(category, ())
    if not keywords:
        return explicit
    keyword_qs = (
        Q(**{f'{prefix}name__iregex': _KEYWORD_PATTERNS[kw].pattern})
        & ~Q(**{f'{prefix}name__iregex': _NEGATION_PATTERNS[kw].pattern})
        for kw in keywords
    )
    name_q = reduce(or_, keyword_qs)
    auto = Q(**{f'{prefix}column_type': ''}) & name_q
    return explicit | auto
