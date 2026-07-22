"""
Celery task for live project migration from an external PM tool.

Runs the whole bridge end-to-end on the 'interactive' queue (user is watching a
progress bar): fetch via the connector -> translate + build Strategy/Boards via
the orchestrator -> run the day-one AI audit. Progress is published to a cache
channel the browser polls.

Task name: 'kanban.migration.run_source_migration' (routed to 'interactive' in
kanban_board/celery.py).
"""

import logging

from celery import shared_task

from kanban.utils.connectors.migration_progress import set_progress

logger = logging.getLogger(__name__)


@shared_task(bind=True, name='kanban.migration.run_source_migration', max_retries=0)
def run_source_migration(self, connection_id, project_id, project_name):
    """
    Args:
        connection_id: integrations.SourceConnection id (already workspace-scoped
            + owned by the requesting user when created in the view).
        project_id: provider project key/id to migrate.
        project_name: display name for the resulting Strategy.
    """
    from django.contrib.auth.models import User  # noqa
    from integrations.models import SourceConnection
    from kanban.utils.connectors import ConnectorFactory, ConnectorError
    from kanban.utils.connectors.migration_orchestrator import run_migration
    from kanban.utils.connectors.migration_audit import generate_migration_audit

    task_id = self.request.id

    try:
        connection = SourceConnection.objects.select_related(
            'workspace', 'created_by'
        ).get(id=connection_id)
    except SourceConnection.DoesNotExist:
        set_progress(task_id, 0, "Connection not found.", state="error")
        return {"state": "error", "message": "Connection not found"}

    user = connection.created_by
    try:
        organization = user.profile.organization
    except Exception:
        organization = None

    connection.status = SourceConnection.STATUS_SYNCING
    connection.save(update_fields=['status'])

    try:
        set_progress(task_id, 8, f"Connecting to {connection.get_provider_display()}…")
        connector = ConnectorFactory.get_connector(connection.provider, connection)

        set_progress(task_id, 15, f"Fetching '{project_name}'…")
        raw = connector.fetch_project(project_id)

        def _cb(pct, msg):
            set_progress(task_id, pct, msg)

        result = run_migration(
            provider=connection.provider,
            raw=raw,
            adapter_name=connector.adapter_name,
            project_name=project_name,
            user=user,
            organization=organization,
            session={},
            progress_cb=_cb,
        )

        set_progress(task_id, 88, "Running your day-one AI audit…")
        generate_migration_audit(result.strategy, user)

        from django.utils import timezone
        connection.status = SourceConnection.STATUS_CONNECTED
        connection.last_synced_at = timezone.now()
        connection.save(update_fields=['status', 'last_synced_at'])

        redirect_url = ""
        try:
            redirect_url = result.strategy.get_absolute_url()
        except Exception:
            logger.debug("Could not resolve strategy url", exc_info=True)

        set_progress(
            task_id, 100, "Migration complete!", state="done",
            extra={
                "redirect_url": redirect_url,
                "strategy_id": result.strategy.id,
                "stats": result.stats,
                "warnings": result.warnings[:5],
            },
        )
        # Include redirect_url in the return value too, so the status endpoint can
        # recover the completion from Celery's result backend if the cache channel
        # didn't propagate.
        return {
            "state": "done",
            "strategy_id": result.strategy.id,
            "stats": result.stats,
            "redirect_url": redirect_url,
        }

    except ConnectorError as exc:
        logger.warning("Migration connector error (conn=%s): %s", connection_id, exc)
        connection.status = SourceConnection.STATUS_ERROR
        connection.save(update_fields=['status'])
        set_progress(task_id, 0, str(exc), state="error")
        return {"state": "error", "message": str(exc)}
    except Exception as exc:
        logger.exception("Migration failed (conn=%s)", connection_id)
        connection.status = SourceConnection.STATUS_ERROR
        connection.save(update_fields=['status'])
        set_progress(task_id, 0, "Migration failed. Please try again.", state="error")
        return {"state": "error", "message": "Migration failed"}
