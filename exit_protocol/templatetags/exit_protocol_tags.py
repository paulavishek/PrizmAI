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


@register.filter(name='usd')
def usd(value):
    """Format a numeric budget as ``$1,234,567`` (no decimals, thousands
    separators). Returns 'N/A' for blank/None. The demo cemetery snapshots are
    USD; this keeps the autopsy's money figures readable instead of ``75000.00``."""
    if value is None or value == '':
        return 'N/A'
    try:
        return '${:,.0f}'.format(float(value))
    except (TypeError, ValueError):
        return value


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
