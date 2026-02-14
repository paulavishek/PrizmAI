"""
Scope Tracking URL patterns
Provides routes for scope dashboard, baseline management, and alert handling
"""
from django.urls import path
from kanban import scope_views

urlpatterns = [
    # Main Scope Dashboard
    path(
        'boards/<int:board_id>/scope/',
        scope_views.scope_dashboard,
        name='scope_dashboard'
    ),
    
    # Baseline Management
    path(
        'boards/<int:board_id>/scope/set-baseline/',
        scope_views.set_scope_baseline,
        name='set_scope_baseline'
    ),
    
    # Snapshot Management
    path(
        'boards/<int:board_id>/scope/create-snapshot/',
        scope_views.create_scope_snapshot,
        name='create_scope_snapshot'
    ),
    path(
        'boards/<int:board_id>/scope/snapshot/<int:snapshot_id>/',
        scope_views.scope_snapshot_detail,
        name='scope_snapshot_detail'
    ),
    
    # Alert Management
    path(
        'boards/<int:board_id>/scope/alert/<int:alert_id>/acknowledge/',
        scope_views.acknowledge_scope_alert,
        name='acknowledge_scope_alert'
    ),
    path(
        'boards/<int:board_id>/scope/alert/<int:alert_id>/resolve/',
        scope_views.resolve_scope_alert,
        name='resolve_scope_alert'
    ),
    path(
        'boards/<int:board_id>/scope/alert/<int:alert_id>/dismiss/',
        scope_views.dismiss_scope_alert,
        name='dismiss_scope_alert'
    ),
    
    # AI Analysis
    path(
        'boards/<int:board_id>/scope/analyze/',
        scope_views.run_scope_analysis,
        name='run_scope_analysis'
    ),
    
    # API Endpoints
    path(
        'boards/<int:board_id>/scope/api/metrics/',
        scope_views.scope_api_metrics,
        name='scope_api_metrics'
    ),
    
    # Comparison Tool
    path(
        'boards/<int:board_id>/scope/compare/',
        scope_views.scope_comparison,
        name='scope_comparison'
    ),
]
