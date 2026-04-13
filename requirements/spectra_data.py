"""
Spectra Verified Data Fetchers (VDFs) — Requirements Analysis

Pre-computed data functions for the Requirements Analysis feature.
All reasoning and computation happens here so Spectra receives
clean, structured data ready for natural-language synthesis.

These functions follow the same VDF contract as spectra_data_fetchers.py:
- Board-scoped queries only (no cross-board leakage)
- Pre-computed summaries (Spectra never does raw math)
- Returns dicts/strings ready for prompt injection

Created: Requirements Analysis feature integration
"""

import logging

from django.db.models import Count, Q

logger = logging.getLogger(__name__)


def _safe_import_models():
    """Lazy import to avoid circular imports at module load."""
    from requirements.models import (
        Requirement,
        RequirementCategory,
        ProjectObjective,
        RequirementHistory,
    )
    return Requirement, RequirementCategory, ProjectObjective, RequirementHistory


def get_requirements_summary_for_board(board):
    """
    High-level summary of all requirements for a board.
    Returns a structured dict with counts, breakdowns, and narrative.

    Used by: chatbot_service context builder, API endpoint.
    """
    Requirement, RequirementCategory, ProjectObjective, _ = _safe_import_models()

    reqs = Requirement.objects.filter(board=board)
    total = reqs.count()

    if total == 0:
        return {
            'total': 0,
            'narrative': f'Board "{board.name}" has no requirements defined yet.',
            'status_breakdown': {},
            'type_breakdown': {},
            'priority_breakdown': {},
            'coverage_pct': 0,
            'categories': [],
            'objectives_count': 0,
            'critical_items': [],
        }

    # Status breakdown
    status_counts = {}
    for entry in reqs.values('status').annotate(count=Count('id')):
        status_counts[entry['status']] = entry['count']

    # Type breakdown
    type_counts = {}
    for entry in reqs.values('type').annotate(count=Count('id')):
        type_counts[entry['type']] = entry['count']

    # Priority breakdown
    priority_counts = {}
    for entry in reqs.values('priority').annotate(count=Count('id')):
        priority_counts[entry['priority']] = entry['count']

    # Task coverage
    with_tasks = reqs.filter(linked_tasks__isnull=False).distinct().count()
    coverage_pct = round((with_tasks / total) * 100) if total > 0 else 0

    # Categories
    categories = list(
        RequirementCategory.objects.filter(board=board)
        .annotate(req_count=Count('requirements'))
        .values('name', 'req_count')
    )

    # Objectives
    objectives_count = ProjectObjective.objects.filter(board=board).count()

    # Critical items (high/critical priority that aren't implemented/verified)
    critical_items = list(
        reqs.filter(
            priority__in=['critical', 'high'],
        ).exclude(
            status__in=['implemented', 'verified'],
        ).values('identifier', 'title', 'status', 'priority')[:10]
    )

    # Build narrative summary
    status_labels = dict(Requirement.STATUS_CHOICES)
    status_parts = []
    for s in ['draft', 'in_review', 'approved', 'rejected', 'implemented', 'verified']:
        c = status_counts.get(s, 0)
        if c > 0:
            status_parts.append(f"{c} {status_labels.get(s, s)}")
    status_narrative = ', '.join(status_parts)

    narrative = (
        f'Board "{board.name}" has {total} requirements '
        f'({status_narrative}). '
        f'Task coverage is {coverage_pct}% ({with_tasks} of {total} linked to tasks). '
    )
    if critical_items:
        narrative += f'{len(critical_items)} high/critical-priority items still need attention. '
    if categories:
        cat_names = ', '.join(c['name'] for c in categories)
        narrative += f'Categories: {cat_names}. '

    return {
        'total': total,
        'narrative': narrative,
        'status_breakdown': status_counts,
        'type_breakdown': type_counts,
        'priority_breakdown': priority_counts,
        'coverage_pct': coverage_pct,
        'covered_count': with_tasks,
        'categories': categories,
        'objectives_count': objectives_count,
        'critical_items': critical_items,
    }


