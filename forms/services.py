"""
Forms submission processing — maps FormAnswers onto a DiscoveryIdea or Task.

This is the "front door" the Forms feature adds onto machinery that already
exists: DiscoveryIdea creation mirrors kanban.discovery_views.idea_create,
and Task creation reuses the same intake-column auto-detection used when
promoting a Discovery idea (kanban.discovery_utils.pick_intake_column).
"""
import logging

from django.db import transaction

logger = logging.getLogger(__name__)


def build_property_values(submission):
    """
    Walk a FormSubmission's answers and return (title, description, source)
    to seed the created DiscoveryIdea/Task.

    Fields mapped to 'title'/'description'/'source' populate those
    properties directly (last non-empty answer wins if a form has more than
    one field mapped to the same property). Fields mapped to 'none' are
    context-only and get folded into the description as "Label: value"
    lines, so Spectra still sees them when scoring (the "structured intake
    -> higher-quality scoring" idea from the product brief).
    """
    title = ''
    description_parts = []
    source = 'other'

    answers = submission.answers.select_related('field').order_by('field__order', 'field_id')
    for answer in answers:
        field = answer.field
        if field.field_type == 'STATIC_CONTENT':
            continue
        value = answer.value
        text_value = ', '.join(str(v) for v in value) if isinstance(value, list) else str(value or '').strip()
        if not text_value:
            continue

        if field.mapped_property == 'title':
            title = text_value
        elif field.mapped_property == 'description':
            description_parts.append(text_value)
        elif field.mapped_property == 'source':
            source = text_value
        else:  # 'none' — context only, still feeds Spectra via the description
            description_parts.append(f"{field.label}: {text_value}")

    return title, '\n\n'.join(description_parts), source


def process_submission(submission, user):
    """
    Create the DiscoveryIdea or Task a FormSubmission targets, and save the
    link back onto the submission. Returns the created object (or None if
    a Kanban-Task form has no usable target column).
    """
    form = submission.form
    title, description, source = build_property_values(submission)
    if not title:
        title = form.title  # never create an untitled idea/task

    if form.target_destination == 'DISCOVERY':
        return _create_idea(form, submission, user, title, description, source)
    return _create_task(form, submission, user, title, description)


def _create_idea(form, submission, user, title, description, source):
    from kanban.discovery_models import DiscoveryIdea, IDEA_SOURCE_CHOICES
    from kanban.discovery_views import _demo_owner_filter

    valid_sources = {c[0] for c in IDEA_SOURCE_CHOICES}
    if source not in valid_sources:
        source = 'other'

    org = form.workspace.organization
    idea = DiscoveryIdea.objects.create(
        organization=org,
        workspace=form.workspace,
        title=title,
        description=description,
        source=source,
        stage='new',
        submitted_by=user,
        # In demo mode, ideas the user submits belong to their private
        # sandbox set so they don't leak to other demo users (mirrors
        # kanban.discovery_views.idea_create).
        **_demo_owner_filter(org, user),
    )
    submission.created_idea = idea
    submission.save(update_fields=['created_idea'])

    from forms.tasks import score_form_idea
    transaction.on_commit(lambda: score_form_idea.delay(idea.id))

    return idea


def _create_task(form, submission, user, title, description):
    from kanban.models import Task
    from kanban.discovery_utils import pick_intake_column

    board = form.target_board
    target_col = pick_intake_column(board) if board else None
    if target_col is None:
        logger.warning(
            'Form %s (target Kanban Task) has no usable target column on board %s',
            form.pk, board and board.pk,
        )
        return None

    task = Task.objects.create(
        title=title,
        description=(
            f'Submitted via Form "{form.title}".\n\n{description}'
            if description
            else f'Submitted via Form "{form.title}".'
        ),
        column=target_col,
        created_by=user,
        position=Task.objects.filter(column=target_col).count(),
    )
    submission.created_task = task
    submission.save(update_fields=['created_task'])
    return task
