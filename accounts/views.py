from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import login, authenticate, logout, get_user_model
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.contrib.auth.models import User
from django.contrib.auth.views import PasswordResetView
from django.http import JsonResponse
from django.views.decorators.http import require_POST
from .forms import LoginForm, RegistrationForm, UserProfileForm
from .models import Organization, UserProfile, OrganizationInvitation, COMMON_TIMEZONES
import json
import logging

logger = logging.getLogger(__name__)


class CustomPasswordResetView(PasswordResetView):
    """Override PasswordResetView to handle OAuth-only accounts gracefully.

    Django's default silently skips users with no usable password, showing the
    success page anyway. This gives a clear, actionable message instead.
    """
    template_name = 'accounts/password_reset.html'
    email_template_name = 'accounts/password_reset_email.html'
    subject_template_name = 'accounts/password_reset_subject.txt'
    success_url = '/accounts/password-reset/done/'

    def form_valid(self, form):
        email = form.cleaned_data.get('email')
        UserModel = get_user_model()
        users = UserModel.objects.filter(email__iexact=email, is_active=True)
        if users.exists() and all(not u.has_usable_password() for u in users):
            form.add_error(
                'email',
                'This account was created with Google sign-in and does not have a password. '
                'Please use the "Continue with Google" button on the login page.'
            )
            return self.form_invalid(form)
        return super().form_valid(form)


def _resolve_post_login_redirect(user):
    """Determine where to send a user after login based on workspace state.

    Returns a URL string:
      - '/workspace-selection/' if user has 2+ real workspaces
      - '/dashboard/' otherwise (0 or 1 real workspaces)

    Side-effect: when there are 0 real workspaces we ensure the active
    workspace is set to the demo workspace. When there is exactly 1 real
    workspace we ensure it's selected as active.
    """
    try:
        profile = user.profile
    except UserProfile.DoesNotExist:
        return '/dashboard/'

    org = profile.organization
    if not org:
        return '/dashboard/'

    from kanban.models import Workspace

    real_ws = list(
        Workspace.objects.filter(
            organization=org, is_active=True, is_demo=False,
        ).order_by('-updated_at')
    )
    demo_ws = Workspace.objects.filter(
        organization=org, is_active=True, is_demo=True,
    ).first()

    if len(real_ws) == 0:
        # No personal workspaces — land on demo
        if demo_ws and profile.active_workspace_id != demo_ws.pk:
            profile.active_workspace = demo_ws
            profile.is_viewing_demo = True
            profile.save(update_fields=['active_workspace', 'is_viewing_demo'])
        return '/dashboard/'

    if len(real_ws) == 1:
        # Exactly one — go straight there
        ws = real_ws[0]
        if profile.active_workspace_id != ws.pk or profile.is_viewing_demo:
            profile.active_workspace = ws
            profile.is_viewing_demo = False
            profile.save(update_fields=['active_workspace', 'is_viewing_demo'])
        return '/dashboard/'

    # 2+ real workspaces — show the selection page
    return '/workspace-selection/'


def quick_demo_login(request, username):
    """
    Quick login for demo users with pre-set credentials.
    Allows one-click login from the dashboard.
    Saves the real user's username in session so they can switch back.
    """
    # Only allow login for demo users
    demo_users = ['alex_chen_demo', 'sam_rivera_demo', 'jordan_taylor_demo']
    
    if username not in demo_users:
        messages.error(request, 'Invalid demo user.')
        return redirect('login')
    
    # Remember the real user before switching to demo
    real_username = None
    if request.user.is_authenticated and request.user.username not in demo_users:
        real_username = request.user.username

    # Authenticate with the known demo password
    user = authenticate(request=request, username=username, password='demo123')
    
    if user is not None:
        login(request, user)
        # Restore the real username into the new session so we can switch back
        if real_username:
            request.session['real_user_username'] = real_username
        # Ensure demo user's profile has is_viewing_demo=True so demo boards appear
        try:
            profile = user.profile
            if not profile.is_viewing_demo:
                profile.is_viewing_demo = True
                profile.save(update_fields=['is_viewing_demo'])
        except Exception:
            pass
        messages.success(request, f'Logged in as {user.get_full_name() or user.username}!')
        logger.info(f"Quick demo login successful for user: {username}")
        return redirect('dashboard')
    else:
        messages.error(request, 'Demo user not found or credentials invalid.')
        logger.warning(f"Quick demo login failed for user: {username}")
        return redirect('login')


