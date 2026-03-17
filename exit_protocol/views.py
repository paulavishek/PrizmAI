"""
Views for Exit Protocol: Hospice, Organ Transplant, Cemetery.
"""

import json
import logging
from datetime import timedelta
from io import BytesIO

import bleach
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db.models import Q
from django.http import HttpResponseBadRequest, JsonResponse, HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from kanban.models import Board
from kanban.simple_access import check_access_or_403, check_management_or_403
from kanban.audit_utils import log_audit

from .models import (
    ProjectHealthSignal, HospiceSession, ProjectOrgan,
    OrganTransplant, CemeteryEntry, HospiceDismissal,
)

logger = logging.getLogger(__name__)


# ──────────────────────────
# Hospice / Dashboard Views
# ──────────────────────────

@login_required
def exit_protocol_dashboard(request, board_id):
    board = get_object_or_404(Board, id=board_id)
    check_access_or_403(request.user, board)

    signals = ProjectHealthSignal.objects.filter(
        board=board
    ).order_by('-recorded_at')[:10]

    last_signal = signals[0] if signals else None
    current_score = last_signal.hospice_risk_score if last_signal else 0

    hospice_session = HospiceSession.objects.filter(board=board).first()

    # Check if banner is dismissed
    now = timezone.now()
    banner_dismissed = HospiceDismissal.objects.filter(
        board=board, user=request.user, expires_at__gt=now
    ).exists()

    # Build per-dimension score breakdown
    score_breakdown = []
    if last_signal and last_signal.score_is_valid:
        WEIGHTS = {'velocity': 0.30, 'budget': 0.25, 'deadlines': 0.25, 'activity': 0.20}
        available = {}
        if last_signal.velocity_decline_pct is not None:
            available['velocity'] = min(max(last_signal.velocity_decline_pct / 100, 0.0), 1.0)
        if last_signal.budget_spent_pct is not None and last_signal.tasks_complete_pct is not None:
            available['budget'] = min(
                (last_signal.budget_spent_pct / 100) * (1 - last_signal.tasks_complete_pct / 100), 1.0
            )
        if last_signal.deadlines_missed_30d is not None:
            available['deadlines'] = min(last_signal.deadlines_missed_30d / 10, 1.0)
        available['activity'] = min(last_signal.days_since_last_activity / 30, 1.0)

        total_weight = sum(WEIGHTS[k] for k in available)
        for dim, factor in available.items():
            adjusted_weight = WEIGHTS[dim] / total_weight
            score_breakdown.append({
                'label': dim.replace('_', ' ').title(),
                'factor_pct': round(factor * 100),
                'contribution_pct': round(factor * adjusted_weight * 100),
                'status': 'danger' if factor >= 0.75 else 'warning' if factor >= 0.40 else 'success',
            })

    return render(request, 'exit_protocol/dashboard.html', {
        'board': board,
        'signals': signals,
        'current_risk_score': current_score,
        'hospice_session': hospice_session,
        'show_initiate_cta': not hospice_session and current_score >= 0.75,
        'banner_dismissed': banner_dismissed,
        'score_breakdown': score_breakdown,
        'last_signal': last_signal,
    })


@login_required
@require_POST
def recalculate_health_score(request, board_id):
    """Manually triggers a health score recomputation for this board."""
    board = get_object_or_404(Board, id=board_id)
    check_access_or_403(request.user, board)

    from .tasks import compute_board_health_score
    compute_board_health_score.delay(board_id)

    return JsonResponse({
        'status': 'recalculating',
        'message': 'Health score recalculation started. Refresh in a few seconds.',
    })


@login_required
@require_POST
def initiate_hospice(request, board_id):
    board = get_object_or_404(Board, id=board_id)
    check_management_or_403(request.user, board)

    if HospiceSession.objects.filter(board=board).exists():
        return HttpResponseBadRequest("A hospice session already exists for this board.")

    session = HospiceSession.objects.create(
        board=board,
        initiated_by=request.user,
        trigger_type='manager_initiated',
        status='assessment',
    )

    # Spawn parallel AI tasks
    from .tasks import (
        generate_hospice_assessment,
        generate_knowledge_checklist,
        generate_team_transition_memos,
        scan_and_extract_organs,
    )
    generate_hospice_assessment.delay(session.id)
    generate_knowledge_checklist.delay(session.id)
    generate_team_transition_memos.delay(session.id)
    scan_and_extract_organs.delay(session.id)

    messages.success(
        request,
        "Wind-down review initiated. AI assessment is being generated — "
        "this may take a minute."
    )
    return redirect('exit_protocol:dashboard', board_id=board.id)