def get_requirements_by_status(board, status=None):
    """
    Get requirements filtered by status, with pre-computed metadata.
    If status is None, returns all requirements grouped by status.

    Returns a dict keyed by status with lists of requirement summaries.
    """
    Requirement, _, _, _ = _safe_import_models()

    qs = Requirement.objects.filter(board=board).select_related(
        'category', 'created_by', 'reviewer'
    ).prefetch_related('linked_tasks', 'objectives')

    if status:
        qs = qs.filter(status=status)

    grouped = {}
    for req in qs:
        s = req.status
        if s not in grouped:
            grouped[s] = []
        grouped[s].append({
            'identifier': req.identifier,
            'title': req.title,
            'type': req.get_type_display(),
            'priority': req.get_priority_display(),
            'status': req.get_status_display(),
            'category': req.category.name if req.category else None,
            'task_count': req.linked_tasks.count(),
            'objective_count': req.objectives.count(),
            'created_by': req.created_by.get_full_name() or req.created_by.username,
        })

    return grouped


def get_traceability_summary(board):
    """
    Pre-computed traceability analysis for Spectra.
    Shows which requirements are covered by tasks and objectives.

    Returns a narrative string and structured data.
    """
    Requirement, _, ProjectObjective, _ = _safe_import_models()

    reqs = Requirement.objects.filter(board=board).prefetch_related(
        'linked_tasks', 'objectives'
    )
    total = reqs.count()
    if total == 0:
        return {
            'narrative': 'No requirements exist for traceability analysis.',
            'covered': [],
            'uncovered': [],
            'coverage_pct': 0,
        }

    covered = []
    uncovered = []
    for req in reqs:
        task_count = req.linked_tasks.count()
        info = {
            'identifier': req.identifier,
            'title': req.title,
            'priority': req.get_priority_display(),
            'task_count': task_count,
        }
        if task_count > 0:
            covered.append(info)
        else:
            uncovered.append(info)

    coverage_pct = round((len(covered) / total) * 100) if total > 0 else 0

    narrative = (
        f'Traceability: {len(covered)} of {total} requirements ({coverage_pct}%) '
        f'are linked to tasks. '
    )
    if uncovered:
        unc_list = ', '.join(r['identifier'] for r in uncovered[:5])
        narrative += f'Uncovered requirements: {unc_list}'
        if len(uncovered) > 5:
            narrative += f' and {len(uncovered) - 5} more'
        narrative += '. '

    # Highlight critical uncovered
    critical_uncovered = [r for r in uncovered if r['priority'] in ('Critical', 'High')]
    if critical_uncovered:
        crit_list = ', '.join(r['identifier'] for r in critical_uncovered[:5])
        narrative += f'⚠ Critical/high-priority without tasks: {crit_list}. '

    return {
        'narrative': narrative,
        'covered': covered,
        'uncovered': uncovered,
        'coverage_pct': coverage_pct,
    }