@login_required
def return_to_real_account(request):
    """
    Switch back from a demo account to the real user account that initiated the demo session.
    """
    real_username = request.session.get('real_user_username')
    demo_users = ['alex_chen_demo', 'sam_rivera_demo', 'jordan_taylor_demo']

    if not real_username:
        messages.warning(request, 'No previous account found. Please log in.')
        return redirect('login')

    try:
        real_user = User.objects.get(username=real_username)
    except User.DoesNotExist:
        messages.error(request, 'Your original account could not be found. Please log in.')
        return redirect('login')

    # Log out of demo account and log back in as the real user
    # Use the model backend directly (no password needed — we trust the session token)
    real_user.backend = 'django.contrib.auth.backends.ModelBackend'
    login(request, real_user)
    # Clear the real_user flag now that we're back
    request.session.pop('real_user_username', None)
    # Restore demo mode view for the real user (they were in demo before switching)
    try:
        profile = real_user.profile
        if not profile.is_viewing_demo:
            profile.is_viewing_demo = True
            profile.save(update_fields=['is_viewing_demo'])
    except Exception:
        pass
    messages.success(request, f'Welcome back, {real_user.get_full_name() or real_user.username}!')
    logger.info(f"Returned to real account: {real_username}")
    return redirect('dashboard')

def login_view(request):
    if request.user.is_authenticated:
        return redirect(_resolve_post_login_redirect(request.user))
    
    next_url = request.GET.get('next', '')

    if request.method == 'POST':
        form = LoginForm(request, data=request.POST)
        next_url = request.POST.get('next', next_url)
        if form.is_valid():
            username = form.cleaned_data.get('username')
            password = form.cleaned_data.get('password')
            user = authenticate(request=request, username=username, password=password)
            if user is not None:
                login(request, user)
                # Honour the ?next= redirect (e.g. invitation accept link)
                if next_url and next_url.startswith('/'):
                    return redirect(next_url)
                return redirect(_resolve_post_login_redirect(user))
    else:
        form = LoginForm()
    
    return render(request, 'accounts/login.html', {'form': form, 'next': next_url})

def logout_view(request):
    # Consume any pending messages so they don't leak into the next session
    # via Django's FallbackStorage cookie (which survives session.flush()).
    storage = messages.get_messages(request)
    for _ in storage:
        pass
    logout(request)
    return redirect('login')

def register_view(request, org_id=None):
    """
    Simplified registration - no organization assignment required.
    Organization field is now optional.
    """
    if request.user.is_authenticated:
        messages.info(
            request,
            f'You are already signed in as <strong>{request.user.username}</strong>. '
            'Please <a href="/accounts/logout/">log out</a> first if you want to create a new account.'
        )
        return redirect('dashboard')

    # org_id parameter is kept for backward compatibility but ignored

    if request.method == 'POST':
        form = RegistrationForm(request.POST)
        if form.is_valid():
            user = form.save()
            
            # Create user profile — v2 onboarding (AI-powered setup)
            UserProfile.objects.get_or_create(
                user=user,
                defaults={
                    'organization': None,
                    'is_admin': False,
                    'completed_wizard': True,
                    'has_seen_welcome': True,        # v2 uses new welcome screen
                    'onboarding_version': 2,
                    'onboarding_status': 'pending',  # will redirect to /onboarding/
                }
            )
            
            # v2 users access demo boards via the demo-mode toggle,
            # NOT via board membership — keeps their "My Boards" clean.
            
            messages.success(request, 'Registration successful! Please log in.')
            # If an invite token is waiting in the session, carry it forward
            from kanban.invitation_views import SESSION_INVITE_KEY
            pending_token = request.session.get(SESSION_INVITE_KEY)
            if pending_token:
                from django.urls import reverse
                next_url = reverse('accept_board_invitation', args=[pending_token])
                return redirect(f"{reverse('login')}?next={next_url}")
            return redirect('login')
    else:
        form = RegistrationForm()
    
    return render(request, 'accounts/register.html', {
        'form': form,
        'organization': None  # No organization choice needed
    })

