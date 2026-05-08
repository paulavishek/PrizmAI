"""
API v1 URL Configuration
"""
from django.urls import path, include
from rest_framework.routers import DefaultRouter
from api.v1 import views, auth_views, zapier_views

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

    # -----------------------------------------------------------------------
    # Global workspace search
    # -----------------------------------------------------------------------
    path('search/global/', views.global_search, name='global_search'),

    # -----------------------------------------------------------------------
    # Zapier integration endpoints
    # See api/v1/zapier_views.py for full documentation.
    # -----------------------------------------------------------------------
    # Polling triggers (GET — flat array, no pagination wrapper)
    path('zapier/tasks/', zapier_views.zapier_task_list, name='zapier_task_list'),
    path('zapier/tasks/completed/', zapier_views.zapier_task_completed, name='zapier_task_completed'),
    path('zapier/tasks/assigned/', zapier_views.zapier_task_assigned, name='zapier_task_assigned'),
    # Actions (POST / PATCH)
    path('zapier/tasks/create/', zapier_views.zapier_task_create, name='zapier_task_create'),
    path('zapier/tasks/<int:task_id>/status/', zapier_views.zapier_task_update_status, name='zapier_task_update_status'),
    # Dynamic dropdowns
    path('zapier/boards/', zapier_views.zapier_board_list, name='zapier_board_list'),
    path('zapier/boards/<int:board_id>/columns/', zapier_views.zapier_column_list, name='zapier_column_list'),
]
