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
import time

logger = logging.getLogger(__name__)


MIN_BASELINE_VELOCITY = 0.5

# Serialization lock for the read-dedup-insert critical section of a recalc.
# Two recalcs for the same board can fire near-simultaneously from different
# processes — e.g. the inline "Manual refresh" running in the Daphne request
# thread and the countdown=2 "Task completed" Celery task in the worker.  Each
# reads get_latest_snapshot() before the other commits its INSERT, so neither
# sees the other as a duplicate and both land byte-identical rows one second
# apart (the "×2 unchanged" pairs in Snapshot History).  Holding a per-board
# lock across the loop makes the second recalc wait, so its dedup check sees
# the first's committed snapshot and correctly suppresses the duplicate.
# Must live on the cross-process 'ai_cache' (Redis) — 'default' is per-process
# LocMemCache in local DEBUG and would NOT span the Daphne thread + Celery
# worker, which is exactly where the race occurs (see sandbox_provisioning).
SHADOW_RECALC_LOCK_TTL = 60          # seconds; safety net if a holder crashes
SHADOW_RECALC_LOCK_WAIT = 8.0        # max seconds to wait for the lock
SHADOW_RECALC_LOCK_POLL = 0.1        # spin-wait poll interval

# Minimum score movement (in points, 0-100 scale) from a real board event
# before it is recorded as a "Significant Score Change" (BranchDivergenceLog).
# Kept low so moderate real-world shifts register; heartbeats/baseline
# corrections are excluded separately via is_real_board_event().
DIVERGENCE_THRESHOLD = 2

# Trigger strings that represent a heartbeat / housekeeping recalc rather
# than a real-world event.  Snapshots from these may be dedup'd; snapshots
# from any other trigger always land in history so the audit trail reflects
# every task completion, deadline shift, team change, branch link, etc.
HEARTBEAT_TRIGGERS = frozenset({
    'Periodic branch refresh',
    'Manual recalculation',
    # User-clicked "Refresh Scores" on the Shadow Board.  Treated as a
    # heartbeat so an idle click on a quiet board doesn't bloat Snapshot
    # History with identical entries every time.
    'Manual refresh',
})

# Trigger prefixes for snapshots that re-baseline a branch against the live
# board WITHOUT a real-world board event having occurred (branch creation,
# restoring an archived branch).  Like heartbeats, these must NOT be counted
# as "today's progress" in the Quantum Standup impact table — otherwise a
# restore that corrects a stale demo score reads as a dramatic same-day swing.
BASELINE_CORRECTION_PREFIXES = (
    'Branch restored',
    'Branch "',  # 'Branch "<name>" created'
    # Demo sandbox provisioning/reset clones branches with the template's stale
    # snapshot and then recalcs them to the live value — a baseline correction,
    # not real-world work, so it must not log a divergence or show in standup.
    'Sandbox provisioned',
)


def is_real_board_event(trigger_event: str) -> bool:
    """
    True when `trigger_event` represents a genuine real-world board change
    (task completed, deadline moved, team member added/removed) rather than a
    heartbeat or a baseline correction (create/restore).  Drives which
    snapshots the "How It Affected Your Branches" standup attributes to
    today's progress.
    """
    if not trigger_event:
        return False
    if trigger_event in HEARTBEAT_TRIGGERS:
        return False
    if any(trigger_event.startswith(p) for p in BASELINE_CORRECTION_PREFIXES):
        return False
    return True


