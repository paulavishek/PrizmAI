"""
spectra_tools.py — Gemini Function Calling tool schemas for Spectra actions.

Each tool defines the bare minimum required parameters.  Optional fields
have sensible defaults so Spectra keeps conversations short — users can
fill the rest via the UI later.
"""
import logging

logger = logging.getLogger(__name__)

# Cache built Tool objects so we only construct them once.
_cached_tools = None


def get_action_tools():
    """
    Return a list of ``genai.types.Tool`` objects ready to pass to
    ``GeminiClient.get_function_call_response()``.

    The tools cover all eight Spectra action types.
    """
    global _cached_tools
    if _cached_tools is not None:
        return _cached_tools

    try:
        from google.generativeai.types import FunctionDeclaration, Tool

        # ── 1. Create Task ───────────────────────────────────────────────
        create_task = FunctionDeclaration(
            name='create_task',
            description='Create a new task on a project board.',
            parameters={
                'type': 'object',
                'properties': {
                    'title': {
                        'type': 'string',
                        'description': 'Task title (required).',
                    },
                    'priority': {
                        'type': 'string',
                        'enum': ['low', 'medium', 'high', 'urgent'],
                        'description': 'Task priority. Default: medium.',
                    },
                    'assigned_to': {
                        'type': 'string',
                        'description': 'Full name or username of the assignee.',
                    },
                    'due_date': {
                        'type': 'string',
                        'description': 'Due date in natural language (e.g. "next Friday") or ISO format.',
                    },
                    'description': {
                        'type': 'string',
                        'description': 'Brief task description.',
                    },
                },
                'required': ['title'],
            },
        )

        # ── 2. Create Board ──────────────────────────────────────────────
        create_board = FunctionDeclaration(
            name='create_board',
            description='Create a new project board.',
            parameters={
                'type': 'object',
                'properties': {
                    'name': {
                        'type': 'string',
                        'description': 'Board name (required).',
                    },
                    'description': {
                        'type': 'string',
                        'description': 'Board description.',
                    },
                },
                'required': ['name'],
            },
        )

        # ── 3. Send Message ──────────────────────────────────────────────
        send_message = FunctionDeclaration(
            name='send_message',
            description=(
                'Send a message to a board member in the team chat. '
                'If the user describes the intent rather than typing the exact text, '
                'generate a professional, context-appropriate message as the message_content.'
            ),
            parameters={
                'type': 'object',
                'properties': {
                    'recipient': {
                        'type': 'string',
                        'description': 'Full name or username of the recipient.',
                    },
                    'message_content': {
                        'type': 'string',
                        'description': 'The message text to send.',
                    },
                },
                'required': ['recipient', 'message_content'],
            },
        )

        # ── 4. Log Time ─────────────────────────────────────────────────
        log_time = FunctionDeclaration(
            name='log_time',
            description='Log time spent working on a task.',
            parameters={
                'type': 'object',
                'properties': {
                    'task_name': {
                        'type': 'string',
                        'description': 'Name of the task worked on.',
                    },
                    'hours': {
                        'type': 'number',
                        'description': 'Hours spent (0.25 to 16, in 0.25 increments).',
                    },
                    'work_date': {
                        'type': 'string',
                        'description': 'Date the work was performed (ISO or natural language). Default: today.',
                    },
                    'description': {
                        'type': 'string',
                        'description': 'What was done during this time.',
                    },
                },
                'required': ['task_name', 'hours'],
            },
        )

        # ── 5. Schedule Event ────────────────────────────────────────────
        schedule_event = FunctionDeclaration(
            name='schedule_event',
            description='Schedule a calendar event or meeting.',
            parameters={
                'type': 'object',
                'properties': {
                    'title': {
                        'type': 'string',
                        'description': 'Event title.',
                    },
                    'start_datetime': {
                        'type': 'string',
                        'description': 'Start date and time in natural language or ISO format.',
                    },
                    'end_datetime': {
                        'type': 'string',
                        'description': 'End date and time. Default: 1 hour after start.',
                    },
                    'event_type': {
                        'type': 'string',
                        'enum': ['meeting', 'out_of_office', 'busy_block', 'team_event'],
                        'description': 'Type of event. Default: meeting.',
                    },
                    'participants': {
                        'type': 'array',
                        'items': {'type': 'string'},
                        'description': 'Names or usernames of participants to invite.',
                    },
                    'location': {
                        'type': 'string',
                        'description': 'Meeting location or video link.',
                    },
                    'description': {
                        'type': 'string',
                        'description': 'Event description or agenda.',
                    },
                },
                'required': ['title', 'start_datetime'],
            },
        )

        # ── 6. Create Retrospective ─────────────────────────────────────
        create_retrospective = FunctionDeclaration(
            name='create_retrospective',
            description='Generate an AI-powered sprint/project retrospective.',
            parameters={
                'type': 'object',
                'properties': {
                    'retrospective_type': {
                        'type': 'string',
                        'enum': ['sprint', 'project', 'milestone', 'quarterly'],
                        'description': 'Type of retrospective. Default: sprint.',
                    },
                    'period_start': {
                        'type': 'string',
                        'description': 'Start date of the analysis period (ISO or natural language).',
                    },
                    'period_end': {
                        'type': 'string',
                        'description': 'End date of the analysis period (ISO or natural language).',
                    },
                    'manual_insights': {
                        'type': 'string',
                        'description': 'Optional observations or notes to include.',
                    },
                },
                'required': ['period_start', 'period_end'],
            },
        )

        # ── 7. Create Automation (trigger-based) ────────────────────────
        create_automation = FunctionDeclaration(
            name='create_automation',
            description='Create a trigger-based automation rule for the board.',
            parameters={
                'type': 'object',
                'properties': {
                    'name': {
                        'type': 'string',
                        'description': 'Rule name.',
                    },
                    'trigger_type': {
                        'type': 'string',
                        'enum': [
                            'task_overdue', 'moved_to_column', 'task_created',
                            'task_completed', 'priority_changed', 'task_assigned',
                            'due_date_approaching',
                        ],
                        'description': 'What triggers the rule.',
                    },
                    'trigger_value': {
                        'type': 'string',
                        'description': 'Trigger parameter (column name, priority level, or days before deadline).',
                    },
                    'action_type': {
                        'type': 'string',
                        'enum': [
                            'set_priority', 'add_label', 'send_notification',
                            'move_to_column', 'assign_to_user', 'set_due_date',
                        ],
                        'description': 'What action to perform when triggered.',
                    },
                    'action_value': {
                        'type': 'string',
                        'description': 'Action parameter (priority, label, column name, username, or days).',
                    },
                },
                'required': ['name', 'trigger_type', 'action_type'],
            },
        )

        # ── 8. Create Scheduled Automation ───────────────────────────────
        create_scheduled_automation = FunctionDeclaration(
            name='create_scheduled_automation',
            description='Create a time-based scheduled automation rule.',
            parameters={
                'type': 'object',
                'properties': {
                    'name': {
                        'type': 'string',
                        'description': 'Rule name.',
                    },
                    'schedule_type': {
                        'type': 'string',
                        'enum': ['daily', 'weekly', 'monthly'],
                        'description': 'How often to run the rule.',
                    },
                    'scheduled_time': {
                        'type': 'string',
                        'description': 'Time of day in HH:MM format. Default: 09:00.',
                    },
                    'action': {
                        'type': 'string',
                        'enum': ['send_notification', 'set_priority'],
                        'description': 'Action to perform.',
                    },
                    'notify_target': {
                        'type': 'string',
                        'enum': ['assignee', 'board_members', 'creator'],
                        'description': 'Who to notify (for send_notification). Default: board_members.',
                    },
                    'task_filter': {
                        'type': 'string',
                        'enum': ['all', 'overdue', 'incomplete', 'high_priority'],
                        'description': 'Which tasks to apply to. Default: all.',
                    },
                    'action_value': {
                        'type': 'string',
                        'description': 'For set_priority: the priority level. For send_notification: optional custom message.',
                    },
                },
                'required': ['name', 'schedule_type', 'action'],
            },
        )

        # Bundle all declarations into a single Tool
        _cached_tools = [
            Tool(function_declarations=[
                create_task,
                create_board,
                send_message,
                log_time,
                schedule_event,
                create_retrospective,
                create_automation,
                create_scheduled_automation,
            ])
        ]
        logger.info("Spectra action tool schemas loaded (%d functions)", 8)
        return _cached_tools

    except ImportError:
        logger.error("google-generativeai not installed — tool schemas unavailable")
        return []
    except Exception as e:
        logger.error(f"Failed to build Spectra tool schemas: {e}")
        return []


# ── Mapping from FC function names to pending_action values ──────────────
FUNCTION_TO_ACTION = {
    'create_task': 'create_task',
    'create_board': 'create_board',
    'send_message': 'send_message',
    'log_time': 'log_time',
    'schedule_event': 'schedule_event',
    'create_retrospective': 'create_retrospective',
    'create_automation': 'create_custom_automation',
    'create_scheduled_automation': 'create_scheduled_automation',
}

# ── Mapping from AI router intents to collecting modes ───────────────────
INTENT_TO_MODE = {
    'create_task': 'collecting_task',
    'create_board': 'collecting_board',
    'create_automation': 'collecting_automation',
    'send_message': 'collecting_message',
    'log_time': 'collecting_time_entry',
    'schedule_event': 'collecting_event',
    'create_retrospective': 'collecting_retrospective',
}
