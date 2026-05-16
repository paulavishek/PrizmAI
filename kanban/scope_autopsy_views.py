"""
Scope Creep Autopsy Views

Provides four endpoints:
  1. Dashboard — shows locked / ready / generating / results state
  2. Run      — triggers the Celery autopsy task
  3. Status   — lightweight poll endpoint
  4. Export   — PDF download of the report
"""
import logging
from collections import Counter, defaultdict
from io import BytesIO

from django.conf import settings
from django.contrib.auth.decorators import login_required
from django.http import HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, render
from django.utils import timezone
from django.views.decorators.http import require_POST

import json

from kanban.models import Board, Task
from kanban.scope_autopsy_models import ScopeAutopsyReport, TaskScopeReason
from kanban.utils.scope_autopsy import calculate_baseline, has_scope_change_history
from kanban.audit_utils import log_audit
from api.ai_usage_utils import check_ai_quota, require_ai_quota

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# 1. Dashboard (main page)
# ---------------------------------------------------------------------------
@login_required
def scope_autopsy_dashboard(request, board_id):
    """
    Render the Scope Autopsy tab.

    Three states:
      A. Locked  — no scope changes detected
      B. Ready   — scope changes exist, no report (or stale report)
      C. Results — a completed report is available
    Plus an intermediate state D (Generating) handled client-side via polling.
    """
    board = get_object_or_404(Board, id=board_id)

    has_changes = has_scope_change_history(board)
    baseline = calculate_baseline(board)
    current_task_count = Task.objects.filter(column__board=board, item_type='task').count()

    # Growth calculation
    if baseline['task_count'] > 0:
        growth_pct = round(
            ((current_task_count - baseline['task_count']) / baseline['task_count']) * 100, 1
        )
    else:
        growth_pct = 0.0

    latest_report = (
        ScopeAutopsyReport.objects.filter(board=board)
        .order_by('-created_at')
        .first()
    )

    # Auto-expire reports stuck in 'generating' for over 5 minutes
    from datetime import timedelta
    if (
        latest_report
        and latest_report.status == 'generating'
        and latest_report.created_at < timezone.now() - timedelta(minutes=5)
    ):
        latest_report.status = 'failed'
        latest_report.ai_summary = 'Analysis timed out. The task may not have been processed by the worker. Please try again.'
        latest_report.save(update_fields=['status', 'ai_summary'])

    # Determine state
    if latest_report and latest_report.status == 'generating':
        state = 'generating'
    elif latest_report and latest_report.status == 'complete':
        state = 'results'
    elif latest_report and latest_report.status == 'failed':
        state = 'failed'
    elif has_changes and growth_pct > 0:
        state = 'ready'
    else:
        state = 'locked'

    # AI quota check
    has_quota = True
    if request.user.is_authenticated:
        has_quota, _, _ = check_ai_quota(request.user)

    # Enrich report data for template
    enriched_events = []
    if latest_report and latest_report.status == 'complete':
        # Pre-fetch all TaskScopeReason for this board (one query) so we can
        # annotate each task_added event with the reason the user recorded.
        reasons_qs = list(
            TaskScopeReason.objects.filter(board=board).select_related('task')
        )
        reason_by_task_id = {r.task_id: r for r in reasons_qs}
        # Secondary index keyed by (task_created_date, created_by_id) so that
        # multi-task daily groups (where source_object_id is only task[0]) can
        # still surface a representative reason.
        reasons_by_day_user = defaultdict(list)
        for r in reasons_qs:
            day_user_key = (r.task.created_at.date(), r.task.created_by_id)
            reasons_by_day_user[day_user_key].append(r)
        REASON_DISPLAY = dict(TaskScopeReason.REASON_CHOICES)

        for ev in latest_report.timeline_events.all():
            scope_reason_label = ''
            scope_reason_note = ''

            if ev.source_type == 'task_added':
                # Primary: direct lookup by source task (handles all single-task events)
                reason_obj = reason_by_task_id.get(ev.source_object_id) if ev.source_object_id else None
                if reason_obj and reason_obj.reason != 'unrecorded':
                    scope_reason_label = REASON_DISPLAY.get(reason_obj.reason, reason_obj.reason)
                    scope_reason_note = reason_obj.note or ''
                else:
                    # Secondary: aggregate by (day, user) for multi-task daily groups
                    day_user_key = (ev.event_date.date(), ev.added_by_id)
                    day_reasons = [
                        r for r in reasons_by_day_user.get(day_user_key, [])
                        if r.reason != 'unrecorded'
                    ]
                    if day_reasons:
                        dominant = Counter(r.reason for r in day_reasons).most_common(1)[0][0]
                        scope_reason_label = REASON_DISPLAY.get(dominant, dominant)
                        notes = list({r.note for r in day_reasons if (r.note or '').strip()})
                        scope_reason_note = '; '.join(notes[:2])

            enriched_events.append({
                'date': ev.event_date,
                'title': ev.title,
                'description': ev.description,
                'source_type': ev.source_type,
                'get_source_type_display': ev.get_source_type_display(),
                'tasks_added': ev.tasks_added,
                'net_task_change': ev.net_task_change,
                'is_major_event': ev.is_major_event,
                'estimated_delay_days': ev.estimated_delay_days,
                'estimated_budget_impact': ev.estimated_budget_impact,
                'cumulative_task_count': ev.cumulative_task_count,
                'added_by_name': (
                    ev.added_by.get_full_name() or ev.added_by.username
                ) if ev.added_by else '',
                'scope_reason_label': scope_reason_label,
                'scope_reason_note': scope_reason_note,
            })

    # Fix 1: Detect baseline mismatch between Scope Dashboard and Autopsy
    baseline_mismatch = None
    if latest_report and latest_report.status == 'complete':
        dashboard_baseline_count = board.baseline_task_count
        dashboard_baseline_date = board.baseline_set_date
        autopsy_baseline_count = latest_report.baseline_task_count
        if (dashboard_baseline_count is not None
                and dashboard_baseline_count != autopsy_baseline_count):
            baseline_mismatch = {
                'dashboard_count': dashboard_baseline_count,
                'dashboard_date': dashboard_baseline_date,
                'autopsy_count': autopsy_baseline_count,
            }

    # Fix 3: Calculate undocumented scope gap
    undocumented_gap = 0
    if latest_report and latest_report.status == 'complete' and enriched_events:
        documented_task_count = latest_report.baseline_task_count + sum(
            ev['net_task_change'] for ev in enriched_events
        )
        undocumented_gap = max(0, latest_report.final_task_count - documented_task_count)

    context = {
        'board': board,
        'state': state,
        'has_changes': has_changes,
        'baseline': baseline,
        'current_task_count': current_task_count,
        'growth_pct': growth_pct,
        'latest_report': latest_report,
        'enriched_events': enriched_events,
        'has_quota': has_quota,
        'is_archived': board.is_archived,
        'baseline_mismatch': baseline_mismatch,
        'undocumented_gap': undocumented_gap,
    }
    return render(request, 'kanban/scope_autopsy_dashboard.html', context)


