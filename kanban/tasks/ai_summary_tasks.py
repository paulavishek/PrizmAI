"""
Celery tasks for async, enterprise-scale AI summary generation.

Architecture: Map-Reduce + Debounced Signal Trigger
- Level 1 (Worker):     generate_board_summary_task   — one LLM call per board
- Level 2 (Aggregator): generate_strategy_summary_task — aggregates board summaries
- Level 3 (Aggregator): generate_mission_summary_task  — aggregates strategy summaries
- Beat task:            generate_daily_executive_briefing — 08:00 IST daily

Debounce / Race-condition guard
  Signals use cache.add() (Redis SET NX) before enqueueing, so concurrent task
  saves on the same board always produce exactly ONE Celery task per window.
"""
import logging
from datetime import date

from celery import shared_task
from django.core.cache import caches

logger = logging.getLogger(__name__)

# Always use the dedicated AI cache backend (Redis DB 1) for lock keys
def _ai_cache():
    try:
        return caches['ai_cache']
    except Exception:
        from django.core.cache import cache
        return cache


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------

def _board_lock_key(board_id):
    return f'board_ai_lock_{board_id}'


def _release_board_lock(board_id):
    """Delete the debounce lock after the task finishes (or fails)."""
    try:
        _ai_cache().delete(_board_lock_key(board_id))
    except Exception as exc:
        logger.warning(f"Could not release board AI lock for board {board_id}: {exc}")


def _strategy_lock_key(strategy_id):
    return f'strategy_ai_lock_{strategy_id}'


def _release_strategy_lock(strategy_id):
    """Delete the debounce lock after the strategy task finishes (or fails)."""
    try:
        _ai_cache().delete(_strategy_lock_key(strategy_id))
    except Exception as exc:
        logger.warning(f"Could not release strategy AI lock for strategy {strategy_id}: {exc}")


def _mission_lock_key(mission_id):
    return f'mission_ai_lock_{mission_id}'


def _release_mission_lock(mission_id):
    """Delete the debounce lock after the mission task finishes (or fails)."""
    try:
        _ai_cache().delete(_mission_lock_key(mission_id))
    except Exception as exc:
        logger.warning(f"Could not release mission AI lock for mission {mission_id}: {exc}")


# ---------------------------------------------------------------------------
# Goal-Aware Analytics — auto-classification tasks
# ---------------------------------------------------------------------------

@shared_task(
    bind=True,
    name='kanban.ai_summary.classify_board_on_creation',
    max_retries=2,
    default_retry_delay=30,
    queue='summaries',
    time_limit=60,
    soft_time_limit=50,
)
def classify_board_on_creation(self, board_id):
    """Classify a newly created board's project type in the background."""
    from kanban.models import Board
    from kanban.utils.ai_utils import classify_board_project_type

    try:
        board = Board.objects.get(pk=board_id)
    except Board.DoesNotExist:
        logger.warning(f"Board {board_id} not found for classification")
        return

    if board.project_type is not None:
        logger.info(f"Board {board_id} already classified — skipping")
        return

    result = classify_board_project_type(board)
    if result:
        board.project_type = result['project_type']
        board.project_type_confidence = result['confidence']
        board.project_type_confirmed = False
        board.save(update_fields=['project_type', 'project_type_confidence', 'project_type_confirmed'])
        logger.info(f"Board {board_id} classified as {result['project_type']} (confidence={result['confidence']:.2f})")
    else:
        logger.warning(f"Board {board_id} classification failed")


