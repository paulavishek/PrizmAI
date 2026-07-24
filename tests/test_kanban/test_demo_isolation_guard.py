"""Systemic guard against the recurring demo cross-user data-bleed bug class.

Demo is ONE shared org + ONE shared workspace; per-user isolation comes either
from being BOARD-scoped (cloned by _duplicate_board) or from carrying a
``sandbox_owner`` FK (cloned per user, like Wiki / Discovery / Custom Fields).

A model that is scoped only by ``workspace`` or ``organization`` — with no
``board`` FK and no ``sandbox_owner`` field — bleeds across every demo user
through the shared demo workspace. That exact class of bug has recurred for
Wiki, Discovery, Calendar, Time Tracking, and Custom Fields.

This test fails when a NEW such model ships, forcing the author to either
board-scope it, add a ``sandbox_owner`` clone, or (if it is genuinely-shared
read-only scaffolding, or never demo-seeded) add it to ``ALLOWLIST`` with a
reason. It is deliberately conservative: it only flags models that actually
carry a workspace/organization FK, so it can't fail spuriously on unrelated
models.
"""
import pytest
from django.apps import apps


# Models that carry a workspace/organization FK but are intentionally NOT
# per-user isolated. Each entry MUST have a reason. Keep this list short — a new
# entry is a deliberate decision, not a rubber stamp.
ALLOWLIST = {
    # (app_label, model_name): "why it doesn't bleed"
    # ── Genuinely-shared read-only demo scaffolding ──
    'kanban.Mission': 'Shared read-only demo hierarchy; demo users never edit it.',
    'kanban.Strategy': 'Shared read-only demo hierarchy; demo users never edit it.',
    'kanban.OrganizationGoal': 'Shared read-only demo hierarchy; demo users never edit it.',
    'kanban.Workspace': 'The tenant boundary itself, not tenant content.',
    'kanban.WorkspacePreset': 'Per-workspace feature level; demo workspace is uniform.',
    # ── Per-user by construction (exactly one row per user; the workspace/org
    #    FK is that user's own, so it cannot bleed to another user) ──
    'decision_center.DecisionCenterBriefing': 'Per-user (user FK) + is_demo flag; not workspace-shared.',
    'accounts.UserProfile': 'Exactly one per user; the org/workspace FKs are that user\'s own.',
    'kanban.UserPerformanceProfile': 'Per-user profile (user FK); not demo-seeded, not shared.',
    # ── Not demo-seeded (audited empty on the demo workspace) — guard only ──
    'kanban.OrganizationLearningProfile': 'Coach workspace aggregate; never demo-seeded (0 rows).',
    'kanban.AIExperimentResult': 'Coach experiment log; never demo-seeded (0 rows).',
    'integrations.SourceConnection': 'External-tool tokens; never demo-seeded (0 rows on demo ws).',
    'kanban.CustomFieldOption': 'Child of CustomFieldDefinition (isolated via its parent + FK cascade).',
    'analytics.WorkspacePresetEvent': 'Org-scoped telemetry (append-only), not tenant content.',
    'ai_assistant.OrganizationAISettings': 'Org AI config; not demo-seeded (0 rows).',
    'kanban.ResourceLevelingSuggestion': 'Not demo-seeded (0 rows); would be board-derived if ever seeded.',
    'wiki.WikiMeetingAnalysis': 'Child of WikiPage (which is sandbox_owner-isolated); not demo-seeded (0 rows).',
    'wiki.WikiDocumentationAnalysis': 'Child of WikiPage (which is sandbox_owner-isolated); not demo-seeded (0 rows).',
    # ── Membership / invitation infrastructure (not tenant content) ──
    'kanban.WorkspaceMembership': 'Membership infra (who belongs to a workspace), user-keyed; not demo-seeded.',
    'kanban.WorkspaceInvitation': 'Invitation infra, not tenant content; not demo-seeded.',
    'accounts.OrganizationInvitation': 'Invitation infra, not tenant content; not demo-seeded (0 rows).',
}

# Apps whose models participate in the demo dataset. Third-party/admin apps are
# out of scope. Keep this aligned with the feature apps in INSTALLED_APPS.
DEMO_APPS = {
    'kanban', 'accounts', 'ai_assistant', 'api', 'analytics', 'messaging',
    'wiki', 'webhooks', 'integrations', 'knowledge_graph', 'decision_center',
    'exit_protocol', 'requirements',
}


def _field_names(model):
    return {f.name for f in model._meta.get_fields()}


def _has_fk_to(model, target_model_name):
    for f in model._meta.get_fields():
        if getattr(f, 'many_to_one', False) or getattr(f, 'one_to_one', False):
            related = getattr(f, 'related_model', None)
            if related is not None and related.__name__ == target_model_name:
                return True
    return False


@pytest.mark.django_db
def test_no_unisolated_workspace_or_org_scoped_demo_models():
    offenders = []
    for model in apps.get_models():
        app_label = model._meta.app_label
        if app_label not in DEMO_APPS:
            continue
        key = f'{app_label}.{model.__name__}'
        if key in ALLOWLIST:
            continue

        fields = _field_names(model)
        is_ws_or_org_scoped = (
            _has_fk_to(model, 'Workspace') or _has_fk_to(model, 'Organization')
        )
        if not is_ws_or_org_scoped:
            continue

        # Safe if board-scoped (cloned by _duplicate_board) OR carries a
        # per-user sandbox_owner clone. NB: a bare User FK is NOT enough to be
        # safe — DiscoveryIdea has submitted_by yet still bleeds without
        # sandbox_owner (the FK is the author, not an access boundary) — so
        # genuinely per-user models (one row PER user, e.g. profiles) are
        # allow-listed explicitly with a reason rather than auto-skipped.
        board_scoped = _has_fk_to(model, 'Board') or 'board' in fields
        per_user_cloned = 'sandbox_owner' in fields
        if board_scoped or per_user_cloned:
            continue

        offenders.append(key)

    assert not offenders, (
        'These workspace/organization-scoped models have neither a board FK nor '
        'a sandbox_owner clone, so they will BLEED across demo users through the '
        'shared demo workspace. Fix by board-scoping, adding a sandbox_owner '
        'clone (see kanban.sandbox_views._clone_custom_fields_for_user), or — if '
        'genuinely shared/never-demo-seeded — add to ALLOWLIST with a reason: '
        + ', '.join(sorted(offenders))
    )
