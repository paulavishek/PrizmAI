from allauth.account.adapter import DefaultAccountAdapter
from allauth.socialaccount.adapter import DefaultSocialAccountAdapter
from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from .models import Organization, UserProfile
import re


class CustomAccountAdapter(DefaultAccountAdapter):
    """Custom adapter for regular account signup"""

    def add_message(self, request, level, message_template=None, message_context=None, extra_tags="", **kwargs):
        """
        Suppress the allauth "Successfully signed in as..." message.
        Django's FallbackStorage writes messages to cookies, which survive
        logout(). Suppressing this message at source prevents it from
        appearing on unrelated pages (e.g. the register form) after logout.
        """
        if message_template and 'logged_in' in str(message_template):
            return
        super().add_message(
            request, level,
            message_template=message_template,
            message_context=message_context,
            extra_tags=extra_tags,
            **kwargs,
        )

    def clean_email(self, email):
        """
        Validates the email and checks if it matches an organization domain
        """
        email = super().clean_email(email)
        
        # Extract domain from email
        domain = email.split('@')[-1].lower()
        
        # Check if there's an organization with this domain
        try:
            organization = Organization.objects.get(domain=domain)
            # Store organization in session for later use
            if hasattr(self.request, 'session'):
                self.request.session['signup_organization_id'] = organization.id
        except Organization.DoesNotExist:
            # If no organization exists with this domain, user can still sign up
            # but will need to create or join an organization later
            pass
        
        return email


class CustomSocialAccountAdapter(DefaultSocialAccountAdapter):
    """Custom adapter for social account signup (Google OAuth)"""
    
    def pre_social_login(self, request, sociallogin):
        """
        Called just after a user successfully authenticates via a social provider,
        but before the login is processed.
        """
        # Get the user's email from Google
        if sociallogin.account.provider == 'google':
            email = sociallogin.account.extra_data.get('email')
            if email:
                # Check if user already exists with this email
                try:
                    user = User.objects.get(email=email)
                    # If the social account isn't already linked, tell allauth
                    # to use this existing user instead of creating a new one.
                    # NOTE: Do NOT call sociallogin.connect() here — that
                    # prematurely authenticates the user and causes the
                    # sidebar to appear on the social-auth confirmation pages.
                    if not sociallogin.is_existing:
                        sociallogin.user = user
                except User.DoesNotExist:
                    pass
    
    def populate_user(self, request, sociallogin, data):
        """
        Hook to populate user instance from social account data.
        This is called BEFORE the user is saved, allowing us to set proper values.
        """
        user = super().populate_user(request, sociallogin, data)
        
        if sociallogin.account.provider == 'google':
            extra_data = sociallogin.account.extra_data
            
            # Set first and last name from Google profile
            user.first_name = extra_data.get('given_name', '')
            user.last_name = extra_data.get('family_name', '')
            
            # Generate a proper username from full name or email
            given_name = extra_data.get('given_name', '').lower()
            family_name = extra_data.get('family_name', '').lower()
            email = extra_data.get('email', '')
            
            if given_name and family_name:
                # Use first.last format
                base_username = f"{given_name}.{family_name}"
            elif email:
                # Fallback to email prefix
                base_username = email.split('@')[0].lower()
            else:
                base_username = 'user'
            
            # Clean username (remove special characters except dots and underscores)
            base_username = re.sub(r'[^a-z0-9._]', '', base_username)
            
            # Ensure username is unique
            username = base_username
            counter = 1
            while User.objects.filter(username=username).exists():
                username = f"{base_username}{counter}"
                counter += 1
            
            user.username = username
        
        return user
    
    def save_user(self, request, sociallogin, form=None):
        """
        Saves a newly signed up social account user.
        Creates user profile after the user is saved.
        """
        user = super().save_user(request, sociallogin, form)
        
        if sociallogin.account.provider == 'google':
            # Get user's email domain
            email = user.email
            domain = email.split('@')[-1].lower()
            
            # Try to find an organization with this domain
            try:
                organization = Organization.objects.get(domain=domain)
                
                # Create user profile and assign to organization — v2 onboarding
                UserProfile.objects.get_or_create(
                    user=user,
                    defaults={
                        'organization': organization,
                        'is_admin': False,
                        'completed_wizard': True,
                        'has_seen_welcome': True,
                        'onboarding_version': 2,
                        'onboarding_status': 'pending',
                    }
                )
                
            except Organization.DoesNotExist:
                # Create profile without organization — v2 onboarding
                UserProfile.objects.get_or_create(
                    user=user,
                    defaults={
                        'organization': None,
                        'is_admin': False,
                        'completed_wizard': True,
                        'has_seen_welcome': True,
                        'onboarding_version': 2,
                        'onboarding_status': 'pending',
                    }
                )
            except Organization.MultipleObjectsReturned:
                # If multiple organizations with same domain, use the first one (oldest)
                organization = Organization.objects.filter(domain=domain).order_by('created_at').first()
                UserProfile.objects.get_or_create(
                    user=user,
                    defaults={
                        'organization': organization,
                        'is_admin': False,
                        'completed_wizard': True,
                        'has_seen_welcome': True,
                        'onboarding_version': 2,
                        'onboarding_status': 'pending',
                    }
                )
            
            # v2 users access demo boards via demo-mode toggle,
            # NOT via board membership — keeps their "My Boards" clean.
        
        return user
    
    def get_login_redirect_url(self, request):
        """
        Custom redirect after social login — route to the correct
        onboarding step for new users, or dashboard for returning users.
        """
        try:
            profile = request.user.profile
            # Route v2 users to the correct onboarding step
            if profile.onboarding_version >= 2:
                if profile.onboarding_status == 'pending':
                    return '/onboarding/'
                if profile.onboarding_status == 'goal_submitted':
                    return '/onboarding/generating/'
                if profile.onboarding_status == 'workspace_generated':
                    return '/onboarding/review/'
            # completed, skipped, demo_exploring, or v1 → dashboard
            return '/dashboard/'
        except (AttributeError, UserProfile.DoesNotExist):
            return '/accounts/social-signup-complete/'