@login_required
@require_POST
def complete_checklist_item(request, board_id, item_id):
    board = get_object_or_404(Board, id=board_id)
    check_access_or_403(request.user, board)

    session = get_object_or_404(HospiceSession, board=board)

    completed = session.checklist_completed_items or []
    if item_id not in completed:
        completed.append(item_id)
        session.checklist_completed_items = completed
        session.save(update_fields=['checklist_completed_items'])

    # Count total items across all checklist categories
    checklist = session.knowledge_checklist or {}
    total = sum(len(items) for items in checklist.values())

    return JsonResponse({
        'completed': True,
        'total': total,
        'done': len(completed),
    })


@login_required
def view_transition_memos(request, board_id):
    board = get_object_or_404(Board, id=board_id)
    check_access_or_403(request.user, board)

    session = get_object_or_404(HospiceSession, board=board)

    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            memos = data.get('memos', {})
            # Sanitize all memo text
            sanitized = {
                uid: bleach.clean(text, strip=True)
                for uid, text in memos.items()
            }
            session.team_transition_memos = sanitized
            session.save(update_fields=['team_transition_memos'])
            return JsonResponse({'success': True})
        except (json.JSONDecodeError, ValueError):
            return HttpResponseBadRequest("Invalid JSON")

    # GET: render memos page
    from django.contrib.auth.models import User
    memos_with_users = []
    if session.team_transition_memos:
        for user_id, memo in session.team_transition_memos.items():
            try:
                member = User.objects.get(id=user_id)
                memos_with_users.append({
                    'user': member,
                    'memo': memo,
                })
            except User.DoesNotExist:
                memos_with_users.append({
                    'user': None,
                    'user_id': user_id,
                    'memo': memo,
                })

    return render(request, 'exit_protocol/transition_memos.html', {
        'board': board,
        'hospice_session': session,
        'memos': memos_with_users,
    })


@login_required
@require_POST
def bury_project(request, board_id):
    board = get_object_or_404(Board, id=board_id)
    check_management_or_403(request.user, board)

    session = get_object_or_404(HospiceSession, board=board)

    confirmation = request.POST.get('confirmation', '')
    if confirmation != "I confirm I want to archive this project":
        return HttpResponseBadRequest(
            "Confirmation text required: "
            '"I confirm I want to archive this project"'
        )

    from .tasks import perform_burial
    perform_burial.delay(session.id)

    session.status = 'burial_pending'
    session.save(update_fields=['status'])

    messages.success(
        request,
        f'Project "{board.name}" is being archived. '
        "You'll be notified when the process is complete."
    )
    return redirect('exit_protocol:cemetery')


@login_required
@require_POST
def dismiss_hospice_banner(request, board_id):
    board = get_object_or_404(Board, id=board_id)

    HospiceDismissal.objects.update_or_create(
        board=board,
        user=request.user,
        defaults={
            'dismissed_at': timezone.now(),
            'expires_at': timezone.now() + timedelta(days=7),
        }
    )
    return JsonResponse({'dismissed': True})


# ──────────────────────────
# Organ Transplant Views
# ──────────────────────────

@login_required
def organ_bank(request, board_id):
    board = get_object_or_404(Board, id=board_id)
    check_access_or_403(request.user, board)

    organs = ProjectOrgan.objects.filter(
        source_board=board
    ).order_by('-reusability_score')

    return render(request, 'exit_protocol/organ_bank.html', {
        'board': board,
        'organs': organs,
    })


