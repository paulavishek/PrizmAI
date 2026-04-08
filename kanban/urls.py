from django.urls import path, include
from . import views
from . import api_views
from . import forecasting_views
from . import burndown_views
from . import retrospective_views
from . import conflict_views
from . import demo_views
# permission_views deleted in RBAC Phase 1 — legacy permission UI removed.
from . import invitation_views
from . import triple_constraint_views
from . import automation_views
from . import scheduled_automation_views
from . import mission_views
from . import mission_views
from . import calendar_views
from . import prizmbrief_views
from . import onboarding_views
from . import whatif_views
from . import shadow_views
from . import workspace_member_views
from . import commitment_views
from . import favorite_views
from . import sandbox_views
from . import access_request_views

urlpatterns = [
    path('', views.welcome, name='welcome'),
    path('dashboard/', views.dashboard, name='dashboard'),
    
    # Getting Started Wizard
    path('getting-started/', views.getting_started_wizard, name='getting_started_wizard'),
    path('getting-started/complete/', views.complete_wizard, name='complete_wizard'),
    path('getting-started/reset/', views.reset_wizard, name='reset_wizard'),
    path('api/wizard/create-board/', views.wizard_create_board, name='wizard_create_board'),
    path('api/wizard/create-task/', views.wizard_create_task, name='wizard_create_task'),
    
    # Demo Mode — legacy routes kept as redirects, new single-tier sandbox
    path('demo/', demo_views.demo_dashboard, name='demo_dashboard'),
    path('demo/start/', demo_views.demo_mode_selection, name='demo_mode_selection'),
    path('demo/switch-role/', demo_views.switch_demo_role, name='demo_switch_role'),
    path('demo/exit/', demo_views.exit_demo, name='exit_demo'),
    path('demo/fingerprint/', demo_views.receive_client_fingerprint, name='receive_client_fingerprint'),

    # Single-tier personal sandbox
    path('demo/reset-mine/', sandbox_views.reset_my_demo, name='reset_my_demo'),
    path('sandbox/status/', sandbox_views.sandbox_status, name='sandbox_status'),
    path('demo/track-event/', demo_views.track_demo_event, name='track_demo_event'),
    path('demo/check-nudge/', demo_views.check_nudge, name='check_nudge'),
    path('demo/track-nudge/', demo_views.track_nudge, name='track_nudge'),
    path('demo/api/feature-counts/', demo_views.demo_feature_counts_api, name='demo_feature_counts_api'),
    path('demo/board/<int:board_id>/', demo_views.demo_board_detail, name='demo_board_detail'),
    path('demo/board/<int:board_id>/tasks/', demo_views.demo_board_tasks_list, name='demo_board_tasks_list'),
    path('demo/tasks/', demo_views.demo_all_tasks_list, name='demo_all_tasks'),
    path('demo/reset/', demo_views.reset_demo_data, name='reset_demo'),
    
    path('boards/', views.board_list, name='board_list'),
    path('boards/create/', views.create_board, name='create_board'),

    # -----------------------------------------------------------------------
    # Organization Goal hierarchy  (Goal → Mission → Strategy → Board → Task)
    # No access restrictions — all authenticated users can use these.
    # -----------------------------------------------------------------------
    path('goals/', mission_views.goal_list, name='goal_list'),
    path('goals/create/', mission_views.create_goal, name='create_goal'),
    path('goals/<int:goal_id>/', mission_views.goal_detail, name='goal_detail'),
    path('goals/<int:goal_id>/edit/', mission_views.edit_goal, name='edit_goal'),
    path('goals/<int:goal_id>/delete/', mission_views.delete_goal, name='delete_goal'),
    path('goals/<int:goal_id>/link-mission/', mission_views.link_mission_to_goal, name='link_mission_to_goal'),
    path('goals/<int:goal_id>/unlink-mission/<int:mission_id>/', mission_views.unlink_mission_from_goal, name='unlink_mission_from_goal'),
    # -----------------------------------------------------------------------
    # Mission & Strategy hierarchy  (Mission → Strategy → Board)
    # No access restrictions — all authenticated users can use these.
    # -----------------------------------------------------------------------
    path('missions/', mission_views.mission_list, name='mission_list'),
    path('missions/create/', mission_views.create_mission, name='create_mission'),
    path('missions/<int:mission_id>/', mission_views.mission_detail, name='mission_detail'),
    path('missions/<int:mission_id>/edit/', mission_views.edit_mission, name='edit_mission'),
    path('missions/<int:mission_id>/delete/', mission_views.delete_mission, name='delete_mission'),
    path('missions/<int:mission_id>/set-goal/', mission_views.set_mission_goal, name='set_mission_goal'),
    # Top-level strategy shortcut (spec §8.2)
    path('strategies/<int:strategy_id>/', mission_views.strategy_detail_shortcut, name='strategy_detail_shortcut'),
    path('missions/<int:mission_id>/strategies/create/', mission_views.create_strategy, name='create_strategy'),
    path('missions/<int:mission_id>/strategies/<int:strategy_id>/', mission_views.strategy_detail, name='strategy_detail'),
    path('missions/<int:mission_id>/strategies/<int:strategy_id>/edit/', mission_views.edit_strategy, name='edit_strategy'),
    path('missions/<int:mission_id>/strategies/<int:strategy_id>/delete/', mission_views.delete_strategy, name='delete_strategy'),
    path('missions/<int:mission_id>/strategies/<int:strategy_id>/link-board/', mission_views.link_board_to_strategy, name='link_board_to_strategy'),
    path('missions/<int:mission_id>/strategies/<int:strategy_id>/unlink-board/<int:board_id>/', mission_views.unlink_board_from_strategy, name='unlink_board_from_strategy'),
    # --- AJAX endpoints (shared across Goal / Mission / Strategy) ---
    path('api/strategic/<str:level>/<int:pk>/update/', mission_views.post_strategic_update, name='post_strategic_update'),
    path('api/strategic/<str:level>/<int:pk>/follow/', mission_views.toggle_follow, name='toggle_follow'),
    path('api/strategic/<str:level>/<int:pk>/regenerate/', mission_views.regenerate_summary, name='regenerate_summary'),
    path('api/strategic/<str:level>/<int:pk>/members/', mission_views.list_strategic_members, name='list_strategic_members'),
    path('api/strategic/<str:level>/<int:pk>/members/invite/', mission_views.invite_strategic_member, name='invite_strategic_member'),
    path('api/strategic/<str:level>/<int:pk>/members/<int:user_id>/remove/', mission_views.remove_strategic_member, name='remove_strategic_member'),
    # -----------------------------------------------------------------------
    path('boards/<int:board_id>/', views.board_detail, name='board_detail'),
    path('boards/<int:board_id>/analytics/', views.board_analytics, name='board_analytics'),
    path('boards/<int:board_id>/scope-tracking/', views.scope_tracking_dashboard, name='scope_tracking_dashboard'),
    path('boards/<int:board_id>/skill-gaps/', views.skill_gap_dashboard, name='skill_gap_dashboard'),
    path('boards/<int:board_id>/gantt/', views.gantt_chart, name='gantt_chart'),
    path('boards/<int:board_id>/calendar/', views.board_calendar, name='board_calendar'),

    # -----------------------------------------------------------------------
    # Unified Cross-Board Calendar
    # -----------------------------------------------------------------------
    path('calendar/', calendar_views.unified_calendar, name='unified_calendar'),
    path('calendar/events/', calendar_views.unified_calendar_events_api, name='unified_calendar_events_api'),
    path('calendar/create-task/', calendar_views.calendar_create_task, name='calendar_create_task'),
    path('calendar/create-event/', calendar_views.calendar_create_event, name='calendar_create_event'),
    path('calendar/boards/<int:board_id>/columns/', calendar_views.calendar_get_board_columns, name='calendar_get_board_columns'),
    path('calendar/events/<int:event_id>/', calendar_views.calendar_event_detail, name='calendar_event_detail'),
    path('calendar/events/<int:event_id>/delete/', calendar_views.calendar_event_delete, name='calendar_event_delete'),
    # -----------------------------------------------------------------------
    path('boards/<int:board_id>/status-report/', views.board_status_report, name='board_status_report'),
    path('boards/<int:board_id>/prizmbrief/', prizmbrief_views.prizmbrief_setup, name='prizmbrief_setup'),
    path('boards/<int:board_id>/gantt/add-milestone/', views.add_gantt_milestone, name='add_gantt_milestone'),
    path('boards/<int:board_id>/gantt/milestones/<int:task_id>/delete/', views.delete_gantt_milestone, name='delete_gantt_milestone'),
    path('boards/<int:board_id>/edit/', views.edit_board, name='edit_board'),
    path('boards/<int:board_id>/link-strategy/', views.link_board_to_strategy_dashboard, name='link_board_to_strategy_dashboard'),
    path('boards/<int:board_id>/create-task/', views.create_task, name='create_task'),
    path('boards/<int:board_id>/columns/<int:column_id>/create-task/', views.create_task, name='create_task_in_column'),
    path('boards/<int:board_id>/create-column/', views.create_column, name='create_column'),
    path('boards/<int:board_id>/create-label/', views.create_label, name='create_label'),
    path('boards/<int:board_id>/add-member/', views.add_board_member, name='add_board_member'),
    path('boards/<int:board_id>/members/<int:user_id>/remove/', views.remove_board_member, name='remove_board_member'),
    path('boards/<int:board_id>/members/<int:user_id>/role/', invitation_views.update_member_role, name='update_member_role'),
    # Board invitations
    path('boards/<int:board_id>/members/', invitation_views.manage_board_members, name='manage_board_members'),
    path('boards/<int:board_id>/invite/', invitation_views.invite_to_board, name='invite_to_board'),
    path('invite/<uuid:token>/', invitation_views.accept_invitation, name='accept_board_invitation'),
    path('invitations/<int:invitation_id>/revoke/', invitation_views.revoke_invitation, name='revoke_board_invitation'),

    # -----------------------------------------------------------------------
    # Workspace-level member management
    # -----------------------------------------------------------------------
    path('workspace/members/', workspace_member_views.manage_workspace_members, name='manage_workspace_members'),
    path('workspace/members/add/', workspace_member_views.add_workspace_member_view, name='add_workspace_member'),
    path('workspace/members/<int:user_id>/remove/', workspace_member_views.remove_workspace_member_view, name='remove_workspace_member'),
    path('workspace/members/<int:user_id>/role/', workspace_member_views.update_workspace_member_role_view, name='update_workspace_member_role'),
    path('workspace/invite/<uuid:token>/', workspace_member_views.accept_workspace_invitation, name='accept_workspace_invitation'),
    path('workspace/invitations/<int:invitation_id>/revoke/', workspace_member_views.revoke_workspace_invitation_view, name='revoke_workspace_invitation'),

    path('boards/<int:board_id>/delete/', views.delete_board, name='delete_board'),
    path('boards/<int:board_id>/join/', views.join_board, name='join_board'),
    path('boards/<int:board_id>/export/', views.export_board, name='export_board'),
    path('boards/import/', views.import_board, name='import_board'),
    path('tasks/<int:task_id>/', views.task_detail, name='task_detail'),
    path('tasks/<int:task_id>/quick-view/', views.task_quick_view, name='task_quick_view'),
    path('tasks/<int:task_id>/update-status/', views.task_update_status, name='task_update_status'),
    path('tasks/<int:task_id>/update-assignee/', views.task_update_assignee, name='task_update_assignee'),
    path('milestones/<int:milestone_id>/', views.milestone_detail, name='milestone_detail'),
    path('tasks/<int:task_id>/delete/', views.delete_task, name='delete_task'),
    path('tasks/move/', views.move_task, name='move_task'),
    path('tasks/<int:task_id>/update-progress/', views.update_task_progress, name='update_task_progress'),
    path('tasks/<int:task_id>/update-fields/', views.task_update_fields, name='task_update_fields'),
    path('organization-boards/', views.organization_boards, name='organization_boards'),
    path('labels/<int:label_id>/delete/', views.delete_label, name='delete_label'),
    path('columns/<int:column_id>/move/left/', views.move_column, {'direction': 'left'}, name='move_column_left'),    path('columns/<int:column_id>/move/right/', views.move_column, {'direction': 'right'}, name='move_column_right'),
    path('columns/reorder/', views.reorder_columns, name='reorder_columns'),
    path('columns/reorder-multiple/', views.reorder_multiple_columns, name='reorder_multiple_columns'),
    path('columns/<int:column_id>/update/', views.update_column, name='update_column'),
    path('columns/<int:column_id>/update-wip/', views.column_update_wip, name='column_update_wip'),
    path('columns/<int:column_id>/update-color/', views.column_update_color, name='column_update_color'),
    path('columns/<int:column_id>/delete/', views.delete_column, name='delete_column'),    path('boards/<int:board_id>/add-lean-labels/', views.add_lean_labels, name='add_lean_labels'),
    
    # Test page for AI features
    path('test-ai-features/', views.test_ai_features, name='test_ai_features'),    # AI API Endpoints
    path('api/generate-task-description/', api_views.generate_task_description_api, name='generate_task_description_api'),
    path('api/summarize-comments/<int:task_id>/', api_views.summarize_comments_api, name='summarize_comments_api'),
    path('api/download-comment-summary-pdf/<int:task_id>/', api_views.download_comment_summary_pdf, name='download_comment_summary_pdf'),
    path('api/suggest-lss-classification/', api_views.suggest_lss_classification_api, name='suggest_lss_classification_api'),
    path('api/summarize-board-analytics/<int:board_id>/', api_views.summarize_board_analytics_api, name='summarize_board_analytics_api'),
    path('api/download-analytics-pdf/<int:board_id>/', api_views.download_analytics_summary_pdf, name='download_analytics_summary_pdf'),
    path('api/summarize-task-details/<int:task_id>/', api_views.summarize_task_details_api, name='summarize_task_details_api'),

    # Bubble-up AI Summary endpoints (persist summaries at each hierarchy level)
    path('api/generate-task-summary/<int:task_id>/', api_views.generate_task_summary_api, name='generate_task_summary_api'),
    path('api/generate-board-summary/<int:board_id>/', api_views.generate_board_summary_api, name='generate_board_summary_api'),
    path('api/generate-strategy-summary/<int:strategy_id>/', api_views.generate_strategy_summary_api, name='generate_strategy_summary_api'),
    path('api/generate-mission-summary/<int:mission_id>/', api_views.generate_mission_summary_api, name='generate_mission_summary_api'),
    # Polling endpoint — returns current saved summary + stale/queued flags
    path('api/summary-status/<str:level>/<int:obj_id>/', api_views.summary_status_api, name='summary_status_api'),

      # New AI Enhancement API Endpoints
    path('api/suggest-task-priority/', api_views.suggest_task_priority_api, name='suggest_task_priority_api'),
    path('api/predict-deadline/', api_views.predict_deadline_api, name='predict_deadline_api'),
    path('api/suggest-assignee/', api_views.suggest_assignee_api, name='suggest_assignee_api'),
    path('api/recommend-columns/', api_views.recommend_columns_api, name='recommend_columns_api'),
    path('api/generate-board-setup/', api_views.generate_board_setup_api, name='generate_board_setup_api'),
    path('api/suggest-task-breakdown/', api_views.suggest_task_breakdown_api, name='suggest_task_breakdown_api'),
    path('api/analyze-workflow-optimization/', api_views.analyze_workflow_optimization_api, name='analyze_workflow_optimization_api'),    path('api/create-subtasks/', api_views.create_subtasks_api, name='create_subtasks_api'),

    # Checklist API Endpoints
    path('api/create-checklist-items/', api_views.create_checklist_from_breakdown, name='create_checklist_from_breakdown'),
    path('api/checklist-item/<int:item_id>/toggle/', api_views.toggle_checklist_item, name='toggle_checklist_item'),
    path('api/checklist-item/<int:item_id>/delete/', api_views.delete_checklist_item, name='delete_checklist_item'),
    path('api/checklist-items/reorder/', api_views.reorder_checklist_items, name='reorder_checklist_items'),
    path('api/checklist-items/add/', api_views.add_checklist_item, name='add_checklist_item'),

    # Epic API Endpoints
    path('api/create-epic-children/', api_views.create_epic_with_children, name='create_epic_with_children'),
    
    # AI Semantic Search
    path('api/search-tasks-semantic/', api_views.search_tasks_semantic_api, name='search_tasks_semantic_api'),
    
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

    path('board/<int:board_id>/burndown/history/', burndown_views.prediction_history, name='prediction_history'),
    path('board/<int:board_id>/burndown/suggestions/', burndown_views.actionable_suggestions_api, name='actionable_suggestions_api'),

    # Triple Constraint Dashboard (Scope + Cost + Time)
    path('boards/<int:board_id>/triple-constraint/', triple_constraint_views.triple_constraint_dashboard, name='triple_constraint_dashboard'),
    path('boards/<int:board_id>/triple-constraint/set-deadline/', triple_constraint_views.set_project_deadline, name='set_project_deadline'),

    # Board Automations (new engine)
    path('boards/<int:board_id>/automations/', automation_views.automations_page, name='automations_list'),
    path('boards/<int:board_id>/automations/rules/create/', automation_views.rule_create, name='automation_rule_create'),
    path('boards/<int:board_id>/automations/rules/<int:rule_id>/', automation_views.rule_detail, name='automation_rule_detail'),
    path('boards/<int:board_id>/automations/rules/<int:rule_id>/update/', automation_views.rule_update, name='automation_rule_update'),
    path('boards/<int:board_id>/automations/rules/<int:rule_id>/delete/', automation_views.rule_delete, name='automation_rule_delete'),
    path('boards/<int:board_id>/automations/rules/<int:rule_id>/toggle/', automation_views.rule_toggle, name='automation_rule_toggle'),
    path('boards/<int:board_id>/automations/templates/<int:template_id>/use/', automation_views.template_use, name='automation_template_use'),
    # Legacy form-based endpoints (backward compat)
    path('boards/<int:board_id>/automations/create-form/', automation_views.rule_create_form, name='automation_create_form'),
    path('boards/<int:board_id>/automations/<int:automation_id>/delete/', automation_views.rule_delete, name='automation_delete'),
    path('boards/<int:board_id>/automations/<int:automation_id>/toggle/', automation_views.rule_toggle, name='automation_toggle'),
    path('boards/<int:board_id>/automations/templates/<str:template_id>/activate/', automation_views.automation_activate_template, name='automation_activate_template'),

    # Scheduled Automations (legacy + new)
    path('boards/<int:board_id>/scheduled-automations/create/', automation_views.scheduled_rule_create_form, name='scheduled_automation_create'),
    path('boards/<int:board_id>/scheduled-automations/<int:automation_id>/toggle/', automation_views.scheduled_rule_toggle, name='scheduled_automation_toggle'),
    path('boards/<int:board_id>/scheduled-automations/<int:automation_id>/delete/', automation_views.scheduled_rule_delete, name='scheduled_automation_delete'),

    # Task Dependency Management API Endpoints
    path('api/task/<int:task_id>/dependencies/', api_views.get_task_dependencies_api, name='get_task_dependencies_api'),
    path('api/task/<int:task_id>/set-parent/', api_views.set_parent_task_api, name='set_parent_task_api'),
    path('api/task/<int:task_id>/add-related/', api_views.add_related_task_api, name='add_related_task_api'),
    path('api/task/<int:task_id>/analyze-dependencies/', api_views.analyze_task_dependencies_api, name='analyze_task_dependencies_api'),
    path('api/task/<int:task_id>/dependency-tree/', api_views.get_dependency_tree_api, name='get_dependency_tree_api'),
    path('api/board/<int:board_id>/dependency-graph/', api_views.get_board_dependency_graph_api, name='get_board_dependency_graph_api'),
    
    # Gantt Chart API Endpoints
    path('api/tasks/update-dates/', api_views.update_task_dates_api, name='update_task_dates_api'),
    path('api/tasks/<int:task_id>/reschedule/', api_views.reschedule_task_api, name='reschedule_task_api'),
    path('api/tasks/<int:task_id>/update-fields/', api_views.update_task_fields_api, name='update_task_fields_api'),

    # Phase Management API Endpoints
    path('api/board/<int:board_id>/phases/<int:phase_number>/delete/', api_views.delete_phase, name='delete_phase'),
    path('api/board/<int:board_id>/phases/add/', api_views.add_phase, name='add_phase'),
    
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
    path('api/development-plans/<int:plan_id>/update/', api_views.update_skill_development_plan_api, name='update_skill_development_plan_api'),
    path('api/development-plans/<int:plan_id>/delete/', api_views.delete_skill_development_plan_api, name='delete_skill_development_plan_api'),
    path('api/skill-gaps/list/<int:board_id>/', api_views.get_skill_gaps_list_api, name='get_skill_gaps_list_api'),
    path('api/development-plans/<int:board_id>/', api_views.get_development_plans_api, name='get_development_plans_api'),
    
    # File Management for Tasks
    path('tasks/<int:task_id>/files/upload/', views.upload_task_file, name='upload_task_file'),
    path('tasks/<int:task_id>/files/list/', views.list_task_files, name='list_task_files'),
    path('files/<int:file_id>/download/', views.download_task_file, name='download_task_file'),
    path('files/<int:file_id>/delete/', views.delete_task_file, name='delete_task_file'),
    path('files/<int:file_id>/ai-analyze/', views.analyze_task_file, name='analyze_task_file'),
    path('files/<int:file_id>/ai-create-tasks/', views.create_tasks_from_task_file, name='create_tasks_from_task_file'),
    
    # Retrospective URLs
    path('', include('kanban.retrospective_urls')),

    # Budget & ROI Tracking URLs
    path('', include('kanban.budget_urls')),
    
    # Scope Tracking URLs
    path('', include('kanban.scope_urls')),
    
    # AI Coach URLs
    path('', include('kanban.coach_urls')),
    
    # Pre-Mortem AI Analysis URLs
    path('', include('kanban.premortem_urls')),

    # Project Stress Test URLs
    path('', include('kanban.stress_test_urls')),
    
    # Scope Creep Autopsy URLs
    path('', include('kanban.scope_autopsy_urls')),

    # What-If Scenario Analyzer
    path('boards/<int:board_id>/what-if/', whatif_views.whatif_dashboard, name='whatif_dashboard'),
    path('boards/<int:board_id>/what-if/simulate/', whatif_views.whatif_simulate, name='whatif_simulate'),
    path('boards/<int:board_id>/what-if/save/', whatif_views.whatif_save, name='whatif_save'),
    path('boards/<int:board_id>/what-if/history/', whatif_views.whatif_history, name='whatif_history'),
    path('boards/<int:board_id>/what-if/<int:scenario_id>/delete/', whatif_views.whatif_delete, name='whatif_delete'),
    
    # Shadow Board URLs (Parallel Universe Simulator)
    path('boards/<int:board_id>/shadow/', shadow_views.ShadowBoardListView.as_view(), name='shadow_board_list'),
    path('boards/<int:board_id>/shadow/create/', shadow_views.CreateBranchView.as_view(), name='create_shadow_branch'),
    path('boards/<int:board_id>/shadow/<int:branch_id>/', shadow_views.BranchDetailView.as_view(), name='shadow_branch_detail'),
    path('boards/<int:board_id>/shadow/<int:branch_id>/commit/', shadow_views.CommitBranchView.as_view(), name='commit_shadow_branch'),
    path('api/boards/<int:board_id>/shadow/conflicts/', shadow_views.merge_conflict_check, name='merge_conflict_check'),
    path('api/boards/<int:board_id>/shadow/branch/<int:branch_id>/snapshots/', shadow_views.get_branch_snapshots, name='get_branch_snapshots'),
    path('api/boards/<int:board_id>/shadow/branches/<int:branch_a_id>/<int:branch_b_id>/', shadow_views.get_branches_comparison, name='get_branches_comparison'),
    path('api/boards/<int:board_id>/shadow/<int:branch_id>/toggle-star/', shadow_views.toggle_star_branch, name='toggle_star_branch'),
    path('api/boards/<int:board_id>/shadow/<int:branch_id>/delete/', shadow_views.delete_branch, name='delete_shadow_branch'),
    path('api/boards/<int:board_id>/shadow/<int:branch_id>/restore/', shadow_views.restore_branch, name='restore_shadow_branch'),
    path('api/boards/<int:board_id>/shadow/<int:branch_id>/link-scenario/', shadow_views.link_scenario_to_branch, name='link_scenario_to_branch'),
    path('boards/<int:board_id>/shadow/promote-scenario/', shadow_views.promote_scenario_to_branch, name='promote_scenario'),
    
    # Resource Leveling URLs
    path('api/resource-leveling/', include('kanban.resource_leveling_urls')),
    
    # Conflict Detection & Resolution URLs
    path('conflicts/', conflict_views.conflict_dashboard, name='conflict_dashboard'),
    path('conflicts/<int:conflict_id>/', conflict_views.conflict_detail, name='conflict_detail'),
    path('conflicts/<int:conflict_id>/resolutions/<int:resolution_id>/apply/', conflict_views.apply_resolution, name='apply_resolution'),
    path('conflicts/<int:conflict_id>/ignore/', conflict_views.ignore_conflict, name='ignore_conflict'),
    path('conflicts/<int:conflict_id>/feedback/', conflict_views.conflict_feedback, name='conflict_feedback'),
    path('conflicts/trigger/all/', conflict_views.trigger_detection_all, name='trigger_detection_all'),
    path('conflicts/trigger/<int:board_id>/', conflict_views.trigger_detection, name='trigger_detection_board'),
    path('conflicts/notifications/<int:notification_id>/acknowledge/', conflict_views.acknowledge_notification, name='acknowledge_notification'),
    path('conflicts/analytics/', conflict_views.conflict_analytics, name='conflict_analytics'),
    
    # Legacy Permission Management URLs removed in RBAC Phase 1.
    # New RBAC uses django-rules predicates defined in kanban/permissions.py.

    # Onboarding v2 — AI-powered workspace setup
    path('onboarding/', onboarding_views.onboarding_welcome, name='onboarding_welcome'),
    path('onboarding/goal/', onboarding_views.onboarding_goal_input, name='onboarding_goal'),
    path('onboarding/generating/', onboarding_views.onboarding_generating, name='onboarding_generating'),
    path('onboarding/status/', onboarding_views.onboarding_status, name='onboarding_status'),
    path('onboarding/review/', onboarding_views.onboarding_review, name='onboarding_review'),
    path('onboarding/commit/', onboarding_views.onboarding_commit, name='onboarding_commit'),
    path('onboarding/start-over/', onboarding_views.onboarding_start_over, name='onboarding_start_over'),
    path('onboarding/skip/', onboarding_views.onboarding_skip, name='onboarding_skip'),
    path('onboarding/invite/', onboarding_views.onboarding_invite, name='onboarding_invite'),
    path('onboarding/demo/', onboarding_views.onboarding_explore_demo, name='onboarding_explore_demo'),
    path('onboarding/validate/', onboarding_views.onboarding_validate, name='onboarding_validate'),
    path('onboarding/regenerate-children/', onboarding_views.onboarding_regenerate_children, name='onboarding_regenerate_children'),

    # Demo mode toggle (v2)
    path('toggle-demo-mode/', views.toggle_demo_mode, name='toggle_demo_mode'),

    # Workspace context switcher
    path('switch-workspace/', views.switch_workspace, name='switch_workspace'),
    path('rename-workspace/', views.rename_workspace, name='rename_workspace'),
    path('delete-workspace/', views.delete_workspace, name='delete_workspace'),
    path('workspace-selection/', views.workspace_selection, name='workspace_selection'),

    # Workspace preset settings (Org Admin)
    path('settings/workspace/', views.workspace_preset_settings, name='workspace_preset_settings'),
    # Board-level preset override (Board Owner / Org Admin) — AJAX endpoint
    path('boards/<int:board_id>/preset/', views.board_preset_update, name='board_preset_update'),

    # -----------------------------------------------------------------------
    # Living Commitment Protocols (Anti-Roadmap)
    # -----------------------------------------------------------------------
    path('boards/<int:board_id>/commitments/', commitment_views.commitment_dashboard, name='commitment_dashboard'),
    path('boards/<int:board_id>/commitments/new/', commitment_views.commitment_create, name='commitment_create'),
    path('boards/<int:board_id>/commitments/<int:commitment_id>/', commitment_views.commitment_detail, name='commitment_detail'),
    path('boards/<int:board_id>/commitments/<int:commitment_id>/bet/', commitment_views.commitment_place_bet, name='commitment_place_bet'),
    path('boards/<int:board_id>/commitments/<int:commitment_id>/signal/', commitment_views.commitment_signal_manual, name='commitment_signal_manual'),
    path('boards/<int:board_id>/negotiations/<int:negotiation_id>/', commitment_views.negotiation_session_detail, name='negotiation_session_detail'),
    path('boards/<int:board_id>/negotiations/<int:negotiation_id>/resolve/', commitment_views.negotiation_resolve, name='negotiation_resolve'),
    # Commitment API endpoints (JSON, used by JS auto-refresh and Chart.js)
    path('api/boards/<int:board_id>/commitments/', commitment_views.commitments_list_api, name='commitments_list_api'),
    path('api/boards/<int:board_id>/commitments/<int:commitment_id>/curve/', commitment_views.commitment_curve_api, name='commitment_curve_api'),

    # -----------------------------------------------------------------------
    # Spectra Smart Access Request System
    # -----------------------------------------------------------------------
    path('access-requests/submit/', access_request_views.submit_access_request, name='submit_access_request'),
    path('access-requests/mine/', access_request_views.my_access_requests, name='my_access_requests'),
    path('access-requests/<int:request_id>/review/', access_request_views.review_access_request, name='review_access_request'),
    path('access-requests/<int:request_id>/cancel/', access_request_views.cancel_access_request, name='cancel_access_request'),
    path('access-requests/pending/', access_request_views.pending_access_requests, name='pending_access_requests'),
    path('api/access-requests/<int:request_id>/approve/', access_request_views.api_approve_access_request, name='api_approve_access_request'),
    path('api/access-requests/<int:request_id>/deny/', access_request_views.api_deny_access_request, name='api_deny_access_request'),
    path('api/access-requests/pending-count/', access_request_views.get_pending_access_request_count, name='get_pending_access_request_count'),
    path('api/boards/<int:board_id>/commitments/<int:commitment_id>/market/', commitment_views.commitment_market_api, name='commitment_market_api'),

    # -----------------------------------------------------------------------
    # My Favorites
    # -----------------------------------------------------------------------
    path('api/favorites/toggle/', favorite_views.toggle_favorite, name='toggle_favorite'),
    path('api/favorites/reorder/', favorite_views.reorder_favorites, name='reorder_favorites'),
    path('api/favorites/list/', favorite_views.favorites_list_api, name='favorites_list_api'),

    # -----------------------------------------------------------------------
    # Goal-Aware Analytics API Endpoints
    # -----------------------------------------------------------------------
    path('api/boards/<int:board_id>/classify/', api_views.classify_board_api, name='classify_board_api'),
    path('api/boards/<int:board_id>/confirm-type/', api_views.confirm_board_type_api, name='confirm_board_type_api'),
    path('api/boards/<int:board_id>/generate-narrative/', api_views.generate_board_narrative_api, name='generate_board_narrative_api'),
    path('api/strategic/<str:record_type>/<int:record_id>/portfolio-analytics/', api_views.portfolio_analytics_api, name='portfolio_analytics_api'),
    path('api/strategic/<str:record_type>/<int:record_id>/generate-portfolio-narrative/', api_views.generate_portfolio_narrative_api, name='generate_portfolio_narrative_api'),
    path('api/goals/<int:goal_id>/generate-proxy-metrics/', api_views.generate_proxy_metrics_api, name='generate_proxy_metrics_api'),
    path('api/goals/<int:goal_id>/proxy-metrics/<int:metric_id>/update-value/', api_views.update_proxy_metric_value_api, name='update_proxy_metric_value_api'),
]