@shared_task(
    bind=True,
    name='kanban.ai_summary.generate_proxy_metrics_on_goal_creation',
    max_retries=2,
    default_retry_delay=30,
    queue='summaries',
    time_limit=90,
    soft_time_limit=75,
)
def generate_proxy_metrics_on_goal_creation(self, goal_id):
    """Generate proxy metrics for a newly created goal in the background."""
    from kanban.models import OrganizationGoal, GoalProxyMetric
    from kanban.utils.ai_utils import generate_proxy_metrics

    try:
        goal = OrganizationGoal.objects.get(pk=goal_id)
    except OrganizationGoal.DoesNotExist:
        logger.warning(f"Goal {goal_id} not found for proxy metric generation")
        return

    if goal.proxy_metrics.exists():
        logger.info(f"Goal {goal_id} already has proxy metrics — skipping")
        return

    metrics = generate_proxy_metrics(goal)
    if metrics:
        GoalProxyMetric.objects.filter(goal=goal).delete()
        for i, m in enumerate(metrics):
            GoalProxyMetric.objects.create(
                goal=goal,
                name=m['name'],
                why_it_matters=m['why_it_matters'],
                how_to_measure=m['how_to_measure'],
                display_order=i,
            )
        logger.info(f"Generated {len(metrics)} proxy metrics for goal {goal_id}")
    else:
        logger.warning(f"Proxy metric generation failed for goal {goal_id}")


def _build_board_prompt(board_name, exception_lines, agg):
    """
    Build the structured Program-Manager prompt from pruned task data.

    exception_lines : list[str]  — full-detail rows for high-risk / blocked / overdue tasks
    agg             : dict       — aggregate counts for normal tasks
    """
    exc_block = "\n".join(exception_lines) if exception_lines else "  (none)"
    return f"""You are a Program Manager reviewing the '{board_name}' project board.

=== BOARD SNAPSHOT ===
Total tasks       : {agg['total']}
Completed         : {agg['completed']} ({agg['done_pct']}%)
In Progress       : {agg['in_progress']}
Not Started       : {agg['not_started']}
Overdue           : {agg['overdue']}
High / Critical Risk: {agg['high_risk']}

Lean Six Sigma breakdown (non-exception tasks):
  Value-Added     : {agg['lss_value_added']}
  Necessary NVA   : {agg['lss_necessary_nva']}
  Waste / Eliminate: {agg['lss_waste']}

Budget variance   : Estimated ${agg['estimated_cost']:.2f} vs Actual ${agg['actual_cost']:.2f}
                    (variance: ${agg['cost_variance']:+.2f})

=== EXCEPTION TASKS (Blocked / Overdue / High-Risk) — full detail ===
{exc_block}

=== YOUR TASK ===
Write 4–6 concise bullet points covering:
• Overall progress & health (tasks done, % complete, status)
• Top critical blockers — name tasks explicitly if listed above
• One actionable Lean Six Sigma Value-Add improvement
• Budget flag if actual cost exceeds estimate by more than 10%

Rules: Be factual. Do NOT invent data not listed above.
Each bullet MUST start with the • character. Output ONLY the bullet list — no headings, no paragraphs, no JSON."""


def _board_task_fallback(board, max_tasks=15):
    """Content-grounded fallback for a board with no saved AI summary.

    Returns aggregate counts PLUS a short list of real tasks (column, progress,
    overdue flag) so the strategy/mission roll-up has actual task content to
    describe rather than only counts — which forces the model to anchor on the
    strategy's name and confabulate domain detail.
    """
    from kanban.models import Task

    try:
        qs = (
            Task.objects.filter(column__board=board, item_type='task')
            .select_related('column')
            .order_by('column__position', 'position')
        )
        total = qs.count()
        if total == 0:
            return "no tasks yet"

        today = date.today()
        done = 0
        overdue = 0
        task_lines = []
        for t in qs:
            prog = t.progress or 0
            if prog >= 100:
                done += 1
            is_overdue = (
                t.due_date is not None
                and t.due_date.date() < today
                and prog < 100
            )
            if is_overdue:
                overdue += 1
            if len(task_lines) < max_tasks:
                col = (t.column.name if t.column else 'Unassigned')
                flag = ' OVERDUE' if is_overdue else ''
                task_lines.append(f'    · [{col}] "{t.title}" — {prog}%{flag}')

        header = (
            f"{total} tasks, {done} completed "
            f"({round(done / total * 100)}% done), {overdue} overdue. Tasks:"
        )
        more = f"\n    · …and {total - max_tasks} more" if total > max_tasks else ""
        return header + "\n" + "\n".join(task_lines) + more
    except Exception:
        return f"Board '{board.name}' — no data yet"


