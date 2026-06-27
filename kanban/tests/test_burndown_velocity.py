"""
Burndown velocity-history regression tests.

Guards the fix for the demo data corruption where demo boards accumulated
dozens of duplicate / overlapping TeamVelocitySnapshot rows, diluting average
velocity toward 0 and pushing predicted completion years into the future.

Covers:
  * _get_velocity_history caps to VELOCITY_WINDOW_WEEKS most-recent buckets.
  * It excludes snapshots whose period_end is older than the look-back window.
  * The (board, period_start, period_end) UniqueConstraint blocks duplicate
    buckets at the DB level.
"""

from datetime import timedelta
from decimal import Decimal

from django.db import IntegrityError, transaction
from django.test import TestCase
from django.utils import timezone

from accounts.models import Organization
from kanban.models import Board, Workspace
from kanban.burndown_models import TeamVelocitySnapshot
from kanban.utils.burndown_predictor import BurndownPredictor


def _make_board(slug):
    from django.contrib.auth.models import User
    user = User.objects.create_user(username=f'{slug}_user', password='pw',
                                    email=f'{slug}@example.com')
    org = Organization.objects.create(name=f'{slug} Org', created_by=user)
    ws = Workspace.objects.create(name=f'{slug} WS', organization=org,
                                  created_by=user, is_demo=False)
    return Board.objects.create(name=f'{slug} Board', created_by=user, owner=user,
                                organization=org, workspace=ws)


def _make_snapshot(board, *, weeks_ago, tasks):
    """Create a Monday-Sunday weekly snapshot `weeks_ago` weeks back."""
    today = timezone.now().date()
    this_monday = today - timedelta(days=today.weekday())
    period_start = this_monday - timedelta(weeks=weeks_ago)
    period_end = period_start + timedelta(days=6)
    return TeamVelocitySnapshot.objects.create(
        board=board, period_start=period_start, period_end=period_end,
        period_type='weekly', tasks_completed=tasks,
        story_points_completed=Decimal('0'), active_team_members=1,
    )


class GetVelocityHistoryTest(TestCase):
    def test_caps_to_window_and_returns_newest_first(self):
        board = _make_board('cap')
        # 12 distinct weekly buckets, all inside the 8-week window's reach is
        # not required — we assert the cap independent of window here by using
        # weeks 0..11; weeks 0..7 (<=8 weeks back) are in-window.
        for w in range(12):
            _make_snapshot(board, weeks_ago=w, tasks=w)

        history = BurndownPredictor()._get_velocity_history(board)

        # Never more than the look-back window.
        self.assertLessEqual(len(history), BurndownPredictor.VELOCITY_WINDOW_WEEKS)
        # Returned newest-first (period_end descending).
        ends = [h['period_end'] for h in history]
        self.assertEqual(ends, sorted(ends, reverse=True))

    def test_excludes_snapshots_older_than_window(self):
        board = _make_board('window')
        _make_snapshot(board, weeks_ago=0, tasks=3)     # in-window
        _make_snapshot(board, weeks_ago=20, tasks=99)   # well outside window

        history = BurndownPredictor()._get_velocity_history(board)

        self.assertEqual(len(history), 1)
        self.assertEqual(history[0]['tasks_completed'], 3)


class VelocitySnapshotUniqueConstraintTest(TestCase):
    def test_duplicate_period_rejected(self):
        board = _make_board('uniq')
        _make_snapshot(board, weeks_ago=1, tasks=2)
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                _make_snapshot(board, weeks_ago=1, tasks=5)
