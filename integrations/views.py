"""
Integrations views.

GitHub Webhook Receiver
-----------------------
Endpoint: POST /api/integrations/github/

GitHub sends a POST request when a pull_request event fires.
We verify the HMAC-SHA256 signature, then scan the PR title and body
for PrizmAI task IDs (e.g. "SD-101") and move matching tasks to the
configured "In Review" column.

Security:
  - Every request must carry a valid X-Hub-Signature-256 header.
  - Requests without a valid signature are rejected with HTTP 403.
  - Requests from repos not linked to any board are silently ignored (HTTP 200).
"""
import hashlib
import hmac
import json
import re

from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST
from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, render, redirect
from django.contrib import messages

from kanban.models import Board, Column, Task
from integrations.models import GitHubIntegration, SourceConnection
from integrations.forms import GitHubIntegrationForm

# ---------------------------------------------------------------------------
# GitHub Webhook Receiver
# ---------------------------------------------------------------------------

@csrf_exempt
@require_POST
def github_webhook_receiver(request):
    """
    Receives pull_request webhook events from GitHub.

    GitHub configuration:
      Payload URL : https://<your-domain>/api/integrations/github/
      Content type: application/json
      Secret      : (copy from PrizmAI board settings)
      Events      : Pull requests
    """
    raw_body = request.body

    # ------------------------------------------------------------------
    # 1. Identify which integration this payload belongs to.
    #    GitHub sends a user-defined secret per webhook; we store one secret
    #    per GitHubIntegration row and find the matching one by trying each.
    # ------------------------------------------------------------------
    signature_header = request.META.get("HTTP_X_HUB_SIGNATURE_256", "")
    if not signature_header.startswith("sha256="):
        return JsonResponse({"error": "Missing or malformed signature."}, status=403)

    received_sig = signature_header[len("sha256="):]

    # Find the matching integration by testing HMAC against each active one.
    matched_integration = None
    for integration in GitHubIntegration.objects.filter(is_active=True).select_related(
        "board", "in_review_column"
    ):
        expected_sig = hmac.new(
            integration.webhook_secret.encode("utf-8"),
            raw_body,
            hashlib.sha256,
        ).hexdigest()
        if hmac.compare_digest(expected_sig, received_sig):
            matched_integration = integration
            break

    if matched_integration is None:
        # Unknown source or invalid signature — silently accept to avoid
        # leaking information about which integrations exist.
        return JsonResponse({"status": "ok"}, status=200)

    # ------------------------------------------------------------------
    # 2. Parse the event type.
    # ------------------------------------------------------------------
    event_type = request.META.get("HTTP_X_GITHUB_EVENT", "")
    if event_type != "pull_request":
        # Not a PR event — ignore gracefully (e.g. ping events on setup).
        return JsonResponse({"status": "ignored", "reason": f"event '{event_type}' not handled"})

    try:
        payload = json.loads(raw_body)
    except json.JSONDecodeError:
        return JsonResponse({"error": "Invalid JSON payload."}, status=400)

    action = payload.get("action", "")
    # Only react to PR open / sync / ready-for-review transitions.
    if action not in ("opened", "synchronize", "ready_for_review"):
        return JsonResponse({"status": "ignored", "reason": f"PR action '{action}' not handled"})

    pr = payload.get("pull_request", {})
    pr_title = pr.get("title", "")
    pr_body = pr.get("body") or ""

    # ------------------------------------------------------------------
    # 3. Extract task IDs from PR title + body.
    #    Pattern: one or more uppercase letters, a dash, one or more digits.
    #    e.g. "SD-101", "PROJ-999"
    # ------------------------------------------------------------------
    candidate_ids = re.findall(r"\b([A-Z]+-\d+)\b", pr_title + " " + pr_body)
    if not candidate_ids:
        return JsonResponse({"status": "ok", "updated": 0})

    board = matched_integration.board
    target_column = matched_integration.in_review_column
    if not target_column:
        return JsonResponse({"status": "ok", "updated": 0, "reason": "no in_review_column configured"})

    # Board's task prefix (e.g. "SD")
    board_prefix = (board.task_prefix or "").upper()

    updated_count = 0
    for task_ref in set(candidate_ids):
        parts = task_ref.split("-", 1)
        if len(parts) != 2:
            continue
        prefix, num_str = parts
        if board_prefix and prefix.upper() != board_prefix:
            # Silently ignore IDs that don't belong to this board's prefix.
            continue
        try:
            task_num = int(num_str)
        except ValueError:
            continue

        # Match by sequential id within this board.
        task = Task.objects.filter(
            id=task_num,
            column__board=board,
            item_type="task",
        ).first()
        if task and task.column_id != target_column.id:
            task.column = target_column
            task.save(update_fields=["column", "updated_at"])
            updated_count += 1

    return JsonResponse({"status": "ok", "updated": updated_count})


