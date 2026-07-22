"""
Celery tasks for the accounts app.

Currently:
  sync_task_to_calendar  — syncs a PrizmAI task's due date to Google Calendar.
  delete_calendar_event  — deletes a single Google Calendar event by event id.
"""
from celery import shared_task
import logging

logger = logging.getLogger(__name__)


@shared_task(bind=True, max_retries=2, default_retry_delay=30)
def delete_calendar_event(self, user_id, event_id):
    """
    Delete a single Google Calendar event from a user's calendar.

    Used when a PrizmAI task is deleted so the corresponding calendar event is
    cleaned up automatically.  Failures are best-effort — a missing or already-
    deleted event is silently ignored.
    """
    try:
        from googleapiclient.discovery import build
        from googleapiclient.errors import HttpError
        from google.oauth2.credentials import Credentials
        from google.auth.transport.requests import Request as GoogleRequest
        from django.conf import settings
        from accounts.models import GoogleCalendarToken

        try:
            token_obj = GoogleCalendarToken.objects.get(
                user_id=user_id, sync_enabled=True
            )
        except GoogleCalendarToken.DoesNotExist:
            return

        expiry = token_obj.token_expiry
        if expiry is not None and expiry.tzinfo is not None:
            from datetime import timezone as _stdlib_tz
            expiry = expiry.astimezone(_stdlib_tz.utc).replace(tzinfo=None)

        creds = Credentials(
            token=token_obj.access_token,
            refresh_token=token_obj.refresh_token,
            token_uri="https://oauth2.googleapis.com/token",
            client_id=settings.GOOGLE_OAUTH2_CLIENT_ID,
            client_secret=settings.GOOGLE_OAUTH2_CLIENT_SECRET,
            scopes=settings.GOOGLE_CALENDAR_SCOPES,
            expiry=expiry,
        )
        if not creds.valid and creds.refresh_token:
            creds.refresh(GoogleRequest())
            from datetime import timezone as _stdlib_tz
            new_expiry = creds.expiry
            if new_expiry is not None and new_expiry.tzinfo is None:
                new_expiry = new_expiry.replace(tzinfo=_stdlib_tz.utc)
            token_obj.access_token = creds.token
            token_obj.token_expiry = new_expiry
            token_obj.save(update_fields=["access_token", "token_expiry", "updated_at"])

        service = build("calendar", "v3", credentials=creds)
        calendar_id = token_obj.calendar_id or "primary"
        try:
            service.events().delete(
                calendarId=calendar_id, eventId=event_id
            ).execute()
        except HttpError as e:
            if e.resp.status != 404:
                raise
    except Exception as exc:
        logger.warning(
            f"delete_calendar_event: could not delete event {event_id} "
            f"for user {user_id}: {exc}"
        )
        try:
            raise self.retry(exc=exc)
        except self.MaxRetriesExceededError:
            pass
        except Exception:
            pass