@login_required
def organ_library(request):
    organs = ProjectOrgan.objects.filter(
        status='available'
    ).order_by('-reusability_score')

    # Filters
    organ_type = request.GET.get('organ_type')
    if organ_type:
        organs = organs.filter(organ_type=organ_type)

    min_score = request.GET.get('min_score')
    if min_score:
        try:
            organs = organs.filter(reusability_score__gte=float(min_score))
        except (ValueError, TypeError):
            pass

    source_project = request.GET.get('source_project')
    if source_project:
        organs = organs.filter(source_board__name__icontains=source_project)

    # Lazy compatibility scoring for target board
    target_board_id = request.GET.get('target_board_id')
    compatibility_scores = {}

    if target_board_id:
        try:
            target_board = Board.objects.get(id=target_board_id, is_archived=False)
            check_access_or_403(request.user, target_board)

            from django.core.cache import cache
            from . import ai_utils

            for organ in organs:
                cache_key = f'organ_compat:{organ.id}:{target_board_id}'
                score = cache.get(cache_key)

                if score is None:
                    try:
                        result = ai_utils.score_organ_compatibility(
                            request.user,
                            {
                                'organ_name': organ.name,
                                'organ_type': organ.get_organ_type_display(),
                                'organ_description': organ.description[:300],
                                'source_project': organ.source_board.name,
                                'target_project': target_board.name,
                                'target_description': target_board.description or '',
                            },
                            board_id=target_board.id,
                        )
                        score = result.get('compatibility_score', 0)
                        cache.set(cache_key, score, 1800)  # 30 min TTL
                    except Exception:
                        score = 0

                compatibility_scores[organ.id] = score
        except Board.DoesNotExist:
            pass

    return render(request, 'exit_protocol/organ_library.html', {
        'organs': organs,
        'target_board_id': target_board_id,
        'compatibility_scores': compatibility_scores,
        'organ_type_choices': ProjectOrgan.ORGAN_TYPE_CHOICES,
    })


@login_required
@require_POST
def transplant_organ(request, organ_id):
    organ = get_object_or_404(ProjectOrgan, id=organ_id, status='available')

    target_board_id = request.POST.get('target_board_id')
    if not target_board_id:
        return HttpResponseBadRequest("target_board_id is required")

    target_board = get_object_or_404(Board, id=target_board_id, is_archived=False)
    check_access_or_403(request.user, target_board)

    created_type = organ.organ_type
    created_id = None
    provenance_note = f"\n\n[Transplanted from \"{organ.source_board.name}\" on {timezone.now().date()}]"

    try:
        if organ.organ_type == 'task_template':
            from kanban.models import Task, Column
            target_column = Column.objects.filter(board=target_board).first()
            if target_column:
                task = Task.objects.create(
                    column=target_column,
                    title=organ.payload.get('title', organ.name),
                    description=(organ.payload.get('description', '') + provenance_note)[:2000],
                    priority=organ.payload.get('priority', 'medium'),
                    created_by=request.user,
                )
                created_id = task.id

        elif organ.organ_type == 'automation_rule':
            from kanban.automation_models import BoardAutomation
            auto = BoardAutomation.objects.create(
                board=target_board,
                trigger=organ.payload.get('trigger', ''),
                action=organ.payload.get('action', ''),
                is_active=True,
            )
            created_id = auto.id

        elif organ.organ_type == 'knowledge_entry':
            from knowledge_graph.models import MemoryNode
            node = MemoryNode.objects.create(
                board=target_board,
                title=organ.payload.get('title', organ.name),
                content=organ.payload.get('content', '') + provenance_note,
                node_type=organ.payload.get('node_type', 'lesson'),
                importance_score=organ.payload.get('importance_score', 0.5),
            )
            created_id = node.id

        elif organ.organ_type == 'role_definition':
            from kanban.permission_models import Role
            role = Role.objects.create(
                name=organ.payload.get('role_name', organ.name),
                description=(organ.payload.get('description', '') + provenance_note)[:500],
            )
            created_id = role.id

        else:
            # goal_framework, checklist, etc. → create as knowledge entry
            from knowledge_graph.models import MemoryNode
            node = MemoryNode.objects.create(
                board=target_board,
                title=organ.name,
                content=json.dumps(organ.payload, default=str) + provenance_note,
                node_type='lesson',
                importance_score=0.7,
            )
            created_id = node.id

    except Exception as e:
        logger.error(f"[ExitProtocol] Transplant failed for organ {organ_id}: {e}")
        return JsonResponse({'success': False, 'error': str(e)}, status=500)

    # Create audit record
    OrganTransplant.objects.create(
        organ=organ,
        target_board=target_board,
        transplanted_by=request.user,
        compatibility_score=0,
    )

    organ.status = 'transplanted'
    organ.save(update_fields=['status'])

    log_audit(
        action_type='board.updated',
        user=request.user,
        object_type='organ_transplant',
        object_id=organ.id,
        object_repr=f"Organ transplant: {organ.name} → {target_board.name}",
        board_id=target_board.id,
    )

    return JsonResponse({
        'success': True,
        'created_type': created_type,
        'created_id': created_id,
    })


