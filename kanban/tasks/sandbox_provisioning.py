"""
Celery task for asynchronous sandbox provisioning.

Uses the same WebSocket progressive-disclosure pattern as AI streaming tasks:
Celery worker deep-copies demo template boards → streams progress updates
via Django Channels → frontend redirects on completion.
"""
import logging
import threading

from celery import shared_task
from channels.layers import get_channel_layer
from asgiref.sync import async_to_sync
from django.utils import timezone

logger = logging.getLogger(__name__)


def touch_sandbox_access(user):
    """Stamp DemoSandbox.last_accessed_at = now for this user, if a sandbox exists.

    Called whenever the user actively enters demo mode so the stale-sandbox
    garbage collector (cleanup_stale_sandboxes) only reclaims genuinely
    abandoned demos. Best-effort: never raises into the request path.
    """
    try:
        from kanban.models import DemoSandbox
        DemoSandbox.objects.filter(user=user).update(last_accessed_at=timezone.now())
    except Exception:
        logger.warning("touch_sandbox_access failed for user %s", getattr(user, 'id', None), exc_info=True)


# When the reset runs SYNCHRONOUSLY inside an HTTP request (see
# kanban.sandbox_views.reset_my_demo) there is no WebSocket to push progress to,
# and calling async_to_sync(channel_layer.group_send) from that request thread —
# which is itself driven by the ASGI event loop — can DEADLOCK (the hang behind
# the "Reset is taking longer than usual" reports). The request path sets
# `_ws_suppress.on = True` so these helpers become no-ops; the Celery path leaves
# it False and streams progress as before.
_ws_suppress = threading.local()


def _send_provision_status(user_id, message, progress=0):
    """Send a provisioning progress update to the user's WebSocket group."""
    if getattr(_ws_suppress, 'on', False):
        return
    try:
        channel_layer = get_channel_layer()
        async_to_sync(channel_layer.group_send)(
            f'sandbox_provision_{user_id}',
            {
                'type': 'provision_status',
                'message': message,
                'progress': progress,
            },
        )
    except Exception as exc:
        logger.warning('Failed to send provision status for user %s: %s', user_id, exc)


def _send_provision_result(user_id, data):
    """Send the provisioning completion result."""
    if getattr(_ws_suppress, 'on', False):
        return
    try:
        channel_layer = get_channel_layer()
        async_to_sync(channel_layer.group_send)(
            f'sandbox_provision_{user_id}',
            {
                'type': 'provision_result',
                'data': data,
            },
        )
    except Exception as exc:
        logger.warning('Failed to send provision result for user %s: %s', user_id, exc)


def _send_provision_error(user_id, message):
    """Send a provisioning error."""
    if getattr(_ws_suppress, 'on', False):
        return
    try:
        channel_layer = get_channel_layer()
        async_to_sync(channel_layer.group_send)(
            f'sandbox_provision_{user_id}',
            {
                'type': 'provision_error',
                'message': message,
            },
        )
    except Exception as exc:
        logger.warning('Failed to send provision error for user %s: %s', user_id, exc)


def _duplicate_board_with_retry(template, user, attempts=4, base_delay=0.4):
    """
    Duplicate a demo board, retrying on transient SQLite "database is locked"
    errors with exponential backoff.

    Even with purge + provision now serialized in one worker, Celery Beat's
    DatabaseScheduler or another request can still briefly hold the single
    SQLite writer. A short bounded retry turns those transient locks into a
    successful copy instead of a half-provisioned sandbox.
    """
    import time
    from django.db import OperationalError
    from kanban.sandbox_views import _duplicate_board

    last_exc = None
    for attempt in range(attempts):
        try:
            return _duplicate_board(template, user)
        except OperationalError as exc:
            if 'locked' not in str(exc).lower():
                raise
            last_exc = exc
            if attempt < attempts - 1:
                time.sleep(base_delay * (2 ** attempt))  # 0.4s, 0.8s, 1.6s
                logger.warning(
                    "Retrying board '%s' after DB lock (attempt %d/%d)",
                    template.name, attempt + 2, attempts,
                )
    raise last_exc


