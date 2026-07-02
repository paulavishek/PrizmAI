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

# Precedence: the first category whose keywords match wins. Done is checked
# before Review/In-Progress so "Done - reviewed" resolves to done, and Blocked
# is checked early so "Blocked / on hold" resolves to blocked.
_PRECEDENCE = (
    (DONE, DONE_KEYWORDS),
    (BLOCKED, BLOCKED_KEYWORDS),
    (REVIEW, REVIEW_KEYWORDS),
    (IN_PROGRESS, IN_PROGRESS_KEYWORDS),
    (TODO, TODO_KEYWORDS),
)

# Back-compat: `ai_assistant` imported this frozenset directly. Kept as an alias
# (exact-name membership) so existing imports keep working; new code should use
# the predicates below, which also match "Done ✅" / "All Done".
DONE_COLUMN_NAMES = frozenset({
    'done', 'completed', 'complete', 'closed', 'finished', 'resolved',
})


def classify_column_name(name):
    """Return the status category derived purely from a column *name* string.

    Returns one of TODO / IN_PROGRESS / REVIEW / DONE / BLOCKED / OTHER.
    """
    low = (name or '').lower()
    for category, keywords in _PRECEDENCE:
        if any(kw in low for kw in keywords):
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

    Example: ``Task.objects.filter(column_type_q('done'))``.
    """
    prefix = f'{field}__' if field else ''
    explicit = Q(**{f'{prefix}column_type': category})
    keywords = _KEYWORDS_BY_TYPE.get(category, ())
    if not keywords:
        return explicit
    name_q = reduce(
        or_,
        (Q(**{f'{prefix}name__icontains': kw}) for kw in keywords),
    )
    auto = Q(**{f'{prefix}column_type': ''}) & name_q
    return explicit | auto
