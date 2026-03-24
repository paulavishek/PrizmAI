"""
API views for the "My Favorites" feature.
Handles toggling favorites and reordering them in the sidebar.
"""
import json
import logging

from django.contrib.auth.decorators import login_required
from django.contrib.contenttypes.models import ContentType
from django.db.models import Q, Max
from django.http import JsonResponse
from django.views.decorators.http import require_POST

from kanban.models import UserFavorite

logger = logging.getLogger(__name__)


def is_user_favorite(user, favorite_type, object_id):
    """Check if an object is favorited by the user. Importable helper."""
    if not user.is_authenticated:
        return False
    app_label, model_name = ALLOWED_FAVORITE_TYPES.get(favorite_type, (None, None))
    if not app_label:
        return False
    try:
        ct = ContentType.objects.get(app_label=app_label, model=model_name)
        return UserFavorite.objects.filter(
            user=user, content_type=ct, object_id=object_id
        ).exists()
    except ContentType.DoesNotExist:
        return False

# Allowed content-type mappings: favorite_type -> (app_label, model_name)
ALLOWED_FAVORITE_TYPES = {
    'board': ('kanban', 'board'),
    'goal': ('kanban', 'organizationgoal'),
    'mission': ('kanban', 'mission'),
    'wiki_page': ('wiki', 'wikipage'),
    'task': ('kanban', 'task'),
    'retrospective': ('kanban', 'projectretrospective'),
    'chat_room': ('messaging', 'chatroom'),
    'conflict': ('kanban', 'conflictdetection'),
    'shadow_branch': ('kanban', 'shadowbranch'),
    'automation': ('kanban', 'automationrule'),
}

# Fields to look up for display_name per model
DISPLAY_NAME_FIELDS = {
    'board': 'name',
    'goal': 'title',
    'mission': 'title',
    'wiki_page': 'title',
    'task': 'title',
    'retrospective': 'title',
    'chat_room': 'name',
    'conflict': 'title',
    'shadow_branch': 'name',
    'automation': 'name',
}


def _user_can_access(user, favorite_type, obj):
    """Check that user has legitimate access to the object."""
    if favorite_type == 'board':
        return obj.created_by == user or obj.memberships.filter(user=user).exists() or obj.is_official_demo_board
    elif favorite_type in ('goal', 'mission'):
        return True  # Goals/Missions are visible to all authenticated users
    elif favorite_type == 'wiki_page':
        return True  # Wiki pages are shared within workspace
    elif favorite_type == 'task':
        board = obj.column.board
        return board.created_by == user or board.memberships.filter(user=user).exists() or board.is_official_demo_board
    elif favorite_type == 'retrospective':
        board = obj.board
        return board.created_by == user or board.memberships.filter(user=user).exists() or board.is_official_demo_board
    elif favorite_type == 'chat_room':
        return obj.members.filter(pk=user.pk).exists()
    elif favorite_type == 'conflict':
        board = obj.board
        return board.created_by == user or board.memberships.filter(user=user).exists() or board.is_official_demo_board
    elif favorite_type == 'shadow_branch':
        board = obj.board
        return board.created_by == user or board.memberships.filter(user=user).exists() or board.is_official_demo_board
    elif favorite_type == 'automation':
        board = obj.board
        return board.created_by == user or board.memberships.filter(user=user).exists() or board.is_official_demo_board
    return False


@login_required
@require_POST
def toggle_favorite(request):
    """Toggle a favorite on/off for the current user.

    POST body (JSON): { "favorite_type": "board", "object_id": 123 }
    Returns: { "is_favorited": true/false, "favorite_id": int|null }
    """
    try:
        data = json.loads(request.body)
    except (json.JSONDecodeError, ValueError):
        return JsonResponse({'error': 'Invalid JSON'}, status=400)

    favorite_type = data.get('favorite_type', '').strip()
    object_id = data.get('object_id')

    if favorite_type not in ALLOWED_FAVORITE_TYPES:
        return JsonResponse({'error': 'Invalid favorite_type'}, status=400)

    if not object_id or not str(object_id).isdigit():
        return JsonResponse({'error': 'Invalid object_id'}, status=400)

    object_id = int(object_id)
    app_label, model_name = ALLOWED_FAVORITE_TYPES[favorite_type]

    try:
        ct = ContentType.objects.get(app_label=app_label, model=model_name)
    except ContentType.DoesNotExist:
        return JsonResponse({'error': 'Content type not found'}, status=400)

    # Get the actual object
    model_class = ct.model_class()
    try:
        obj = model_class.objects.get(pk=object_id)
    except model_class.DoesNotExist:
        return JsonResponse({'error': 'Object not found'}, status=404)

    # Check access
    if not _user_can_access(request.user, favorite_type, obj):
        return JsonResponse({'error': 'Access denied'}, status=403)

    # Toggle
    existing = UserFavorite.objects.filter(
        user=request.user, content_type=ct, object_id=object_id
    ).first()

    if existing:
        existing.delete()
        return JsonResponse({'is_favorited': False, 'favorite_id': None})
    else:
        # Get display name
        name_field = DISPLAY_NAME_FIELDS.get(favorite_type, 'name')
        display_name = getattr(obj, name_field, str(obj))[:200]

        # Set position to end
        max_pos = UserFavorite.objects.filter(
            user=request.user
        ).aggregate(Max('position'))['position__max'] or 0

        fav = UserFavorite.objects.create(
            user=request.user,
            content_type=ct,
            object_id=object_id,
            favorite_type=favorite_type,
            display_name=display_name,
            position=max_pos + 1,
        )
        return JsonResponse({
            'is_favorited': True,
            'favorite_id': fav.pk,
        })


@login_required
@require_POST
def reorder_favorites(request):
    """Reorder the user's favorites.

    POST body (JSON): { "order": [id1, id2, id3, ...] }
    Returns: { "success": true }
    """
    try:
        data = json.loads(request.body)
    except (json.JSONDecodeError, ValueError):
        return JsonResponse({'error': 'Invalid JSON'}, status=400)

    order = data.get('order', [])
    if not isinstance(order, list):
        return JsonResponse({'error': 'order must be a list'}, status=400)

    # Validate all IDs belong to the current user
    user_fav_ids = set(
        UserFavorite.objects.filter(user=request.user).values_list('id', flat=True)
    )

    for i, fav_id in enumerate(order):
        if not isinstance(fav_id, int) or fav_id not in user_fav_ids:
            continue
        UserFavorite.objects.filter(
            pk=fav_id, user=request.user
        ).update(position=i)

    return JsonResponse({'success': True})


@login_required
def favorites_list_api(request):
    """Return current user's favorites as JSON for sidebar refresh."""
    favorites = (
        UserFavorite.objects
        .filter(user=request.user)
        .select_related('content_type')
        .order_by('position', '-created_at')[:20]
    )
    items = []
    for fav in favorites:
        items.append({
            'id': fav.pk,
            'favorite_type': fav.favorite_type,
            'display_name': fav.display_name,
            'icon_class': fav.get_icon_class(),
            'url': fav.get_absolute_url(),
        })
    return JsonResponse({'favorites': items})