@shared_task(
    bind=True,
    name='kanban.sandbox_provisioning.provision_sandbox',
    time_limit=120,
    soft_time_limit=90,
)
def provision_sandbox_task(self, user_id, is_reset=False):
    """
    Deep-copy all demo template boards into a private sandbox for *user_id*.

    Streams progress via WebSocket so the frontend can show a loading state.
    On completion, sends the redirect URL.

    Args:
        is_reset: If True, this is a reset operation and last_reset_at will be set.
    """
    # Guard the whole run. If the task blows past soft_time_limit (90s), Celery
    # raises SoftTimeLimitExceeded; uncaught, the task dies WITHOUT sending a
    # WebSocket result, leaving the frontend "Resetting…" banner spinning
    # forever (the exact symptom we hit). Surface it as a provision_error so the
    # UI can recover and tell the user to retry.
    from celery.exceptions import SoftTimeLimitExceeded
    from django.core.cache import caches

    # ── Cross-process single-flight lock ──────────────────────────────────────
    # Provisioning deep-copies ~30 demo tasks per board and only writes its
    # DemoSandbox marker row at the very END (see _provision_sandbox). So the
    # `user.demo_sandbox` existence check inside cannot stop a SECOND trigger
    # that arrives mid-copy. Without this lock a Reset Demo (async via
    # /demo/reset-mine/) racing the dashboard's synchronous auto-provision
    # (kanban/views.py, which fires when it sees no sandbox boards yet) — or a
    # simple double-click — runs the copy twice and leaves 2–4 duplicate
    # "Software Development" boards, some half-populated. The lock lives in
    # 'ai_cache', the only alias guaranteed to be Redis (cross-process) even in
    # local DEBUG runs; 'default' is per-process LocMemCache there and would not
    # span the Daphne request thread and the Celery worker.
    lock_cache = caches['ai_cache']
    lock_key = f'sandbox_provision_lock_{user_id}'
    try:
        # TTL outlives the 120s hard time_limit so a crashed worker can't
        # deadlock future resets; released in finally on normal completion.
        got_lock = lock_cache.add(lock_key, '1', timeout=150)
    except Exception:
        got_lock = True  # cache unavailable — fail open, never block a reset
    if not got_lock:
        logger.info(
            "Sandbox provisioning already in progress for user %s — skipping "
            "duplicate trigger to avoid creating duplicate boards.", user_id,
        )
        return {'status': 'in_progress', 'message': 'Provisioning already running.'}

    try:
        return _provision_sandbox(self, user_id, is_reset=is_reset)
    except SoftTimeLimitExceeded:
        logger.error(
            "provision_sandbox exceeded soft_time_limit (90s) for user %s — "
            "sending error so the UI stops waiting.", user_id,
        )
        _send_provision_error(
            user_id,
            'Reset took longer than expected and was stopped. Please click '
            'Reset Demo again.',
        )
        return {'status': 'error', 'message': 'soft time limit exceeded'}
    finally:
        try:
            lock_cache.delete(lock_key)
        except Exception:
            pass


def provision_sandbox_sync(user_id, is_reset=False):
    """Run provisioning SYNCHRONOUSLY in the caller's thread (no Celery, no
    WebSocket) and return the result dict.

    Used by the Reset Demo HTTP view so the reset never depends on a Celery
    worker consuming the task or on a WebSocket round-trip — both proved
    unreliable on the local solo-worker/Windows setup and left resets hung with
    the DB untouched. The deep-copy is only ~10s, well within an HTTP request.

    Reuses the same single-flight lock as the Celery task (so a double-click or a
    racing auto-provision can't create duplicate boards) and suppresses the
    progress WebSocket sends (which would otherwise deadlock when async_to_sync
    is called from the request thread).
    """
    from django.core.cache import caches
    lock_cache = caches['ai_cache']
    lock_key = f'sandbox_provision_lock_{user_id}'
    try:
        got_lock = lock_cache.add(lock_key, '1', timeout=150)
    except Exception:
        got_lock = True  # cache unavailable — fail open, never block a reset
    if not got_lock:
        return {'status': 'in_progress', 'redirect_url': '/dashboard/'}

    _ws_suppress.on = True
    try:
        return _provision_sandbox(None, user_id, is_reset=is_reset)
    finally:
        _ws_suppress.on = False
        try:
            lock_cache.delete(lock_key)
        except Exception:
            pass


