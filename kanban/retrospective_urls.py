"""
URL patterns for Retrospective feature
"""

from django.urls import path
from . import retrospective_views

urlpatterns = [
    # Retrospective list and dashboard
    path('board/<int:board_id>/retrospectives/', 
         retrospective_views.retrospective_list, 
         name='retrospective_list'),
    
    path('board/<int:board_id>/retrospectives/dashboard/', 
         retrospective_views.retrospective_dashboard, 
         name='retrospective_dashboard'),
    
    # Retrospective CRUD
    path('board/<int:board_id>/retrospectives/create/', 
         retrospective_views.retrospective_create, 
         name='retrospective_create'),
    
    path('board/<int:board_id>/retrospectives/<int:retro_id>/', 
         retrospective_views.retrospective_detail, 
         name='retrospective_detail'),
    
    path('board/<int:board_id>/retrospectives/<int:retro_id>/finalize/', 
         retrospective_views.retrospective_finalize, 
         name='retrospective_finalize'),
    
    path('board/<int:board_id>/retrospectives/<int:retro_id>/export/', 
         retrospective_views.retrospective_export, 
         name='retrospective_export'),
    
    # Lessons learned
    path('board/<int:board_id>/lessons/', 
         retrospective_views.lessons_learned_list, 
         name='lessons_learned_list'),
    
    path('board/<int:board_id>/lessons/<int:lesson_id>/status/', 
         retrospective_views.lesson_update_status, 
         name='lesson_update_status'),
    
    # Action items
    path('board/<int:board_id>/actions/<int:action_id>/status/', 
         retrospective_views.action_update_status, 
         name='action_update_status'),
]
