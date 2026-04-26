"""
Communication Context Provider — messages, notifications.

NEW provider — messaging data was previously invisible to Spectra.
"""

import logging
from datetime import timedelta

from django.utils import timezone

from .base import BaseContextProvider
from . import registry

logger = logging.getLogger(__name__)


class CommunicationContextProvider(BaseContextProvider):
    PROVIDER_NAME = 'Communication'
    FEATURE_TAGS = [
        'message', 'messages', 'notification', 'notifications',
        'chat', 'inbox', 'unread', 'mentioned', 'mention',
        'alert', 'alerts', 'communication',
    ]

    def _get_summary_impl(self, board, user, is_demo_mode=False):
        try:
            from messaging.models import Notification
        except ImportError:
            return ''

        unread = Notification.objects.filter(
            recipient=user, is_read=False
        ).count()

        recent_cutoff = timezone.now() - timedelta(days=7)
        recent = Notification.objects.filter(
            recipient=user, created_at__gte=recent_cutoff
        ).count()

        if unread == 0 and recent == 0:
            return '💬 **Notifications:** All caught up.\n'

        return (
            f'💬 **Notifications:** {unread} unread, '
            f'{recent} in last 7 days.\n'
        )

    def _get_detail_impl(self, board, user, query='', is_demo_mode=False):
        try:
            from messaging.models import Notification
        except ImportError:
            return ''

        # Unread notifications
        unread = Notification.objects.filter(
            recipient=user, is_read=False
        ).select_related('sender').order_by('-created_at')[:15]

        ctx = '**💬 Notifications:**\n'

        if unread.exists():
            ctx += f'\n**Unread ({unread.count()}):**\n'
            for n in unread:
                sender = n.sender.get_full_name() or n.sender.username if n.sender else 'System'
                ctx += f'  • [{n.notification_type}] from {sender}: {n.text[:100]}\n'
                if n.created_at:
                    ctx += f'    {n.created_at.strftime("%b %d, %I:%M %p")}\n'

        # Recent read notifications
        recent_cutoff = timezone.now() - timedelta(days=7)
        recent_read = Notification.objects.filter(
            recipient=user,
            is_read=True,
            created_at__gte=recent_cutoff,
        ).select_related('sender').order_by('-created_at')[:10]

        if recent_read.exists():
            ctx += f'\n**Recent Read ({recent_read.count()}):**\n'
            for n in recent_read:
                sender = n.sender.get_full_name() or n.sender.username if n.sender else 'System'
                ctx += f'  • [{n.notification_type}] from {sender}: {n.text[:80]}\n'

        # Board-specific messages if board is set
        if board:
            try:
                from messaging.models import ChatMessage, ChatRoom
                rooms = ChatRoom.objects.filter(board=board)
                recent_msgs = ChatMessage.objects.filter(
                    chat_room__in=rooms
                ).select_related('author').order_by('-created_at')[:10]

                if recent_msgs.exists():
                    ctx += f'\n**Recent Board Messages ({board.name}):**\n'
                    for msg in recent_msgs:
                        author = msg.author.get_full_name() or msg.author.username
                        ctx += f'  • {author}: {msg.content[:100]}\n'
            except (ImportError, Exception):
                pass

        return ctx


registry.register(CommunicationContextProvider())
