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
    
    # API Endpoints
    path('board/<int:board_id>/budget/api/metrics/', 
         budget_views.budget_api_metrics, 
         name='budget_api_metrics'),
]
