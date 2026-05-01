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
from integrations.models import GitHubIntegration
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