@login_required
def organization_choice(request):
    """
    MVP Mode: Organization is optional - users don't need to be assigned.
    Auto-create profile if missing.
    """
    try:
        profile = request.user.profile
        # Organization is now optional - don't force assignment
        return redirect('dashboard')
    except UserProfile.DoesNotExist:
        # Auto-create profile without organization — v2 onboarding
        UserProfile.objects.create(
            user=request.user,
            organization=None,
            is_admin=False,
            completed_wizard=True,
            has_seen_welcome=True,
            onboarding_version=2,
            onboarding_status='pending',
        )
        messages.success(request, 'Welcome! Your profile has been created.')
        return redirect('dashboard')

@login_required
def join_organization(request):
    """
    MVP Mode: Redirect to dashboard since organization is not required.
    """
    messages.info(request, 'Organization features are not available in MVP mode.')
    return redirect('dashboard')

@login_required
def create_organization(request):
    """
    MVP Mode: Redirect to dashboard since organization is not required.
    """
    messages.info(request, 'Organization features are not available in MVP mode.')
    return redirect('dashboard')

@login_required
def profile_view(request):
    from accounts.forms import UserAISettingsForm
    from ai_assistant.models import UserAISettings, PROVIDER_CHOICES, OrganizationAISettings
    from ai_assistant.utils.ai_router import AIRouter
    from django.core.exceptions import ImproperlyConfigured
    from django.utils import timezone as tz
    from django.http import HttpResponseForbidden

    try:
        profile = request.user.profile
    except UserProfile.DoesNotExist:
        # MVP Mode: Auto-create profile without organization (v2 onboarding)
        profile = UserProfile.objects.create(
            user=request.user,
            organization=None,
            is_admin=False,
            completed_wizard=True,
            has_seen_welcome=True,
            onboarding_version=2,
            onboarding_status='pending',
        )

    # ------------------------------------------------------------------
    # AI context variables — computed once, used for GET and all re-renders
    # ------------------------------------------------------------------
    org = profile.organization
    allow_override = False
    org_provider = 'gemini'
    if org:
        try:
            org_ai = org.ai_settings
            allow_override = org_ai.allow_user_provider_override
            org_provider = org_ai.provider
        except OrganizationAISettings.DoesNotExist:
            pass

    show_provider_override = profile.is_admin or allow_override
    org_provider_display = dict(PROVIDER_CHOICES).get(org_provider, 'Google Gemini')

    user_ai = None
    try:
        user_ai = request.user.ai_settings
    except UserAISettings.DoesNotExist:
        pass

    # Always initialise both forms up front so they're always defined.
    # POST handlers may replace them with bound versions.
    profile_form = UserProfileForm(instance=profile)
    ai_settings_form = None  # built lazily below

    # ------------------------------------------------------------------
    # POST handler
    # ------------------------------------------------------------------
    if request.method == 'POST':
        form_type = request.POST.get('form_type', 'profile')

        if form_type == 'user_ai_settings':
            ai_settings_form = UserAISettingsForm(request.POST)
            if ai_settings_form.is_valid():
                cd = ai_settings_form.cleaned_data
                raw_key = cd.get('raw_api_key', '').strip()
                byok_prov = cd.get('byok_provider', '')
                remove_key = cd.get('remove_byok_key', False)
                provider_override_val = cd.get('provider_override', 'inherit')
                byok_model_val = (cd.get('byok_model') or '').strip() or None

                # RBAC: prevent API-level bypass of the org policy
                if (
                    provider_override_val != 'inherit'
                    and not profile.is_admin
                    and not allow_override
                ):
                    return HttpResponseForbidden()

                user_ai_obj, _ = UserAISettings.objects.get_or_create(user=request.user)
                user_ai_obj.provider_override = provider_override_val

                save_ok = True

                if remove_key:
                    user_ai_obj.encrypted_api_key = None
                    user_ai_obj.byok_provider = None
                    user_ai_obj.key_last_four = None
                    user_ai_obj.key_validated_at = None
                    user_ai_obj.byok_model = None

                elif raw_key:
                    router = AIRouter()
                    # If user entered a custom model name, validate it against
                    # the provider before encrypting and storing the key.
                    if byok_model_val and save_ok:
                        is_model_valid = router.validate_api_key(byok_prov, raw_key, model=byok_model_val)
                        if not is_model_valid:
                            ai_settings_form.add_error(
                                None,
                                'The custom model name was not recognised by the provider. '
                                'Please check the model name and try again.'
                            )
                            save_ok = False

                    if save_ok:
                        try:
                            is_valid = router.validate_api_key(byok_prov, raw_key)
                        except ImproperlyConfigured:
                            ai_settings_form.add_error(
                                None,
                                'API key encryption is not configured on this server. '
                                'Contact your administrator.'
                            )
                            save_ok = False
                            is_valid = False

                        if save_ok and not is_valid:
                            ai_settings_form.add_error(
                                None,
                                'The API key could not be validated. '
                                'Please check the key and try again.'
                            )
                            save_ok = False

                    if save_ok:
                        try:
                            user_ai_obj.encrypted_api_key = router._encrypt_key(raw_key)
                        except ImproperlyConfigured:
                            ai_settings_form.add_error(
                                None,
                                'API key encryption is not configured on this server. '
                                'Contact your administrator.'
                            )
                            save_ok = False

                    if save_ok:
                        user_ai_obj.key_last_four = '••••' + raw_key[-4:]
                        user_ai_obj.byok_provider = byok_prov
                        user_ai_obj.key_validated_at = tz.now()
                        user_ai_obj.byok_model = byok_model_val

                elif byok_model_val is not None:
                    # No new key submitted but model preference changed — update model only
                    user_ai_obj.byok_model = byok_model_val

                if save_ok:
                    user_ai_obj.save()
                    messages.success(request, 'AI preferences saved.')
                    return redirect('profile')
                # Validation failed — fall through to re-render with errors in ai_settings_form

        else:
            # Profile form
            profile_form = UserProfileForm(request.POST, request.FILES, instance=profile)
            if profile_form.is_valid():
                profile_form.save()
                # Sync timezone session cache so middleware picks it up immediately
                request.session['user_timezone'] = profile.timezone
                messages.success(request, 'Profile updated successfully!')
                return redirect('profile')
            # Invalid — fall through to re-render with errors in profile_form

    # ------------------------------------------------------------------
    # Build AI form if not already bound (GET or failed AI settings POST)
    # ------------------------------------------------------------------
    if ai_settings_form is None:
        if user_ai:
            ai_settings_form = UserAISettingsForm(initial={
                'provider_override': user_ai.provider_override,
                'byok_provider': user_ai.byok_provider or '',
                'byok_model': user_ai.byok_model or '',
            })
        else:
            ai_settings_form = UserAISettingsForm(initial={'provider_override': 'inherit'})

    user_has_byok_key = bool(user_ai and user_ai.encrypted_api_key)

    # effective_provider: only use the saved personal override when the user
    # is actually allowed to override (show_provider_override is True).
    # When the org flag is off, even a stale saved override must be ignored.
    if show_provider_override and user_ai and user_ai.provider_override != 'inherit':
        effective_provider = dict(PROVIDER_CHOICES).get(
            user_ai.provider_override, user_ai.provider_override
        )
    else:
        effective_provider = org_provider_display

    # effective_model: the model non-BYOK users are actually using (for the read-only note)
    from ai_assistant.utils.ai_router import AIRouter as _AIRouter
    try:
        _eff_prov_key = (
            user_ai.provider_override
            if (show_provider_override and user_ai and user_ai.provider_override != 'inherit')
            else org_provider
        )
        effective_model = _AIRouter.get_model_name(_eff_prov_key, complexity='simple')
    except Exception:
        effective_model = 'gemini-2.5-flash-lite'

    context = {
        'form': profile_form,
        'profile': profile,
        'user_ai_settings_form': ai_settings_form,
        'user_has_byok_key': user_has_byok_key,
        'show_provider_override': show_provider_override,
        'effective_provider': effective_provider,
        'effective_model': effective_model,
        'org_provider_display': org_provider_display,
        'user_ai': user_ai,
    }
    return render(request, 'accounts/profile.html', context)