@shared_task(bind=True, max_retries=3, default_retry_delay=60)
def sync_task_to_calendar(self, task_id, old_assignee_id=None, old_event_id=None):
    """
    Create, update, or delete a Google Calendar event for a PrizmAI task.

    Called whenever a task's `due_date` or `assigned_to` changes AND the task's
    assigned user has an active `GoogleCalendarToken` with `sync_enabled=True`.

    Calendar event logic:
      - If task has a due_date → create or update a Calendar event.
      - If task no longer has a due_date → delete the Calendar event if one exists.
      - Stores the Google Calendar event id back on the task in `google_calendar_event_id`.
      - When old_assignee_id + old_event_id are supplied (assignee changed), the stale
        event is deleted from the old assignee's calendar before creating a new one.

    Token refresh is handled automatically by google.oauth2.credentials.Credentials.
    """
    token_obj = None
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
        # Cleanup: remove the stale event from the old assignee's calendar
        # when the task's assignee changed.
        # -----------------------------------------------------------------
        if old_assignee_id and old_event_id:
            try:
                old_token = GoogleCalendarToken.objects.get(
                    user_id=old_assignee_id, sync_enabled=True
                )
                old_expiry = old_token.token_expiry
                if old_expiry is not None and old_expiry.tzinfo is not None:
                    from datetime import timezone as _stdlib_tz
                    old_expiry = old_expiry.astimezone(_stdlib_tz.utc).replace(tzinfo=None)
                old_creds = Credentials(
                    token=old_token.access_token,
                    refresh_token=old_token.refresh_token,
                    token_uri="https://oauth2.googleapis.com/token",
                    client_id=settings.GOOGLE_OAUTH2_CLIENT_ID,
                    client_secret=settings.GOOGLE_OAUTH2_CLIENT_SECRET,
                    scopes=settings.GOOGLE_CALENDAR_SCOPES,
                    expiry=old_expiry,
                )
                if not old_creds.valid and old_creds.refresh_token:
                    old_creds.refresh(GoogleRequest())
                old_service = build("calendar", "v3", credentials=old_creds)
                old_cal_id = old_token.calendar_id or "primary"
                try:
                    old_service.events().delete(
                        calendarId=old_cal_id, eventId=old_event_id
                    ).execute()
                except HttpError as _he:
                    if _he.resp.status != 404:
                        logger.warning(
                            f"sync_task_to_calendar: could not delete old event "
                            f"{old_event_id} for user {old_assignee_id}: {_he}"
                        )
            except GoogleCalendarToken.DoesNotExist:
                pass  # old assignee had no sync token — nothing to clean up
            except Exception as _ex:
                logger.warning(
                    f"sync_task_to_calendar: best-effort cleanup failed for "
                    f"old assignee {old_assignee_id}: {_ex}"
                )

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
        # google-auth uses datetime.utcnow() (naive UTC) internally to check
        # expiry. Django stores token_expiry as timezone-aware. We must
        # convert to naive UTC before passing to Credentials, otherwise
        # comparing aware vs naive datetimes raises TypeError.
        expiry = token_obj.token_expiry
        if expiry is not None and expiry.tzinfo is not None:
            from datetime import timezone as _stdlib_tz
            expiry = expiry.astimezone(_stdlib_tz.utc).replace(tzinfo=None)

        creds = Credentials(
            token=token_obj.access_token,
            refresh_token=token_obj.refresh_token,
            token_uri="https://oauth2.googleapis.com/token",
            client_id=settings.GOOGLE_OAUTH2_CLIENT_ID,
            client_secret=settings.GOOGLE_OAUTH2_CLIENT_SECRET,
            scopes=settings.GOOGLE_CALENDAR_SCOPES,
            expiry=expiry,  # naive UTC — required by google-auth
        )
        if not creds.valid and creds.refresh_token:
            creds.refresh(GoogleRequest())
            # Persist refreshed token — store as aware UTC for Django
            from datetime import timezone as _stdlib_tz
            new_expiry = creds.expiry
            if new_expiry is not None and new_expiry.tzinfo is None:
                new_expiry = new_expiry.replace(tzinfo=_stdlib_tz.utc)
            token_obj.access_token = creds.token
            token_obj.token_expiry = new_expiry
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
        from datetime import timedelta
        from django.utils import timezone as tz

        # Ensure due_dt is timezone-aware — Google Calendar API requires
        # either a timezone offset in the dateTime string or a separate
        # timeZone field.  If the stored value is naive, attach UTC.
        if due_dt.tzinfo is None:
            due_dt = tz.make_aware(due_dt, tz.utc)

        # Google Calendar requires RFC 3339 datetime strings.
        start_str = due_dt.isoformat()
        # Make end = start + 1 hour (Calendar requires a non-zero duration).
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

        # Record successful sync
        from django.utils import timezone as _tz
        token_obj.last_synced_at = _tz.now()
        token_obj.last_sync_error = ""
        token_obj.save(update_fields=["last_synced_at", "last_sync_error", "updated_at"])

    except Exception as exc:
        error_msg = str(exc)
        logger.error(f"sync_task_to_calendar task={task_id} failed: {error_msg}", exc_info=True)

        # Persist the error so the profile page can surface it to the user.
        try:
            if token_obj is not None:
                token_obj.last_sync_error = error_msg[:500]
                token_obj.save(update_fields=["last_sync_error", "updated_at"])
        except Exception:
            pass

        # If the Google Calendar API itself is disabled in the Cloud project,
        # or the OAuth scope was rejected, retrying won't help — mark the token
        # as broken so the user sees a clear status on their profile page.
        non_retryable_phrases = [
            "has not been used in project",
            "it is disabled",
            "accessNotConfigured",
            "disabled for your project",
            "insufficientPermissions",
            "unauthorized_client",
        ]
        if any(phrase in error_msg for phrase in non_retryable_phrases):
            try:
                from accounts.models import GoogleCalendarToken
                from kanban.models import Task as _Task
                task_obj = _Task.objects.select_related("assigned_to").get(pk=task_id)
                GoogleCalendarToken.objects.filter(user=task_obj.assigned_to).update(
                    sync_enabled=False
                )
            except Exception:
                pass
            logger.error(
                f"sync_task_to_calendar: non-retryable Google API error for task {task_id} — "
                f"calendar sync disabled for user. Error: {error_msg}"
            )
            return  # Do not retry

        try:
            # self.retry() only works when running inside a Celery worker.
            # When called synchronously (no worker), skip the retry to avoid
            # a MaxRetriesExceededError / no-request-context crash.
            raise self.retry(exc=exc)
        except self.MaxRetriesExceededError:
            raise
        except Exception:
            # Not in a Celery context — just re-raise the original error.
            raise exc


