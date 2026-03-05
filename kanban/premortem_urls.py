"""
URL patterns for Pre-Mortem AI Analysis
"""

from django.urls import path
from kanban import premortem_views

urlpatterns = [
    # Dashboard (main page)
    path('board/<int:board_id>/premortem/',
         premortem_views.premortem_dashboard,
         name='premortem_dashboard'),

    # Run analysis (POST)
    path('board/<int:board_id>/premortem/run/',
         premortem_views.run_premortem,
         name='run_premortem'),

    # Get latest analysis (JSON)
    path('board/<int:board_id>/premortem/latest/',
         premortem_views.get_latest_premortem,
         name='get_latest_premortem'),

    # Acknowledge a scenario (POST)
    path('premortem/<int:premortem_id>/acknowledge/<int:scenario_index>/',
         premortem_views.acknowledge_scenario,
         name='acknowledge_scenario'),
]
