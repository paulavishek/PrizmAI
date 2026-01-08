"""
URL configuration for analytics app.
"""
from django.urls import path
from . import views
from . import abuse_views

app_name = 'analytics'

urlpatterns = [
    # Custom logout with feedback
    path('logout/', views.CustomLogoutView.as_view(), name='custom_logout'),
    
    # AJAX feedback submission
    path('api/submit-feedback/', views.submit_feedback_ajax, name='submit_feedback_ajax'),
    
    # Aha moment tracking API
    path('api/track-aha-moment/', views.track_aha_moment_ajax, name='track_aha_moment'),
    path('api/aha-moment-interaction/', views.aha_moment_interaction, name='aha_moment_interaction'),
    path('api/aha-moment-stats/', views.aha_moment_stats_api, name='aha_moment_stats'),
    
    # Demo email collection (for reminders)
    path('api/collect-demo-email/', views.collect_demo_email, name='collect_demo_email'),
    
    # Analytics dashboard (staff only)
    path('dashboard/', views.analytics_dashboard, name='dashboard'),
    
    # Abuse Monitoring Dashboard (staff only)
    path('abuse/', abuse_views.abuse_dashboard, name='abuse_dashboard'),
    path('abuse/visitors/', abuse_views.abuse_visitor_list, name='abuse_visitor_list'),
    path('abuse/visitors/<int:visitor_id>/', abuse_views.abuse_visitor_detail, name='abuse_visitor_detail'),
    path('abuse/action/', abuse_views.abuse_action, name='abuse_action'),
    path('abuse/visitors/bulk-action/', abuse_views.abuse_bulk_action, name='abuse_bulk_action'),
    path('abuse/ip-lookup/', abuse_views.abuse_ip_lookup, name='abuse_ip_lookup'),
    path('abuse/realtime/', abuse_views.abuse_realtime_monitor, name='abuse_realtime_monitor'),
    path('abuse/api/sessions/', abuse_views.abuse_api_sessions, name='abuse_api_sessions'),
    path('abuse/api/stats/', abuse_views.abuse_stats_api, name='abuse_stats_api'),
    path('abuse/export/', abuse_views.abuse_export, name='abuse_export'),
]
