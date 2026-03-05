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
]