@login_required
def organization_members(request):
    """
    Organization members page — lists members, pending invitations, and invite form.
    """
    import re

    try:
        profile = request.user.profile
    except UserProfile.DoesNotExist:
        profile = UserProfile.objects.create(
            user=request.user,
            organization=None,
            is_admin=False,
            completed_wizard=True,
            has_seen_welcome=True,
            onboarding_version=2,
            onboarding_status='pending',
        )

    org = profile.organization

    # If user has no org, show a prompt to set up their workspace
    if not org:
        return render(request, 'accounts/organization_members.html', {
            'organization': None,
            'members': [],
            'pending_invitations': [],
            'can_manage': False,
        })

    # Permission: only org creator or admin can manage invites
    can_manage = (org.created_by == request.user or profile.is_admin)

    # Handle invitation POST
    if request.method == 'POST' and can_manage:
        # Handle workspace rename
        new_name = request.POST.get('workspace_name', '').strip()
        if new_name and new_name != org.name:
            org.name = new_name[:100]
            org.save(update_fields=['name'])
            messages.success(request, 'Workspace name updated.')

        # Handle email invitations
        raw = request.POST.get('invite_emails', '').strip()
        if raw:
            raw_emails = re.split(r'[,;\n]+', raw)
            emails = list(dict.fromkeys(
                e.strip().lower() for e in raw_emails if e.strip()
            ))

            sent_list, skipped_list = [], []
            for email in emails:
                if not re.match(r'^[^@\s]+@[^@\s]+\.[^@\s]+$', email):
                    skipped_list.append(f"{email} (invalid format)")
                    continue

                if UserProfile.objects.filter(
                    organization=org, user__email__iexact=email
                ).exists():
                    skipped_list.append(f"{email} (already a member)")
                    continue

                OrganizationInvitation.objects.filter(
                    organization=org, email=email,
                    status=OrganizationInvitation.STATUS_PENDING,
                ).update(status=OrganizationInvitation.STATUS_REVOKED)

                invitation = OrganizationInvitation.objects.create(
                    organization=org,
                    invited_by=request.user,
                    email=email,
                )

                # Send invitation email
                from django.core.mail import send_mail
                from django.template.loader import render_to_string
                from django.urls import reverse as url_reverse
                accept_url = request.build_absolute_uri(
                    url_reverse('accept_org_invitation', args=[invitation.token])
                )
                context = {
                    'invitation': invitation,
                    'organization': org,
                    'invited_by': request.user,
                    'accept_url': accept_url,
                    'expires_hours': 48,
                }
                try:
                    send_mail(
                        subject=f"You're invited to join '{org.name}' on PrizmAI",
                        message=render_to_string('kanban/email/org_invitation.txt', context),
                        from_email=None,
                        recipient_list=[email],
                        html_message=render_to_string('kanban/email/org_invitation.html', context),
                        fail_silently=False,
                    )
                    sent_list.append(email)
                except Exception:
                    sent_list.append(email)  # Invitation created even if email fails

            if sent_list:
                count = len(sent_list)
                if count == 1:
                    messages.success(request, f"Invitation sent to {sent_list[0]}.")
                else:
                    messages.success(request, f"Invitations sent to {count} addresses.")
            for note in skipped_list:
                messages.info(request, f"Skipped: {note}")

        return redirect('organization_members')

    # GET: show members + pending invitations
    members = UserProfile.objects.filter(organization=org).select_related('user')
    pending_invitations = OrganizationInvitation.objects.filter(
        organization=org, status=OrganizationInvitation.STATUS_PENDING,
    ).order_by('-created_at')

    return render(request, 'accounts/organization_members.html', {
        'organization': org,
        'members': members,
        'pending_invitations': pending_invitations,
        'can_manage': can_manage,
    })

