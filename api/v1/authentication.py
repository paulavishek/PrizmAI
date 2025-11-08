"""
API Authentication Classes
"""
from rest_framework import authentication, exceptions
from django.utils import timezone
from django.utils.translation import gettext_lazy as _
from api.models import APIToken


class APITokenAuthentication(authentication.BaseAuthentication):
    """
    Custom authentication class for API tokens.
    
    Usage:
        Include the token in the Authorization header:
        Authorization: Bearer <token>
    """
    
    keyword = 'Bearer'
    
    def authenticate(self, request):
        """
        Authenticate the request and return a two-tuple of (user, token).
        """
        auth_header = request.META.get('HTTP_AUTHORIZATION', '')
        
        if not auth_header:
            return None
        
        try:
            keyword, token = auth_header.split()
        except ValueError:
            raise exceptions.AuthenticationFailed(_('Invalid authorization header format.'))
        
        if keyword != self.keyword:
            return None
        
        return self.authenticate_credentials(token, request)
    
    def authenticate_credentials(self, key, request):
        """
        Validate the token and return user.
        """
        try:
            token = APIToken.objects.select_related('user').get(token=key)
        except APIToken.DoesNotExist:
            raise exceptions.AuthenticationFailed(_('Invalid API token.'))
        
        # Check if token is active
        if not token.is_active:
            raise exceptions.AuthenticationFailed(_('API token is inactive.'))
        
        # Check if token is expired
        if token.is_expired():
            raise exceptions.AuthenticationFailed(_('API token has expired.'))
        
        # Check IP whitelist
        if token.ip_whitelist:
            client_ip = self.get_client_ip(request)
            if client_ip not in token.ip_whitelist:
                raise exceptions.AuthenticationFailed(
                    _('API requests from this IP address are not allowed.')
                )
        
        # Check rate limit
        if not token.check_rate_limit():
            raise exceptions.AuthenticationFailed(
                _('Rate limit exceeded. Please try again later.')
            )
        
        # Increment request count
        token.increment_request_count()
        
        # Store token in request for later use
        request.api_token = token
        
        return (token.user, token)
    
    def authenticate_header(self, request):
        """
        Return the authentication scheme to be used in the WWW-Authenticate header.
        """
        return self.keyword
    
    @staticmethod
    def get_client_ip(request):
        """
        Get the client IP address from the request.
        """
        x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded_for:
            ip = x_forwarded_for.split(',')[0]
        else:
            ip = request.META.get('REMOTE_ADDR')
        return ip


class ScopePermission:
    """
    Permission class to check API token scopes.
    
    Usage in views:
        permission_classes = [ScopePermission]
        required_scopes = ['tasks.read', 'tasks.write']
    """
    
    def has_permission(self, request, view):
        """
        Check if the authenticated token has required scopes.
        """
        # If no API token, allow (session auth users have full access)
        if not hasattr(request, 'api_token'):
            return True
        
        # Get required scopes from view
        required_scopes = getattr(view, 'required_scopes', [])
        
        if not required_scopes:
            return True
        
        # Check if token has all required scopes
        token = request.api_token
        for scope in required_scopes:
            if not token.has_scope(scope):
                return False
        
        return True
