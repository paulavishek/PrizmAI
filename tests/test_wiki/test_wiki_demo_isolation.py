"""Wiki demo isolation tests.

Wiki content is workspace-scoped, but the demo sandbox is a single shared
workspace — so without per-user copies every demo user would see and edit every
other demo user's wiki. The fix mirrors Discovery: demo wiki is cloned per user
(``sandbox_owner=user``) and reads are scoped to the current user's own clones.

These tests pin that guarantee: templates stay hidden, each demo user sees only
their own clones, and one user's edits never bleed to another.
"""
from types import SimpleNamespace

import pytest
from django.contrib.auth.models import User

from accounts.models import Organization
from kanban.models import Workspace
from kanban.sandbox_views import _clone_wiki_for_user
from wiki.models import WikiCategory, WikiPage
from wiki.scoping import wiki_scope_q


@pytest.fixture
def demo_setup(db):
    author = User.objects.create_user('priya.persona', password='x')
    org = Organization.objects.create(name='Demo Org', is_demo=True, created_by=author)
    ws = Workspace.objects.create(
        name='Demo WS', organization=org, is_demo=True, is_active=True, created_by=author,
    )
    # Create the template wiki the seeder would produce (sandbox_owner=None).
    cat = WikiCategory.objects.create(
        name='Engineering', slug='engineering', organization=org, workspace=ws,
        sandbox_owner=None,
    )
    page = WikiPage.objects.create(
        title='API Design Standards', slug='api-design-standards',
        content='# Original', category=cat, organization=org, workspace=ws,
        created_by=author, updated_by=author, is_published=True, sandbox_owner=None,
    )
    return SimpleNamespace(org=org, ws=ws, author=author, cat=cat, page=page)


def _demo_user(username, ws):
    """Create a demo user whose profile reports the demo workspace, so
    wiki_scope_q returns Q(sandbox_owner=user) — the real object resolves the FK
    by pk while the profile drives the demo branch."""
    from accounts.models import UserProfile
    user = User.objects.create_user(username, password='x')
    profile, _ = UserProfile.objects.get_or_create(user=user)
    profile.active_workspace = ws
    profile.is_viewing_demo = True
    profile.save()
    return user


def _scope_pages(user):
    req = SimpleNamespace(user=user)
    return WikiPage.objects.filter(wiki_scope_q(req))


@pytest.mark.django_db
def test_clone_creates_private_per_user_copy(demo_setup):
    alice = _demo_user('alice', demo_setup.ws)
    _clone_wiki_for_user(alice)

    alice_pages = _scope_pages(alice)
    assert alice_pages.count() == 1
    clone = alice_pages.first()
    assert clone.sandbox_owner_id == alice.id
    assert clone.pk != demo_setup.page.pk          # it's a copy, not the template
    assert clone.title == demo_setup.page.title
    # Category is re-pointed at Alice's own cloned category.
    assert clone.category.sandbox_owner_id == alice.id


@pytest.mark.django_db
def test_templates_are_hidden_from_demo_users(demo_setup):
    alice = _demo_user('alice', demo_setup.ws)
    _clone_wiki_for_user(alice)
    # The shared template (sandbox_owner=None) must not appear in a demo scope.
    assert demo_setup.page not in list(_scope_pages(alice))


@pytest.mark.django_db
def test_edits_do_not_bleed_between_demo_users(demo_setup):
    alice = _demo_user('alice', demo_setup.ws)
    bob = _demo_user('bob', demo_setup.ws)
    _clone_wiki_for_user(alice)
    _clone_wiki_for_user(bob)

    # Alice edits her copy.
    alice_page = _scope_pages(alice).first()
    alice_page.content = '# Alice was here'
    alice_page.save()

    # Bob's copy and the template are untouched.
    bob_page = _scope_pages(bob).first()
    assert bob_page.pk != alice_page.pk
    assert bob_page.content == '# Original'
    demo_setup.page.refresh_from_db()
    assert demo_setup.page.content == '# Original'


@pytest.mark.django_db
def test_clone_is_idempotent(demo_setup):
    alice = _demo_user('alice', demo_setup.ws)
    _clone_wiki_for_user(alice)
    _clone_wiki_for_user(alice)  # second (re-)provision / reset
    assert _scope_pages(alice).count() == 1
    assert WikiCategory.objects.filter(sandbox_owner=alice).count() == 1
