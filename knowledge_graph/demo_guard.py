"""Demo-board guard for auto-captured Organizational Memory.

The demo's Organizational Memory is a fixed, hand-curated set (seeded by
``populate_knowledge_demo_data``) — 29 entries spanning every memory type, with a
few pre-flagged "Gaps Noted" so demo users can experience the Spectra
fill-the-gaps loop. Live auto-capture (post_save signals, daily Celery tasks,
commitment/autopsy/automation writers) must NOT run on demo boards, or each
per-user sandbox copy drifts upward without bound and the curated experience
stops being deterministic across Reset Demo.

``is_demo_board`` is the single predicate every background auto-capture writer
consults before creating a node. It is board-attribute only (no request), so it
works equally from signals and Celery tasks.
"""


def is_demo_board(board):
    """True if ``board`` is part of the curated demo experience.

    Covers the official template board, every per-user sandbox copy (including
    orphaned copies whose ``workspace`` is None), and any board living in a demo
    workspace (``Workspace.is_demo`` — the canonical demo marker also used by
    ``kanban.permissions.is_demo_context``).
    """
    if board is None:
        return False
    if getattr(board, 'is_sandbox_copy', False) or getattr(board, 'is_official_demo_board', False):
        return True
    ws = getattr(board, 'workspace', None)
    return bool(ws and getattr(ws, 'is_demo', False))
