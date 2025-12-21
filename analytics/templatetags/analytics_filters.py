"""
Custom template filters for analytics.
"""
from django import template
import hashlib

register = template.Library()


@register.filter(name='hash')
def hash_value(value, algorithm='md5'):
    """
    Hash a value using specified algorithm.
    Usage: {{ user.id|stringformat:"s"|hash:"md5" }}
    """
    if value is None:
        return ''
    
    # Convert to string if not already
    value_str = str(value)
    
    # Hash based on algorithm
    if algorithm == 'md5':
        return hashlib.md5(value_str.encode()).hexdigest()
    elif algorithm == 'sha256':
        return hashlib.sha256(value_str.encode()).hexdigest()
    elif algorithm == 'sha1':
        return hashlib.sha1(value_str.encode()).hexdigest()
    else:
        return hashlib.md5(value_str.encode()).hexdigest()


@register.filter(name='md5')
def md5_hash(value):
    """
    Shorthand for MD5 hashing.
    Usage: {{ user.id|md5 }}
    """
    if value is None:
        return ''
    return hashlib.md5(str(value).encode()).hexdigest()


@register.filter
def multiply(value, arg):
    """Multiply value by arg"""
    try:
        return float(value) * float(arg)
    except (ValueError, TypeError):
        return 0


@register.filter
def divide(value, arg):
    """Divide value by arg"""
    try:
        if float(arg) == 0:
            return 0
        return float(value) / float(arg)
    except (ValueError, TypeError):
        return 0


@register.filter
def replace(value, args):
    """Replace old with new in string"""
    try:
        old, new = args.split(',')
        return str(value).replace(old, new)
    except (ValueError, AttributeError):
        return value
