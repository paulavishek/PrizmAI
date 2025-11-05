from django.urls import path
from . import views

app_name = 'ai_assistant'

urlpatterns = [
    # Main views
    path('', views.assistant_welcome, name='welcome'),
    path('chat/', views.chat_interface, name='chat'),
    path('chat/new/', views.create_session, name='create_session'),
    
    # API endpoints
    path('api/send-message/', views.send_message, name='send_message'),
    path('api/sessions/', views.get_sessions, name='get_sessions'),
    path('api/session/<int:session_id>/messages/', views.get_session_messages, name='get_session_messages'),
    path('api/sessions/<int:session_id>/rename/', views.rename_session, name='rename_session'),
    path('api/sessions/<int:session_id>/delete/', views.delete_session, name='delete_session'),
    path('api/sessions/<int:session_id>/clear/', views.clear_session, name='clear_session'),
    path('api/sessions/<int:session_id>/export/', views.export_session, name='export_session'),
    
    # Message interactions
    path('api/message/<int:message_id>/star/', views.toggle_star_message, name='toggle_star'),
    path('api/message/<int:message_id>/feedback/', views.submit_feedback, name='submit_feedback'),
    
    # Analytics and insights
    path('analytics/', views.analytics_dashboard, name='analytics'),
    path('api/analytics/data/', views.get_analytics_data, name='analytics_data'),
    
    # Task recommendations
    path('recommendations/', views.view_recommendations, name='recommendations'),
    path('api/recommendations/<int:recommendation_id>/accept/', views.accept_recommendation, name='accept_rec'),
    path('api/recommendations/<int:recommendation_id>/reject/', views.reject_recommendation, name='reject_rec'),
    
    # Settings and preferences
    path('preferences/', views.user_preferences, name='preferences'),
    path('api/preferences/save/', views.save_preferences, name='save_preferences'),
    
    # Knowledge base management
    path('knowledge-base/', views.knowledge_base_view, name='knowledge_base'),
    path('api/knowledge-base/refresh/', views.refresh_knowledge_base, name='refresh_kb'),
]
