"""
Celery configuration for the kanban_board project.
"""
import os
from celery import Celery
from celery.schedules import crontab

# Set the default Django settings module for the 'celery' program.
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'kanban_board.settings')

app = Celery('kanban_board')

# Load configuration from Django settings, all celery configuration should have a `CELERY_` prefix.
app.config_from_object('django.conf:settings', namespace='CELERY')

# Auto-discover tasks from all registered Django apps
app.autodiscover_tasks()

# Celery Beat Schedule for Periodic Tasks
app.conf.beat_schedule = {
    # Conflict detection - runs every hour
    'detect-conflicts-hourly': {
        'task': 'kanban.detect_conflicts',
        'schedule': crontab(minute=0),  # Every hour at minute 0
    },
    # Cleanup old resolved conflicts - runs daily at 2 AM
    'cleanup-resolved-conflicts': {
        'task': 'kanban.cleanup_resolved_conflicts',
        'schedule': crontab(hour=2, minute=0),  # Daily at 2:00 AM
    },
    # Refresh demo dates - runs daily at 3 AM to keep demo data current
    'refresh-demo-dates-daily': {
        'task': 'kanban.refresh_demo_dates',
        'schedule': crontab(hour=3, minute=0),  # Daily at 3:00 AM
    },
    # Time tracking reminder - runs at 5 PM on weekdays
    'time-tracking-reminder': {
        'task': 'kanban.send_time_tracking_reminders',
        'schedule': crontab(hour=17, minute=0, day_of_week='1-5'),  # 5 PM Mon-Fri
    },
    # Time anomaly detection - runs daily at 9 AM
    'time-anomaly-detection': {
        'task': 'kanban.detect_time_anomalies',
        'schedule': crontab(hour=9, minute=0),  # Daily at 9:00 AM
    },
    # Weekly time summary - runs Monday at 8 AM
    'weekly-time-summary': {
        'task': 'kanban.weekly_time_summary',
        'schedule': crontab(hour=8, minute=0, day_of_week='1'),  # Monday at 8 AM
    },
    # Due-date approaching automations - runs every hour
    'due-date-approaching-automations': {
        'task': 'kanban.run_due_date_approaching_automations',
        'schedule': crontab(minute=30),  # Every hour at :30 (offset from conflict detection)
    },
    # Overdue task automations - runs every hour to catch tasks whose due date just passed
    'overdue-task-automations': {
        'task': 'kanban.run_overdue_task_automations',
        'schedule': crontab(minute=45),  # Every hour at :45 (offset from other automation tasks)
    },
    # Idle-task automations - hourly sweep, offset from other automation tasks
    'idle-task-automations': {
        'task': 'kanban.run_idle_task_automations',
        'schedule': crontab(minute=15),  # Every hour at :15
    },
    # Start-date-reached automations - daily check shortly after midnight local time
    'start-date-reached-automations': {
        'task': 'kanban.run_start_date_reached_automations',
        'schedule': crontab(hour=0, minute=5),  # Daily at 00:05
    },
    # Predicted-late automations - daily check (heavier query, runs once/day)
    'predicted-late-automations': {
        'task': 'kanban.run_predicted_late_automations',
        'schedule': crontab(hour=1, minute=5),  # Daily at 01:05
    },
    # Dependency-overdue automations - hourly sweep, offset from other automations
    'dependency-overdue-automations': {
        'task': 'kanban.run_dependency_overdue_automations',
        'schedule': crontab(minute=50),  # Every hour at :50
    },
    # Daily executive briefing - 08:00 IST (CELERY_TIMEZONE = 'Asia/Kolkata')
    'daily-executive-briefing': {
        'task': 'kanban.ai_summary.generate_daily_executive_briefing',
        'schedule': crontab(hour=8, minute=0),
    },
    # --- AI Learning Loop Tasks ---
    # Refresh PM performance metrics daily at 6:30 AM (before coaching)
    'refresh-pm-metrics-daily': {
        'task': 'kanban.refresh_pm_metrics',
        'schedule': crontab(hour=6, minute=30),
    },
    # Generate coaching suggestions daily at 7:00 AM (before briefing)
    'generate-coaching-suggestions-daily': {
        'task': 'kanban.generate_coaching_suggestions',
        'schedule': crontab(hour=7, minute=0),
    },
    # Train priority models weekly on Sunday at 2:00 AM
    'train-priority-models-weekly': {
        'task': 'kanban.train_priority_models_periodic',
        'schedule': crontab(hour=2, minute=0, day_of_week='0'),  # Sunday 2 AM
    },
    # Analyze feedback text weekly on Wednesday at 3:00 AM
    'analyze-feedback-text-weekly': {
        'task': 'kanban.analyze_feedback_text',
        'schedule': crontab(hour=3, minute=0, day_of_week='3'),  # Wednesday 3 AM
    },
    # Aggregate org-level learning daily at 6:00 AM (before PM metrics)
    'aggregate-org-learning-daily': {
        'task': 'kanban.aggregate_org_learning',
        'schedule': crontab(hour=6, minute=0),  # Daily 6 AM
    },
    'run-ab-experiments-weekly': {
        'task': 'kanban.run_ab_experiments',
        'schedule': crontab(hour=4, minute=0, day_of_week=0),  # Sunday 4 AM
    },
    # --- Knowledge Graph Tasks ---
    # Generate memory connections weekly on Sunday at 5:00 AM
    'kg-generate-connections-weekly': {
        'task': 'knowledge_graph.generate_memory_connections',
        'schedule': crontab(hour=5, minute=0, day_of_week=0),  # Sunday 5 AM
    },
    # Check missed deadlines daily at 1:00 AM
    'kg-check-missed-deadlines-daily': {
        'task': 'knowledge_graph.check_missed_deadlines',
        'schedule': crontab(hour=1, minute=0),  # Daily 1 AM
    },
    # Check budget thresholds daily at 1:30 AM
    'kg-check-budget-thresholds-daily': {
        'task': 'knowledge_graph.check_budget_thresholds',
        'schedule': crontab(hour=1, minute=30),  # Daily 1:30 AM
    },
    # --- Decision Center Tasks ---
    # Collect decision items daily at 7:00 AM (after coaching suggestions)
    'dc-collect-decision-items-daily': {
        'task': 'decision_center.collect_decision_items',
        'schedule': crontab(hour=7, minute=15),  # Daily 7:15 AM
    },
    # Generate AI briefing daily at 7:30 AM (after collection completes)
    'dc-generate-briefing-daily': {
        'task': 'decision_center.generate_decision_briefing',
        'schedule': crontab(hour=7, minute=30),  # Daily 7:30 AM
    },
    # Send digest emails every 30 min (honours per-user preferred time)
    'dc-send-digest-emails': {
        'task': 'decision_center.send_daily_digest_emails',
        'schedule': crontab(minute='0,30'),  # Every 30 minutes
    },
    # --- Exit Protocol Tasks ---
    # Monitor board health daily at 2:15 AM
    'monitor-board-health-daily': {
        'task': 'exit_protocol.tasks.monitor_all_boards_health',
        'schedule': crontab(hour=2, minute=15),  # Daily 2:15 AM
    },
    # --- Project Confidence Score ---
    # Compute auto confidence scores for all boards every 6 hours
    'compute-board-confidence': {
        'task': 'kanban.compute_all_board_confidence',
        'schedule': crontab(minute=30, hour='*/6'),  # Every 6 hours at :30
    },
    # --- Analytics Tasks ---
    # Clean up user sessions older than 90 days (daily at 4:30 AM)
    'analytics-cleanup-old-sessions': {
        'task': 'analytics.tasks.cleanup_old_sessions',
        'schedule': crontab(hour=4, minute=30),
    },
    # Generate daily analytics report (daily at 5:00 AM)
    'analytics-daily-report': {
        'task': 'analytics.tasks.generate_daily_analytics_report',
        'schedule': crontab(hour=5, minute=0),
    },
    # --- Webhook Maintenance ---
    # Purge webhook delivery logs older than 30 days (daily at 4:15 AM) so the
    # WebhookDelivery table doesn't grow unbounded.
    'cleanup-old-webhook-deliveries': {
        'task': 'webhooks.tasks.cleanup_old_deliveries',
        'schedule': crontab(hour=4, minute=15),
    },
}

