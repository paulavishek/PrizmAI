"""
Sandbox Views - persistent personal demo system.

Each real user gets their own private copy of the demo template boards.
The sandbox persists as long as the user's account. No timer, no expiry.
Master Demo Template boards (is_official_demo_board=True) are NEVER modified.

Endpoints:
  POST /toggle-demo-mode/           - provision sandbox (async via Celery) or re-enter existing
  POST /demo/reset-mine/            - wipe user's sandbox and re-provision
  GET  /sandbox/status/             - JSON status for in-app banner
"""
import logging

from django.contrib.auth.decorators import login_required
from django.db import models
from django.http import JsonResponse
from django.shortcuts import redirect
from django.utils import timezone
from django.views.decorators.http import require_http_methods

from kanban.utils.demo_protection import allow_demo_writes

logger = logging.getLogger(__name__)


# ── Helpers ───────────────────────────────────────────────────────────────────

def _duplicate_board(template_board, user):
    """
    Deep-copy a single template board for a sandbox user.
    Returns the new Board instance.

    Per spec Edge Case 3:
    - Set pk=None and id=None on every record before .save()
    - Assign sandbox user as owner
    - Set is_official_demo_board = False on all copies
    - Do NOT copy BoardMembership records — create a fresh owner membership
    """
    from kanban.models import Board, BoardMembership, Column, TaskLabel, Task, Comment

    # --- Board ---
    # Build a fresh board from the template's field values, leaving M2M until after save
    new_board = Board(
        name=template_board.name,
        description=template_board.description,
        organization=None,                      # ← sandbox boards are user-owned, not demo org
        owner=user,
        created_by=user,
        is_official_demo_board=False,          # ← critical: not a template
        is_seed_demo_data=False,
        is_sandbox_copy=True,                    # ← tags this as a sandbox copy
        cloned_from=template_board,              # ← track which template it was cloned from
        strategy=None,                          # Do not inherit — mission tree uses _template_to_sandbox mapping
        num_phases=template_board.num_phases,
        task_prefix=template_board.task_prefix,
        project_type=template_board.project_type,
        # Copy baseline for Scope Creep Index
        baseline_task_count=template_board.baseline_task_count,
        baseline_complexity_total=template_board.baseline_complexity_total,
        baseline_set_date=template_board.baseline_set_date,
    )
    new_board.save()

    # Fresh owner membership for the real user
    BoardMembership.objects.create(board=new_board, user=user, role='owner')

    # Copy demo persona memberships so assignees resolve correctly
    for membership in template_board.memberships.select_related('user').all():
        if membership.user != user:
            BoardMembership.objects.get_or_create(
                board=new_board, user=membership.user,
                defaults={'role': 'member'},
            )

    # --- TaskLabels (board FK) ---
    label_map = {}  # old label pk → new label instance
    for label in template_board.labels.all():
        new_label = TaskLabel(
            name=label.name,
            color=label.color,
            board=new_board,
            category=label.category,
        )
        new_label.save()
        label_map[label.pk] = new_label

    # --- Columns ---
    column_map = {}  # old column pk → new column instance
    for col in template_board.columns.order_by('position'):
        new_col = Column(
            name=col.name,
            board=new_board,
            position=col.position,
            wip_limit=col.wip_limit,
        )
        new_col.save()
        column_map[col.pk] = new_col

    # --- Tasks ---
    task_map = {}  # old task pk → new task instance
    task_template_dates = {}  # new task pk → template task updated_at
    for task in (
        Task.objects
        .filter(column__board=template_board)
        .select_related('column', 'assigned_to')
        .order_by('column__position', 'position')
    ):
        new_col = column_map.get(task.column.pk)
        if new_col is None:
            continue

        new_task = Task(
            title=task.title,
            description=task.description,
            column=new_col,
            position=task.position,
            priority=task.priority,
            progress=task.progress,
            due_date=task.due_date,
            start_date=task.start_date,
            phase=task.phase,
            item_type=task.item_type,
            milestone_status=task.milestone_status,
            created_by=user,
            # Keep original demo persona assignment (alex/sam/jordan)
            assigned_to=task.assigned_to,
            risk_level=task.risk_level,
            risk_likelihood=task.risk_likelihood,
            risk_impact=task.risk_impact,
            complexity_score=task.complexity_score,
            # Clear AI and personal operational data
            ai_summary=None,
            ai_summary_generated_at=None,
            ai_risk_score=None,
            ai_recommendations=None,
        )
        new_task.save()
        task_map[task.pk] = new_task
        task_template_dates[new_task.pk] = task.updated_at

        # Re-assign labels via new label instances
        for old_label in task.labels.all():
            new_lab = label_map.get(old_label.pk)
            if new_lab:
                new_task.labels.add(new_lab)

    # --- Comments (keep demo comments for realism) ---
    for task in Task.objects.filter(column__board=template_board).select_related('column'):
        new_task = task_map.get(task.pk)
        if new_task is None:
            continue
        for comment in task.comments.order_by('created_at'):
            Comment.objects.create(
                task=new_task,
                user=user,
                content=comment.content,
            )

    # --- ChecklistItems ---
    from kanban.models import ChecklistItem
    for old_task in Task.objects.filter(column__board=template_board):
        new_task = task_map.get(old_task.pk)
        if new_task is None:
            continue
        for item in old_task.checklist_items.order_by('position'):
            ChecklistItem.objects.create(
                task=new_task,
                title=item.title,
                description=item.description,
                is_completed=item.is_completed,
                completed_at=item.completed_at,
                position=item.position,
                estimated_effort=item.estimated_effort,
                priority=item.priority,
                source=item.source,
            )

    # --- Task-to-Task Relationships (parent_task, dependencies, related, milestones) ---
    for old_pk, new_task in task_map.items():
        old_task = Task.objects.get(pk=old_pk)
        updated = False

        # Parent-child relationships (subtasks)
        if old_task.parent_task_id and old_task.parent_task_id in task_map:
            new_task.parent_task = task_map[old_task.parent_task_id]
            updated = True

        # Milestone positioning (position_after_task)
        if old_task.position_after_task_id and old_task.position_after_task_id in task_map:
            new_task.position_after_task = task_map[old_task.position_after_task_id]
            updated = True

        if updated:
            new_task.save(update_fields=['parent_task', 'position_after_task'])

        # Gantt chart dependencies (M2M)
        for dep in old_task.dependencies.all():
            if dep.pk in task_map:
                new_task.dependencies.add(task_map[dep.pk])

        # Related tasks (M2M)
        for related in old_task.related_tasks.all():
            if related.pk in task_map:
                new_task.related_tasks.add(task_map[related.pk])

    # --- Budget + TaskCost (for CPI calculation) ---
    try:
        from kanban.budget_models import ProjectBudget, TaskCost
        template_budget = ProjectBudget.objects.filter(board=template_board).first()
        if template_budget:
            ProjectBudget.objects.create(
                board=new_board,
                allocated_budget=template_budget.allocated_budget,
                currency=template_budget.currency,
                allocated_hours=template_budget.allocated_hours,
                warning_threshold=template_budget.warning_threshold,
                critical_threshold=template_budget.critical_threshold,
                ai_optimization_enabled=template_budget.ai_optimization_enabled,
                created_by=user,
            )
            for tc in TaskCost.objects.filter(task__column__board=template_board).select_related('task'):
                new_task = task_map.get(tc.task_id)
                if new_task:
                    TaskCost.objects.create(
                        task=new_task,
                        estimated_cost=tc.estimated_cost,
                        estimated_hours=tc.estimated_hours,
                        actual_cost=tc.actual_cost,
                        hourly_rate=tc.hourly_rate,
                        resource_cost=tc.resource_cost,
                    )
    except Exception:
        pass  # Budget copying is best-effort; don't block provisioning

    # --- Commitment Protocols (with signals, bets, credibility) ---
    try:
        from kanban.commitment_models import (
            CommitmentProtocol, ConfidenceSignal, CommitmentBet, UserCredibilityScore,
        )
        for proto in CommitmentProtocol.objects.filter(board=template_board):
            old_proto_pk = proto.pk
            new_proto = CommitmentProtocol(
                board=new_board,
                title=proto.title,
                description=proto.description,
                target_date=proto.target_date,
                initial_confidence=proto.initial_confidence,
                current_confidence=proto.current_confidence,
                confidence_halflife_days=proto.confidence_halflife_days,
                decay_model=proto.decay_model,
                status=proto.status,
                created_by=proto.created_by,
                baseline_snapshot=proto.baseline_snapshot,
                last_signal_date=proto.last_signal_date,
                ai_reasoning=proto.ai_reasoning,
                negotiation_threshold=proto.negotiation_threshold,
                token_pool_per_member=proto.token_pool_per_member,
            )
            new_proto.save()

            # Preserve created_at and last_decay_calculation
            CommitmentProtocol.objects.filter(pk=new_proto.pk).update(
                created_at=proto.created_at,
                last_decay_calculation=proto.last_decay_calculation,
            )

            # Link tasks via task_map
            for old_task in proto.linked_tasks.all():
                new_task = task_map.get(old_task.pk)
                if new_task:
                    new_proto.linked_tasks.add(new_task)

            # Copy stakeholders directly (demo personas + sandbox user)
            new_proto.stakeholders.set(proto.stakeholders.all())

            # Copy signals
            for sig in ConfidenceSignal.objects.filter(protocol_id=old_proto_pk):
                related = task_map.get(sig.related_task_id) if sig.related_task_id else None
                new_sig = ConfidenceSignal.objects.create(
                    protocol=new_proto,
                    signal_type=sig.signal_type,
                    signal_value=sig.signal_value,
                    description=sig.description,
                    confidence_before=sig.confidence_before,
                    confidence_after=sig.confidence_after,
                    ai_generated=sig.ai_generated,
                    recorded_by=sig.recorded_by,
                    related_task=related,
                )
                ConfidenceSignal.objects.filter(pk=new_sig.pk).update(
                    timestamp=sig.timestamp,
                )

            # Copy bets
            for bet in CommitmentBet.objects.filter(protocol_id=old_proto_pk):
                new_bet = CommitmentBet.objects.create(
                    protocol=new_proto,
                    bettor=bet.bettor,
                    tokens_wagered=bet.tokens_wagered,
                    confidence_estimate=bet.confidence_estimate,
                    reasoning=bet.reasoning,
                    is_anonymous=bet.is_anonymous,
                    resolved=bet.resolved,
                    resolution_correct=bet.resolution_correct,
                    credibility_delta=bet.credibility_delta,
                )
                CommitmentBet.objects.filter(pk=new_bet.pk).update(
                    placed_at=bet.placed_at,
                )

            # Ensure credibility scores exist for bettors
            for bet in CommitmentBet.objects.filter(protocol_id=old_proto_pk):
                try:
                    old_cred = UserCredibilityScore.objects.get(user=bet.bettor)
                    UserCredibilityScore.objects.get_or_create(
                        user=bet.bettor,
                        defaults={
                            'score': old_cred.score,
                            'total_bets': old_cred.total_bets,
                            'correct_bets': old_cred.correct_bets,
                            'tokens_remaining': old_cred.tokens_remaining,
                        },
                    )
                except UserCredibilityScore.DoesNotExist:
                    pass
    except Exception:
        pass  # Commitment copying is best-effort; don't block provisioning

    # --- Time Entries (for time tracking views) ---
    try:
        from kanban.budget_models import TimeEntry
        for te in TimeEntry.objects.filter(task__column__board=template_board).select_related('task'):
            new_task = task_map.get(te.task_id)
            if new_task:
                new_te = TimeEntry.objects.create(
                    task=new_task,
                    user=te.user,
                    hours_spent=te.hours_spent,
                    work_date=te.work_date,
                    description=te.description,
                )
                TimeEntry.objects.filter(pk=new_te.pk).update(created_at=te.created_at)
    except Exception:
        pass

    # --- ProjectROI ---
    try:
        from kanban.budget_models import ProjectROI
        for roi in ProjectROI.objects.filter(board=template_board):
            new_roi = ProjectROI.objects.create(
                board=new_board,
                expected_value=roi.expected_value,
                realized_value=roi.realized_value,
                snapshot_date=roi.snapshot_date,
                total_cost=roi.total_cost,
                roi_percentage=roi.roi_percentage,
                completed_tasks=roi.completed_tasks,
                total_tasks=roi.total_tasks,
                ai_insights=roi.ai_insights,
                ai_risk_score=roi.ai_risk_score,
                created_by=roi.created_by,
            )
            ProjectROI.objects.filter(pk=new_roi.pk).update(created_at=roi.created_at)
    except Exception:
        pass

    # --- Burndown / Velocity ---
    try:
        from kanban.burndown_models import (
            TeamVelocitySnapshot, BurndownPrediction, BurndownAlert, SprintMilestone,
        )

        velocity_map = {}
        for vs in TeamVelocitySnapshot.objects.filter(board=template_board):
            old_pk = vs.pk
            new_vs = TeamVelocitySnapshot.objects.create(
                board=new_board,
                period_start=vs.period_start,
                period_end=vs.period_end,
                period_type=vs.period_type,
                tasks_completed=vs.tasks_completed,
                story_points_completed=vs.story_points_completed,
                hours_completed=vs.hours_completed,
                active_team_members=vs.active_team_members,
                team_member_list=vs.team_member_list,
                tasks_reopened=vs.tasks_reopened,
                quality_score=vs.quality_score,
                calculated_by=vs.calculated_by,
            )
            TeamVelocitySnapshot.objects.filter(pk=new_vs.pk).update(created_at=vs.created_at)
            velocity_map[old_pk] = new_vs

        prediction_map = {}
        for bp in BurndownPrediction.objects.filter(board=template_board):
            old_pk = bp.pk
            new_bp = BurndownPrediction.objects.create(
                board=new_board,
                prediction_type=bp.prediction_type,
                total_tasks=bp.total_tasks,
                completed_tasks=bp.completed_tasks,
                remaining_tasks=bp.remaining_tasks,
                total_story_points=bp.total_story_points,
                completed_story_points=bp.completed_story_points,
                remaining_story_points=bp.remaining_story_points,
                current_velocity=bp.current_velocity,
                average_velocity=bp.average_velocity,
                velocity_std_dev=bp.velocity_std_dev,
                velocity_trend=bp.velocity_trend,
                predicted_completion_date=bp.predicted_completion_date,
                completion_date_lower_bound=bp.completion_date_lower_bound,
                completion_date_upper_bound=bp.completion_date_upper_bound,
                days_until_completion_estimate=bp.days_until_completion_estimate,
                days_margin_of_error=bp.days_margin_of_error,
                confidence_percentage=bp.confidence_percentage,
                prediction_confidence_score=bp.prediction_confidence_score,
                delay_probability=bp.delay_probability,
                risk_level=bp.risk_level,
                target_completion_date=bp.target_completion_date,
                will_meet_target=bp.will_meet_target,
                days_ahead_behind_target=bp.days_ahead_behind_target,
                burndown_curve_data=bp.burndown_curve_data,
                confidence_bands_data=bp.confidence_bands_data,
                velocity_history_data=bp.velocity_history_data,
                actionable_suggestions=bp.actionable_suggestions,
                model_parameters=bp.model_parameters,
            )
            BurndownPrediction.objects.filter(pk=new_bp.pk).update(prediction_date=bp.prediction_date)
            prediction_map[old_pk] = new_bp
            # M2M: based_on_velocity_snapshots
            for old_vs in bp.based_on_velocity_snapshots.all():
                mapped = velocity_map.get(old_vs.pk)
                if mapped:
                    new_bp.based_on_velocity_snapshots.add(mapped)

        for ba in BurndownAlert.objects.filter(board=template_board).select_related('prediction'):
            new_pred = prediction_map.get(ba.prediction_id)
            if new_pred:
                new_ba = BurndownAlert.objects.create(
                    prediction=new_pred,
                    board=new_board,
                    alert_type=ba.alert_type,
                    severity=ba.severity,
                    status=ba.status,
                    title=ba.title,
                    message=ba.message,
                    metric_value=ba.metric_value,
                    threshold_value=ba.threshold_value,
                    suggested_actions=ba.suggested_actions,
                    acknowledged_by=ba.acknowledged_by,
                    acknowledged_at=ba.acknowledged_at,
                    resolved_at=ba.resolved_at,
                )
                BurndownAlert.objects.filter(pk=new_ba.pk).update(created_at=ba.created_at)

        for sm in SprintMilestone.objects.filter(board=template_board):
            new_sm = SprintMilestone.objects.create(
                board=new_board,
                name=sm.name,
                description=sm.description,
                target_date=sm.target_date,
                actual_date=sm.actual_date,
                target_tasks_completed=sm.target_tasks_completed,
                target_story_points=sm.target_story_points,
                is_completed=sm.is_completed,
                completion_percentage=sm.completion_percentage,
                created_by=sm.created_by,
            )
            SprintMilestone.objects.filter(pk=new_sm.pk).update(created_at=sm.created_at)
    except Exception:
        pass

    # --- Scope Tracking ---
    try:
        from kanban.models import ScopeChangeSnapshot, ScopeCreepAlert

        scope_snapshot_map = {}
        # Copy non-baseline snapshots first, then fix self-refs
        for ss in ScopeChangeSnapshot.objects.filter(board=template_board).order_by('pk'):
            old_pk = ss.pk
            new_ss = ScopeChangeSnapshot.objects.create(
                board=new_board,
                total_tasks=ss.total_tasks,
                total_complexity_points=ss.total_complexity_points,
                avg_complexity=ss.avg_complexity,
                high_priority_tasks=ss.high_priority_tasks,
                urgent_priority_tasks=ss.urgent_priority_tasks,
                todo_tasks=ss.todo_tasks,
                in_progress_tasks=ss.in_progress_tasks,
                completed_tasks=ss.completed_tasks,
                is_baseline=ss.is_baseline,
                scope_change_percentage=ss.scope_change_percentage,
                complexity_change_percentage=ss.complexity_change_percentage,
                ai_analysis=ss.ai_analysis,
                predicted_delay_days=ss.predicted_delay_days,
                created_by=ss.created_by,
                snapshot_type=ss.snapshot_type,
                notes=ss.notes,
            )
            ScopeChangeSnapshot.objects.filter(pk=new_ss.pk).update(snapshot_date=ss.snapshot_date)
            scope_snapshot_map[old_pk] = new_ss
        # Fix baseline_snapshot self-refs
        for old_pk, new_ss in scope_snapshot_map.items():
            old_ss = ScopeChangeSnapshot.objects.get(pk=old_pk)
            if old_ss.baseline_snapshot_id and old_ss.baseline_snapshot_id in scope_snapshot_map:
                new_ss.baseline_snapshot = scope_snapshot_map[old_ss.baseline_snapshot_id]
                new_ss.save(update_fields=['baseline_snapshot'])

        for sca in ScopeCreepAlert.objects.filter(board=template_board).select_related('snapshot'):
            new_snap = scope_snapshot_map.get(sca.snapshot_id)
            if new_snap:
                new_sca = ScopeCreepAlert.objects.create(
                    board=new_board,
                    snapshot=new_snap,
                    severity=sca.severity,
                    status=sca.status,
                    scope_increase_percentage=sca.scope_increase_percentage,
                    complexity_increase_percentage=sca.complexity_increase_percentage,
                    tasks_added=sca.tasks_added,
                    predicted_delay_days=sca.predicted_delay_days,
                    timeline_at_risk=sca.timeline_at_risk,
                    recommendations=sca.recommendations,
                    ai_summary=sca.ai_summary,
                    acknowledged_by=sca.acknowledged_by,
                    acknowledged_at=sca.acknowledged_at,
                    resolved_by=sca.resolved_by,
                    resolved_at=sca.resolved_at,
                    resolution_notes=sca.resolution_notes,
                )
                ScopeCreepAlert.objects.filter(pk=new_sca.pk).update(detected_at=sca.detected_at)
    except Exception:
        pass

    # --- Skill Profiles & Gaps ---
    try:
        from kanban.models import TeamSkillProfile, SkillGap, SkillDevelopmentPlan

        tsp = TeamSkillProfile.objects.filter(board=template_board).first()
        if tsp:
            new_tsp = TeamSkillProfile.objects.create(
                board=new_board,
                skill_inventory=tsp.skill_inventory,
                total_capacity_hours=tsp.total_capacity_hours,
                utilized_capacity_hours=tsp.utilized_capacity_hours,
                last_analysis=tsp.last_analysis,
            )

        skill_gap_map = {}
        for sg in SkillGap.objects.filter(board=template_board):
            old_pk = sg.pk
            new_sg = SkillGap.objects.create(
                board=new_board,
                skill_name=sg.skill_name,
                proficiency_level=sg.proficiency_level,
                required_count=sg.required_count,
                available_count=sg.available_count,
                gap_count=sg.gap_count,
                severity=sg.severity,
                status=sg.status,
                sprint_period_start=sg.sprint_period_start,
                sprint_period_end=sg.sprint_period_end,
                ai_recommendations=sg.ai_recommendations,
                estimated_impact_hours=sg.estimated_impact_hours,
                confidence_score=sg.confidence_score,
                resolved_at=sg.resolved_at,
                acknowledged_by=sg.acknowledged_by,
            )
            SkillGap.objects.filter(pk=new_sg.pk).update(identified_at=sg.identified_at)
            skill_gap_map[old_pk] = new_sg
            # M2M: affected_tasks
            for old_task in sg.affected_tasks.all():
                mapped = task_map.get(old_task.pk)
                if mapped:
                    new_sg.affected_tasks.add(mapped)

        for sdp in SkillDevelopmentPlan.objects.filter(board=template_board):
            new_gap = skill_gap_map.get(sdp.skill_gap_id)
            if new_gap:
                new_sdp = SkillDevelopmentPlan.objects.create(
                    skill_gap=new_gap,
                    board=new_board,
                    plan_type=sdp.plan_type,
                    title=sdp.title,
                    description=sdp.description,
                    target_skill=sdp.target_skill,
                    target_proficiency=sdp.target_proficiency,
                    start_date=sdp.start_date,
                    target_completion_date=sdp.target_completion_date,
                    actual_completion_date=sdp.actual_completion_date,
                    estimated_cost=sdp.estimated_cost,
                    estimated_hours=sdp.estimated_hours,
                    status=sdp.status,
                    progress_percentage=sdp.progress_percentage,
                    expected_impact=sdp.expected_impact,
                    actual_impact=sdp.actual_impact,
                    success_metrics=sdp.success_metrics,
                    created_by=sdp.created_by,
                    assigned_to=sdp.assigned_to,
                    ai_suggested=sdp.ai_suggested,
                    ai_confidence=sdp.ai_confidence,
                )
                SkillDevelopmentPlan.objects.filter(pk=new_sdp.pk).update(created_at=sdp.created_at)
                new_sdp.target_users.set(sdp.target_users.all())
    except Exception:
        pass

    # --- Retrospectives ---
    try:
        from kanban.retrospective_models import (
            ProjectRetrospective, LessonLearned, ImprovementMetric,
            RetrospectiveActionItem, RetrospectiveTrend,
        )

        retro_map = {}
        for retro in ProjectRetrospective.objects.filter(board=template_board).order_by('pk'):
            old_pk = retro.pk
            prev_retro = retro_map.get(retro.previous_retrospective_id) if retro.previous_retrospective_id else None
            new_retro = ProjectRetrospective.objects.create(
                board=new_board,
                title=retro.title,
                retrospective_type=retro.retrospective_type,
                status=retro.status,
                period_start=retro.period_start,
                period_end=retro.period_end,
                metrics_snapshot=retro.metrics_snapshot,
                what_went_well=retro.what_went_well,
                what_needs_improvement=retro.what_needs_improvement,
                lessons_learned=retro.lessons_learned,
                key_achievements=retro.key_achievements,
                challenges_faced=retro.challenges_faced,
                improvement_recommendations=retro.improvement_recommendations,
                overall_sentiment_score=retro.overall_sentiment_score,
                team_morale_indicator=retro.team_morale_indicator,
                previous_retrospective=prev_retro,
                performance_trend=retro.performance_trend,
                ai_generated_at=retro.ai_generated_at,
                ai_confidence_score=retro.ai_confidence_score,
                ai_model_used=retro.ai_model_used,
                team_notes=retro.team_notes,
                team_feedback_on_ai=retro.team_feedback_on_ai,
                created_by=retro.created_by,
                finalized_by=retro.finalized_by,
                finalized_at=retro.finalized_at,
                meeting_transcript=None,  # Transcripts are board-specific, skip cross-ref
            )
            ProjectRetrospective.objects.filter(pk=new_retro.pk).update(created_at=retro.created_at)
            retro_map[old_pk] = new_retro

        lesson_map = {}
        for ll in LessonLearned.objects.filter(board=template_board):
            old_pk = ll.pk
            new_retro = retro_map.get(ll.retrospective_id)
            if new_retro:
                new_ll = LessonLearned.objects.create(
                    retrospective=new_retro,
                    board=new_board,
                    title=ll.title,
                    description=ll.description,
                    category=ll.category,
                    priority=ll.priority,
                    trigger_event=ll.trigger_event,
                    impact_description=ll.impact_description,
                    recommended_action=ll.recommended_action,
                    action_owner=ll.action_owner,
                    status=ll.status,
                    implementation_date=ll.implementation_date,
                    validation_date=ll.validation_date,
                    expected_benefit=ll.expected_benefit,
                    actual_benefit=ll.actual_benefit,
                    success_metrics=ll.success_metrics,
                    ai_suggested=ll.ai_suggested,
                    ai_confidence=ll.ai_confidence,
                    is_recurring_issue=ll.is_recurring_issue,
                    recurrence_count=ll.recurrence_count,
                )
                LessonLearned.objects.filter(pk=new_ll.pk).update(created_at=ll.created_at)
                lesson_map[old_pk] = new_ll
        # Fix related_lessons M2M (self-referential)
        for old_pk, new_ll in lesson_map.items():
            old_ll = LessonLearned.objects.get(pk=old_pk)
            for rel in old_ll.related_lessons.all():
                mapped = lesson_map.get(rel.pk)
                if mapped:
                    new_ll.related_lessons.add(mapped)

        for im in ImprovementMetric.objects.filter(board=template_board):
            new_retro = retro_map.get(im.retrospective_id)
            if new_retro:
                new_im = ImprovementMetric.objects.create(
                    board=new_board,
                    retrospective=new_retro,
                    metric_type=im.metric_type,
                    metric_name=im.metric_name,
                    description=im.description,
                    metric_value=im.metric_value,
                    previous_value=im.previous_value,
                    target_value=im.target_value,
                    change_amount=im.change_amount,
                    change_percentage=im.change_percentage,
                    trend=im.trend,
                    unit_of_measure=im.unit_of_measure,
                    higher_is_better=im.higher_is_better,
                    measured_at=im.measured_at,
                )
                ImprovementMetric.objects.filter(pk=new_im.pk).update(created_at=im.created_at)

        for rai in RetrospectiveActionItem.objects.filter(board=template_board):
            new_retro = retro_map.get(rai.retrospective_id)
            new_lesson = lesson_map.get(rai.related_lesson_id) if rai.related_lesson_id else None
            new_task = task_map.get(rai.related_task_id) if rai.related_task_id else None
            if new_retro:
                new_rai = RetrospectiveActionItem.objects.create(
                    retrospective=new_retro,
                    board=new_board,
                    title=rai.title,
                    description=rai.description,
                    action_type=rai.action_type,
                    status=rai.status,
                    assigned_to=rai.assigned_to,
                    target_completion_date=rai.target_completion_date,
                    actual_completion_date=rai.actual_completion_date,
                    priority=rai.priority,
                    expected_impact=rai.expected_impact,
                    actual_impact=rai.actual_impact,
                    blocked_reason=rai.blocked_reason,
                    blocked_date=rai.blocked_date,
                    progress_percentage=rai.progress_percentage,
                    progress_notes=rai.progress_notes,
                    related_lesson=new_lesson,
                    related_task=new_task,
                    ai_suggested=rai.ai_suggested,
                    ai_confidence=rai.ai_confidence,
                )
                RetrospectiveActionItem.objects.filter(pk=new_rai.pk).update(created_at=rai.created_at)
                new_rai.stakeholders.set(rai.stakeholders.all())

        for rt in RetrospectiveTrend.objects.filter(board=template_board):
            new_rt = RetrospectiveTrend.objects.create(
                board=new_board,
                period_type=rt.period_type,
                retrospectives_analyzed=rt.retrospectives_analyzed,
                total_lessons_learned=rt.total_lessons_learned,
                lessons_implemented=rt.lessons_implemented,
                lessons_validated=rt.lessons_validated,
                implementation_rate=rt.implementation_rate,
                total_action_items=rt.total_action_items,
                action_items_completed=rt.action_items_completed,
                completion_rate=rt.completion_rate,
                recurring_issues=rt.recurring_issues,
                top_improvement_categories=rt.top_improvement_categories,
                velocity_trend=rt.velocity_trend,
                quality_trend=rt.quality_trend,
                ai_insights=rt.ai_insights,
                key_recommendations=rt.key_recommendations,
            )
            RetrospectiveTrend.objects.filter(pk=new_rt.pk).update(
                analysis_date=rt.analysis_date, created_at=rt.created_at,
            )
    except Exception:
        pass

    # --- Coaching ---
    try:
        from kanban.coach_models import CoachingSuggestion, PMMetrics

        for cs in CoachingSuggestion.objects.filter(board=template_board):
            new_task_ref = task_map.get(cs.task_id) if cs.task_id else None
            new_cs = CoachingSuggestion.objects.create(
                board=new_board,
                task=new_task_ref,
                suggestion_type=cs.suggestion_type,
                severity=cs.severity,
                status=cs.status,
                title=cs.title,
                message=cs.message,
                reasoning=cs.reasoning,
                recommended_actions=cs.recommended_actions,
                expected_impact=cs.expected_impact,
                metrics_snapshot=cs.metrics_snapshot,
                confidence_score=cs.confidence_score,
                ai_model_used=cs.ai_model_used,
                generation_method=cs.generation_method,
                expires_at=cs.expires_at,
                resolved_at=cs.resolved_at,
                acknowledged_by=cs.acknowledged_by,
                acknowledged_at=cs.acknowledged_at,
                was_helpful=cs.was_helpful,
                action_taken=cs.action_taken,
            )
            CoachingSuggestion.objects.filter(pk=new_cs.pk).update(created_at=cs.created_at)

        for pm in PMMetrics.objects.filter(board=template_board):
            PMMetrics.objects.create(
                board=new_board,
                pm_user=pm.pm_user,
                period_start=pm.period_start,
                period_end=pm.period_end,
                suggestions_received=pm.suggestions_received,
                suggestions_acted_on=pm.suggestions_acted_on,
                avg_response_time_hours=pm.avg_response_time_hours,
                velocity_trend=pm.velocity_trend,
                risk_mitigation_success_rate=pm.risk_mitigation_success_rate,
                deadline_hit_rate=pm.deadline_hit_rate,
                team_satisfaction_score=pm.team_satisfaction_score,
                improvement_areas=pm.improvement_areas,
                struggle_areas=pm.struggle_areas,
                coaching_effectiveness_score=pm.coaching_effectiveness_score,
                calculated_by=pm.calculated_by,
            )
    except Exception:
        pass

    # --- Stakeholders ---
    try:
        from kanban.stakeholder_models import (
            ProjectStakeholder, StakeholderTaskInvolvement,
            EngagementMetrics, StakeholderTag, ProjectStakeholderTag,
        )

        stakeholder_tag_map = {}
        for st in StakeholderTag.objects.filter(board=template_board):
            new_st = StakeholderTag.objects.create(
                name=st.name,
                color=st.color,
                board=new_board,
                created_by=st.created_by,
            )
            stakeholder_tag_map[st.pk] = new_st

        stakeholder_map = {}
        for ps in ProjectStakeholder.objects.filter(board=template_board):
            old_pk = ps.pk
            new_ps = ProjectStakeholder.objects.create(
                name=ps.name,
                role=ps.role,
                organization=ps.organization,
                email=ps.email,
                phone=ps.phone,
                board=new_board,
                influence_level=ps.influence_level,
                interest_level=ps.interest_level,
                current_engagement=ps.current_engagement,
                desired_engagement=ps.desired_engagement,
                notes=ps.notes,
                is_active=ps.is_active,
                created_by=ps.created_by,
            )
            ProjectStakeholder.objects.filter(pk=new_ps.pk).update(created_at=ps.created_at)
            stakeholder_map[old_pk] = new_ps
            # Copy stakeholder tags via through model
            for pst in ProjectStakeholderTag.objects.filter(stakeholder_id=old_pk):
                mapped_tag = stakeholder_tag_map.get(pst.tag_id)
                if mapped_tag:
                    ProjectStakeholderTag.objects.create(
                        stakeholder=new_ps,
                        tag=mapped_tag,
                    )

        for sti in StakeholderTaskInvolvement.objects.filter(
            stakeholder__board=template_board
        ).select_related('stakeholder', 'task'):
            new_sh = stakeholder_map.get(sti.stakeholder_id)
            new_task = task_map.get(sti.task_id)
            if new_sh and new_task:
                StakeholderTaskInvolvement.objects.create(
                    stakeholder=new_sh,
                    task=new_task,
                    involvement_type=sti.involvement_type,
                    engagement_status=sti.engagement_status,
                    engagement_count=sti.engagement_count,
                    last_engagement=sti.last_engagement,
                    satisfaction_rating=sti.satisfaction_rating,
                    feedback=sti.feedback,
                    concerns=sti.concerns,
                    metadata=sti.metadata,
                )

        for em in EngagementMetrics.objects.filter(board=template_board).select_related('stakeholder'):
            new_sh = stakeholder_map.get(em.stakeholder_id)
            if new_sh:
                EngagementMetrics.objects.create(
                    board=new_board,
                    stakeholder=new_sh,
                    total_engagements=em.total_engagements,
                    engagements_this_month=em.engagements_this_month,
                    engagements_this_quarter=em.engagements_this_quarter,
                    average_engagements_per_month=em.average_engagements_per_month,
                    primary_channel=em.primary_channel,
                    channels_used=em.channels_used,
                    average_satisfaction=em.average_satisfaction,
                    positive_engagements_count=em.positive_engagements_count,
                    negative_engagements_count=em.negative_engagements_count,
                    days_since_last_engagement=em.days_since_last_engagement,
                    pending_follow_ups=em.pending_follow_ups,
                    engagement_gap=em.engagement_gap,
                    period_start=em.period_start,
                    period_end=em.period_end,
                )
    except Exception:
        pass

    # --- Conflict Detection ---
    try:
        from kanban.conflict_models import (
            ConflictDetection, ConflictResolution, ConflictNotification, ResolutionPattern,
        )

        conflict_map = {}
        for cd in ConflictDetection.objects.filter(board=template_board):
            old_pk = cd.pk
            new_cd = ConflictDetection.objects.create(
                conflict_type=cd.conflict_type,
                severity=cd.severity,
                status=cd.status,
                title=cd.title,
                description=cd.description,
                board=new_board,
                conflict_data=cd.conflict_data,
                ai_confidence_score=cd.ai_confidence_score,
                suggested_resolutions=cd.suggested_resolutions,
                resolution_feedback=cd.resolution_feedback,
                resolution_effectiveness=cd.resolution_effectiveness,
                detection_run_id=cd.detection_run_id,
                auto_detection=cd.auto_detection,
                resolved_at=cd.resolved_at,
            )
            ConflictDetection.objects.filter(pk=new_cd.pk).update(detected_at=cd.detected_at)
            conflict_map[old_pk] = new_cd
            # M2M: tasks
            for old_task in cd.tasks.all():
                mapped = task_map.get(old_task.pk)
                if mapped:
                    new_cd.tasks.add(mapped)
            # M2M: affected_users
            new_cd.affected_users.set(cd.affected_users.all())

        resolution_map = {}
        for cr in ConflictResolution.objects.filter(conflict__board=template_board):
            new_conflict = conflict_map.get(cr.conflict_id)
            if new_conflict:
                new_cr = ConflictResolution.objects.create(
                    conflict=new_conflict,
                    resolution_type=cr.resolution_type,
                    title=cr.title,
                    description=cr.description,
                    action_steps=cr.action_steps,
                    estimated_impact=cr.estimated_impact,
                    ai_confidence=cr.ai_confidence,
                    ai_reasoning=cr.ai_reasoning,
                    auto_applicable=cr.auto_applicable,
                    implementation_data=cr.implementation_data,
                    applied_at=cr.applied_at,
                    applied_by=cr.applied_by,
                    times_suggested=cr.times_suggested,
                    times_accepted=cr.times_accepted,
                    avg_effectiveness_rating=cr.avg_effectiveness_rating,
                )
                resolution_map[cr.pk] = new_cr

        # Fix chosen_resolution FK on conflicts
        for old_pk, new_cd in conflict_map.items():
            old_cd = ConflictDetection.objects.get(pk=old_pk)
            if old_cd.chosen_resolution_id:
                mapped_res = resolution_map.get(old_cd.chosen_resolution_id)
                if mapped_res:
                    new_cd.chosen_resolution = mapped_res
                    new_cd.save(update_fields=['chosen_resolution'])

        for cn in ConflictNotification.objects.filter(conflict__board=template_board):
            new_conflict = conflict_map.get(cn.conflict_id)
            if new_conflict:
                new_cn = ConflictNotification.objects.create(
                    conflict=new_conflict,
                    user=cn.user,
                    read_at=cn.read_at,
                    acknowledged=cn.acknowledged,
                    notification_type=cn.notification_type,
                )
                ConflictNotification.objects.filter(pk=new_cn.pk).update(sent_at=cn.sent_at)

        for rp in ResolutionPattern.objects.filter(board=template_board):
            ResolutionPattern.objects.create(
                conflict_type=rp.conflict_type,
                resolution_type=rp.resolution_type,
                board=new_board,
                pattern_context=rp.pattern_context,
                times_used=rp.times_used,
                times_successful=rp.times_successful,
                success_rate=rp.success_rate,
                avg_effectiveness_rating=rp.avg_effectiveness_rating,
                last_used_at=rp.last_used_at,
                confidence_boost=rp.confidence_boost,
            )
    except Exception:
        pass

    # --- Messaging (ChatRoom + ChatMessage + TaskThreadComment) ---
    try:
        from messaging.models import ChatRoom, ChatMessage, TaskThreadComment

        chatroom_map = {}
        for cr in ChatRoom.objects.filter(board=template_board):
            old_pk = cr.pk
            new_cr = ChatRoom.objects.create(
                board=new_board,
                name=cr.name,
                description=cr.description,
                created_by=cr.created_by,
            )
            ChatRoom.objects.filter(pk=new_cr.pk).update(created_at=cr.created_at)
            chatroom_map[old_pk] = new_cr
            new_cr.members.set(cr.members.all())

        for cm in ChatMessage.objects.filter(chat_room__board=template_board).order_by('created_at'):
            new_room = chatroom_map.get(cm.chat_room_id)
            if new_room:
                new_cm = ChatMessage.objects.create(
                    chat_room=new_room,
                    author=cm.author,
                    content=cm.content,
                    is_read=cm.is_read,
                    read_at=cm.read_at,
                )
                ChatMessage.objects.filter(pk=new_cm.pk).update(created_at=cm.created_at)
                new_cm.read_by.set(cm.read_by.all())
                new_cm.mentioned_users.set(cm.mentioned_users.all())

        for ttc in TaskThreadComment.objects.filter(task__column__board=template_board):
            new_task = task_map.get(ttc.task_id)
            if new_task:
                new_ttc = TaskThreadComment.objects.create(
                    task=new_task,
                    author=ttc.author,
                    content=ttc.content,
                )
                TaskThreadComment.objects.filter(pk=new_ttc.pk).update(created_at=ttc.created_at)
                new_ttc.mentioned_users.set(ttc.mentioned_users.all())
    except Exception:
        pass

    # --- AI Assistant (Knowledge Base + Recommendations) ---
    try:
        from ai_assistant.models import ProjectKnowledgeBase, AITaskRecommendation

        for kb in ProjectKnowledgeBase.objects.filter(board=template_board):
            new_source = task_map.get(kb.source_task_id) if kb.source_task_id else None
            ProjectKnowledgeBase.objects.create(
                board=new_board,
                content_type=kb.content_type,
                title=kb.title,
                content=kb.content,
                summary=kb.summary,
                source_task=new_source,
                source_url=kb.source_url,
                is_active=kb.is_active,
            )

        for rec in AITaskRecommendation.objects.filter(board=template_board):
            new_task = task_map.get(rec.task_id)
            if new_task:
                AITaskRecommendation.objects.create(
                    task=new_task,
                    board=new_board,
                    recommendation_type=rec.recommendation_type,
                    title=rec.title,
                    description=rec.description,
                    potential_impact=rec.potential_impact,
                    confidence_score=rec.confidence_score,
                    suggested_action=rec.suggested_action,
                    expected_benefit=rec.expected_benefit,
                    status=rec.status,
                    implemented_at=rec.implemented_at,
                    implementation_notes=rec.implementation_notes,
                )
    except Exception:
        pass

    # --- Decision Center ---
    # DecisionItems are NOT copied from the template.  ``collect_for_user()``
    # (called right after sandbox provisioning) will regenerate them for the
    # sandbox owner's board set, avoiding orphaned/duplicate items that were
    # left with the wrong ``created_for`` user.
    # See sandbox_provisioning.py → provision_sandbox_task.

    # --- Task Activities (keep demo activity history for realism) ---
    try:
        from kanban.models import TaskActivity
        for act in TaskActivity.objects.filter(task__column__board=template_board).select_related('task'):
            new_task = task_map.get(act.task_id)
            if new_task:
                new_act = TaskActivity.objects.create(
                    task=new_task,
                    user=act.user,
                    activity_type=act.activity_type,
                    description=act.description,
                )
                TaskActivity.objects.filter(pk=new_act.pk).update(created_at=act.created_at)
    except Exception:
        pass

    # --- Wiki Links (board/task references only, WikiPages are org-level) ---
    try:
        from wiki.models import WikiLink
        for wl in WikiLink.objects.filter(board=template_board):
            new_task_ref = task_map.get(wl.task_id) if wl.task_id else None
            WikiLink.objects.create(
                wiki_page=wl.wiki_page,  # Wiki pages are org-level, shared
                link_type=wl.link_type,
                task=new_task_ref,
                board=new_board,
                created_by=wl.created_by,
                description=wl.description,
            )
    except Exception:
        pass

    # --- Preserve template timestamps (bypass auto_now via .update()) ---
    # Without this, all sandbox tasks get updated_at=now which causes the
    # Completion Velocity chart to show a single spike on today's date.
    for new_pk, template_updated_at in task_template_dates.items():
        Task.objects.filter(pk=new_pk).update(updated_at=template_updated_at)

    return new_board


