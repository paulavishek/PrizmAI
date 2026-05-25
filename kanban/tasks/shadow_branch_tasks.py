"""
Shadow Board Celery Tasks

Async tasks for recalculating shadow branches whenever real board changes occur.
All Gemini API calls happen here in the Celery worker, not in the request cycle.
"""
from celery import shared_task
from datetime import date as date_type, timedelta
from django.utils import timezone
from django.core.cache import caches
import logging

logger = logging.getLogger(__name__)


MIN_BASELINE_VELOCITY = 0.5
MAX_PER_EVENT_DELTA = 15.0


def _parse_date(value):
    """Safely convert a date value that may be a string, date, or None."""
    if value is None:
        return None
    if isinstance(value, date_type):
        return value
    try:
        return date_type.fromisoformat(str(value)[:10])
    except (ValueError, TypeError):
        return None


def scale_feasibility(float_score):
    """
    Scale feasibility from 0-1 float to 0-100 with 2dp precision.

    Returns float (the BranchSnapshot.feasibility_score column is a
    DecimalField that quantizes on save).  2dp retention is important so
    single-task micro-nudges (sub-integer score changes) persist instead
    of being rounded away into duplicates.
    """
    if float_score is None:
        return 0.0
    return round(min(1.0, max(0.0, float(float_score))) * 100, 2)


def extract_branch_params(branch):
    """
    Extract the current slider parameter values for a branch.

    Priority:
    1. If the branch has a linked source_scenario, use its input_parameters.
       This ensures that after linking/changing a scenario, the very next
       recalculation always picks up the scenario's values — even before a
       snapshot with those values has been stored.
    2. Otherwise fall back to the latest snapshot's stored delta fields.

    Args:
        branch: ShadowBranch instance

    Returns:
        dict with keys: tasks_added, team_size_delta, deadline_shift_days
    """
    # Priority 1: use the linked scenario's parameters directly
    if branch.source_scenario and branch.source_scenario.input_parameters:
        params = branch.source_scenario.input_parameters
        return {
            'tasks_added': int(params.get('tasks_added', 0)),
            'team_size_delta': int(params.get('team_size_delta', 0)),
            'deadline_shift_days': int(params.get('deadline_shift_days', 0)),
        }

    # Priority 2: read stored deltas from the latest snapshot
    latest_snapshot = branch.get_latest_snapshot()
    if not latest_snapshot:
        return {
            'tasks_added': 0,
            'team_size_delta': 0,
            'deadline_shift_days': 0,
        }

    return {
        'tasks_added': latest_snapshot.scope_delta,
        'team_size_delta': latest_snapshot.team_delta,
        'deadline_shift_days': latest_snapshot.deadline_delta_weeks * 7,  # Convert weeks to days
    }


def _format_ai_recommendation(ai_result):
    """
    Format the structured AI analysis dict into a readable recommendation string.

    Args:
        ai_result: dict from WhatIfEngine.analyze_with_ai()

    Returns:
        str: Human-readable recommendation text, or empty string on failure.
    """
    if not ai_result or 'error' in ai_result:
        return ''

    parts = []

    assessment = ai_result.get('feasibility_assessment', '')
    if assessment:
        parts.append(f"Feasibility: {assessment}")

    risk_summary = ai_result.get('risk_summary', '')
    if risk_summary:
        parts.append(f"\nRisk Summary:\n{risk_summary}")

    mitigations = ai_result.get('recommended_mitigations', [])
    if mitigations:
        items = '\n'.join(f"  • {m}" for m in mitigations if m)
        parts.append(f"\nRecommended Mitigations:\n{items}")

    trade_off = ai_result.get('trade_off_analysis', '')
    if trade_off:
        parts.append(f"\nTrade-off Analysis:\n{trade_off}")

    alternative = ai_result.get('alternative_suggestion', '')
    if alternative:
        parts.append(f"\nAlternative Suggestion:\n{alternative}")

    return '\n'.join(parts).strip()


def compute_baseline_velocity(board):
    """
    Snapshot the board's current tasks/week velocity at branch-creation time.

    Uses the same logic as WhatIfEngine._capture_baseline so the velocity
    health comparison stays self-consistent.

    Returns:
        float (tasks/week) or 0.0 if no velocity data available yet.
    """
    from kanban.utils.whatif_engine import WhatIfEngine
    try:
        baseline = WhatIfEngine(board)._capture_baseline()
        raw = float(baseline.get('velocity_per_week') or 0.0)
        # Floor the baseline when the engine reports a real but tiny value
        # so velocity_health = actual / baseline can't explode to 20x-50x.
        # 0.0 still propagates as "no data" — the recalc path treats that
        # as neutral (velocity_health = 1.0).
        if raw > 0:
            return max(raw, MIN_BASELINE_VELOCITY)
        return 0.0
    except Exception as exc:
        logger.warning('compute_baseline_velocity failed for board %s: %s', board.pk, exc)
        return 0.0


