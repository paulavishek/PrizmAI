"""
Demo persona switching — "Back to <real user>" session anchor.

Covers a bug where hopping directly between demo personas (e.g. Elena ->
Marcus via the "Sign in as any of these demo users" dropdown, available
while already viewing any persona) lost the `real_user_username` session
key. quick_demo_login only captured it from `request.user.username` when
the *current* user wasn't itself a demo persona, so a persona-to-persona
hop passed `real_username=None` — and Django's `login()` flushes the
session on the resulting pk change, permanently dropping the anchor back
to the real account for that session (the "Back to X" topbar button
disappears and return_to_real_account() has nothing to return to).
"""
from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse

from accounts.demo_personas import DEMO_PASSWORD
from accounts.models import UserProfile


class DemoPersonaSwitchTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.real_user = User.objects.create_user('testuser1', password='x')
        UserProfile.objects.get_or_create(user=cls.real_user)

        cls.elena = User.objects.create_user(
            'elena.vasquez', email='elena.vasquez@demo.prizmai.local', password=DEMO_PASSWORD,
        )
        UserProfile.objects.get_or_create(user=cls.elena)

        cls.marcus = User.objects.create_user(
            'marcus.chen', email='marcus.chen@demo.prizmai.local', password=DEMO_PASSWORD,
        )
        UserProfile.objects.get_or_create(user=cls.marcus)

    def test_real_user_to_persona_sets_real_username(self):
        self.client.force_login(self.real_user)
        self.client.get(reverse('quick_demo_login', args=['elena.vasquez']))
        self.assertEqual(self.client.session['real_user_username'], 'testuser1')

    def test_persona_to_persona_hop_preserves_real_username(self):
        self.client.force_login(self.real_user)
        self.client.get(reverse('quick_demo_login', args=['elena.vasquez']))
        self.assertEqual(self.client.session['real_user_username'], 'testuser1')

        # Hop directly from Elena to Marcus, as the Demo Info dropdown allows.
        self.client.get(reverse('quick_demo_login', args=['marcus.chen']))
        self.assertEqual(self.client.session['real_user_username'], 'testuser1')

    def test_return_to_real_account_after_persona_hop(self):
        self.client.force_login(self.real_user)
        self.client.get(reverse('quick_demo_login', args=['elena.vasquez']))
        self.client.get(reverse('quick_demo_login', args=['marcus.chen']))

        response = self.client.get(reverse('return_to_real_account'))
        self.assertRedirects(response, reverse('dashboard'))
        self.assertEqual(self.client.session['_auth_user_id'], str(self.real_user.pk))
