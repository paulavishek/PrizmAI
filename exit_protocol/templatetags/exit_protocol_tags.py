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


@register.filter(name='dict_get')
def dict_get(mapping, key):
    """Look up ``mapping[key]`` from a template (dicts can't be indexed by a
    variable key in the Django template language). Tries both the raw key and
    its string form; returns '' when absent."""
    if hasattr(mapping, 'get'):
        if key in mapping:
            return mapping.get(key)
        return mapping.get(str(key), '')
    return ''
