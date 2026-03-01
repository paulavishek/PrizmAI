from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import login, authenticate, logout
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.contrib.auth.models import User
from .forms import LoginForm, RegistrationForm, UserProfileForm
from .models import Organization, UserProfile
from kanban.permission_audit import log_permission_change
import logging

logger = logging.getLogger(__name__)

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
    messages.success(request, f'Welcome back, {real_user.get_full_name() or real_user.username}!')
    logger.info(f"Returned to real account: {real_username}")
    return redirect('dashboard')

def login_view(request):
    if request.user.is_authenticated:
        return redirect('dashboard')
    
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
                return redirect('dashboard')
    else:
        form = LoginForm()
    
    return render(request, 'accounts/login.html', {'form': form, 'next': next_url})

def logout_view(request):
    logout(request)
    return redirect('login')

def register_view(request, org_id=None):
    """
    Simplified registration - no organization assignment required.
    Organization field is now optional.
    """
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
    
    if request.method == 'POST':
        form = UserProfileForm(request.POST, request.FILES, instance=profile)
        if form.is_valid():
            form.save()
            messages.success(request, 'Profile updated successfully!')
            return redirect('profile')
    else:
        form = UserProfileForm(instance=profile)
    
    return render(request, 'accounts/profile.html', {'form': form, 'profile': profile})

@login_required
def organization_members(request):
    """
    MVP Mode: Show all users since everyone shares the same space.
    """
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
    
    # MVP Mode: Show all users (including demo users)
    members = UserProfile.objects.all()
    
    return render(request, 'accounts/organization_members.html', {
        'organization': None,  # No organization in MVP mode
        'members': members
    })

@login_required
def organization_settings(request):
    """
    MVP Mode: Organization settings are not available.
    """
    messages.info(request, 'Organization settings are not available in MVP mode.')
    return redirect('dashboard')

# Add this method to toggle admin status for a member
@login_required
def toggle_admin(request, profile_id):
    """MVP Mode: Admin toggle is not available."""
    messages.info(request, 'Admin management is not available in MVP mode.')
    return redirect('dashboard')

# Add this method to remove a member from the organization
@login_required
def remove_member(request, profile_id):
    """MVP Mode: Member removal is not available."""
    messages.info(request, 'Member management is not available in MVP mode.')
    return redirect('dashboard')

@login_required
def delete_organization(request):
    """MVP Mode: Organization deletion is not available."""
    messages.info(request, 'Organization management is not available in MVP mode.')
    return redirect('dashboard')


@login_required
def social_signup_complete(request):
    """
    Handle post-social signup flow - auto-create profile in MVP mode.
    """
    try:
        profile = request.user.profile
        return redirect('dashboard')  # User already has profile
    except UserProfile.DoesNotExist:
        # v2 onboarding: auto-create profile with new onboarding flow
        UserProfile.objects.create(
            user=request.user,
            organization=None,
            is_admin=False,
            completed_wizard=True,
            has_seen_welcome=True,       # v2 uses new welcome screen
            onboarding_version=2,
            onboarding_status='pending', # will redirect to /onboarding/
        )
        messages.success(request, 'Welcome! Your account is ready to use.')
        return redirect('dashboard')