# ---------------------------------------------------------------------------
# Level 1 — Board
# ---------------------------------------------------------------------------

@shared_task(
    bind=True,
    name='kanban.ai_summary.generate_board_summary',
    max_retries=2,
    default_retry_delay=30,
    queue='summaries',
    time_limit=90,
    soft_time_limit=75,
)
def generate_board_summary_task(self, board_id):
    """
    Async Celery task: generate and persist an AI summary for a single board.

    Uses intelligent data pruning:
    - Exception tasks (blocked / overdue / high-risk): send full detail to LLM.
    - All other tasks: contribute only to aggregate counts.
    This keeps the prompt lean regardless of board size (enterprise-safe).
    """
    try:
        from django.utils import timezone as tz
        from kanban.models import Board, Task
        from kanban.utils.ai_utils import generate_ai_content

        board = Board.objects.get(pk=board_id)
        today = date.today()

        tasks = (
            Task.objects
            .filter(column__board_id=board_id, item_type='task')
            .select_related('column', 'assigned_to')
            .prefetch_related('dependencies', 'labels')
        )

        # --- aggregate counters ---
        agg = {
            'total': 0, 'completed': 0, 'in_progress': 0, 'not_started': 0,
            'overdue': 0, 'high_risk': 0,
            'lss_value_added': 0, 'lss_necessary_nva': 0, 'lss_waste': 0,
            'estimated_cost': 0.0, 'actual_cost': 0.0, 'cost_variance': 0.0,
        }

        exception_lines = []

        for task in tasks:
            agg['total'] += 1

            # progress buckets
            if task.progress is not None and task.progress >= 100:
                agg['completed'] += 1
            elif task.progress and task.progress > 0:
                agg['in_progress'] += 1
            else:
                agg['not_started'] += 1

            # overdue flag
            is_overdue = (
                task.due_date is not None
                and task.due_date.date() < today
                and (task.progress or 0) < 100
            )
            if is_overdue:
                agg['overdue'] += 1

            # risk flag
            is_high_risk = task.risk_level in ('high', 'critical')
            if is_high_risk:
                agg['high_risk'] += 1

            # blocked-column flag (structural column_type marker, else name heuristic)
            is_blocked = task.column.is_blocked() if task.column else False

            # LSS counts
            lss = task.lss_classification or ''
            if lss == 'value_added':
                agg['lss_value_added'] += 1
            elif lss == 'necessary_nva':
                agg['lss_necessary_nva'] += 1
            elif lss == 'waste':
                agg['lss_waste'] += 1

            # budget via TaskCost (OneToOne, may not exist)
            try:
                cost = task.cost
                est = float(cost.estimated_cost or 0)
                act = float(cost.actual_cost or 0)
                agg['estimated_cost'] += est
                agg['actual_cost'] += act
            except Exception:
                pass

            # build exception row (full detail)
            if is_overdue or is_high_risk or is_blocked:
                deps = ', '.join(
                    d.title for d in task.dependencies.all()[:3]
                ) or 'none'
                mitigation = ''
                if task.mitigation_suggestions:
                    suggestions = task.mitigation_suggestions
                    if isinstance(suggestions, list):
                        mitigation = '; '.join(str(s) for s in suggestions[:2])
                    else:
                        mitigation = str(suggestions)[:120]
                flags = []
                if is_overdue:
                    flags.append('OVERDUE')
                if is_high_risk:
                    flags.append(f'RISK:{task.risk_level}')
                if is_blocked:
                    flags.append('BLOCKED')
                due_str = (
                    task.due_date.strftime('%b %d') if task.due_date else 'no due date'
                )
                cost_str = ''
                try:
                    c = task.cost
                    var = float(c.actual_cost or 0) - float(c.estimated_cost or 0)
                    cost_str = f' | budget variance: ${var:+.2f}'
                except Exception:
                    pass
                exception_lines.append(
                    f"  [{', '.join(flags)}] {task.title} "
                    f"| priority:{task.priority} | due:{due_str} | progress:{task.progress or 0}% "
                    f"| LSS:{lss or 'unset'} | deps:[{deps}] "
                    f"| mitigation: {mitigation or 'none'}{cost_str}"
                )

        agg['cost_variance'] = agg['actual_cost'] - agg['estimated_cost']
        agg['done_pct'] = round(agg['completed'] / agg['total'] * 100) if agg['total'] else 0

        if agg['total'] == 0:
            summary_text = f"No tasks on board '{board.name}' yet."
        else:
            prompt = _build_board_prompt(board.name, exception_lines, agg)
            summary_text = generate_ai_content(
                prompt, task_type='board_analytics_summary', use_cache=False
            )

        if not summary_text:
            logger.warning(f"generate_board_summary_task: empty result for board {board_id}")
            return None

        board.ai_summary = summary_text
        board.ai_summary_generated_at = tz.now()
        board.save(update_fields=['ai_summary', 'ai_summary_generated_at'])
        logger.info(f"Board {board_id} AI summary saved ({len(summary_text)} chars)")
        return summary_text

    except Exception as exc:
        logger.error(f"generate_board_summary_task error (board {board_id}): {exc}")
        try:
            raise self.retry(exc=exc)
        except self.MaxRetriesExceededError:
            return None
    finally:
        # Always release the debounce lock so the board can be re-queued after
        # this task finishes (even on failure / retry exhaustion).
        _release_board_lock(board_id)


