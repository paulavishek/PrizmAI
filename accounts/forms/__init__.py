from django import forms
from django.contrib.auth.forms import UserCreationForm, AuthenticationForm, SetPasswordForm, PasswordChangeForm
from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from ..models import Organization, UserProfile
from kanban.utils.email_validation import validate_email_for_signup

class LoginForm(AuthenticationForm):
    username = forms.CharField(
        label='Username or Email',
        widget=forms.TextInput(attrs={
            'class': 'form-control', 
            'placeholder': 'Username or Email',
            'autocomplete': 'off'  # Disable browser autocomplete for username
        })
    )
    password = forms.CharField(
        widget=forms.PasswordInput(attrs={
            'class': 'form-control', 
            'placeholder': 'Password',
            'id': 'password-field'
        })
    )

class CustomSetPasswordForm(SetPasswordForm):
    new_password1 = forms.CharField(
        label="New password",
        widget=forms.PasswordInput(attrs={
            'class': 'form-control',
            'id': 'new-password1-field',
            'placeholder': 'New Password'
        })
    )
    new_password2 = forms.CharField(
        label="New password confirmation",
        widget=forms.PasswordInput(attrs={
            'class': 'form-control',
            'id': 'new-password2-field',
            'placeholder': 'Confirm New Password'
        })
    )

class CustomPasswordChangeForm(PasswordChangeForm):
    old_password = forms.CharField(
        label="Current Password",
        widget=forms.PasswordInput(attrs={
            'class': 'form-control',
            'id': 'old-password-field',
            'placeholder': 'Current Password',
            'autocomplete': 'current-password'
        })
    )
    new_password1 = forms.CharField(
        label="New Password",
        widget=forms.PasswordInput(attrs={
            'class': 'form-control',
            'id': 'new-password1-field',
            'placeholder': 'New Password',
            'autocomplete': 'new-password'
        })
    )
    new_password2 = forms.CharField(
        label="Confirm New Password",
        widget=forms.PasswordInput(attrs={
            'class': 'form-control',
            'id': 'new-password2-field',
            'placeholder': 'Confirm New Password',
            'autocomplete': 'new-password'
        })
    )

class OrganizationForm(forms.ModelForm):
    class Meta:
        model = Organization
        fields = ['name', 'domain']
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control'}),
            'domain': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'example.com'}),
        }
    
    def clean_domain(self):
        """Validate domain format and uniqueness."""
        domain = self.cleaned_data.get('domain')
        if domain:
            # Validate domain format - no spaces allowed
            if ' ' in domain:
                raise ValidationError("Domain cannot contain spaces.")
            
            # Check for duplicate domain (excluding current instance if editing)
            queryset = Organization.objects.filter(domain=domain)
            if self.instance and self.instance.pk:
                queryset = queryset.exclude(pk=self.instance.pk)
            if queryset.exists():
                raise ValidationError(f"An organization with domain '{domain}' already exists.")
        
        return domain

class RegistrationForm(UserCreationForm):
    """
    Simplified registration form for MVP mode.
    No organization or domain validation required.
    """
    email = forms.EmailField(
        required=True,
        widget=forms.EmailInput(attrs={'class': 'form-control'})
    )
    
    class Meta:
        model = User
        fields = ['username', 'email', 'password1', 'password2']
        widgets = {
            'username': forms.TextInput(attrs={'class': 'form-control'}),
        }
    
    def __init__(self, *args, **kwargs):
        # Remove organization param if passed (for backward compatibility)
        kwargs.pop('organization', None)
        super().__init__(*args, **kwargs)
        self.fields['password1'].widget = forms.PasswordInput(attrs={
            'class': 'form-control',
            'id': 'password1-field'
        })
        self.fields['password2'].widget = forms.PasswordInput(attrs={
            'class': 'form-control',
            'id': 'password2-field'
        })
    
    def clean_email(self):
        email = self.cleaned_data.get('email')
        
        # Basic email validation (no domain restriction for MVP)
        is_valid, error_message = validate_email_for_signup(email)
        if not is_valid:
            raise ValidationError(error_message)
        
        # Check for duplicate email
        if User.objects.filter(email=email).exists():
            raise ValidationError("A user with this email already exists.")
        
        return email
    
    def save(self, commit=True):
        user = super().save(commit=False)
        user.email = self.cleaned_data['email']
        
        if commit:
            user.save()
            # MVP Mode: Create profile without organization
            UserProfile.objects.create(
                user=user,
                organization=None,
                is_admin=False,
                completed_wizard=True
            )
        
        return user

