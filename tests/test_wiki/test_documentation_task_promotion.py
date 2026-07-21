"""Tests for wiki Documentation-assistant task promotion.

The Documentation assistant historically extracted action items but could not
promote them to a board (the "Create Tasks" button threw "not yet implemented").
These tests pin the new parity flow: analyze persists a WikiDocumentationAnalysis
(content-hash cached), and create_tasks_from_documentation_analysis promotes
selected items to a chosen board/column with assignee overrides, an origin-snippet
traceability footer, and a WikiDocumentationTask audit link that blocks re-promotion.

They also include a regression assertion that the meeting promote flow still works
after the shared-helper refactor.

New tests use force_login (client.login errors under django-axes).
"""
import json

import pytest
from django.contrib.auth.models import User
from django.test import Client
from django.urls import reverse

from accounts.models import Organization
from kanban.models import Board, Column, BoardMembership, Task
from wiki.models import (
    WikiCategory, WikiPage,
    WikiDocumentationAnalysis, WikiDocumentationTask,
    WikiMeetingAnalysis, WikiMeetingTask,
)


DOC_ANALYSIS_RESULTS = {
    'summary': 'A design doc.',
    'action_items': [
        {
            'title': 'Write the migration',
            'description': 'Add the new column',
            'priority': 'high',
            'type': 'todo',
            'source_context': 'See the Schema Changes section',
        },
        {
            'title': 'Update the API docs',
            'description': '',
            'priority': 'low',
            'type': 'documentation',
            'source_context': 'API section',
        },
    ],
}


@pytest.fixture
def doc_setup(db):
    user = User.objects.create_user('doc_owner', password='x', first_name='Dana')
    org = Organization.objects.create(name='Docs Org', created_by=user)
    board = Board.objects.create(name='Docs Board', created_by=user)
    todo = Column.objects.create(name='To Do', board=board, position=0)
    Column.objects.create(name='Done', board=board, position=1)
    BoardMembership.objects.create(board=board, user=user, role='owner')

    cat = WikiCategory.objects.create(
        name='Engineering Docs', slug='eng-docs', ai_assistant_type='documentation',
        organization=org,
    )
    page = WikiPage.objects.create(
        title='Schema Design', slug='schema-design', content='# Schema\nDetails.',
        category=cat, organization=org, created_by=user, updated_by=user,
    )
    analysis = WikiDocumentationAnalysis.objects.create(
        wiki_page=page, processed_by=user, processing_status='completed',
        content_hash='abc123', analysis_results=DOC_ANALYSIS_RESULTS,
    )
    analysis.update_counts()
    analysis.save()

    client = Client()
    client.force_login(user)
    return {
        'user': user, 'board': board, 'todo': todo, 'page': page,
        'analysis': analysis, 'client': client,
    }


def _promote(client, analysis_id, **body):
    url = reverse('wiki:api_create_tasks_from_documentation_analysis', args=[analysis_id])
    return client.post(url, data=json.dumps(body), content_type='application/json')


