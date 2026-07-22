"""
Regression tests for the Gantt "Shift N tasks" dependency cascade.

Reproduces the reported bug: dragging a task to a later due date and clicking
"Shift N tasks" left every dependent untouched (a silent no-op), even though the
banner promised N tasks would move.

Scenario mirrors the demo board exactly:

  Security Architecture Patterns (SAP)  start 05-31  due 06-10
    └─ Social Login Integration         start 06-10  due 06-14   (dep: SAP)
    └─ Authentication System            start 06-12  due 06-18   (dep: SAP)
    └─ Authentication Testing Suite     start 06-13  due 06-22   (dep: SAP)
    └─ Role-Based Access Control (RBAC) start 06-16  due 06-26   (dep: SAP)

Dragging SAP's due date to 06-14 must shift the first three (each starts before
06-14) and leave RBAC alone (it already starts after 06-14).
"""

import json
from datetime import date, datetime, time

from django.contrib.auth.models import User
from django.test import TestCase, Client
from django.urls import reverse
from django.utils import timezone


def _aware_due(d):
    """End-of-day aware datetime for a due-date, matching how the app stores them."""
    return timezone.make_aware(datetime.combine(d, time(23, 59, 59)))


class GanttCascadeRescheduleTest(TestCase):
    def setUp(self):
        from accounts.models import Organization, UserProfile
        from kanban.models import Workspace, Board, Column, Task

        self.user = User.objects.create_user(
            username='cascade_user', password='pw', email='cascade@example.com',
        )
        org = Organization.objects.create(name='Cascade Org', created_by=self.user)
        ws = Workspace.objects.create(
            name="Cascade WS", organization=org, created_by=self.user, is_demo=False,
        )
        profile, _ = UserProfile.objects.get_or_create(user=self.user)
        profile.organization = org
        profile.active_workspace = ws
        profile.save()

        # owner=user → is_record_owner → prizmai.edit_board granted (no membership needed)
        self.board = Board.objects.create(
            name='Cascade Board', created_by=self.user, owner=self.user,
            organization=org, workspace=ws,
        )
        self.col = Column.objects.create(board=self.board, name='Backlog', position=0)

        def mk(title, start, due):
            return Task.objects.create(
                column=self.col, title=title, created_by=self.user,
                item_type='task', phase='Phase 1',
                start_date=start, due_date=_aware_due(due),
            )

        self.sap = mk('Security Architecture Patterns', date(2026, 5, 31), date(2026, 6, 10))
        self.social = mk('Social Login Integration', date(2026, 6, 10), date(2026, 6, 14))
        self.authsys = mk('Authentication System', date(2026, 6, 12), date(2026, 6, 18))
        self.authtest = mk('Authentication Testing Suite', date(2026, 6, 13), date(2026, 6, 22))
        self.rbac = mk('Role-Based Access Control (RBAC)', date(2026, 6, 16), date(2026, 6, 26))

        # Each dependent must finish AFTER SAP: SAP ∈ dependent.dependencies
        for dep in (self.social, self.authsys, self.authtest, self.rbac):
            dep.dependencies.add(self.sap)

        self.client = Client()
        self.client.force_login(self.user)

    def _reschedule(self, task, due):
        url = reverse('reschedule_task_api', args=[task.id])
        return self.client.patch(
            url, data=json.dumps({'due_date': due.isoformat()}),
            content_type='application/json',
        )

    def _cascade(self, task, start=None, due=None):
        url = reverse('cascade_reschedule_task_api', args=[task.id])
        body = {}
        if start is not None:
            body['start_date'] = start.isoformat()
        if due is not None:
            body['due_date'] = due.isoformat()
        return self.client.post(
            url, data=json.dumps(body), content_type='application/json',
        )

    def test_banner_count_excludes_already_late_dependent(self):
        """Dragging SAP to 06-14: the banner should flag exactly the 3 that start
        before 06-14, and NOT RBAC (starts 06-16)."""
        resp = self._reschedule(self.sap, date(2026, 6, 14))
        self.assertEqual(resp.status_code, 200, resp.content)
        data = resp.json()
        self.assertTrue(data['success'])
        titles = {d['title'] for d in data['affected_dependents']}
        self.assertEqual(
            titles,
            {'Social Login Integration', 'Authentication System', 'Authentication Testing Suite'},
        )
        # total_dependents counts ALL 4 linked dependents (incl. RBAC) so the
        # banner can explain why it offers to shift only 3. Difference == 1.
        self.assertEqual(data['total_dependents'], 4)
        self.assertEqual(data['total_dependents'] - len(data['affected_dependents']), 1)

    def test_shift_actually_moves_dependents(self):
        """The core regression: after reschedule + cascade, every flagged dependent
        must actually have advanced; RBAC must stay put."""
        from kanban.models import Task

        r1 = self._reschedule(self.sap, date(2026, 6, 14))
        self.assertEqual(r1.status_code, 200, r1.content)

        r2 = self._cascade(self.sap, start=date(2026, 5, 31), due=date(2026, 6, 14))
        self.assertEqual(r2.status_code, 200, r2.content)
        moved = {m['title'] for m in r2.json().get('updated', [])}
        self.assertIn('Social Login Integration', moved)
        self.assertIn('Authentication System', moved)
        self.assertIn('Authentication Testing Suite', moved)

        # Authoritative DB check: each dependent now starts no earlier than SAP's
        # new due date (06-14) and preserved its own duration.
        social = Task.objects.get(id=self.social.id)
        authsys = Task.objects.get(id=self.authsys.id)
        authtest = Task.objects.get(id=self.authtest.id)
        rbac = Task.objects.get(id=self.rbac.id)

        self.assertEqual(social.start_date, date(2026, 6, 14))
        self.assertEqual(social.due_date.date(), date(2026, 6, 18))   # 4-day span preserved
        self.assertEqual(authsys.start_date, date(2026, 6, 14))
        self.assertEqual(authsys.due_date.date(), date(2026, 6, 20))  # 6-day span
        self.assertEqual(authtest.start_date, date(2026, 6, 14))
        self.assertEqual(authtest.due_date.date(), date(2026, 6, 23))  # 9-day span

        # RBAC already started after 06-14 → untouched.
        self.assertEqual(rbac.start_date, date(2026, 6, 16))
        self.assertEqual(rbac.due_date.date(), date(2026, 6, 26))

    def test_cascade_is_self_sufficient(self):
        """The cascade must move dependents using the source dates it is given,
        WITHOUT relying on a prior reschedule request having persisted them.

        This isolates the real-world failure: across separate requests the
        cascade could read a stale source due date and silently move nothing.
        With the source's authoritative new dates in the POST body it must move
        the dependents regardless. (Fails on the old body-ignoring endpoint.)
        """
        from kanban.models import Task

        # SAP still has its ORIGINAL due (06-10) in the DB — no reschedule call.
        r = self._cascade(self.sap, start=date(2026, 5, 31), due=date(2026, 6, 14))
        self.assertEqual(r.status_code, 200, r.content)
        moved = {m['title'] for m in r.json().get('updated', [])}
        self.assertEqual(
            moved & {'Social Login Integration', 'Authentication System',
                     'Authentication Testing Suite'},
            {'Social Login Integration', 'Authentication System',
             'Authentication Testing Suite'},
        )

        # Source task itself should now carry the authoritative new due date.
        sap = Task.objects.get(id=self.sap.id)
        self.assertEqual(sap.due_date.date(), date(2026, 6, 14))

        # Dependents advanced to start at SAP's new finish.
        self.assertEqual(Task.objects.get(id=self.social.id).start_date, date(2026, 6, 14))
        self.assertEqual(Task.objects.get(id=self.authsys.id).start_date, date(2026, 6, 14))
        self.assertEqual(Task.objects.get(id=self.authtest.id).start_date, date(2026, 6, 14))
