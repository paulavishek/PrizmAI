"""
Custom template tags for demo mode
"""
from django import template

register = template.Library()


@register.filter
def get_item(dictionary, key):
    """
    Get an item from a dictionary using a key
    Usage: {{ my_dict|get_item:key_variable }}
    """
    if dictionary is None:
        return []
    return dictionary.get(key, [])