# ---------------------------------------------------------------------------
# Board Settings: GitHub Integration UI (requires login + board access)
# ---------------------------------------------------------------------------

@login_required
def github_integration_settings(request, board_id):
    """
    Board settings page for GitHub integration.
    Shows the PrizmAI webhook endpoint URL to copy into GitHub.
    """
    board = get_object_or_404(Board, id=board_id)
    if not request.user.has_perm("prizmai.edit_board", board):
        from django.http import Http404
        raise Http404

    integration = GitHubIntegration.objects.filter(board=board).first()

    if request.method == "POST":
        action = request.POST.get("action")

        if action == "save":
            form = GitHubIntegrationForm(request.POST, instance=integration, board=board)
            if form.is_valid():
                obj = form.save(commit=False)
                obj.board = board
                obj.created_by = request.user
                obj.save()
                messages.success(request, "GitHub integration saved.")
                return redirect("integrations:github_settings", board_id=board.id)

        elif action == "regenerate_secret":
            if integration:
                import secrets as _secrets
                integration.webhook_secret = _secrets.token_hex()
                integration.save(update_fields=["webhook_secret", "updated_at"])
                messages.success(request, "Webhook secret regenerated.")
            return redirect("integrations:github_settings", board_id=board.id)

        elif action == "delete":
            if integration:
                integration.delete()
                messages.success(request, "GitHub integration removed.")
            return redirect("integrations:github_settings", board_id=board.id)

        else:
            form = GitHubIntegrationForm(request.POST, instance=integration, board=board)
    else:
        form = GitHubIntegrationForm(instance=integration, board=board)

    # Build the absolute receiver URL for display.
    receiver_url = request.build_absolute_uri("/api/integrations/github/")

    return render(request, "integrations/github_settings.html", {
        "board": board,
        "integration": integration,
        "form": form,
        "receiver_url": receiver_url,
    })


# ---------------------------------------------------------------------------
# Live Migration: import a whole project from another PM tool via its API
# ---------------------------------------------------------------------------

# Per-provider UI metadata: credential fields, where to get a token, and a short
# "what to expect" list shown as a banner when the tool is selected.
_PROVIDER_HELP = {
    "jira": {
        "label": "Jira",
        "needs_site": True,
        "needs_email": True,
        "site_hint": "https://your-team.atlassian.net",
        "token_url": "https://id.atlassian.com/manage-profile/security/api-tokens",
        "expectations": [
            "Each Jira <strong>Epic</strong> becomes its own <strong>Board</strong>; issues with no epic go to a “General” board.",
            "Issues become <strong>Tasks</strong>, and each status becomes a column.",
            "Priority, labels, assignees, due dates and story points are carried across.",
            "The Epic card itself is not duplicated as a task.",
            "An <strong>AI audit</strong> runs automatically the moment your project lands.",
        ],
    },
    "asana": {
        "label": "Asana",
        "needs_site": False,
        "needs_email": False,
        "token_url": "https://app.asana.com/0/my-apps",
        "expectations": [
            "Your Asana <strong>project</strong> becomes one <strong>Board</strong> under a new Strategy.",
            "Each <strong>section</strong> becomes a column; tasks become <strong>Tasks</strong>.",
            "Assignees, due dates, tags and completion status are carried across.",
            "An <strong>AI audit</strong> runs automatically the moment your project lands.",
        ],
    },
    "monday": {
        "label": "Monday.com",
        "needs_site": False,
        "needs_email": False,
        "token_url": "https://monday.com/developers/v2/try-it-yourself",
        "expectations": [
            "Your Monday <strong>board</strong> becomes one <strong>Board</strong> under a new Strategy.",
            "Each <strong>group</strong> becomes a column; items become <strong>Tasks</strong>.",
            "Status, owner, due date and labels are carried across.",
            "An <strong>AI audit</strong> runs automatically the moment your project lands.",
        ],
    },
}


def _resolve_workspace(user):
    """User's active workspace (never the demo one), creating a real one if needed."""
    ws = None
    try:
        ws = user.profile.active_workspace
        if ws and ws.is_demo:
            ws = None
    except Exception:
        ws = None
    if not ws:
        from kanban.workspace_utils import get_or_create_real_workspace
        ws = get_or_create_real_workspace(user)
    return ws


