import json
from django import template
from django.utils import timezone
from django.utils.safestring import mark_safe
from datetime import datetime

register = template.Library()


@register.filter
def to_json(value):
    """Serialize a Python object to a compact JSON string safe for HTML attributes."""
    return json.dumps(value)


@register.filter
def humanize_slug(value):
    """
    Convert a slug/underscore string to human-readable Title Case.
    Handles both valid model choices and raw AI-generated values.

    Usage: {{ action.action_type|humanize_slug }}
    Examples:
        'process_improvement' → 'Process Improvement'
        'team_building'       → 'Team Building'
        'Process Change'      → 'Process Change'  (already human-readable, untouched)
    """
    try:
        return str(value).replace('_', ' ').title()
    except (AttributeError, TypeError):
        return value


@register.filter
def as_percentage(value):
    """
    Convert a decimal fraction (0–1) to a display percentage integer.

    Usage: {{ retrospective.ai_confidence_score|as_percentage }}
    Example: 0.63 → 63
    """
    try:
        return int(float(value) * 100)
    except (ValueError, TypeError):
        return 0


@register.filter
def percentage(value, arg):
    """
    Calculate percentage of value/arg
    
    Usage: {{ value|percentage:total }}
    """
    try:
        value = float(value)
        arg = float(arg)
        if arg == 0:
            return 0
        return int((value / arg) * 100)
    except (ValueError, ZeroDivisionError):
        return 0

@register.filter
def divide(value, arg):
    """
    Divide the value by the argument
    
    Usage: {{ value|divide:divisor }}
    """
    try:
        value = float(value)
        arg = float(arg)
        if arg == 0:
            return 0
        return value / arg
    except (ValueError, ZeroDivisionError):
        return 0

@register.filter
def mul(value, arg):
    """
    Multiply the value by the argument
    
    Usage: {{ value|mul:multiplier }}
    """
    try:
        value = float(value)
        arg = float(arg)
        return value * arg
    except (ValueError, TypeError):
        return 0

@register.filter
def div(value, arg):
    """
    Divide the value by the argument and return integer
    
    Usage: {{ value|div:divisor }}
    """
    try:
        value = float(value)
        arg = float(arg)
        if arg == 0:
            return 0
        return int(value / arg)
    except (ValueError, ZeroDivisionError):
        return 0

@register.filter
def timesince_days(value):
    """
    Calculate the number of days since a given date
    
    Usage: {{ task.due_date|timesince_days }}
    """
    try:
        if value is None:
            return 0
        
        if isinstance(value, datetime):
            due_date = value.date()
        else:
            due_date = value
            
        today = timezone.now().date()
        delta = today - due_date
        return delta.days
    except (AttributeError, TypeError):
        return 0

@register.filter
def replace(value, args):
    """
    Replace a substring in the value
    
    Usage: {{ value|replace:"old,new" }}
    """
    try:
        old, new = args.split(',')
        return value.replace(old, new)
    except (ValueError, AttributeError):
        return value

@register.simple_tag
def assign_value(value):
    """
    Assign a value to a variable in the template
    
    Usage: {% assign_value "some_value" as my_var %}
    """
    return value

@register.filter
def get_item(dictionary, key):
    """
    Get an item from a dictionary by key
    
    Usage: {{ my_dict|get_item:key }}
    """
    if dictionary is None:
        return None
    try:
        return dictionary.get(key)
    except (AttributeError, TypeError):
        return None

@register.filter
def make_range(value):
    """
    Return a range object from 0 to value-1 to allow {% for i in value|make_range %}
    
    Usage: {% for i in num_phases|make_range %}
    """
    try:
        return range(int(value))
    except (ValueError, TypeError):
        return range(0)


@register.filter
def wip_age_days(value):
    """
    Return the number of days since a task entered its current column.
    Used for WIP age badges on the Kanban board.

    Usage: {{ task.column_entered_at|wip_age_days }}
    """
    try:
        if value is None:
            return 0
        now = timezone.now()
        if hasattr(value, 'tzinfo') and value.tzinfo is None:
            # Naive datetime – make it aware
            import pytz
            value = pytz.utc.localize(value)
        delta = now - value
        return max(0, delta.days)
    except (AttributeError, TypeError):
        return 0


@register.filter(is_safe=True)
def format_coach_action(action_text):
    """
    Parse a coach action string that uses ' • ' as a sub-label separator and
    return structured HTML.

    Input format:
        "Do something • Rationale: why it helps • Expected outcome: measurable result • How to: practical hint"

    Output: An HTML block with the main action bold and each sub-label on its
    own line as a bold label followed by its value.

    Usage: {{ action|format_coach_action }}
    """
    from django.utils.html import escape, mark_safe
    if not action_text:
        return mark_safe('')

    parts = [p.strip() for p in str(action_text).split(' • ')]
    if not parts:
        return mark_safe(escape(action_text))

    # Known sub-labels (case-insensitive prefix match)
    sub_labels = ('rationale:', 'expected outcome:', 'how to:', 'implementation hint:')

    html_parts = []
    for i, part in enumerate(parts):
        lower = part.lower()
        is_sub = any(lower.startswith(lbl) for lbl in sub_labels)
        if i == 0 and not is_sub:
            # Main action text
            html_parts.append('<strong>' + escape(part) + '</strong>')
        else:
            # Sub-label: split at first ':' to bold just the label
            colon_idx = part.find(':')
            if colon_idx != -1:
                label = escape(part[:colon_idx + 1])
                content = escape(part[colon_idx + 1:].strip())
                html_parts.append('<span><strong>' + label + '</strong> ' + content + '</span>')
            else:
                html_parts.append('<span>' + escape(part) + '</span>')

    return mark_safe('<br>'.join(html_parts))


@register.simple_tag
def board_immunity_badge(board):
    """
    Render a small immunity score badge for a board card.
    Returns empty string if no stress test session exists.

    Usage: {% board_immunity_badge board %}
    """
    try:
        from kanban.stress_test_models import ImmunityScore
        score_obj = (
            ImmunityScore.objects
            .filter(session__board=board)
            .order_by('-session__created_at')
            .first()
        )
        if not score_obj:
            return ''
        colour = score_obj.get_band_colour()
        band = score_obj.get_band()
        score = score_obj.overall
        return mark_safe(
            f'<span class="badge ms-2" style="background-color:{colour};color:#fff;" '
            f'title="Immunity: {band}">'
            f'<i class="fas fa-shield-alt me-1"></i>{score}'
            f'</span>'
        )
    except Exception:
        return ''