def _provision_sandbox(self, user_id, is_reset=False):
    """Actual provisioning logic; wrapped by ``provision_sandbox_task`` so a
    soft-timeout is reported to the frontend instead of dying silently."""
    from django.contrib.auth import get_user_model
    from kanban.models import Board, DemoSandbox
    from kanban.sandbox_views import (
        _duplicate_board, _purge_existing_sandbox,
        _join_demo_org, _reassign_demo_tasks_to_user,
    )
    from kanban.utils.demo_protection import allow_demo_writes, suppress_calendar_sync

    User = get_user_model()
    try:
        user = User.objects.get(pk=user_id)
    except User.DoesNotExist:
        _send_provision_error(user_id, 'User not found.')
        return {'status': 'error', 'message': 'User not found.'}

    _send_provision_status(user_id, 'Preparing your private workspace…', 5)

    # On reset, purge the existing sandbox HERE (inside the worker) rather than
    # in the request thread. Running the purge and the re-provision in the same
    # worker serializes them against SQLite's single writer; doing the purge in
    # the request thread while this task duplicates boards produces two
    # concurrent writers → an immediate "database is locked" error that left a
    # half-provisioned sandbox (fewer tasks, missing notifications). See the
    # _duplicate_board failure path below.
    if is_reset:
        _send_provision_status(user_id, 'Clearing your previous demo data…', 8)
        with allow_demo_writes():
            _purge_existing_sandbox(user)
        # Re-fetch the user so its cached reverse relations are dropped. The
        # purge reads `user.demo_sandbox` (caching it on this instance) and then
        # deletes the row — but Django keeps the stale object in the instance
        # cache. Without this refresh, the existence check below would read the
        # cached DemoSandbox, wrongly return 'exists', and skip re-provisioning
        # (the "Reset Demo does nothing" bug).
        user = User.objects.get(pk=user_id)

    # Check for existing sandbox. On reset we've just purged it, so this only
    # short-circuits for a non-reset call where a sandbox already exists.
    try:
        existing = user.demo_sandbox
        # Active sandbox already exists — just return it
        first_board = Board.objects.filter(
            owner=user,
            is_sandbox_copy=True,
        ).first()
        redirect_url = f'/boards/{first_board.id}/' if first_board else '/dashboard/'
        _send_provision_result(user_id, {
            'status': 'exists',
            'redirect_url': redirect_url,
        })
        return {'status': 'exists', 'redirect_url': redirect_url}
    except DemoSandbox.DoesNotExist:
        pass

    template_boards = list(Board.objects.filter(is_official_demo_board=True).order_by('name'))
    if not template_boards:
        _send_provision_error(user_id, 'No demo template boards found.')
        return {'status': 'error', 'message': 'No demo template boards found.'}

    # Re-seed the canonical PrizmDiscovery template ideas on the shared template
    # board BEFORE duplicating it. The promoted "Regional Pricing" ticket is
    # (re)created here with its phase, Phase 3 dates and Gantt dependency, so
    # duplicating the board AFTER this makes the user's copy carry all of it
    # (_duplicate_board copies phase, dates and dependencies). The per-user idea
    # clone itself runs further down, once the user's board copy exists.
    try:
        from django.core.management import call_command
        with allow_demo_writes():
            call_command('populate_discovery_demo_data')
    except Exception as e:
        logger.warning("Could not seed Discovery template ideas before board copy: %s", e)

    _send_provision_status(user_id, 'Copying demo boards…', 15)

    new_boards = []
    total = len(template_boards)
    # Suppress Google Calendar sync for the ENTIRE provisioning block. Both
    # _duplicate_board (copies demo tasks — some assigned to the real user with
    # due dates) and _reassign_demo_tasks_to_user create/modify tasks owned by
    # the user, so without this every sandbox (re-)provision pushes demo events
    # onto the user's Google Calendar — the "notifications come back after Reset
    # Demo" bug. NB: allow_demo_writes() sets a *different* thread-local and does
    # NOT gate calendar sync.
    with allow_demo_writes(), suppress_calendar_sync():
        for idx, template in enumerate(template_boards):
            pct = 15 + int((idx / total) * 70)  # 15% → 85%
            _send_provision_status(
                user_id,
                f'Creating board {idx + 1} of {total}: {template.name}…',
                pct,
            )
            try:
                new_board = _duplicate_board_with_retry(template, user)
                new_boards.append(new_board)
            except Exception as e:
                # A board failed to duplicate even after retries. Do NOT commit a
                # partial sandbox — that is exactly the "fewer tasks / missing
                # notifications" bug. Roll back what we copied and report failure
                # so the user can retry on a clean slate.
                logger.error(
                    "Error duplicating board '%s' for %s: %s — aborting reset to "
                    "avoid a half-provisioned sandbox.",
                    template.name, user.username, e,
                )
                for partial in new_boards:
                    try:
                        partial.delete()
                    except Exception:
                        logger.warning(
                            "Failed to roll back partial sandbox board %s", partial.id,
                        )
                _send_provision_error(
                    user_id,
                    'Reset hit a temporary database lock. Please click Reset Demo '
                    'again.',
                )
                return {'status': 'error', 'message': 'Sandbox creation failed.'}

        if not new_boards:
            _send_provision_error(user_id, 'Sandbox creation failed — no boards duplicated.')
            return {'status': 'error', 'message': 'Sandbox creation failed.'}

        _send_provision_status(user_id, 'Finalizing your workspace…', 90)

        sandbox = DemoSandbox.objects.create(
            user=user,
            last_reset_at=timezone.now() if is_reset else None,
            last_accessed_at=timezone.now(),
        )

        # Join demo org and reassign a few tasks to the real user
        _join_demo_org(user)
        # Suppress Google Calendar sync while reassigning demo tasks to the
        # real user. These are demo-content tasks and must not push events to
        # the user's personal Google Calendar — same rationale as the demo
        # reset / seed path, which also wraps task writes in
        # suppress_calendar_sync(). Without this, every demo task reassigned to
        # the user (with a due date) creates a calendar event on each sandbox
        # (re-)provision — the "notifications come back after Reset Demo" bug.
        # NB: allow_demo_writes() above sets a *different* thread-local flag and
        # does NOT suppress calendar sync.
        from kanban.utils.demo_protection import suppress_calendar_sync
        with suppress_calendar_sync():
            _reassign_demo_tasks_to_user(sandbox, user)

    # Set the profile flag
    try:
        profile = user.profile
        profile.is_viewing_demo = True
        profile.save(update_fields=['is_viewing_demo'])
    except Exception:
        pass

    # Refresh dates on the newly created sandbox boards so they are
    # relative to today (template dates may have been refreshed hours ago).
    try:
        from kanban.utils.demo_date_refresh import refresh_single_board_dates
        from kanban.utils.demo_protection import suppress_calendar_sync
        # Suppress calendar sync — these due-date changes are on demo tasks
        # (including those just reassigned to the user) and must not push
        # events to the user's Google Calendar.
        with suppress_calendar_sync():
            for board in new_boards:
                refresh_single_board_dates(board.id)
    except Exception as e:
        logger.warning("Error refreshing sandbox board dates: %s", e)

    # Clone the (already-seeded) PrizmDiscovery ideas into the user's private
    # per-user set SYNCHRONOUSLY, before the redirect. This used to be deferred to
    # _run_sandbox_extras on the default worker, which is starvation-prone right
    # after a reset — so the user landed on an EMPTY Discovery inbox (the recurring
    # "no ideas in the inbox" bug). It is small (~8 ideas) so it adds negligible
    # time to the reset. The templates were seeded before the board copy above; the
    # clone re-points each promotion to the user's own board copy + matching task.
    try:
        from kanban.sandbox_views import _clone_discovery_ideas_for_user
        with allow_demo_writes():
            _clone_discovery_ideas_for_user(user)
    except Exception as e:
        logger.warning("Could not clone Discovery demo ideas during provision: %s", e)

    # Clone the demo wiki (categories + pages) into the user's private per-user
    # copy so wiki content is isolated per demo user (it is workspace-scoped but
    # the demo workspace is shared). Templates were seeded before this; the clone
    # re-points pages at the user's own category copies. Idempotent.
    try:
        from kanban.sandbox_views import _clone_wiki_for_user
        with allow_demo_writes():
            _clone_wiki_for_user(user)
    except Exception as e:
        logger.warning("Could not clone demo wiki during provision: %s", e)

    # Clone the demo custom-field schema (+ seeded task values) into the user's
    # private per-user set. Definitions are workspace-scoped but the demo
    # workspace is shared, so without per-user clones every demo user would share
    # (and edit/delete) one set of fields. Idempotent.
    try:
        from kanban.sandbox_views import _clone_custom_fields_for_user
        with allow_demo_writes():
            _clone_custom_fields_for_user(user)
    except Exception as e:
        logger.warning("Could not clone demo custom fields during provision: %s", e)

    # Belt-and-suspenders: ensure the primary persona's cloned time entries are
    # owned by the sandbox owner so the time-tracking dashboard is per-user. The
    # board clone above already remaps them; this is idempotent and also self-heals
    # any sandbox that predates that fix.
    try:
        from kanban.sandbox_views import _remap_demo_time_entries_to_owner
        with allow_demo_writes():
            _remap_demo_time_entries_to_owner(user)
    except Exception as e:
        logger.warning("Could not remap demo time entries during provision: %s", e)

    # Clone the demo calendar events into the user's own sandbox boards so the
    # calendar is per-user (events are seeded only on the shared template board and
    # were never cloned). Clone-if-empty, so this is idempotent.
    try:
        from kanban.sandbox_views import _clone_calendar_events_for_user
        with allow_demo_writes():
            _clone_calendar_events_for_user(user)
    except Exception as e:
        logger.warning("Could not clone demo calendar events during provision: %s", e)

    # ── Essential work is done ────────────────────────────────────────────────
    # The sandbox boards now exist with the correct columns, tasks, assignments
    # and refreshed dates — everything the user actually looks at on the board
    # they land on. Send the redirect NOW so Reset Demo feels instant, then
    # finish the non-critical extras below while the user is already on their
    # fresh workspace.
    #
    # Why this is safe: the extras (conflict pre-population, Decision Center
    # counts, requirements/discovery/automation seeds, shadow-branch scores)
    # only populate *secondary* feature pages, each already guards its own
    # errors, and each self-heals on next visit. Running them after the redirect
    # cannot fail the reset or roll back the sandbox. We deliberately stay in the
    # SAME Celery task (rather than enqueueing a follow-up) so that on the single
    # solo worker the extras run immediately in this slot instead of waiting
    # behind other queued jobs.
    redirect_url = '/dashboard/'
    _send_provision_status(user_id, 'Your workspace is ready!', 100)
    _send_provision_result(user_id, {
        'status': 'created',
        'boards_created': len(new_boards),
        'redirect_url': redirect_url,
    })

    # ── Non-critical extras → DEFAULT worker ──────────────────────────────────
    # Conflict pre-population, Decision Center counts, requirements/discovery/
    # automation seeds and shadow-branch scores only populate *secondary* feature
    # pages and each self-heals on next visit. They take 30–90s, so running them
    # inline here would keep THIS dedicated 'interactive' worker busy and block a
    # rapid successive Reset Demo (the interactive worker is solo, one-at-a-time
    # — exactly what made reset #3 hang in testing). Hand them to the default
    # 'celery' worker via a follow-up task so the interactive worker frees the
    # instant the redirect is sent.
    board_ids = [b.id for b in new_boards]
    try:
        finalize_sandbox_extras.delay(user_id, board_ids)
    except Exception:
        # Broker unreachable — run inline as a fallback so features still
        # populate (slower, but correct).
        _run_sandbox_extras(user_id, board_ids)

    return {
        'status': 'created',
        'boards_created': len(new_boards),
        'redirect_url': redirect_url,
    }


