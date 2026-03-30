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
    # --- Living Commitment Protocol Tasks ---
    # Apply Bayesian confidence decay every 4 hours
    'run-commitment-decay': {
        'task': 'kanban.run_commitment_decay_all',
        'schedule': crontab(minute=0, hour='*/4'),  # Every 4 hours
    },
    # Refill credibility tokens every Monday at midnight
    'reset-commitment-tokens': {
        'task': 'kanban.reset_weekly_tokens',
        'schedule': crontab(hour=0, minute=0, day_of_week='1'),  # Mon 00:00
    },
}

# Route all AI summary tasks to a dedicated 'summaries' queue so they never
# compete with user-facing operations (auth, data saves, conflict detection).
app.conf.task_routes = {
    'kanban.ai_summary.*': {'queue': 'summaries'},
    'kanban.ai_streaming.*': {'queue': 'ai_tasks'},
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
                _logger.info("Missed daily executive briefing — enqueueing now")
                app.send_task('kanban.ai_summary.generate_daily_executive_briefing')
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
                _logger.info("Missed decision item collection — enqueueing now")
                app.send_task('decision_center.collect_decision_items')
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
                _logger.info("Missed decision center briefing — enqueueing now")
                app.send_task('decision_center.generate_decision_briefing')
            else:
                _logger.info("Decision center briefing already ran today — skipping")
        except Exception as exc:
            _logger.warning("Catchup check for decision briefing failed: %s", exc)

    # Run in a separate thread to avoid blocking worker startup
    threading.Thread(target=_run_catchup, daemon=True).start()


@app.task(bind=True)
def debug_task(self):
    print(f'Request: {self.request!r}')