# ---------------------------------------------------------------------------
# Bulk cleanup — purge every PrizmAI-synced event from a user's calendar
# ---------------------------------------------------------------------------
# Marker written into the description of every event we create (see the
# event_body in sync_task_to_calendar above). It lets us recognise PrizmAI
# events on the calendar even when the local Task.google_calendar_event_id
# pointer has been lost — i.e. *orphaned* events. Orphans are created, for
# example, when a demo reset deletes tasks while calendar sync is suppressed
# (see kanban.utils.demo_protection.allow_demo_writes): the per-task delete
# signal short-circuits, so the Google event survives with nothing pointing
# at it, and the app can never clean it up by event id again.
PRIZMAI_EVENT_MARKER = "PrizmAI Task"


def _calendar_service_for_token(token_obj):
    """Build an authorised Google Calendar service from a stored token.

    Mirrors the credential build/refresh handling used by the sync tasks
    above. Returns ``(service, calendar_id)``.
    """
    from googleapiclient.discovery import build
    from google.oauth2.credentials import Credentials
    from google.auth.transport.requests import Request as GoogleRequest
    from django.conf import settings

    expiry = token_obj.token_expiry
    if expiry is not None and expiry.tzinfo is not None:
        from datetime import timezone as _stdlib_tz
        expiry = expiry.astimezone(_stdlib_tz.utc).replace(tzinfo=None)

    creds = Credentials(
        token=token_obj.access_token,
        refresh_token=token_obj.refresh_token,
        token_uri="https://oauth2.googleapis.com/token",
        client_id=settings.GOOGLE_OAUTH2_CLIENT_ID,
        client_secret=settings.GOOGLE_OAUTH2_CLIENT_SECRET,
        scopes=settings.GOOGLE_CALENDAR_SCOPES,
        expiry=expiry,  # naive UTC — required by google-auth
    )
    if not creds.valid and creds.refresh_token:
        creds.refresh(GoogleRequest())
        from datetime import timezone as _stdlib_tz
        new_expiry = creds.expiry
        if new_expiry is not None and new_expiry.tzinfo is None:
            new_expiry = new_expiry.replace(tzinfo=_stdlib_tz.utc)
        token_obj.access_token = creds.token
        token_obj.token_expiry = new_expiry
        token_obj.save(update_fields=["access_token", "token_expiry", "updated_at"])

    service = build("calendar", "v3", credentials=creds)
    calendar_id = token_obj.calendar_id or "primary"
    return service, calendar_id


