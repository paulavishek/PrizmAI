"""
Workspace-level member management views.

Provides UI for adding/removing members at the workspace level,
with automatic propagation to all boards in the workspace.
"""
import re
import logging

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from django.core.mail import send_mail
from django.http import Http404
from django.shortcuts import get_object_or_404, redirect, render
from django.template.loader import render_to_string
from django.urls import reverse

from accounts.models import UserProfile
from kanban.models import (
    WorkspaceInvitation,
    WorkspaceMembership,
)
from kanban.permissions import is_user_org_admin
from kanban.workspace_member_utils import (
    add_workspace_member,
    remove_workspace_member,
    update_workspace_member_role,
)

logger = logging.getLogger(__name__)


def _can_manage_workspace(request):
    """Return (workspace, True) if the user can manage workspace members, else raise Http404."""
    ws = getattr(request, 'workspace', None)
    if not ws or ws.is_demo:
        raise Http404

    if is_user_org_admin(request.user) or ws.created_by_id == request.user.pk:
        return ws

    raise Http404


@login_required
def manage_workspace_members(request):
    """GET /workspace/members/ — list workspace members + pending invitations."""
    ws = _can_manage_workspace(request)

    memberships = WorkspaceMembership.objects.filter(
        workspace=ws,
    ).select_related('user', 'added_by').order_by('-added_at')

    pending_invitations = WorkspaceInvitation.objects.filter(
        workspace=ws, status=WorkspaceInvitation.STATUS_PENDING,
    ).order_by('-created_at')

    # Org users not yet in this workspace (for the "add existing member" dropdown)
    existing_member_ids = memberships.values_list('user_id', flat=True)
    org = ws.organization
    org_users = User.objects.filter(
        profile__organization=org,
    ).exclude(
        id__in=existing_member_ids,
    ).order_by('first_name', 'username')

    return render(request, 'kanban/manage_workspace_members.html', {
        'workspace': ws,
        'memberships': memberships,
        'pending_invitations': pending_invitations,
        'org_users': org_users,
        'can_manage': True,
    })


@login_required
def add_workspace_member_view(request):
    """POST /workspace/members/add/ — add an existing org user or send email invite."""
    ws = _can_manage_workspace(request)
    if request.method != 'POST':
        return redirect('manage_workspace_members')

    role = request.POST.get('role', 'member')
    if role not in ('owner', 'member', 'viewer'):
        role = 'member'

    # Path 1: Add existing org user by user_id
    user_id = request.POST.get('user_id')
    if user_id:
        try:
            target_user = User.objects.get(pk=user_id)
        except User.DoesNotExist:
            messages.error(request, 'User not found.')
            return redirect('manage_workspace_members')

        add_workspace_member(ws, target_user, role, added_by=request.user)
        messages.success(
            request,
            f'{target_user.get_full_name() or target_user.username} added as {role}.',
        )
        return redirect('manage_workspace_members')

    # Path 2: Email invite for external / non-org users
    raw_emails = request.POST.get('invite_emails', '').strip()
    if not raw_emails:
        messages.warning(request, 'Please select a user or enter an email address.')
        return redirect('manage_workspace_members')

    emails = list(dict.fromkeys(
        e.strip().lower() for e in re.split(r'[,;\n]+', raw_emails) if e.strip()
    ))

    sent, skipped = [], []
    for email in emails:
        if not re.match(r'^[^@\s]+@[^@\s]+\.[^@\s]+$', email):
            skipped.append(f'{email} (invalid)')
            continue

        # Already a workspace member?
        if WorkspaceMembership.objects.filter(
            workspace=ws, user__email__iexact=email,
        ).exists():
            skipped.append(f'{email} (already a member)')
            continue

        # Revoke previous pending invites for same email + workspace
        WorkspaceInvitation.objects.filter(
            workspace=ws, email=email,
            status=WorkspaceInvitation.STATUS_PENDING,
        ).update(status=WorkspaceInvitation.STATUS_REVOKED)

        invitation = WorkspaceInvitation.objects.create(
            workspace=ws,
            invited_by=request.user,
            email=email,
            role=role,
        )
        _send_workspace_invitation_email(request, invitation)
        sent.append(email)

    if sent:
        messages.success(request, f'Invitation{"s" if len(sent) > 1 else ""} sent to {", ".join(sent)}.')
    for note in skipped:
        messages.info(request, f'Skipped: {note}')

    return redirect('manage_workspace_members')


