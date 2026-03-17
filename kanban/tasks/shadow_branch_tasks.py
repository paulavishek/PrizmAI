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
    Scale feasibility from 0-1 float to 0-100 integer.
    
    Args:
        float_score: Float value between 0-1
    
    Returns:
        Integer value between 0-100 (rounded to nearest int)
    """
    if float_score is None:
        return 0
    return round(min(1.0, max(0.0, float_score)) * 100)


def extract_branch_params(branch):
    """
    Extract the current slider parameter values from a branch's latest snapshot.
    
    Used to re-run the what-if simulation with the same parameters.
    
    Args:
        branch: ShadowBranch instance
    
    Returns:
        dict with keys: tasks_added, team_size_delta, deadline_shift_days
    """
    latest_snapshot = branch.get_latest_snapshot()
    if not latest_snapshot:
        # Fallback: read parameters from linked source scenario
        if branch.source_scenario and branch.source_scenario.input_parameters:
            params = branch.source_scenario.input_parameters
            return {
                'tasks_added': int(params.get('tasks_added', 0)),
                'team_size_delta': int(params.get('team_size_delta', 0)),
                'deadline_shift_days': int(params.get('deadline_shift_days', 0)),
            }
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

        for branch in active_branches:
            try:
                # Extract current parameters from branch's latest snapshot
                params = extract_branch_params(branch)

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

                # Create new snapshot with current results
                new_snapshot = BranchSnapshot.objects.create(
                    branch=branch,
                    scope_delta=params['tasks_added'],
                    team_delta=params['team_size_delta'],
                    deadline_delta_weeks=params['deadline_shift_days'] // 7,  # Convert days back to weeks
                    feasibility_score=new_feasibility,
                    projected_completion_date=projected_date,
                    projected_budget_utilization=results.get('projected', {}).get('budget_utilization_pct'),
                    conflicts_detected=results.get('new_conflicts', []),
                    gemini_recommendation=recommendation_text,
                )
                snapshots_created += 1

                # Log divergence if score changed by more than 5 points
                if abs(new_feasibility - old_score) > 5:
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
