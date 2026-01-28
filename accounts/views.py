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
    """
    # Only allow login for demo users
    demo_users = ['alex_chen_demo', 'sam_rivera_demo', 'jordan_taylor_demo']
    
    if username not in demo_users:
        messages.error(request, 'Invalid demo user.')
        return redirect('login')
    
    # Authenticate with the known demo password
    user = authenticate(request=request, username=username, password='demo123')
    
    if user is not None:
        login(request, user)
        messages.success(request, f'Logged in as {user.get_full_name() or user.username}!')
        logger.info(f"Quick demo login successful for user: {username}")
        return redirect('dashboard')
    else:
        messages.error(request, 'Demo user not found or credentials invalid.')
        logger.warning(f"Quick demo login failed for user: {username}")
        return redirect('login')

def login_view(request):
    if request.user.is_authenticated:
        return redirect('dashboard')
    
    if request.method == 'POST':
        form = LoginForm(request, data=request.POST)
        if form.is_valid():
            username = form.cleaned_data.get('username')
            password = form.cleaned_data.get('password')
            user = authenticate(request=request, username=username, password=password)
            if user is not None:
                login(request, user)
                return redirect('dashboard')
    else:
        form = LoginForm()
    
    return render(request, 'accounts/login.html', {'form': form})

def logout_view(request):
    logout(request)
    return redirect('login')

def register_view(request, org_id=None):
    """
    Simplified registration - automatically assigns users to the single organization.
    All users (demo + real) belong to "Demo - Acme Corporation".
    """
    # org_id parameter is kept for backward compatibility but ignored
    
    if request.method == 'POST':
        form = RegistrationForm(request.POST)
        if form.is_valid():
            user = form.save()
            
            # Automatically assign user to Demo - Acme Corporation
            demo_org = Organization.objects.filter(name='Demo - Acme Corporation').first()
            if demo_org:
                UserProfile.objects.get_or_create(
                    user=user,
                    defaults={
                        'organization': demo_org,
                        'is_admin': False,
                        'completed_wizard': True
                    }
                )
            
            messages.success(request, 'Registration successful! Please log in.')
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
    Single organization mode: Ensure user is assigned to Demo - Acme Corporation.
    Auto-create profile if missing.
    """
    try:
        profile = request.user.profile
        # Ensure they're in the demo organization
        if not profile.organization:
            demo_org = Organization.objects.filter(name='Demo - Acme Corporation').first()
            if demo_org:
                profile.organization = demo_org
                profile.save()
        return redirect('dashboard')
    except UserProfile.DoesNotExist:
        # Auto-create profile and assign to demo organization
        demo_org = Organization.objects.filter(name='Demo - Acme Corporation').first()
        UserProfile.objects.create(
            user=request.user,
            organization=demo_org,
            is_admin=False,
            completed_wizard=True
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
        # MVP Mode: Auto-create profile without organization
        profile = UserProfile.objects.create(
            user=request.user,
            organization=None,
            is_admin=False,
            completed_wizard=True
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
            completed_wizard=True
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
        # MVP Mode: Auto-create profile without organization
        UserProfile.objects.create(
            user=request.user,
            organization=None,
            is_admin=False,
            completed_wizard=True
        )
        messages.success(request, 'Welcome! Your account is ready to use.')
        return redirect('dashboard')
