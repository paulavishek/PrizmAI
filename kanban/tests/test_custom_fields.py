"""
Custom Fields — v1 tests.

Covers:
  • Model basics (typed values, list options, soft-delete).
  • The 3 review-flagged guardrails:
      (1) N+1 prevention via prefetch_related — fetch_task_dict on a board with
          many tasks must stay at a small constant number of queries.
      (2) Scope Autopsy signal guard — only writes with `updated_by` set
          create TaskActivity events. Bulk/system writes are silent.
      (3) Retrospective min-5 threshold — buckets with fewer than 5 tasks
          are silently dropped from the breakdown.
  • AI injection — serialize_for_ai honors `exclude_from_ai`, and
    fetch_task_dict's output contains the custom_fields key.
  • RBAC — non-org-admins can't reach the admin list view.
"""

import datetime as dt
from decimal import Decimal

from django.contrib.auth.models import Group, User
from django.test import TestCase, Client
from django.urls import reverse
from django.utils import timezone

from accounts.models import Organization, UserProfile
from kanban.custom_field_models import (
    CustomFieldDefinition,
    CustomFieldOption,
    TaskCustomFieldValue,
    FIELD_TYPE_BOOLEAN,
    FIELD_TYPE_LIST,
    FIELD_TYPE_NUMBER,
    FIELD_TYPE_TEXT,
)
from kanban.custom_field_serializers import (
    serialize_for_ai,
    serialize_task_custom_fields,
    save_custom_field_values_from_post,
)
from kanban.models import Board, Column, Task, TaskActivity, Workspace


def _make_user(username, *, org=None, admin=False):
    user = User.objects.create_user(username=username, password='pw')
    profile, _ = UserProfile.objects.get_or_create(user=user)
    if org:
        profile.organization = org
        profile.save()
    if admin:
        admin_group, _ = Group.objects.get_or_create(name='OrgAdmin')
        user.groups.add(admin_group)
    return user


def _make_board_with_tasks(org, workspace_name='Default', task_count=0):
    workspace = Workspace.objects.create(
        name=workspace_name,
        organization=org,
        created_by=org.created_by,
    )
    board = Board.objects.create(
        name='Board',
        workspace=workspace,
        created_by=org.created_by,
        owner=org.created_by,
    )
    col = Column.objects.create(board=board, name='To Do', position=0)
    tasks = [
        Task.objects.create(
            title=f'Task {i}', column=col, position=i,
            created_by=org.created_by,
        )
        for i in range(task_count)
    ]
    return workspace, board, col, tasks


# ────────────────────────────────────────────────────────────────────────


class CustomFieldModelTests(TestCase):
    def setUp(self):
        self.creator = _make_user('creator')
        self.org = Organization.objects.create(name='Acme', created_by=self.creator)
        self.creator.profile.organization = self.org
        self.creator.profile.save()
        self.workspace, self.board, self.column, _ = _make_board_with_tasks(self.org)

    def test_list_field_with_options_resolves_default(self):
        fdef = CustomFieldDefinition.objects.create(
            workspace=self.workspace, name='City', field_type=FIELD_TYPE_LIST,
        )
        CustomFieldOption.objects.create(field=fdef, value='Berlin', is_default=True)
        CustomFieldOption.objects.create(field=fdef, value='London')
        self.assertEqual(fdef.resolved_default(), 'Berlin')

    def test_number_field_stores_decimal_value(self):
        fdef = CustomFieldDefinition.objects.create(
            workspace=self.workspace, name='Contract Value', field_type=FIELD_TYPE_NUMBER,
        )
        task = Task.objects.create(
            title='T', column=self.column, position=0, created_by=self.creator,
        )
        TaskCustomFieldValue.objects.create(
            task=task, field=fdef, value_number=Decimal('1500.50'),
            updated_by=self.creator,
        )
        row = TaskCustomFieldValue.objects.get(task=task, field=fdef)
        self.assertEqual(row.resolved_value(), Decimal('1500.50'))

    def test_uniq_active_field_name_per_workspace(self):
        CustomFieldDefinition.objects.create(
            workspace=self.workspace, name='Phase', field_type=FIELD_TYPE_TEXT,
        )
        with self.assertRaises(Exception):
            CustomFieldDefinition.objects.create(
                workspace=self.workspace, name='Phase', field_type=FIELD_TYPE_TEXT,
            )

    def test_soft_delete_frees_name_for_reuse(self):
        f1 = CustomFieldDefinition.objects.create(
            workspace=self.workspace, name='Phase', field_type=FIELD_TYPE_TEXT,
        )
        f1.is_active = False
        f1.save()
        # Same name should now be reusable.
        CustomFieldDefinition.objects.create(
            workspace=self.workspace, name='Phase', field_type=FIELD_TYPE_TEXT,
        )


