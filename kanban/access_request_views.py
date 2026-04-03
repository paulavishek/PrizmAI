"""
Spectra Access Request Views

Handles the access request workflow:
- User sends a request (triggered by Spectra denial UX)
- Owner reviews and approves/denies via in-app notification
- User is notified of the outcome
"""
import json
import logging

from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, render, redirect
from django.views.decorators.http import require_http_methods, require_POST

from kanban.permissions import is_user_org_admin

from kanban.models import Board, BoardMembership
from kanban.access_request_models import AccessRequest
from kanban.decorators import demo_write_guard

logger = logging.getLogger(__name__)


# ============================================================================
# USER-FACING: Submit an access request
# ============================================================================

@login_required
@demo_write_guard
@require_POST
def submit_access_request(request):
    """
    Submit an access request to a board owner.
    Called from the Spectra denial UX (AJAX).
    """
    try:
        data = json.loads(request.body)
    except (json.JSONDecodeError, ValueError):
        return JsonResponse({'error': 'Invalid JSON'}, status=400)

    board_id = data.get('board_id')
    message = data.get('message', '').strip()
    trigger = data.get('trigger', 'board_view')
    requested_role = data.get('requested_role', 'member')

    if not board_id:
        return JsonResponse({'error': 'board_id is required'}, status=400)

    board = get_object_or_404(Board, id=board_id)

    # Don't allow requests if user already has access
    from kanban.simple_access import can_access_board
    if can_access_board(request.user, board):
        return JsonResponse({
            'error': 'You already have access to this board.',
        }, status=400)

    # Validate trigger
    valid_triggers = dict(AccessRequest.TRIGGER_CHOICES).keys()
    if trigger not in valid_triggers:
        trigger = 'board_view'

    # Validate role
    if requested_role not in ('viewer', 'member'):
        requested_role = 'member'

    # Create the request and notify the owner
    access_request = AccessRequest.create_and_notify_owner(
        requester=request.user,
        board=board,
        trigger=trigger,
        message=message,
        spectra_context=f"User attempted {trigger} on board '{board.name}'",
        requested_role=requested_role,
    )

    if access_request is None:
        return JsonResponse({
            'error': 'Unable to create access request. The board may not have an owner.',
        }, status=400)

    already_pending = access_request.created_at != access_request.created_at  # always False
    # Detect if it was a pre-existing request (returned by has_pending)
    is_existing = AccessRequest.objects.filter(
        requester=request.user, board=board, status='pending'
    ).count() > 0

    owner_name = (
        access_request.owner.get_full_name()
        or access_request.owner.username
    )

    return JsonResponse({
        'success': True,
        'request_id': access_request.id,
        'spectra_message': (
            f"Done! I've sent an access request to **{owner_name}**. "
            f"They'll receive a notification and can approve your request "
            f"from their dashboard. I'll let you know as soon as they respond!"
        ),
    })


# ============================================================================
# USER-FACING: View my sent access requests
# ============================================================================

@login_required
def my_access_requests(request):
    """View access requests sent by the current user."""
    requests_list = AccessRequest.objects.filter(
        requester=request.user
    ).select_related('board', 'owner', 'resolved_by').order_by('-created_at')

    return render(request, 'kanban/my_access_requests.html', {
        'access_requests': requests_list,
    })


@login_required
@demo_write_guard
@require_POST
def cancel_access_request(request, request_id):
    """Cancel a pending access request."""
    access_request = get_object_or_404(
        AccessRequest, id=request_id, requester=request.user, status='pending'
    )
    access_request.cancel()

    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        return JsonResponse({'success': True})

    return redirect('my_access_requests')


# ============================================================================
# OWNER-FACING: Review access requests
# ============================================================================

