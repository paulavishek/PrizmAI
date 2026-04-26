"""
Celery tasks for Exit Protocol.
Health monitoring, hospice AI generation, organ extraction, and burial.
"""

import logging
from datetime import timedelta
from celery import shared_task, group
from django.utils import timezone
from django.db.models import Q, Count

logger = logging.getLogger(__name__)


# ──────────────────────────────────────────
# 4.1 — Health Monitoring (Scheduled Daily)
# ──────────────────────────────────────────

@shared_task(name='exit_protocol.tasks.monitor_all_boards_health')
def monitor_all_boards_health():
    """
    Dispatcher: loops all non-archived boards and spawns per-board subtasks.
    Registered in Celery Beat as 'monitor-board-health-daily' at 2:00 AM.
    """
    from kanban.models import Board

    board_ids = list(
        Board.objects.filter(
            is_archived=False,
            is_sandbox_copy=False,
            is_official_demo_board=False,
        ).values_list('id', flat=True)
    )
    logger.info(f"[ExitProtocol] Monitoring health for {len(board_ids)} boards")

    for board_id in board_ids:
        compute_board_health_score.delay(board_id)


@shared_task(name='exit_protocol.tasks.compute_board_health_score')
def compute_board_health_score(board_id, force=False):
    """
    Computes hospice_risk_score for a single board.
    Applies minimum-data rules to avoid false positives.
    Pass force=True to bypass age guard (used by manual recalculate).
    """
    from kanban.models import Board, Task
    from .models import ProjectHealthSignal, HospiceSession, HospiceDismissal

    try:
        board = Board.objects.get(id=board_id, is_archived=False)
    except Board.DoesNotExist:
        return

    now = timezone.now()

    # RULE: Skip boards with fewer than 7 days of activity (bypassed on manual recalculate)
    if not force and board.created_at and (now - board.created_at).days < 7:
        return

    # ── Collect metrics per dimension ──

    # Dimension 1: Velocity
    velocity_factor = None
    velocity_decline_pct = None
    velocity_last = None
    velocity_avg = None
    try:
        from kanban.burndown_models import TeamVelocitySnapshot
        snapshots = TeamVelocitySnapshot.objects.filter(
            board=board
        ).order_by('-period_end')[:10]

        if snapshots.count() >= 3:
            recent = list(snapshots[:3])
            baseline = list(snapshots[3:])

            avg_recent = sum(s.tasks_completed for s in recent) / len(recent)
            velocity_last = recent[0].tasks_completed if recent else None
            velocity_avg = avg_recent

            if baseline:
                avg_baseline = sum(s.tasks_completed for s in baseline) / len(baseline)
                if avg_baseline > 0:
                    velocity_decline_pct = ((avg_baseline - avg_recent) / avg_baseline) * 100
                    velocity_factor = min(max(velocity_decline_pct / 100, 0.0), 1.0)
    except Exception as e:
        logger.debug(f"[ExitProtocol] Velocity data unavailable for board {board_id}: {e}")

    # Dimension 2: Budget
    budget_factor = None
    budget_spent_pct = None
    tasks_complete_pct = None
    try:
        from kanban.budget_models import ProjectBudget
        budget = ProjectBudget.objects.get(board=board)
        budget_spent_pct = budget.get_budget_utilization_percent()

        total_tasks = Task.objects.filter(column__board=board).count()
        completed_tasks = Task.objects.filter(
            column__board=board, completed_at__isnull=False
        ).count()
        tasks_complete_pct = (completed_tasks / total_tasks * 100) if total_tasks > 0 else 0

        if budget_spent_pct is not None:
            # High spend + low completion = danger; high spend + high completion = fine
            budget_factor = (budget_spent_pct / 100) * (1 - tasks_complete_pct / 100)
            budget_factor = min(max(budget_factor, 0.0), 1.0)
    except Exception:
        pass  # No budget configured — dimension unavailable

    # Dimension 3: Deadlines
    deadline_factor = None
    deadlines_missed = 0
    thirty_days_ago = now - timedelta(days=30)
    tasks_with_deadlines = Task.objects.filter(
        column__board=board, due_date__isnull=False
    ).count()

    if tasks_with_deadlines > 0:
        deadlines_missed = Task.objects.filter(
            column__board=board,
            due_date__lt=now,
            due_date__gte=thirty_days_ago,
            completed_at__isnull=True,
        ).count()
        deadline_factor = min(deadlines_missed / 10, 1.0)

    # Dimension 4: Activity (always available)
    last_task_activity = Task.objects.filter(
        column__board=board
    ).order_by('-updated_at').values_list('updated_at', flat=True).first()

    days_inactive = 0
    if last_task_activity:
        days_inactive = (now - last_task_activity).days
    else:
        days_inactive = (now - board.created_at).days if board.created_at else 0

    activity_factor = min(days_inactive / 30, 1.0)

    # ── Count available dimensions ──
    weights = {
        'velocity': (0.30, velocity_factor),
        'budget': (0.25, budget_factor),
        'deadline': (0.25, deadline_factor),
        'activity': (0.20, activity_factor),
    }

    available = {k: v for k, v in weights.items() if v[1] is not None}
    dimensions_available = len(available)

    # RULE: Need at least 2 dimensions for a valid score
    if dimensions_available < 2:
        ProjectHealthSignal.objects.create(
            board=board,
            velocity_last_sprint=velocity_last,
            velocity_3sprint_avg=velocity_avg,
            velocity_decline_pct=velocity_decline_pct,
            budget_spent_pct=budget_spent_pct,
            tasks_complete_pct=tasks_complete_pct,
            deadlines_missed_30d=deadlines_missed,
            days_since_last_activity=days_inactive,
            dimensions_available=dimensions_available,
            hospice_risk_score=0.0,
            score_is_valid=False,
            triggered_hospice=False,
        )
        return

    # ── Re-normalize weights and compute score ──
    total_weight = sum(w for w, _ in available.values())
    risk_score = sum(
        (w / total_weight) * factor for w, factor in available.values()
    )
    risk_score = min(max(risk_score, 0.0), 1.0)

    # ── Should we trigger hospice? ──
    should_trigger = (
        risk_score >= 0.75
        and not HospiceSession.objects.filter(board=board).exists()
        and not HospiceDismissal.objects.filter(
            board=board, expires_at__gt=now
        ).exists()
    )

    signal = ProjectHealthSignal.objects.create(
        board=board,
        velocity_last_sprint=velocity_last,
        velocity_3sprint_avg=velocity_avg,
        velocity_decline_pct=velocity_decline_pct,
        budget_spent_pct=budget_spent_pct,
        tasks_complete_pct=tasks_complete_pct,
        deadlines_missed_30d=deadlines_missed,
        days_since_last_activity=days_inactive,
        dimensions_available=dimensions_available,
        hospice_risk_score=risk_score,
        score_is_valid=True,
        triggered_hospice=should_trigger,
    )

    if should_trigger:
        trigger_hospice_notification.delay(board_id)

    logger.info(
        f"[ExitProtocol] Board {board_id}: score={risk_score:.2f}, "
        f"dims={dimensions_available}, trigger={should_trigger}"
    )