NUM_TASKS_TO_REASSIGN = 3  # How many demo tasks to reassign to the real user


def _reassign_demo_tasks_to_user(sandbox, user):
    """
    Pick NUM_TASKS_TO_REASSIGN tasks on the user's sandbox copy and reassign
    them from demo personas to the real user.  Store the mapping in
    sandbox.reassigned_tasks so we can restore on leave.

    Selection criteria: prefer variety — different priorities, with due dates,
    from different demo personas.
    """
    from kanban.models import Board, Task

    boards = Board.objects.filter(owner=user, is_sandbox_copy=True)
    if not boards.exists():
        return

    # Find tasks on sandbox boards that are assigned to demo personas
    candidates = (
        Task.objects
        .filter(
            column__board__in=boards,
            item_type='task',
            assigned_to__isnull=False,
            assigned_to__email__contains='@demo.prizmai.local',
        )
        .exclude(progress=100)
        .select_related('assigned_to', 'column__board')
        .order_by('priority', 'due_date')
    )

    # Pick up to NUM_TASKS_TO_REASSIGN from different assignees for variety
    picked = []
    seen_assignees = set()
    # First pass: one per assignee
    for t in candidates:
        if t.assigned_to_id not in seen_assignees and len(picked) < NUM_TASKS_TO_REASSIGN:
            picked.append(t)
            seen_assignees.add(t.assigned_to_id)
    # Second pass: fill remaining slots
    if len(picked) < NUM_TASKS_TO_REASSIGN:
        for t in candidates:
            if t not in picked and len(picked) < NUM_TASKS_TO_REASSIGN:
                picked.append(t)

    mapping = {}
    for task in picked:
        mapping[str(task.id)] = task.assigned_to_id
        task.assigned_to = user
        task.save(update_fields=['assigned_to'])

    sandbox.reassigned_tasks = mapping
    sandbox.save(update_fields=['reassigned_tasks'])