@login_required
def review_access_request(request, request_id):
    """
    Page where the board owner reviews an access request.
    Supports both GET (view) and POST (approve/deny).
    """
    access_request = get_object_or_404(
        AccessRequest.objects.select_related('requester', 'board', 'owner'),
        id=request_id,
    )

    # Only the board owner (or OrgAdmin/superuser) can review
    is_authorized = (
        request.user == access_request.owner
        or request.user.is_superuser
        or is_user_org_admin(request.user)
    )
    if not is_authorized:
        return JsonResponse({'error': 'Not authorized'}, status=403)

    if request.method == 'GET':
        return render(request, 'kanban/review_access_request.html', {
            'access_request': access_request,
        })

    # POST — approve or deny
    action = request.POST.get('action', '')
    reviewer_message = request.POST.get('reviewer_message', '').strip()

    if access_request.status != 'pending':
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return JsonResponse({
                'error': f'This request has already been {access_request.status}.',
            }, status=400)
        return redirect('review_access_request', request_id=request_id)

    if action == 'approve':
        role = request.POST.get('role', access_request.requested_role)
        if role not in ('viewer', 'member', 'owner'):
            role = 'member'
        access_request.approve(
            reviewer=request.user, role=role, message=reviewer_message,
        )
    elif action == 'deny':
        access_request.deny(
            reviewer=request.user, message=reviewer_message,
        )
    else:
        return JsonResponse({'error': 'Invalid action'}, status=400)

    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        return JsonResponse({
            'success': True,
            'status': access_request.status,
        })

    return redirect('pending_access_requests')


@login_required
def pending_access_requests(request):
    """
    Dashboard view showing all pending access requests for boards
    the current user owns.
    """
    pending = AccessRequest.objects.filter(
        owner=request.user, status='pending'
    ).select_related('requester', 'board').order_by('-created_at')

    resolved = AccessRequest.objects.filter(
        owner=request.user
    ).exclude(status='pending').select_related(
        'requester', 'board', 'resolved_by'
    ).order_by('-resolved_at')[:20]

    return render(request, 'kanban/pending_access_requests.html', {
        'pending_requests': pending,
        'resolved_requests': resolved,
    })


# ============================================================================
# API: Approve / Deny via AJAX (for notification inline actions)
# ============================================================================

@login_required
@demo_write_guard
@require_POST
def api_approve_access_request(request, request_id):
    """AJAX endpoint: approve an access request."""
    access_request = get_object_or_404(
        AccessRequest.objects.select_related('requester', 'board', 'owner'),
        id=request_id,
    )

    is_authorized = (
        request.user == access_request.owner
        or request.user.is_superuser
        or is_user_org_admin(request.user)
    )
    if not is_authorized:
        return JsonResponse({'error': 'Not authorized'}, status=403)

    if access_request.status != 'pending':
        return JsonResponse({
            'error': f'Request already {access_request.status}.',
        }, status=400)

    try:
        data = json.loads(request.body) if request.body else {}
    except (json.JSONDecodeError, ValueError):
        data = {}

    role = data.get('role', access_request.requested_role)
    message = data.get('message', '')
    if role not in ('viewer', 'member', 'owner'):
        role = 'member'

    access_request.approve(reviewer=request.user, role=role, message=message)

    return JsonResponse({
        'success': True,
        'status': 'approved',
        'spectra_message': (
            f"{access_request.requester.get_full_name() or access_request.requester.username} "
            f"now has {role} access to '{access_request.board.name}'."
        ),
    })


@login_required
@demo_write_guard
@require_POST
def api_deny_access_request(request, request_id):
    """AJAX endpoint: deny an access request."""
    access_request = get_object_or_404(
        AccessRequest.objects.select_related('requester', 'board', 'owner'),
        id=request_id,
    )

    is_authorized = (
        request.user == access_request.owner
        or request.user.is_superuser
        or is_user_org_admin(request.user)
    )
    if not is_authorized:
        return JsonResponse({'error': 'Not authorized'}, status=403)

    if access_request.status != 'pending':
        return JsonResponse({
            'error': f'Request already {access_request.status}.',
        }, status=400)

    try:
        data = json.loads(request.body) if request.body else {}
    except (json.JSONDecodeError, ValueError):
        data = {}

    message = data.get('message', '')
    access_request.deny(reviewer=request.user, message=message)

    return JsonResponse({
        'success': True,
        'status': 'denied',
    })


# ============================================================================
# API: Pending access request count (polled by notification bell)
# ============================================================================

@login_required
def get_pending_access_request_count(request):
    """Return the count of pending access requests where current user is the owner."""
    count = AccessRequest.objects.filter(
        owner=request.user, status='pending'
    ).count()
    return JsonResponse({'count': count})
