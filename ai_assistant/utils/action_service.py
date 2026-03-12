"""
SpectraActionService — executes database writes for Conversational Spectra.

This service is completely separate from the AI / Gemini logic.
Every database write is wrapped in try / except and returns a structured dict.
"""
import logging
from django.db import transaction
from django.db.models import Q
from django.urls import reverse
from django.utils import timezone

logger = logging.getLogger(__name__)

# Mapping from user-facing numeric template IDs (1, 2, 3) to the internal
# string IDs used in kanban.automation_views.TEMPLATE_RULES.
TEMPLATE_ID_MAP = {
    1: 'tpl_overdue_urgent',
    2: 'tpl_done_notify',
    3: 'tpl_approaching_notify',
}


class SpectraActionService:
    """Handles all database writes initiated by Spectra conversations."""

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _user_has_board_access(user, board):
        """Return True if *user* is a member of (or creator of) *board*."""
        if board.created_by_id == user.id:
            return True
        return board.members.filter(id=user.id).exists()

    @staticmethod
    def _resolve_column(board):
        """Find the 'To Do' column (or fall back to the first column)."""
        from kanban.models import Column

        col = Column.objects.filter(
            board=board,
            name__iregex=r'^(to do|todo)$',
        ).first()
        if not col:
            col = Column.objects.filter(board=board).order_by('position').first()
        return col

    @staticmethod
    def _resolve_assignee(name, board):
        """
        Try to match *name* (case-insensitive) against board members.

        Returns ``(user_obj, None)`` on success, or
        ``(None, member_names_list)`` on failure.
        """
        name_lower = name.lower().strip()
        if not name_lower:
            return None, []
        candidates = list(board.members.all())
        if board.created_by and board.created_by not in candidates:
            candidates.append(board.created_by)

        for u in candidates:
            full = u.get_full_name().lower()
            if (
                name_lower == u.username.lower()
                or name_lower == full
                or name_lower == u.first_name.lower()
                or name_lower == u.last_name.lower()
            ):
                return u, None

        member_names = [
            u.get_full_name() or u.username for u in candidates
        ]
        return None, member_names

    # ------------------------------------------------------------------
    # Task creation
    # ------------------------------------------------------------------

    def create_task(self, user, board, collected_data):
        """
        Create a Task using *collected_data* dict.

        Expected keys: ``title`` (required), ``due_date`` (datetime | None),
        ``assignee`` (User | None), ``priority`` (str, default 'medium').

        Returns ``{'success': True, 'task': <Task>, 'url': str}``
        or ``{'success': False, 'error': str}``.
        """
        from kanban.models import Task, TaskActivity
        from kanban.audit_utils import log_model_change

        try:
            # Permission check
            if not self._user_has_board_access(user, board):
                return {
                    'success': False,
                    'error': "You don't have access to this board.",
                }

            column = self._resolve_column(board)
            if not column:
                return {
                    'success': False,
                    'error': 'This board has no columns. Please create a column first.',
                }

            # Determine position (end of column)
            last = Task.objects.filter(column=column).order_by('-position').first()
            position = (last.position + 1) if last else 0

            task = Task(
                title=collected_data['title'],
                column=column,
                position=position,
                priority=collected_data.get('priority', 'medium'),
                created_by=user,
            )

            if collected_data.get('due_date'):
                due = collected_data['due_date']
                # due_date may be a datetime object or an ISO string from JSON serialization
                if isinstance(due, str):
                    from django.utils import timezone as tz
                    from datetime import datetime as dt
                    due = dt.fromisoformat(due)
                    if tz.is_naive(due):
                        due = tz.make_aware(due)
                task.due_date = due
            if collected_data.get('assignee'):
                task.assigned_to = collected_data['assignee']
            if collected_data.get('description'):
                task.description = collected_data['description']

            # Set change-tracking attribute used by signals
            task._changed_by_user = user

            with transaction.atomic():
                task.save()

                # Record activity
                TaskActivity.objects.create(
                    task=task,
                    user=user,
                    activity_type='created',
                    description=f"Created task '{task.title}' via Spectra",
                )

            # Audit trail (non-critical — outside the atomic block)
            try:
                log_model_change('task.created', task, user)
            except Exception as audit_err:
                logger.warning('Spectra audit log failed for task %s: %s', task.id, audit_err)

            task_url = reverse('task_detail', args=[task.id])
            logger.info('Spectra created task #%s "%s" for user %s', task.id, task.title, user.username)

            return {'success': True, 'task': task, 'url': task_url}

        except Exception as exc:
            logger.exception('Spectra task creation failed: %s', exc)
            return {'success': False, 'error': str(exc)}

    # ------------------------------------------------------------------
    # Board creation
    # ------------------------------------------------------------------

    def create_board(self, user, collected_data):
        """
        Create a Board with default columns and add *user* as owner.

        Expected keys: ``name`` (required), ``description`` (str | None).

        Returns ``{'success': True, 'board': <Board>, 'url': str}``
        or ``{'success': False, 'error': str}``.
        """
        from kanban.models import Board, Column
        from kanban.audit_utils import log_model_change

        try:
            # Resolve organization from user profile (may be None in MVP mode)
            organization = None
            if hasattr(user, 'profile') and user.profile:
                organization = user.profile.organization

            with transaction.atomic():
                board = Board(
                    name=collected_data['name'],
                    description=collected_data.get('description', '') or '',
                    organization=organization,
                    created_by=user,
                )
                board.save()
                board.members.add(user)

                # Assign Admin role via RBAC if organization exists
                if organization:
                    try:
                        from kanban.permission_models import Role, BoardMembership
                        admin_role = Role.objects.filter(
                            organization=organization,
                            name='Admin',
                        ).first()
                        if admin_role:
                            BoardMembership.objects.create(
                                board=board,
                                user=user,
                                role=admin_role,
                                added_by=user,
                            )
                    except Exception as rbac_err:
                        logger.warning('Spectra RBAC setup failed for board %s: %s', board.id, rbac_err)

                # Create 3 default columns (matching existing board creation behaviour)
                default_columns = ['To Do', 'In Progress', 'Done']
                for i, col_name in enumerate(default_columns):
                    Column.objects.create(name=col_name, board=board, position=i)

            # Audit trail (non-critical — outside the atomic block)
            try:
                log_model_change('board.created', board, user)
            except Exception as audit_err:
                logger.warning('Spectra audit log failed for board %s: %s', board.id, audit_err)

            board_url = reverse('board_detail', args=[board.id])
            logger.info('Spectra created board #%s "%s" for user %s', board.id, board.name, user.username)

            return {'success': True, 'board': board, 'url': board_url}

        except Exception as exc:
            logger.exception('Spectra board creation failed: %s', exc)
            return {'success': False, 'error': str(exc)}

    # ------------------------------------------------------------------
    # Automation template activation
    # ------------------------------------------------------------------

    def activate_automation_template(self, user, board, template_number):
        """
        Activate one of the three preset automation templates.

        ``template_number``: 1, 2, or 3 (mapped internally to string IDs).

        Returns ``{'success': True, 'automation': <BoardAutomation>}``
        or ``{'success': False, 'error': str}``.
        """
        from kanban.automation_models import BoardAutomation
        from kanban.automation_views import TEMPLATE_RULES

        try:
            # Permission check
            if not self._user_has_board_access(user, board):
                return {
                    'success': False,
                    'error': "You don't have access to this board.",
                }

            tpl_id = TEMPLATE_ID_MAP.get(template_number)
            if not tpl_id:
                return {
                    'success': False,
                    'error': f'Unknown template number {template_number}. Choose 1, 2, or 3.',
                }

            tpl = next((t for t in TEMPLATE_RULES if t['id'] == tpl_id), None)
            if tpl is None:
                return {
                    'success': False,
                    'error': 'Template definition not found.',
                }

            # Reuse the same get_or_create logic as the Activate button
            automation, created = BoardAutomation.objects.get_or_create(
                board=board,
                name=tpl['name'],
                defaults=dict(
                    trigger_type=tpl['trigger_type'],
                    trigger_value=tpl['trigger_value'],
                    action_type=tpl['action_type'],
                    action_value=tpl['action_value'],
                    is_active=True,
                    created_by=user,
                ),
            )

            if not created:
                if not automation.is_active:
                    # Re-activate previously deactivated automation
                    automation.is_active = True
                    automation.save(update_fields=['is_active'])
                    logger.info(
                        'Spectra re-activated automation "%s" on board #%s for user %s',
                        tpl['name'], board.id, user.username,
                    )
                    return {'success': True, 'automation': automation}
                return {
                    'success': False,
                    'error': f'The automation "{tpl["name"]}" is already active on this board.',
                }

            logger.info(
                'Spectra activated automation "%s" on board #%s for user %s',
                tpl['name'], board.id, user.username,
            )
            return {'success': True, 'automation': automation}

        except Exception as exc:
            logger.exception('Spectra automation activation failed: %s', exc)
            return {'success': False, 'error': str(exc)}

    # ------------------------------------------------------------------
    # Send message
    # ------------------------------------------------------------------

    def send_message(self, user, board, collected_data):
        """
        Send a chat message to a board member.

        Expected keys: ``recipient`` (name/username), ``message_content`` (str).
        """
        from messaging.models import ChatRoom, ChatMessage

        try:
            if not self._user_has_board_access(user, board):
                return {'success': False, 'error': "You don't have access to this board."}

            # Resolve recipient
            recipient_text = collected_data.get('recipient', '')
            recipient, member_names = self._resolve_assignee(recipient_text, board)
            if not recipient:
                names = ', '.join(member_names) if member_names else 'No members'
                return {
                    'success': False,
                    'error': f'Could not find "{recipient_text}". Board members: {names}',
                }

            content = collected_data.get('message_content', '')
            if not content:
                return {'success': False, 'error': 'Message content cannot be empty.'}

            # Find or create a chat room on this board (use "General" room)
            room = ChatRoom.objects.filter(board=board).first()
            if not room:
                room = ChatRoom.objects.create(
                    board=board,
                    name='General',
                    created_by=user,
                )
                room.members.add(user, recipient)

            # Ensure both users are room members
            room.members.add(user, recipient)

            with transaction.atomic():
                msg = ChatMessage.objects.create(
                    chat_room=room,
                    author=user,
                    content=content,
                )
                msg.mentioned_users.add(recipient)

            logger.info(
                'Spectra sent message from %s to %s in room %s',
                user.username, recipient.username, room.name,
            )
            return {
                'success': True,
                'message': (
                    f"✅ **Message sent!**\n\n"
                    f"💬 Your message to **{recipient.get_full_name() or recipient.username}** "
                    f"has been posted in **{room.name}** on **{board.name}**."
                ),
            }

        except Exception as exc:
            logger.exception('Spectra send_message failed: %s', exc)
            return {'success': False, 'error': str(exc)}

    # ------------------------------------------------------------------
    # Log time entry
    # ------------------------------------------------------------------

    def log_time_entry(self, user, board, collected_data):
        """
        Log a time entry against a task.

        Expected keys: ``task_name`` (str), ``hours`` (number),
        ``work_date`` (str, optional), ``description`` (str, optional).
        """
        from kanban.budget_models import TimeEntry
        from kanban.models import Task

        try:
            if not self._user_has_board_access(user, board):
                return {'success': False, 'error': "You don't have access to this board."}

            # Resolve task by name
            task_name = collected_data.get('task_name', '')
            task = Task.objects.filter(
                column__board=board,
                title__icontains=task_name,
            ).first()
            if not task:
                return {
                    'success': False,
                    'error': f'Could not find a task matching "{task_name}" on this board.',
                }

            hours = collected_data.get('hours', 0)
            try:
                hours = float(hours)
            except (TypeError, ValueError):
                return {'success': False, 'error': 'Invalid hours value.'}
            if hours < 0.01 or hours > 16:
                return {'success': False, 'error': 'Hours must be between 0.01 and 16.'}

            # Parse work date
            work_date_str = collected_data.get('work_date', '')
            if work_date_str:
                from ai_assistant.utils.conversation_flow import _parse_date
                parsed = _parse_date(work_date_str)
                work_date = parsed.date() if parsed else timezone.now().date()
            else:
                work_date = timezone.now().date()

            with transaction.atomic():
                entry = TimeEntry.objects.create(
                    task=task,
                    user=user,
                    hours_spent=hours,
                    work_date=work_date,
                    description=collected_data.get('description', ''),
                )

            logger.info(
                'Spectra logged %s hours on task "%s" for user %s',
                hours, task.title, user.username,
            )
            return {
                'success': True,
                'message': (
                    f"✅ **Time logged!**\n\n"
                    f"⏱️ **{hours}h** logged on **{task.title}** "
                    f"for {work_date.strftime('%B %d, %Y')}."
                ),
            }

        except Exception as exc:
            logger.exception('Spectra log_time_entry failed: %s', exc)
            return {'success': False, 'error': str(exc)}

    # ------------------------------------------------------------------
    # Schedule event
    # ------------------------------------------------------------------

    def schedule_event(self, user, board, collected_data):
        """
        Create a calendar event.

        Expected keys: ``title`` (str), ``start_datetime`` (str),
        ``end_datetime`` (str, optional), ``event_type`` (str, optional),
        ``participants`` (list of names, optional), ``location`` (str, optional).
        """
        from kanban.models import CalendarEvent

        try:
            title = collected_data.get('title', 'Untitled Event')

            # Parse start datetime
            from ai_assistant.utils.conversation_flow import _parse_date
            start_str = collected_data.get('start_datetime', '')
            start_dt = _parse_date(start_str) if start_str else None
            if not start_dt:
                return {'success': False, 'error': f'Could not parse start time: "{start_str}"'}

            # Parse end datetime (default: 1 hour after start)
            end_str = collected_data.get('end_datetime', '')
            end_dt = _parse_date(end_str) if end_str else None
            if not end_dt:
                from datetime import timedelta
                end_dt = start_dt + timedelta(hours=1)

            event_type = collected_data.get('event_type', 'meeting')
            valid_types = ('meeting', 'out_of_office', 'busy_block', 'team_event')
            if event_type not in valid_types:
                event_type = 'meeting'

            with transaction.atomic():
                event = CalendarEvent.objects.create(
                    title=title,
                    start_datetime=start_dt,
                    end_datetime=end_dt,
                    event_type=event_type,
                    location=collected_data.get('location', ''),
                    description=collected_data.get('description', ''),
                    board=board,
                    created_by=user,
                )
                # Add creator as participant
                event.participants.add(user)

                # Resolve and add other participants
                participants = collected_data.get('participants', [])
                if isinstance(participants, list) and board:
                    for name in participants:
                        p, _ = self._resolve_assignee(str(name), board)
                        if p:
                            event.participants.add(p)

            logger.info(
                'Spectra scheduled event "%s" for user %s', title, user.username,
            )
            return {
                'success': True,
                'message': (
                    f"✅ **Event scheduled!**\n\n"
                    f"📅 **{event.title}** on "
                    f"{start_dt.strftime('%A, %B %d at %I:%M %p')}."
                ),
            }

        except Exception as exc:
            logger.exception('Spectra schedule_event failed: %s', exc)
            return {'success': False, 'error': str(exc)}

    # ------------------------------------------------------------------
    # Create retrospective
    # ------------------------------------------------------------------

    def create_retrospective(self, user, board, collected_data):
        """
        Generate an AI-powered retrospective using RetrospectiveGenerator.

        Expected keys: ``period_start`` (str), ``period_end`` (str),
        ``retrospective_type`` (str, optional), ``manual_insights`` (str, optional).
        """
        try:
            if not self._user_has_board_access(user, board):
                return {'success': False, 'error': "You don't have access to this board."}

            from ai_assistant.utils.conversation_flow import _parse_date

            start_str = collected_data.get('period_start', '')
            end_str = collected_data.get('period_end', '')

            start_dt = _parse_date(start_str)
            end_dt = _parse_date(end_str)

            if not start_dt or not end_dt:
                return {
                    'success': False,
                    'error': f'Could not parse period dates: "{start_str}" to "{end_str}"',
                }

            retro_type = collected_data.get('retrospective_type', 'sprint')

            from kanban.utils.retrospective_generator import RetrospectiveGenerator
            generator = RetrospectiveGenerator(
                board=board,
                period_start=start_dt.date() if hasattr(start_dt, 'date') else start_dt,
                period_end=end_dt.date() if hasattr(end_dt, 'date') else end_dt,
            )
            retro = generator.create_retrospective(
                created_by=user,
                retrospective_type=retro_type,
            )

            logger.info(
                'Spectra created %s retrospective for board %s, user %s',
                retro_type, board.name, user.username,
            )
            return {
                'success': True,
                'message': (
                    f"✅ **Retrospective generated!**\n\n"
                    f"📊 **{retro_type.capitalize()} retrospective** for **{board.name}** "
                    f"({start_dt.strftime('%b %d')} → {end_dt.strftime('%b %d, %Y')}) "
                    f"is ready for review."
                ),
            }

        except Exception as exc:
            logger.exception('Spectra create_retrospective failed: %s', exc)
            return {'success': False, 'error': str(exc)}

    # ------------------------------------------------------------------
    # Create custom automation (trigger-based)
    # ------------------------------------------------------------------

    def create_custom_automation(self, user, board, collected_data):
        """
        Create a custom trigger-based automation rule.

        Expected keys: ``name``, ``trigger_type``, ``action_type``,
        plus optional ``trigger_value``, ``action_value``.
        """
        from kanban.automation_models import BoardAutomation

        try:
            if not self._user_has_board_access(user, board):
                return {'success': False, 'error': "You don't have access to this board."}

            name = collected_data.get('name', 'Untitled Automation')
            trigger_type = collected_data.get('trigger_type', '')
            action_type = collected_data.get('action_type', '')

            if not trigger_type or not action_type:
                return {'success': False, 'error': 'Trigger type and action type are required.'}

            with transaction.atomic():
                automation = BoardAutomation.objects.create(
                    board=board,
                    name=name,
                    trigger_type=trigger_type,
                    trigger_value=collected_data.get('trigger_value', ''),
                    action_type=action_type,
                    action_value=collected_data.get('action_value', ''),
                    is_active=True,
                    created_by=user,
                )

            logger.info(
                'Spectra created automation "%s" on board %s for user %s',
                name, board.name, user.username,
            )
            return {
                'success': True,
                'message': (
                    f"✅ **Automation created!**\n\n"
                    f"⚡ **{automation.name}** is now active on **{board.name}**.\n"
                    f"Trigger: {trigger_type} → Action: {action_type}"
                ),
            }

        except Exception as exc:
            logger.exception('Spectra create_custom_automation failed: %s', exc)
            return {'success': False, 'error': str(exc)}

    # ------------------------------------------------------------------
    # Create scheduled automation
    # ------------------------------------------------------------------

    def create_scheduled_automation(self, user, board, collected_data):
        """
        Create a time-based scheduled automation.

        Expected keys: ``name``, ``schedule_type``, ``action``,
        plus optional ``scheduled_time``, ``notify_target``, ``task_filter``,
        ``action_value``.
        """
        from kanban.automation_models import ScheduledAutomation

        try:
            if not self._user_has_board_access(user, board):
                return {'success': False, 'error': "You don't have access to this board."}

            name = collected_data.get('name', 'Untitled Scheduled Automation')
            schedule_type = collected_data.get('schedule_type', 'daily')
            action = collected_data.get('action', '')

            if not action:
                return {'success': False, 'error': 'Action type is required.'}

            # Parse scheduled time
            time_str = collected_data.get('scheduled_time', '09:00')
            from datetime import time as dt_time
            try:
                parts = time_str.split(':')
                scheduled_time = dt_time(int(parts[0]), int(parts[1]) if len(parts) > 1 else 0)
            except (ValueError, IndexError):
                scheduled_time = dt_time(9, 0)

            with transaction.atomic():
                sa = ScheduledAutomation.objects.create(
                    board=board,
                    created_by=user,
                    name=name,
                    is_active=True,
                    schedule_type=schedule_type,
                    scheduled_time=scheduled_time,
                    action=action,
                    action_value=collected_data.get('action_value', ''),
                    notify_target=collected_data.get('notify_target', 'board_members'),
                    task_filter=collected_data.get('task_filter', 'all'),
                )

            # Register with Celery Beat
            try:
                from kanban.scheduled_automation_utils import create_periodic_task_for_automation
                create_periodic_task_for_automation(sa)
            except Exception as celery_err:
                logger.warning(
                    'Celery Beat registration failed for scheduled automation %s: %s',
                    sa.id, celery_err,
                )

            logger.info(
                'Spectra created scheduled automation "%s" on board %s for user %s',
                name, board.name, user.username,
            )
            return {
                'success': True,
                'message': (
                    f"✅ **Scheduled automation created!**\n\n"
                    f"⏰ **{sa.name}** will run **{schedule_type}** at "
                    f"**{scheduled_time.strftime('%I:%M %p')}** on **{board.name}**."
                ),
            }

        except Exception as exc:
            logger.exception('Spectra create_scheduled_automation failed: %s', exc)
            return {'success': False, 'error': str(exc)}
