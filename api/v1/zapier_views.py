"""
Zapier REST API Views — PrizmAI v1
====================================
These endpoints follow Zapier's polling trigger requirements:
- Returns a flat JSON array (no pagination wrapper)
- Supports ?since=<task_id> for deduplication
- Ordered by id DESC (newest first) so Zapier can detect new items

Authentication: same API token as the rest of PrizmAI's REST API.
Send token in the Authorization header:  Authorization: Token <your_token>

NOTE: This integration is currently private/internal for testing.
When PrizmAI is deployed on a public server, this app definition can be
submitted to Zapier's marketplace via `zapier push` (see zapier-app/ directory).
"""
import re
from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework.decorators import api_view, authentication_classes, permission_classes
from rest_framework.response import Response
from rest_framework import status, permissions

from kanban.models import Board, Column, Task
from api.v1.authentication import APITokenAuthentication, ScopePermission
from api.v1.serializers import TaskSerializer, BoardListSerializer


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _get_accessible_boards(user):
    """Return boards the authenticated user can access, excluding demos."""
    from kanban.utils.demo_protection import get_user_boards
    return get_user_boards(user)


def _task_to_zapier(task):
    """Flatten a Task into the simple dict Zapier expects."""
    board = task.column.board
    return {
        "id": task.id,
        "title": task.title,
        "description": task.description or "",
        "priority": task.priority,
        "progress": task.progress,
        "column_id": task.column_id,
        "column_name": task.column.name,
        "board_id": board.id,
        "board_name": board.name,
        "assigned_to_id": task.assigned_to_id,
        "assigned_to_username": task.assigned_to.username if task.assigned_to else None,
        "due_date": task.due_date.isoformat() if task.due_date else None,
        "start_date": task.start_date.isoformat() if task.start_date else None,
        "created_at": task.created_at.isoformat(),
        "updated_at": task.updated_at.isoformat(),
    }


def _apply_since_filter(queryset, request):
    """Apply ?since=<task_id> deduplication filter used by Zapier polling."""
    since = request.query_params.get("since")
    if since:
        try:
            since_id = int(since)
            queryset = queryset.filter(id__gt=since_id)
        except (ValueError, TypeError):
            pass
    return queryset


def _apply_board_filter(queryset, request):
    """Apply optional ?board_id=<id> filter."""
    board_id = request.query_params.get("board_id")
    if board_id:
        queryset = queryset.filter(column__board_id=board_id)
    return queryset


# ---------------------------------------------------------------------------
# Trigger: New Task (Zapier polling)
# GET /api/v1/zapier/tasks/
# ---------------------------------------------------------------------------

@api_view(["GET"])
@authentication_classes([APITokenAuthentication])
@permission_classes([permissions.IsAuthenticated])
def zapier_task_list(request):
    """
    Zapier polling trigger — New Task.

    Returns the most recent tasks (newest first).
    Supports:
      ?since=<task_id>    — only return tasks with id > this value (deduplication)
      ?board_id=<id>      — filter to a specific board
    """
    # Scope check: tasks.read
    token = getattr(request, "auth", None)
    if token and not _has_scope(token, "tasks.read"):
        return Response({"error": "Scope 'tasks.read' required."}, status=status.HTTP_403_FORBIDDEN)

    boards = _get_accessible_boards(request.user)
    queryset = (
        Task.objects.filter(column__board__in=boards, item_type="task")
        .select_related("column", "column__board", "assigned_to")
        .order_by("-id")
    )
    queryset = _apply_since_filter(queryset, request)
    queryset = _apply_board_filter(queryset, request)

    return Response([_task_to_zapier(t) for t in queryset[:100]])


# ---------------------------------------------------------------------------
# Trigger: Task Completed (Zapier polling)
# GET /api/v1/zapier/tasks/completed/
# ---------------------------------------------------------------------------

@api_view(["GET"])
@authentication_classes([APITokenAuthentication])
@permission_classes([permissions.IsAuthenticated])
def zapier_task_completed(request):
    """
    Zapier polling trigger — Task Completed.

    Returns tasks with progress == 100, newest first.
    Supports ?since and ?board_id filters.
    """
    token = getattr(request, "auth", None)
    if token and not _has_scope(token, "tasks.read"):
        return Response({"error": "Scope 'tasks.read' required."}, status=status.HTTP_403_FORBIDDEN)

    boards = _get_accessible_boards(request.user)
    queryset = (
        Task.objects.filter(column__board__in=boards, item_type="task", progress=100)
        .select_related("column", "column__board", "assigned_to")
        .order_by("-id")
    )
    queryset = _apply_since_filter(queryset, request)
    queryset = _apply_board_filter(queryset, request)

    return Response([_task_to_zapier(t) for t in queryset[:100]])


