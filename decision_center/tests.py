from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone

from accounts.models import UserProfile
from decision_center.models import DecisionCenterBriefing
from kanban.utils.demo_protection import user_is_demo

User = get_user_model()


class BriefingWorkspaceIsolationTests(TestCase):
    """Guard against the demo briefing leaking into the real workspace.

    The Focus Today "AI Briefing" headline is a per-(user, date) record. Before
    the ``is_demo`` discriminator existed, the same row showed in both the demo
    and real workspaces, so the demo headline appeared in the real dashboard.
    """

    def setUp(self):
        self.user = User.objects.create_user(
            username='isouser', password='pw', email='iso@example.com',
        )
        UserProfile.objects.get_or_create(user=self.user)
        today = timezone.localdate()
        self.real = DecisionCenterBriefing.objects.create(
            user=self.user, headline='REAL headline', briefing='r',
            is_demo=False,
        )
        self.demo = DecisionCenterBriefing.objects.create(
            user=self.user, headline='DEMO headline', briefing='d',
            is_demo=True,
        )
        assert self.real.generated_at.date() == today
        assert self.demo.generated_at.date() == today

    def _headline_for_mode(self, is_demo):
        return (
            DecisionCenterBriefing.objects
            .filter(
                user=self.user,
                generated_at__date=timezone.localdate(),
                is_demo=is_demo,
            )
            .values_list('headline', flat=True)
            .first()
        )

    def test_real_mode_sees_only_real_briefing(self):
        self.user.profile.is_viewing_demo = False
        self.user.profile.save(update_fields=['is_viewing_demo'])
        self.assertFalse(user_is_demo(self.user))
        self.assertEqual(self._headline_for_mode(user_is_demo(self.user)),
                         'REAL headline')

    def test_demo_mode_sees_only_demo_briefing(self):
        self.user.profile.is_viewing_demo = True
        self.user.profile.save(update_fields=['is_viewing_demo'])
        self.assertTrue(user_is_demo(self.user))
        self.assertEqual(self._headline_for_mode(user_is_demo(self.user)),
                         'DEMO headline')
