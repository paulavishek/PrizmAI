"""
Analytics signals — fire-and-forget hooks that record analytics events
whenever key model saves happen throughout the application.

All database writes are wrapped in try/except so that a bug here can never
break the main application flow.
"""
import logging
from django.db.models.signals import post_save
from django.dispatch import receiver
from django.utils import timezone

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Helper: resolve the current active UserSession for an authenticated user
# ---------------------------------------------------------------------------

def _active_session(user):
    """Return the currently-open UserSession for *user*, or None."""
    try:
        from analytics.models import UserSession
        return UserSession.objects.filter(user=user, session_end__isnull=True).first()
    except Exception:
        return None


def _record_feature(user, feature, category, event_type='repeat_use', metadata=None, session=None):
    """
    Create a FeatureAdoptionEvent.  Automatically determines first_use vs
    repeat_use if *event_type* is not overridden by the caller.
    """
    try:
        from analytics.models import FeatureAdoptionEvent
        if session is None:
            session = _active_session(user)
        already = FeatureAdoptionEvent.objects.filter(user=user, feature=feature).exists()
        resolved_type = 'first_use' if not already else event_type
        FeatureAdoptionEvent.objects.create(
            user=user,
            user_session=session,
            feature=feature,
            feature_category=category,
            event_type=resolved_type,
            workspace_preset=getattr(session, 'workspace_preset', '') if session else '',
            using_byok=getattr(session, 'byok_active', False) if session else False,
            ai_provider=getattr(session, 'ai_provider_used', '') if session else '',
            metadata=metadata or {},
        )
    except Exception:
        logger.exception("FeatureAdoptionEvent creation failed (feature=%s, user=%s)", feature, getattr(user, 'username', '?'))


# ---------------------------------------------------------------------------
# User registration
# ---------------------------------------------------------------------------

@receiver(post_save, sender='auth.User')
def on_user_created(sender, instance, created, **kwargs):
    """Mark the most-recent anonymous→registered session as converted."""
    if not created:
        return
    try:
        from analytics.models import UserSession
        session = UserSession.objects.filter(user=instance, session_end__isnull=True).first()
        if session:
            session.registered_during_session = True
            session.save(update_fields=['registered_during_session'])
    except Exception:
        logger.exception("on_user_created analytics hook failed for user=%s", instance.pk)


# ---------------------------------------------------------------------------
# BYOK key configured / removed
# ---------------------------------------------------------------------------

@receiver(post_save, sender='ai_assistant.UserAISettings')
def on_user_ai_settings_saved(sender, instance, created, **kwargs):
    """Record BYOK configure / remove events when a user saves their AI settings."""
    try:
        from analytics.models import AIQuotaEvent, FeatureAdoptionEvent
        user = instance.user
        session = _active_session(user)

        # Detect whether an encrypted key is present
        has_key = bool(getattr(instance, 'encrypted_api_key', None))
        if has_key:
            AIQuotaEvent.objects.create(
                user=user,
                event_type='byok_configured',
                provider_configured=getattr(instance, 'byok_provider', '') or '',
            )
            _record_feature(user, 'byok_setup', 'integration', session=session,
                            metadata={'provider': getattr(instance, 'byok_provider', '')})
        elif not created:
            # Key was cleared (removal)
            AIQuotaEvent.objects.create(
                user=user,
                event_type='byok_removed',
            )
    except Exception:
        logger.exception("on_user_ai_settings_saved analytics hook failed")


@receiver(post_save, sender='ai_assistant.OrganizationAISettings')
def on_org_ai_settings_saved(sender, instance, created, **kwargs):
    """Record org-level BYOK events."""
    try:
        from analytics.models import AIQuotaEvent
        user = getattr(instance, 'updated_by', None)
        if user is None:
            return
        has_key = bool(getattr(instance, 'encrypted_api_key', None))
        if has_key:
            AIQuotaEvent.objects.create(
                user=user,
                event_type='byok_configured',
                provider_configured=getattr(instance, 'byok_provider', '') or '',
            )
            _record_feature(user, 'byok_setup', 'integration',
                            metadata={'scope': 'org', 'provider': getattr(instance, 'byok_provider', '')})
    except Exception:
        logger.exception("on_org_ai_settings_saved analytics hook failed")