# ---------------------------------------------------------------------------
# Trigger: Task Assigned to Me (Zapier polling)
# GET /api/v1/zapier/tasks/assigned/
# ---------------------------------------------------------------------------

@api_view(["GET"])
@authentication_classes([APITokenAuthentication])
@permission_classes([permissions.IsAuthenticated])
def zapier_task_assigned(request):
    """
    Zapier polling trigger — Task Assigned.

    Returns tasks assigned to the authenticated user, newest first.
    Supports ?since and ?board_id filters.
    """
    token = getattr(request, "auth", None)
    if token and not _has_scope(token, "tasks.read"):
        return Response({"error": "Scope 'tasks.read' required."}, status=status.HTTP_403_FORBIDDEN)

    boards = _get_accessible_boards(request.user)
    queryset = (
        Task.objects.filter(
            column__board__in=boards,
            item_type="task",
            assigned_to=request.user,
        )
        .select_related("column", "column__board", "assigned_to")
        .order_by("-id")
    )
    queryset = _apply_since_filter(queryset, request)
    queryset = _apply_board_filter(queryset, request)

    return Response([_task_to_zapier(t) for t in queryset[:100]])


# ---------------------------------------------------------------------------
# Action: Create Task
# POST /api/v1/zapier/tasks/
# ---------------------------------------------------------------------------

@api_view(["POST"])
@authentication_classes([APITokenAuthentication])
@permission_classes([permissions.IsAuthenticated])
def zapier_task_create(request):
    """
    Zapier action — Create Task.

    Required body fields:
      title       string
      board_id    int
      column_id   int (optional; defaults to first column of the board)

    Optional body fields:
      description  string
      priority     low | medium | high | urgent
      due_date     ISO 8601 datetime string
      assigned_to  user id (int)
    """
    token = getattr(request, "auth", None)
    if token and not _has_scope(token, "tasks.write"):
        return Response({"error": "Scope 'tasks.write' required."}, status=status.HTTP_403_FORBIDDEN)

    title = request.data.get("title", "").strip()
    if not title:
        return Response({"error": "'title' is required."}, status=status.HTTP_400_BAD_REQUEST)

    board_id = request.data.get("board_id")
    if not board_id:
        return Response({"error": "'board_id' is required."}, status=status.HTTP_400_BAD_REQUEST)

    boards = _get_accessible_boards(request.user)
    board = boards.filter(id=board_id).first()
    if not board:
        return Response({"error": "Board not found or not accessible."}, status=status.HTTP_404_NOT_FOUND)

    column_id = request.data.get("column_id")
    if column_id:
        column = Column.objects.filter(id=column_id, board=board).first()
        if not column:
            return Response({"error": "Column not found on this board."}, status=status.HTTP_404_NOT_FOUND)
    else:
        column = board.columns.order_by("position").first()
        if not column:
            return Response({"error": "Board has no columns."}, status=status.HTTP_400_BAD_REQUEST)

    task = Task(
        title=title,
        description=request.data.get("description", ""),
        column=column,
        created_by=request.user,
        priority=request.data.get("priority", "medium"),
        item_type="task",
    )

    due_date = request.data.get("due_date")
    if due_date:
        try:
            from django.utils.dateparse import parse_datetime
            task.due_date = parse_datetime(due_date)
        except Exception:
            return Response({"error": "Invalid due_date format. Use ISO 8601."}, status=status.HTTP_400_BAD_REQUEST)

    assigned_to_id = request.data.get("assigned_to")
    if assigned_to_id:
        from django.contrib.auth.models import User
        try:
            task.assigned_to = User.objects.get(id=assigned_to_id)
        except User.DoesNotExist:
            return Response({"error": "assigned_to user not found."}, status=status.HTTP_404_NOT_FOUND)

    task.save()
    return Response(_task_to_zapier(task), status=status.HTTP_201_CREATED)