# ────────────────────────────────────────────────────────────────────────
# Guardrail 1 — N+1 prevention via prefetch_related
# ────────────────────────────────────────────────────────────────────────


class FetchTaskDictPrefetchTests(TestCase):
    def setUp(self):
        self.creator = _make_user('creator')
        self.org = Organization.objects.create(name='Acme', created_by=self.creator)
        self.creator.profile.organization = self.org
        self.creator.profile.save()
        self.workspace, self.board, self.column, self.tasks = _make_board_with_tasks(
            self.org, task_count=10,
        )
        # Create two custom fields and set values on every task so the
        # prefetched relationships are non-empty.
        self.text_field = CustomFieldDefinition.objects.create(
            workspace=self.workspace, name='Phase', field_type=FIELD_TYPE_TEXT,
        )
        self.list_field = CustomFieldDefinition.objects.create(
            workspace=self.workspace, name='Region', field_type=FIELD_TYPE_LIST,
        )
        self.opt_apac = CustomFieldOption.objects.create(field=self.list_field, value='APAC')
        for t in self.tasks:
            TaskCustomFieldValue.objects.create(
                task=t, field=self.text_field, value_text='Phase 1',
                updated_by=self.creator,
            )
            row = TaskCustomFieldValue.objects.create(
                task=t, field=self.list_field, updated_by=self.creator,
            )
            row.selected_options.add(self.opt_apac)

    def test_serialize_for_ai_uses_prefetch_and_stays_constant(self):
        """serialize_for_ai must not issue extra queries per task — its inputs
        are guaranteed by prefetch_related on the calling queryset.

        With the documented prefetch ('custom_field_values__field',
        'custom_field_values__selected_options'), iterating N tasks and
        calling serialize_for_ai on each costs ZERO queries beyond the
        original fetch + prefetch. Without the prefetch it would be 3N+.
        """
        from kanban.custom_field_serializers import serialize_for_ai
        from django.db import connection
        from django.test.utils import CaptureQueriesContext

        def _run(n_tasks):
            tasks_qs = (
                Task.objects
                .filter(column__board=self.board)[:n_tasks]
                .select_related('column__board')
                .prefetch_related(
                    'custom_field_values__field',
                    'custom_field_values__selected_options',
                )
            )
            with CaptureQueriesContext(connection) as ctx:
                tasks = list(tasks_qs)
                for t in tasks:
                    _ = serialize_for_ai(t)
            return len(ctx.captured_queries)

        baseline_queries = _run(5)

        # Add 20 more tasks with values, then run with 25.
        for i in range(20):
            t = Task.objects.create(
                title=f'Extra {i}', column=self.column, position=100 + i,
                created_by=self.creator,
            )
            TaskCustomFieldValue.objects.create(
                task=t, field=self.text_field, value_text='Phase 1',
                updated_by=self.creator,
            )
            row = TaskCustomFieldValue.objects.create(
                task=t, field=self.list_field, updated_by=self.creator,
            )
            row.selected_options.add(self.opt_apac)

        scaled_queries = _run(25)

        # With proper prefetch, both numbers should be the same small constant
        # (1 query for tasks + 1 for values + 1 for fields + 1 for options).
        # Without prefetch, scaled_queries would be ~3x higher.
        self.assertLessEqual(
            scaled_queries, baseline_queries + 1,
            f"N+1 detected: serialize_for_ai used {baseline_queries} queries "
            f"on 5 tasks vs {scaled_queries} on 25. Verify prefetch_related "
            f"on custom_field_values__field and custom_field_values__selected_options.",
        )


# ────────────────────────────────────────────────────────────────────────
# Guardrail 2 — Signal `updated_by` guard
# ────────────────────────────────────────────────────────────────────────