class UserProfileForm(forms.ModelForm):
    # Add email and username fields from User model
    email = forms.EmailField(
        required=True,
        widget=forms.EmailInput(attrs={'class': 'form-control'}),
        help_text='Your email address'
    )
    
    username = forms.CharField(
        max_length=150,
        required=True,
        widget=forms.TextInput(attrs={'class': 'form-control', 'readonly': 'readonly'}),
        help_text='Username cannot be changed'
    )
    
    # Add a text field for entering skills (comma-separated)
    skills_input = forms.CharField(
        required=False,
        widget=forms.Textarea(attrs={
            'class': 'form-control',
            'rows': 3,
            'placeholder': 'Enter skills separated by commas (e.g., Python, JavaScript, Project Management)'
        }),
        help_text='Enter your skills separated by commas. Example: Python, Django, React, AWS',
        label='Skills'
    )
    
    class Meta:
        model = UserProfile
        fields = ['profile_picture', 'weekly_capacity_hours']
        widgets = {
            'profile_picture': forms.FileInput(attrs={'class': 'form-control'}),
            'weekly_capacity_hours': forms.NumberInput(attrs={
                'class': 'form-control',
                'min': 1,
                'max': 168
            })
        }
        labels = {
            'weekly_capacity_hours': 'Weekly Working Hours',
        }
        help_texts = {
            'weekly_capacity_hours': 'How many hours per week are you available for work?',
        }
    
    def clean_weekly_capacity_hours(self):
        """Validate that capacity hours is positive and reasonable."""
        hours = self.cleaned_data.get('weekly_capacity_hours')
        if hours is not None:
            if hours < 0:
                raise ValidationError("Weekly capacity hours cannot be negative.")
            if hours > 168:  # 24 * 7 = 168 hours in a week
                raise ValidationError("Weekly capacity hours cannot exceed 168 (hours in a week).")
        return hours
    
    def clean_email(self):
        """Validate email uniqueness (excluding current user)"""
        email = self.cleaned_data.get('email')
        if email and self.instance and self.instance.user:
            # Check if another user has this email
            existing_user = User.objects.filter(email=email).exclude(id=self.instance.user.id).first()
            if existing_user:
                raise ValidationError("A user with this email already exists.")
        return email
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Pre-populate username and email from User model
        if self.instance and self.instance.user:
            self.fields['username'].initial = self.instance.user.username
            self.fields['email'].initial = self.instance.user.email
        
        # Pre-populate skills input with existing skills
        if self.instance and self.instance.pk and self.instance.skills:
            # Convert list of skill dicts to comma-separated string
            skills_list = []
            for skill in self.instance.skills:
                if isinstance(skill, dict):
                    skills_list.append(skill.get('name', ''))
                elif isinstance(skill, str):
                    skills_list.append(skill)
            self.fields['skills_input'].initial = ', '.join(skills_list)
    
    def save(self, commit=True):
        instance = super().save(commit=False)
        
        # Update User model fields (email)
        if self.instance and self.instance.user:
            self.instance.user.email = self.cleaned_data.get('email')
            if commit:
                self.instance.user.save()
        
        # Process skills input
        skills_text = self.cleaned_data.get('skills_input', '')
        if skills_text:
            # Split by comma and create skill objects
            skill_names = [s.strip() for s in skills_text.split(',') if s.strip()]
            instance.skills = [{'name': name, 'level': 'Intermediate'} for name in skill_names]
        else:
            instance.skills = []
        
        if commit:
            instance.save()
        return instance

