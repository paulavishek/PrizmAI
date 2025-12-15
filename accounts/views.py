from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import login, authenticate, logout
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.contrib.auth.models import User
from .forms import LoginForm, RegistrationForm, OrganizationForm, UserProfileForm, OrganizationSettingsForm, JoinOrganizationForm
from .models import Organization, UserProfile

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
    organization = None
    if org_id:
        organization = get_object_or_404(Organization, id=org_id)
    
    if request.method == 'POST':
        form = RegistrationForm(request.POST, organization=organization)
        if form.is_valid():
            user = form.save()
            messages.success(request, 'Registration successful! Please log in.')
            return redirect('login')
    else:
        form = RegistrationForm(organization=organization)
    
    return render(request, 'accounts/register.html', {
        'form': form,
        'organization': organization
    })

@login_required
def organization_choice(request):
    """
    Show a page with options to either join an existing organization
    or create a new organization after registration.
    """
    # Check if user already has a profile
    try:
        profile = request.user.profile
        # If user already has a profile, redirect to dashboard
        return redirect('dashboard')
    except UserProfile.DoesNotExist:
        # User is logged in but doesn't have a profile yet
        return render(request, 'accounts/organization_choice.html')

@login_required
def join_organization(request):
    """
    Handle requests for joining an existing organization.
    Validates email domain before allowing a user to join.
    """
    try:
        # Check if user already has a profile
        profile = request.user.profile
        messages.error(request, 'You already belong to an organization.')
        return redirect('dashboard')
    except UserProfile.DoesNotExist:
        # Only allow users without an organization to join one
        if request.method == 'POST':
            form = JoinOrganizationForm(request.POST)
            if form.is_valid():
                # Get the organization from clean() method
                organization = form.cleaned_data['organization']
                email = form.cleaned_data['email']
                
                # Update user's email if different
                if request.user.email != email:
                    request.user.email = email
                    request.user.save()
                
                # Create user profile with regular member status
                UserProfile.objects.create(
                    user=request.user,
                    organization=organization,
                    is_admin=False
                )
                
                messages.success(request, f'Successfully joined {organization.name}!')
                return redirect('dashboard')
        else:
            # Pre-fill email field with user's current email
            form = JoinOrganizationForm(initial={'email': request.user.email})
        
        return render(request, 'accounts/join_organization.html', {'form': form})

@login_required
def create_organization(request):
    try:
        # Check if user already has a profile
        user_profile = request.user.profile
        messages.error(request, 'You already belong to an organization.')
        return redirect('dashboard')
    except UserProfile.DoesNotExist:
        # Only allow users without an organization to create one
        if request.method == 'POST':
            form = OrganizationForm(request.POST)
            if form.is_valid():
                organization = form.save(commit=False)
                organization.created_by = request.user
                organization.save()
                
                # Create user profile and set as admin
                UserProfile.objects.create(
                    user=request.user,
                    organization=organization,
                    is_admin=True
                )
                
                messages.success(request, f'Organization {organization.name} created successfully!')
                return redirect('dashboard')
        else:
            form = OrganizationForm()
        
        return render(request, 'accounts/create_organization.html', {'form': form})

@login_required
def profile_view(request):
    try:
        profile = request.user.profile
    except UserProfile.DoesNotExist:
        return redirect('organization_choice')
    
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
    try:
        profile = request.user.profile
        if not profile.is_admin:
            messages.error(request, 'You do not have permission to view this page.')
            return redirect('dashboard')
        
        organization = profile.organization
        members = UserProfile.objects.filter(organization=organization)
        
        return render(request, 'accounts/organization_members.html', {
            'organization': organization,
            'members': members
        })
    except UserProfile.DoesNotExist:
        return redirect('create_organization')

