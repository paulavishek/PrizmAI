"""
AI-powered views for the messaging app.

Provides:
  - summarize_thread       : Summarize last N messages in a chat room
  - extract_tasks_from_thread  : Extract actionable tasks from last N messages
  - extract_tasks_from_message : Extract actionable tasks from a single message
  - confirm_create_tasks   : Create confirmed task suggestions on the board
"""

import json
import logging
import re

from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.shortcuts import get_object_or_404
from django.views.decorators.http import require_POST

from .models import ChatMessage, ChatRoom
from kanban.models import Column, Task

logger = logging.getLogger(__name__)

# Maximum messages to include in thread-level AI calls (token budget guard)
THREAD_MESSAGE_LIMIT = 50


def _require_room_member(request, room):
    """Return True if the user is a member of the chat room, False otherwise."""
    return room.members.filter(pk=request.user.pk).exists()


def _build_message_transcript(messages):
    """Build a readable transcript string from a queryset of ChatMessage objects."""
    lines = []
    for msg in messages:
        ts = msg.created_at.strftime("%Y-%m-%d %H:%M")
        author = msg.author.get_full_name() or msg.author.username
        lines.append(f"[{ts}] {author}: {msg.content}")
    return "\n".join(lines)


def _extract_json_array(text):
    """
    Defensively extract the first JSON array from an AI response string.
    Handles markdown code fences and surrounding prose.
    Returns a Python list or None on failure.
    """
    if not text:
        return None
    # Strip markdown code fences (```json ... ``` or ``` ... ```)
    text = re.sub(r"```(?:json)?", "", text).strip()
    # Find the first [ ... ] block
    match = re.search(r"(\[.*\])", text, re.DOTALL)
    if not match:
        return None
    try:
        return json.loads(match.group(1))
    except (json.JSONDecodeError, ValueError):
        return None


# ---------------------------------------------------------------------------
# View 1: Summarize thread
# ---------------------------------------------------------------------------

@login_required
@require_POST
def summarize_thread(request, room_id):
    """
    POST /messaging/room/<room_id>/ai/summarize/
    Returns: {"summary": "..."}
    """
    room = get_object_or_404(ChatRoom, pk=room_id)
    if not _require_room_member(request, room):
        return JsonResponse({"error": "You are not a member of this room."}, status=403)

    messages = (
        ChatMessage.objects
        .filter(chat_room=room)
        .select_related("author")
        .order_by("-created_at")[:THREAD_MESSAGE_LIMIT]
    )
    messages = list(reversed(messages))  # chronological order

    if not messages:
        return JsonResponse({"error": "No messages to summarize."}, status=400)

    transcript = _build_message_transcript(messages)

    prompt = f"""You are a project management assistant helping a busy team.
Below is a chat transcript from the "{room.name}" channel on the "{room.board.name}" project board.

TRANSCRIPT:
{transcript}

Write a concise summary (3-5 sentences) that covers:
1. The main topics discussed
2. Any decisions made
3. Any blockers or concerns raised
4. Any action items or next steps mentioned

Be direct and professional. Do not include greetings or meta-commentary."""

    try:
        from kanban.utils.ai_utils import generate_ai_content
        summary = generate_ai_content(prompt, task_type="simple")
    except Exception as exc:
        logger.exception("AI summarize_thread failed for room %s: %s", room_id, exc)
        return JsonResponse({"error": "AI service unavailable. Please try again."}, status=503)

    if not summary:
        return JsonResponse({"error": "AI returned an empty response. Please try again."}, status=503)

    return JsonResponse({"summary": summary.strip()})


# ---------------------------------------------------------------------------
# View 2: Extract tasks from a single message
# ---------------------------------------------------------------------------

@login_required
@require_POST
def extract_tasks_from_message(request, message_id):
    """
    POST /messaging/message/<message_id>/ai/extract-tasks/
    Returns: {"tasks": [{title, description, priority}, ...]}
    """
    message = get_object_or_404(ChatMessage, pk=message_id)
    room = message.chat_room

    if not _require_room_member(request, room):
        return JsonResponse({"error": "You are not a member of this room."}, status=403)

    author = message.author.get_full_name() or message.author.username
    prompt = f"""You are a project management assistant.
Analyse the following chat message and extract any actionable tasks, action items, or work to be done.

MESSAGE (from {author}):
{message.content}

Return a raw JSON array of task objects — NO markdown, NO prose, ONLY the JSON.
Each object must have exactly these keys:
  "title"       : short task title (max 80 chars)
  "description" : brief explanation of what needs to be done (1-2 sentences)
  "priority"    : one of "low", "medium", "high", or "urgent"

If there are no actionable tasks in the message, return an empty array: []

Example format:
[{{"title": "Fix login bug", "description": "Resolve the authentication error reported by users.", "priority": "high"}}]"""

    try:
        from kanban.utils.ai_utils import generate_ai_content
        raw = generate_ai_content(prompt, task_type="simple")
    except Exception as exc:
        logger.exception("AI extract_tasks_from_message failed for message %s: %s", message_id, exc)
        return JsonResponse({"error": "AI service unavailable. Please try again."}, status=503)

    tasks = _extract_json_array(raw)
    if tasks is None:
        # AI returned unparseable output — treat gracefully
        logger.warning("Could not parse task JSON from AI response for message %s: %r", message_id, raw)
        return JsonResponse({"tasks": [], "note": "No actionable tasks could be identified."})

    # Sanitize: keep only expected keys, enforce priority values
    valid_priorities = {"low", "medium", "high", "urgent"}
    clean_tasks = []
    for t in tasks:
        if isinstance(t, dict) and t.get("title"):
            clean_tasks.append({
                "title": str(t.get("title", ""))[:80].strip(),
                "description": str(t.get("description", "")).strip(),
                "priority": t.get("priority", "medium") if t.get("priority") in valid_priorities else "medium",
            })

    return JsonResponse({"tasks": clean_tasks})


