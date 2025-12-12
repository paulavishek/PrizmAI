"""
AI Usage URLs
"""
from django.urls import path
from api import ai_usage_views

app_name = 'ai_usage'

urlpatterns = [
    # Dashboard
    path('dashboard/', ai_usage_views.ai_usage_dashboard, name='dashboard'),
    
    # Stats API
    path('stats/', ai_usage_views.ai_usage_stats_api, name='stats_api'),
]
