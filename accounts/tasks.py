"""
Celery tasks for the accounts app.

Currently:
  sync_task_to_calendar — syncs a PrizmAI task's due date to Google Calendar.
"""
from celery import shared_task
import logging

logger = logging.getLogger(__name__)


@shared_task(bind=True, max_retries=3, default_retry_delay=60)
def sync_task_to_calendar(self, task_id):
    """
    Create, update, or delete a Google Calendar event for a PrizmAI task.

    Called whenever a task's `due_date` changes AND the task's assigned user
    has an active `GoogleCalendarToken` with `sync_enabled=True`.

    Calendar event logic:
      - If task has a due_date → create or update a Calendar event.
      - If task no longer has a due_date → delete the Calendar event if one exists.
      - Stores the Google Calendar event id back on the task in `google_calendar_event_id`.

    Token refresh is handled automatically by google.oauth2.credentials.Credentials.
    """
    try:
        from django.utils import timezone as tz
        from googleapiclient.discovery import build
        from googleapiclient.errors import HttpError
        from google.oauth2.credentials import Credentials
        from google.auth.transport.requests import Request as GoogleRequest
        from django.conf import settings

        from kanban.models import Task
        from accounts.models import GoogleCalendarToken

        # -----------------------------------------------------------------
        # Load task
        # -----------------------------------------------------------------
        try:
            task = Task.objects.select_related("assigned_to").get(pk=task_id)
        except Task.DoesNotExist:
            logger.warning(f"sync_task_to_calendar: task {task_id} not found — skipping.")
            return

        if not task.assigned_to:
            return

        # -----------------------------------------------------------------
        # Load token (master toggle check)
        # -----------------------------------------------------------------
        try:
            token_obj = GoogleCalendarToken.objects.get(
                user=task.assigned_to, sync_enabled=True
            )
        except GoogleCalendarToken.DoesNotExist:
            return  # user not connected or sync paused

        # -----------------------------------------------------------------
        # Build credentials and refresh if needed
        # -----------------------------------------------------------------
        creds = Credentials(
            token=token_obj.access_token,
            refresh_token=token_obj.refresh_token,
            token_uri="https://oauth2.googleapis.com/token",
            client_id=settings.GOOGLE_OAUTH2_CLIENT_ID,
            client_secret=settings.GOOGLE_OAUTH2_CLIENT_SECRET,
            scopes=settings.GOOGLE_CALENDAR_SCOPES,
        )
        if creds.expired and creds.refresh_token:
            creds.refresh(GoogleRequest())
            # Persist refreshed token
            token_obj.access_token = creds.token
            token_obj.token_expiry = creds.expiry
            token_obj.save(update_fields=["access_token", "token_expiry", "updated_at"])

        service = build("calendar", "v3", credentials=creds)
        calendar_id = token_obj.calendar_id or "primary"

        # -----------------------------------------------------------------
        # Delete case: due_date removed
        # -----------------------------------------------------------------
        if not task.due_date:
            if task.google_calendar_event_id:
                try:
                    service.events().delete(
                        calendarId=calendar_id,
                        eventId=task.google_calendar_event_id,
                    ).execute()
                except HttpError as e:
                    if e.resp.status != 404:  # 404 = already deleted, fine
                        raise
                task.google_calendar_event_id = None
                task.save(update_fields=["google_calendar_event_id"])
            return

        # -----------------------------------------------------------------
        # Create / update event
        # -----------------------------------------------------------------
        due_dt = task.due_date
        # Google Calendar requires RFC 3339 datetime strings.
        start_str = due_dt.isoformat()
        # Make end = start + 1 hour (Calendar requires a non-zero duration).
        from datetime import timedelta
        end_str = (due_dt + timedelta(hours=1)).isoformat()

        board_name = task.column.board.name if task.column_id else ""
        event_body = {
            "summary": f"[{board_name}] {task.title}" if board_name else task.title,
            "description": (
                f"PrizmAI Task\n"
                f"Board: {board_name}\n"
                f"Column: {task.column.name if task.column_id else ''}\n"
                f"Priority: {task.get_priority_display()}\n"
                f"Progress: {task.progress}%"
            ),
            "start": {"dateTime": start_str},
            "end": {"dateTime": end_str},
            "reminders": {"useDefault": True},
        }

        if task.google_calendar_event_id:
            # Update existing event
            service.events().update(
                calendarId=calendar_id,
                eventId=task.google_calendar_event_id,
                body=event_body,
            ).execute()
        else:
            # Create new event and persist the id
            created = service.events().insert(
                calendarId=calendar_id,
                body=event_body,
            ).execute()
            task.google_calendar_event_id = created.get("id")
            task.save(update_fields=["google_calendar_event_id"])

    except Exception as exc:
        logger.error(f"sync_task_to_calendar task={task_id} failed: {exc}", exc_info=True)
        raise self.retry(exc=exc)