@pytest.mark.django_db
def test_promote_creates_tasks_with_mapped_priority(doc_setup):
    resp = _promote(
        doc_setup['client'], doc_setup['analysis'].id,
        board_id=doc_setup['board'].id, selected_action_items=[0, 1],
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data['success'] is True
    assert data['total_created'] == 2

    tasks = Task.objects.filter(column=doc_setup['todo']).order_by('id')
    assert tasks.count() == 2
    assert tasks[0].title == 'Write the migration'
    assert tasks[0].priority == 'high'           # mapped straight through
    assert tasks[1].priority == 'low'
    assert all(t.is_seed_demo_data is False for t in tasks)

    # Audit links written, analysis count updated
    assert WikiDocumentationTask.objects.filter(
        documentation_analysis=doc_setup['analysis']
    ).count() == 2
    doc_setup['analysis'].refresh_from_db()
    assert doc_setup['analysis'].tasks_created_count == 2


@pytest.mark.django_db
def test_invalid_priority_falls_back_to_medium(doc_setup):
    doc_setup['analysis'].analysis_results = {
        'action_items': [{'title': 'X', 'priority': 'super-urgent'}]
    }
    doc_setup['analysis'].save()
    _promote(
        doc_setup['client'], doc_setup['analysis'].id,
        board_id=doc_setup['board'].id, selected_action_items=[0],
    )
    task = Task.objects.get(title='X')
    assert task.priority == 'medium'


@pytest.mark.django_db
def test_origin_footer_links_back_to_wiki_page(doc_setup):
    _promote(
        doc_setup['client'], doc_setup['analysis'].id,
        board_id=doc_setup['board'].id, selected_action_items=[0],
    )
    task = Task.objects.get(title='Write the migration')
    assert 'Add the new column' in task.description               # original description kept
    assert doc_setup['page'].title in task.description            # page title
    assert doc_setup['page'].get_absolute_url() in task.description  # clickable back-link
    assert 'See the Schema Changes section' in task.description   # source snippet


@pytest.mark.django_db
def test_assignee_override_honored_and_restricted_to_board(doc_setup):
    member = User.objects.create_user('teammate', password='x', first_name='Tom')
    BoardMembership.objects.create(board=doc_setup['board'], user=member, role='member')
    outsider = User.objects.create_user('outsider', password='x', first_name='Olga')

    resp = _promote(
        doc_setup['client'], doc_setup['analysis'].id,
        board_id=doc_setup['board'].id, selected_action_items=[0, 1],
        assignee_overrides={'0': 'teammate', '1': 'outsider'},
    )
    assert resp.status_code == 200
    t0 = Task.objects.get(title='Write the migration')
    t1 = Task.objects.get(title='Update the API docs')
    assert t0.assigned_to == member          # board member matched
    assert t1.assigned_to is None            # non-member rejected, left unassigned


@pytest.mark.django_db
def test_double_promotion_blocked_by_unique_together(doc_setup):
    first = _promote(
        doc_setup['client'], doc_setup['analysis'].id,
        board_id=doc_setup['board'].id, selected_action_items=[0],
    )
    assert first.json()['total_created'] == 1

    # Re-promoting the same index fails per-item (IntegrityError caught), creating none.
    second = _promote(
        doc_setup['client'], doc_setup['analysis'].id,
        board_id=doc_setup['board'].id, selected_action_items=[0],
    )
    data = second.json()
    assert data['total_created'] == 0
    assert data['total_failed'] == 1
    assert WikiDocumentationTask.objects.filter(
        documentation_analysis=doc_setup['analysis'], action_item_index=0
    ).count() == 1


@pytest.mark.django_db
def test_permission_denied_for_non_board_editor(doc_setup):
    stranger = User.objects.create_user('stranger', password='x')
    client = Client()
    client.force_login(stranger)
    resp = _promote(
        client, doc_setup['analysis'].id,
        board_id=doc_setup['board'].id, selected_action_items=[0],
    )
    assert resp.status_code == 403
    assert Task.objects.count() == 0


@pytest.mark.django_db
def test_meeting_promote_regression(doc_setup):
    """Meeting flow still works (and now also writes the origin footer) after the
    shared-helper refactor."""
    page = doc_setup['page']
    meeting_analysis = WikiMeetingAnalysis.objects.create(
        wiki_page=page, processed_by=doc_setup['user'], processing_status='completed',
        content_hash='m1',
        analysis_results={
            'action_items': [{
                'text': 'Ship the release',
                'description': 'Cut v2',
                'priority': 'urgent',
                'source_quote': 'we agreed to ship Friday',
            }],
        },
    )
    url = reverse('wiki:api_create_tasks_from_analysis', args=[meeting_analysis.id])
    resp = doc_setup['client'].post(
        url,
        data=json.dumps({'board_id': doc_setup['board'].id, 'selected_action_items': [0]}),
        content_type='application/json',
    )
    assert resp.status_code == 200
    assert resp.json()['total_created'] == 1
    task = Task.objects.get(title='Ship the release')
    assert task.priority == 'urgent'                              # meeting keeps urgent
    assert 'we agreed to ship Friday' in task.description         # origin footer added
    assert WikiMeetingTask.objects.filter(meeting_analysis=meeting_analysis).count() == 1
