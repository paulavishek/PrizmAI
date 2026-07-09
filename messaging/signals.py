import logging

from django.db.models.signals import post_delete
from django.dispatch import receiver

from .models import ChatRoom, Notification

logger = logging.getLogger(__name__)


@receiver(post_delete, sender=ChatRoom)
def delete_notifications_for_deleted_room(sender, instance, **kwargs):
    """
    CHAT_ROOM_INVITE notifications point at their room via the plain-string
    action_url field, not a FK, so they aren't cascade-deleted when the room
    is removed — whether directly (delete_chat_room) or via a board
    delete/demo-reset cascade. Left behind, they send *every* recipient
    (including other users/personas who were invited) to a 404. Sweep them
    here so the fix covers every deletion path, not just the one the
    deleting user's own notifications get purged from.
    """
    try:
        Notification.objects.filter(
            action_url=f'/messaging/room/{instance.id}/',
        ).delete()
    except Exception:
        logger.warning(
            'delete_notifications_for_deleted_room: cleanup failed for room %s',
            instance.id, exc_info=True,
        )
