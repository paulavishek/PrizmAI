"""
Board invitation views — email-based invite-to-board flow.
"""
import logging

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.mail import send_mail
from django.shortcuts import get_object_or_404, redirect, render
from django.template.loader import render_to_string
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.http import require_POST

from .models import Board, BoardInvitation
from accounts.models import UserProfile

logger = logging.getLogger(__name__)

SESSION_INVITE_KEY = 'pending_board_invite_token'


# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────

def _can_manage_invites(user, board):
    """Return True if user may send/revoke invites for this board."""
    return board.created_by == user or getattr(getattr(user, 'profile', None), 'is_admin', False)


def _send_invitation_email(request, invitation):
    """Send the invitation email (console in dev, SMTP in prod)."""
    accept_url = request.build_absolute_uri(
        reverse('accept_board_invitation', args=[invitation.token])
    )
    context = {
        'invitation': invitation,
        'board': invitation.board,
        'invited_by': invitation.invited_by,
        'accept_url': accept_url,
        'expires_hours': 48,
    }
    subject = f"You're invited to join '{invitation.board.name}' on PrizmAI"
    body_text = render_to_string('kanban/email/board_invitation.txt', context)
    body_html = render_to_string('kanban/email/board_invitation.html', context)

    try:
        send_mail(
            subject=subject,
            message=body_text,
            from_email=None,   # uses DEFAULT_FROM_EMAIL from settings
            recipient_list=[invitation.email],
            html_message=body_html,
            fail_silently=False,
        )
        logger.info(
            "Board invitation email sent to %s for board %s",
            invitation.email, invitation.board.id
        )
        return True
    except Exception as exc:
        logger.error("Failed to send invitation email: %s", exc)
        return False


# ─────────────────────────────────────────────────────────────────────────────
# Views
# ─────────────────────────────────────────────────────────────────────────────

@login_required
@require_POST
def invite_to_board(request, board_id):
    """Send an email invitation to join a board."""
    board = get_object_or_404(Board, id=board_id)

    if not _can_manage_invites(request.user, board):
        messages.error(request, "You don't have permission to invite members to this board.")
        return redirect('manage_board_members', board_id=board.id)

    email = request.POST.get('invite_email', '').strip().lower()
    if not email:
        messages.error(request, "Please enter an email address.")
        return redirect('manage_board_members', board_id=board.id)

    # Check if email already belongs to a current board member
    if board.members.filter(email__iexact=email).exists():
        messages.info(request, f"{email} is already a member of this board.")
        return redirect('manage_board_members', board_id=board.id)

    # Cancel any previous pending invite for this email + board
    BoardInvitation.objects.filter(
        board=board, email=email, status=BoardInvitation.STATUS_PENDING
    ).update(status=BoardInvitation.STATUS_REVOKED)

    # Create a fresh invitation
    invitation = BoardInvitation.objects.create(
        board=board,
        invited_by=request.user,
        email=email,
    )

    sent = _send_invitation_email(request, invitation)
    if sent:
        messages.success(
            request,
            f"Invitation sent to {email}. The link will expire in 48 hours."
        )
    else:
        messages.warning(
            request,
            f"Invitation created for {email} but the email could not be delivered. "
            "Check your email settings."
        )

    return redirect('manage_board_members', board_id=board.id)


def accept_invitation(request, token):
    """
    Accept a board invitation via its token.

    • If the user is already logged in  → adds them to the board immediately.
    • If not logged in                  → stores token in session, redirects to
                                          login. After login the token is read
                                          from session and this view is called
                                          again automatically.
    """
    invitation = get_object_or_404(BoardInvitation, token=token)

    # Validate the invitation before anything else
    if not invitation.is_valid():
        status_label = invitation.get_status_display()
        return render(request, 'kanban/invitation_invalid.html', {
            'reason': status_label,
            'board': invitation.board,
        })

    if not request.user.is_authenticated:
        # Save the token so login / register can pick it up
        request.session[SESSION_INVITE_KEY] = str(token)
        messages.info(
            request,
            f"Please sign in (or create an account) to join '{invitation.board.name}'."
        )
        return redirect(f"{reverse('login')}?next={reverse('accept_board_invitation', args=[token])}")

    # ── User is authenticated ────────────────────────────────────────────────
    user = request.user

    # Ensure the user has a profile (MVP auto-create)
    try:
        profile = user.profile
    except UserProfile.DoesNotExist:
        UserProfile.objects.create(user=user, organization=None, is_admin=False, completed_wizard=True)

    board = invitation.board

    if user in board.members.all():
        messages.info(request, f"You are already a member of '{board.name}'.")
        invitation.mark_accepted(user)
        return redirect('board_detail', board_id=board.id)

    # Add member and finalise invite
    board.members.add(user)
    invitation.mark_accepted(user)

    # Clear session key if it was set
    request.session.pop(SESSION_INVITE_KEY, None)

    messages.success(request, f"Welcome! You have joined '{board.name}'.")
    logger.info("User %s accepted invitation to board %s", user.username, board.id)
    return redirect('board_detail', board_id=board.id)


@login_required
@require_POST
def revoke_invitation(request, invitation_id):
    """Revoke a pending invitation."""
    invitation = get_object_or_404(BoardInvitation, id=invitation_id)

    if not _can_manage_invites(request.user, invitation.board):
        messages.error(request, "You don't have permission to revoke this invitation.")
        return redirect('manage_board_members', board_id=invitation.board.id)

    if invitation.status != BoardInvitation.STATUS_PENDING:
        messages.warning(request, "This invitation is no longer pending.")
    else:
        invitation.status = BoardInvitation.STATUS_REVOKED
        invitation.save(update_fields=['status'])
        messages.success(request, f"Invitation for {invitation.email} has been revoked.")

    return redirect('manage_board_members', board_id=invitation.board.id)
