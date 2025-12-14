"""
API Authentication Views for Mobile/PWA
Provides login, register, logout, and user info endpoints
Uses Bearer token authentication (APIToken model)
"""
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework import status
from django.contrib.auth import authenticate
from django.contrib.auth.models import User
from django.db import transaction
from api.models import APIToken
from api.v1.serializers import UserSerializer
from accounts.models import Organization, UserProfile
import secrets


@api_view(['POST'])
@permission_classes([AllowAny])
def api_login(request):
    """
    API endpoint for mobile/PWA login
    
    POST /api/v1/auth/login/
    Body:
    {
        "username": "user123",
        "password": "password"
    }
    
    Returns:
    {
        "token": "bearer_token_here",
        "user": {
            "id": 1,
            "username": "user123",
            "email": "user@example.com",
            "first_name": "John",
            "last_name": "Doe"
        }
    }
    """
    username = request.data.get('username')
    password = request.data.get('password')
    
    if not username or not password:
        return Response(
            {'error': 'Username and password are required'},
            status=status.HTTP_400_BAD_REQUEST
        )
    
    user = authenticate(request=request, username=username, password=password)
    
    if user:
        # Get or create API token for mobile app
        token, created = APIToken.objects.get_or_create(
            user=user,
            name='Mobile/PWA App',
            defaults={
                'token': secrets.token_urlsafe(32),
                'scopes': ['boards.read', 'boards.write', 'tasks.read', 'tasks.write', 'comments.read', 'comments.write'],
                'rate_limit_per_hour': 5000,
                'monthly_quota': 100000
            }
        )
        
        # If token already exists but is inactive, reactivate it
        if not token.is_active:
            token.is_active = True
            token.save()
        
        serializer = UserSerializer(user)
        
        return Response({
            'token': token.token,
            'user': serializer.data
        })
    
    return Response(
        {'error': 'Invalid credentials'},
        status=status.HTTP_401_UNAUTHORIZED
    )


@api_view(['POST'])
@permission_classes([AllowAny])
def api_register(request):
    """
    API endpoint for mobile/PWA registration
    
    POST /api/v1/auth/register/
    Body:
    {
        "username": "newuser",
        "email": "user@example.com",
        "password": "password",
        "first_name": "John",
        "last_name": "Doe"
    }
    
    Returns:
    {
        "token": "bearer_token_here",
        "user": {
            "id": 1,
            "username": "newuser",
            "email": "user@example.com",
            "first_name": "John",
            "last_name": "Doe"
        }
    }
    """
    username = request.data.get('username')
    email = request.data.get('email')
    password = request.data.get('password')
    first_name = request.data.get('first_name', '')
    last_name = request.data.get('last_name', '')
    
    # Validation
    if not username or not password:
        return Response(
            {'error': 'Username and password are required'},
            status=status.HTTP_400_BAD_REQUEST
        )
    
    if User.objects.filter(username=username).exists():
        return Response(
            {'error': 'Username already exists'},
            status=status.HTTP_400_BAD_REQUEST
        )
    
    if email and User.objects.filter(email=email).exists():
        return Response(
            {'error': 'Email already exists'},
            status=status.HTTP_400_BAD_REQUEST
        )
    
    try:
        with transaction.atomic():
            # Create user
            user = User.objects.create_user(
                username=username,
                email=email,
                password=password,
                first_name=first_name,
                last_name=last_name
            )
            
            # Create a default organization for the user
            organization = Organization.objects.create(
                name=f"{username}'s Organization",
                created_by=user
            )
            
            # Create user profile
            UserProfile.objects.create(
                user=user,
                organization=organization,
                is_admin=True
            )
            
            # Create API token for mobile app
            token = APIToken.objects.create(
                user=user,
                name='Mobile/PWA App',
                token=secrets.token_urlsafe(32),
                scopes=['boards.read', 'boards.write', 'tasks.read', 'tasks.write', 'comments.read', 'comments.write'],
                rate_limit_per_hour=5000,
                monthly_quota=100000
            )
            
            serializer = UserSerializer(user)
            
            return Response({
                'token': token.token,
                'user': serializer.data
            }, status=status.HTTP_201_CREATED)
            
    except Exception as e:
        return Response(
            {'error': f'Registration failed: {str(e)}'},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


@api_view(['POST'])
def api_logout(request):
    """
    API endpoint for mobile/PWA logout
    Deactivates the current API token
    
    POST /api/v1/auth/logout/
    Headers:
        Authorization: Bearer <token>
    
    Returns:
    {
        "message": "Logged out successfully"
    }
    """
    # Get the token from the request (set by APITokenAuthentication)
    if hasattr(request, 'api_token'):
        token = request.api_token
        token.is_active = False
        token.save()
        return Response({'message': 'Logged out successfully'})
    
    return Response(
        {'message': 'No active token found'},
        status=status.HTTP_400_BAD_REQUEST
    )


@api_view(['GET'])
def api_current_user(request):
    """
    Get current authenticated user info
    
    GET /api/v1/auth/user/
    Headers:
        Authorization: Bearer <token>
    
    Returns:
    {
        "id": 1,
        "username": "user123",
        "email": "user@example.com",
        "first_name": "John",
        "last_name": "Doe"
    }
    """
    serializer = UserSerializer(request.user)
    return Response(serializer.data)


@api_view(['POST'])
@permission_classes([AllowAny])
def api_refresh_token(request):
    """
    Refresh an existing API token (optional endpoint)
    
    POST /api/v1/auth/refresh/
    Body:
    {
        "token": "current_token"
    }
    
    Returns:
    {
        "token": "new_token",
        "user": {...}
    }
    """
    old_token_key = request.data.get('token')
    
    if not old_token_key:
        return Response(
            {'error': 'Token is required'},
            status=status.HTTP_400_BAD_REQUEST
        )
    
    try:
        old_token = APIToken.objects.get(token=old_token_key, is_active=True)
        
        # Create new token
        new_token = APIToken.objects.create(
            user=old_token.user,
            name=old_token.name,
            token=secrets.token_urlsafe(32),
            scopes=old_token.scopes,
            rate_limit_per_hour=old_token.rate_limit_per_hour,
            monthly_quota=old_token.monthly_quota
        )
        
        # Deactivate old token
        old_token.is_active = False
        old_token.save()
        
        serializer = UserSerializer(old_token.user)
        
        return Response({
            'token': new_token.token,
            'user': serializer.data
        })
        
    except APIToken.DoesNotExist:
        return Response(
            {'error': 'Invalid or expired token'},
            status=status.HTTP_401_UNAUTHORIZED
        )