@login_required
def organization_settings(request):
    """Organization settings — rename workspace."""
    try:
        profile = request.user.profile
    except UserProfile.DoesNotExist:
        return redirect('dashboard')

    org = profile.organization
    if not org:
        messages.info(request, 'No workspace found. Set up your workspace first.')
        return redirect('onboarding_welcome')

    if request.method == 'POST':
        can_manage = (org.created_by == request.user or profile.is_admin)
        if can_manage:
            new_name = request.POST.get('workspace_name', '').strip()
            if new_name:
                org.name = new_name[:100]
                org.save(update_fields=['name'])
                messages.success(request, 'Workspace name updated.')
        return redirect('organization_settings')

    return render(request, 'accounts/organization_settings.html', {
        'organization': org,
        'can_manage': (org.created_by == request.user or profile.is_admin),
    })

# Add this method to toggle admin status for a member
@login_required
def toggle_admin(request, profile_id):
    """Toggle admin status for a member."""
    try:
        profile = request.user.profile
    except UserProfile.DoesNotExist:
        return redirect('dashboard')

    org = profile.organization
    if not org:
        return redirect('dashboard')

    # Only org creator can toggle admin
    if org.created_by != request.user:
        messages.error(request, "Only the workspace creator can manage admin roles.")
        return redirect('organization_members')

    target_profile = get_object_or_404(UserProfile, id=profile_id)

    if target_profile.user == org.created_by:
        messages.error(request, "Cannot change the workspace creator's role.")
        return redirect('organization_members')

    if target_profile.organization != org:
        messages.error(request, "This user is not in your workspace.")
        return redirect('organization_members')

    target_profile.is_admin = not target_profile.is_admin
    target_profile.save(update_fields=['is_admin'])

    # Keep OrgAdmin Django Group in sync with profile.is_admin
    from django.contrib.auth.models import Group
    org_admin_group, _ = Group.objects.get_or_create(name='OrgAdmin')
    if target_profile.is_admin:
        target_profile.user.groups.add(org_admin_group)
    else:
        target_profile.user.groups.remove(org_admin_group)

    action = "promoted to Admin" if target_profile.is_admin else "demoted to Member"
    messages.success(request, f"{target_profile.user.get_full_name() or target_profile.user.username} has been {action}."  )
    return redirect('organization_members')