@shared_task(name='exit_protocol.tasks.trigger_hospice_notification')
def trigger_hospice_notification(board_id):
    """
    Creates a Notification (type ACTIVITY) for board managers.
    Does NOT auto-create HospiceSession — that requires manager action.
    """
    from kanban.models import Board, BoardMembership
    from messaging.models import Notification
    from django.contrib.auth.models import User

    try:
        board = Board.objects.get(id=board_id)
    except Board.DoesNotExist:
        return

    # Get all board members (owners/members who can edit)
    memberships = BoardMembership.objects.filter(
        board=board
    ).select_related('user')

    # Use the first member or system as sender
    sender = None
    recipients = []
    for membership in memberships:
        if sender is None:
            sender = membership.user
        if membership.role in ('owner', 'member'):
            recipients.append(membership.user)

    # Fallback: if no managers found, notify all members
    if not recipients:
        recipients = [m.user for m in memberships]

    if not sender:
        # Use any superuser as fallback sender
        sender = User.objects.filter(is_superuser=True).first()
        if not sender:
            return

    for recipient in recipients:
        if recipient.id == sender.id:
            # Don't create a self-notification; use another member as sender
            alt_sender = next((m.user for m in memberships if m.user.id != recipient.id), sender)
            notif_sender = alt_sender
        else:
            notif_sender = sender

        Notification.objects.create(
            recipient=recipient,
            sender=notif_sender,
            notification_type='ACTIVITY',
            text=(
                f"🏥 PrizmAI has detected sustained challenges on \"{board.name}\". "
                f"The project may benefit from a structured wind-down review. "
                f"Visit the Exit Protocol dashboard to review the AI assessment."
            ),
            action_url=f'/boards/{board.id}/exit-protocol/',
        )


# ──────────────────────────────────────────
# 4.2 — Hospice AI Tasks (Parallel Group)
# ──────────────────────────────────────────