# NB: name is OUTSIDE the 'kanban.sandbox_provisioning.*' wildcard on purpose so
# this routes to the DEFAULT 'celery' queue, NOT the 'interactive' queue — the
# whole point is to get this work off the interactive worker.
@shared_task(name='kanban.finalize_sandbox_extras')
def finalize_sandbox_extras(user_id, board_ids):
    """Follow-up task: populate secondary demo features for freshly-provisioned
    sandbox boards on the default worker, keeping the interactive worker free for
    the next Reset Demo."""
    _run_sandbox_extras(user_id, board_ids)


def _run_sandbox_extras(user_id, board_ids):
    """Best-effort population of secondary demo features (conflicts, Decision
    Center, requirements/discovery/automation seeds, shadow-branch scores) for
    the given sandbox boards. Everything self-heals on next visit, so individual
    failures are logged and swallowed."""
    from django.contrib.auth import get_user_model
    from kanban.models import Board
    from kanban.utils.demo_protection import allow_demo_writes

    User = get_user_model()
    try:
        user = User.objects.get(pk=user_id)
    except User.DoesNotExist:
        return
    new_boards = list(Board.objects.filter(id__in=board_ids))
    if not new_boards:
        return

    # Pre-populate conflicts so the Conflict Dashboard isn't empty on first
    # visit (matches every other pre-populated demo feature). Only run for
    # boards that don't already have conflicts copied from the template, and
    # only after dates are refreshed so overdue/overlap detection is accurate.
    try:
        from kanban.utils.conflict_detection import ConflictDetectionService
        from kanban.conflict_models import ConflictDetection
        with allow_demo_writes():
            for board in new_boards:
                try:
                    has_conflicts = ConflictDetection.objects.filter(
                        board=board, status='active'
                    ).exists()
                    if not has_conflicts:
                        ConflictDetectionService(board=board).detect_all_conflicts()
                except Exception as detect_err:
                    logger.warning(
                        "Error detecting conflicts for sandbox board %s: %s",
                        board.id, detect_err,
                    )
    except Exception as e:
        logger.warning("Error during sandbox conflict detection: %s", e)

    # Regenerate Decision Center items so the dashboard/DC page
    # show fresh, accurate counts immediately after provisioning.
    # collect_for_user is cheap (DB scans); the briefing makes a blocking Gemini
    # call (30–60s) so it is enqueued separately rather than run inline.
    try:
        from decision_center.tasks import collect_for_user
        from decision_center.tasks import generate_briefing_for_user_task
        collect_for_user(user)
        try:
            generate_briefing_for_user_task.delay(user.id)
        except Exception:
            # Broker unreachable — fall back to inline so the briefing still
            # generates (slower, but correct).
            from decision_center.tasks import generate_briefing_for_user
            generate_briefing_for_user(user)
    except Exception:
        pass

    # Seed Requirements demo data for the new sandbox boards (idempotent).
    try:
        from django.core.management import call_command
        call_command('populate_demo_requirements')
    except Exception as e:
        logger.warning("Could not seed requirements after sandbox provision: %s", e)

    # NB: PrizmDiscovery ideas are now seeded + cloned SYNCHRONOUSLY in
    # _provision_sandbox (before the redirect) so the inbox is never empty and the
    # promoted ticket's phase is mirrored onto the user's board copy. Do not
    # re-run it here — a second clear-and-clone on the default worker would just
    # re-delete and recreate the user's clones for no benefit.

    # Seed automation hierarchy demo data: checklist items, parent/subtask
    # groups, and blocking dependency pair needed for T-22–T-29 test scenarios.
    try:
        from django.core.management import call_command
        call_command('populate_automation_demo_data')
    except Exception as e:
        logger.warning("Could not seed automation hierarchy data after sandbox provision: %s", e)

    # Recalculate shadow branches against the freshly-provisioned board so
    # their feasibility scores reflect THIS sandbox's tasks/deadline/team right
    # away.  Branches are deep-copied from the template carrying the template's
    # last snapshot (often a stale score like 81%); without this the user sees
    # that stale value until they manually click "Refresh Scores", and the
    # first refresh then appears to "jump" the score by 40+ points.  Run
    # synchronously (we're already in a worker) with skip_ai so provisioning
    # isn't blocked on Gemini, then enqueue the AI backfill per new snapshot.
    # Trigger 'Sandbox provisioned' is treated as a baseline correction, so it
    # writes no divergence log and doesn't appear in the Quantum Standup.
    try:
        from django.core.cache import cache as _shadow_cache
        from kanban.tasks.shadow_branch_tasks import (
            run_branch_recalc_sync, generate_ai_for_branch_snapshot,
        )
        from kanban.shadow_models import ShadowBranch
        for board in new_boards:
            if not ShadowBranch.objects.filter(board=board, status='active').exists():
                continue
            # _duplicate_board sets a 120s demo_shadow_lock to suppress recalcs
            # *during* the clone.  Cloning is finished now, so clear the lock for
            # this board before recalculating — otherwise run_branch_recalc_sync
            # early-returns ("demo data populate in progress") and the branches
            # keep their stale cloned scores until a later signal recalc.
            try:
                _shadow_cache.delete(f'demo_shadow_lock_{board.id}')
            except Exception:
                pass
            recalc = run_branch_recalc_sync(
                board.id,
                trigger_event='Sandbox provisioned',
                skip_ai=True,
            )
            for snapshot_id in recalc.get('snapshot_ids', []):
                try:
                    generate_ai_for_branch_snapshot.delay(snapshot_id)
                except Exception:
                    pass
    except Exception as e:
        logger.warning("Could not recalc shadow branches after sandbox provision: %s", e)