# ---------------------------------------------------------------------------
# Workspace preset changes
# ---------------------------------------------------------------------------

@receiver(post_save, sender='kanban.WorkspacePreset')
def on_workspace_preset_saved(sender, instance, created, **kwargs):
    """Record a WorkspacePresetEvent when the global_preset changes."""
    try:
        from analytics.models import WorkspacePresetEvent
        # On creation there's no "from" tier, so from_preset is blank
        WorkspacePresetEvent.objects.create(
            organization=instance.organization,
            from_preset='' if created else '',   # We can't know the old value after save; use signals' pre_save for that
            to_preset=instance.global_preset,
        )
    except Exception:
        logger.exception("on_workspace_preset_saved analytics hook failed")


# ---------------------------------------------------------------------------
# Enterprise AI feature usage signals
# ---------------------------------------------------------------------------

def _enterprise_feature_signal(model_path, feature_name, category='enterprise_ai'):
    """
    Factory: returns a post_save receiver that fires a FeatureAdoptionEvent
    for the given feature whenever *model_path* is saved.
    """
    @receiver(post_save, sender=model_path, weak=False)
    def _handler(sender, instance, created, **kwargs):
        if not created:
            return
        try:
            user = getattr(instance, 'user', None) or getattr(instance, 'created_by', None)
            if user is None:
                return
            _record_feature(user, feature_name, category)
        except Exception:
            logger.exception("FeatureAdoptionEvent signal failed for %s", feature_name)
    _handler.__name__ = f'on_{feature_name}_created'
    return _handler


# Register enterprise feature hooks
_enterprise_feature_signal('kanban.StressTestSession',    'stress_test')
_enterprise_feature_signal('kanban.ProjectRetrospective', 'ai_retrospective')
_enterprise_feature_signal('kanban.PreMortemAnalysis',    'premortem')
_enterprise_feature_signal('kanban.ScopeAutopsyReport',   'scope_autopsy')
_enterprise_feature_signal('kanban.WhatIfScenario',       'what_if')
_enterprise_feature_signal('kanban.ShadowBranch',         'shadow_board')
_enterprise_feature_signal('exit_protocol.HospiceSession', 'exit_protocol')
_enterprise_feature_signal('kanban.SavedBrief',           'prizm_brief')
_enterprise_feature_signal('kanban.CommitmentProtocol',   'commitments')


# ---------------------------------------------------------------------------
# AI quota threshold events
# ---------------------------------------------------------------------------

@receiver(post_save, sender='api.AIUsageQuota')
def on_ai_quota_saved(sender, instance, created, **kwargs):
    """
    Fire quota_warning at 80 % and quota_exhausted at 100 % of the monthly limit.
    Uses a simple "just crossed the threshold" check to avoid duplicate events.
    """
    try:
        from analytics.models import AIQuotaEvent
        limit = instance.monthly_quota
        if limit <= 0:
            return
        used = instance.requests_used
        pct = (used / limit) * 100

        # Calculate days since first AI use
        days = 0
        first_log = instance.user.ai_request_logs.order_by('timestamp').first() if hasattr(instance.user, 'ai_request_logs') else None
        if first_log and hasattr(first_log, 'timestamp'):
            days = (timezone.now() - first_log.timestamp).days

        if pct >= 100:
            # Only create one exhausted event per "cycle"
            already = AIQuotaEvent.objects.filter(
                user=instance.user,
                event_type='quota_exhausted',
                quota_used=used,
            ).exists()
            if not already:
                AIQuotaEvent.objects.create(
                    user=instance.user,
                    event_type='quota_exhausted',
                    quota_used=used,
                    quota_limit=limit,
                    days_since_first_use=days,
                )
        elif pct >= 80:
            already = AIQuotaEvent.objects.filter(
                user=instance.user,
                event_type='quota_warning',
                quota_used__gte=int(limit * 0.8),
            ).exists()
            if not already:
                AIQuotaEvent.objects.create(
                    user=instance.user,
                    event_type='quota_warning',
                    quota_used=used,
                    quota_limit=limit,
                    days_since_first_use=days,
                )
    except Exception:
        logger.exception("on_ai_quota_saved analytics hook failed")