@login_required
def organization_settings(request):
    try:
        profile = request.user.profile
        if not profile.is_admin:
            messages.error(request, 'You do not have permission to access organization settings.')
            return redirect('dashboard')
        
        organization = profile.organization
        
        if request.method == 'POST':
            form = OrganizationSettingsForm(request.POST, instance=organization)
            if form.is_valid():
                form.save()
                messages.success(request, 'Organization settings updated successfully!')
                return redirect('organization_settings')
        else:
            form = OrganizationSettingsForm(instance=organization)
        
        # Calculate admin count
        admin_count = UserProfile.objects.filter(
            organization=organization,
            is_admin=True
        ).count()
        
        return render(request, 'accounts/organization_settings.html', {
            'form': form,
            'organization': organization,
            'admin_count': admin_count
        })
    except UserProfile.DoesNotExist:
        return redirect('create_organization')

# Add this method to toggle admin status for a member
@login_required
def toggle_admin(request, profile_id):
    try:
        user_profile = request.user.profile
        if not user_profile.is_admin:
            messages.error(request, 'You do not have permission for this action.')
            return redirect('dashboard')
            
        target_profile = get_object_or_404(UserProfile, id=profile_id)
        
        # Verify they're in the same organization
        if target_profile.organization != user_profile.organization:
            messages.error(request, 'User does not belong to your organization.')
            return redirect('organization_members')
        
        # Only the organization creator can demote/promote other admins
        if target_profile.is_admin and request.user != target_profile.organization.created_by:
            messages.error(request, 'Only the organization creator can demote other admins.')
            return redirect('organization_members')
            
        # Toggle admin status
        target_profile.is_admin = not target_profile.is_admin
        target_profile.save()
        
        action = "promoted to admin" if target_profile.is_admin else "demoted from admin"
        messages.success(request, f'User {target_profile.user.username} {action} successfully.')
        
        return redirect('organization_members')
    except UserProfile.DoesNotExist:
        return redirect('create_organization')

# Add this method to remove a member from the organization
@login_required
def remove_member(request, profile_id):
    try:
        user_profile = request.user.profile
        if not user_profile.is_admin:
            messages.error(request, 'You do not have permission for this action.')
            return redirect('dashboard')
            
        target_profile = get_object_or_404(UserProfile, id=profile_id)
        
        # Verify they're in the same organization
        if target_profile.organization != user_profile.organization:
            messages.error(request, 'User does not belong to your organization.')
            return redirect('organization_members')
        
        # Don't allow removing the organization creator
        if target_profile.user == target_profile.organization.created_by:
            messages.error(request, 'Cannot remove the organization creator.')
            return redirect('organization_members')
            
        # Don't allow admins to remove other admins unless they're the creator
        if target_profile.is_admin and request.user != target_profile.organization.created_by:
            messages.error(request, 'Only the organization creator can remove admins.')
            return redirect('organization_members')
        
        # Actually delete the user's profile
        username = target_profile.user.username
        target_profile.delete()
        
        messages.success(request, f'User {username} has been removed from the organization.')
        return redirect('organization_members')
    except UserProfile.DoesNotExist:
        return redirect('create_organization')

@login_required
def delete_organization(request):
    try:
        profile = request.user.profile
        organization = profile.organization
        
        # Only the organization creator can delete it
        if request.user != organization.created_by:
            messages.error(request, 'Only the organization creator can delete the organization.')
            return redirect('organization_settings')
        
        # Use POST to ensure this can't be triggered by a GET request
        if request.method == 'POST':
            org_name = organization.name
            
            # Delete all user profiles associated with the organization
            # This will leave user accounts intact but without organization association
            UserProfile.objects.filter(organization=organization).delete()
            
            # Delete the organization itself
            organization.delete()
            
            messages.success(request, f'Organization "{org_name}" has been permanently deleted.')
            return redirect('create_organization')
            
        return redirect('organization_settings')
    except UserProfile.DoesNotExist:
        return redirect('create_organization')


@login_required
def social_signup_complete(request):
    """
    Handle post-social signup flow when user needs to be assigned to an organization
    """
    try:
        # Check if user already has a profile
        profile = request.user.profile
        return redirect('dashboard')  # User already has organization
    except UserProfile.DoesNotExist:
        # User signed up with Google but doesn't have an organization
        # Redirect them to organization choice page
        messages.info(request, 
                     'Welcome! Since this is your first time signing in with Google, '
                     'please choose or create an organization.')
        return redirect('organization_choice')