@shared_task(name='exit_protocol.tasks.generate_hospice_assessment')
def generate_hospice_assessment(session_id):
    """Generates the compassionate AI health assessment."""
    from .models import HospiceSession, ProjectHealthSignal
    from . import ai_utils

    try:
        session = HospiceSession.objects.select_related('board', 'initiated_by').get(id=session_id)
    except HospiceSession.DoesNotExist:
        return

    board = session.board
    user = session.initiated_by

    if not user:
        logger.warning(f"[ExitProtocol] No user for session {session_id}, skipping assessment")
        return

    # Gather context
    total_tasks = 0
    completed_tasks = 0
    try:
        from kanban.models import Task
        total_tasks = Task.objects.filter(column__board=board).count()
        completed_tasks = Task.objects.filter(column__board=board, completed_at__isnull=False).count()
    except Exception:
        pass

    completion_pct = round(completed_tasks / total_tasks * 100) if total_tasks > 0 else 0

    # Latest health signal
    latest_signal = ProjectHealthSignal.objects.filter(board=board).order_by('-recorded_at').first()

    # Pre-mortem risks
    materialized_risks = 'None recorded'
    try:
        from kanban.premortem_models import PreMortemAnalysis
        premortem = PreMortemAnalysis.objects.filter(board=board).order_by('-created_at').first()
        if premortem and premortem.analysis_json:
            scenarios = premortem.analysis_json.get('scenarios', [])
            high_risks = [s.get('scenario', '') for s in scenarios if s.get('risk_level') == 'high']
            if high_risks:
                materialized_risks = '; '.join(high_risks[:3])
    except Exception:
        pass

    # Stress test score
    stress_score = 'Not available'
    try:
        from kanban.stress_test_models import ImmunityScore
        immunity = ImmunityScore.objects.filter(session__board=board).order_by('-session__created_at').first()
        if immunity:
            stress_score = f"{immunity.overall}/100 ({immunity.get_band()})"
    except Exception:
        pass

    # Velocity trend
    velocity_trend = 'Not available'
    if latest_signal and latest_signal.velocity_decline_pct is not None:
        velocity_trend = f"{latest_signal.velocity_decline_pct:.0f}% decline"

    context = {
        'project_name': board.name,
        'start_date': board.created_at.strftime('%Y-%m-%d') if board.created_at else 'Unknown',
        'days_active': (timezone.now() - board.created_at).days if board.created_at else 'Unknown',
        'completed_tasks': completed_tasks,
        'total_tasks': total_tasks,
        'completion_pct': completion_pct,
        'budget_spent_pct': f"{latest_signal.budget_spent_pct:.0f}%" if latest_signal and latest_signal.budget_spent_pct else 'Not tracked',
        'velocity_trend': velocity_trend,
        'deadlines_missed': latest_signal.deadlines_missed_30d if latest_signal else 0,
        'days_inactive': latest_signal.days_since_last_activity if latest_signal else 0,
        'materialized_risks': materialized_risks,
        'stress_score': stress_score,
    }

    try:
        assessment = ai_utils.generate_assessment(user, context, board_id=board.id)
        session.ai_assessment = assessment
        session.status = 'knowledge_extraction'
        session.save(update_fields=['ai_assessment', 'status'])
        logger.info(f"[ExitProtocol] Assessment generated for session {session_id}")
    except Exception as e:
        logger.error(f"[ExitProtocol] Assessment generation failed for session {session_id}: {e}")
        session.ai_assessment = (
            "We were unable to generate an automated assessment at this time. "
            "Please review the project data manually and consult with your team."
        )
        session.save(update_fields=['ai_assessment'])


@shared_task(name='exit_protocol.tasks.generate_knowledge_checklist')
def generate_knowledge_checklist(session_id):
    """Queries MemoryNode and structures knowledge into an extraction checklist."""
    from .models import HospiceSession

    try:
        session = HospiceSession.objects.select_related('board').get(id=session_id)
    except HospiceSession.DoesNotExist:
        return

    board = session.board

    # Query knowledge graph nodes
    checklist = {
        'decisions': [],
        'risks_materialized': [],
        'lessons': [],
        'milestones_achieved': [],
    }

    try:
        from knowledge_graph.models import MemoryNode

        type_to_category = {
            'decision': 'decisions',
            'risk_event': 'risks_materialized',
            'lesson': 'lessons',
            'milestone': 'milestones_achieved',
            'outcome': 'milestones_achieved',
            'scope_change': 'risks_materialized',
        }

        nodes = MemoryNode.objects.filter(board=board).order_by('-importance_score')

        # Track seen scope-change percentages and titles to deduplicate
        seen_scope_pcts = set()
        seen_titles = set()

        for node in nodes:
            category = type_to_category.get(node.node_type)
            if category:
                # Deduplicate by title across all node types
                title_key = (node.title or '').strip().lower()
                if title_key in seen_titles:
                    continue
                seen_titles.add(title_key)

                # Also deduplicate scope_change nodes by percentage
                if node.node_type == 'scope_change' and node.context_data:
                    pct = node.context_data.get('scope_increase_pct')
                    if pct is not None:
                        pct_key = round(float(pct), 1)
                        if pct_key in seen_scope_pcts:
                            continue
                        seen_scope_pcts.add(pct_key)

                checklist[category].append({
                    'id': str(node.id),
                    'title': node.title,
                    'content': node.content[:300] if node.content else '',
                    'importance': float(node.importance_score) if node.importance_score else 0.5,
                    'node_type': node.node_type,
                    'status': 'pending',
                    'date': node.created_at.strftime('%b %d, %Y'),
                })
    except Exception as e:
        logger.error(f"[ExitProtocol] Knowledge checklist failed for session {session_id}: {e}")

    # Strip empty categories so template doesn't show blank headings (EXP-05)
    checklist = {k: v for k, v in checklist.items() if v}

    session.knowledge_checklist = checklist
    session.save(update_fields=['knowledge_checklist'])
    logger.info(f"[ExitProtocol] Knowledge checklist generated for session {session_id}")


