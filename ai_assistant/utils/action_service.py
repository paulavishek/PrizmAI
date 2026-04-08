"""
SpectraActionService — executes database writes for Conversational Spectra.

This service is completely separate from the AI / Gemini logic.
Every database write is wrapped in try / except and returns a structured dict.
"""
import logging
import re
from django.contrib.auth import get_user_model
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
        """Return True if *user* has any access (including viewer) to *board*."""
        from ai_assistant.utils.rbac_utils import can_spectra_read_board
        return can_spectra_read_board(user, board)

    @staticmethod
    def _user_can_modify_board(user, board):
        """Return True if *user* can create/edit/delete content on *board* (not viewer)."""
        from ai_assistant.utils.rbac_utils import can_spectra_write_board
        return can_spectra_write_board(user, board)

    @staticmethod
    def _user_can_manage_board(user, board):
        """Return True if *user* has owner-level access on *board*."""
        from ai_assistant.utils.rbac_utils import can_spectra_manage_board
        return can_spectra_manage_board(user, board)

    @staticmethod
    def _viewer_denial_message(board):
        """Standard denial message for viewer-role users attempting writes."""
        return (
            f"You have **viewer** access on **{board.name}**, which is read-only. "
            "I can answer questions about this board, but I can't create, edit, or "
            "delete content on your behalf. Please ask a board owner to upgrade your role."
        )

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
        candidates = list(get_user_model().objects.filter(board_memberships__board=board))
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
            # Permission check — must be member or owner to create tasks
            if not self._user_can_modify_board(user, board):
                if self._user_has_board_access(user, board):
                    return {
                        'success': False,
                        'error': self._viewer_denial_message(board),
                    }
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

    def create_board(self, user, collected_data, is_demo_mode=False):
        """
        Create a Board with default columns and add *user* as owner.

        Expected keys: ``name`` (required), ``description`` (str | None).
        When *is_demo_mode* is True the board is tagged so it appears in the
        Demo Workspace and not in the user's personal workspace.

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
                # Resolve workspace
                ws = None
                if hasattr(user, 'profile') and user.profile:
                    ws = user.profile.active_workspace
                    if ws and ws.is_demo and not is_demo_mode:
                        ws = None  # Don't put real boards into demo workspace
                    if not ws and not is_demo_mode:
                        from kanban.workspace_utils import get_or_create_real_workspace
                        ws = get_or_create_real_workspace(user)

                board = Board(
                    name=collected_data['name'],
                    description=collected_data.get('description', '') or '',
                    organization=organization,
                    created_by=user,
                    workspace=ws,
                )
                # Tag the board so it shows up in demo workspace (and is
                # excluded from the personal workspace).
                if is_demo_mode:
                    board.created_by_session = f'spectra_demo_{user.id}'
                board.save()
                board.owner = user
                board.save(update_fields=['owner'])

                # Create RBAC membership for the creator as Owner
                from kanban.models import BoardMembership
                BoardMembership.objects.get_or_create(
                    board=board, user=user,
                    defaults={'role': 'owner', 'added_by': user}
                )

                # Create 3 default columns (matching existing board creation behaviour)
                default_columns = ['To Do', 'In Progress', 'Done']
                for i, col_name in enumerate(default_columns):
                    Column.objects.create(name=col_name, board=board, position=i)

                # Auto-add workspace members to the new board
                from kanban.workspace_member_utils import auto_add_workspace_members_to_board
                auto_add_workspace_members_to_board(board)

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
        Activate one of the preset automation templates.

        Uses the new AutomationTemplate + AutomationRule models.
        Falls back to legacy BoardAutomation for backward compat.

        Returns ``{'success': True, 'automation': <AutomationRule>}``
        or ``{'success': False, 'error': str}``.
        """
        from kanban.automation_models import AutomationRule, AutomationTemplate

        try:
            if not self._user_can_manage_board(user, board):
                if self._user_has_board_access(user, board):
                    from ai_assistant.utils.rbac_utils import get_user_board_role
                    role = get_user_board_role(user, board)
                    return {
                        'success': False,
                        'error': (
                            f"Managing automations on **{board.name}** requires **owner** access. "
                            f"You're currently a **{role}**."
                        ),
                    }
                return {'success': False, 'error': "You don't have access to this board."}

            # Map number → template by ID order
            templates = list(AutomationTemplate.objects.filter(is_builtin=True).order_by('id'))
            if not templates:
                return {'success': False, 'error': 'No automation templates available.'}

            idx = template_number - 1
            if idx < 0 or idx >= len(templates):
                return {
                    'success': False,
                    'error': f'Unknown template number {template_number}. Choose 1-{len(templates)}.',
                }

            tpl = templates[idx]

            automation, created = AutomationRule.objects.get_or_create(
                board=board,
                name=tpl.name,
                defaults=dict(
                    trigger_type=tpl.trigger_type,
                    action_type='send_notification',
                    action_value='',
                    rule_definition=tpl.rule_definition,
                    is_active=True,
                    created_by=user,
                ),
            )

            if not created:
                if not automation.is_active:
                    automation.is_active = True
                    automation.save(update_fields=['is_active'])
                    logger.info(
                        'Spectra re-activated automation "%s" on board #%s for user %s',
                        tpl.name, board.id, user.username,
                    )
                    return {'success': True, 'automation': automation}
                return {
                    'success': False,
                    'error': f'The automation "{tpl.name}" is already active on this board.',
                }

            logger.info(
                'Spectra activated automation "%s" on board #%s for user %s',
                tpl.name, board.id, user.username,
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
            if not self._user_can_modify_board(user, board):
                if self._user_has_board_access(user, board):
                    return {'success': False, 'error': self._viewer_denial_message(board)}
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
            if not self._user_can_modify_board(user, board):
                if self._user_has_board_access(user, board):
                    return {'success': False, 'error': self._viewer_denial_message(board)}
                return {'success': False, 'error': "You don't have access to this board."}

            # Resolve task by name using fuzzy matching
            task_name = collected_data.get('task_name', '')
            board_tasks = list(Task.objects.filter(
                column__board=board, is_archived=False,
            ).select_related('column'))

            matched = self._fuzzy_match_task(task_name, board_tasks)
            if isinstance(matched, list):
                return {
                    'success': False,
                    'disambiguation_needed': True,
                    'candidates': [{'id': t.id, 'title': t.title} for t in matched],
                }
            if matched is None:
                all_titles = [t.title for t in board_tasks[:5]]
                hint = ''
                if all_titles:
                    hint = '\n\nTasks on this board: ' + ', '.join(
                        f'**{t}**' for t in all_titles
                    )
                return {
                    'success': False,
                    'error': f'Could not find a task matching "{task_name}" on this board.{hint}',
                }
            task = matched

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
            if not self._user_can_modify_board(user, board):
                if self._user_has_board_access(user, board):
                    return {'success': False, 'error': self._viewer_denial_message(board)}
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
        from kanban.automation_models import AutomationRule

        try:
            if not self._user_can_manage_board(user, board):
                if self._user_has_board_access(user, board):
                    from ai_assistant.utils.rbac_utils import get_user_board_role
                    role = get_user_board_role(user, board)
                    return {
                        'success': False,
                        'error': (
                            f"Managing automations on **{board.name}** requires **owner** access. "
                            f"You're currently a **{role}**."
                        ),
                    }
                return {'success': False, 'error': "You don't have access to this board."}

            name = collected_data.get('name', 'Untitled Automation')
            trigger_type = collected_data.get('trigger_type', '')
            action_type = collected_data.get('action_type', '')

            if not trigger_type or not action_type:
                return {'success': False, 'error': 'Trigger type and action type are required.'}

            with transaction.atomic():
                automation = AutomationRule.objects.create(
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
            if not self._user_can_manage_board(user, board):
                if self._user_has_board_access(user, board):
                    from ai_assistant.utils.rbac_utils import get_user_board_role
                    role = get_user_board_role(user, board)
                    return {
                        'success': False,
                        'error': (
                            f"Managing automations on **{board.name}** requires **owner** access. "
                            f"You're currently a **{role}**."
                        ),
                    }
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

    # ------------------------------------------------------------------
    # Update task
    # ------------------------------------------------------------------

    def update_task(self, user, board, collected_data):
        """
        Update an existing task's field (status, priority, assignee, due date, title).

        Expected keys: ``task_name``, ``field``, ``new_value``.
        """
        from kanban.models import Task, Column

        try:
            if not self._user_can_modify_board(user, board):
                if self._user_has_board_access(user, board):
                    return {'success': False, 'error': self._viewer_denial_message(board)}
                return {'success': False, 'error': 'You don\'t have access to this board.'}

            task_name = collected_data.get('task_name', '').strip()
            field = collected_data.get('field', '').strip().lower()
            new_value = collected_data.get('new_value', '').strip()

            if not task_name:
                return {'success': False, 'error': 'No task name provided.'}

            # Resolve the task
            tasks = list(Task.objects.filter(
                column__board=board, is_archived=False,
            ).select_related('column', 'assigned_to'))

            matched = self._fuzzy_match_task(task_name, tasks)
            if isinstance(matched, list):
                # Multiple matches — trigger disambiguation
                return {
                    'success': False,
                    'disambiguation_needed': True,
                    'candidates': [{'id': t.id, 'title': t.title} for t in matched],
                }
            if matched is None:
                return {'success': False, 'error': f'No task matching "{task_name}" found on this board.'}

            task = matched

            # Apply the update based on field
            if field == 'status':
                # "done", "complete" → move to last column; otherwise match column name
                val_lower = new_value.lower()
                if val_lower in ('done', 'complete', 'completed', 'finished'):
                    target_col = Column.objects.filter(board=board).order_by('-position').first()
                else:
                    target_col = Column.objects.filter(
                        board=board, name__icontains=new_value,
                    ).first()
                if not target_col:
                    return {'success': False, 'error': f'No column matching "{new_value}" found.'}
                old_col = task.column.name
                task.column = target_col
                task.position = Task.objects.filter(column=target_col).count()
                task.save(update_fields=['column', 'position', 'updated_at'])
                # Proactive insight: remaining open tasks
                insight = ''
                if val_lower in ('done', 'complete', 'completed', 'finished'):
                    remaining = Task.objects.filter(
                        column__board=board, is_archived=False,
                    ).exclude(column=target_col).count()
                    if remaining > 0:
                        insight = f"\n\n💡 **{remaining} tasks** remaining on this board."
                    else:
                        insight = "\n\n🎉 **All tasks on this board are done!**"
                return {
                    'success': True,
                    'message': (
                        f"✅ **Task updated!**\n\n"
                        f"📋 **{task.title}** moved from **{old_col}** → **{target_col.name}**.{insight}"
                    ),
                }

            elif field == 'priority':
                valid = {'low', 'medium', 'high', 'urgent'}
                if new_value.lower() not in valid:
                    return {'success': False, 'error': f'Invalid priority "{new_value}". Choose: low, medium, high, urgent.'}
                old_priority = task.priority
                task.priority = new_value.lower()
                task.save(update_fields=['priority', 'updated_at'])
                return {
                    'success': True,
                    'message': (
                        f"✅ **Priority updated!**\n\n"
                        f"📋 **{task.title}**: {old_priority} → **{task.priority}**."
                    ),
                }

            elif field == 'assignee':
                assignee, display = self._resolve_assignee(new_value, board)
                if not assignee:
                    return {'success': False, 'error': f'No member matching "{new_value}" found on this board.'}
                task.assigned_to = assignee
                task.save(update_fields=['assigned_to', 'updated_at'])
                return {
                    'success': True,
                    'message': (
                        f"✅ **Assignee updated!**\n\n"
                        f"📋 **{task.title}** is now assigned to **{display}**."
                    ),
                }

            elif field == 'due_date':
                from ai_assistant.utils.conversation_flow import _parse_date
                parsed = _parse_date(new_value)
                if not parsed:
                    return {'success': False, 'error': f'Could not parse date "{new_value}".'}
                task.due_date = parsed
                task.save(update_fields=['due_date', 'updated_at'])
                return {
                    'success': True,
                    'message': (
                        f"✅ **Due date updated!**\n\n"
                        f"📋 **{task.title}** due date set to **{parsed.strftime('%A, %B %d, %Y')}**."
                    ),
                }

            elif field == 'title':
                old_title = task.title
                task.title = new_value
                task.save(update_fields=['title', 'updated_at'])
                return {
                    'success': True,
                    'message': (
                        f"✅ **Task renamed!**\n\n"
                        f"📋 **{old_title}** → **{new_value}**."
                    ),
                }

            elif field == 'description':
                task.description = new_value
                task.save(update_fields=['description', 'updated_at'])
                return {
                    'success': True,
                    'message': (
                        f"✅ **Description updated!**\n\n"
                        f"📋 **{task.title}** description has been updated."
                    ),
                }

            else:
                return {'success': False, 'error': f'Unknown field "{field}". Supported: status, priority, assignee, due_date, title, description.'}

        except Exception as exc:
            logger.exception('Spectra update_task failed: %s', exc)
            return {'success': False, 'error': str(exc)}

    def _fuzzy_match_task(self, query, tasks):
        """
        Match a task by name. Returns a single Task if unambiguous,
        a list of Tasks if multiple match, or None if no match.
        """
        query_lower = query.lower()

        # Exact match
        exact = [t for t in tasks if t.title.lower() == query_lower]
        if len(exact) == 1:
            return exact[0]

        # Prefix match
        prefix = [t for t in tasks if t.title.lower().startswith(query_lower)]
        if len(prefix) == 1:
            return prefix[0]

        # Substring match
        substr = [t for t in tasks if query_lower in t.title.lower()]
        if len(substr) == 1:
            return substr[0]
        if len(substr) > 1 and len(substr) <= 5:
            return substr  # disambiguation

        # Word overlap scoring
        query_words = set(query_lower.split())
        scored = []
        for t in tasks:
            title_words = set(t.title.lower().split())
            if not query_words:
                continue
            overlap = len(query_words & title_words) / len(query_words)
            if overlap >= 0.5:
                scored.append((overlap, t))
        scored.sort(key=lambda x: -x[0])
        if scored:
            if len(scored) == 1 or (len(scored) > 1 and scored[0][0] > scored[1][0]):
                return scored[0][1]
            top = [s[1] for s in scored if s[0] == scored[0][0]]
            if len(top) <= 5:
                return top

        return None

    # ── Living Commitment Protocols ──────────────────────────────────────────

    def get_commitment_status(self, user, board, collected_data):
        """
        Return the current confidence and status of a commitment protocol.
        collected_data keys: board_id, commitment_id
        """
        from kanban.commitment_models import CommitmentProtocol

        try:
            if not self._user_has_board_access(user, board):
                return {'success': False, 'error': "You don't have access to this board."}

            commitment_id = collected_data.get('commitment_id')
            if not commitment_id:
                return {'success': False, 'error': 'commitment_id is required.'}

            try:
                protocol = CommitmentProtocol.objects.select_related('owner').get(
                    pk=commitment_id, board=board
                )
            except CommitmentProtocol.DoesNotExist:
                return {'success': False, 'error': f'Commitment #{commitment_id} not found on this board.'}

            days_left = protocol.days_until_deadline

            message = (
                f"📊 **{protocol.title}**\n\n"
                f"- **Status:** {protocol.get_status_display()}\n"
                f"- **Confidence:** {protocol.current_confidence:.0f}%\n"
                f"- **Decay model:** {protocol.get_decay_model_display()}\n"
                f"- **Owner:** {protocol.owner.get_full_name() or protocol.owner.username}\n"
            )
            if days_left is not None:
                message += f"- **Days to deadline:** {days_left}\n"
            if protocol.ai_reasoning:
                message += f"\n💡 *AI reasoning:* {protocol.ai_reasoning[:200]}…"

            return {'success': True, 'message': message}

        except Exception as exc:
            logger.exception('Spectra get_commitment_status failed: %s', exc)
            return {'success': False, 'error': str(exc)}

    def list_at_risk_commitments(self, user, board, collected_data):
        """
        List all at-risk or critical commitment protocols on a board.
        collected_data keys: board_id
        """
        from kanban.commitment_models import CommitmentProtocol

        try:
            if not self._user_has_board_access(user, board):
                return {'success': False, 'error': "You don't have access to this board."}

            protocols = CommitmentProtocol.objects.filter(
                board=board,
                status__in=['at_risk', 'critical'],
            ).order_by('current_confidence')

            if not protocols.exists():
                return {
                    'success': True,
                    'message': f"✅ No at-risk or critical commitment protocols on **{board.name}**.",
                }

            lines = [f"⚠️ **At-risk commitments on {board.name}:**\n"]
            for p in protocols:
                icon = "🔴" if p.status == 'critical' else "🟡"
                deadline = p.target_date.strftime('%b %d, %Y') if p.target_date else 'no deadline'
                lines.append(
                    f"{icon} **{p.title}** — {p.current_confidence:.0f}% confidence "
                    f"({p.get_status_display()}, due {deadline})"
                )

            return {'success': True, 'message': '\n'.join(lines)}

        except Exception as exc:
            logger.exception('Spectra list_at_risk_commitments failed: %s', exc)
            return {'success': False, 'error': str(exc)}

    def place_commitment_bet(self, user, board, collected_data):
        """
        Place or update a prediction market bet for the current user.
        collected_data keys: board_id, commitment_id, predicted_confidence, tokens_wagered
        """
        from kanban.commitment_models import CommitmentProtocol, CommitmentBet, UserCredibilityScore

        try:
            if not self._user_can_modify_board(user, board):
                if self._user_has_board_access(user, board):
                    return {'success': False, 'error': self._viewer_denial_message(board)}
                return {'success': False, 'error': "You don't have access to this board."}

            commitment_id = collected_data.get('commitment_id')
            predicted = collected_data.get('predicted_confidence')
            tokens = int(collected_data.get('tokens_wagered', 1))

            if not commitment_id or predicted is None:
                return {'success': False, 'error': 'commitment_id and predicted_confidence are required.'}

            try:
                protocol = CommitmentProtocol.objects.get(pk=commitment_id, board=board)
            except CommitmentProtocol.DoesNotExist:
                return {'success': False, 'error': f'Commitment #{commitment_id} not found on this board.'}

            credibility, _ = UserCredibilityScore.objects.get_or_create(
                user=user,
                defaults={'tokens_remaining': 100},
            )
            existing = CommitmentBet.objects.filter(protocol=protocol, bettor=user).first()
            tokens_needed = max(0, tokens - (existing.tokens_wagered if existing else 0))
            if tokens_needed > credibility.tokens_remaining:
                return {
                    'success': False,
                    'error': (
                        f"Not enough tokens. You have {credibility.tokens_remaining} remaining "
                        f"but need {tokens_needed} more."
                    ),
                }

            with transaction.atomic():
                if existing:
                    existing.confidence_estimate = predicted / 100.0
                    existing.tokens_wagered = tokens
                    existing.save(update_fields=['confidence_estimate', 'tokens_wagered'])
                else:
                    CommitmentBet.objects.create(
                        protocol=protocol,
                        bettor=user,
                        confidence_estimate=predicted / 100.0,
                        tokens_wagered=tokens,
                    )
                credibility.tokens_remaining = max(0, credibility.tokens_remaining - tokens_needed)
                credibility.save(update_fields=['tokens_remaining'])

            action = "updated" if existing else "placed"
            return {
                'success': True,
                'message': (
                    f"🎯 **Bet {action}!**\n\n"
                    f"You predicted **{predicted:.0f}%** confidence on **{protocol.title}**, "
                    f"wagering **{tokens}** token{'s' if tokens != 1 else ''}.\n"
                    f"Tokens remaining: **{credibility.tokens_remaining}**."
                ),
            }

        except Exception as exc:
            logger.exception('Spectra place_commitment_bet failed: %s', exc)
            return {'success': False, 'error': str(exc)}

