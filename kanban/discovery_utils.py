"""
Shared helpers for turning a PrizmDiscovery idea (or a Forms submission)
into a real Kanban Task.
"""
import re

_INTAKE_COLUMN_NAMES = re.compile(r'\b(to.?do|backlog|inbox|todo|open|new|ideas?|ready)\b', re.I)


def pick_intake_column(board, column_id=None):
    """
    Return the Column a new intake-created Task should land in.

    Honours an explicit column_id (must belong to this board) first;
    otherwise auto-detects a likely "intake" column by name (To Do, Backlog,
    Inbox, ...), falling back to the board's first column by position.
    Returns None if the board has no columns.
    """
    from kanban.models import Column

    all_cols = list(Column.objects.filter(board=board).order_by('position'))
    if not all_cols:
        return None

    if column_id:
        target = next((c for c in all_cols if str(c.pk) == str(column_id)), None)
        if target is not None:
            return target

    return next((c for c in all_cols if _INTAKE_COLUMN_NAMES.search(c.name)), None) or all_cols[0]
