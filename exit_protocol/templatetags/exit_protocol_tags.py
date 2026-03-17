from django import template

register = template.Library()


@register.filter(name='humanize_key')
def humanize_key(value):
    """
    Converts snake_case dictionary keys to readable Title Case labels.
    'risks_materialized' → 'Risks Materialized'
    'milestones_achieved' → 'Milestones Achieved'
    """
    if not isinstance(value, str):
        return value
    return value.replace('_', ' ').title()