# ---------------------------------------------------------------------------
# 2. Run autopsy (POST)
# ---------------------------------------------------------------------------
@login_required
@require_POST
@require_ai_quota('scope_autopsy')
def run_scope_autopsy(request, board_id):
    """Trigger a new Scope Autopsy Celery task."""
    board = get_object_or_404(Board, id=board_id)

    if not has_scope_change_history(board):
        return JsonResponse({
            'success': False,
            'error': 'No scope changes detected. Autopsy requires scope growth beyond baseline.',
        }, status=400)

    # Prevent duplicate runs — but allow re-run if the existing generating report is stale (>5 min)
    from datetime import timedelta
    stale_cutoff = timezone.now() - timedelta(minutes=5)
    stale_running = ScopeAutopsyReport.objects.filter(
        board=board,
        status='generating',
        created_at__lt=stale_cutoff,
    )
    if stale_running.exists():
        # Expire stale reports so the new run can proceed
        stale_running.update(
            status='failed',
            ai_summary='Analysis timed out before a new run was requested.',
        )

    running = ScopeAutopsyReport.objects.filter(
        board=board, status='generating',
    ).exists()
    if running:
        return JsonResponse({
            'success': False,
            'error': 'An autopsy is already generating for this board.',
        }, status=409)

    # Create report in the view so we can return report_id immediately
    report = ScopeAutopsyReport.objects.create(
        board=board,
        created_by=request.user,
        status='generating',
    )

    from kanban.tasks.scope_autopsy_tasks import generate_scope_autopsy
    generate_scope_autopsy.delay(report.id)

    return JsonResponse({
        'success': True,
        'message': 'Scope autopsy generation started.',
        'report_id': report.id,
    })