@login_required
@require_POST
def reject_organ(request, organ_id):
    organ = get_object_or_404(ProjectOrgan, id=organ_id)
    organ.status = 'rejected'
    organ.save(update_fields=['status'])
    return JsonResponse({'rejected': True})


# ──────────────────────────
# Cemetery Views
# ──────────────────────────

@login_required
def cemetery(request):
    entries = CemeteryEntry.objects.all().order_by('-buried_at')

    # Search
    q = request.GET.get('q', '').strip()
    if q:
        entries = entries.filter(
            Q(autopsy_summary__icontains=q) | Q(project_name__icontains=q)
        )

    # Filters
    cause = request.GET.get('cause_of_death')
    if cause:
        entries = entries.filter(cause_of_death=cause)

    date_from = request.GET.get('date_from')
    if date_from:
        entries = entries.filter(buried_at__date__gte=date_from)

    date_to = request.GET.get('date_to')
    if date_to:
        entries = entries.filter(buried_at__date__lte=date_to)

    paginator = Paginator(entries, 20)
    page = request.GET.get('page')
    cemetery_entries = paginator.get_page(page)

    return render(request, 'exit_protocol/cemetery/index.html', {
        'cemetery_entries': cemetery_entries,
        'search_query': q,
        'selected_cause': cause,
        'cause_choices': CemeteryEntry.CAUSE_OF_DEATH_CHOICES,
    })


@login_required
def autopsy_report(request, entry_id):
    entry = get_object_or_404(CemeteryEntry, id=entry_id)

    # Get related organ transplants
    transplants = OrganTransplant.objects.filter(
        organ__source_board=entry.board
    ).select_related('organ', 'target_board', 'transplanted_by')

    return render(request, 'exit_protocol/cemetery/autopsy_report.html', {
        'entry': entry,
        'transplants': transplants,
    })


@login_required
@require_POST
def update_lessons(request, entry_id):
    entry = get_object_or_404(CemeteryEntry, id=entry_id)

    try:
        data = json.loads(request.body)
    except json.JSONDecodeError:
        return HttpResponseBadRequest("Invalid JSON")

    updated_fields = []

    if 'lessons_to_repeat' in data:
        val = data['lessons_to_repeat']
        if isinstance(val, list):
            entry.lessons_to_repeat = [
                {k: bleach.clean(str(v), strip=True) for k, v in item.items()}
                if isinstance(item, dict) else bleach.clean(str(item), strip=True)
                for item in val
            ]
        else:
            entry.lessons_to_repeat = bleach.clean(str(val), strip=True)
        updated_fields.append('lessons_to_repeat')

    if 'lessons_to_avoid' in data:
        val = data['lessons_to_avoid']
        if isinstance(val, list):
            entry.lessons_to_avoid = [
                {k: bleach.clean(str(v), strip=True) for k, v in item.items()}
                if isinstance(item, dict) else bleach.clean(str(item), strip=True)
                for item in val
            ]
        else:
            entry.lessons_to_avoid = bleach.clean(str(val), strip=True)
        updated_fields.append('lessons_to_avoid')

    if 'open_questions' in data:
        val = data['open_questions']
        if isinstance(val, list):
            entry.open_questions = [
                {k: bleach.clean(str(v), strip=True) for k, v in item.items()}
                if isinstance(item, dict) else bleach.clean(str(item), strip=True)
                for item in val
            ]
        else:
            entry.open_questions = bleach.clean(str(val), strip=True)
        updated_fields.append('open_questions')

    if updated_fields:
        entry.save(update_fields=updated_fields)

        log_audit(
            action_type='board.updated',
            user=request.user,
            object_type='cemetery_entry',
            object_id=entry.id,
            object_repr=f"Lessons updated: {entry.project_name}",
            board_id=entry.board_id,
            changes={'fields_updated': updated_fields},
        )

    return JsonResponse({'success': True})