def get_requirement_detail_for_spectra(board, identifier):
    """
    Detailed info about a single requirement by identifier (e.g. REQ-001).
    Returns a dict with all fields pre-formatted for Spectra.
    """
    Requirement, _, _, RequirementHistory = _safe_import_models()

    try:
        req = Requirement.objects.select_related(
            'category', 'created_by', 'reviewer', 'parent'
        ).prefetch_related(
            'linked_tasks', 'objectives', 'children', 'related_requirements'
        ).get(board=board, identifier=identifier)
    except Requirement.DoesNotExist:
        return None

    # History
    history = list(
        RequirementHistory.objects.filter(requirement=req)
        .select_related('changed_by')
        .order_by('-changed_at')
        .values('old_status', 'new_status', 'changed_at', 'notes')[:10]
    )

    # Linked tasks
    linked_tasks = [
        {
            'title': t.title,
            'column': t.column.name if t.column else 'Unknown',
            'assignee': t.assigned_to.get_full_name() if t.assigned_to else 'Unassigned',
        }
        for t in req.linked_tasks.select_related('column', 'assigned_to').all()
    ]

    return {
        'identifier': req.identifier,
        'title': req.title,
        'description': req.description or '',
        'type': req.get_type_display(),
        'priority': req.get_priority_display(),
        'status': req.get_status_display(),
        'category': req.category.name if req.category else None,
        'acceptance_criteria': req.acceptance_criteria or '',
        'created_by': req.created_by.get_full_name() or req.created_by.username,
        'reviewer': (req.reviewer.get_full_name() or req.reviewer.username) if req.reviewer else None,
        'parent': req.parent.identifier if req.parent else None,
        'children': [c.identifier for c in req.children.all()],
        'linked_tasks': linked_tasks,
        'objectives': [o.title for o in req.objectives.all()],
        'related_requirements': [r.identifier for r in req.related_requirements.all()],
        'history': history,
        'created_at': req.created_at.isoformat() if req.created_at else None,
    }


def get_requirement_coverage_stats(board):
    """
    Detailed coverage statistics pre-computed for Spectra.
    Answers questions like "how well are our requirements covered?"
    """
    Requirement, RequirementCategory, ProjectObjective, _ = _safe_import_models()

    reqs = Requirement.objects.filter(board=board).prefetch_related(
        'linked_tasks', 'objectives'
    )
    total = reqs.count()
    if total == 0:
        return {'narrative': 'No requirements to analyze coverage for.', 'stats': {}}

    # Per-priority coverage
    priority_coverage = {}
    for p_val, p_label in Requirement.PRIORITY_CHOICES:
        p_reqs = [r for r in reqs if r.priority == p_val]
        p_total = len(p_reqs)
        p_covered = sum(1 for r in p_reqs if r.linked_tasks.count() > 0)
        priority_coverage[p_label] = {
            'total': p_total,
            'covered': p_covered,
            'pct': round((p_covered / p_total) * 100) if p_total > 0 else 0,
        }

    # Per-status coverage
    status_coverage = {}
    for s_val, s_label in Requirement.STATUS_CHOICES:
        s_reqs = [r for r in reqs if r.status == s_val]
        s_total = len(s_reqs)
        s_covered = sum(1 for r in s_reqs if r.linked_tasks.count() > 0)
        status_coverage[s_label] = {
            'total': s_total,
            'covered': s_covered,
            'pct': round((s_covered / s_total) * 100) if s_total > 0 else 0,
        }

    # Narrative
    overall_covered = sum(1 for r in reqs if r.linked_tasks.count() > 0)
    overall_pct = round((overall_covered / total) * 100) if total > 0 else 0

    parts = []
    for label, data in priority_coverage.items():
        if data['total'] > 0:
            parts.append(f"{label}: {data['covered']}/{data['total']} ({data['pct']}%)")
    coverage_by_priority = '; '.join(parts)

    narrative = (
        f'Overall coverage: {overall_covered}/{total} ({overall_pct}%). '
        f'By priority — {coverage_by_priority}.'
    )

    return {
        'narrative': narrative,
        'overall_pct': overall_pct,
        'priority_coverage': priority_coverage,
        'status_coverage': status_coverage,
    }


def get_requirements_context_for_board(board):
    """
    Master context function called by the API endpoint and chatbot_service.
    Bundles all requirement data into a single context dict for Spectra.

    This is the primary entry point for Spectra integration.
    """
    summary = get_requirements_summary_for_board(board)
    traceability = get_traceability_summary(board)
    coverage = get_requirement_coverage_stats(board)

    return {
        'summary': summary,
        'traceability': traceability,
        'coverage': coverage,
        'full_narrative': (
            f"REQUIREMENTS ANALYSIS:\n"
            f"{summary.get('narrative', '')}\n"
            f"{traceability.get('narrative', '')}\n"
            f"{coverage.get('narrative', '')}"
        ),
    }