# ---------------------------------------------------------------------------
# 3. Status poll (GET)
# ---------------------------------------------------------------------------
@login_required
def scope_autopsy_status(request, report_id):
    """Return the current status of a report (for polling)."""
    from datetime import timedelta
    report = get_object_or_404(ScopeAutopsyReport, id=report_id)

    # Auto-expire reports stuck in 'generating' for over 5 minutes
    if (
        report.status == 'generating'
        and report.created_at < timezone.now() - timedelta(minutes=5)
    ):
        report.status = 'failed'
        report.ai_summary = (
            'Analysis timed out. The AI did not respond in time. '
            'Please try re-running the autopsy.'
        )
        report.save(update_fields=['status', 'ai_summary'])

    data = {
        'status': report.status,
        'report_id': report.id,
    }

    if report.status == 'complete':
        data.update({
            'baseline_task_count': report.baseline_task_count,
            'final_task_count': report.final_task_count,
            'total_scope_growth_percentage': report.total_scope_growth_percentage,
            'total_delay_days': report.total_delay_days,
            'total_budget_impact': float(report.total_budget_impact),
            'ai_summary': report.ai_summary,
            'pattern_analysis': report.pattern_analysis,
            'recommendations': report.recommendations,
        })
    elif report.status == 'failed':
        data['error'] = report.ai_summary  # failure message stored here

    return JsonResponse(data)