@shared_task(name='exit_protocol.tasks.generate_team_transition_memos')
def generate_team_transition_memos(session_id):
    """Generates transition memos for each team member."""
    from .models import HospiceSession
    from . import ai_utils

    try:
        session = HospiceSession.objects.select_related('board', 'initiated_by').get(id=session_id)
    except HospiceSession.DoesNotExist:
        return

    board = session.board
    user = session.initiated_by
    if not user:
        return

    memos = {}

    try:
        from kanban.models import BoardMembership
        from kanban.models import Task

        memberships = BoardMembership.objects.filter(
            board=board
        ).select_related('user')

        for membership in memberships:
            member = membership.user
            # Find tasks assigned to this member
            member_tasks = Task.objects.filter(
                column__board=board, assigned_to=member
            ).values_list('title', flat=True)[:15]

            tasks_summary = ', '.join(member_tasks) if member_tasks else 'No specific task assignments recorded'
            role_name = membership.role.capitalize() if membership.role else 'Team Member'

            try:
                memo = ai_utils.generate_transition_memo(user, {
                    'member_name': member.get_full_name() or member.username,
                    'tasks_summary': tasks_summary,
                    'role_name': role_name,
                    'project_name': board.name,
                }, board_id=board.id)
                memos[str(member.id)] = memo
            except Exception as e:
                logger.warning(f"[ExitProtocol] Memo generation failed for user {member.id}: {e}")
                memos[str(member.id)] = (
                    f"{member.get_full_name() or member.username} contributed to this project "
                    f"as {role_name}. Their efforts are valued and recognized."
                )
    except Exception as e:
        logger.error(f"[ExitProtocol] Transition memos failed for session {session_id}: {e}")

    session.team_transition_memos = memos
    session.status = 'team_transition'
    session.save(update_fields=['team_transition_memos', 'status'])
    logger.info(f"[ExitProtocol] Transition memos generated for session {session_id}")


# ──────────────────────────────────────────
# 4.3 — Organ Extraction Tasks
# ──────────────────────────────────────────