# Add this method to remove a member from the organization
@login_required
def remove_member(request, profile_id):
    """Remove a member from the organization."""
    try:
        profile = request.user.profile
    except UserProfile.DoesNotExist:
        return redirect('dashboard')

    org = profile.organization
    if not org:
        return redirect('dashboard')

    can_manage = (org.created_by == request.user or profile.is_admin)
    if not can_manage:
        messages.error(request, "You don't have permission to remove members.")
        return redirect('organization_members')

    target_profile = get_object_or_404(UserProfile, id=profile_id)

    # Cannot remove the org creator
    if target_profile.user == org.created_by:
        messages.error(request, "Cannot remove the workspace creator.")
        return redirect('organization_members')

    # Cannot remove yourself
    if target_profile.user == request.user:
        messages.error(request, "You cannot remove yourself.")
        return redirect('organization_members')

    # Unlink from org
    if target_profile.organization == org:
        target_profile.organization = None
        target_profile.save(update_fields=['organization'])
        messages.success(request, f"{target_profile.user.get_full_name() or target_profile.user.username} has been removed from the workspace.")

    return redirect('organization_members')

@login_required
def delete_organization(request):
    """MVP Mode: Organization deletion is not available."""
    messages.info(request, 'Organization management is not available in MVP mode.')
    return redirect('dashboard')


@login_required
def social_signup_complete(request):
    """
    Handle post-social signup flow - auto-create profile in MVP mode.
    Safety net: normally save_user() already creates the profile.
    """
    try:
        profile = request.user.profile
        # Route v2 users to the correct onboarding step
        if profile.onboarding_version >= 2 and profile.onboarding_status == 'pending':
            return redirect('onboarding_welcome')
        return redirect('dashboard')
    except UserProfile.DoesNotExist:
        # v2 onboarding: auto-create profile with new onboarding flow
        UserProfile.objects.create(
            user=request.user,
            organization=None,
            is_admin=False,
            completed_wizard=True,
            has_seen_welcome=True,
            onboarding_version=2,
            onboarding_status='pending',
        )
        messages.success(request, 'Welcome! Your account is ready to use.')
        return redirect('onboarding_welcome')


SESSION_ORG_INVITE_KEY = 'pending_org_invite_token'