class OrganizationSettingsForm(forms.ModelForm):
    """
    A form for admins to update organization settings.
    Domain changes require careful validation to not break existing accounts.
    """
    class Meta:
        model = Organization
        fields = ['name', 'domain']
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control'}),
            'domain': forms.TextInput(attrs={
                'class': 'form-control', 
                'placeholder': 'example.com'
            }),
        }
        
    def clean_domain(self):
        """
        Ensure domain changes don't invalidate existing user emails.
        """
        domain = self.cleaned_data.get('domain')
        if self.instance and self.instance.pk:
            # This is an existing organization
            if domain != self.instance.domain:
                # Check if there are users with emails that wouldn't match the new domain
                profiles = UserProfile.objects.filter(organization=self.instance)
                for profile in profiles:
                    email_domain = profile.user.email.split('@')[-1]
                    if email_domain != domain:
                        raise ValidationError(
                            f"Cannot change domain to {domain} as user {profile.user.username} " +
                            f"has an email with domain {email_domain}. All user emails must match " +
                            "the organization domain."
                        )
        return domain

class JoinOrganizationForm(forms.Form):
    organization_name = forms.CharField(
        widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Enter organization name'}),
        max_length=100,
        required=True,
        help_text="Enter the exact name of the organization you want to join"
    )
    
    email = forms.EmailField(
        widget=forms.EmailInput(attrs={'class': 'form-control', 'placeholder': 'Your email address'}),
        help_text="Your email must match the organization's domain"
    )
    
    def clean(self):
        cleaned_data = super().clean()
        organization_name = cleaned_data.get('organization_name')
        email = cleaned_data.get('email')
        
        if organization_name and email:
            try:
                # Try to find the organization by name
                organization = Organization.objects.get(name=organization_name)
                
                # Check if email domain matches organization domain
                email_domain = email.split('@')[-1]
                if email_domain != organization.domain:
                    raise ValidationError(
                        f"Your email domain ({email_domain}) does not match the organization's domain ({organization.domain}). "
                        "Please use your organization email or contact your administrator."
                    )
                
                # Store the organization instance for later use in the view
                cleaned_data['organization'] = organization
                
            except Organization.DoesNotExist:
                raise ValidationError(f"Organization '{organization_name}' not found. Please check the spelling.")
                
        return cleaned_data