# ---------------------------------------------------------------------------
# Level 2 — Strategy
# ---------------------------------------------------------------------------

@shared_task(
    bind=True,
    name='kanban.ai_summary.generate_strategy_summary',
    max_retries=2,
    default_retry_delay=30,
    queue='summaries',
    time_limit=90,
    soft_time_limit=75,
)
def generate_strategy_summary_task(self, strategy_id):
    """
    Aggregate board summaries into a strategy-level summary.
    Falls back to task-count stats for boards without a saved summary
    (no LLM cascade, just DB queries).
    """
    try:
        from django.utils import timezone as tz
        from kanban.models import Strategy, Task
        from kanban.utils.ai_utils import generate_ai_content

        strategy = Strategy.objects.select_related('mission').get(pk=strategy_id)
        boards = strategy.boards.all()

        board_lines = []
        for board in boards:
            snippet = board.ai_summary
            if not snippet:
                # Fallback for boards with no saved summary yet. Ground it in real
                # task content (titles/columns/progress), not bare counts, so the
                # model describes what's actually on the board instead of riffing
                # on the strategy's name.
                snippet = _board_task_fallback(board)
            board_lines.append(f"- [{board.name}] {snippet}")

        if not board_lines:
            summary_text = f"No boards linked to strategy '{strategy.name}' yet."
        else:
            snippets_block = "\n".join(board_lines)
            prompt = (
                f"You are a senior strategy analyst.\n"
                f'The strategy is named "{strategy.name}" (mission: "{strategy.mission.name}").\n'
                f"IMPORTANT: that name is the team's ASPIRATION, not evidence of what has been done. "
                f"Base every statement ONLY on the board/task data below. Do NOT infer domain "
                f"specifics (e.g. compliance, architecture, testing phases) from the strategy name "
                f"if the tasks don't mention them. If the tasks are unrelated to the strategy's stated "
                f"intent, say so plainly.\n\n"
                f"Board / task data:\n{snippets_block}\n\n"
                f"Write 3\u20135 concise bullet points that ADD NEW INSIGHT beyond simply restating the "
                f"task list. Do NOT repeat raw task counts or budget figures already shown above.\n"
                f"Focus on:\n"
                f"\u2022 What the actual tasks reveal about progress and the nearest risks (name real tasks)\n"
                f"\u2022 Whether the current work plausibly advances the strategy's stated intent \u2014 or diverges from it\n"
                f"\u2022 Cross-board dependencies or sequencing risks, if any are visible in the data\n"
                f"\u2022 The single highest-leverage next action, grounded in a task shown above\n\n"
                f"Be strictly factual \u2014 do NOT invent tasks, phases, or domain details not present above. "
                f"Refer to tasks by their real titles.\n"
                f"Each bullet MUST start with the \u2022 character. "
                f"Output ONLY the bullet list \u2014 no headings, no paragraphs, no JSON."
            )
            summary_text = generate_ai_content(
                prompt, task_type='board_analytics_summary', use_cache=False
            )

        if not summary_text:
            logger.warning(f"generate_strategy_summary_task: empty for strategy {strategy_id}")
            return None

        strategy.ai_summary = summary_text
        strategy.ai_summary_generated_at = tz.now()
        strategy.save(update_fields=['ai_summary', 'ai_summary_generated_at'])
        logger.info(f"Strategy {strategy_id} AI summary saved")
        return summary_text

    except Exception as exc:
        logger.error(f"generate_strategy_summary_task error (strategy {strategy_id}): {exc}")
        try:
            raise self.retry(exc=exc)
        except self.MaxRetriesExceededError:
            return None
    finally:
        # Always release the debounce lock so the strategy can be re-queued after
        # this task finishes (even on failure / retry exhaustion).
        _release_strategy_lock(strategy_id)


