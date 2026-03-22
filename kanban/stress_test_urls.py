"""
URL patterns for Project Stress Test
"""

from django.urls import path
from kanban import stress_test_views

urlpatterns = [
    # Dashboard (main page)
    path('board/<int:board_id>/stress-test/',
         stress_test_views.stress_test_dashboard,
         name='stress_test_dashboard'),

    # Run new stress test (POST)
    path('board/<int:board_id>/stress-test/run/',
         stress_test_views.run_stress_test,
         name='run_stress_test'),

    # Apply / unapply a vaccine (POST)
    path('board/<int:board_id>/stress-test/vaccine/<int:vaccine_id>/apply/',
         stress_test_views.apply_vaccine,
         name='apply_vaccine'),

    # Mark scenario as addressed (POST)
    path('board/<int:board_id>/stress-test/scenario/<int:scenario_id>/address/',
         stress_test_views.mark_scenario_addressed,
         name='mark_scenario_addressed'),

    # Reset (delete) all session history for this board (POST, owner only)
    path('board/<int:board_id>/stress-test/reset-history/',
         stress_test_views.reset_stress_test_history,
         name='reset_stress_test_history'),
]
