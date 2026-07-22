"""
URL patterns for Scope Creep Autopsy
"""
from django.urls import path
from kanban import scope_autopsy_views

urlpatterns = [
    # Dashboard (main page)
    path('boards/<int:board_id>/scope-autopsy/',
         scope_autopsy_views.scope_autopsy_dashboard,
         name='scope_autopsy_dashboard'),

    # Run autopsy (POST)
    path('boards/<int:board_id>/scope-autopsy/run/',
         scope_autopsy_views.run_scope_autopsy,
         name='run_scope_autopsy'),

    # Status poll (GET)
    path('scope-autopsy/<int:report_id>/status/',
         scope_autopsy_views.scope_autopsy_status,
         name='scope_autopsy_status'),

    # Export PDF (GET)
    path('scope-autopsy/<int:report_id>/export/',
         scope_autopsy_views.scope_autopsy_export,
         name='scope_autopsy_export'),

    # Save scope change reason after task creation (POST) — Fix 2
    path('tasks/<int:task_id>/scope-reason/',
         scope_autopsy_views.save_scope_reason,
         name='save_scope_reason'),
]