def compute_actual_7d_velocity(board):
    """
    Live 7-day completion rate (tasks/week) on the real board.

    Counts unique tasks moved into a Done/Complete column in the last 7 days,
    using TaskActivity rows so demo data seeding doesn't pollute the signal
    (Task.completed_at is stamped by the seeder; TaskActivity is only written
    by user-facing views).
    """
    from datetime import timedelta
    from django.db.models import Q
    from kanban.models import TaskActivity

    cutoff = timezone.now() - timedelta(days=7)
    qs = (
        TaskActivity.objects
        .filter(
            task__column__board=board,
            task__item_type='task',
            activity_type__in=['moved', 'updated'],
            created_at__gte=cutoff,
        )
        .filter(Q(description__icontains='done') | Q(description__icontains='complete'))
        .select_related('task', 'task__column')
    )

    seen = set()
    for act in qs:
        if act.task_id in seen:
            continue
        col_lower = act.task.column.name.lower()
        if 'done' in col_lower or 'complete' in col_lower:
            seen.add(act.task_id)

    # 7-day count IS already per-week; no scaling needed.
    return float(len(seen))


def _is_duplicate_snapshot(latest, new_feasibility, new_proj_date,
                            new_budget_util, new_conflicts,
                            new_scope_delta=None, new_team_delta=None,
                            new_deadline_delta_weeks=None):
    """
    True if a new snapshot would be functionally identical to the latest one
    AND we already have one today.  Allows exactly one heartbeat snapshot per
    day so the Feasibility Trend chart stays continuous on quiet days without
    bloating Snapshot History with minute-by-minute duplicates.

    What "identical" means here:
      * Feasibility score (rounded to 2dp — matches what users see in the UI)
      * Scenario sliders (scope, team, deadline) — these are the user's actual
        levers and never drift on their own.
      * Conflicts list — different conflicts represent a meaningful change.

    What we INTENTIONALLY ignore for dedup:
      * projected_completion_date — recomputed live each recalc (remaining
        tasks / velocity), drifts by 1 day naturally as the calendar moves;
        treating those as "different" was flooding the timeline with cosmetic
        duplicates.
      * projected_budget_utilization — float arithmetic produces sub-percent
        wobble even when nothing meaningful changed.

    Those two are still persisted on the new snapshot; we just don't gate
    snapshot creation on them.
    """
    if not latest:
        return False
    if latest.captured_at.date() != date_type.today():
        return False  # first capture today — always allow
    # Decimal vs float/int comparison tolerance — round to 2dp for the dedup check.
    try:
        latest_score = round(float(latest.feasibility_score), 2)
    except (TypeError, ValueError):
        latest_score = 0.0
    new_score = round(float(new_feasibility), 2)
    if latest_score != new_score:
        return False
    if (latest.conflicts_detected or []) != (new_conflicts or []):
        return False
    # Compare scenario sliders when the caller supplies them.  (Legacy callers
    # that don't pass them get the score+conflicts check only — still tighter
    # than the old date/budget-sensitive comparison.)
    if new_scope_delta is not None and latest.scope_delta != new_scope_delta:
        return False
    if new_team_delta is not None and latest.team_delta != new_team_delta:
        return False
    if (new_deadline_delta_weeks is not None
            and latest.deadline_delta_weeks != new_deadline_delta_weeks):
        return False
    return True


def _estimate_completion_date(simulation_results):
    """
    Estimate a projected completion date from simulation results when the engine
    couldn't compute one (e.g. no burndown prediction in the DB).

    Uses velocity and remaining tasks to project a date from today.

    Returns:
        date or None
    """
    projected = simulation_results.get('projected', {})
    # If the engine already computed a date, use it
    engine_date = projected.get('predicted_date')
    if engine_date:
        return None  # Signal caller to use the engine value

    velocity = projected.get('velocity_per_week', 0)
    remaining = projected.get('remaining_tasks', 0)

    if velocity and velocity >= 0.5 and remaining > 0:
        weeks_needed = remaining / velocity
        return date_type.today() + timedelta(weeks=weeks_needed)

    return None