@shared_task(name='exit_protocol.tasks.scan_and_extract_organs')
def scan_and_extract_organs(session_id):
    """Scans the board for reusable components and creates ProjectOrgan records."""
    from .models import HospiceSession, ProjectOrgan

    try:
        session = HospiceSession.objects.select_related('board').get(id=session_id)
    except HospiceSession.DoesNotExist:
        return

    board = session.board
    organs_created = []

    # 1. Automation Rules
    try:
        from kanban.automation_models import BoardAutomation, ScheduledAutomation

        for auto in BoardAutomation.objects.filter(board=board, is_active=True):
            payload = {
                'trigger': auto.trigger,
                'action': auto.action,
                'trigger_config': auto.trigger_config if hasattr(auto, 'trigger_config') else {},
                'action_config': auto.action_config if hasattr(auto, 'action_config') else {},
                'name': auto.name if hasattr(auto, 'name') else f"Automation: {auto.trigger} → {auto.action}",
            }
            organ = ProjectOrgan.objects.create(
                source_board=board,
                hospice_session=session,
                organ_type='automation_rule',
                name=payload['name'],
                description=f"Board automation: when {auto.trigger}, then {auto.action}",
                payload=payload,
            )
            organs_created.append(organ.id)

        for sched in ScheduledAutomation.objects.filter(board=board, is_active=True):
            payload = {
                'name': sched.name,
                'frequency': sched.frequency,
                'action': sched.action,
                'action_config': sched.action_config if hasattr(sched, 'action_config') else {},
                'time_config': sched.time_config if hasattr(sched, 'time_config') else {},
            }
            organ = ProjectOrgan.objects.create(
                source_board=board,
                hospice_session=session,
                organ_type='automation_rule',
                name=sched.name,
                description=f"Scheduled automation: {sched.frequency} — {sched.action}",
                payload=payload,
            )
            organs_created.append(organ.id)
    except Exception as e:
        logger.debug(f"[ExitProtocol] Automation extraction skipped: {e}")

    # 2. Knowledge Entries (high importance)
    try:
        from knowledge_graph.models import MemoryNode

        important_nodes = MemoryNode.objects.filter(
            board=board, importance_score__gte=0.7
        ).order_by('-importance_score')[:20]

        for node in important_nodes:
            payload = {
                'title': node.title,
                'content': node.content,
                'node_type': node.node_type,
                'tags': node.tags if node.tags else [],
                'context_data': node.context_data if node.context_data else {},
                'importance_score': float(node.importance_score) if node.importance_score else 0.5,
            }
            organ = ProjectOrgan.objects.create(
                source_board=board,
                hospice_session=session,
                organ_type='knowledge_entry',
                name=node.title,
                description=node.content[:500] if node.content else node.title,
                payload=payload,
            )
            organs_created.append(organ.id)
    except Exception as e:
        logger.debug(f"[ExitProtocol] Knowledge extraction skipped: {e}")

    # 3. Task Templates (completed tasks with high complexity / reuse patterns)
    try:
        from kanban.models import Task

        # Find tasks that were completed and had notable structure
        completed_tasks = Task.objects.filter(
            column__board=board,
            completed_at__isnull=False,
        ).select_related('column').order_by('-complexity_score')[:10]

        for task in completed_tasks:
            # Get subtasks if any
            subtasks = []
            if hasattr(task, 'subtasks'):
                subtasks = list(task.subtasks.values_list('title', flat=True))

            # Get labels
            labels = []
            if hasattr(task, 'labels'):
                labels = list(task.labels.values_list('name', flat=True))

            payload = {
                'title': task.title,
                'description': task.description or '',
                'priority': task.priority,
                'complexity_score': task.complexity_score,
                'subtasks': subtasks,
                'labels': labels,
                'estimated_hours': float(task.estimated_hours) if hasattr(task, 'estimated_hours') and task.estimated_hours else None,
            }
            organ = ProjectOrgan.objects.create(
                source_board=board,
                hospice_session=session,
                organ_type='task_template',
                name=f"Template: {task.title}",
                description=task.description[:500] if task.description else task.title,
                payload=payload,
            )
            organs_created.append(organ.id)
    except Exception as e:
        logger.debug(f"[ExitProtocol] Task template extraction skipped: {e}")

    # 4. Role Definitions
    try:
        from kanban.models import BoardMembership

        memberships = BoardMembership.objects.filter(
            board=board
        )

        roles_seen = set()
        for m in memberships:
            if m.role and m.role not in roles_seen:
                roles_seen.add(m.role)
                payload = {
                    'role_name': m.role,
                    'description': f'Board {m.role} role',
                    'permissions': [],
                }
                organ = ProjectOrgan.objects.create(
                    source_board=board,
                    hospice_session=session,
                    organ_type='role_definition',
                    name=f"Role: {m.role}",
                    description=f"Role definition for {m.role}",
                    payload=payload,
                )
                organs_created.append(organ.id)
    except Exception as e:
        logger.debug(f"[ExitProtocol] Role extraction skipped: {e}")

    # 5. Goal Frameworks (Mission/Strategy)
    try:
        from kanban.models import Board as BoardModel
        if board.strategy:
            strategy = board.strategy
            mission = strategy.mission if hasattr(strategy, 'mission') else None
            payload = {
                'strategy_name': strategy.name if hasattr(strategy, 'name') else '',
                'strategy_description': strategy.description if hasattr(strategy, 'description') else '',
                'mission_name': mission.name if mission and hasattr(mission, 'name') else '',
                'mission_description': mission.description if mission and hasattr(mission, 'description') else '',
            }
            organ = ProjectOrgan.objects.create(
                source_board=board,
                hospice_session=session,
                organ_type='goal_framework',
                name=f"Goal Framework: {payload['strategy_name'] or board.name}",
                description=f"Strategic framework from {board.name}",
                payload=payload,
            )
            organs_created.append(organ.id)
    except Exception as e:
        logger.debug(f"[ExitProtocol] Goal framework extraction skipped: {e}")

    # Update session status
    session.status = 'organ_scan'
    session.save(update_fields=['status'])

    # Spawn reusability scoring for each organ
    for organ_id in organs_created:
        score_organ_reusability_task.delay(organ_id, session.initiated_by_id)

    logger.info(f"[ExitProtocol] Extracted {len(organs_created)} organs from board {board.id}")