def accept_org_invitation(request, token):
    """
    Accept an organization invitation via token link.
    - If logged in: join the organization immediately.
    - If not logged in: save token in session, redirect to login.
    """
    invitation = get_object_or_404(OrganizationInvitation, token=token)

    if not invitation.is_valid():
        return render(request, 'accounts/org_invitation_invalid.html', {
            'reason': invitation.get_status_display(),
            'organization': invitation.organization,
        })

    if not request.user.is_authenticated:
        request.session[SESSION_ORG_INVITE_KEY] = str(token)
        messages.info(request, f"Please sign in to join '{invitation.organization.name}'.")
        from django.urls import reverse
        return redirect(f"{reverse('login')}?next={reverse('accept_org_invitation', args=[token])}")

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

    # Link user to the organization
    if not profile.organization or profile.organization != invitation.organization:
        profile.organization = invitation.organization
        profile.save(update_fields=['organization'])

    # Grant viewer membership on all boards belonging to this organization
    from kanban.models import Board, BoardMembership
    org_boards = Board.objects.filter(
        strategy__mission__organization_goal__organization=invitation.organization
    ).distinct()
    for board in org_boards:
        BoardMembership.objects.get_or_create(
            board=board, user=user,
            defaults={'role': 'viewer', 'added_by': invitation.invited_by},
        )

    # Also process any pending WorkspaceInvitation for this email + org
    from kanban.models import WorkspaceInvitation
    from kanban.workspace_member_utils import add_workspace_member
    ws_invitations = WorkspaceInvitation.objects.filter(
        workspace__organization=invitation.organization,
        email__iexact=user.email,
        status=WorkspaceInvitation.STATUS_PENDING,
    )
    for ws_inv in ws_invitations:
        if ws_inv.is_valid():
            add_workspace_member(ws_inv.workspace, user, ws_inv.role, added_by=ws_inv.invited_by)
            ws_inv.mark_accepted(user)
            # Set active workspace if user doesn't have one
            if not profile.active_workspace:
                profile.active_workspace = ws_inv.workspace
                profile.save(update_fields=['active_workspace'])

    invitation.mark_accepted(user)
    request.session.pop(SESSION_ORG_INVITE_KEY, None)

    messages.success(request, f"Welcome! You've joined '{invitation.organization.name}'.")
    return redirect('dashboard')


@login_required
@require_POST
def set_timezone(request):
    """API endpoint to update the user's timezone preference via AJAX."""
    try:
        data = json.loads(request.body)
    except (json.JSONDecodeError, ValueError):
        return JsonResponse({'status': 'error', 'message': 'Invalid JSON'}, status=400)

    tzname = data.get('timezone', '').strip()
    if not tzname or tzname not in COMMON_TIMEZONES:
        return JsonResponse({'status': 'error', 'message': 'Invalid timezone'}, status=400)

    try:
        profile = request.user.profile
    except UserProfile.DoesNotExist:
        return JsonResponse({'status': 'error', 'message': 'Profile not found'}, status=404)

    profile.timezone = tzname
    profile.save(update_fields=['timezone'])

    # Update session cache so the middleware picks it up immediately
    request.session['user_timezone'] = tzname

    return JsonResponse({'status': 'ok', 'timezone': tzname})


@login_required
@require_POST
def update_display_mode(request):
    """API endpoint to update the user's display mode preference via AJAX."""
    VALID_MODES = {'light', 'dark', 'auto', 'accessibility'}
    try:
        data = json.loads(request.body)
    except (json.JSONDecodeError, ValueError):
        return JsonResponse({'status': 'error', 'message': 'Invalid JSON'}, status=400)

    mode = data.get('display_mode', '').strip()
    if mode not in VALID_MODES:
        return JsonResponse({'status': 'error', 'message': 'Invalid display mode'}, status=400)

    try:
        profile = request.user.profile
    except UserProfile.DoesNotExist:
        return JsonResponse({'status': 'error', 'message': 'Profile not found'}, status=404)

    profile.display_mode = mode
    profile.save(update_fields=['display_mode'])

    return JsonResponse({'status': 'ok', 'display_mode': mode})


# ---------------------------------------------------------------------------
# Google Calendar OAuth 2.0 — Connect / Callback / Disconnect
# ---------------------------------------------------------------------------

