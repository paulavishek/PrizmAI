"""
Deterministic color-coded user avatars — single source of truth for
rendering a user as a colored-initials circle (or profile photo) across
board cards, member-management lists, and the workspace topbar.
"""
from django import template

register = template.Library()

AVATAR_COLOR_COUNT = 8


def avatar_color_index(user_id):
    """Stable palette index for a user, hashed on the DB primary key so it
    never changes if the user renames themselves (unlike a username hash)."""
    return user_id % AVATAR_COLOR_COUNT


def user_initials(user):
    first = (user.first_name or '').strip()
    last = (user.last_name or '').strip()
    if first and last:
        return (first[0] + last[0]).upper()
    if first:
        return first[:2].upper()
    username = user.username or ''
    return (username[:2] or '?').upper()


@register.inclusion_tag('kanban/partials/_user_avatar.html')
def user_avatar(user, size='md'):
    photo_url = ''
    profile = getattr(user, 'profile', None)
    if profile and profile.profile_picture:
        photo_url = profile.profile_picture.url
    return {
        'user': user,
        'photo_url': photo_url,
        'initials': user_initials(user),
        'color_class': f'prizm-avatar--c{avatar_color_index(user.id)}',
        'size_class': f'prizm-avatar--{size}' if size != 'md' else '',
    }


@register.inclusion_tag('kanban/partials/_avatar_stack.html')
def avatar_stack(users, max_avatars=4, size='sm'):
    users = list(users)
    shown = users[:max_avatars]
    overflow = len(users) - len(shown)
    return {'shown': shown, 'overflow': overflow, 'size': size}


@register.filter
def extract_users(memberships):
    """BoardMembership/WorkspaceMembership list -> User list, for avatar_stack."""
    return [m.user for m in memberships]