@shared_task(
    bind=True,
    name='kanban.recalculate_branches',
    max_retries=2,
    default_retry_delay=10,
    time_limit=300,
    soft_time_limit=270,
)
def recalculate_branches_for_board(self, board_id, trigger_event='Manual recalculation'):
    """
    Recalculate feasibility scores for all active shadow branches on a board.
    
    Triggered by Django signals when:
      - A task is completed
      - Team membership changes
      - Board deadline changes
    
    Args:
        board_id: Integer board ID
        trigger_event: String description of what triggered the recalculation
                      (e.g., "Task 'Design API' completed", "Team member added")
    
    Returns:
        dict with summary of divergences logged
    """
    try:
        from django.core.cache import cache as _cache
        if _cache.get(f'demo_shadow_lock_{board_id}'):
            logger.info(
                f'Skipping branch recalculation for board {board_id}: '
                'demo data populate in progress'
            )
            return {'divergences_logged': 0, 'snapshots_created': 0}

        from kanban.models import Board
        from kanban.shadow_models import ShadowBranch, BranchSnapshot, BranchDivergenceLog
        from kanban.utils.whatif_engine import WhatIfEngine

        board = Board.objects.get(pk=board_id)
        logger.info(f'Recalculating branches for board {board.name} (ID: {board_id}), trigger: {trigger_event}')

        # Fetch all active branches for this board
        active_branches = ShadowBranch.objects.filter(
            board=board,
            status='active',
        ).select_related('board')

        if not active_branches.exists():
            logger.info(f'No active branches found for board {board_id}')
            return {'divergences_logged': 0, 'snapshots_created': 0}

        divergences_created = 0
        snapshots_created = 0

        # Compute the board-wide actual 7-day velocity once per recalc cycle.
        # Each branch then derives its own velocity_health by comparing this
        # against the velocity captured at branch creation.
        actual_7d_velocity = compute_actual_7d_velocity(board)

        for branch in active_branches:
            try:
                # Extract current parameters from branch's latest snapshot
                params = extract_branch_params(branch)

                # Derive velocity health for this branch.  If the branch has no
                # baseline velocity recorded (legacy / pre-migration branches),
                # snapshot the current board velocity now so subsequent recalcs
                # have something to compare against, and treat this run as neutral.
                if not branch.baseline_velocity_per_week:
                    lazy_baseline = (
                        compute_baseline_velocity(board) or actual_7d_velocity or 0.0
                    )
                    # Apply the same floor as compute_baseline_velocity so the
                    # lazy-fill path can't capture a sub-floor value either.
                    if lazy_baseline > 0:
                        lazy_baseline = max(lazy_baseline, MIN_BASELINE_VELOCITY)
                    branch.baseline_velocity_per_week = lazy_baseline
                    if branch.baseline_velocity_per_week:
                        branch.save(update_fields=['baseline_velocity_per_week'])
                if branch.baseline_velocity_per_week and branch.baseline_velocity_per_week > 0:
                    params['velocity_health'] = (
                        actual_7d_velocity / branch.baseline_velocity_per_week
                    )
                else:
                    params['velocity_health'] = 1.0

                # Re-run what-if simulation with same parameters
                engine = WhatIfEngine(board)
                results = engine.simulate(params)

                if not results:
                    logger.warning(f'Simulate returned empty results for branch {branch.id}')
                    continue

                # Scale feasibility from 0-1 to 0-100
                # This captures how the SAME what-if parameters affect the CURRENT board state
                new_feasibility = scale_feasibility(results.get('feasibility_score', 0))

                # Get previous feasibility score from last snapshot
                latest_snapshot = branch.get_latest_snapshot()
                old_score = 0
                if latest_snapshot:
                    old_score = latest_snapshot.feasibility_score

                # --- Gemini AI Analysis ---
                # Call Gemini to generate a recommendation and enrich the snapshot
                recommendation_text = ''
                try:
                    ai_result = engine.analyze_with_ai(params, results)
                    recommendation_text = _format_ai_recommendation(ai_result)
                    if recommendation_text:
                        logger.info(f'Generated AI recommendation for branch {branch.id}')
                    else:
                        logger.warning(f'AI analysis returned empty for branch {branch.id}')
                except Exception as ai_err:
                    logger.warning(
                        f'Gemini AI analysis failed for branch {branch.id}: {ai_err}',
                        exc_info=True,
                    )
                    # Graceful degradation — snapshot is still created without recommendation

                # --- Projected Completion Date ---
                # Try the engine's computed date first, then fall back to velocity estimate
                projected_date = _parse_date(
                    results.get('projected', {}).get('predicted_date')
                )
                if not projected_date:
                    projected_date = _estimate_completion_date(results)

                new_budget_util = results.get('projected', {}).get('budget_utilization_pct')
                new_conflicts = results.get('new_conflicts', [])

                # --- Per-event delta cap ---
                # No single recalc cycle should move feasibility by more than
                # MAX_PER_EVENT_DELTA points.  This bounds compound movement
                # in the underlying penalty curves (delay_probability +
                # utilization + velocity_health) so a single task completion
                # can never produce a 50-point swing.  Only applied when
                # there's a prior snapshot to cap against — the first
                # snapshot for a branch is unconstrained.
                if latest_snapshot is not None:
                    try:
                        old_score_float = float(old_score)
                    except (TypeError, ValueError):
                        old_score_float = 0.0
                    raw_delta = new_feasibility - old_score_float
                    if abs(raw_delta) > MAX_PER_EVENT_DELTA:
                        capped_delta = (
                            MAX_PER_EVENT_DELTA if raw_delta > 0
                            else -MAX_PER_EVENT_DELTA
                        )
                        capped = old_score_float + capped_delta
                        logger.warning(
                            'Feasibility delta cap triggered for branch %s: '
                            'raw_delta=%.2f capped_delta=%.2f '
                            '(old=%.2f new_raw=%.2f new_capped=%.2f, '
                            'trigger=%s)',
                            branch.id, raw_delta, capped_delta,
                            old_score_float, new_feasibility, capped,
                            trigger_event,
                        )
                        new_feasibility = round(capped, 2)

                # --- Dedup + daily heartbeat ---
                # Skip snapshot creation if the user-facing fields would be
                # identical to the latest snapshot AND we already captured one
                # today.  First snapshot of a new day always proceeds
                # (heartbeat tick) so the trend chart stays continuous on
                # quiet days.
                new_deadline_weeks = params['deadline_shift_days'] // 7
                if _is_duplicate_snapshot(
                    latest_snapshot, new_feasibility,
                    projected_date, new_budget_util, new_conflicts,
                    new_scope_delta=params['tasks_added'],
                    new_team_delta=params['team_size_delta'],
                    new_deadline_delta_weeks=new_deadline_weeks,
                ):
                    logger.debug(
                        f'Skipping duplicate snapshot for branch {branch.id} '
                        f'(score={new_feasibility} unchanged today)'
                    )
                    continue

                # Create new snapshot with current results
                new_snapshot = BranchSnapshot.objects.create(
                    branch=branch,
                    scope_delta=params['tasks_added'],
                    team_delta=params['team_size_delta'],
                    deadline_delta_weeks=params['deadline_shift_days'] // 7,  # Convert days back to weeks
                    feasibility_score=new_feasibility,
                    projected_completion_date=projected_date,
                    projected_budget_utilization=new_budget_util,
                    conflicts_detected=new_conflicts,
                    gemini_recommendation=recommendation_text,
                )
                snapshots_created += 1

                # Log divergence if score changed by more than 5 points
                if abs(float(new_feasibility) - float(old_score)) > 5:
                    divergence_log = BranchDivergenceLog.objects.create(
                        branch=branch,
                        old_score=old_score,
                        new_score=new_feasibility,
                        trigger_event=trigger_event,
                    )
                    divergences_created += 1
                    logger.info(
                        f'Logged divergence for branch {branch.name}: {old_score} → {new_feasibility} '
                        f'(trigger: {trigger_event})'
                    )

                # Update Redis cache with latest snapshot (15-min TTL)
                try:
                    cache = caches['default']
                    cache_key = f'branch_snapshot:{branch.id}'
                    snapshot_data = {
                        'branch_id': branch.id,
                        'feasibility_score': new_snapshot.feasibility_score,
                        'projected_completion_date': str(new_snapshot.projected_completion_date),
                        'projected_budget_utilization': new_snapshot.projected_budget_utilization,
                        'scope_delta': new_snapshot.scope_delta,
                        'team_delta': new_snapshot.team_delta,
                        'deadline_delta_weeks': new_snapshot.deadline_delta_weeks,
                        'conflicts_detected': new_snapshot.conflicts_detected,
                        'gemini_recommendation': new_snapshot.gemini_recommendation,
                        'captured_at': new_snapshot.captured_at.isoformat(),
                    }
                    cache.set(cache_key, snapshot_data, timeout=15 * 60)  # 15 minutes
                    logger.debug(f'Cached branch snapshot {branch.id} in Redis')
                except Exception as cache_err:
                    logger.warning(f'Failed to cache branch snapshot {branch.id}: {cache_err}')

            except Exception as branch_err:
                logger.error(f'Error recalculating branch {branch.id}: {branch_err}', exc_info=True)
                # Continue with other branches even if one fails
                continue

        logger.info(
            f'Branch recalculation complete: {snapshots_created} snapshots created, '
            f'{divergences_created} divergences logged'
        )
        return {
            'divergences_logged': divergences_created,
            'snapshots_created': snapshots_created,
        }

    except Exception as e:
        logger.error(f'Task recalculate_branches_for_board failed for board {board_id}: {e}', exc_info=True)
        # Retry with exponential backoff
        raise self.retry(exc=e, countdown=10)