def _restore_demo_task_assignments(sandbox):
    """
    Reassign tasks back to their original demo persona owners using the
    mapping stored in sandbox.reassigned_tasks.
    """
    from kanban.models import Task
    from django.contrib.auth.models import User

    mapping = sandbox.reassigned_tasks or {}
    if not mapping:
        return

    for task_id_str, original_user_id in mapping.items():
        try:
            task = Task.objects.get(pk=int(task_id_str))
            task.assigned_to_id = original_user_id
            task.save(update_fields=['assigned_to'])
        except Task.DoesNotExist:
            pass  # Task was deleted (board purged)

    sandbox.reassigned_tasks = {}
    sandbox.save(update_fields=['reassigned_tasks'])


def _join_demo_org(user):
    """Add the user to the demo organization and as a member of the demo board."""
    from accounts.models import Organization, UserProfile
    from kanban.models import Board, BoardMembership

    demo_org = Organization.objects.filter(is_demo=True).first()
    if not demo_org:
        return

    # Store original org so we can restore on leave
    profile = user.profile
    if not profile.organization or not profile.organization.is_demo:
        # Only update if not already in demo org
        profile._original_org_id = getattr(profile, '_original_org_id', profile.organization_id)
        profile.organization = demo_org
        profile.save(update_fields=['organization'])


