from allauth.account.adapter import DefaultAccountAdapter
from allauth.socialaccount.adapter import DefaultSocialAccountAdapter
from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from .models import Organization, UserProfile
import re


class CustomAccountAdapter(DefaultAccountAdapter):
    """Custom adapter for regular account signup"""
    
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
                    # Connect the social account to existing user
                    sociallogin.connect(request, user)
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
                
                # Create user profile and assign to organization
                UserProfile.objects.get_or_create(
                    user=user,
                    defaults={
                        'organization': organization,
                        'is_admin': False  # New Google users are not admins by default
                    }
                )
                
            except Organization.DoesNotExist:
                # Create profile without organization - will be handled in post-signup flow
                UserProfile.objects.get_or_create(
                    user=user,
                    defaults={
                        'organization': None,
                        'is_admin': False,
                        'completed_wizard': True
                    }
                )
            except Organization.MultipleObjectsReturned:
                # If multiple organizations with same domain, use the first one (oldest)
                organization = Organization.objects.filter(domain=domain).order_by('created_at').first()
                UserProfile.objects.get_or_create(
                    user=user,
                    defaults={
                        'organization': organization,
                        'is_admin': False
                    }
                )
        
        return user
    
    def get_login_redirect_url(self, request):
        """
        Custom redirect after social login based on user's organization status
        """
        try:
            # Check if user has a profile/organization
            profile = request.user.profile
            # User has organization, redirect to dashboard
            return '/dashboard/'
        except (AttributeError, UserProfile.DoesNotExist):
            # User doesn't have organization, redirect to organization choice
            return '/accounts/social-signup-complete/'