# ---------------------------------------------------------------------------
# Level 3 — Mission
# ---------------------------------------------------------------------------

@shared_task(
    bind=True,
    name='kanban.ai_summary.generate_mission_summary',
    max_retries=2,
    default_retry_delay=30,
    queue='summaries',
    time_limit=90,
    soft_time_limit=75,
)
def generate_mission_summary_task(self, mission_id):
    """
    Aggregate strategy summaries into a mission-level executive summary.
    Falls back to strategy description/status for strategies without a saved summary.
    """
    try:
        from django.utils import timezone as tz
        from kanban.models import Mission
        from kanban.utils.ai_utils import generate_ai_content

        mission = Mission.objects.select_related('organization_goal').get(pk=mission_id)
        strategies = mission.strategies.all()
        org_goal = mission.organization_goal

        strategy_lines = []
        for s in strategies:
            snippet = s.ai_summary
            if not snippet:
                snippet = (
                    (s.description or '').strip()[:200]
                    or f"Strategy '{s.name}' — status: {s.status}"
                )
            strategy_lines.append(f"- [{s.name}] {snippet}")

        if not strategy_lines:
            summary_text = f"No strategies defined for mission '{mission.name}' yet."
        else:
            snippets_block = "\n".join(strategy_lines)

            # Build Organization Goal context block (injected when a goal is linked)
            if org_goal:
                goal_block = (
                    f"ORGANIZATION GOAL (the North Star this mission must move):\n"
                    f"  Name: {org_goal.name}\n"
                )
                if org_goal.target_metric:
                    goal_block += f"  Target Metric: {org_goal.target_metric}\n"
                if org_goal.description:
                    goal_block += f"  Context: {org_goal.description[:300]}\n"
                goal_instruction = (
                    "CRITICAL EVALUATION REQUIREMENT: Beyond reporting strategy progress, "
                    "explicitly assess whether this mission's current trajectory is genuinely "
                    "advancing the Organization Goal above. Answer the question: "
                    f"\"Are the strategies under this mission actually moving the needle on "
                    f"'{org_goal.name}'?\" "
                    "If there is a disconnect between task activity and the stated goal, flag it clearly."
                )
            else:
                goal_block = ""
                goal_instruction = ""

            prompt = (
                f"You are a C-level executive advisor.\n"
                f"{goal_block}\n"
                f"MISSION: \"{mission.name}\"\n"
                f"Mission description: {(mission.description or 'Not provided.')[:300]}\n\n"
                f"IMPORTANT: the mission name and description are the team's INTENT, not evidence of "
                f"what has been delivered. Base every statement ONLY on the strategy summaries below. Do "
                f"NOT infer domain specifics from the mission's name if the underlying work doesn't show "
                f"them. If the strategies' actual work diverges from the mission's stated intent, flag it.\n\n"
                f"Strategy summaries (what the teams are actually doing):\n{snippets_block}\n\n"
                f"{goal_instruction}\n\n"
                f"Write 4\u20136 concise bullet points at the EXECUTIVE level. "
                f"Do NOT repeat task counts, blocker names, budget figures, or completion percentages that are "
                f"already visible in the strategy summaries above. Those details belong at the strategy level.\n"
                f"Instead focus exclusively on:\n"
                f"\u2022 Overall mission trajectory \u2014 is it fundamentally on track or off track, and why\n"
                f"\u2022 Whether the collective strategies add up to achieving the mission goal within the timeline\n"
                f"\u2022 Strategic-level risks the organisation needs to decide on (not operational task blockers)\n"
                f"\u2022 The single most important decision or action for senior leadership to take\n"
                f"\u2022 Whether this mission is advancing the Organization Goal (if one is set) \u2014 be direct\n\n"
                f"Be factual and actionable \u2014 do NOT invent data not listed above.\n"
                f"Each bullet MUST start with the \u2022 character. "
                f"Output ONLY the bullet list \u2014 no headings, no paragraphs, no JSON."
            )
            summary_text = generate_ai_content(
                prompt, task_type='board_analytics_summary', use_cache=False
            )

        if not summary_text:
            logger.warning(f"generate_mission_summary_task: empty for mission {mission_id}")
            return None

        mission.ai_summary = summary_text
        mission.ai_summary_generated_at = tz.now()
        mission.save(update_fields=['ai_summary', 'ai_summary_generated_at'])
        logger.info(f"Mission {mission_id} AI summary saved")
        return summary_text

    except Exception as exc:
        logger.error(f"generate_mission_summary_task error (mission {mission_id}): {exc}")
        try:
            raise self.retry(exc=exc)
        except self.MaxRetriesExceededError:
            return None
    finally:
        # Always release the debounce lock so the mission can be re-queued after
        # this task finishes (even on failure / retry exhaustion).
        _release_mission_lock(mission_id)