@login_required
@require_POST
def resurrect_project(request, entry_id):
    entry = get_object_or_404(CemeteryEntry, id=entry_id)

    if entry.is_resurrected:
        return HttpResponseBadRequest("This project has already been resurrected.")

    # 1. Create new Board
    new_board = Board.objects.create(
        name=f"{entry.project_name} — Resurrected",
        description=(
            f"Resurrected from archived project on {timezone.now().date()}. "
            f"Original cause of death: {entry.get_cause_of_death_display()}."
        ),
        created_by=request.user,
    )
    # Add creator as member
    new_board.members.add(request.user)

    # 2. Import surviving knowledge nodes
    try:
        from knowledge_graph.models import MemoryNode
        surviving = MemoryNode.objects.filter(
            board=entry.board,
            node_type__in=['decision', 'lesson'],
        )
        for node in surviving:
            MemoryNode.objects.create(
                board=new_board,
                title=node.title,
                content=node.content,
                node_type=node.node_type,
                importance_score=node.importance_score,
            )
    except Exception as e:
        logger.warning(f"[ExitProtocol] Knowledge import failed during resurrection: {e}")

    # 3. Auto-create PreMortemAnalysis from risk_event nodes
    try:
        from knowledge_graph.models import MemoryNode
        from kanban.premortem_models import PreMortemAnalysis

        risk_nodes = MemoryNode.objects.filter(
            board=entry.board,
            node_type='risk_event',
        )
        if risk_nodes.exists():
            scenarios = []
            for rn in risk_nodes:
                scenarios.append({
                    'risk_level': 'high',
                    'scenario': rn.title,
                    'root_cause': rn.content[:500] if rn.content else 'Materialized in predecessor project',
                    'mitigation': 'Review the full autopsy report for context.',
                    'source_note': (
                        '\u26a0\ufe0f This risk destroyed the original project '
                        'this board was resurrected from.'
                    ),
                    'cemetery_entry_id': entry.id,
                })

            PreMortemAnalysis.objects.create(
                board=new_board,
                analysis_json={'scenarios': scenarios},
                created_by=request.user,
            )
    except Exception as e:
        logger.warning(f"[ExitProtocol] Pre-mortem creation failed during resurrection: {e}")

    # 4. Mark original as resurrected
    entry.is_resurrected = True
    entry.resurrected_as = new_board
    entry.save(update_fields=['is_resurrected', 'resurrected_as'])

    # 5. Audit log
    log_audit(
        action_type='board.updated',
        user=request.user,
        object_type='cemetery_entry',
        object_id=entry.id,
        object_repr=f"Project resurrection: {entry.project_name}",
        board_id=new_board.id,
        changes={
            'action': 'project_resurrection',
            'new_board_id': new_board.id,
            'original_board_id': entry.board_id,
        },
    )

    messages.success(
        request,
        f'Project "{entry.project_name}" has been resurrected as a new board. '
        'Risk knowledge from the original project has been imported.'
    )
    return redirect('board_detail', board_id=new_board.id)


