"""
SpectraActionService — executes database writes for Conversational Spectra.

This service is completely separate from the AI / Gemini logic.
Every database write is wrapped in try / except and returns a structured dict.
"""
import logging
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
            task.save()

            # Record activity
            TaskActivity.objects.create(
                task=task,
                user=user,
                activity_type='created',
                description=f"Created task '{task.title}' via Spectra",
            )

            # Audit trail
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

            # Audit trail
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