# ---------------------------------------------------------------------------
# Level 4 — Organization Goal
# ---------------------------------------------------------------------------

def _goal_lock_key(goal_id):
    return f'goal_ai_lock_{goal_id}'


def _release_goal_lock(goal_id):
    try:
        _ai_cache().delete(_goal_lock_key(goal_id))
    except Exception as exc:
        logger.warning(f"Could not release goal AI lock for goal {goal_id}: {exc}")


@shared_task(
    bind=True,
    name='kanban.ai_summary.generate_goal_summary',
    max_retries=2,
    default_retry_delay=30,
    queue='summaries',
    time_limit=90,
    soft_time_limit=75,
)
def generate_goal_summary_task(self, goal_id):
    """
    Aggregate mission summaries into an organization-goal-level executive summary.
    """
    try:
        from django.utils import timezone as tz
        from kanban.models import OrganizationGoal
        from kanban.utils.ai_utils import generate_ai_content

        goal = OrganizationGoal.objects.get(pk=goal_id)
        missions = goal.missions.all()

        mission_lines = []
        for m in missions:
            snippet = m.ai_summary
            if not snippet:
                snippet = (
                    (m.description or '').strip()[:200]
                    or f"Mission '{m.name}' — status: {m.status}"
                )
            mission_lines.append(f"- [{m.name}] {snippet}")

        if not mission_lines:
            summary_text = f"No missions defined for goal '{goal.name}' yet."
        else:
            snippets_block = "\n".join(mission_lines)
            target_line = f"  Target Metric: {goal.target_metric}\n" if goal.target_metric else ""
            desc_line = f"  Context: {(goal.description or '')[:300]}\n" if goal.description else ""
            prompt = (
                f"You are a C-level executive advisor.\n"
                f"ORGANIZATION GOAL: \"{goal.name}\"\n"
                f"{target_line}{desc_line}\n"
                f"IMPORTANT: the goal's name, target metric, and context are the organisation's AMBITION, "
                f"not evidence of what has been achieved. Base every statement ONLY on the mission summaries "
                f"below. Do NOT infer progress or domain specifics from the goal's name if the missions don't "
                f"show them. If the missions' actual work diverges from the goal's stated ambition, say so directly.\n\n"
                f"Mission summaries (each mission addresses one facet of the goal):\n{snippets_block}\n\n"
                f"Write 4–6 concise bullet points at the EXECUTIVE level.\n"
                f"Focus on:\n"
                f"• Whether the collective missions are on track to achieve the goal within the timeline\n"
                f"• Cross-mission dependencies or gaps\n"
                f"• Strategic-level risks that leadership should act on\n"
                f"• The single most important decision for senior leadership\n\n"
                f"Be factual — do NOT invent data not listed above.\n"
                f"Each bullet MUST start with the • character. "
                f"Output ONLY the bullet list — no headings, no paragraphs, no JSON."
            )
            summary_text = generate_ai_content(
                prompt, task_type='board_analytics_summary', use_cache=False
            )

        if not summary_text:
            logger.warning(f"generate_goal_summary_task: empty for goal {goal_id}")
            return None

        goal.ai_summary = summary_text
        goal.ai_summary_generated_at = tz.now()
        goal.save(update_fields=['ai_summary', 'ai_summary_generated_at'])
        logger.info(f"Goal {goal_id} AI summary saved")
        return summary_text

    except Exception as exc:
        logger.error(f"generate_goal_summary_task error (goal {goal_id}): {exc}")
        try:
            raise self.retry(exc=exc)
        except self.MaxRetriesExceededError:
            return None
    finally:
        _release_goal_lock(goal_id)


