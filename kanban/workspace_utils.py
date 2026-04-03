"""
Workspace resolution utilities.

Provides ``get_or_create_real_workspace(user)`` which guarantees a real
(non-demo) Workspace exists for the user's organization.  This is called
by the WorkspaceMiddleware (lazy creation) and explicitly by onboarding_skip,
board creation, goal creation, etc.
"""
import logging

logger = logging.getLogger(__name__)


def get_or_create_real_workspace(user):
    """Return the user's default real workspace, creating one if necessary.

    Logic:
    1. If the user has no profile or no organization → return None.
    2. If a real (non-demo) workspace already exists for the org → return it.
    3. Otherwise create one named "{first_name}'s Workspace" and set it as
       the user's ``active_workspace``.

    Returns a Workspace instance or None.
    """
    from accounts.models import UserProfile
    from kanban.models import Workspace

    try:
        profile = user.profile
    except (UserProfile.DoesNotExist, AttributeError):
        return None

    org = profile.organization
    if not org:
        return None

    # Look for an existing real workspace
    real_ws = Workspace.objects.filter(
        organization=org,
        is_demo=False,
        is_active=True,
    ).order_by('-created_at').first()

    if real_ws:
        return real_ws

    # None found — create one
    first_name = (user.first_name or user.username).strip()
    ws = Workspace.objects.create(
        name=f"{first_name}'s Workspace",
        organization=org,
        created_by=user,
        is_demo=False,
    )
    logger.info(
        "Auto-created real Workspace #%s '%s' for user %s (org #%s)",
        ws.pk, ws.name, user.username, org.pk,
    )

    # Point the profile at it (only if not already on a real workspace)
    if not profile.active_workspace or profile.active_workspace.is_demo:
        profile.active_workspace = ws
        profile.is_viewing_demo = False
        profile.save(update_fields=['active_workspace', 'is_viewing_demo'])

    return ws