class SocialSignupForm(forms.Form):
    """
    Form for users to confirm/customize their account when signing up via social auth (Google OAuth).
    This form is shown when SOCIALACCOUNT_AUTO_SIGNUP = False, giving users the opportunity
    to review their information before account creation.
    """
    username = forms.CharField(
        max_length=150,
        required=True,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Choose a username',
            'autocomplete': 'username'
        }),
        help_text='Your unique username for PrizmAI. Letters, digits and . _ only.'
    )
    
    email = forms.EmailField(
        required=True,
        widget=forms.EmailInput(attrs={
            'class': 'form-control',
            'readonly': 'readonly'  # Email comes from Google, shouldn't be editable
        }),
        help_text='Your email from Google (cannot be changed)'
    )
    
    def __init__(self, *args, **kwargs):
        # Extract sociallogin from kwargs if present
        self.sociallogin = kwargs.pop('sociallogin', None)
        super().__init__(*args, **kwargs)
        
        # Pre-populate from social account data
        if self.sociallogin:
            extra_data = self.sociallogin.account.extra_data
            email = extra_data.get('email', '')
            given_name = extra_data.get('given_name', '').lower()
            family_name = extra_data.get('family_name', '').lower()
            
            # Set email (readonly)
            self.initial['email'] = email
            
            # Generate suggested username
            if given_name and family_name:
                base_username = f"{given_name}.{family_name}"
            elif email:
                base_username = email.split('@')[0].lower()
            else:
                base_username = 'user'
            
            # Clean username
            import re
            base_username = re.sub(r'[^a-z0-9._]', '', base_username)
            
            # Ensure uniqueness
            username = base_username
            counter = 1
            while User.objects.filter(username=username).exists():
                username = f"{base_username}{counter}"
                counter += 1
            
            self.initial['username'] = username
    
    def clean_username(self):
        username = self.cleaned_data.get('username', '').strip().lower()
        
        if not username:
            raise ValidationError('Username is required.')
        
        # Validate username format
        import re
        if not re.match(r'^[a-z0-9._]+$', username):
            raise ValidationError('Username can only contain lowercase letters, numbers, dots, and underscores.')
        
        if len(username) < 3:
            raise ValidationError('Username must be at least 3 characters long.')
        
        if len(username) > 30:
            raise ValidationError('Username cannot be longer than 30 characters.')
        
        # Check for reserved usernames
        reserved = ['admin', 'administrator', 'root', 'system', 'support', 'help', 
                    'info', 'webmaster', 'postmaster', 'hostmaster', 'abuse']
        if username in reserved:
            raise ValidationError('This username is reserved. Please choose another.')
        
        # Check if username already exists
        if User.objects.filter(username=username).exists():
            raise ValidationError('This username is already taken. Please choose another.')
        
        return username
    
    def clean_email(self):
        email = self.cleaned_data.get('email', '').strip().lower()
        
        # Email should come from Google and shouldn't be changed
        if self.sociallogin:
            google_email = self.sociallogin.account.extra_data.get('email', '').lower()
            if email != google_email:
                raise ValidationError('Email cannot be changed. It must match your Google account.')
        
        return email
    
    def try_save(self, request):
        """
        New API method for django-allauth 65.9.0+
        Creates and saves the user, returns (user, response) tuple.
        Response is None if we just want to continue, or an HttpResponse to redirect.
        """
        from allauth.account.internal import flows
        from allauth.socialaccount.models import SocialLogin
        
        # Get the sociallogin from the request session
        if not self.sociallogin:
            from allauth.socialaccount import app_settings
            state_id = request.GET.get(app_settings.STATE_ID_KEY) or request.POST.get(app_settings.STATE_ID_KEY)
            if state_id:
                self.sociallogin = SocialLogin.state_from_request(request)
        
        if not self.sociallogin:
            return None, None
        
        # Update user data with form input
        user = self.sociallogin.user
        user.username = self.cleaned_data.get('username')
        user.email = self.cleaned_data.get('email')
        
        # Extract name from Google data if available
        if self.sociallogin.account.provider == 'google':
            extra_data = self.sociallogin.account.extra_data
            user.first_name = extra_data.get('given_name', '')
            user.last_name = extra_data.get('family_name', '')
        
        # Save the user first
        user.save()
        
        # Complete the social connection and create UserProfile through adapter
        self.sociallogin.save(request, connect=False)
        
        # Create UserProfile if it doesn't exist (fallback safety)
        from accounts.models import UserProfile, Organization
        if not hasattr(user, 'profile'):
            domain = user.email.split('@')[-1].lower()
            try:
                organization = Organization.objects.get(domain=domain)
                UserProfile.objects.create(
                    user=user,
                    organization=organization,
                    is_admin=False,
                    completed_wizard=True
                )
            except Organization.DoesNotExist:
                UserProfile.objects.create(
                    user=user,
                    organization=None,
                    is_admin=False,
                    completed_wizard=True
                )
        
        # Perform login using the updated API
        # Note: In django-allauth 65.9.0+, perform_login() no longer accepts 'signup' parameter
        ret = flows.login.perform_login(
            request,
            user,
        )
        
        return user, ret
    
    def signup(self, request, user):
        """
        Legacy method for backward compatibility (still used internally).
        Called after user is created. Can be used to add custom logic.
        """
        # Set the username from the form
        user.username = self.cleaned_data.get('username')
        user.save()
        return user