def purge_calendar_events_for_user(user_id, dry_run=False):
    """Delete EVERY PrizmAI-synced event from a user's Google Calendar.

    Unlike :func:`delete_calendar_event` (which removes a single known event
    id), this scans the calendar for events carrying ``PRIZMAI_EVENT_MARKER``
    in their description and removes them — so it also catches *orphaned*
    events whose ``Task.google_calendar_event_id`` pointer was already lost.
    Local pointers are cleared afterwards so the DB and the calendar end up
    consistent.

    Args:
        user_id: id of the user whose calendar to purge.
        dry_run: when True, only count what would be deleted; delete nothing.

    Returns:
        dict with integer keys ``found``, ``deleted``, ``failed``, ``cleared``.
    """
    from googleapiclient.errors import HttpError
    from accounts.models import GoogleCalendarToken
    from kanban.models import Task

    result = {'found': 0, 'deleted': 0, 'failed': 0, 'cleared': 0}

    # Cleanup must work even when sync is paused, so don't filter on
    # sync_enabled — any stored token has the credentials we need.
    token_obj = GoogleCalendarToken.objects.filter(user_id=user_id).first()
    if token_obj is None:
        logger.info(
            "purge_calendar_events_for_user: no calendar token for user %s", user_id
        )
        return result

    service, calendar_id = _calendar_service_for_token(token_obj)

    page_token = None
    while True:
        resp = service.events().list(
            calendarId=calendar_id,
            q=PRIZMAI_EVENT_MARKER,   # narrow the scan; verified below
            maxResults=2500,
            singleEvents=True,
            showDeleted=False,
            pageToken=page_token,
        ).execute()

        for event in resp.get('items', []):
            description = event.get('description') or ''
            if PRIZMAI_EVENT_MARKER not in description:
                # `q` does loose full-text matching — only delete events we
                # are certain we created.
                continue
            result['found'] += 1
            if dry_run:
                continue
            try:
                service.events().delete(
                    calendarId=calendar_id, eventId=event['id'],
                ).execute()
                result['deleted'] += 1
            except HttpError as e:
                if e.resp.status == 404:
                    result['deleted'] += 1  # already gone — that's the goal
                else:
                    result['failed'] += 1
                    logger.warning(
                        "purge_calendar_events_for_user: could not delete "
                        "event %s for user %s: %s",
                        event.get('id'), user_id, e,
                    )

        page_token = resp.get('nextPageToken')
        if not page_token:
            break

    if not dry_run:
        result['cleared'] = (
            Task.objects.filter(assigned_to_id=user_id)
            .exclude(google_calendar_event_id__isnull=True)
            .exclude(google_calendar_event_id='')
            .update(google_calendar_event_id=None)
        )

    logger.info(
        "purge_calendar_events_for_user(user=%s, dry_run=%s): %s",
        user_id, dry_run, result,
    )
    return result


@shared_task(bind=True, max_retries=1, default_retry_delay=30)
def purge_user_calendar_events(self, user_id, dry_run=False):
    """Best-effort Celery wrapper around :func:`purge_calendar_events_for_user`.

    Failures are swallowed (and returned in the result) so a purge can never
    block the caller — e.g. a demo reset request.
    """
    try:
        return purge_calendar_events_for_user(user_id, dry_run=dry_run)
    except Exception as exc:
        logger.warning(
            "purge_user_calendar_events: purge failed for user %s: %s",
            user_id, exc,
        )
        return {'found': 0, 'deleted': 0, 'failed': 0, 'cleared': 0, 'error': str(exc)}