@login_required
def export_autopsy_pdf(request, entry_id):
    from reportlab.lib.pagesizes import letter
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib.units import inch
    from reportlab.platypus import (
        SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, PageBreak,
    )
    from reportlab.lib import colors
    from reportlab.lib.enums import TA_CENTER

    entry = get_object_or_404(CemeteryEntry, id=entry_id)

    buffer = BytesIO()
    doc = SimpleDocTemplate(
        buffer, pagesize=letter,
        rightMargin=72, leftMargin=72, topMargin=72, bottomMargin=18,
    )

    elements = []
    styles = getSampleStyleSheet()
    title_style = ParagraphStyle(
        'CustomTitle',
        parent=styles['Heading1'],
        fontSize=18,
        textColor=colors.HexColor('#1a1a1a'),
        spaceAfter=12,
        alignment=TA_CENTER,
    )

    # Header
    elements.append(Paragraph(f"Autopsy Report: {entry.project_name}", title_style))
    buried_date = entry.buried_at.strftime('%B %d, %Y') if entry.buried_at else 'N/A'
    elements.append(Paragraph(f"Archived on {buried_date}", styles['Normal']))
    elements.append(Spacer(1, 0.3 * inch))

    # Section 1: Vital Stats
    completion_pct = (
        round(entry.completed_tasks / entry.total_tasks * 100)
        if entry.total_tasks else 0
    )
    vital_data = [
        ['Metric', 'Value'],
        ['Project Name', entry.project_name],
        ['Team Size', str(entry.team_size or 'N/A')],
        ['Duration', f"{entry.start_date or '?'} to {entry.end_date or '?'}"],
        ['Completion', f"{completion_pct}% ({entry.completed_tasks}/{entry.total_tasks})"],
        ['Budget Allocated', str(entry.budget_allocated or 'N/A')],
        ['Budget Spent', str(entry.budget_spent or 'N/A')],
    ]
    vital_table = Table(vital_data, colWidths=[2.5 * inch, 4 * inch])
    vital_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
        ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, 0), 11),
        ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
        ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
        ('GRID', (0, 0), (-1, -1), 1, colors.black),
    ]))
    elements.append(vital_table)
    elements.append(Spacer(1, 0.3 * inch))

    # Section 2: Cause of Death
    elements.append(Paragraph("<b>Cause of Death:</b>", styles['Heading2']))
    cause_display = entry.get_cause_of_death_display()
    elements.append(Paragraph(
        f"{cause_display} — {entry.ai_cause_rationale or 'No rationale provided.'}",
        styles['Normal'],
    ))
    elements.append(Spacer(1, 0.2 * inch))

    # Section 3: Timeline of Decline
    if entry.decline_timeline:
        elements.append(Paragraph("<b>Timeline of Decline:</b>", styles['Heading2']))
        for event in entry.decline_timeline:
            evt_date = event.get('date', '?')
            evt_desc = event.get('event', event.get('event_description', ''))
            severity = event.get('severity', '?')
            elements.append(Paragraph(
                f"<b>{evt_date}:</b> {evt_desc} (Severity: {severity}/5)",
                styles['Normal'],
            ))
        elements.append(Spacer(1, 0.2 * inch))

    # Page break before lessons
    elements.append(PageBreak())

    # Section 4: Lessons Learned
    elements.append(Paragraph("<b>Lessons Learned</b>", styles['Heading2']))

    elements.append(Paragraph("<u>Lessons to Repeat:</u>", styles['Normal']))
    if entry.lessons_to_repeat:
        if isinstance(entry.lessons_to_repeat, list):
            for item in entry.lessons_to_repeat:
                text = item.get('lesson', str(item)) if isinstance(item, dict) else str(item)
                elements.append(Paragraph(f"• {text}", styles['Normal']))
        else:
            elements.append(Paragraph(str(entry.lessons_to_repeat), styles['Normal']))
    else:
        elements.append(Paragraph("[Not specified]", styles['Normal']))
    elements.append(Spacer(1, 0.1 * inch))

    elements.append(Paragraph("<u>Lessons to Avoid:</u>", styles['Normal']))
    if entry.lessons_to_avoid:
        if isinstance(entry.lessons_to_avoid, list):
            for item in entry.lessons_to_avoid:
                text = item.get('lesson', str(item)) if isinstance(item, dict) else str(item)
                elements.append(Paragraph(f"• {text}", styles['Normal']))
        else:
            elements.append(Paragraph(str(entry.lessons_to_avoid), styles['Normal']))
    else:
        elements.append(Paragraph("[Not specified]", styles['Normal']))
    elements.append(Spacer(1, 0.1 * inch))

    elements.append(Paragraph("<u>Open Questions:</u>", styles['Normal']))
    if entry.open_questions:
        if isinstance(entry.open_questions, list):
            for item in entry.open_questions:
                text = item.get('question', str(item)) if isinstance(item, dict) else str(item)
                elements.append(Paragraph(f"• {text}", styles['Normal']))
        else:
            elements.append(Paragraph(str(entry.open_questions), styles['Normal']))
    else:
        elements.append(Paragraph("[Not specified]", styles['Normal']))
    elements.append(Spacer(1, 0.3 * inch))

    # Section 5: Organ Transplants
    transplants = OrganTransplant.objects.filter(
        organ__source_board=entry.board
    ).select_related('organ', 'target_board')
    if transplants.exists():
        elements.append(Paragraph("<b>Organ Transplants:</b>", styles['Heading2']))
        for tx in transplants:
            tx_date = tx.transplanted_at.strftime('%Y-%m-%d') if tx.transplanted_at else 'N/A'
            elements.append(Paragraph(
                f"• {tx.organ.name} ({tx.organ.get_organ_type_display()}) "
                f"→ {tx.target_board.name} on {tx_date}",
                styles['Normal'],
            ))

    # Footer
    elements.append(Spacer(1, 0.5 * inch))
    elements.append(Paragraph(
        f"<i>Generated by PrizmAI Exit Protocol | "
        f"{timezone.now().strftime('%Y-%m-%d %H:%M')}</i>",
        styles['Normal'],
    ))

    doc.build(elements)
    buffer.seek(0)

    safe_name = entry.project_name.replace(' ', '_').replace('"', '')
    response = HttpResponse(buffer.getvalue(), content_type='application/pdf')
    response['Content-Disposition'] = (
        f'attachment; filename="autopsy_{safe_name}_'
        f'{timezone.now().strftime("%Y%m%d")}.pdf"'
    )
    return response