class ScopeAutopsySignalGuardTests(TestCase):
    """The custom_field_signals module records a TaskActivity row only when
    a real authenticated user touched the value. System/bulk writes leave
    updated_by=None and must be silently ignored."""

    def setUp(self):
        self.user = _make_user('alice')
        self.org = Organization.objects.create(name='Acme', created_by=self.user)
        self.user.profile.organization = self.org
        self.user.profile.save()
        self.workspace, self.board, self.column, [self.task] = _make_board_with_tasks(
            self.org, task_count=1,
        )
        self.fdef = CustomFieldDefinition.objects.create(
            workspace=self.workspace, name='Phase', field_type=FIELD_TYPE_TEXT,
        )

    def test_real_user_change_records_activity(self):
        starting = TaskActivity.objects.filter(activity_type='custom_field').count()
        TaskCustomFieldValue.objects.create(
            task=self.task, field=self.fdef, value_text='Phase 1',
            updated_by=self.user,
        )
        self.assertEqual(
            TaskActivity.objects.filter(activity_type='custom_field').count(),
            starting + 1,
        )

    def test_system_write_with_no_updated_by_is_silent(self):
        """Bulk imports / data migrations leave updated_by=None and must not
        pollute the autopsy timeline."""
        starting = TaskActivity.objects.filter(activity_type='custom_field').count()
        TaskCustomFieldValue.objects.create(
            task=self.task, field=self.fdef, value_text='Phase 1',
            updated_by=None,  # ← the guard condition
        )
        self.assertEqual(
            TaskActivity.objects.filter(activity_type='custom_field').count(),
            starting,
            "Signal should NOT record an activity when updated_by is None.",
        )


# ────────────────────────────────────────────────────────────────────────
# Guardrail 3 — Retrospective min-5 threshold
# ────────────────────────────────────────────────────────────────────────


class RetrospectiveMinSampleTests(TestCase):
    """Buckets with fewer than 5 tasks must be silently dropped."""

    def setUp(self):
        self.user = _make_user('user')
        self.org = Organization.objects.create(name='Acme', created_by=self.user)
        self.user.profile.organization = self.org
        self.user.profile.save()
        self.workspace, self.board, self.column, _ = _make_board_with_tasks(self.org)
        self.fdef = CustomFieldDefinition.objects.create(
            workspace=self.workspace, name='External', field_type=FIELD_TYPE_BOOLEAN,
        )

    def _make_tasks(self, n, value_boolean):
        out = []
        for i in range(n):
            t = Task.objects.create(
                title=f'T{i}', column=self.column, position=i,
                created_by=self.user,
            )
            TaskCustomFieldValue.objects.create(
                task=t, field=self.fdef, value_boolean=value_boolean,
                updated_by=self.user,
            )
            out.append(t)
        return out

    def test_below_threshold_bucket_is_dropped(self):
        from kanban.utils.retrospective_generator import RetrospectiveGenerator
        # 6 with Yes (above threshold), 3 with No (below).
        self._make_tasks(6, True)
        self._make_tasks(3, False)

        gen = RetrospectiveGenerator(
            self.board,
            period_start=timezone.now().date() - dt.timedelta(days=30),
            period_end=timezone.now().date() + dt.timedelta(days=1),
        )
        metrics = gen.collect_metrics()
        breakdowns = metrics.get('custom_field_breakdowns', [])

        # Should contain the Yes bucket only — No had n=3 < 5.
        labels = {(b['field'], b['value']) for b in breakdowns}
        self.assertIn(('External', 'Yes'), labels)
        self.assertNotIn(('External', 'No'), labels)

    def test_above_threshold_buckets_both_surface(self):
        from kanban.utils.retrospective_generator import RetrospectiveGenerator
        self._make_tasks(5, True)
        self._make_tasks(5, False)
        gen = RetrospectiveGenerator(
            self.board,
            period_start=timezone.now().date() - dt.timedelta(days=30),
            period_end=timezone.now().date() + dt.timedelta(days=1),
        )
        metrics = gen.collect_metrics()
        labels = {(b['field'], b['value']) for b in metrics.get('custom_field_breakdowns', [])}
        self.assertEqual(labels, {('External', 'Yes'), ('External', 'No')})


# ────────────────────────────────────────────────────────────────────────
# AI injection
# ────────────────────────────────────────────────────────────────────────