@login_required
def remove_workspace_member_view(request, user_id):
    """POST /workspace/members/<user_id>/remove/"""
    ws = _can_manage_workspace(request)
    if request.method != 'POST':
        return redirect('manage_workspace_members')

    target_user = get_object_or_404(User, pk=user_id)

    try:
        remove_workspace_member(ws, target_user)
        messages.success(
            request,
            f'{target_user.get_full_name() or target_user.username} removed from workspace.',
        )
    except ValueError as e:
        messages.error(request, str(e))

    return redirect('manage_workspace_members')


@login_required
def update_workspace_member_role_view(request, user_id):
    """POST /workspace/members/<user_id>/role/"""
    ws = _can_manage_workspace(request)
    if request.method != 'POST':
        return redirect('manage_workspace_members')

    new_role = request.POST.get('role', 'member')
    if new_role not in ('owner', 'member', 'viewer'):
        new_role = 'member'

    target_user = get_object_or_404(User, pk=user_id)

    try:
        update_workspace_member_role(ws, target_user, new_role)
        messages.success(
            request,
            f'{target_user.get_full_name() or target_user.username} role updated to {new_role}.',
        )
    except WorkspaceMembership.DoesNotExist:
        messages.error(request, 'User is not a workspace member.')

    return redirect('manage_workspace_members')


@login_required
def revoke_workspace_invitation_view(request, invitation_id):
    """POST /workspace/invitations/<id>/revoke/"""
    ws = _can_manage_workspace(request)
    if request.method != 'POST':
        return redirect('manage_workspace_members')

    invitation = get_object_or_404(
        WorkspaceInvitation, pk=invitation_id, workspace=ws,
    )
    invitation.status = WorkspaceInvitation.STATUS_REVOKED
    invitation.save(update_fields=['status'])
    messages.success(request, f'Invitation to {invitation.email} revoked.')
    return redirect('manage_workspace_members')


@login_required
def accept_workspace_invitation(request, token):
    """
    GET /workspace/invite/<token>/ — accept a workspace invitation.

    If the user is not logged in, redirect to login with next= param.
    On acceptance: link user to org → create WorkspaceMembership → sync boards.
    """
    invitation = get_object_or_404(WorkspaceInvitation, token=token)

    if not invitation.is_valid():
        return render(request, 'accounts/org_invitation_invalid.html', {
            'reason': invitation.get_status_display(),
            'organization': invitation.workspace.organization,
        })

    if not request.user.is_authenticated:
        request.session['ws_invite_token'] = str(token)
        messages.info(request, f"Please sign in to join '{invitation.workspace.name}'.")
        login_url = reverse('login')
        accept_url = reverse('accept_workspace_invitation', args=[token])
        return redirect(f'{login_url}?next={accept_url}')

    user = request.user

    # Ensure profile exists
    try:
        profile = user.profile
    except UserProfile.DoesNotExist:
        profile = UserProfile.objects.create(
            user=user, organization=None, is_admin=False,
            completed_wizard=True, has_seen_welcome=True,
            onboarding_version=2, onboarding_status='pending',
        )

    # Link user to the organization if needed
    org = invitation.workspace.organization
    if not profile.organization or profile.organization != org:
        profile.organization = org
        profile.save(update_fields=['organization'])

    # Set active workspace if user doesn't have one
    if not profile.active_workspace:
        profile.active_workspace = invitation.workspace
        profile.save(update_fields=['active_workspace'])

    # Create workspace membership (which also syncs to all boards)
    add_workspace_member(
        invitation.workspace,
        user,
        invitation.role,
        added_by=invitation.invited_by,
    )

    invitation.mark_accepted(user)
    request.session.pop('ws_invite_token', None)

    messages.success(request, f"Welcome! You've joined '{invitation.workspace.name}'.")
    return redirect('dashboard')


def _send_workspace_invitation_email(request, invitation):
    """Send a workspace invitation email."""
    accept_url = request.build_absolute_uri(
        reverse('accept_workspace_invitation', args=[invitation.token])
    )
    context = {
        'invitation': invitation,
        'organization': invitation.workspace.organization,
        'workspace': invitation.workspace,
        'invited_by': invitation.invited_by,
        'accept_url': accept_url,
        'expires_hours': 48,
    }
    subject = f"You're invited to join '{invitation.workspace.name}' on PrizmAI"
    body_text = render_to_string('kanban/email/workspace_invitation.txt', context)
    body_html = render_to_string('kanban/email/workspace_invitation.html', context)

    try:
        send_mail(
            subject=subject,
            message=body_text,
            from_email=None,
            recipient_list=[invitation.email],
            html_message=body_html,
            fail_silently=False,
        )
    except Exception:
        logger.exception('Failed to send workspace invitation email to %s', invitation.email)
