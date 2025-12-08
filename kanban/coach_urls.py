"""
URL patterns for AI Coach
"""

from django.urls import path
from kanban import coach_views

urlpatterns = [
    # Dashboard
    path('board/<int:board_id>/coach/', coach_views.coach_dashboard, name='coach_dashboard'),
    
    # Suggestion views
    path('coach/suggestion/<int:suggestion_id>/', coach_views.suggestion_detail, name='coach_suggestion_detail'),
    
    # Actions
    path('board/<int:board_id>/coach/generate/', coach_views.generate_suggestions, name='coach_generate_suggestions'),
    path('coach/suggestion/<int:suggestion_id>/acknowledge/', coach_views.acknowledge_suggestion, name='coach_acknowledge_suggestion'),
    path('coach/suggestion/<int:suggestion_id>/dismiss/', coach_views.dismiss_suggestion, name='coach_dismiss_suggestion'),
    path('coach/suggestion/<int:suggestion_id>/feedback/', coach_views.submit_feedback, name='coach_submit_feedback'),
    
    # Ask coach
    path('board/<int:board_id>/coach/ask/', coach_views.ask_coach, name='coach_ask'),
    
    # Analytics
    path('board/<int:board_id>/coach/analytics/', coach_views.coaching_analytics, name='coach_analytics'),
    
    # API
    path('api/board/<int:board_id>/coach/suggestions/', coach_views.get_suggestions_api, name='coach_get_suggestions_api'),
]