@shared_task(name='exit_protocol.tasks.score_organ_reusability_task')
def score_organ_reusability_task(organ_id, user_id=None):
    """Scores a single organ's reusability via AI."""
    from .models import ProjectOrgan
    from . import ai_utils
    from django.contrib.auth.models import User

    try:
        organ = ProjectOrgan.objects.select_related('source_board').get(id=organ_id)
    except ProjectOrgan.DoesNotExist:
        return

    user = None
    if user_id:
        try:
            user = User.objects.get(id=user_id)
        except User.DoesNotExist:
            pass

    if not user:
        user = User.objects.filter(is_superuser=True).first()
        if not user:
            return

    import json
    payload_summary = json.dumps(organ.payload, default=str)[:500]

    context = {
        'organ_type': organ.get_organ_type_display(),
        'name': organ.name,
        'description': organ.description[:300],
        'payload_summary': payload_summary,
        'source_project_context': organ.source_board.name,
    }

    try:
        result = ai_utils.score_organ_reusability(user, context, board_id=organ.source_board_id)
        organ.reusability_score = result.get('reusability_score', 0)
        organ.ai_rationale = result.get('rationale', '')
        organ.best_suited_for = result.get('best_suited_for', '')
        organ.cautions = result.get('cautions', '')
        organ.save(update_fields=[
            'reusability_score', 'ai_rationale', 'best_suited_for', 'cautions'
        ])
    except Exception as e:
        logger.error(f"[ExitProtocol] Organ scoring failed for organ {organ_id}: {e}")


# ──────────────────────────────────────────
# 4.4 — Burial Task
# ──────────────────────────────────────────