# ---------------------------------------------------------------------------
# Action: Update Task Status
# PATCH /api/v1/zapier/tasks/<task_id>/status/
# ---------------------------------------------------------------------------

@api_view(["PATCH"])
@authentication_classes([APITokenAuthentication])
@permission_classes([permissions.IsAuthenticated])
def zapier_task_update_status(request, task_id):
    """
    Zapier action — Update Task Status.

    Moves the task to a different column (status) by column name or column_id.

    Body fields (one required):
      column_id    int      — move to column by id
      column_name  string   — move to column matching this name (case-insensitive)
      progress     int 0-100 — optionally update progress too
    """
    token = getattr(request, "auth", None)
    if token and not _has_scope(token, "tasks.write"):
        return Response({"error": "Scope 'tasks.write' required."}, status=status.HTTP_403_FORBIDDEN)

    boards = _get_accessible_boards(request.user)
    task = Task.objects.filter(id=task_id, column__board__in=boards).select_related(
        "column", "column__board", "assigned_to"
    ).first()
    if not task:
        return Response({"error": "Task not found or not accessible."}, status=status.HTTP_404_NOT_FOUND)

    board = task.column.board
    column_id = request.data.get("column_id")
    column_name = request.data.get("column_name")

    if column_id:
        column = Column.objects.filter(id=column_id, board=board).first()
    elif column_name:
        column = Column.objects.filter(board=board, name__iexact=column_name).first()
    else:
        return Response({"error": "Provide 'column_id' or 'column_name'."}, status=status.HTTP_400_BAD_REQUEST)

    if not column:
        return Response({"error": "Column not found on this board."}, status=status.HTTP_404_NOT_FOUND)

    task.column = column

    progress = request.data.get("progress")
    if progress is not None:
        try:
            task.progress = max(0, min(100, int(progress)))
        except (ValueError, TypeError):
            return Response({"error": "progress must be an integer 0-100."}, status=status.HTTP_400_BAD_REQUEST)

    task.save()
    return Response(_task_to_zapier(task))


# ---------------------------------------------------------------------------
# Boards list (for Zapier dynamic dropdown)
# GET /api/v1/zapier/boards/
# ---------------------------------------------------------------------------

@api_view(["GET"])
@authentication_classes([APITokenAuthentication])
@permission_classes([permissions.IsAuthenticated])
def zapier_board_list(request):
    """
    Returns a flat list of boards the authenticated user can access.
    Used by Zapier for dynamic board dropdowns in triggers/actions.
    """
    token = getattr(request, "auth", None)
    if token and not _has_scope(token, "boards.read"):
        return Response({"error": "Scope 'boards.read' required."}, status=status.HTTP_403_FORBIDDEN)

    boards = _get_accessible_boards(request.user).order_by("name")
    return Response([
        {
            "id": b.id,
            "name": b.name,
            "task_prefix": b.task_prefix,
            "column_count": b.columns.count(),
        }
        for b in boards
    ])


# ---------------------------------------------------------------------------
# Columns list (for Zapier dynamic dropdown)
# GET /api/v1/zapier/boards/<board_id>/columns/
# ---------------------------------------------------------------------------

@api_view(["GET"])
@authentication_classes([APITokenAuthentication])
@permission_classes([permissions.IsAuthenticated])
def zapier_column_list(request, board_id):
    """
    Returns columns for a board.
    Used by Zapier for dynamic column/status dropdowns.
    """
    token = getattr(request, "auth", None)
    if token and not _has_scope(token, "boards.read"):
        return Response({"error": "Scope 'boards.read' required."}, status=status.HTTP_403_FORBIDDEN)

    boards = _get_accessible_boards(request.user)
    board = boards.filter(id=board_id).first()
    if not board:
        return Response({"error": "Board not found or not accessible."}, status=status.HTTP_404_NOT_FOUND)

    columns = board.columns.order_by("position")
    return Response([{"id": c.id, "name": c.name, "position": c.position} for c in columns])


# ---------------------------------------------------------------------------
# Internal helper
# ---------------------------------------------------------------------------

def _has_scope(token, required_scope):
    """
    Returns True if the token has the required scope OR has no scopes set
    (empty scopes = full access, matching existing ScopePermission behaviour).
    """
    scopes = getattr(token, "scopes", None)
    if not scopes:
        return True  # no scope restrictions → full access
    return required_scope in scopes