def is_baseline_correction(trigger_event: str) -> bool:
    """
    True when `trigger_event` re-baselines a branch against the live board
    WITHOUT any real-world event having occurred (branch created/restored,
    sandbox-cloned, or a legacy blank trigger from before this field existed).
    Distinct from a heartbeat ("Manual refresh"): a heartbeat still reflects
    genuinely-live board state, so it should count toward "today's real
    progress" if real work happened before it; a correction should not,
    because it can jump the score by dozens of points purely from re-syncing
    stale template/demo data.  Used to anchor the "How It Affected Your
    Branches" before/after comparison past any such jump.
    """
    if not trigger_event:
        return True
    return any(trigger_event.startswith(p) for p in BASELINE_CORRECTION_PREFIXES)


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
    from kanban.models import TaskActivity

    cutoff = timezone.now() - timedelta(days=7)
    # Candidates = tasks with a move/update activity in the window. The
    # Done-ness gate is applied per-task below via Column.is_done() (which
    # honours the structural column_type marker), so we don't pre-filter on the
    # activity description text — that would silently miss renamed Done columns
    # (e.g. "Finished"/"Achieved").
    qs = (
        TaskActivity.objects
        .filter(
            task__column__board=board,
            task__item_type='task',
            activity_type__in=['moved', 'updated'],
            created_at__gte=cutoff,
        )
        .select_related('task', 'task__column')
    )

    seen = set()
    for act in qs:
        if act.task_id in seen:
            continue
        if act.task.column.is_done():
            seen.add(act.task_id)

    # 7-day count IS already per-week; no scaling needed.
    return float(len(seen))