@shared_task(name='exit_protocol.tasks.perform_burial')
def perform_burial(session_id):
    """
    Final burial action. Must be idempotent.
    Creates CemeteryEntry, archives board, generates autopsy data.
    """
    from .models import HospiceSession, CemeteryEntry, ProjectHealthSignal
    from . import ai_utils
    from kanban.models import Board, Task
    from kanban.audit_utils import log_audit
    from messaging.models import Notification
    from django.contrib.auth.models import User

    try:
        session = HospiceSession.objects.select_related('board', 'initiated_by').get(id=session_id)
    except HospiceSession.DoesNotExist:
        return

    board = session.board
    user = session.initiated_by

    # Idempotency: skip only if the session is already marked buried (fully processed).
    # A pre-created stub entry (burial_pending) should still be updated with AI content.
    if session.status == 'buried':
        logger.info(f"[ExitProtocol] Session {session_id} already buried, skipping")
        return

    now = timezone.now()

    # ── 1. Snapshot board metadata ──
    total_tasks = Task.objects.filter(column__board=board).count()
    completed_tasks = Task.objects.filter(column__board=board, completed_at__isnull=False).count()

    team_size = 0
    try:
        from kanban.models import BoardMembership
        team_size = BoardMembership.objects.filter(board=board).count()
    except Exception:
        team_size = 0

    budget_allocated = None
    budget_spent = None
    try:
        from kanban.budget_models import ProjectBudget
        budget = ProjectBudget.objects.get(board=board)
        budget_allocated = budget.allocated_budget
        budget_spent = budget.get_spent_amount()
    except Exception:
        pass

    # ── 2. Classify cause of death ──
    cause = 'zombie_death'
    cause_rationale = ''
    contributing_factors = []

    if user:
        # Gather context for classification
        completion_pct = round(completed_tasks / total_tasks * 100) if total_tasks > 0 else 0

        # Velocity data
        velocity_ratio = 'Not available'
        try:
            from kanban.burndown_models import TeamVelocitySnapshot
            snapshots = TeamVelocitySnapshot.objects.filter(board=board).order_by('-period_end')
            if snapshots.count() >= 2:
                latest = snapshots.first().tasks_completed
                earliest = snapshots.last().tasks_completed
                if earliest > 0:
                    velocity_ratio = f"{latest / earliest:.1%}"
        except Exception:
            pass

        # Scope changes
        scope_change_count = 0
        scope_change_pct = 0
        try:
            from kanban.models import ScopeChangeSnapshot
            scope_change_count = ScopeChangeSnapshot.objects.filter(board=board).count()
            if board.baseline_task_count and board.baseline_task_count > 0:
                scope_change_pct = round((total_tasks - board.baseline_task_count) / board.baseline_task_count * 100)
        except Exception:
            pass

        # Team turnover
        team_turnover = 0
        try:
            # No is_active tracking in new model; turnover not available
            team_turnover = 0
        except Exception:
            pass

        # Knowledge graph events
        kg_events = 'None recorded'
        try:
            from knowledge_graph.models import MemoryNode
            events = MemoryNode.objects.filter(board=board).values_list('title', flat=True)[:10]
            if events:
                kg_events = '; '.join(events)
        except Exception:
            pass

        planned_duration = 'Not set'
        actual_duration = f"{(now - board.created_at).days} days" if board.created_at else 'Unknown'
        if board.project_deadline:
            planned_duration = f"{(board.project_deadline - board.created_at.date()).days} days" if board.created_at else 'Not calculable'

        cod_context = {
            'velocity_ratio': velocity_ratio,
            'budget_pct': round(float(budget_spent) / float(budget_allocated) * 100) if budget_allocated and budget_spent and float(budget_allocated) > 0 else 'Not tracked',
            'total_budget': str(budget_allocated) if budget_allocated else 'Not set',
            'completion_pct': completion_pct,
            'planned_duration': planned_duration,
            'actual_duration': actual_duration,
            'scope_change_count': scope_change_count,
            'scope_change_pct': scope_change_pct,
            'team_turnover_count': team_turnover,
            'strategic_notes': board.description or 'No strategic notes',
            'kg_events_summary': kg_events,
        }

        try:
            result = ai_utils.classify_cause_of_death(user, cod_context, board_id=board.id)
            cause = result.get('cause', 'zombie_death')
            cause_rationale = result.get('primary_rationale', '')
            contributing_factors = result.get('contributing_factors', [])
        except Exception as e:
            logger.error(f"[ExitProtocol] Cause of death classification failed: {e}")

    # ── 3. Build decline timeline ──
    decline_timeline = _build_decline_timeline(board)

    # ── 4. Extract lessons ──
    lessons_to_repeat = []
    lessons_to_avoid = []
    open_questions = []

    if user:
        # Knowledge graph summary for lessons
        kg_summary = 'No knowledge graph data'
        try:
            from knowledge_graph.models import MemoryNode
            nodes = MemoryNode.objects.filter(board=board).values_list('title', 'content')[:15]
            if nodes:
                kg_summary = '; '.join(f"{t}: {c[:100]}" for t, c in nodes)
        except Exception:
            pass

        # Pre-mortem hits
        premortem_hits = 'None'
        try:
            from kanban.premortem_models import PreMortemAnalysis
            pm = PreMortemAnalysis.objects.filter(board=board).first()
            if pm and pm.analysis_json:
                scenarios = pm.analysis_json.get('scenarios', [])
                premortem_hits = '; '.join(s.get('scenario', '')[:100] for s in scenarios[:3])
        except Exception:
            pass

        # Positive signals (completed tasks / milestones)
        positive_signals = f"{completed_tasks} of {total_tasks} tasks completed"

        lessons_context = {
            'project_name': board.name,
            'cause_of_death': cause,
            'knowledge_graph_summary': kg_summary,
            'premortem_hits': premortem_hits,
            'scope_changes': f"{scope_change_count} scope changes" if scope_change_count else 'No scope tracking data',
            'positive_signals': positive_signals,
        }

        try:
            result = ai_utils.extract_lessons(user, lessons_context, board_id=board.id)
            lessons_to_repeat = result.get('lessons_to_repeat', [])
            lessons_to_avoid = result.get('lessons_to_avoid', [])
            open_questions = result.get('open_questions', [])
        except Exception as e:
            logger.error(f"[ExitProtocol] Lessons extraction failed: {e}")

    # ── 5-6. Generate autopsy summary and tags ──
    autopsy_summary = (
        f"Project '{board.name}' was archived on {now.strftime('%Y-%m-%d')}. "
        f"Cause: {cause}. {cause_rationale} "
        f"Team size: {team_size}. Tasks: {completed_tasks}/{total_tasks} completed."
    )

    tags = []
    if user:
        try:
            key_lessons = '; '.join(
                l.get('lesson', '') for l in (lessons_to_repeat + lessons_to_avoid)[:5]
            )
            tags = ai_utils.generate_tags(user, {
                'project_name': board.name,
                'project_description': board.description or '',
                'cause_of_death': cause,
                'key_lessons': key_lessons or 'No lessons extracted',
            }, board_id=board.id)
            if not isinstance(tags, list):
                tags = []
        except Exception as e:
            logger.debug(f"[ExitProtocol] Tag generation failed: {e}")
            tags = [cause, board.name.lower()]

    # ── Create or update CemeteryEntry ──
    # A stub entry may already exist (created synchronously in the view on "Proceed to Burial"
    # so the cemetery list shows it immediately). Update it with the full AI-generated data.
    entry, _created = CemeteryEntry.objects.update_or_create(
        hospice_session=session,
        defaults=dict(
            board=board,
            project_name=board.name,
            project_description=board.description or '',
            board_id_snapshot=board.id,
            team_size=team_size,
            total_tasks=total_tasks,
            completed_tasks=completed_tasks,
            budget_allocated=budget_allocated,
            budget_spent=budget_spent,
            start_date=board.created_at.date() if board.created_at else None,
            end_date=now.date(),
            cause_of_death=cause,
            ai_cause_rationale=cause_rationale,
            contributing_factors=contributing_factors,
            autopsy_report={
                'cause_of_death': cause,
                'rationale': cause_rationale,
                'contributing_factors': contributing_factors,
                'lessons_to_repeat': lessons_to_repeat,
                'lessons_to_avoid': lessons_to_avoid,
                'open_questions': open_questions,
                'decline_timeline': decline_timeline,
            },
            autopsy_summary=autopsy_summary,
            lessons_to_repeat=lessons_to_repeat,
            lessons_to_avoid=lessons_to_avoid,
            open_questions=open_questions,
            decline_timeline=decline_timeline,
            tags=tags,
        ),
    )

    # ── 7. Archive board ──
    board.is_archived = True
    board.archived_at = now
    board.save(update_fields=['is_archived', 'archived_at'])

    # ── 8. Mark session as buried ──
    session.status = 'buried'
    session.buried_at = now
    session.save(update_fields=['status', 'buried_at'])

    # ── 9. Send closure notification ──
    from django.contrib.auth.models import User
    members = User.objects.filter(board_memberships__board=board)
    sender = user if user else User.objects.filter(is_superuser=True).first()
    if sender:
        for member in members:
            if member.id != sender.id:
                Notification.objects.create(
                    recipient=member,
                    sender=sender,
                    notification_type='ACTIVITY',
                    text=(
                        f"Project \"{board.name}\" has been gracefully archived. "
                        f"View the autopsy report to see what we learned."
                    ),
                    action_url=f'/cemetery/{entry.id}/',
                )

    # ── 10. Audit log ──
    log_audit(
        action_type='board.updated',
        user=user,
        object_type='board',
        object_id=board.id,
        object_repr=f"Project burial: {board.name}",
        board_id=board.id,
        changes={'action': 'project_burial', 'cemetery_entry_id': entry.id},
    )

    logger.info(f"[ExitProtocol] Burial complete for board {board.id}, cemetery entry {entry.id}")


