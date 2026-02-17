"""
Budget & ROI Tracking URL Configuration
"""
from django.urls import path
from kanban import budget_views

urlpatterns = [
    # Budget Dashboard
    path('board/<int:board_id>/budget/', 
         budget_views.budget_dashboard, 
         name='budget_dashboard'),
    
    path('board/<int:board_id>/budget/create/', 
         budget_views.budget_create_or_edit, 
         name='budget_create_or_edit'),
    
    # Budget Analytics
    path('board/<int:board_id>/budget/analytics/', 
         budget_views.budget_analytics, 
         name='budget_analytics'),
    
    # Task Cost Management
    path('task/<int:task_id>/cost/edit/', 
         budget_views.task_cost_edit, 
         name='task_cost_edit'),
    
    # Time Entry
    path('task/<int:task_id>/time/log/', 
         budget_views.time_entry_create, 
         name='time_entry_create'),
    
    # ROI Dashboard
    path('board/<int:board_id>/roi/', 
         budget_views.roi_dashboard, 
         name='roi_dashboard'),
    
    path('board/<int:board_id>/roi/snapshot/create/', 
         budget_views.roi_snapshot_create, 
         name='roi_snapshot_create'),
    
    # AI-Powered Features
    path('board/<int:board_id>/budget/ai/analyze/', 
         budget_views.ai_analyze_budget, 
         name='ai_analyze_budget'),
    
    path('board/<int:board_id>/budget/ai/recommendations/', 
         budget_views.ai_generate_recommendations, 
         name='ai_generate_recommendations'),
    
    path('board/<int:board_id>/budget/ai/predict/', 
         budget_views.ai_predict_overrun, 
         name='ai_predict_overrun'),
    
    path('board/<int:board_id>/budget/ai/learn-patterns/', 
         budget_views.ai_learn_patterns, 
         name='ai_learn_patterns'),
    
    # Recommendations Management
    path('board/<int:board_id>/budget/recommendations/', 
         budget_views.recommendations_list, 
         name='recommendations_list'),
    
    path('recommendation/<int:recommendation_id>/action/', 
         budget_views.recommendation_action, 
         name='recommendation_action'),
    
    path('recommendation/<int:recommendation_id>/preview/', 
         budget_views.recommendation_preview, 
         name='recommendation_preview'),
    
    path('recommendation/<int:recommendation_id>/details/', 
         budget_views.recommendation_implementation_details, 
         name='recommendation_implementation_details'),
    
    # API Endpoints
    path('board/<int:board_id>/budget/api/metrics/', 
         budget_views.budget_api_metrics, 
         name='budget_api_metrics'),
    
    # Time Tracking Views
    path('timesheet/', 
         budget_views.my_timesheet, 
         name='my_timesheet'),
    
    path('board/<int:board_id>/timesheet/', 
         budget_views.my_timesheet, 
         name='board_timesheet'),
    
    path('time-tracking/', 
         budget_views.time_tracking_dashboard, 
         name='time_tracking_dashboard'),
    
    path('board/<int:board_id>/time-tracking/', 
         budget_views.time_tracking_dashboard, 
         name='board_time_tracking'),
    
    path('board/<int:board_id>/team-timesheet/', 
         budget_views.team_timesheet, 
         name='team_timesheet'),
    
    path('task/<int:task_id>/time/quick-log/', 
         budget_views.quick_time_entry, 
         name='quick_time_entry'),
    
    path('time-entry/<int:entry_id>/delete/', 
         budget_views.delete_time_entry, 
         name='delete_time_entry'),
    
    path('api/time-entries-by-date/', 
         budget_views.time_entries_by_date, 
         name='time_entries_by_date'),
    
    path('api/time-entries-by-period/', 
         budget_views.time_entries_by_period, 
         name='time_entries_by_period'),
    
    path('api/search-tasks/', 
         budget_views.search_tasks_for_time_entry, 
         name='search_tasks_for_time_entry'),
    
    # AI-powered time entry validation
    path('api/time-entry/validate/', 
         budget_views.validate_time_entry_api, 
         name='validate_time_entry_api'),
    
    path('api/time-entry/create-split/', 
         budget_views.create_split_time_entries, 
         name='create_split_time_entries'),
]
