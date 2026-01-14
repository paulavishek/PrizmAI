# kanban/stakeholder_urls.py
"""
URL patterns for stakeholder engagement tracking
"""

from django.urls import path
from . import stakeholder_views

app_name = 'stakeholder'

urlpatterns = [
    # Stakeholder management
    path('boards/<int:board_id>/stakeholders/', stakeholder_views.stakeholder_list, name='stakeholder_list'),
    path('boards/<int:board_id>/stakeholders/create/', stakeholder_views.stakeholder_create, name='stakeholder_create'),
    path('boards/<int:board_id>/stakeholders/<int:pk>/', stakeholder_views.stakeholder_detail, name='stakeholder_detail'),
    path('boards/<int:board_id>/stakeholders/<int:pk>/update/', stakeholder_views.stakeholder_update, name='stakeholder_update'),
    path('boards/<int:board_id>/stakeholders/<int:pk>/delete/', stakeholder_views.stakeholder_delete, name='stakeholder_delete'),
    
    # Engagement recording
    path('boards/<int:board_id>/stakeholders/<int:stakeholder_id>/engagement/create/', 
         stakeholder_views.engagement_record_create, name='engagement_record_create'),
    path('boards/<int:board_id>/stakeholders/<int:stakeholder_id>/engagement/<int:record_id>/update/', 
         stakeholder_views.engagement_record_update, name='engagement_record_update'),
    path('boards/<int:board_id>/stakeholders/<int:stakeholder_id>/engagement/<int:record_id>/delete/', 
         stakeholder_views.engagement_record_delete, name='engagement_record_delete'),
    
    # Task-stakeholder involvement
    path('boards/<int:board_id>/tasks/<int:task_id>/stakeholders/', 
         stakeholder_views.task_stakeholder_involvement, name='task_stakeholder_involvement'),
    path('boards/<int:board_id>/tasks/<int:task_id>/stakeholders/add/', 
         stakeholder_views.add_task_stakeholder, name='add_task_stakeholder'),
    path('boards/<int:board_id>/tasks/<int:task_id>/stakeholders/<int:involvement_id>/edit/', 
         stakeholder_views.edit_task_stakeholder, name='edit_task_stakeholder'),
    path('boards/<int:board_id>/tasks/<int:task_id>/stakeholders/<int:involvement_id>/remove/', 
         stakeholder_views.remove_task_stakeholder, name='remove_task_stakeholder'),
    
    # Analytics and dashboards
    path('boards/<int:board_id>/engagement-metrics/', 
         stakeholder_views.engagement_metrics_dashboard, name='engagement_metrics_dashboard'),
    path('boards/<int:board_id>/engagement-analytics/', 
         stakeholder_views.engagement_analytics, name='engagement_analytics'),
    
    # API endpoints
    path('api/boards/<int:board_id>/stakeholders-data/', 
         stakeholder_views.stakeholder_api_data, name='stakeholder_api_data'),
]
