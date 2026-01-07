from django.urls import path, include
from . import views
from . import api_views
from . import forecasting_views
from . import burndown_views
from . import retrospective_views
from . import milestone_views
from . import conflict_views
from . import demo_views
from . import permission_views

urlpatterns = [
    path('', views.welcome, name='welcome'),
    path('dashboard/', views.dashboard, name='dashboard'),
    
    # Getting Started Wizard
    path('getting-started/', views.getting_started_wizard, name='getting_started_wizard'),
    path('getting-started/complete/', views.complete_wizard, name='complete_wizard'),
    path('getting-started/reset/', views.reset_wizard, name='reset_wizard'),
    path('api/wizard/create-board/', views.wizard_create_board, name='wizard_create_board'),
    path('api/wizard/create-task/', views.wizard_create_task, name='wizard_create_task'),
    
    # Demo Mode (New System)
    path('demo/', demo_views.demo_dashboard, name='demo_dashboard'),
    path('demo/start/', demo_views.demo_mode_selection, name='demo_mode_selection'),
    path('demo/switch-role/', demo_views.switch_demo_role, name='demo_switch_role'),
    path('demo/exit/', demo_views.exit_demo, name='exit_demo'),
    path('demo/extend/', demo_views.extend_demo_session, name='extend_demo_session'),
    path('demo/track-event/', demo_views.track_demo_event, name='track_demo_event'),
    path('demo/check-nudge/', demo_views.check_nudge, name='check_nudge'),
    path('demo/track-nudge/', demo_views.track_nudge, name='track_nudge'),
    path('demo/api/feature-counts/', demo_views.demo_feature_counts_api, name='demo_feature_counts_api'),
    path('demo/board/<int:board_id>/', demo_views.demo_board_detail, name='demo_board_detail'),
    path('demo/board/<int:board_id>/tasks/', demo_views.demo_board_tasks_list, name='demo_board_tasks_list'),
    path('demo/reset/', demo_views.reset_demo_data, name='reset_demo'),
    
    path('boards/', views.board_list, name='board_list'),
    path('boards/create/', views.create_board, name='create_board'),    path('boards/<int:board_id>/', views.board_detail, name='board_detail'),    path('boards/<int:board_id>/analytics/', views.board_analytics, name='board_analytics'),
    path('boards/<int:board_id>/scope-tracking/', views.scope_tracking_dashboard, name='scope_tracking_dashboard'),
    path('boards/<int:board_id>/skill-gaps/', views.skill_gap_dashboard, name='skill_gap_dashboard'),
    path('boards/<int:board_id>/gantt/', views.gantt_chart, name='gantt_chart'),
    path('boards/<int:board_id>/edit/', views.edit_board, name='edit_board'),
    path('boards/<int:board_id>/create-task/', views.create_task, name='create_task'),
    path('boards/<int:board_id>/columns/<int:column_id>/create-task/', views.create_task, name='create_task_in_column'),
    path('boards/<int:board_id>/create-column/', views.create_column, name='create_column'),
    path('boards/<int:board_id>/create-label/', views.create_label, name='create_label'),
    path('boards/<int:board_id>/add-member/', views.add_board_member, name='add_board_member'),
    path('boards/<int:board_id>/members/<int:user_id>/remove/', views.remove_board_member, name='remove_board_member'),
    path('boards/<int:board_id>/delete/', views.delete_board, name='delete_board'),
    path('boards/<int:board_id>/join/', views.join_board, name='join_board'),
    path('boards/<int:board_id>/export/', views.export_board, name='export_board'),
    path('boards/import/', views.import_board, name='import_board'),
    path('tasks/<int:task_id>/', views.task_detail, name='task_detail'),
    path('tasks/<int:task_id>/delete/', views.delete_task, name='delete_task'),
    path('tasks/move/', views.move_task, name='move_task'),
    path('tasks/<int:task_id>/update-progress/', views.update_task_progress, name='update_task_progress'),
    path('organization-boards/', views.organization_boards, name='organization_boards'),
    path('labels/<int:label_id>/delete/', views.delete_label, name='delete_label'),
    path('columns/<int:column_id>/move/left/', views.move_column, {'direction': 'left'}, name='move_column_left'),    path('columns/<int:column_id>/move/right/', views.move_column, {'direction': 'right'}, name='move_column_right'),
    path('columns/reorder/', views.reorder_columns, name='reorder_columns'),
    path('columns/reorder-multiple/', views.reorder_multiple_columns, name='reorder_multiple_columns'),
    path('columns/<int:column_id>/delete/', views.delete_column, name='delete_column'),    path('boards/<int:board_id>/add-lean-labels/', views.add_lean_labels, name='add_lean_labels'),
    
    # Test page for AI features
    path('test-ai-features/', views.test_ai_features, name='test_ai_features'),    # AI API Endpoints
    path('api/generate-task-description/', api_views.generate_task_description_api, name='generate_task_description_api'),
    path('api/summarize-comments/<int:task_id>/', api_views.summarize_comments_api, name='summarize_comments_api'),
    path('api/suggest-lss-classification/', api_views.suggest_lss_classification_api, name='suggest_lss_classification_api'),
    path('api/summarize-board-analytics/<int:board_id>/', api_views.summarize_board_analytics_api, name='summarize_board_analytics_api'),
    path('api/download-analytics-pdf/<int:board_id>/', api_views.download_analytics_summary_pdf, name='download_analytics_summary_pdf'),
    path('api/summarize-task-details/<int:task_id>/', api_views.summarize_task_details_api, name='summarize_task_details_api'),
      # New AI Enhancement API Endpoints
    path('api/suggest-task-priority/', api_views.suggest_task_priority_api, name='suggest_task_priority_api'),
    path('api/predict-deadline/', api_views.predict_deadline_api, name='predict_deadline_api'),
    path('api/recommend-columns/', api_views.recommend_columns_api, name='recommend_columns_api'),
    path('api/suggest-task-breakdown/', api_views.suggest_task_breakdown_api, name='suggest_task_breakdown_api'),
    path('api/analyze-workflow-optimization/', api_views.analyze_workflow_optimization_api, name='analyze_workflow_optimization_api'),    path('api/create-subtasks/', api_views.create_subtasks_api, name='create_subtasks_api'),
    
    # Risk Management API Endpoints
    path('api/kanban/calculate-task-risk/', api_views.calculate_task_risk_api, name='calculate_task_risk_api'),
    path('api/kanban/get-mitigation-suggestions/', api_views.get_mitigation_suggestions_api, name='get_mitigation_suggestions_api'),
    path('api/kanban/assess-task-dependencies/', api_views.assess_task_dependencies_api, name='assess_task_dependencies_api'),
    
    # Resource Demand Forecasting - NEW FEATURES
    path('board/<int:board_id>/forecast/', forecasting_views.forecast_dashboard, name='forecast_dashboard'),
    path('board/<int:board_id>/forecast/generate/', forecasting_views.generate_forecast, name='generate_forecast'),
    path('board/<int:board_id>/recommendations/', forecasting_views.workload_recommendations, name='workload_recommendations'),
    path('board/<int:board_id>/recommendation/<int:rec_id>/', forecasting_views.recommendation_detail, name='recommendation_detail'),
    path('board/<int:board_id>/alerts/', forecasting_views.capacity_alerts, name='capacity_alerts'),
    path('board/<int:board_id>/alerts/<int:alert_id>/acknowledge/', forecasting_views.acknowledge_alert, name='acknowledge_alert'),
    path('board/<int:board_id>/alerts/<int:alert_id>/resolve/', forecasting_views.resolve_alert, name='resolve_alert'),
    path('board/<int:board_id>/capacity-chart/', forecasting_views.team_capacity_chart, name='team_capacity_chart'),
    path('board/<int:board_id>/task/<int:task_id>/assignment-suggestion/', forecasting_views.task_assignment_suggestion, name='task_assignment_suggestion'),
    
    # Burndown/Burnup Prediction with Confidence Intervals - NEW FEATURE
    path('board/<int:board_id>/burndown/', burndown_views.burndown_dashboard, name='burndown_dashboard'),
    path('board/<int:board_id>/burndown/generate/', burndown_views.generate_burndown_prediction, name='generate_burndown_prediction'),
    path('board/<int:board_id>/burndown/chart-data/', burndown_views.burndown_chart_data, name='burndown_chart_data'),
    path('board/<int:board_id>/burndown/velocity-data/', burndown_views.velocity_chart_data, name='velocity_chart_data'),
    path('board/<int:board_id>/burndown/alerts/<int:alert_id>/acknowledge/', burndown_views.acknowledge_burndown_alert, name='acknowledge_burndown_alert'),
    path('board/<int:board_id>/burndown/alerts/<int:alert_id>/resolve/', burndown_views.resolve_burndown_alert, name='resolve_burndown_alert'),
    path('board/<int:board_id>/burndown/milestones/', burndown_views.manage_milestones, name='manage_milestones'),
    path('board/<int:board_id>/burndown/history/', burndown_views.prediction_history, name='prediction_history'),
    path('board/<int:board_id>/burndown/suggestions/', burndown_views.actionable_suggestions_api, name='actionable_suggestions_api'),

    
    # Task Dependency Management API Endpoints
    path('api/task/<int:task_id>/dependencies/', api_views.get_task_dependencies_api, name='get_task_dependencies_api'),
    path('api/task/<int:task_id>/set-parent/', api_views.set_parent_task_api, name='set_parent_task_api'),
    path('api/task/<int:task_id>/add-related/', api_views.add_related_task_api, name='add_related_task_api'),
    path('api/task/<int:task_id>/analyze-dependencies/', api_views.analyze_task_dependencies_api, name='analyze_task_dependencies_api'),
    path('api/task/<int:task_id>/dependency-tree/', api_views.get_dependency_tree_api, name='get_dependency_tree_api'),
    path('api/board/<int:board_id>/dependency-graph/', api_views.get_board_dependency_graph_api, name='get_board_dependency_graph_api'),
    
    # Gantt Chart API Endpoints
    path('api/tasks/update-dates/', api_views.update_task_dates_api, name='update_task_dates_api'),
    
    # Task Prediction API Endpoints
    path('api/task/<int:task_id>/prediction/', api_views.get_task_prediction_api, name='get_task_prediction_api'),
    path('api/board/<int:board_id>/update-predictions/', api_views.bulk_update_predictions_api, name='bulk_update_predictions_api'),
    
    # Priority Suggestion API Endpoints
    path('api/suggest-priority/', api_views.suggest_task_priority_api, name='suggest_task_priority_api'),
    path('api/log-priority-decision/', api_views.log_priority_decision_api, name='log_priority_decision_api'),
    path('api/board/<int:board_id>/train-priority-model/', api_views.train_priority_model_api, name='train_priority_model_api'),
    path('api/board/<int:board_id>/priority-model-info/', api_views.get_priority_model_info_api, name='get_priority_model_info_api'),
    
    # Skill Gap Analysis API Endpoints
    path('api/skill-gaps/analyze/<int:board_id>/', api_views.analyze_skill_gaps_api, name='analyze_skill_gaps_api'),
    path('api/team-skill-profile/<int:board_id>/', api_views.get_team_skill_profile_api, name='get_team_skill_profile_api'),
    path('api/skill-gaps/<int:gap_id>/detail/', api_views.get_skill_gap_detail_api, name='get_skill_gap_detail_api'),
    path('api/task/<int:task_id>/match-team/', api_views.match_team_to_task_api, name='match_team_to_task_api'),
    path('api/task/<int:task_id>/extract-skills/', api_views.extract_task_skills_api, name='extract_task_skills_api'),
    path('api/development-plans/create/', api_views.create_skill_development_plan_api, name='create_skill_development_plan_api'),
    path('api/skill-gaps/list/<int:board_id>/', api_views.get_skill_gaps_list_api, name='get_skill_gaps_list_api'),
    path('api/development-plans/<int:board_id>/', api_views.get_development_plans_api, name='get_development_plans_api'),
    
    # File Management for Tasks
    path('tasks/<int:task_id>/files/upload/', views.upload_task_file, name='upload_task_file'),
    path('tasks/<int:task_id>/files/list/', views.list_task_files, name='list_task_files'),
    path('files/<int:file_id>/download/', views.download_task_file, name='download_task_file'),
    path('files/<int:file_id>/delete/', views.delete_task_file, name='delete_task_file'),
    
    # Retrospective URLs
    path('', include('kanban.retrospective_urls')),
    
    # Milestone Management URLs
    path('board/<int:board_id>/milestones/create/', milestone_views.create_milestone, name='create_milestone'),
    path('board/<int:board_id>/milestones/<int:milestone_id>/update/', milestone_views.update_milestone, name='update_milestone'),
    path('board/<int:board_id>/milestones/<int:milestone_id>/delete/', milestone_views.delete_milestone, name='delete_milestone'),
    path('board/<int:board_id>/milestones/<int:milestone_id>/toggle/', milestone_views.toggle_milestone_completion, name='toggle_milestone_completion'),
    path('board/<int:board_id>/milestones/<int:milestone_id>/', milestone_views.get_milestone_details, name='get_milestone_details'),
    path('api/milestones/<int:board_id>/list/', milestone_views.list_board_milestones, name='list_board_milestones'),
    
    # Budget & ROI Tracking URLs
    path('', include('kanban.budget_urls')),
    
    # AI Coach URLs
    path('', include('kanban.coach_urls')),
    
    # Resource Leveling URLs
    path('api/resource-leveling/', include('kanban.resource_leveling_urls')),
    
    # Conflict Detection & Resolution URLs
    path('conflicts/', conflict_views.conflict_dashboard, name='conflict_dashboard'),
    path('conflicts/<int:conflict_id>/', conflict_views.conflict_detail, name='conflict_detail'),
    path('conflicts/<int:conflict_id>/resolutions/<int:resolution_id>/apply/', conflict_views.apply_resolution, name='apply_resolution'),
    path('conflicts/<int:conflict_id>/ignore/', conflict_views.ignore_conflict, name='ignore_conflict'),
    path('conflicts/trigger/all/', conflict_views.trigger_detection_all, name='trigger_detection_all'),
    path('conflicts/trigger/<int:board_id>/', conflict_views.trigger_detection, name='trigger_detection_board'),
    path('conflicts/notifications/<int:notification_id>/acknowledge/', conflict_views.acknowledge_notification, name='acknowledge_notification'),
    path('conflicts/analytics/', conflict_views.conflict_analytics, name='conflict_analytics'),
    
    # Permission Management URLs - NEW ADVANCED FEATURES
    path('permissions/roles/', permission_views.manage_roles, name='manage_roles'),
    path('permissions/roles/create/', permission_views.create_role, name='create_role'),
    path('permissions/roles/<int:role_id>/edit/', permission_views.edit_role, name='edit_role'),
    path('permissions/roles/<int:role_id>/delete/', permission_views.delete_role, name='delete_role'),
    path('board/<int:board_id>/members/manage/', permission_views.manage_board_members, name='manage_board_members'),
    path('board/membership/<int:membership_id>/change-role/', permission_views.change_member_role, name='change_member_role'),
    path('board/<int:board_id>/members/add/', permission_views.add_board_member_with_role, name='add_board_member_with_role'),
    path('board/membership/<int:membership_id>/remove/', permission_views.remove_board_member_role, name='remove_board_member_role'),
    path('permissions/audit/', permission_views.view_permission_audit, name='view_permission_audit_org'),
    path('board/<int:board_id>/permissions/audit/', permission_views.view_permission_audit, name='view_permission_audit'),
]