# ---------------------------------------------------------------------------
# View 3: Extract tasks from entire thread
# ---------------------------------------------------------------------------

@login_required
@require_POST
def extract_tasks_from_thread(request, room_id):
    """
    POST /messaging/room/<room_id>/ai/extract-tasks/
    Returns: {"tasks": [{title, description, priority}, ...]}
    """
    room = get_object_or_404(ChatRoom, pk=room_id)
    if not _require_room_member(request, room):
        return JsonResponse({"error": "You are not a member of this room."}, status=403)

    messages = (
        ChatMessage.objects
        .filter(chat_room=room)
        .select_related("author")
        .order_by("-created_at")[:THREAD_MESSAGE_LIMIT]
    )
    messages = list(reversed(messages))

    if not messages:
        return JsonResponse({"tasks": [], "note": "No messages in this room."})

    transcript = _build_message_transcript(messages)

    prompt = f"""You are a project management assistant.
Analyse the following chat transcript from the "{room.name}" channel and extract ALL actionable tasks, action items, or work to be done.

TRANSCRIPT:
{transcript}

Return a raw JSON array of task objects — NO markdown, NO prose, ONLY the JSON.
Each object must have exactly these keys:
  "title"       : short task title (max 80 chars)
  "description" : brief explanation of what needs to be done (1-2 sentences)
  "priority"    : one of "low", "medium", "high", or "urgent"

Consolidate duplicate or similar items into one task. Do not invent tasks not mentioned in the conversation.
If there are no actionable tasks, return an empty array: []"""

    try:
        from kanban.utils.ai_utils import generate_ai_content
        raw = generate_ai_content(prompt, task_type="simple")
    except Exception as exc:
        logger.exception("AI extract_tasks_from_thread failed for room %s: %s", room_id, exc)
        return JsonResponse({"error": "AI service unavailable. Please try again."}, status=503)

    tasks = _extract_json_array(raw)
    if tasks is None:
        logger.warning("Could not parse task JSON from AI response for room %s: %r", room_id, raw)
        return JsonResponse({"tasks": [], "note": "No actionable tasks could be identified."})

    valid_priorities = {"low", "medium", "high", "urgent"}
    clean_tasks = []
    for t in tasks:
        if isinstance(t, dict) and t.get("title"):
            clean_tasks.append({
                "title": str(t.get("title", ""))[:80].strip(),
                "description": str(t.get("description", "")).strip(),
                "priority": t.get("priority", "medium") if t.get("priority") in valid_priorities else "medium",
            })

    return JsonResponse({"tasks": clean_tasks})


# ---------------------------------------------------------------------------
# View 4: Confirm and create selected tasks
# ---------------------------------------------------------------------------

@login_required
@require_POST
def confirm_create_tasks(request, room_id):
    """
    POST /messaging/room/<room_id>/ai/confirm-tasks/
    Body (JSON): {"tasks": [{title, description, priority}, ...]}
    Returns: {"created": [{id, title, url}, ...]}
    """
    room = get_object_or_404(ChatRoom, pk=room_id)
    if not _require_room_member(request, room):
        return JsonResponse({"error": "You are not a member of this room."}, status=403)

    try:
        body = json.loads(request.body)
        tasks_data = body.get("tasks", [])
    except (json.JSONDecodeError, ValueError):
        return JsonResponse({"error": "Invalid JSON body."}, status=400)

    if not tasks_data:
        return JsonResponse({"error": "No tasks provided."}, status=400)

    board = room.board

    # Resolve target column: prefer "To Do" by name, fallback to first column by position
    column = (
        Column.objects.filter(board=board, name__icontains="to do").first()
        or Column.objects.filter(board=board, name__icontains="todo").first()
        or Column.objects.filter(board=board).order_by("position").first()
    )

    if not column:
        return JsonResponse({"error": "No columns found on this board. Please create a column first."}, status=400)

    valid_priorities = {"low", "medium", "high", "urgent"}
    created_tasks = []

    for task_data in tasks_data:
        title = str(task_data.get("title", "")).strip()[:200]
        if not title:
            continue

        description = str(task_data.get("description", "")).strip()
        priority = task_data.get("priority", "medium")
        if priority not in valid_priorities:
            priority = "medium"

        # Compute next position in column
        last_position = (
            Task.objects.filter(column=column).order_by("-position").values_list("position", flat=True).first()
        )
        next_position = (last_position + 1) if last_position is not None else 0

        task = Task.objects.create(
            title=title,
            description=description,
            priority=priority,
            column=column,
            created_by=request.user,
            position=next_position,
        )

        # Build URL to the task detail page
        try:
            from django.urls import reverse
            task_url = reverse("task_detail", args=[task.id])
        except Exception:
            task_url = f"/tasks/{task.id}/"

        created_tasks.append({
            "id": task.id,
            "title": task.title,
            "url": task_url,
        })

    return JsonResponse({"created": created_tasks, "board_name": board.name, "column_name": column.name})
