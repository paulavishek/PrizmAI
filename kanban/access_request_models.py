"""
Spectra Smart Access Request System

When a user hits a board/task permission wall, Spectra intercepts
with a contextual message and can send an automated access request
to the board Owner on the user's behalf.

Owner receives an in-app notification, approves/denies, and the user
is notified of the outcome.
"""
from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone


class AccessRequest(models.Model):
    """
    Tracks access requests initiated by Spectra when a user
    encounters a board or task they don't have access to.
    """
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('approved', 'Approved'),
        ('denied', 'Denied'),
        ('cancelled', 'Cancelled'),
        ('expired', 'Expired'),
    ]

    TRIGGER_CHOICES = [
        ('board_view', 'Board View Denied'),
        ('task_search', 'Task Search — Parent Board Inaccessible'),
        ('task_view', 'Task View Denied'),
        ('spectra_chat', 'Spectra Chat Query'),
    ]

    REQUESTED_ROLE_CHOICES = [
        ('viewer', 'Viewer'),
        ('member', 'Member'),
    ]

    # Who is requesting
    requester = models.ForeignKey(
        User, on_delete=models.CASCADE,
        related_name='access_requests_sent',
        help_text="The user requesting access.",
    )

    # Which board
    board = models.ForeignKey(
        'Board', on_delete=models.CASCADE,
        related_name='access_requests',
        help_text="The board being requested.",
    )

    # Who should approve (the board owner)
    owner = models.ForeignKey(
        User, on_delete=models.CASCADE,
        related_name='access_requests_received',
        help_text="The board owner who reviews this request.",
    )

    # Request metadata
    status = models.CharField(
        max_length=12, choices=STATUS_CHOICES, default='pending',
        db_index=True,
    )
    trigger = models.CharField(
        max_length=20, choices=TRIGGER_CHOICES, default='board_view',
        help_text="What action triggered the access denial.",
    )
    requested_role = models.CharField(
        max_length=10, choices=REQUESTED_ROLE_CHOICES, default='member',
        help_text="The role the requester is asking for.",
    )
    message = models.TextField(
        blank=True, default='',
        help_text="Optional message from the requester to the owner.",
    )
    spectra_context = models.TextField(
        blank=True, default='',
        help_text="Context Spectra captured when the denial occurred.",
    )

    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    resolved_at = models.DateTimeField(null=True, blank=True)
    resolved_by = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='access_requests_resolved',
    )
    reviewer_message = models.TextField(
        blank=True, default='',
        help_text="Optional message from the reviewer on approval/denial.",
    )

    # Prevent spam — only one pending request per user per board
    class Meta:
        ordering = ['-created_at']
        constraints = [
            models.UniqueConstraint(
                fields=['requester', 'board'],
                condition=models.Q(status='pending'),
                name='unique_pending_access_request',
            ),
        ]
        indexes = [
            models.Index(fields=['requester', 'status']),
            models.Index(fields=['owner', 'status']),
            models.Index(fields=['board', 'status']),
        ]

    def __str__(self):
        return (
            f"{self.requester.username} → {self.board.name} "
            f"({self.get_status_display()})"
        )

    def approve(self, reviewer, role=None, message=''):
        """
        Approve the request: create BoardMembership and notify the requester.
        """
        from kanban.models import BoardMembership

        final_role = role or self.requested_role or 'member'

        # Create the membership (idempotent)
        BoardMembership.objects.get_or_create(
            board=self.board,
            user=self.requester,
            defaults={
                'role': final_role,
                'added_by': reviewer,
            },
        )

        self.status = 'approved'
        self.resolved_at = timezone.now()
        self.resolved_by = reviewer
        self.reviewer_message = message
        self.save()

        # Send notification to requester
        self._notify_requester(approved=True)

    def deny(self, reviewer, message=''):
        """Deny the request and notify the requester."""
        self.status = 'denied'
        self.resolved_at = timezone.now()
        self.resolved_by = reviewer
        self.reviewer_message = message
        self.save()

        self._notify_requester(approved=False)

    def cancel(self):
        """Cancel the request (by the requester)."""
        self.status = 'cancelled'
        self.resolved_at = timezone.now()
        self.save()

    def _notify_requester(self, approved):
        """Create an in-app notification for the requester about the outcome."""
        from messaging.models import Notification

        if approved:
            text = (
                f"Your access request to the '{self.board.name}' board "
                f"has been approved by {self.resolved_by.get_full_name() or self.resolved_by.username}. "
                f"You now have {self.requested_role} access."
            )
        else:
            text = (
                f"Your access request to the '{self.board.name}' board "
                f"was declined by {self.resolved_by.get_full_name() or self.resolved_by.username}."
            )
            if self.reviewer_message:
                text += f" Reason: {self.reviewer_message}"

        Notification.objects.create(
            recipient=self.requester,
            sender=self.resolved_by,
            notification_type='ACCESS_RESPONSE',
            text=text,
            action_url=f'/board/{self.board.id}/' if approved else '',
        )

    @classmethod
    def has_pending(cls, user, board):
        """Check if user already has a pending request for this board."""
        return cls.objects.filter(
            requester=user, board=board, status='pending'
        ).exists()

    @classmethod
    def create_and_notify_owner(cls, requester, board, trigger='board_view',
                                 message='', spectra_context='',
                                 requested_role='member'):
        """
        Create an access request and send an in-app notification
        to the board owner.
        """
        from messaging.models import Notification
        from kanban.models import BoardMembership

        # Find the board owner (BoardMembership with role='owner', or created_by)
        owner_membership = BoardMembership.objects.filter(
            board=board, role='owner'
        ).select_related('user').first()

        owner = owner_membership.user if owner_membership else board.created_by

        if not owner or owner == requester:
            return None

        # Check for existing pending request
        if cls.has_pending(requester, board):
            return cls.objects.filter(
                requester=requester, board=board, status='pending'
            ).first()

        access_request = cls.objects.create(
            requester=requester,
            board=board,
            owner=owner,
            trigger=trigger,
            requested_role=requested_role,
            message=message,
            spectra_context=spectra_context,
        )

        # Notify the board owner
        requester_name = requester.get_full_name() or requester.username
        Notification.objects.create(
            recipient=owner,
            sender=requester,
            notification_type='ACCESS_REQUEST',
            text=(
                f"{requester_name} is requesting {requested_role} access "
                f"to your '{board.name}' board."
            ),
            action_url=f'/access-requests/{access_request.id}/review/',
        )

        return access_request
