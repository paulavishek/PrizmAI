"""
Resource Leveling URL Configuration
"""
from django.urls import path
from kanban import resource_leveling_views

urlpatterns = [
    # Task-specific endpoints
    path('tasks/<int:task_id>/analyze-assignment/', 
         resource_leveling_views.analyze_task_assignment, 
         name='analyze_task_assignment'),
    path('tasks/<int:task_id>/suggest-reassignment/', 
         resource_leveling_views.create_leveling_suggestion, 
         name='create_leveling_suggestion'),
    
    # Suggestion management
    path('suggestions/<int:suggestion_id>/accept/', 
         resource_leveling_views.accept_suggestion, 
         name='accept_suggestion'),
    path('suggestions/<int:suggestion_id>/reject/', 
         resource_leveling_views.reject_suggestion, 
         name='reject_suggestion'),
    
    # Board-level endpoints
    path('boards/<int:board_id>/leveling-suggestions/', 
         resource_leveling_views.get_board_suggestions, 
         name='get_board_suggestions'),
    path('boards/<int:board_id>/workload-report/', 
         resource_leveling_views.get_team_workload_report, 
         name='get_team_workload_report'),
    path('boards/<int:board_id>/optimize-workload/', 
         resource_leveling_views.optimize_board_workload, 
         name='optimize_board_workload'),
    path('boards/<int:board_id>/balance-workload/', 
         resource_leveling_views.balance_workload, 
         name='balance_workload'),
    path('boards/<int:board_id>/update-profiles/', 
         resource_leveling_views.update_performance_profiles, 
         name='update_performance_profiles'),
    
    # User performance
    path('users/<int:user_id>/performance-profile/', 
         resource_leveling_views.get_user_performance_profile, 
         name='get_user_performance_profile'),
]