@login_required
def google_calendar_connect(request):
    """
    Step 1 of the OAuth 2.0 flow: redirect the user to Google's consent screen.
    Requests calendar.events scope so PrizmAI can create/update/delete events.
    """
    try:
        from google_auth_oauthlib.flow import Flow
        from django.conf import settings

        flow = Flow.from_client_config(
            {
                "web": {
                    "client_id": settings.GOOGLE_OAUTH2_CLIENT_ID,
                    "client_secret": settings.GOOGLE_OAUTH2_CLIENT_SECRET,
                    "auth_uri": "https://accounts.google.com/o/oauth2/auth",
                    "token_uri": "https://oauth2.googleapis.com/token",
                }
            },
            scopes=settings.GOOGLE_CALENDAR_SCOPES,
        )
        flow.redirect_uri = settings.GOOGLE_CALENDAR_REDIRECT_URI

        authorization_url, state = flow.authorization_url(
            access_type="offline",
            include_granted_scopes="true",
            prompt="consent",  # force consent to always get a refresh_token
        )
        request.session["google_calendar_oauth_state"] = state
        return redirect(authorization_url)

    except Exception:
        messages.error(request, "Could not initiate Google Calendar connection. Check that GOOGLE_OAUTH2_CLIENT_ID and GOOGLE_OAUTH2_CLIENT_SECRET are configured.")
        return redirect("profile")


@login_required
def google_calendar_callback(request):
    """
    Step 2: Google redirects back here with an authorization code.
    Exchange for tokens and store in GoogleCalendarToken.
    """
    try:
        from google_auth_oauthlib.flow import Flow
        from django.conf import settings
        from accounts.models import GoogleCalendarToken

        state = request.session.pop("google_calendar_oauth_state", None)
        if not state:
            messages.error(request, "Invalid OAuth state. Please try connecting again.")
            return redirect("profile")

        flow = Flow.from_client_config(
            {
                "web": {
                    "client_id": settings.GOOGLE_OAUTH2_CLIENT_ID,
                    "client_secret": settings.GOOGLE_OAUTH2_CLIENT_SECRET,
                    "auth_uri": "https://accounts.google.com/o/oauth2/auth",
                    "token_uri": "https://oauth2.googleapis.com/token",
                }
            },
            scopes=settings.GOOGLE_CALENDAR_SCOPES,
            state=state,
        )
        flow.redirect_uri = settings.GOOGLE_CALENDAR_REDIRECT_URI

        # Allow HTTP for local dev. Production must use HTTPS.
        import os
        if os.getenv("DJANGO_DEBUG", "True").lower() == "true":
            os.environ.setdefault("OAUTHLIB_INSECURE_TRANSPORT", "1")

        flow.fetch_token(authorization_response=request.build_absolute_uri())
        creds = flow.credentials

        token_obj, _ = GoogleCalendarToken.objects.update_or_create(
            user=request.user,
            defaults={
                "access_token": creds.token,
                "refresh_token": creds.refresh_token or "",
                "token_expiry": creds.expiry,
                "sync_enabled": True,
            },
        )
        messages.success(request, "Google Calendar connected. Tasks with due dates will now sync automatically.")

    except Exception as exc:
        messages.error(request, f"Google Calendar connection failed: {exc}")

    return redirect("profile")


@login_required
@require_POST
def google_calendar_disconnect(request):
    """
    Remove the user's GoogleCalendarToken.
    Future task saves will no longer trigger calendar sync.
    """
    from accounts.models import GoogleCalendarToken
    GoogleCalendarToken.objects.filter(user=request.user).delete()
    messages.success(request, "Google Calendar disconnected.")
    return redirect("profile")


@login_required
@require_POST
def google_calendar_toggle_sync(request):
    """
    Toggle the master sync_enabled flag without fully disconnecting.
    """
    from accounts.models import GoogleCalendarToken
    try:
        token_obj = GoogleCalendarToken.objects.get(user=request.user)
        token_obj.sync_enabled = not token_obj.sync_enabled
        token_obj.save(update_fields=["sync_enabled", "updated_at"])
        state = "enabled" if token_obj.sync_enabled else "paused"
        messages.success(request, f"Google Calendar sync {state}.")
    except GoogleCalendarToken.DoesNotExist:
        messages.error(request, "Google Calendar is not connected.")
    return redirect("profile")