def _leave_demo_org(user):
    """Remove the user from the demo organization, restoring their original org."""
    from accounts.models import UserProfile

    profile = user.profile
    if profile.organization and profile.organization.is_demo:
        profile.organization = None
        profile.save(update_fields=['organization'])


def _purge_existing_sandbox(user):
    """
    Delete any existing sandbox for the user (boards + DemoSandbox record).

    Also cleans up:
    - Models with SET_NULL on Board FK (orphaned after board deletion)
    - User-scoped data that isn't board-scoped (DC briefings, notifications, etc.)
    """
    from kanban.models import DemoSandbox, Board, Task

    sandbox_boards = Board.objects.filter(
        owner=user,
        is_sandbox_copy=True,
        is_official_demo_board=False,
        is_seed_demo_data=False,
    )
    sandbox_board_ids = list(sandbox_boards.values_list('id', flat=True))

    try:
        sandbox = user.demo_sandbox
        # Restore assignments before deleting
        _restore_demo_task_assignments(sandbox)
    except Exception:
        pass

    if sandbox_board_ids:
        sandbox_task_ids = list(
            Task.objects.filter(column__board_id__in=sandbox_board_ids)
            .values_list('id', flat=True)
        )

        # ── Models with SET_NULL on Board FK (won't cascade-delete) ──
        try:
            from ai_assistant.models import (
                AIAssistantMessage, AIAssistantSession, AIAssistantAnalytics,
            )
            orphan_sessions = AIAssistantSession.objects.filter(board_id__in=sandbox_board_ids)
            AIAssistantMessage.objects.filter(session__in=orphan_sessions).delete()
            orphan_sessions.delete()
            AIAssistantAnalytics.objects.filter(board_id__in=sandbox_board_ids).delete()
        except Exception:
            pass

        try:
            from kanban.models import CalendarEvent
            CalendarEvent.objects.filter(board_id__in=sandbox_board_ids).delete()
        except Exception:
            pass

        try:
            from knowledge_graph.models import MemoryNode, MemoryConnection
            orphan_nodes = MemoryNode.objects.filter(board_id__in=sandbox_board_ids)
            orphan_node_ids = list(orphan_nodes.values_list('id', flat=True))
            if orphan_node_ids:
                MemoryConnection.objects.filter(
                    models.Q(from_node_id__in=orphan_node_ids)
                    | models.Q(to_node_id__in=orphan_node_ids)
                ).delete()
                orphan_nodes.delete()
        except Exception:
            pass

        try:
            from wiki.models import WikiLink
            WikiLink.objects.filter(board_id__in=sandbox_board_ids).delete()
            if sandbox_task_ids:
                WikiLink.objects.filter(task_id__in=sandbox_task_ids).delete()
        except Exception:
            pass

        # ── Now delete sandbox boards (cascades most other models) ──
        sandbox_boards.delete()

    # ── User-scoped data (not board-scoped, survives board deletion) ──
    try:
        from decision_center.models import DecisionItem, DecisionCenterBriefing
        DecisionItem.objects.filter(created_for=user).delete()
        DecisionCenterBriefing.objects.filter(user=user).delete()
    except Exception:
        pass

    try:
        from django.core.cache import cache
        cache.delete(f'dc_widget_{user.id}_demo')
        cache.delete(f'dc_widget_{user.id}_real')
    except Exception:
        pass

    try:
        from messaging.models import Notification
        Notification.objects.filter(recipient=user).delete()
    except Exception:
        pass

    try:
        from ai_assistant.models import AIAssistantMessage, AIAssistantSession
        # Also clean any user-owned sessions not tied to a board
        user_sessions = AIAssistantSession.objects.filter(user=user)
        AIAssistantMessage.objects.filter(session__in=user_sessions).delete()
        user_sessions.delete()
    except Exception:
        pass

    try:
        from kanban.models import CalendarEvent
        # Clean user-created calendar events (not board-scoped ones)
        CalendarEvent.objects.filter(created_by=user, board__isnull=True).delete()
    except Exception:
        pass

    # ── DemoSandbox record ──
    try:
        sandbox = user.demo_sandbox
        sandbox.delete()
    except Exception:
        pass


# ── Views ─────────────────────────────────────────────────────────────────────

@login_required
@require_http_methods(["POST"])
def reset_my_demo(request):
    """POST /demo/reset-mine/ — wipe user's sandbox and re-provision via Celery."""
    from kanban.models import DemoSandbox

    _purge_existing_sandbox(request.user)

    # Re-provision asynchronously (last_reset_at is set in the provisioning task)
    from kanban.tasks.sandbox_provisioning import provision_sandbox_task
    result = provision_sandbox_task.delay(request.user.id, is_reset=True)

    return JsonResponse({
        'status': 'resetting',
        'task_id': result.id,
    })


@login_required
@require_http_methods(["GET"])
def sandbox_status(request):
    """
    JSON status endpoint — reports whether a sandbox exists and is active.
    """
    from kanban.models import DemoSandbox

    user = request.user
    is_viewing_demo = getattr(getattr(user, 'profile', None), 'is_viewing_demo', False)
    try:
        user.demo_sandbox
        return JsonResponse({
            'has_sandbox': True,
            'is_viewing_demo': is_viewing_demo,
        })
    except DemoSandbox.DoesNotExist:
        return JsonResponse({'has_sandbox': False, 'is_viewing_demo': False})
