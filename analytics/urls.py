"""
URL configuration for analytics app.
"""
from django.urls import path
from . import views

app_name = 'analytics'

urlpatterns = [
    # Custom logout with feedback
    path('logout/', views.CustomLogoutView.as_view(), name='custom_logout'),
    
    # AJAX feedback submission
    path('api/submit-feedback/', views.submit_feedback_ajax, name='submit_feedback_ajax'),
    
    # Analytics dashboard (staff only)
    path('dashboard/', views.analytics_dashboard, name='dashboard'),
]