# ---------------------------------------------------------------------------
# Daily executive briefing (beat-triggered)
# ---------------------------------------------------------------------------

@shared_task(
    bind=True,
    name='kanban.ai_summary.generate_daily_executive_briefing',
    max_retries=1,
    queue='summaries',
    time_limit=600,   # up to 10 min for all active missions
    soft_time_limit=540,
)
def generate_daily_executive_briefing(self):
    """
    Beat task: regenerate every active mission summary once a day (08:00 IST).

    Order: boards → strategies → missions  (each layer reads the layer below).
    Boards get a fresh task-pruned summary first; strategies and missions then
    aggregate bottom-up. Uses the same intelligent-pruning logic as the
    signal-triggered tasks so API cost stays flat regardless of board count.
    """
    try:
        from kanban.models import Mission, Board

        active_missions = Mission.objects.filter(status='active').prefetch_related(
            'strategies__boards'
        )

        board_ids_done = set()
        strategy_ids_done = set()
        results = {'missions': 0, 'strategies': 0, 'boards': 0, 'errors': []}

        for mission in active_missions:
            try:
                for strategy in mission.strategies.all():
                    for board in strategy.boards.all():
                        if board.pk not in board_ids_done:
                            try:
                                # Run synchronously within this task to preserve order
                                generate_board_summary_task.apply(args=[board.pk])
                                board_ids_done.add(board.pk)
                                results['boards'] += 1
                            except Exception as be:
                                results['errors'].append(f"board {board.pk}: {be}")

                    if strategy.pk not in strategy_ids_done:
                        try:
                            generate_strategy_summary_task.apply(args=[strategy.pk])
                            strategy_ids_done.add(strategy.pk)
                            results['strategies'] += 1
                        except Exception as se:
                            results['errors'].append(f"strategy {strategy.pk}: {se}")

                generate_mission_summary_task.apply(args=[mission.pk])
                results['missions'] += 1

            except Exception as me:
                results['errors'].append(f"mission {mission.pk}: {me}")

        logger.info(
            f"Daily executive briefing complete: "
            f"{results['boards']} boards, {results['strategies']} strategies, "
            f"{results['missions']} missions refreshed. "
            f"Errors: {results['errors'] or 'none'}"
        )
        return results

    except Exception as exc:
        logger.error(f"generate_daily_executive_briefing error: {exc}")
        raise