# ---------------------------------------------------------------------------
# 4. Export PDF (GET)
# ---------------------------------------------------------------------------
@login_required
def scope_autopsy_export(request, report_id):
    """Generate and return a PDF of the autopsy report."""
    from reportlab.lib.pagesizes import letter
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib.units import inch
    from reportlab.platypus import (
        SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle,
    )
    from reportlab.lib import colors
    from reportlab.lib.enums import TA_CENTER, TA_JUSTIFY

    report = get_object_or_404(ScopeAutopsyReport, id=report_id)
    if report.status != 'complete':
        return JsonResponse({'error': 'Report is not complete.'}, status=400)

    board = report.board

    # Audit log
    try:
        log_audit(
            'scope_autopsy.exported',
            user=request.user,
            request=request,
            object_type='ScopeAutopsyReport',
            object_id=report.id,
            object_repr=str(report),
            board_id=board.id,
        )
    except Exception:
        logger.warning("Audit log for scope_autopsy.exported failed", exc_info=True)

    # Build PDF
    buffer = BytesIO()
    doc = SimpleDocTemplate(
        buffer, pagesize=letter,
        rightMargin=72, leftMargin=72,
        topMargin=72, bottomMargin=18,
    )

    styles = getSampleStyleSheet()
    title_style = ParagraphStyle(
        'AutopsyTitle', parent=styles['Heading1'],
        fontSize=22, textColor=colors.HexColor('#e67e22'),
        spaceAfter=28, alignment=TA_CENTER,
    )
    heading_style = ParagraphStyle(
        'AutopsyHeading', parent=styles['Heading2'],
        fontSize=14, textColor=colors.HexColor('#2c3e50'),
        spaceAfter=10, spaceBefore=14,
    )
    body_style = ParagraphStyle(
        'AutopsyBody', parent=styles['BodyText'],
        fontSize=10, alignment=TA_JUSTIFY, spaceAfter=10,
    )
    footer_style = ParagraphStyle(
        'AutopsyFooter', parent=styles['Normal'],
        fontSize=8, textColor=colors.grey, alignment=TA_CENTER,
    )

    elements = []

    # Title
    elements.append(Paragraph(f"Scope Autopsy Report: {board.name}", title_style))
    elements.append(Spacer(1, 0.15 * inch))

    # Summary table
    summary_data = [
        ['Baseline Tasks', str(report.baseline_task_count)],
        ['Final Tasks', str(report.final_task_count)],
        ['Scope Growth', f"+{report.total_scope_growth_percentage:.1f}%"],
        ['Estimated Delay', f"+{report.total_delay_days} days"],
        ['Estimated Cost Impact', f"+${report.total_budget_impact:,.2f}"],
        ['Analyzed', report.created_at.strftime('%B %d, %Y at %I:%M %p')],
        ['Run by', (
            report.created_by.get_full_name() or report.created_by.username
        ) if report.created_by else 'System'],
    ]
    summary_table = Table(summary_data, colWidths=[2.2 * inch, 3.8 * inch])
    summary_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (0, -1), colors.HexColor('#ecf0f1')),
        ('FONTNAME', (0, 0), (0, -1), 'Helvetica-Bold'),
        ('FONTNAME', (1, 0), (1, -1), 'Helvetica'),
        ('FONTSIZE', (0, 0), (-1, -1), 10),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('LEFTPADDING', (0, 0), (-1, -1), 10),
        ('TOPPADDING', (0, 0), (-1, -1), 8),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
    ]))
    elements.append(summary_table)
    elements.append(Spacer(1, 0.25 * inch))

    # AI Summary
    if report.ai_summary:
        elements.append(Paragraph("Executive Summary", heading_style))
        elements.append(Paragraph(
            report.ai_summary.replace('\n', '<br/>'), body_style,
        ))

    # Timeline Events — fetch once as a list for both visual and table
    events = list(report.timeline_events.all())
    documented_task_count = report.baseline_task_count + sum(ev.net_task_change for ev in events)
    undocumented_gap = max(0, report.final_task_count - documented_task_count)

    if events:
        elements.append(Paragraph("Scope Growth Timeline", heading_style))

        # Fix 4: Visual horizontal timeline drawing
        elements.append(_build_scope_timeline_drawing(report, events, undocumented_gap))
        elements.append(Spacer(1, 0.15 * inch))

        # Detailed events table
        event_header = [['Date', 'Event', 'Tasks', 'Delay', 'Cost']]
        event_rows = []
        for ev in events:
            event_rows.append([
                ev.event_date.strftime('%b %d, %Y'),
                Paragraph(ev.title[:60], body_style),
                f"+{ev.net_task_change}",
                f"+{ev.estimated_delay_days}d",
                f"+${ev.estimated_budget_impact:,.0f}",
            ])

        event_table = Table(
            event_header + event_rows,
            colWidths=[1.1 * inch, 2.4 * inch, 0.7 * inch, 0.7 * inch, 1.1 * inch],
        )
        event_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#e67e22')),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, 0), 9),
            ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('LEFTPADDING', (0, 0), (-1, -1), 6),
            ('TOPPADDING', (0, 1), (-1, -1), 6),
            ('BOTTOMPADDING', (0, 1), (-1, -1), 6),
        ]))
        elements.append(event_table)
        elements.append(Spacer(1, 0.2 * inch))

    # Pattern Analysis
    if report.pattern_analysis:
        elements.append(Paragraph("Pattern Analysis", heading_style))
        elements.append(Paragraph(
            report.pattern_analysis.replace('\n', '<br/>'), body_style,
        ))

    # Recommendations
    if report.recommendations:
        elements.append(Paragraph("Recommendations", heading_style))
        for i, rec in enumerate(report.recommendations, 1):
            if isinstance(rec, dict):
                rec_text = (
                    f"<b>{i}. {rec.get('title', 'Recommendation')}</b><br/>"
                    f"{rec.get('description', '')}<br/>"
                    f"<i>Applies to: {rec.get('applies_to', 'general')}</i>"
                )
            else:
                rec_text = f"<b>{i}.</b> {rec}"
            elements.append(Paragraph(rec_text, body_style))

    # Footer
    elements.append(Spacer(1, 0.3 * inch))
    elements.append(Paragraph(
        f"Generated on {timezone.now().strftime('%B %d, %Y at %I:%M %p')} | PrizmAI Scope Autopsy",
        footer_style,
    ))

    doc.build(elements)
    pdf = buffer.getvalue()
    buffer.close()

    safe_name = board.name.replace(' ', '_')[:50]
    response = HttpResponse(content_type='application/pdf')
    response['Content-Disposition'] = (
        f'attachment; filename="scope_autopsy_{safe_name}_{report.created_at:%Y%m%d}.pdf"'
    )
    response.write(pdf)
    return response