def _is_duplicate_snapshot(latest, new_feasibility, new_proj_date,
                            new_budget_util, new_conflicts,
                            new_scope_delta=None, new_team_delta=None,
                            new_deadline_delta_weeks=None):
    """
    True if a new snapshot would be functionally identical to the latest one
    AND we already have one today.  Applied to every trigger (heartbeats and
    real board events alike): allows exactly one snapshot per day per distinct
    state so the Feasibility Trend chart stays continuous on quiet days without
    bloating Snapshot History with duplicates (e.g. a burst of task-completion
    recalcs that all land on the same score).

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


def run_branch_recalc_sync(board_id, trigger_event='Manual recalculation',
                           branch_id=None, skip_ai=False):
    """
    Run the per-branch recalc loop synchronously in the caller's thread.

    This is the shared implementation behind both the Celery task
    (`recalculate_branches_for_board`) and the manual "Refresh Scores"
    HTTP endpoint.  Splitting it out lets the refresh endpoint produce
    fresh snapshots inline so the user sees results immediately after
    the page reload, instead of relying on a Celery worker to pick up
    the task in the next few seconds.

    Args:
        board_id: Integer board ID.
        trigger_event: Human-readable description of what triggered the
            recalc — surfaces in BranchDivergenceLog.trigger_event.
        branch_id: When supplied, only that branch is recalculated.  Used
            by creation / link-scenario paths so they cannot mutate
            unrelated branches' snapshots.
        skip_ai: When True, do NOT call Gemini for the AI recommendation.
            The manual-refresh endpoint sets this so the user isn't
            blocked for 5–10 seconds per branch on a slow AI call; the
            recommendation gets backfilled by the next scheduled recalc.

    Every recalc path (task completion, deadline/team change, restore,
    create, manual refresh) lands the engine's true deterministic value
    directly.  There is intentionally no per-cycle smoothing: the score is
    a pure function of the live board state, so recalculating with no real
    change returns the identical number every time (and the daily-heartbeat
    dedup then suppresses a duplicate snapshot).

    Returns:
        dict {'divergences_logged': int, 'snapshots_created': int,
              'snapshot_ids': list[int]}
    """
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
    logger.info(
        f'Recalculating branches for board {board.name} (ID: {board_id}), '
        f'trigger: {trigger_event}, scope: '
        f'{"branch=" + str(branch_id) if branch_id else "all active"}, '
        f'skip_ai={skip_ai}'
    )

    # Fetch branches to recalculate. When branch_id is supplied, restrict
    # to that single branch — events scoped to one branch (creation,
    # scenario link) must never touch other branches' snapshots.
    active_branches = ShadowBranch.objects.filter(
        board=board,
        status='active',
    ).select_related('board')
    if branch_id is not None:
        active_branches = active_branches.filter(id=branch_id)

    if not active_branches.exists():
        logger.info(f'No active branches found for board {board_id}')
        return {'divergences_logged': 0, 'snapshots_created': 0}

    divergences_created = 0
    snapshots_created = 0
    snapshot_ids = []

    # Serialize the read-dedup-insert loop against any other recalc for this
    # same board so concurrent triggers (inline Manual refresh + countdown
    # Task-completed task) don't each miss the other's snapshot and write a
    # duplicate.  We WAIT for the lock (bounded) rather than bail: dropping a
    # recalc could lose a real board event.  Failures acquiring the lock fail
    # open — correctness of dedup degrades to the old behaviour, never blocks.
    lock_cache = caches['ai_cache']
    lock_key = f'shadow_recalc_lock_{board_id}'
    got_lock = False
    deadline = time.monotonic() + SHADOW_RECALC_LOCK_WAIT
    while True:
        try:
            got_lock = lock_cache.add(lock_key, '1', timeout=SHADOW_RECALC_LOCK_TTL)
        except Exception:
            got_lock = True  # cache unavailable — fail open, never block a recalc
        if got_lock or time.monotonic() >= deadline:
            break
        time.sleep(SHADOW_RECALC_LOCK_POLL)
    if not got_lock:
        logger.warning(
            f'Proceeding with branch recalc for board {board_id} without the '
            f'serialization lock after waiting {SHADOW_RECALC_LOCK_WAIT}s '
            f'(trigger={trigger_event!r}) — a duplicate snapshot is possible.'
        )

    # Compute the board-wide actual 7-day velocity once per recalc cycle.
    # Each branch then derives its own velocity_health by comparing this
    # against the velocity captured at branch creation.
    actual_7d_velocity = compute_actual_7d_velocity(board)

    for branch in active_branches:
        try:
            params = extract_branch_params(branch)

            # Derive velocity health for this branch.  If the branch has no
            # baseline velocity recorded (legacy / pre-migration branches),
            # snapshot the current board velocity now so subsequent recalcs
            # have something to compare against, and treat this run as neutral.
            if not branch.baseline_velocity_per_week:
                lazy_baseline = (
                    compute_baseline_velocity(board) or actual_7d_velocity or 0.0
                )
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

            engine = WhatIfEngine(board)
            results = engine.simulate(params)

            if not results:
                logger.warning(f'Simulate returned empty results for branch {branch.id}')
                continue

            new_feasibility = scale_feasibility(results.get('feasibility_score', 0))

            latest_snapshot = branch.get_latest_snapshot()
            old_score = 0
            if latest_snapshot:
                old_score = latest_snapshot.feasibility_score

            # --- Gemini AI Analysis ---
            # The manual-refresh endpoint sets skip_ai=True so the user
            # isn't blocked for 5-10s per branch waiting on Gemini.  When
            # skipped, the snapshot lands without a recommendation; the
            # next heartbeat / event recalc backfills it.
            recommendation_text = ''
            if not skip_ai:
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

            projected_date = _parse_date(
                results.get('projected', {}).get('predicted_date')
            )
            if not projected_date:
                projected_date = _estimate_completion_date(results)

            new_budget_util = results.get('projected', {}).get('budget_utilization_pct')
            new_conflicts = results.get('new_conflicts', [])

            # No per-cycle smoothing: new_feasibility is the engine's true
            # value for the current board state.  Every path (event, restore,
            # create, manual refresh) lands it directly, so recalculating with
            # no real change is idempotent and repeated refreshes never drift.

            # --- Dedup (applies to ALL triggers, not just heartbeats) ---
            # Skip creating a snapshot that would be functionally identical to
            # the latest one already recorded today (same 2dp score, same
            # scope/team/deadline levers, same conflicts).  This used to run for
            # heartbeats only, so real board events always wrote a row "for the
            # audit trail" — but when the solo Celery worker processes a burst of
            # task-completion signals together, every recalc sees the SAME final
            # board state and produced a string of byte-identical snapshots
            # (e.g. 6× "73.58" one second apart), bloating Snapshot History and
            # the trend chart with rows that carry no new information.  A real
            # event that actually moves the score (or changes a lever/conflict)
            # still lands; the per-task audit record lives in TaskActivity /
            # the "Real Progress Today" standup table, not here.  The first
            # capture of each day is always allowed (see _is_duplicate_snapshot)
            # so the trend chart keeps a daily point on quiet days.
            new_deadline_weeks = params['deadline_shift_days'] // 7
            if _is_duplicate_snapshot(
                latest_snapshot, new_feasibility,
                projected_date, new_budget_util, new_conflicts,
                new_scope_delta=params['tasks_added'],
                new_team_delta=params['team_size_delta'],
                new_deadline_delta_weeks=new_deadline_weeks,
            ):
                logger.debug(
                    f'Skipping duplicate snapshot for branch '
                    f'{branch.id} (score={new_feasibility} unchanged today, '
                    f'trigger={trigger_event!r})'
                )
                continue

            new_snapshot = BranchSnapshot.objects.create(
                branch=branch,
                scope_delta=params['tasks_added'],
                team_delta=params['team_size_delta'],
                deadline_delta_weeks=params['deadline_shift_days'] // 7,
                feasibility_score=new_feasibility,
                projected_completion_date=projected_date,
                projected_budget_utilization=new_budget_util,
                conflicts_detected=new_conflicts,
                gemini_recommendation=recommendation_text,
                trigger_event=trigger_event,
            )
            snapshots_created += 1
            snapshot_ids.append(new_snapshot.id)

            # Log divergence only for genuine board events that moved the
            # score by more than DIVERGENCE_THRESHOLD points.  Heartbeats
            # ("Manual refresh") and baseline corrections ("Branch restored",
            # "Branch <name> created") are excluded — they correct a
            # stale/intermediate value rather than reflecting real-world work,
            # so surfacing them as a "Significant Score Change"
            # (e.g. "Manual refresh -25") misled users into thinking a refresh
            # tanked the score.  The threshold is 2 (not 5): once the
            # feasibility curve was widened to spread healthy branches across a
            # ~10-point band, real deadline/team/scope events routinely move the
            # score by 2-4 points, and a 5-point gate meant a freshly-promoted
            # branch that only saw such moves never logged anything — leaving
            # its "Significant Score Changes" section permanently empty while
            # seeded branches (with big historical swings) showed one.
            if (latest_snapshot is not None
                    and is_real_board_event(trigger_event)
                    and abs(float(new_feasibility) - float(old_score)) > DIVERGENCE_THRESHOLD):
                recent_cutoff = timezone.now() - timedelta(seconds=60)
                is_recent_dup = BranchDivergenceLog.objects.filter(
                    branch=branch,
                    trigger_event=trigger_event,
                    old_score=old_score,
                    new_score=new_feasibility,
                    logged_at__gte=recent_cutoff,
                ).exists()
                if is_recent_dup:
                    logger.debug(
                        f'Skipping duplicate divergence log for branch '
                        f'{branch.name}: identical entry within 60s '
                        f'(trigger: {trigger_event})'
                    )
                else:
                    BranchDivergenceLog.objects.create(
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
                cache.set(cache_key, snapshot_data, timeout=15 * 60)
                logger.debug(f'Cached branch snapshot {branch.id} in Redis')
            except Exception as cache_err:
                logger.warning(f'Failed to cache branch snapshot {branch.id}: {cache_err}')

        except Exception as branch_err:
            logger.error(f'Error recalculating branch {branch.id}: {branch_err}', exc_info=True)
            continue

    # Release the serialization lock so the next queued recalc for this board
    # can proceed and see the snapshots we just committed.  Best-effort: the
    # lock also carries a TTL so a crash before this point self-heals.
    if got_lock:
        try:
            lock_cache.delete(lock_key)
        except Exception:
            pass

    logger.info(
        f'Branch recalculation complete: {snapshots_created} snapshots created, '
        f'{divergences_created} divergences logged'
    )
    return {
        'divergences_logged': divergences_created,
        'snapshots_created': snapshots_created,
        'snapshot_ids': snapshot_ids,
    }


@shared_task(
    bind=True,
    name='kanban.recalculate_branches',
    max_retries=2,
    default_retry_delay=10,
    time_limit=300,
    soft_time_limit=270,
)
def recalculate_branches_for_board(self, board_id, trigger_event='Manual recalculation',
                                   branch_id=None):
    """
    Celery wrapper around `run_branch_recalc_sync`.  Used by Django signals
    (task completion, deadline change, team change) and by the create /
    link-scenario paths.  The Celery indirection gives those code paths
    retry semantics and prevents AI latency from blocking the request.
    """
    try:
        return run_branch_recalc_sync(
            board_id, trigger_event=trigger_event, branch_id=branch_id,
        )
    except Exception as e:
        logger.error(
            f'Task recalculate_branches_for_board failed for board {board_id}: {e}',
            exc_info=True,
        )
        raise self.retry(exc=e, countdown=10)


@shared_task(
    bind=True,
    name='kanban.generate_ai_for_branch_snapshot',
    max_retries=2,
    default_retry_delay=15,
    time_limit=180,
    soft_time_limit=150,
)
def generate_ai_for_branch_snapshot(self, snapshot_id):
    """
    Generate the Gemini AI recommendation for an existing BranchSnapshot and
    save it in place. Used immediately after branch creation so the freshly
    promoted branch's detail page shows an AI recommendation within seconds
    instead of "No AI recommendation available for this snapshot."

    Args:
        snapshot_id: PK of BranchSnapshot to enrich. The snapshot's existing
                     scope/team/deadline deltas + the current board state are
                     fed to WhatIfEngine.analyze_with_ai.

    Updates the snapshot's `gemini_recommendation` field only — feasibility
    score, conflicts, projection date, etc. are not recomputed (the snapshot
    was just produced by the same engine moments ago and should not drift).
    """
    try:
        from kanban.shadow_models import BranchSnapshot
        from kanban.utils.whatif_engine import WhatIfEngine

        snapshot = (
            BranchSnapshot.objects
            .select_related('branch', 'branch__board')
            .get(pk=snapshot_id)
        )
        if snapshot.gemini_recommendation:
            return {'skipped': True, 'reason': 'already populated'}

        branch = snapshot.branch
        board = branch.board

        params = {
            'tasks_added': snapshot.scope_delta,
            'team_size_delta': snapshot.team_delta,
            'deadline_shift_days': snapshot.deadline_delta_weeks * 7,
        }
        # Match the live recalc path: include velocity_health so the AI sees
        # the same projection signal the score is anchored to.
        actual_vel = compute_actual_7d_velocity(board)
        baseline_vel = branch.baseline_velocity_per_week or actual_vel or 0.0
        params['velocity_health'] = (
            (actual_vel / baseline_vel) if baseline_vel > 0 else 1.0
        )

        engine = WhatIfEngine(board)
        results = engine.simulate(params)
        if not results:
            return {'skipped': True, 'reason': 'simulate returned empty'}

        ai_result = engine.analyze_with_ai(params, results)
        recommendation_text = _format_ai_recommendation(ai_result)

        if recommendation_text:
            BranchSnapshot.objects.filter(pk=snapshot.pk).update(
                gemini_recommendation=recommendation_text,
            )
            logger.info(
                f'Backfilled AI recommendation for branch {branch.id} '
                f'snapshot {snapshot.pk}'
            )
            return {'updated': True}

        logger.warning(
            f'AI returned no recommendation text for branch {branch.id} '
            f'snapshot {snapshot.pk}'
        )
        return {'updated': False}

    except BranchSnapshot.DoesNotExist:
        logger.warning(
            f'generate_ai_for_branch_snapshot: snapshot {snapshot_id} not found'
        )
        return {'error': 'snapshot not found'}
    except Exception as e:
        logger.error(
            f'generate_ai_for_branch_snapshot failed for snapshot {snapshot_id}: {e}',
            exc_info=True,
        )
        raise self.retry(exc=e, countdown=15)