def _build_decline_timeline(board):
    """Constructs chronological timeline of key negative events."""
    timeline = []

    # From Knowledge Graph
    try:
        from knowledge_graph.models import MemoryNode
        events = MemoryNode.objects.filter(
            board=board,
            node_type__in=['risk_event', 'scope_change', 'conflict_resolution'],
        ).order_by('created_at')

        for event in events:
            severity = 3  # default
            if event.node_type == 'risk_event':
                severity = 4
            elif event.node_type == 'scope_change':
                severity = 3
            timeline.append({
                'date': event.created_at.strftime('%Y-%m-%d'),
                'event': event.title,
                'severity': severity,
                'source': f'Knowledge Graph ({event.node_type})',
            })
    except Exception:
        pass

    # From Velocity drops
    try:
        from kanban.burndown_models import TeamVelocitySnapshot
        snapshots = list(
            TeamVelocitySnapshot.objects.filter(board=board).order_by('period_end')
        )
        for i in range(1, len(snapshots)):
            prev = snapshots[i - 1].tasks_completed
            curr = snapshots[i].tasks_completed
            if prev > 0 and curr < prev * 0.5:  # >50% drop
                timeline.append({
                    'date': snapshots[i].period_end.strftime('%Y-%m-%d'),
                    'event': f"Velocity dropped {round((prev - curr) / prev * 100)}%",
                    'severity': 4,
                    'source': 'Velocity Data',
                })
    except Exception:
        pass

    # From Scope Timeline Events
    try:
        from kanban.scope_autopsy_models import ScopeTimelineEvent
        scope_events = ScopeTimelineEvent.objects.filter(
            report__board=board, is_major_event=True
        ).order_by('event_date')

        for se in scope_events:
            timeline.append({
                'date': se.event_date.strftime('%Y-%m-%d') if se.event_date else 'Unknown',
                'event': se.description if hasattr(se, 'description') else f"Scope change: +{se.net_task_change} tasks",
                'severity': min(abs(se.net_task_change or 0) // 3 + 2, 5),
                'source': 'Scope Autopsy',
            })
    except Exception:
        pass

    # Sort by date
    timeline.sort(key=lambda x: x.get('date', ''))
    return timeline