# ---------------------------------------------------------------------------
# Helper: build a ReportLab Drawing for the scope growth timeline (Fix 4)
# ---------------------------------------------------------------------------
def _build_scope_timeline_drawing(report, events, undocumented_gap=0):
    """
    Return a ReportLab Drawing containing a horizontal scope growth timeline.
    Nodes: Baseline → documented events → [undocumented gap?] → Now
    """
    from reportlab.graphics.shapes import Drawing, Line, Circle, String
    from reportlab.lib.colors import HexColor, white, grey as rl_grey

    nodes = []
    nodes.append({
        'label': 'Baseline',
        'sublabel': f"{report.baseline_task_count} tasks",
        'fill': HexColor('#28a745'),
        'text': 'B',
        'dashed': False,
    })
    for ev in events:
        is_major = ev.net_task_change >= 3
        label = ev.title[:20] + ('…' if len(ev.title) > 20 else '')
        nodes.append({
            'label': label,
            'sublabel': f"+{ev.net_task_change}",
            'fill': HexColor('#dc3545') if is_major else HexColor('#e0a800'),
            'text': f"+{ev.net_task_change}",
            'dashed': False,
        })
    if undocumented_gap > 0:
        nodes.append({
            'label': 'Undocumented growth',
            'sublabel': f"+{undocumented_gap} tasks",
            'fill': HexColor('#e9ecef'),
            'text': f"+{undocumented_gap}",
            'dashed': True,
        })
    nodes.append({
        'label': 'Now',
        'sublabel': f"{report.final_task_count} tasks",
        'fill': HexColor('#6c757d'),
        'text': 'N',
        'dashed': False,
    })

    n = len(nodes)
    r = 14  # circle radius (points)
    drawing_width = 460
    drawing_height = 78
    line_y = 38  # y of the connecting line / circle centers

    start_x = float(r + 10)
    end_x = float(drawing_width - r - 10)
    spacing = (end_x - start_x) / max(n - 1, 1)

    drawing = Drawing(drawing_width, drawing_height)

    # Horizontal connector line
    if n > 1:
        drawing.add(Line(start_x, line_y, end_x, line_y,
                         strokeColor=rl_grey, strokeWidth=1))

    for i, node in enumerate(nodes):
        cx = start_x + i * spacing
        cy = float(line_y)

        is_dashed = node.get('dashed', False)
        circle = Circle(
            cx, cy, float(r),
            fillColor=node['fill'],
            strokeColor=HexColor('#6c757d') if is_dashed else white,
            strokeWidth=1.5,
        )
        if is_dashed:
            circle.strokeDashArray = [3, 2]
        drawing.add(circle)

        text_color = HexColor('#6c757d') if is_dashed else white
        drawing.add(String(cx, cy - 3.5, node['text'],
                           fontSize=7, fillColor=text_color,
                           textAnchor='middle'))

        # Label above circle
        drawing.add(String(cx, cy + float(r) + 4, node['label'],
                           fontSize=6, fillColor=HexColor('#2c3e50'),
                           textAnchor='middle'))

        # Sublabel below circle
        drawing.add(String(cx, cy - float(r) - 11, node['sublabel'],
                           fontSize=6, fillColor=rl_grey,
                           textAnchor='middle'))

    return drawing


# ---------------------------------------------------------------------------
# 5. Save scope change reason (POST) — Fix 2
# ---------------------------------------------------------------------------
@login_required
@require_POST
def save_scope_reason(request, task_id):
    """Record why a task was added to the project scope after creation."""
    task = get_object_or_404(Task, id=task_id)
    board = task.column.board

    try:
        data = json.loads(request.body)
    except (ValueError, TypeError):
        data = {}

    reason = data.get('reason', 'unrecorded')
    note = (data.get('note') or '').strip()

    valid_reasons = {r[0] for r in TaskScopeReason.REASON_CHOICES}
    if reason not in valid_reasons:
        reason = 'unrecorded'

    TaskScopeReason.objects.update_or_create(
        task=task,
        defaults={
            'board': board,
            'reason': reason,
            'note': note,
            'recorded_by': request.user,
        },
    )
    return JsonResponse({'success': True})
