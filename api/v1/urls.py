"""
API v1 URL Configuration
"""
from django.urls import path, include
from rest_framework.routers import DefaultRouter
from api.v1 import views, auth_views

# Create router for viewsets
router = DefaultRouter()
router.register(r'boards', views.BoardViewSet, basename='board')
router.register(r'tasks', views.TaskViewSet, basename='task')
router.register(r'comments', views.CommentViewSet, basename='comment')

app_name = 'api_v1'

urlpatterns = [
    # Status endpoint
    path('status/', views.api_status, name='status'),
    
    # Mobile/PWA Authentication endpoints
    path('auth/login/', auth_views.api_login, name='api_login'),
    path('auth/register/', auth_views.api_register, name='api_register'),
    path('auth/logout/', auth_views.api_logout, name='api_logout'),
    path('auth/user/', auth_views.api_current_user, name='api_current_user'),
    path('auth/refresh/', auth_views.api_refresh_token, name='api_refresh_token'),
    
    # Token management (requires session auth)
    path('auth/tokens/', views.list_api_tokens, name='list_tokens'),
    path('auth/tokens/create/', views.create_api_token, name='create_token'),
    path('auth/tokens/<int:token_id>/delete/', views.delete_api_token, name='delete_token'),
    
    # AI Usage Dashboard (replaces rate limiting dashboard)
    path('ai-usage/', include('api.ai_usage_urls')),
    
    # ViewSet routes
    path('', include(router.urls)),
]