class AISerializerTests(TestCase):
    def setUp(self):
        self.user = _make_user('user')
        self.org = Organization.objects.create(name='Acme', created_by=self.user)
        self.user.profile.organization = self.org
        self.user.profile.save()
        self.workspace, self.board, self.column, _ = _make_board_with_tasks(self.org)
        self.public_field = CustomFieldDefinition.objects.create(
            workspace=self.workspace, name='Phase', field_type=FIELD_TYPE_TEXT,
        )
        self.secret_field = CustomFieldDefinition.objects.create(
            workspace=self.workspace, name='Budget',
            field_type=FIELD_TYPE_NUMBER, exclude_from_ai=True,
        )
        self.task = Task.objects.create(
            title='T', column=self.column, position=0, created_by=self.user,
        )
        TaskCustomFieldValue.objects.create(
            task=self.task, field=self.public_field, value_text='Phase 2',
            updated_by=self.user,
        )
        TaskCustomFieldValue.objects.create(
            task=self.task, field=self.secret_field, value_number=Decimal('100000'),
            updated_by=self.user,
        )

    def test_serialize_for_ai_omits_excluded_fields(self):
        # Prefetch as fetch_task_dict callers must.
        task = Task.objects.prefetch_related(
            'custom_field_values__field',
            'custom_field_values__selected_options',
        ).select_related('column__board').get(pk=self.task.pk)
        ai_dict = serialize_for_ai(task)
        self.assertIn('Phase', ai_dict)
        self.assertEqual(ai_dict['Phase'], 'Phase 2')
        self.assertNotIn('Budget', ai_dict, "exclude_from_ai field must not appear in AI dict")

    def test_fetch_task_dict_contains_custom_fields_key(self):
        from ai_assistant.utils.spectra_data_fetchers import fetch_task_dict
        task = Task.objects.prefetch_related(
            'custom_field_values__field',
            'custom_field_values__selected_options',
        ).select_related('column__board', 'assigned_to').get(pk=self.task.pk)
        d = fetch_task_dict(task)
        self.assertIn('custom_fields', d)
        self.assertEqual(d['custom_fields'].get('Phase'), 'Phase 2')
        self.assertNotIn('Budget', d['custom_fields'])


# ────────────────────────────────────────────────────────────────────────
# Upsert helper (form integration)
# ────────────────────────────────────────────────────────────────────────


class UpsertHelperTests(TestCase):
    def setUp(self):
        self.user = _make_user('user')
        self.org = Organization.objects.create(name='Acme', created_by=self.user)
        self.user.profile.organization = self.org
        self.user.profile.save()
        self.workspace, self.board, self.column, _ = _make_board_with_tasks(self.org)
        self.task = Task.objects.create(
            title='T', column=self.column, position=0, created_by=self.user,
        )

    def test_required_field_blank_raises(self):
        from django.core.exceptions import ValidationError
        fdef = CustomFieldDefinition.objects.create(
            workspace=self.workspace, name='Region', field_type=FIELD_TYPE_TEXT,
            is_required=True,
        )
        with self.assertRaises(ValidationError):
            save_custom_field_values_from_post(self.task, {f'custom_field_{fdef.id}': ''}, self.user)

    def test_text_upsert_stamps_updated_by(self):
        fdef = CustomFieldDefinition.objects.create(
            workspace=self.workspace, name='Region', field_type=FIELD_TYPE_TEXT,
        )
        save_custom_field_values_from_post(
            self.task, {f'custom_field_{fdef.id}': 'APAC'}, self.user,
        )
        row = TaskCustomFieldValue.objects.get(task=self.task, field=fdef)
        self.assertEqual(row.value_text, 'APAC')
        self.assertEqual(row.updated_by, self.user)


# ────────────────────────────────────────────────────────────────────────
# RBAC — admin views require Org Admin
# ────────────────────────────────────────────────────────────────────────


class RBACTests(TestCase):
    def setUp(self):
        self.org_admin = _make_user('admin', admin=True)
        self.org = Organization.objects.create(name='Acme', created_by=self.org_admin)
        self.org_admin.profile.organization = self.org
        self.org_admin.profile.save()
        self.workspace, _, _, _ = _make_board_with_tasks(self.org)

        self.member = _make_user('member')
        self.member.profile.organization = self.org
        self.member.profile.save()

    def test_member_forbidden_from_custom_field_list(self):
        client = Client()
        client.force_login(self.member)
        resp = client.get(reverse('custom_field_list', args=[self.workspace.id]))
        self.assertEqual(resp.status_code, 403)

    def test_admin_can_view_custom_field_list(self):
        client = Client()
        client.force_login(self.org_admin)
        resp = client.get(reverse('custom_field_list', args=[self.workspace.id]))
        self.assertEqual(resp.status_code, 200)