@login_required
def migration_start(request):
    """Landing page for the 'Migrate from another tool' onboarding wizard."""
    from kanban.utils.connectors import ConnectorFactory

    supported = set(ConnectorFactory.supported_providers())
    providers = [
        {"id": pid, **meta, "supported": pid in supported}
        for pid, meta in _PROVIDER_HELP.items()
    ]
    # Show not-yet-live tools too, marked "coming soon", so the UI is honest.
    for pid, disp in SourceConnection.PROVIDER_CHOICES:
        if pid not in _PROVIDER_HELP:
            providers.append({"id": pid, "label": disp, "supported": False})

    return render(request, "integrations/migrate_start.html", {"providers": providers})


@login_required
@require_POST
def migration_connect(request):
    """
    AJAX: save + validate credentials, then return the project list.

    Persists (or updates) a workspace-scoped SourceConnection with the token
    encrypted, tests the credentials, and returns selectable projects.
    """
    from kanban.utils.connectors import ConnectorFactory, ConnectorError

    provider = (request.POST.get("provider") or "").strip().lower()
    base_url = (request.POST.get("base_url") or "").strip()
    account_email = (request.POST.get("account_email") or "").strip()
    api_token = request.POST.get("api_token") or ""

    if not ConnectorFactory.is_supported(provider):
        return JsonResponse({"ok": False, "error": f"'{provider}' is not available yet."}, status=400)
    if not api_token.strip():
        return JsonResponse({"ok": False, "error": "An API token is required."}, status=400)

    ws = _resolve_workspace(request.user)
    # Block writing into the demo workspace.
    if getattr(ws, "is_demo", False):
        return JsonResponse({"ok": False, "error": "Migration is disabled in the demo workspace."}, status=403)

    connection, _ = SourceConnection.objects.update_or_create(
        workspace=ws, created_by=request.user, provider=provider,
        defaults={
            "base_url": base_url,
            "account_email": account_email,
            "status": SourceConnection.STATUS_CONNECTED,
            "is_active": True,
        },
    )
    connection.set_token(api_token)  # encrypts; raw token never stored/logged
    connection.save()

    connector = ConnectorFactory.get_connector(provider, connection)
    try:
        account = connector.test_connection()
        projects = connector.list_projects()
    except ConnectorError as exc:
        connection.status = SourceConnection.STATUS_ERROR
        connection.save(update_fields=["status"])
        return JsonResponse({"ok": False, "error": exc.message}, status=400)

    return JsonResponse({
        "ok": True,
        "connection_id": connection.id,
        "account": account.get("account"),
        "projects": projects,
    })


@login_required
@require_POST
def migration_run(request):
    """AJAX: enqueue the migration Celery task; return its task id for polling."""
    connection_id = request.POST.get("connection_id")
    project_id = (request.POST.get("project_id") or "").strip()
    project_name = (request.POST.get("project_name") or "").strip() or project_id

    connection = get_object_or_404(SourceConnection, id=connection_id)
    # Ownership + tenant scoping: only the creator may run their connection.
    if connection.created_by_id != request.user.id:
        from django.http import Http404
        raise Http404
    if getattr(connection.workspace, "is_demo", False):
        return JsonResponse({"ok": False, "error": "Migration is disabled in the demo workspace."}, status=403)
    if not project_id:
        return JsonResponse({"ok": False, "error": "Pick a project to migrate."}, status=400)

    from kanban.tasks.migration_tasks import run_source_migration
    # Enqueue with an explicit queue so it reliably reaches the dedicated
    # 'interactive' worker regardless of task_routes precedence (this project's
    # effective routes come from settings.CELERY_TASK_ROUTES).
    async_result = run_source_migration.apply_async(
        args=[connection.id, project_id, project_name], queue="interactive"
    )
    return JsonResponse({"ok": True, "task_id": async_result.id})


@login_required
def migration_status(request, task_id):
    """AJAX: poll live migration progress.

    Reads the cache-based progress channel, then reconciles against Celery's
    result backend (shared Redis) so the terminal done/error transition is
    always detected even if a progress tick didn't propagate through the cache.
    """
    from kanban.utils.connectors.migration_progress import get_progress

    data = dict(get_progress(task_id))

    try:
        from kanban_board.celery import app
        res = app.AsyncResult(task_id)
        if res.successful():
            payload = res.result if isinstance(res.result, dict) else {}
            if payload.get("state") == "done":
                data["state"] = "done"
                data["percent"] = 100
                data.setdefault("message", "Migration complete!")
                data["strategy_id"] = payload.get("strategy_id")
                if payload.get("redirect_url"):
                    data["redirect_url"] = payload["redirect_url"]
        elif res.failed():
            data["state"] = "error"
            if not data.get("message") or data.get("state") == "pending":
                data["message"] = "Migration failed. Please try again."
    except Exception:
        pass

    return JsonResponse(data)