# Route all AI summary tasks to a dedicated 'summaries' queue so they never
# compete with user-facing operations (auth, data saves, conflict detection).
app.conf.task_routes = {
    'kanban.ai_summary.*': {'queue': 'summaries'},
    'kanban.ai_streaming.*': {'queue': 'ai_tasks'},
    # User-triggered, latency-sensitive work (Reset Demo / sandbox provisioning)
    # goes to a dedicated 'interactive' queue consumed by its own worker so it
    # never queues behind the burst of heavy scheduled tasks that Celery Beat's
    # DatabaseScheduler fires on startup (detect_conflicts, the daily Gemini
    # executive briefing, commitment decay, digest emails — all on 'celery').
    # NB: the task name is 'kanban.sandbox_provisioning.provision_sandbox'
    # (see provision_sandbox_task's @shared_task name=), NOT 'provision_sandbox_task'.
    'kanban.sandbox_provisioning.*': {'queue': 'interactive'},
}


# ---------------------------------------------------------------------------
# Catch-up: run daily AI tasks if they were missed (celery was not running)
# ---------------------------------------------------------------------------
from celery.signals import worker_ready

@worker_ready.connect
def _catchup_daily_tasks(sender, **kwargs):
    """
    On worker startup, check whether today's daily AI tasks have already run.
    If not, enqueue them so summaries and decision items stay current even when
    celery was down during the scheduled window.
    """
    import threading

    # Stagger the catch-up jobs a few minutes into the future instead of firing
    # them the instant the worker boots. On a single (solo) worker every task
    # runs one-at-a-time, so enqueueing these heavy AI jobs immediately floods
    # the worker for 2–3 minutes and makes any interactive job started right
    # after startup — most visibly "Reset Demo" — wait in line behind them.
    # These are daily summaries with no minute-level deadline, so a short delay
    # is harmless and leaves the worker free for interactive work straight after
    # startup. Staggering (not all at the same ETA) also leaves idle gaps
    # between them so a reset fired a little later still slots in quickly.
    CATCHUP_BRIEFING_DELAY = 180       # 3 min
    CATCHUP_DC_COLLECT_DELAY = 210     # 3.5 min
    CATCHUP_DC_BRIEFING_DELAY = 240    # 4 min

    def _run_catchup():
        import django
        django.setup()

        import logging
        _logger = logging.getLogger('celery.catchup')
        from django.utils import timezone

        today = timezone.localdate()
        _logger.info("Celery worker ready — checking for missed daily tasks (today=%s)", today)

        # 1. Executive briefing (AI summaries for missions/boards)
        try:
            from kanban.models import Mission
            # Check if any active mission was updated today by the briefing task
            stale = Mission.objects.filter(
                status='active',
            ).exclude(
                ai_summary_generated_at__date=today,
            ).exists()
            if stale:
                _logger.info("Missed daily executive briefing — scheduling in %ss", CATCHUP_BRIEFING_DELAY)
                app.send_task(
                    'kanban.ai_summary.generate_daily_executive_briefing',
                    countdown=CATCHUP_BRIEFING_DELAY,
                )
            else:
                _logger.info("Daily executive briefing already ran today — skipping")
        except Exception as exc:
            _logger.warning("Catchup check for executive briefing failed: %s", exc)

        # 2. Decision Center item collection
        try:
            from django.core.cache import cache as _cache
            cache_key = f'dc_collect_ran_{today.isoformat()}'
            already_ran = _cache.get(cache_key)
            if not already_ran:
                _logger.info("Missed decision item collection — scheduling in %ss", CATCHUP_DC_COLLECT_DELAY)
                app.send_task(
                    'decision_center.collect_decision_items',
                    countdown=CATCHUP_DC_COLLECT_DELAY,
                )
                _cache.set(cache_key, True, 86400)  # expires in 24h
            else:
                _logger.info("Decision item collection already ran today — skipping")
        except Exception as exc:
            _logger.warning("Catchup check for decision items failed: %s", exc)

        # 3. Decision Center AI briefing
        try:
            from decision_center.models import DecisionCenterBriefing
            has_today_briefing = DecisionCenterBriefing.objects.filter(
                generated_at__date=today,
            ).exists()
            if not has_today_briefing:
                _logger.info("Missed decision center briefing — scheduling in %ss", CATCHUP_DC_BRIEFING_DELAY)
                app.send_task(
                    'decision_center.generate_decision_briefing',
                    countdown=CATCHUP_DC_BRIEFING_DELAY,
                )
            else:
                _logger.info("Decision center briefing already ran today — skipping")
        except Exception as exc:
            _logger.warning("Catchup check for decision briefing failed: %s", exc)

    # Run in a separate thread to avoid blocking worker startup
    threading.Thread(target=_run_catchup, daemon=True).start()


@app.task(bind=True)
def debug_task(self):
    print(f'Request: {self.request!r}')
