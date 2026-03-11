"""
Custom template tags and filters for conflict detection templates
"""
from django import template
from django.utils.safestring import mark_safe

register = template.Library()

@register.filter
def get_severity_color(conflict):
    """Return Bootstrap color class for conflict severity"""
    colors = {
        'critical': 'danger',
        'high': 'warning',
        'medium': 'info',
        'low': 'secondary'
    }
    return colors.get(conflict.severity, 'secondary')

@register.filter
def resolution_icon(resolution_type):
    """Return FontAwesome icon for resolution type"""
    icons = {
        'reassign': 'user-friends',
        'reschedule': 'calendar-alt',
        'adjust_dates': 'clock',
        'remove_dependency': 'unlink',
        'modify_dependency': 'link',
        'split_task': 'cut',
        'reduce_scope': 'minus-circle',
        'add_resources': 'user-plus',
        'custom': 'cog'
    }
    return icons.get(resolution_type, 'lightbulb')

@register.filter
def div(value, arg):
    """Divide value by arg"""
    try:
        return float(value) / float(arg)
    except (ValueError, ZeroDivisionError):
        return 0

@register.filter
def mul(value, arg):
    """Multiply value by arg"""
    try:
        return float(value) * float(arg)
    except (ValueError, TypeError):
        return 0

@register.filter
def pprint(value):
    """Pretty print JSON/dict data"""
    import json
    if isinstance(value, dict):
        return json.dumps(value, indent=2)
    return str(value)

@register.filter
def filter_board_specific(patterns):
    """Filter patterns that have a board"""
    return [p for p in patterns if p.board is not None]

@register.filter
def filter_global(patterns):
    """Filter patterns that don't have a board (global)"""
    return [p for p in patterns if p.board is None]

@register.filter
def avg_success_rate(patterns):
    """Calculate usage-weighted success rate across patterns.

    Uses a weighted average (sum(times_successful) / sum(times_used)) so that
    low-sample patterns (e.g. a brand-new board-specific pattern with 1 use)
    don't distort the overall figure the same way a simple arithmetic mean
    would. Falls back to a simple mean when no usage data is available.
    """
    if not patterns:
        return 0
    total_used = sum(p.times_used for p in patterns)
    if total_used > 0:
        total_successful = sum(p.times_successful for p in patterns)
        return total_successful / total_used
    # Fallback: simple mean of stored rates
    total = sum(p.success_rate for p in patterns)
    return total / len(patterns)
