"""
API Views for AI-powered features in TaskFlow

This module contains API view functions that handle requests from 
the front-end for AI-powered features.
"""
import json
import logging
import time
from datetime import timedelta
from django.http import JsonResponse
from django.views.decorators.http import require_http_methods
from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404
from django.utils import timezone

# Setup logging
logger = logging.getLogger(__name__)

from kanban.models import Task, Comment, Board, Column, TaskActivity
from accounts.models import UserProfile
from django.contrib.auth.models import User
from kanban.utils.ai_utils import (
    generate_task_description, 
    summarize_comments,
    suggest_lean_classification,
    summarize_board_analytics,
    suggest_task_priority,
    predict_realistic_deadline,
    recommend_board_columns,
    suggest_task_breakdown,
    analyze_workflow_optimization,
    summarize_task_details,
    analyze_critical_path,
    predict_task_completion,
    generate_project_timeline,
    calculate_task_risk_score,
    generate_risk_mitigation_suggestions,
    assess_task_dependencies_and_risks
)
from api.ai_usage_utils import track_ai_request, check_ai_quota

@login_required
@require_http_methods(["POST"])
def generate_task_description_api(request):
    """
    API endpoint to generate a task description using AI
    """
    start_time = time.time()
    try:
        # Check AI quota
        has_quota, quota, remaining = check_ai_quota(request.user)
        if not has_quota:
            return JsonResponse({
                'error': 'AI usage quota exceeded. Please upgrade or wait for quota reset.',
                'quota_exceeded': True
            }, status=429)
        
        data = json.loads(request.body)
        title = data.get('title', '')
        
        if not title:
            return JsonResponse({'error': 'Title is required'}, status=400)
            
        # Call AI util function to generate description
        description = generate_task_description(title)
        
        if not description:
            # Track failed request
            response_time_ms = int((time.time() - start_time) * 1000)
            track_ai_request(
                user=request.user,
                feature='task_description',
                request_type='generate',
                success=False,
                error_message='Failed to generate description',
                response_time_ms=response_time_ms
            )
            return JsonResponse({'error': 'Failed to generate description'}, status=500)
        
        # Track successful request
        response_time_ms = int((time.time() - start_time) * 1000)
        track_ai_request(
            user=request.user,
            feature='task_description',
            request_type='generate',
            success=True,
            response_time_ms=response_time_ms
        )
            
        return JsonResponse({'description': description})
    except Exception as e:
        response_time_ms = int((time.time() - start_time) * 1000)
        track_ai_request(
            user=request.user,
            feature='task_description',
            request_type='generate',
            success=False,
            error_message=str(e),
            response_time_ms=response_time_ms
        )
        return JsonResponse({'error': str(e)}, status=500)

@login_required
@require_http_methods(["GET"])
def summarize_comments_api(request, task_id):
    """
    API endpoint to summarize task comments using AI
    """
    start_time = time.time()
    try:
        # Check AI quota
        has_quota, quota, remaining = check_ai_quota(request.user)
        if not has_quota:
            return JsonResponse({
                'error': 'AI usage quota exceeded. Please upgrade or wait for quota reset.',
                'quota_exceeded': True
            }, status=429)
        
        # Get the task and verify user access
        task = get_object_or_404(Task, id=task_id)
        board = task.column.board
        
        # Check if user has access to this board/task
        if not (board.created_by == request.user or request.user in board.members.all()):
            return JsonResponse({'error': 'Access denied'}, status=403)
        
        # Format comments for AI
        comments_data = []
        for comment in task.comments.all().order_by('created_at'):
            comments_data.append({
                'user': comment.user.username,
                'content': comment.content,
                'created_at': comment.created_at.strftime('%Y-%m-%d %H:%M')
            })
            
        if not comments_data:
            return JsonResponse({'summary': 'No comments to summarize.'})
            
        # Generate summary
        summary = summarize_comments(comments_data)
        
        if not summary:
            response_time_ms = int((time.time() - start_time) * 1000)
            track_ai_request(
                user=request.user,
                feature='comment_summary',
                request_type='summarize',
                board_id=board.id,
                success=False,
                error_message='Failed to generate summary',
                response_time_ms=response_time_ms
            )
            return JsonResponse({'error': 'Failed to generate summary'}, status=500)
        
        # Track successful request
        response_time_ms = int((time.time() - start_time) * 1000)
        track_ai_request(
            user=request.user,
            feature='comment_summary',
            request_type='summarize',
            board_id=board.id,
            success=True,
            response_time_ms=response_time_ms
        )
        
        return JsonResponse({'summary': summary})
    except Exception as e:
        response_time_ms = int((time.time() - start_time) * 1000)
        track_ai_request(
            user=request.user,
            feature='comment_summary',
            request_type='summarize',
            success=False,
            error_message=str(e),
            response_time_ms=response_time_ms
        )
        return JsonResponse({'error': str(e)}, status=500)

@login_required
@require_http_methods(["POST"])
def suggest_lss_classification_api(request):
    """
    API endpoint to suggest Lean Six Sigma classification for a task
    """
    start_time = time.time()
    try:
        # Check AI quota
        has_quota, quota, remaining = check_ai_quota(request.user)
        if not has_quota:
            return JsonResponse({
                'error': 'AI usage quota exceeded. Please upgrade or wait for quota reset.',
                'quota_exceeded': True
            }, status=429)
        
        data = json.loads(request.body)
        title = data.get('title', '')
        description = data.get('description', '')
        
        if not title:
            return JsonResponse({'error': 'Title is required'}, status=400)
            
        # Call AI util function to suggest classification
        suggestion = suggest_lean_classification(title, description)
        
        if not suggestion:
            response_time_ms = int((time.time() - start_time) * 1000)
            track_ai_request(
                user=request.user,
                feature='lean_classification',
                request_type='suggest',
                success=False,
                error_message='Failed to suggest classification',
                response_time_ms=response_time_ms
            )
            return JsonResponse({'error': 'Failed to suggest classification'}, status=500)
        
        # Track successful request
        response_time_ms = int((time.time() - start_time) * 1000)
        track_ai_request(
            user=request.user,
            feature='lean_classification',
            request_type='suggest',
            success=True,
            response_time_ms=response_time_ms
        )
            
        return JsonResponse(suggestion)
    except Exception as e:
        response_time_ms = int((time.time() - start_time) * 1000)
        track_ai_request(
            user=request.user,
            feature='lean_classification',
            request_type='suggest',
            success=False,
            error_message=str(e),
            response_time_ms=response_time_ms
        )
        return JsonResponse({'error': str(e)}, status=500)

@login_required
@require_http_methods(["GET"])
def summarize_board_analytics_api(request, board_id):
    """
    API endpoint to summarize board analytics using AI
    """
    start_time = time.time()
    try:
        # Check AI quota
        has_quota, quota, remaining = check_ai_quota(request.user)
        if not has_quota:
            return JsonResponse({
                'error': 'AI usage quota exceeded. Please upgrade or wait for quota reset.',
                'quota_exceeded': True
            }, status=429)
        
        # Get the board and verify user access
        board = get_object_or_404(Board, id=board_id)
        
        # Check if user has access to this board
        if not (board.created_by == request.user or request.user in board.members.all()):
            return JsonResponse({'error': 'Access denied'}, status=403)
        
        # Gather analytics data (same as in board_analytics view)
        from django.db.models import Count, Q
        from django.utils import timezone
        from datetime import timedelta
        
        # Get all tasks for this board
        all_tasks = Task.objects.filter(column__board=board)
        total_tasks = all_tasks.count()
        
        # Completed tasks (based on progress = 100%)
        completed_count = Task.objects.filter(
            column__board=board, 
            progress=100
        ).count()
        
        # Calculate productivity
        total_progress_percentage = 0
        for task in all_tasks:
            # Use actual task progress, defaulting to 0 if None
            progress = task.progress if task.progress is not None else 0
            total_progress_percentage += progress
        
        productivity = 0
        if total_tasks > 0:
            productivity = (total_progress_percentage / (total_tasks * 100)) * 100
        
        # Overdue and upcoming tasks
        today = timezone.now().date()
        overdue_tasks = Task.objects.filter(
            column__board=board,
            due_date__date__lt=today
        ).exclude(progress=100)
        
        upcoming_tasks = Task.objects.filter(
            column__board=board,
            due_date__date__gte=today,
            due_date__date__lte=today + timedelta(days=7)
        )
        
        # Lean Six Sigma metrics
        value_added_count = Task.objects.filter(
            column__board=board, 
            labels__name='Value-Added', 
            labels__category='lean'
        ).count()
        
        necessary_nva_count = Task.objects.filter(
            column__board=board, 
            labels__name='Necessary NVA', 
            labels__category='lean'
        ).count()
        
        waste_count = Task.objects.filter(
            column__board=board, 
            labels__name='Waste/Eliminate', 
            labels__category='lean'
        ).count()
        
        total_categorized = value_added_count + necessary_nva_count + waste_count
        value_added_percentage = 0
        if total_categorized > 0:
            value_added_percentage = (value_added_count / total_categorized) * 100
        
        # Task distribution by column
        columns = Column.objects.filter(board=board)
        tasks_by_column = []
        for column in columns:
            count = Task.objects.filter(column=column).count()
            tasks_by_column.append({'name': column.name, 'count': count})
        
        # Task distribution by priority
        priority_queryset = Task.objects.filter(column__board=board).values('priority').annotate(
            count=Count('id')
        ).order_by('priority')
        
        tasks_by_priority = []
        for item in priority_queryset:
            priority_name = dict(Task.PRIORITY_CHOICES).get(item['priority'], item['priority'])
            tasks_by_priority.append({'priority': priority_name, 'count': item['count']})
        
        # Task distribution by user
        user_queryset = Task.objects.filter(column__board=board).values(
            'assigned_to__username'
        ).annotate(count=Count('id')).order_by('-count')
        
        tasks_by_user = []
        for item in user_queryset:
            username = item['assigned_to__username'] or 'Unassigned'
            completed_user_tasks = Task.objects.filter(
                column__board=board,
                assigned_to__username=item['assigned_to__username'],
                column__name__icontains='done'
            ).count()
            
            user_completion_rate = 0
            if item['count'] > 0:
                user_completion_rate = (completed_user_tasks / item['count']) * 100
                
            tasks_by_user.append({
                'username': username,
                'count': item['count'],
                'completion_rate': int(user_completion_rate)
            })
        
        # Prepare analytics data for AI
        analytics_data = {
            'total_tasks': total_tasks,
            'completed_count': completed_count,
            'productivity': round(productivity, 1),
            'overdue_count': overdue_tasks.count(),
            'upcoming_count': upcoming_tasks.count(),
            'value_added_percentage': round(value_added_percentage, 1),
            'total_categorized': total_categorized,
            'tasks_by_lean_category': [
                {'name': 'Value-Added', 'count': value_added_count},
                {'name': 'Necessary NVA', 'count': necessary_nva_count},
                {'name': 'Waste/Eliminate', 'count': waste_count}
            ],
            'tasks_by_column': tasks_by_column,
            'tasks_by_priority': tasks_by_priority,
            'tasks_by_user': tasks_by_user
        }
        
        # Generate analytics summary
        summary = summarize_board_analytics(analytics_data)
        
        if not summary:
            response_time_ms = int((time.time() - start_time) * 1000)
            track_ai_request(
                user=request.user,
                feature='board_analytics',
                request_type='summarize',
                board_id=board.id,
                success=False,
                error_message='Failed to generate analytics summary',
                response_time_ms=response_time_ms
            )
            return JsonResponse({'error': 'Failed to generate analytics summary'}, status=500)
        
        # Track successful request
        response_time_ms = int((time.time() - start_time) * 1000)
        track_ai_request(
            user=request.user,
            feature='board_analytics',
            request_type='summarize',
            board_id=board.id,
            success=True,
            response_time_ms=response_time_ms
        )
            
        return JsonResponse({'summary': summary})
    except Exception as e:
        response_time_ms = int((time.time() - start_time) * 1000)
        track_ai_request(
            user=request.user,
            feature='board_analytics',
            request_type='summarize',
            board_id=board_id if 'board' in locals() else None,
            success=False,
            error_message=str(e),
            response_time_ms=response_time_ms
        )
        return JsonResponse({'error': str(e)}, status=500)

@login_required
@require_http_methods(["GET"])
def download_analytics_summary_pdf(request, board_id):
    """
    API endpoint to download board analytics summary as PDF
    """
    try:
        from reportlab.lib.pagesizes import letter, A4
        from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
        from reportlab.lib.units import inch
        from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, PageBreak
        from reportlab.lib import colors
        from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_JUSTIFY
        from io import BytesIO
        from datetime import datetime
        
        # Get the board and verify user access
        board = get_object_or_404(Board, id=board_id)
        
        # Check if user has access to this board
        if not (board.created_by == request.user or request.user in board.members.all()):
            return JsonResponse({'error': 'Access denied'}, status=403)
        
        # Check if there's a summary to download (get it from session or regenerate)
        # For now, we'll fetch the analytics data and generate fresh summary
        from django.db.models import Count, Q
        from django.utils import timezone
        from datetime import timedelta
        
        # Get all tasks for this board
        all_tasks = Task.objects.filter(column__board=board)
        total_tasks = all_tasks.count()
        
        # Completed tasks
        completed_count = Task.objects.filter(
            column__board=board, 
            progress=100
        ).count()
        
        # Calculate productivity
        total_progress_percentage = 0
        for task in all_tasks:
            progress = task.progress if task.progress is not None else 0
            total_progress_percentage += progress
        
        productivity = 0
        if total_tasks > 0:
            productivity = (total_progress_percentage / (total_tasks * 100)) * 100
        
        # Overdue and upcoming tasks
        today = timezone.now().date()
        overdue_tasks = Task.objects.filter(
            column__board=board,
            due_date__date__lt=today
        ).exclude(progress=100)
        
        upcoming_tasks = Task.objects.filter(
            column__board=board,
            due_date__date__gte=today,
            due_date__date__lte=today + timedelta(days=7)
        )
        
        # Lean Six Sigma metrics
        value_added_count = Task.objects.filter(
            column__board=board, 
            labels__name='Value-Added', 
            labels__category='lean'
        ).count()
        
        necessary_nva_count = Task.objects.filter(
            column__board=board, 
            labels__name='Necessary NVA', 
            labels__category='lean'
        ).count()
        
        waste_count = Task.objects.filter(
            column__board=board, 
            labels__name='Waste/Eliminate', 
            labels__category='lean'
        ).count()
        
        total_categorized = value_added_count + necessary_nva_count + waste_count
        value_added_percentage = 0
        if total_categorized > 0:
            value_added_percentage = (value_added_count / total_categorized) * 100
        
        # Task distribution by column
        columns = Column.objects.filter(board=board)
        tasks_by_column = []
        for column in columns:
            count = Task.objects.filter(column=column).count()
            tasks_by_column.append({'name': column.name, 'count': count})
        
        # Task distribution by priority
        priority_queryset = Task.objects.filter(column__board=board).values('priority').annotate(
            count=Count('id')
        ).order_by('priority')
        
        tasks_by_priority = []
        for item in priority_queryset:
            priority_name = dict(Task.PRIORITY_CHOICES).get(item['priority'], item['priority'])
            tasks_by_priority.append({'priority': priority_name, 'count': item['count']})
        
        # Task distribution by user
        user_queryset = Task.objects.filter(
            column__board=board
        ).values('assigned_to__username').annotate(
            count=Count('id')
        ).order_by('-count')
        
        tasks_by_user = []
        for item in user_queryset:
            username = item['assigned_to__username'] or 'Unassigned'
            user_tasks = Task.objects.filter(
                column__board=board, 
                assigned_to__username=username
            )
            completed_by_user = user_tasks.filter(progress=100).count()
            user_completion_rate = 0
            if item['count'] > 0:
                user_completion_rate = (completed_by_user / item['count']) * 100
            
            tasks_by_user.append({
                'username': username,
                'count': item['count'],
                'completion_rate': int(user_completion_rate)
            })
        
        # Prepare analytics data for AI
        analytics_data = {
            'total_tasks': total_tasks,
            'completed_count': completed_count,
            'productivity': round(productivity, 1),
            'overdue_count': overdue_tasks.count(),
            'upcoming_count': upcoming_tasks.count(),
            'value_added_percentage': round(value_added_percentage, 1),
            'total_categorized': total_categorized,
            'tasks_by_lean_category': [
                {'name': 'Value-Added', 'count': value_added_count},
                {'name': 'Necessary NVA', 'count': necessary_nva_count},
                {'name': 'Waste/Eliminate', 'count': waste_count}
            ],
            'tasks_by_column': tasks_by_column,
            'tasks_by_priority': tasks_by_priority,
            'tasks_by_user': tasks_by_user
        }
        
        # Generate analytics summary using AI
        from kanban.utils.ai_utils import summarize_board_analytics
        summary = summarize_board_analytics(analytics_data)
        
        if not summary:
            return JsonResponse({'error': 'Failed to generate analytics summary'}, status=500)
        
        # Create PDF
        buffer = BytesIO()
        doc = SimpleDocTemplate(buffer, pagesize=letter, rightMargin=72, leftMargin=72, topMargin=72, bottomMargin=18)
        
        # Container for PDF elements
        elements = []
        
        # Define styles
        styles = getSampleStyleSheet()
        
        # Custom styles
        title_style = ParagraphStyle(
            'CustomTitle',
            parent=styles['Heading1'],
            fontSize=24,
            textColor=colors.HexColor('#2c3e50'),
            spaceAfter=30,
            alignment=TA_CENTER,
            fontName='Helvetica-Bold'
        )
        
        subtitle_style = ParagraphStyle(
            'CustomSubtitle',
            parent=styles['Normal'],
            fontSize=12,
            textColor=colors.HexColor('#7f8c8d'),
            spaceAfter=20,
            alignment=TA_CENTER,
            fontName='Helvetica'
        )
        
        heading_style = ParagraphStyle(
            'CustomHeading',
            parent=styles['Heading2'],
            fontSize=16,
            textColor=colors.HexColor('#34495e'),
            spaceAfter=12,
            spaceBefore=12,
            fontName='Helvetica-Bold'
        )
        
        body_style = ParagraphStyle(
            'CustomBody',
            parent=styles['Normal'],
            fontSize=11,
            textColor=colors.HexColor('#2c3e50'),
            alignment=TA_JUSTIFY,
            spaceAfter=12,
            leading=16,
            fontName='Helvetica'
        )
        
        # Add title
        title = Paragraph(f"<b>{board.name}</b>", title_style)
        elements.append(title)
        
        # Add subtitle
        subtitle = Paragraph(f"AI Analytics Summary - Generated on {datetime.now().strftime('%B %d, %Y at %I:%M %p')}", subtitle_style)
        elements.append(subtitle)
        elements.append(Spacer(1, 0.3 * inch))
        
        # Add key metrics table
        metrics_heading = Paragraph("<b>Key Metrics Overview</b>", heading_style)
        elements.append(metrics_heading)
        
        metrics_data = [
            ['Metric', 'Value'],
            ['Total Tasks', str(total_tasks)],
            ['Completed Tasks', str(completed_count)],
            ['Productivity Rate', f"{round(productivity, 1)}%"],
            ['Overdue Tasks', str(overdue_tasks.count())],
            ['Tasks Due Soon (7 days)', str(upcoming_tasks.count())],
            ['Value-Added Percentage', f"{round(value_added_percentage, 1)}%"]
        ]
        
        metrics_table = Table(metrics_data, colWidths=[3.5*inch, 2.5*inch])
        metrics_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#3498db')),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, 0), 12),
            ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
            ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
            ('GRID', (0, 0), (-1, -1), 1, colors.grey),
            ('FONTNAME', (0, 1), (-1, -1), 'Helvetica'),
            ('FONTSIZE', (0, 1), (-1, -1), 10),
            ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#f8f9fa')])
        ]))
        elements.append(metrics_table)
        elements.append(Spacer(1, 0.3 * inch))
        
        # Add AI Summary
        summary_heading = Paragraph("<b>AI-Generated Analytics Summary</b>", heading_style)
        elements.append(summary_heading)
        
        # Process the summary text - convert markdown-like formatting to proper paragraphs
        import re
        
        # Split summary into sections
        summary_lines = summary.split('\n')
        for line in summary_lines:
            line = line.strip()
            if not line:
                elements.append(Spacer(1, 0.1 * inch))
                continue
            
            # Check if it's a heading (starts with ##)
            if line.startswith('##'):
                heading_text = line.replace('##', '').strip()
                heading_para = Paragraph(f"<b>{heading_text}</b>", heading_style)
                elements.append(heading_para)
            # Check if it's a subheading (starts with single #)
            elif line.startswith('#') and not line.startswith('##'):
                heading_text = line.replace('#', '').strip()
                heading_para = Paragraph(f"<b>{heading_text}</b>", heading_style)
                elements.append(heading_para)
            # Check if it's a bullet point
            elif line.startswith('*') or line.startswith('-'):
                bullet_text = line.lstrip('*- ').strip()
                # Replace **bold** with <b>bold</b>
                bullet_text = re.sub(r'\*\*(.*?)\*\*', r'<b>\1</b>', bullet_text)
                bullet_para = Paragraph(f"• {bullet_text}", body_style)
                elements.append(bullet_para)
            else:
                # Regular text - replace **bold** with <b>bold</b>
                formatted_line = re.sub(r'\*\*(.*?)\*\*', r'<b>\1</b>', line)
                text_para = Paragraph(formatted_line, body_style)
                elements.append(text_para)
        
        # Build PDF
        doc.build(elements)
        
        # Get PDF from buffer
        pdf = buffer.getvalue()
        buffer.close()
        
        # Create response
        from django.http import HttpResponse
        response = HttpResponse(pdf, content_type='application/pdf')
        response['Content-Disposition'] = f'attachment; filename="{board.name}_Analytics_Summary_{datetime.now().strftime("%Y%m%d_%H%M%S")}.pdf"'
        
        return response
        
    except Exception as e:
        import traceback
        print(f"Error generating PDF: {str(e)}")
        print(traceback.format_exc())
        return JsonResponse({'error': str(e)}, status=500)

@login_required
@require_http_methods(["POST"])
def suggest_task_priority_api(request):
    """
    API endpoint to suggest optimal priority for a task using AI
    """
    start_time = time.time()
    try:
        # Check AI quota
        has_quota, quota, remaining = check_ai_quota(request.user)
        if not has_quota:
            return JsonResponse({
                'error': 'AI usage quota exceeded. Please upgrade or wait for quota reset.',
                'quota_exceeded': True
            }, status=429)
        
        data = json.loads(request.body)
        task_id = data.get('task_id')
        title = data.get('title', '')
        description = data.get('description', '')
        due_date = data.get('due_date', '')
        
        if not title:
            return JsonResponse({'error': 'Title is required'}, status=400)
        
        # Get board - either from task or from request
        board = None
        if task_id:
            try:
                task = get_object_or_404(Task, id=task_id)
                if task.column:
                    board = task.column.board
                else:
                    # Task exists but has no column yet - try board_id from request
                    board_id = data.get('board_id')
                    if board_id:
                        board = get_object_or_404(Board, id=board_id)
            except Exception as e:
                logger.error(f"Error getting task: {str(e)}")
                return JsonResponse({'error': 'Task not found'}, status=404)
        else:
            # For new tasks, get board from request
            board_id = data.get('board_id')
            if board_id:
                board = get_object_or_404(Board, id=board_id)
            else:
                return JsonResponse({'error': 'Board ID is required for new tasks'}, status=400)
        
        # Check if we have a board
        if not board:
            return JsonResponse({'error': 'Could not determine board for task'}, status=400)
        
        # Check access
        if not (board.created_by == request.user or request.user in board.members.all()):
            return JsonResponse({'error': 'Access denied'}, status=403)
        
        # Gather board context for priority suggestion
        from django.db.models import Count
        all_tasks = Task.objects.filter(column__board=board)
        
        board_context = {
            'total_tasks': all_tasks.count(),
            'high_priority_count': all_tasks.filter(priority='high').count(),
            'urgent_count': all_tasks.filter(priority='urgent').count(),
            'overdue_count': all_tasks.filter(due_date__lt=timezone.now()).exclude(progress=100).count(),
            'upcoming_deadlines': all_tasks.filter(
                due_date__gte=timezone.now(),
                due_date__lte=timezone.now() + timedelta(days=7)
            ).count()
        }
        
        task_data = {
            'title': title,
            'description': description,
            'due_date': due_date,
            'current_priority': data.get('current_priority', 'medium')
        }
        
        # Call AI function
        suggestion = suggest_task_priority(task_data, board_context)
        
        if not suggestion:
            response_time_ms = int((time.time() - start_time) * 1000)
            track_ai_request(
                user=request.user,
                feature='task_priority',
                request_type='suggest',
                board_id=board.id,
                success=False,
                error_message='Failed to suggest priority',
                response_time_ms=response_time_ms
            )
            return JsonResponse({'error': 'Failed to suggest priority'}, status=500)
        
        # Track successful request
        response_time_ms = int((time.time() - start_time) * 1000)
        track_ai_request(
            user=request.user,
            feature='task_priority',
            request_type='suggest',
            board_id=board.id,
            success=True,
            response_time_ms=response_time_ms
        )
            
        return JsonResponse(suggestion)
    except Exception as e:
        response_time_ms = int((time.time() - start_time) * 1000)
        board_id_val = board.id if 'board' in locals() and board else None
        track_ai_request(
            user=request.user,
            feature='task_priority',
            request_type='suggest',
            board_id=board_id_val,
            success=False,
            error_message=str(e),
            response_time_ms=response_time_ms
        )
        return JsonResponse({'error': str(e)}, status=500)

@login_required
@require_http_methods(["POST"])
def predict_deadline_api(request):
    """
    API endpoint to predict realistic deadline for a task using AI
    """
    start_time = time.time()
    try:
        # Check AI quota
        has_quota, quota, remaining = check_ai_quota(request.user)
        if not has_quota:
            return JsonResponse({
                'error': 'AI usage quota exceeded. Please upgrade or wait for quota reset.',
                'quota_exceeded': True
            }, status=429)
        
        data = json.loads(request.body)
        task_id = data.get('task_id')
        title = data.get('title', '')
        description = data.get('description', '')
        priority = data.get('priority', 'medium')
        assigned_to = data.get('assigned_to', 'Unassigned')
        
        if not title:
            return JsonResponse({'error': 'Title is required'}, status=400)
        
        # Get board context for deadline prediction
        board_id = data.get('board_id')
        if task_id:
            task = get_object_or_404(Task, id=task_id)
            board = task.column.board
        elif board_id:
            board = get_object_or_404(Board, id=board_id)
        else:
            return JsonResponse({'error': 'Board ID or Task ID is required'}, status=400)
        
        # Check access
        if not (board.created_by == request.user or request.user in board.members.all()):
            return JsonResponse({'error': 'Access denied'}, status=403)
        
        # Gather team context for deadline prediction
        from django.db.models import Avg
        from django.utils import timezone
        
        # Calculate average completion times (simplified calculation)
        completed_tasks = Task.objects.filter(
            column__board=board, 
            progress=100
        )
        
        team_avg_completion = 5  # Default fallback
        assignee_avg_completion = 5  # Default fallback
        
        if completed_tasks.exists():
            # Simple calculation based on created_at to completion
            total_days = 0
            count = 0
            for task in completed_tasks:
                if task.updated_at and task.created_at:
                    days_to_complete = (task.updated_at - task.created_at).days
                    if days_to_complete > 0:  # Avoid zero or negative days
                        total_days += days_to_complete
                        count += 1
            
            if count > 0:
                team_avg_completion = total_days / count
        
        # Get assignee's current workload
        assignee_current_tasks = 0
        if assigned_to and assigned_to != 'Unassigned':
            from django.contrib.auth.models import User
            try:
                assignee_user = User.objects.get(username=assigned_to)
                assignee_current_tasks = Task.objects.filter(
                    column__board=board,
                    assigned_to=assignee_user
                ).exclude(progress=100).count()
            except User.DoesNotExist:
                pass
        
        team_context = {
            'assignee_avg_completion_days': assignee_avg_completion,
            'team_avg_completion_days': team_avg_completion,
            'assignee_current_tasks': assignee_current_tasks,
            'similar_tasks_avg_days': team_avg_completion,  # Simplified
            'upcoming_holidays': []  # Could be enhanced to include actual holidays
        }
        
        task_data = {
            'title': title,
            'description': description,
            'priority': priority,
            'assigned_to': assigned_to
        }
        
        # Call AI function
        prediction = predict_realistic_deadline(task_data, team_context)
        
        if not prediction:
            # Track failed request
            response_time_ms = int((time.time() - start_time) * 1000)
            track_ai_request(
                user=request.user,
                feature='deadline_prediction',
                request_type='predict',
                board_id=board.id,
                success=False,
                error_message='Failed to predict deadline',
                response_time_ms=response_time_ms
            )
            return JsonResponse({'error': 'Failed to predict deadline'}, status=500)
        
        # Track successful request
        response_time_ms = int((time.time() - start_time) * 1000)
        track_ai_request(
            user=request.user,
            feature='deadline_prediction',
            request_type='predict',
            board_id=board.id,
            success=True,
            response_time_ms=response_time_ms
        )
            
        return JsonResponse(prediction)
    except Exception as e:
        response_time_ms = int((time.time() - start_time) * 1000)
        track_ai_request(
            user=request.user,
            feature='deadline_prediction',
            request_type='predict',
            success=False,
            error_message=str(e),
            response_time_ms=response_time_ms
        )
        return JsonResponse({'error': str(e)}, status=500)

@login_required
@require_http_methods(["POST"])
def recommend_columns_api(request):
    """
    API endpoint to recommend optimal column structure for a board using AI
    """
    start_time = time.time()
    board_id_for_tracking = None
    try:
        # Check AI quota
        has_quota, quota, remaining = check_ai_quota(request.user)
        if not has_quota:
            return JsonResponse({
                'error': 'AI usage quota exceeded. Please upgrade or wait for quota reset.',
                'quota_exceeded': True
            }, status=429)
        
        data = json.loads(request.body)
        board_id = data.get('board_id')
        
        if board_id:
            # Existing board - get current structure
            board = get_object_or_404(Board, id=board_id)
            board_id_for_tracking = board.id
            
            # Check access
            if not (board.created_by == request.user or request.user in board.members.all()):
                return JsonResponse({'error': 'Access denied'}, status=403)
            
            existing_columns = [col.name for col in board.columns.all()]
            board_name = board.name
            board_description = board.description
            team_size = board.members.count() + 1  # +1 for creator
        else:
            # New board recommendations
            board_name = data.get('name', '')
            board_description = data.get('description', '')
            team_size = data.get('team_size', 1)
            existing_columns = []
        
        if not board_name:
            return JsonResponse({'error': 'Board name is required'}, status=400)
        
        board_data = {
            'name': board_name,
            'description': board_description,
            'team_size': team_size,
            'project_type': data.get('project_type', 'general'),
            'organization_type': data.get('organization_type', 'general'),
            'existing_columns': existing_columns
        }
        
        # Call AI function
        recommendation = recommend_board_columns(board_data)
        
        if not recommendation:
            # Track failed request
            response_time_ms = int((time.time() - start_time) * 1000)
            track_ai_request(
                user=request.user,
                feature='column_recommendations',
                request_type='recommend',
                board_id=board_id_for_tracking,
                success=False,
                error_message='Failed to recommend columns',
                response_time_ms=response_time_ms
            )
            return JsonResponse({'error': 'Failed to recommend columns'}, status=500)
        
        # Track successful request
        response_time_ms = int((time.time() - start_time) * 1000)
        track_ai_request(
            user=request.user,
            feature='column_recommendations',
            request_type='recommend',
            board_id=board_id_for_tracking,
            success=True,
            response_time_ms=response_time_ms
        )
            
        return JsonResponse(recommendation)
    except Exception as e:
        response_time_ms = int((time.time() - start_time) * 1000)
        track_ai_request(
            user=request.user,
            feature='column_recommendations',
            request_type='recommend',
            board_id=board_id_for_tracking,
            success=False,
            error_message=str(e),
            response_time_ms=response_time_ms
        )
        return JsonResponse({'error': str(e)}, status=500)

@login_required
@require_http_methods(["POST"])
def suggest_task_breakdown_api(request):
    """
    API endpoint to suggest automated breakdown of complex tasks using AI
    """
    start_time = time.time()
    board_id_for_tracking = None
    try:
        # Check AI quota
        has_quota, quota, remaining = check_ai_quota(request.user)
        if not has_quota:
            return JsonResponse({
                'error': 'AI usage quota exceeded. Please upgrade or wait for quota reset.',
                'quota_exceeded': True
            }, status=429)
        
        data = json.loads(request.body)
        task_id = data.get('task_id')
        title = data.get('title', '')
        description = data.get('description', '')
        
        if not title:
            return JsonResponse({'error': 'Title is required'}, status=400)
        
        # If task_id provided, verify access
        if task_id:
            task = get_object_or_404(Task, id=task_id)
            board = task.column.board
            board_id_for_tracking = board.id
            
            # Check access
            if not (board.created_by == request.user or request.user in board.members.all()):
                return JsonResponse({'error': 'Access denied'}, status=403)
        
        task_data = {
            'title': title,
            'description': description,
            'priority': data.get('priority', 'medium'),
            'due_date': data.get('due_date', ''),
            'estimated_effort': data.get('estimated_effort', '')
        }
        
        # Call AI function
        breakdown = suggest_task_breakdown(task_data)
        
        if not breakdown:
            # Track failed request
            response_time_ms = int((time.time() - start_time) * 1000)
            track_ai_request(
                user=request.user,
                feature='task_breakdown',
                request_type='suggest',
                board_id=board_id_for_tracking,
                success=False,
                error_message='Failed to suggest task breakdown',
                response_time_ms=response_time_ms
            )
            return JsonResponse({'error': 'Failed to suggest task breakdown'}, status=500)
        
        # Track successful request
        response_time_ms = int((time.time() - start_time) * 1000)
        track_ai_request(
            user=request.user,
            feature='task_breakdown',
            request_type='suggest',
            board_id=board_id_for_tracking,
            success=True,
            response_time_ms=response_time_ms
        )
            
        return JsonResponse(breakdown)
    except Exception as e:
        response_time_ms = int((time.time() - start_time) * 1000)
        track_ai_request(
            user=request.user,
            feature='task_breakdown',
            request_type='suggest',
            board_id=board_id_for_tracking,
            success=False,
            error_message=str(e),
            response_time_ms=response_time_ms
        )
        return JsonResponse({'error': str(e)}, status=500)

@login_required
@require_http_methods(["POST"])
def analyze_workflow_optimization_api(request):
    """
    API endpoint to analyze workflow and suggest optimizations using AI
    """
    start_time = time.time()
    try:
        # Check AI quota
        has_quota, quota, remaining = check_ai_quota(request.user)
        if not has_quota:
            return JsonResponse({
                'error': 'AI usage quota exceeded. Please upgrade or wait for quota reset.',
                'quota_exceeded': True
            }, status=429)
        
        data = json.loads(request.body)
        board_id = data.get('board_id')
        
        if not board_id:
            return JsonResponse({'error': 'Board ID is required'}, status=400)
        
        board = get_object_or_404(Board, id=board_id)
        
        # Check access
        if not (board.created_by == request.user or request.user in board.members.all()):
            return JsonResponse({'error': 'Access denied'}, status=403)
        
        # Gather comprehensive board analytics (similar to existing analytics)
        from django.db.models import Count, Avg
        from django.utils import timezone
        from datetime import timedelta
        
        all_tasks = Task.objects.filter(column__board=board)
        total_tasks = all_tasks.count()
        
        # Calculate average completion time
        completed_tasks = all_tasks.filter(progress=100)
        avg_completion_time = 5  # Default
        if completed_tasks.exists():
            total_days = 0
            count = 0
            for task in completed_tasks:
                if task.updated_at and task.created_at:
                    days = (task.updated_at - task.created_at).days
                    if days > 0:
                        total_days += days
                        count += 1
            if count > 0:
                avg_completion_time = total_days / count
        
        # Task distribution by column
        columns = Column.objects.filter(board=board)
        tasks_by_column = []
        for column in columns:
            count = Task.objects.filter(column=column).count()
            tasks_by_column.append({'name': column.name, 'count': count})
        
        # Task distribution by priority
        priority_queryset = all_tasks.values('priority').annotate(count=Count('id'))
        tasks_by_priority = []
        for item in priority_queryset:
            priority_name = dict(Task.PRIORITY_CHOICES).get(item['priority'], item['priority'])
            tasks_by_priority.append({'priority': priority_name, 'count': item['count']})
        
        # Task distribution by user
        user_queryset = all_tasks.values('assigned_to__username').annotate(count=Count('id'))
        tasks_by_user = []
        for item in user_queryset:
            username = item['assigned_to__username'] or 'Unassigned'
            completed_user_tasks = completed_tasks.filter(
                assigned_to__username=item['assigned_to__username']
            ).count()
            
            completion_rate = 0
            if item['count'] > 0:
                completion_rate = (completed_user_tasks / item['count']) * 100
                
            tasks_by_user.append({
                'username': username,
                'count': item['count'],
                'completion_rate': int(completion_rate)
            })
        
        # Calculate productivity
        total_progress = sum(task.progress if task.progress is not None else 0 for task in all_tasks)
        productivity = 0
        if total_tasks > 0:
            productivity = total_progress / total_tasks
        
        # Overdue count
        overdue_count = all_tasks.filter(
            due_date__lt=timezone.now()
        ).exclude(progress=100).count()
        
        board_analytics = {
            'total_tasks': total_tasks,
            'tasks_by_column': tasks_by_column,
            'tasks_by_priority': tasks_by_priority,
            'tasks_by_user': tasks_by_user,
            'avg_completion_time_days': avg_completion_time,
            'overdue_count': overdue_count,
            'productivity': productivity,
            'weekly_velocity': []  # Could be enhanced with historical data
        }
        
        # Call AI function
        optimization = analyze_workflow_optimization(board_analytics)
        
        if not optimization:
            # Track failed request
            response_time_ms = int((time.time() - start_time) * 1000)
            track_ai_request(
                user=request.user,
                feature='workflow_optimization',
                request_type='analyze',
                board_id=board.id,
                success=False,
                error_message='Failed to analyze workflow',
                response_time_ms=response_time_ms
            )
            return JsonResponse({'error': 'Failed to analyze workflow'}, status=500)
        
        # Track successful request
        response_time_ms = int((time.time() - start_time) * 1000)
        track_ai_request(
            user=request.user,
            feature='workflow_optimization',
            request_type='analyze',
            board_id=board.id,
            success=True,
            response_time_ms=response_time_ms
        )
            
        return JsonResponse(optimization)
    except Exception as e:
        response_time_ms = int((time.time() - start_time) * 1000)
        track_ai_request(
            user=request.user,
            feature='workflow_optimization',
            request_type='analyze',
            board_id=board.id if 'board' in locals() else None,
            success=False,
            error_message=str(e),
            response_time_ms=response_time_ms
        )
        return JsonResponse({'error': str(e)}, status=500)

@login_required
@require_http_methods(["POST"])
def create_subtasks_api(request):
    """
    API endpoint to create multiple tasks from AI-generated subtask breakdown
    """
    try:
        data = json.loads(request.body)
        board_id = data.get('board_id')
        column_id = data.get('column_id')
        subtasks = data.get('subtasks', [])
        original_task_title = data.get('original_task_title', '')
        if not board_id or not subtasks:
            return JsonResponse({'error': 'Missing required fields (board_id, subtasks)'}, status=400)
              # Verify user has access to the board
        board = get_object_or_404(Board, id=board_id)
        if not (request.user in board.members.all() or request.user == board.created_by):
            return JsonResponse({'error': 'Access denied'}, status=403)
            
        # Get column - if not specified, use first column
        if column_id:
            column = get_object_or_404(Column, id=column_id, board=board)
        else:
            # Default to first column (usually "To Do")
            column = Column.objects.filter(board=board).order_by('position').first()
            if not column:
                return JsonResponse({'error': 'No columns found in board'}, status=400)
        
        created_tasks = []
        errors = []
        
        for i, subtask_data in enumerate(subtasks):
            try:
                # Extract subtask information
                title = subtask_data.get('title', '').strip()
                description = subtask_data.get('description', '').strip()
                estimated_effort = subtask_data.get('estimated_effort', '')
                priority = subtask_data.get('priority', 'medium').lower()
                
                # Validate data
                if not title:
                    errors.append(f"Subtask {i+1}: Title is required")
                    continue
                
                # Ensure priority is valid
                valid_priorities = ['low', 'medium', 'high', 'urgent']
                if priority not in valid_priorities:
                    priority = 'medium'
                
                # Parse estimated effort to get due date (if provided)
                due_date = None
                if estimated_effort and 'day' in estimated_effort.lower():
                    try:
                        # Extract number of days from strings like "2 days", "1 day"
                        import re
                        days_match = re.search(r'(\d+)', estimated_effort)
                        if days_match:
                            days = int(days_match.group(1))
                            due_date = timezone.now() + timedelta(days=days)
                    except:
                        pass  # If parsing fails, just leave due_date as None
                
                # Enhance description with effort information
                if estimated_effort:
                    if description:
                        description += f"\n\n**Estimated Effort:** {estimated_effort}"
                    else:
                        description = f"**Estimated Effort:** {estimated_effort}"
                
                # Add reference to original task
                if original_task_title:
                    description += f"\n\n*Subtask of: {original_task_title}*"
                
                # Create the task
                task = Task.objects.create(
                    title=title,
                    description=description,
                    column=column,
                    priority=priority,
                    due_date=due_date,
                    created_by=request.user,
                    position=Task.objects.filter(column=column).count()  # Add to end
                )
                
                created_tasks.append({
                    'id': task.id,
                    'title': task.title,
                    'priority': task.priority,
                    'due_date': task.due_date.isoformat() if task.due_date else None
                })
                
            except Exception as e:
                errors.append(f"Subtask {i+1}: {str(e)}")
          # Prepare response
        response_data = {
            'success': True,
            'created_count': len(created_tasks),
            'total_subtasks': len(subtasks),
            'created_tasks': created_tasks
        }
        
        if errors:
            response_data['errors'] = errors
            response_data['partial_success'] = True
        
        return JsonResponse(response_data)
        
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)


@login_required
@require_http_methods(["POST"])
def calculate_task_risk_api(request):
    """
    API endpoint to calculate AI-powered risk score for a task
    """
    start_time = time.time()
    try:
        # Check AI quota
        has_quota, quota, remaining = check_ai_quota(request.user)
        if not has_quota:
            return JsonResponse({
                'error': 'AI usage quota exceeded. Please upgrade or wait for quota reset.',
                'quota_exceeded': True
            }, status=429)
        
        data = json.loads(request.body)
        task_id = data.get('task_id')
        title = data.get('title', '')
        description = data.get('description', '')
        priority = data.get('priority', 'medium')
        board_id = data.get('board_id')
        
        if not title:
            return JsonResponse({'error': 'Title is required'}, status=400)
        
        # If task_id provided, verify access
        if task_id:
            task = get_object_or_404(Task, id=task_id)
            board = task.column.board
        elif board_id:
            board = get_object_or_404(Board, id=board_id)
        else:
            return JsonResponse({'error': 'Board ID or Task ID is required'}, status=400)
        
        # Check access
        if not (board.created_by == request.user or request.user in board.members.all()):
            return JsonResponse({'error': 'Access denied'}, status=403)
        
        # Get board context
        board_context = f"Board: {board.name}. Description: {board.description or 'N/A'}"
        
        # Calculate risk score
        risk_analysis = calculate_task_risk_score(title, description, priority, board_context)
        
        if not risk_analysis:
            response_time_ms = int((time.time() - start_time) * 1000)
            track_ai_request(
                user=request.user,
                feature='risk_analysis',
                request_type='calculate',
                board_id=board.id,
                success=False,
                error_message='Failed to calculate risk score',
                response_time_ms=response_time_ms
            )
            return JsonResponse({'error': 'Failed to calculate risk score'}, status=500)
        
        # Track successful request
        response_time_ms = int((time.time() - start_time) * 1000)
        track_ai_request(
            user=request.user,
            feature='risk_analysis',
            request_type='calculate',
            board_id=board.id,
            success=True,
            response_time_ms=response_time_ms
        )
        
        # If task_id provided, save the analysis to the task
        if task_id:
            task.risk_likelihood = risk_analysis.get('likelihood', {}).get('score')
            task.risk_impact = risk_analysis.get('impact', {}).get('score')
            task.risk_score = risk_analysis.get('risk_assessment', {}).get('risk_score')
            task.risk_level = risk_analysis.get('risk_assessment', {}).get('risk_level', 'low').lower()
            task.risk_indicators = risk_analysis.get('risk_indicators', [])
            task.mitigation_suggestions = risk_analysis.get('mitigation_suggestions', [])
            task.risk_analysis = risk_analysis
            task.last_risk_assessment = timezone.now()
            task.save()
        
        return JsonResponse({
            'success': True,
            'risk_analysis': risk_analysis,
            'saved': bool(task_id)
        })
    except Exception as e:
        response_time_ms = int((time.time() - start_time) * 1000)
        board_id_val = board.id if 'board' in locals() and board else None
        track_ai_request(
            user=request.user,
            feature='risk_analysis',
            request_type='calculate',
            board_id=board_id_val,
            success=False,
            error_message=str(e),
            response_time_ms=response_time_ms
        )
        logger.error(f"Error in calculate_task_risk_api: {str(e)}")
        return JsonResponse({'error': str(e)}, status=500)


@login_required
@require_http_methods(["POST"])
def get_mitigation_suggestions_api(request):
    """
    API endpoint to get AI-generated mitigation suggestions for a high-risk task
    """
    start_time = time.time()
    try:
        # Check AI quota
        has_quota, quota, remaining = check_ai_quota(request.user)
        if not has_quota:
            return JsonResponse({
                'error': 'AI usage quota exceeded. Please upgrade or wait for quota reset.',
                'quota_exceeded': True
            }, status=429)
        
        data = json.loads(request.body)
        task_id = data.get('task_id')
        title = data.get('title', '')
        description = data.get('description', '')
        risk_likelihood = data.get('risk_likelihood', 2)
        risk_impact = data.get('risk_impact', 2)
        risk_indicators = data.get('risk_indicators', [])
        board_id = data.get('board_id')
        
        if not title:
            return JsonResponse({'error': 'Title is required'}, status=400)
        
        # If task_id provided, verify access
        if task_id:
            task = get_object_or_404(Task, id=task_id)
            board = task.column.board
        elif board_id:
            board = get_object_or_404(Board, id=board_id)
        else:
            return JsonResponse({'error': 'Board ID or Task ID is required'}, status=400)
        
        # Check access
        if not (board.created_by == request.user or request.user in board.members.all()):
            return JsonResponse({'error': 'Access denied'}, status=403)
        
        # Get mitigation suggestions
        mitigation_suggestions = generate_risk_mitigation_suggestions(
            title, 
            description,
            risk_likelihood,
            risk_impact,
            risk_indicators
        )
        
        if not mitigation_suggestions:
            response_time_ms = int((time.time() - start_time) * 1000)
            track_ai_request(
                user=request.user,
                feature='risk_mitigation',
                request_type='suggest',
                board_id=board.id,
                success=False,
                error_message='Failed to generate mitigation suggestions',
                response_time_ms=response_time_ms
            )
            return JsonResponse({'error': 'Failed to generate mitigation suggestions'}, status=500)
        
        # Track successful request
        response_time_ms = int((time.time() - start_time) * 1000)
        track_ai_request(
            user=request.user,
            feature='risk_mitigation',
            request_type='suggest',
            board_id=board.id,
            success=True,
            response_time_ms=response_time_ms
        )
        
        # If task_id provided, update the task
        if task_id:
            task.mitigation_suggestions = mitigation_suggestions
            task.save()
        
        return JsonResponse({
            'success': True,
            'mitigation_suggestions': mitigation_suggestions,
            'count': len(mitigation_suggestions)
        })
    except Exception as e:
        response_time_ms = int((time.time() - start_time) * 1000)
        board_id_val = board.id if 'board' in locals() and board else None
        track_ai_request(
            user=request.user,
            feature='risk_mitigation',
            request_type='suggest',
            board_id=board_id_val,
            success=False,
            error_message=str(e),
            response_time_ms=response_time_ms
        )
        logger.error(f"Error in get_mitigation_suggestions_api: {str(e)}")
        return JsonResponse({'error': str(e)}, status=500)


@login_required
@require_http_methods(["POST"])
def assess_task_dependencies_api(request):
    """
    API endpoint to assess task dependencies and cascading risks
    """
    try:
        data = json.loads(request.body)
        task_id = data.get('task_id')
        board_id = data.get('board_id')
        
        if task_id:
            task = get_object_or_404(Task, id=task_id)
            board = task.column.board
            task_title = task.title
        elif board_id:
            board = get_object_or_404(Board, id=board_id)
            task_title = data.get('task_title', '')
        else:
            return JsonResponse({'error': 'Board ID or Task ID is required'}, status=400)
        
        # Check access
        if not (board.created_by == request.user or request.user in board.members.all()):
            return JsonResponse({'error': 'Access denied'}, status=403)
        
        # Get related tasks
        all_tasks = Task.objects.filter(column__board=board).values(
            'id', 'title', 'priority', 'column__name'
        )[:20]  # Limit to avoid token overflow
        
        tasks_data = [
            {
                'id': t['id'],
                'title': t['title'],
                'priority': t['priority'],
                'status': t['column__name']
            }
            for t in all_tasks
        ]
        
        # Assess dependencies
        dependency_analysis = assess_task_dependencies_and_risks(task_title, tasks_data)
        
        if not dependency_analysis:
            return JsonResponse({'error': 'Failed to assess task dependencies'}, status=500)
        
        return JsonResponse({
            'success': True,
            'dependency_analysis': dependency_analysis
        })
    except Exception as e:
        logger.error(f"Error in assess_task_dependencies_api: {str(e)}")
        return JsonResponse({'error': str(e)}, status=500)

# Meeting Transcript Extraction API Endpoints










@login_required
@require_http_methods(["POST"])
def update_user_skills_api(request):
    """
    API endpoint to update user skills and capacity information
    """
    try:
        data = json.loads(request.body)
        user_id = data.get('user_id')
        
        # If no user_id provided, update current user
        if not user_id:
            target_user = request.user
        else:
            target_user = get_object_or_404(User, id=user_id)
            
            # Check if current user can update this profile
            if target_user != request.user:
                # Only organization admins can update other users' profiles
                if not hasattr(request.user, 'profile') or not request.user.profile.is_admin:
                    return JsonResponse({'error': 'Permission denied'}, status=403)
        
        # Get or create user profile
        profile, created = UserProfile.objects.get_or_create(
            user=target_user,
            defaults={'organization': request.user.profile.organization}
        )
        
        # Update skills
        if 'skills' in data:
            skills = data['skills']
            if isinstance(skills, list):
                profile.skills = skills
        
        # Update capacity
        if 'weekly_capacity_hours' in data:
            capacity = data['weekly_capacity_hours']
            if isinstance(capacity, int) and capacity > 0:
                profile.weekly_capacity_hours = capacity
        
        # Update availability schedule
        if 'availability_schedule' in data:
            schedule = data['availability_schedule']
            if isinstance(schedule, dict):
                profile.availability_schedule = schedule
        
        # Update preferred task types
        if 'preferred_task_types' in data:
            task_types = data['preferred_task_types']
            if isinstance(task_types, list):
                profile.preferred_task_types = task_types
        
        profile.save()
        
        return JsonResponse({
            'success': True,
            'message': 'User profile updated successfully',
            'utilization_percentage': profile.utilization_percentage,
            'available_hours': profile.available_hours
        })
        
    except Exception as e:
        logger.error(f"Error updating user skills API: {str(e)}")
        return JsonResponse({'error': str(e)}, status=500)

@login_required
@require_http_methods(["POST"])

# ============================================================================
# Task Dependency Management API Endpoints
# ============================================================================

@login_required
@require_http_methods(["GET"])
def get_task_dependencies_api(request, task_id):
    """
    Get all dependencies for a task (parents, children, related tasks)
    """
    try:
        task = get_object_or_404(Task, id=task_id)
        
        # Verify user has access to this task's board
        if not request.user in task.column.board.members.all() and task.column.board.created_by != request.user:
            return JsonResponse({'error': 'Access denied'}, status=403)
        
        dependencies = {
            'task_id': task.id,
            'task_title': task.title,
            'parent_task': None,
            'subtasks': [],
            'related_tasks': [],
            'dependency_chain': task.dependency_chain,
            'dependency_level': task.get_dependency_level()
        }
        
        # Add parent task
        if task.parent_task:
            dependencies['parent_task'] = {
                'id': task.parent_task.id,
                'title': task.parent_task.title,
                'status': task.parent_task.column.name if task.parent_task.column else 'Unknown'
            }
        
        # Add subtasks
        for subtask in task.subtasks.all():
            dependencies['subtasks'].append({
                'id': subtask.id,
                'title': subtask.title,
                'status': subtask.column.name if subtask.column else 'Unknown',
                'assigned_to': subtask.assigned_to.username if subtask.assigned_to else 'Unassigned'
            })
        
        # Add related tasks
        for related in task.related_tasks.all():
            dependencies['related_tasks'].append({
                'id': related.id,
                'title': related.title,
                'status': related.column.name if related.column else 'Unknown'
            })
        
        return JsonResponse({
            'success': True,
            'dependencies': dependencies
        })
        
    except Task.DoesNotExist:
        return JsonResponse({'error': 'Task not found'}, status=404)
    except Exception as e:
        logger.error(f"Error in get_task_dependencies_api: {str(e)}")
        return JsonResponse({'error': str(e)}, status=500)


@login_required
@require_http_methods(["POST"])
def set_parent_task_api(request, task_id):
    """
    Set a parent task for the given task
    """
    try:
        task = get_object_or_404(Task, id=task_id)
        
        # Verify user has access
        if not request.user in task.column.board.members.all() and task.column.board.created_by != request.user:
            return JsonResponse({'error': 'Access denied'}, status=403)
        
        data = json.loads(request.body)
        parent_id = data.get('parent_task_id')
        
        if parent_id is None:
            # Remove parent
            task.parent_task = None
        else:
            parent_task = get_object_or_404(Task, id=parent_id)
            
            # Check for circular dependency
            if task.has_circular_dependency(parent_task):
                return JsonResponse({
                    'error': 'This would create a circular dependency',
                    'success': False
                }, status=400)
            
            task.parent_task = parent_task
        
        task.update_dependency_chain()
        
        return JsonResponse({
            'success': True,
            'message': f'Parent task {'set to' if parent_id else 'removed from'} {task.title}',
            'dependency_chain': task.dependency_chain
        })
        
    except Task.DoesNotExist:
        return JsonResponse({'error': 'Task not found'}, status=404)
    except Exception as e:
        logger.error(f"Error in set_parent_task_api: {str(e)}")
        return JsonResponse({'error': str(e)}, status=500)


@login_required
@require_http_methods(["POST"])
def add_related_task_api(request, task_id):
    """
    Add a related task (non-hierarchical relationship)
    """
    try:
        task = get_object_or_404(Task, id=task_id)
        
        # Verify user has access
        if not request.user in task.column.board.members.all() and task.column.board.created_by != request.user:
            return JsonResponse({'error': 'Access denied'}, status=403)
        
        data = json.loads(request.body)
        related_id = data.get('related_task_id')
        
        if not related_id:
            return JsonResponse({'error': 'No related task ID provided'}, status=400)
        
        related_task = get_object_or_404(Task, id=related_id)
        
        if task.id == related_task.id:
            return JsonResponse({'error': 'Cannot relate a task to itself'}, status=400)
        
        task.related_tasks.add(related_task)
        
        return JsonResponse({
            'success': True,
            'message': f'Related task added to {task.title}'
        })
        
    except Task.DoesNotExist:
        return JsonResponse({'error': 'Task not found'}, status=404)
    except Exception as e:
        logger.error(f"Error in add_related_task_api: {str(e)}")
        return JsonResponse({'error': str(e)}, status=500)


@login_required
@require_http_methods(["POST"])
def analyze_task_dependencies_api(request, task_id):
    """
    Analyze a task and suggest dependencies
    """
    try:
        from kanban.utils.dependency_suggestions import analyze_and_suggest_dependencies
        
        task = get_object_or_404(Task, id=task_id)
        
        # Verify user has access
        if not request.user in task.column.board.members.all() and task.column.board.created_by != request.user:
            return JsonResponse({'error': 'Access denied'}, status=403)
        
        data = json.loads(request.body)
        auto_link = data.get('auto_link', False)
        
        board = task.column.board if task.column else None
        result = analyze_and_suggest_dependencies(task, board, auto_link)
        
        return JsonResponse({
            'success': True,
            'analysis': result,
            'message': result.get('analysis', 'Analysis completed')
        })
        
    except Task.DoesNotExist:
        return JsonResponse({'error': 'Task not found'}, status=404)
    except Exception as e:
        logger.error(f"Error in analyze_task_dependencies_api: {str(e)}")
        return JsonResponse({'error': str(e)}, status=500)


@login_required
@require_http_methods(["GET"])
def get_dependency_tree_api(request, task_id):
    """
    Get a hierarchical dependency tree for visualization
    """
    try:
        from kanban.utils.dependency_suggestions import DependencyGraphGenerator
        
        task = get_object_or_404(Task, id=task_id)
        
        # Verify user has access
        if not request.user in task.column.board.members.all() and task.column.board.created_by != request.user:
            return JsonResponse({'error': 'Access denied'}, status=403)
        
        include_related = request.GET.get('include_related', 'false').lower() == 'true'
        tree = DependencyGraphGenerator.generate_dependency_tree(task, include_subtasks=True, include_related=include_related)
        
        return JsonResponse({
            'success': True,
            'tree': tree
        })
        
    except Task.DoesNotExist:
        return JsonResponse({'error': 'Task not found'}, status=404)
    except Exception as e:
        logger.error(f"Error in get_dependency_tree_api: {str(e)}")
        return JsonResponse({'error': str(e)}, status=500)


@login_required
@require_http_methods(["GET"])
def get_board_dependency_graph_api(request, board_id):
    """
    Get a full dependency graph for a board
    """
    try:
        from kanban.utils.dependency_suggestions import DependencyGraphGenerator
        
        board = get_object_or_404(Board, id=board_id)
        
        # Verify user has access
        if not request.user in board.members.all() and board.created_by != request.user:
            return JsonResponse({'error': 'Access denied'}, status=403)
        
        root_task_id = request.GET.get('root_task_id')
        if root_task_id:
            root_task_id = int(root_task_id)
        
        graph = DependencyGraphGenerator.generate_dependency_graph(board, root_task_id)
        
        return JsonResponse({
            'success': True,
            'graph': graph
        })
        
    except Board.DoesNotExist:
        return JsonResponse({'error': 'Board not found'}, status=404)
    except Exception as e:
        logger.error(f"Error in get_board_dependency_graph_api: {str(e)}")
        return JsonResponse({'error': str(e)}, status=500)


@login_required
@require_http_methods(["POST"])
def update_task_dates_api(request):
    """
    Update task start_date and due_date from Gantt chart
    """
    try:
        data = json.loads(request.body)
        task_id = data.get('task_id')
        start_date = data.get('start_date')
        due_date = data.get('due_date')
        
        if not task_id:
            return JsonResponse({'error': 'Task ID is required'}, status=400)
        
        task = get_object_or_404(Task, id=task_id)
        
        # Verify user has access
        board = task.column.board
        if not (request.user in board.members.all() or board.created_by == request.user):
            return JsonResponse({'error': 'Access denied'}, status=403)
        
        # Update dates
        if start_date:
            from datetime import datetime
            task.start_date = datetime.strptime(start_date, '%Y-%m-%d').date()
        
        if due_date:
            from datetime import datetime
            # Keep the time part if due_date is datetime, otherwise set to end of day
            if task.due_date:
                # Preserve time component
                new_date = datetime.strptime(due_date, '%Y-%m-%d').date()
                task.due_date = datetime.combine(new_date, task.due_date.time())
            else:
                # Set to end of day
                task.due_date = datetime.strptime(due_date + ' 23:59:59', '%Y-%m-%d %H:%M:%S')
        
        task.save()
        
        # Log activity
        TaskActivity.objects.create(
            task=task,
            user=request.user,
            activity_type='updated',
            description=f'Updated task dates: {start_date} to {due_date}'
        )
        
        return JsonResponse({
            'success': True,
            'message': 'Task dates updated successfully'
        })
        
    except Task.DoesNotExist:
        return JsonResponse({'error': 'Task not found'}, status=404)
    except Exception as e:
        logger.error(f"Error in update_task_dates_api: {str(e)}")
        return JsonResponse({'error': str(e)}, status=500)


@login_required
@require_http_methods(["GET"])
def summarize_task_details_api(request, task_id):
    """
    API endpoint to generate a comprehensive AI-powered summary of a task's details.
    
    This analyzes all aspects of the task including:
    - Risk management and mitigation strategies
    - Stakeholder involvement and feedback
    - Resource requirements and skill matching
    - Task dependencies and hierarchy
    - Complexity and effort estimates
    - Lean Six Sigma classification
    """
    start_time = time.time()
    try:
        # Check AI quota
        has_quota, quota, remaining = check_ai_quota(request.user)
        if not has_quota:
            return JsonResponse({
                'error': 'AI usage quota exceeded. Please upgrade or wait for quota reset.',
                'quota_exceeded': True
            }, status=429)
        
        # Get the task and verify user access
        task = get_object_or_404(Task, id=task_id)
        board = task.column.board
        
        # Check if user has access to this board
        if not (board.created_by == request.user or request.user in board.members.all()):
            return JsonResponse({'error': 'Access denied'}, status=403)
        
        # Import StakeholderTaskInvolvement here to avoid circular import
        from kanban.stakeholder_models import StakeholderTaskInvolvement
        
        # Gather comprehensive task data
        task_data = {
            'title': task.title,
            'description': task.description or 'No description provided',
            'status': task.column.name,
            'priority': task.get_priority_display(),
            'progress': task.progress if task.progress is not None else 0,
            'due_date': task.due_date.strftime('%B %d, %Y at %H:%M') if task.due_date else 'No due date set',
            'assigned_to': task.assigned_to.username if task.assigned_to else 'Unassigned',
            'created_by': task.created_by.username,
            'created_at': task.created_at.strftime('%B %d, %Y'),
            
            # Risk management
            'risk_level': task.risk_level,
            'risk_score': task.risk_score,
            'risk_likelihood': task.risk_likelihood,
            'risk_impact': task.risk_impact,
            'risk_indicators': task.risk_indicators if task.risk_indicators else [],
            'mitigation_suggestions': task.mitigation_suggestions if task.mitigation_suggestions else [],
            
            # Stakeholders
            'stakeholders': [
                {
                    'name': involvement.stakeholder.name,
                    'involvement_type': involvement.get_involvement_type_display(),
                    'engagement_status': involvement.get_engagement_status_display(),
                    'satisfaction_rating': involvement.satisfaction_rating,
                    'feedback': involvement.feedback
                }
                for involvement in StakeholderTaskInvolvement.objects.filter(task=task).select_related('stakeholder')
            ],
            
            # Resource management
            'required_skills': task.required_skills if task.required_skills else [],
            'skill_match_score': task.skill_match_score,
            'workload_impact': task.get_workload_impact_display() if task.workload_impact else None,
            'collaboration_required': task.collaboration_required,
            'complexity_score': task.complexity_score,
            
            # Dependencies and hierarchy
            'parent_task': task.parent_task.title if task.parent_task else None,
            'subtasks': [subtask.title for subtask in task.subtasks.all()],
            'dependencies': [
                f"{dep.title} ({dep.progress}% complete, Due: {dep.due_date.strftime('%Y-%m-%d') if dep.due_date else 'No date'})"
                for dep in task.dependencies.all()
            ],
            'dependent_tasks': [
                f"{blocked.title} (Waiting on this task)"
                for blocked in task.dependent_tasks.all()
            ],
            'related_tasks': [rel.title for rel in task.related_tasks.all()],
            
            # Labels
            'labels': [
                {
                    'name': label.name,
                    'category': label.category
                }
                for label in task.labels.all()
            ],
            
            # Additional context
            'comments_count': task.comments.count()
        }
        
        # Generate comprehensive summary
        summary = summarize_task_details(task_data)
        
        if not summary:
            # Track failed request
            response_time_ms = int((time.time() - start_time) * 1000)
            track_ai_request(
                user=request.user,
                feature='task_summarization',
                request_type='summarize',
                board_id=board.id,
                success=False,
                error_message='Failed to generate task summary',
                response_time_ms=response_time_ms
            )
            return JsonResponse({'error': 'Failed to generate task summary'}, status=500)
        
        # Track successful request
        response_time_ms = int((time.time() - start_time) * 1000)
        track_ai_request(
            user=request.user,
            feature='task_summarization',
            request_type='summarize',
            board_id=board.id,
            success=True,
            response_time_ms=response_time_ms
        )
            
        return JsonResponse({'summary': summary})
    except Exception as e:
        response_time_ms = int((time.time() - start_time) * 1000)
        track_ai_request(
            user=request.user,
            feature='task_summarization',
            request_type='summarize',
            board_id=board.id if 'board' in locals() else None,
            success=False,
            error_message=str(e),
            response_time_ms=response_time_ms
        )
        logger.error(f"Error in summarize_task_details_api: {str(e)}")
        return JsonResponse({'error': str(e)}, status=500)


@login_required
@require_http_methods(["GET", "POST"])
def get_task_prediction_api(request, task_id):
    """
    API endpoint to get or update task completion prediction
    GET: Returns current prediction
    POST: Triggers new prediction calculation
    """
    try:
        task = get_object_or_404(Task, pk=task_id)
        
        # Check user has access to this task's board
        if request.user not in task.column.board.members.all():
            return JsonResponse({'error': 'Access denied'}, status=403)
        
        # For POST, force recalculation
        if request.method == 'POST':
            from kanban.utils.task_prediction import update_task_prediction
            prediction = update_task_prediction(task)
            
            if not prediction:
                return JsonResponse({
                    'message': 'Task is completed or cannot be predicted',
                    'has_prediction': False
                })
            
            # Format similar_tasks for JSON serialization
            similar_tasks_formatted = []
            if prediction.get('similar_tasks'):
                for task_data in prediction['similar_tasks']:
                    # completed_at is already a string (isoformat) from task_prediction.py
                    formatted_task = {
                        'id': task_data['id'],
                        'title': task_data['title'],
                        'actual_duration_days': task_data['actual_duration_days'],
                        'complexity_score': task_data['complexity_score'],
                        'priority': task_data['priority'],
                        'completed_at': task_data.get('completed_at')  # Already a string
                    }
                    similar_tasks_formatted.append(formatted_task)
            
            return JsonResponse({
                'success': True,
                'prediction': {
                    'predicted_date': prediction['predicted_date'].isoformat(),
                    'predicted_date_formatted': prediction['predicted_date'].strftime('%B %d, %Y'),
                    'confidence': prediction['confidence'],
                    'confidence_percentage': int(prediction['confidence'] * 100),
                    'confidence_interval_days': prediction['confidence_interval_days'],
                    'based_on_tasks': prediction['based_on_tasks'],
                    'similar_tasks': similar_tasks_formatted,
                    'early_date': prediction['early_date'].isoformat(),
                    'early_date_formatted': prediction['early_date'].strftime('%b %d'),
                    'late_date': prediction['late_date'].isoformat(),
                    'late_date_formatted': prediction['late_date'].strftime('%b %d'),
                    'prediction_method': prediction['prediction_method'],
                    'factors': prediction['factors'],
                    'is_likely_late': prediction['predicted_date'] > task.due_date if task.due_date else False
                },
                'has_prediction': True
            })
        
        # For GET, return existing prediction
        if task.predicted_completion_date and task.prediction_confidence:
            is_likely_late = False
            if task.due_date:
                is_likely_late = task.predicted_completion_date > task.due_date
            
            return JsonResponse({
                'has_prediction': True,
                'prediction': {
                    'predicted_date': task.predicted_completion_date.isoformat(),
                    'predicted_date_formatted': task.predicted_completion_date.strftime('%B %d, %Y'),
                    'confidence': task.prediction_confidence,
                    'confidence_percentage': int(task.prediction_confidence * 100),
                    'confidence_interval_days': task.prediction_metadata.get('confidence_interval_days', 0),
                    'based_on_tasks': task.prediction_metadata.get('based_on_tasks', 0),
                    'similar_tasks': task.prediction_metadata.get('similar_tasks', []),
                    'early_date': task.prediction_metadata.get('early_date', ''),
                    'late_date': task.prediction_metadata.get('late_date', ''),
                    'prediction_method': task.prediction_metadata.get('prediction_method', 'unknown'),
                    'factors': task.prediction_metadata.get('factors', {}),
                    'is_likely_late': is_likely_late,
                    'last_updated': task.last_prediction_update.isoformat() if task.last_prediction_update else None
                }
            })
        else:
            return JsonResponse({
                'has_prediction': False,
                'message': 'No prediction available. Task may need a start date or more historical data.'
            })
            
    except Exception as e:
        logger.error(f"Error in get_task_prediction_api: {str(e)}")
        return JsonResponse({'error': str(e)}, status=500)


@login_required
@require_http_methods(["POST"])
def bulk_update_predictions_api(request, board_id):
    """
    API endpoint to update predictions for all tasks in a board
    """
    try:
        board = get_object_or_404(Board, pk=board_id)
        
        # Check user has access
        if request.user not in board.members.all():
            return JsonResponse({'error': 'Access denied'}, status=403)
        
        from kanban.utils.task_prediction import bulk_update_predictions
        result = bulk_update_predictions(board=board)
        
        return JsonResponse({
            'success': True,
            'total_tasks': result['total_tasks'],
            'updated': result['updated'],
            'failed': result['failed'],
            'message': f"Updated {result['updated']} of {result['total_tasks']} task predictions"
        })
        
    except Exception as e:
        logger.error(f"Error in bulk_update_predictions_api: {str(e)}")
        return JsonResponse({'error': str(e)}, status=500)


@login_required
@require_http_methods(["POST"])
def suggest_task_priority_api(request):
    """
    API endpoint to get AI-powered priority suggestion for a task
    
    Request body:
    {
        "task_id": 123,  # Optional - for existing tasks
        "title": "Task title",  # Required for new tasks
        "due_date": "2025-11-25T10:00:00Z",  # Optional
        "complexity_score": 7,  # Optional
        "board_id": 5  # Required
        ... other task fields
    }
    
    Returns:
    {
        "suggested_priority": "high",
        "confidence": 0.85,
        "reasoning": {
            "top_factors": [...],
            "explanation": "...",
            "confidence_level": "High confidence"
        },
        "alternatives": [...],
        "is_ml_based": true
    }
    """
    try:
        data = json.loads(request.body)
        task_id = data.get('task_id')
        
        # Get or create task object
        if task_id:
            task = get_object_or_404(Task, pk=task_id)
            # Check if task has a column to get board from
            if task.column:
                board = task.column.board
            else:
                # Task exists but no column - get board from request
                board_id = data.get('board_id')
                if not board_id:
                    return JsonResponse({'error': 'board_id required when task has no column'}, status=400)
                board = get_object_or_404(Board, pk=board_id)
            
            # Check access
            if request.user not in board.members.all() and board.created_by != request.user:
                return JsonResponse({'error': 'Access denied'}, status=403)
        else:
            # Create temporary task object for prediction
            board_id = data.get('board_id')
            if not board_id:
                return JsonResponse({'error': 'board_id required for new tasks'}, status=400)
            
            board = get_object_or_404(Board, pk=board_id)
            
            # Check access
            if request.user not in board.members.all() and board.created_by != request.user:
                return JsonResponse({'error': 'Access denied'}, status=403)
            
            # Create temporary task (not saved to DB)
            # Convert string values to appropriate types
            complexity_score = data.get('complexity_score', 5)
            if isinstance(complexity_score, str):
                try:
                    complexity_score = int(complexity_score)
                except (ValueError, TypeError):
                    complexity_score = 5
            
            risk_score = data.get('risk_score')
            if risk_score and isinstance(risk_score, str):
                try:
                    risk_score = int(risk_score)
                except (ValueError, TypeError):
                    risk_score = None
            
            task = Task(
                title=data.get('title', 'New Task'),
                description=data.get('description', ''),
                complexity_score=complexity_score,
                collaboration_required=data.get('collaboration_required', False),
                risk_score=risk_score,
            )
            
            # Parse due_date if provided
            if data.get('due_date'):
                from django.utils.dateparse import parse_datetime
                task.due_date = parse_datetime(data.get('due_date'))
            
            # Attach board for context
            task._board = board
        
        # Get priority suggestion
        from ai_assistant.utils.priority_service import PrioritySuggestionService
        service = PrioritySuggestionService()
        suggestion = service.suggest_priority(task, user=request.user)
        
        return JsonResponse(suggestion)
        
    except Exception as e:
        logger.error(f"Error in suggest_task_priority_api: {str(e)}")
        return JsonResponse({'error': str(e)}, status=500)


@login_required
@require_http_methods(["POST"])
def log_priority_decision_api(request):
    """
    API endpoint to log a priority decision for learning
    
    Request body:
    {
        "task_id": 123,
        "priority": "high",
        "decision_type": "initial" | "correction" | "ai_accepted" | "ai_rejected",
        "suggested_priority": "medium",  # Optional - AI suggestion
        "confidence": 0.75,  # Optional - AI confidence
        "reasoning": {...},  # Optional - AI reasoning
        "feedback_notes": "..."  # Optional - user feedback
    }
    """
    try:
        data = json.loads(request.body)
        task_id = data.get('task_id')
        priority = data.get('priority')
        
        if not task_id or not priority:
            return JsonResponse({'error': 'task_id and priority required'}, status=400)
        
        task = get_object_or_404(Task, pk=task_id)
        board = task.column.board
        
        # Check access
        if request.user not in board.members.all() and board.created_by != request.user:
            return JsonResponse({'error': 'Access denied'}, status=403)
        
        # Log the decision
        from kanban.priority_models import PriorityDecision
        
        previous_priority = task.priority if task.priority != priority else None
        
        decision = PriorityDecision.log_decision(
            task=task,
            priority=priority,
            user=request.user,
            decision_type=data.get('decision_type', 'initial'),
            suggested_priority=data.get('suggested_priority'),
            confidence=data.get('confidence'),
            reasoning=data.get('reasoning'),
            previous_priority=previous_priority
        )
        
        # Update feedback notes if provided
        if data.get('feedback_notes'):
            decision.feedback_notes = data.get('feedback_notes')
            decision.save()
        
        # Update task priority if it changed
        if task.priority != priority:
            old_priority = task.priority
            task.priority = priority
            task.save()
            
            # Log activity
            TaskActivity.objects.create(
                task=task,
                user=request.user,
                activity_type='updated',
                description=f"Changed priority from {old_priority} to {priority}"
            )
        
        return JsonResponse({
            'success': True,
            'decision_id': decision.id,
            'message': 'Priority decision logged successfully'
        })
        
    except Exception as e:
        logger.error(f"Error in log_priority_decision_api: {str(e)}")
        return JsonResponse({'error': str(e)}, status=500)


@login_required
@require_http_methods(["POST"])
def train_priority_model_api(request, board_id):
    """
    API endpoint to train/retrain priority model for a board
    
    Requires sufficient historical data (min 20 decisions)
    """
    try:
        board = get_object_or_404(Board, pk=board_id)
        
        # Check access - only board creators can train models
        if board.created_by != request.user:
            return JsonResponse({'error': 'Only board owner can train models'}, status=403)
        
        from ai_assistant.utils.priority_service import PriorityModelTrainer
        
        trainer = PriorityModelTrainer(board)
        result = trainer.train_model()
        
        if not result['success']:
            return JsonResponse(result, status=400)
        
        return JsonResponse(result)
        
    except Exception as e:
        logger.error(f"Error in train_priority_model_api: {str(e)}")
        return JsonResponse({'error': str(e)}, status=500)


@login_required
@require_http_methods(["GET"])
def get_priority_model_info_api(request, board_id):
    """
    Get information about the current priority model for a board
    """
    try:
        board = get_object_or_404(Board, pk=board_id)
        
        # Check access
        if request.user not in board.members.all() and board.created_by != request.user:
            return JsonResponse({'error': 'Access denied'}, status=403)
        
        from kanban.priority_models import PriorityModel, PriorityDecision
        
        model = PriorityModel.get_active_model(board)
        
        if not model:
            # Check how many decisions we have
            decision_count = PriorityDecision.objects.filter(board=board).count()
            
            return JsonResponse({
                'has_model': False,
                'decision_count': decision_count,
                'min_required': 20,
                'message': f'Need {max(0, 20 - decision_count)} more decisions to train a model'
            })
        
        return JsonResponse({
            'has_model': True,
            'model_version': model.model_version,
            'accuracy': model.accuracy_score,
            'trained_at': model.trained_at.isoformat(),
            'training_samples': model.training_samples,
            'feature_importance': model.feature_importance,
            'precision_scores': model.precision_scores,
            'recall_scores': model.recall_scores,
            'f1_scores': model.f1_scores
        })
        
    except Exception as e:
        logger.error(f"Error in get_priority_model_info_api: {str(e)}")
        return JsonResponse({'error': str(e)}, status=500)


# ========================================
# Skill Gap Analysis & Resource Matching
# ========================================

@login_required
@require_http_methods(["GET"])
def analyze_skill_gaps_api(request, board_id):
    """
    Analyze skill gaps for a board
    Identifies missing skills and generates recommendations
    """
    start_time = time.time()
    try:
        # Check AI quota
        has_quota, quota, remaining = check_ai_quota(request.user)
        if not has_quota:
            return JsonResponse({
                'error': 'AI usage quota exceeded. Please upgrade or wait for quota reset.',
                'quota_exceeded': True
            }, status=429)
        
        board = get_object_or_404(Board, pk=board_id)
        
        # Check access
        if request.user not in board.members.all() and board.created_by != request.user:
            return JsonResponse({'error': 'Access denied'}, status=403)
        
        from kanban.utils.skill_analysis import calculate_skill_gaps, generate_skill_gap_recommendations
        from kanban.models import SkillGap
        
        # Get sprint period from query params (default 14 days)
        sprint_days = int(request.GET.get('sprint_days', 14))
        
        # Calculate gaps
        gaps = calculate_skill_gaps(board, sprint_period_days=sprint_days)
        
        # Save gaps to database (without AI recommendations initially for speed)
        saved_gaps = []
        gaps_needing_recommendations = []
        
        for gap_data in gaps:
            # Find existing active gap or create new one
            skill_gap = SkillGap.objects.filter(
                board=board,
                skill_name=gap_data['skill_name'],
                proficiency_level=gap_data['proficiency_level'],
                status__in=['identified', 'acknowledged', 'in_progress']
            ).first()
            
            if skill_gap:
                # Update existing gap
                skill_gap.required_count = gap_data['required_count']
                skill_gap.available_count = gap_data['available_count']
                skill_gap.gap_count = gap_data['gap_count']
                skill_gap.severity = gap_data['severity']
                skill_gap.sprint_period_start = timezone.now().date()
                skill_gap.sprint_period_end = timezone.now().date() + timedelta(days=sprint_days)
                skill_gap.save()
                created = False
            else:
                # Create new gap
                skill_gap = SkillGap.objects.create(
                    board=board,
                    skill_name=gap_data['skill_name'],
                    proficiency_level=gap_data['proficiency_level'],
                    required_count=gap_data['required_count'],
                    available_count=gap_data['available_count'],
                    gap_count=gap_data['gap_count'],
                    severity=gap_data['severity'],
                    status='identified',
                    sprint_period_start=timezone.now().date(),
                    sprint_period_end=timezone.now().date() + timedelta(days=sprint_days),
                )
                created = True
            
            # Link affected tasks
            from kanban.models import Task
            affected_task_ids = [t['id'] for t in gap_data['affected_tasks']]
            affected_tasks = Task.objects.filter(id__in=affected_task_ids)
            skill_gap.affected_tasks.set(affected_tasks)
            
            # Queue for async recommendation generation if needed
            if not skill_gap.ai_recommendations or created:
                gaps_needing_recommendations.append((skill_gap, gap_data))
            
            saved_gaps.append({
                'id': skill_gap.id,
                'skill_name': skill_gap.skill_name,
                'proficiency_level': skill_gap.proficiency_level,
                'required_count': skill_gap.required_count,
                'available_count': skill_gap.available_count,
                'gap_count': skill_gap.gap_count,
                'severity': skill_gap.severity,
                'status': skill_gap.status,
                'affected_tasks': gap_data['affected_tasks'],
                'recommendations': skill_gap.ai_recommendations or [],
                'recommendations_pending': not skill_gap.ai_recommendations,
                'identified_at': skill_gap.identified_at.isoformat()
            })
        
        # Generate AI recommendations in background (non-blocking)
        if gaps_needing_recommendations:
            from threading import Thread
            def generate_recommendations_async():
                for skill_gap, gap_data in gaps_needing_recommendations:
                    try:
                        recommendations = generate_skill_gap_recommendations(gap_data, board)
                        skill_gap.ai_recommendations = recommendations
                        skill_gap.confidence_score = 0.8
                        skill_gap.save()
                    except Exception as e:
                        logger.error(f"Error generating recommendations for {skill_gap.skill_name}: {str(e)}")
            
            thread = Thread(target=generate_recommendations_async, daemon=True)
            thread.start()
        
        # Track successful request
        response_time_ms = int((time.time() - start_time) * 1000)
        track_ai_request(
            user=request.user,
            feature='skill_analysis',
            request_type='analyze_gaps',
            board_id=board.id,
            success=True,
            response_time_ms=response_time_ms
        )
        
        return JsonResponse({
            'success': True,
            'gaps': saved_gaps,
            'sprint_period_days': sprint_days,
            'total_gaps': len(saved_gaps)
        })
        
    except Exception as e:
        response_time_ms = int((time.time() - start_time) * 1000)
        board_id_val = board.id if 'board' in locals() and board else board_id
        track_ai_request(
            user=request.user,
            feature='skill_analysis',
            request_type='analyze_gaps',
            board_id=board_id_val,
            success=False,
            error_message=str(e),
            response_time_ms=response_time_ms
        )
        logger.error(f"Error in analyze_skill_gaps_api: {str(e)}")
        return JsonResponse({'error': str(e)}, status=500)


@login_required
@require_http_methods(["GET"])
def get_team_skill_profile_api(request, board_id):
    """
    Get comprehensive skill inventory for a board's team
    """
    try:
        board = get_object_or_404(Board, pk=board_id)
        
        # Check access
        if request.user not in board.members.all() and board.created_by != request.user:
            return JsonResponse({'error': 'Access denied'}, status=403)
        
        from kanban.utils.skill_analysis import build_team_skill_profile, update_team_skill_profile_model
        
        # Build and save profile
        team_profile_model = update_team_skill_profile_model(board)
        profile_data = build_team_skill_profile(board)
        
        # Format skill inventory for display
        skills_summary = []
        for skill_name, skill_data in profile_data['skill_inventory'].items():
            skills_summary.append({
                'skill_name': skill_name,
                'total_members': len(skill_data.get('members', [])),
                'expert': skill_data.get('expert', 0),
                'advanced': skill_data.get('advanced', 0),
                'intermediate': skill_data.get('intermediate', 0),
                'beginner': skill_data.get('beginner', 0),
                'members': skill_data.get('members', [])
            })
        
        # Sort by total members (most common skills first)
        skills_summary.sort(key=lambda x: x['total_members'], reverse=True)
        
        return JsonResponse({
            'success': True,
            'team_size': profile_data['team_size'],
            'total_capacity_hours': float(profile_data['total_capacity_hours']),
            'utilized_capacity_hours': float(profile_data['utilized_capacity_hours']),
            'utilization_percentage': round(profile_data['utilization_percentage'], 1),
            'skills': skills_summary,
            'total_unique_skills': len(skills_summary),
            'last_updated': team_profile_model.last_updated.isoformat() if team_profile_model else None
        })
        
    except Exception as e:
        logger.error(f"Error in get_team_skill_profile_api: {str(e)}")
        return JsonResponse({'error': str(e)}, status=500)


@login_required
@require_http_methods(["POST"])
def match_team_to_task_api(request, task_id):
    """
    Find best team members for a task based on skill matching
    """
    try:
        task = get_object_or_404(Task, pk=task_id)
        board = task.column.board
        
        # Check access
        if request.user not in board.members.all() and board.created_by != request.user:
            return JsonResponse({'error': 'Access denied'}, status=403)
        
        from kanban.utils.skill_analysis import match_team_member_to_task
        
        # Get board members
        board_members = board.members.select_related('profile').all()
        
        # Find matches
        matches = match_team_member_to_task(task, board_members)
        
        # Format response
        formatted_matches = []
        for match in matches[:10]:  # Top 10 matches
            formatted_matches.append({
                'user_id': match['user_id'],
                'username': match['username'],
                'full_name': match['full_name'],
                'match_score': match['match_score'],
                'matched_skills': match['matched_skills'],
                'missing_skills': match['missing_skills'],
                'current_workload': match['current_workload'],
                'available_hours': match['available_hours']
            })
        
        return JsonResponse({
            'success': True,
            'task_id': task.id,
            'task_title': task.title,
            'required_skills': task.required_skills or [],
            'matches': formatted_matches,
            'total_candidates': len(formatted_matches)
        })
        
    except Exception as e:
        logger.error(f"Error in match_team_to_task_api: {str(e)}")
        return JsonResponse({'error': str(e)}, status=500)


@login_required
@require_http_methods(["POST"])
def extract_task_skills_api(request, task_id):
    """
    AI-extract required skills from a task description
    """
    try:
        task = get_object_or_404(Task, pk=task_id)
        board = task.column.board
        
        # Check access
        if request.user not in board.members.all() and board.created_by != request.user:
            return JsonResponse({'error': 'Access denied'}, status=403)
        
        from kanban.utils.skill_analysis import extract_skills_from_task
        
        # Extract skills
        skills = extract_skills_from_task(task.title, task.description or "")
        
        if skills:
            # Update task
            task.required_skills = skills
            task.save(update_fields=['required_skills'])
            
            return JsonResponse({
                'success': True,
                'task_id': task.id,
                'skills': skills,
                'message': f'Extracted {len(skills)} skills from task description'
            })
        else:
            return JsonResponse({
                'success': False,
                'message': 'Could not extract skills from task'
            }, status=400)
        
    except Exception as e:
        logger.error(f"Error in extract_task_skills_api: {str(e)}")
        return JsonResponse({'error': str(e)}, status=500)


@login_required
@require_http_methods(["POST"])
def create_skill_development_plan_api(request):
    """
    Create a skill development plan to address a gap
    """
    try:
        data = json.loads(request.body)
        
        skill_gap_id = data.get('skill_gap_id')
        plan_type = data.get('plan_type')
        title = data.get('title')
        description = data.get('description')
        
        if not all([skill_gap_id, plan_type, title]):
            return JsonResponse({'error': 'Missing required fields'}, status=400)
        
        from kanban.models import SkillGap, SkillDevelopmentPlan
        
        skill_gap = get_object_or_404(SkillGap, pk=skill_gap_id)
        board = skill_gap.board
        
        # Check access
        if request.user not in board.members.all() and board.created_by != request.user:
            return JsonResponse({'error': 'Access denied'}, status=403)
        
        # Create plan
        plan = SkillDevelopmentPlan.objects.create(
            skill_gap=skill_gap,
            board=board,
            plan_type=plan_type,
            title=title,
            description=description or '',
            target_skill=skill_gap.skill_name,
            target_proficiency=skill_gap.proficiency_level,
            created_by=request.user,
            start_date=data.get('start_date'),
            target_completion_date=data.get('target_completion_date'),
            estimated_cost=data.get('estimated_cost'),
            estimated_hours=data.get('estimated_hours'),
            ai_suggested=data.get('ai_suggested', False),
            status='proposed'
        )
        
        # Add target users if specified
        if 'target_user_ids' in data:
            from django.contrib.auth.models import User
            target_users = User.objects.filter(id__in=data['target_user_ids'])
            plan.target_users.set(target_users)
        
        return JsonResponse({
            'success': True,
            'plan_id': plan.id,
            'message': 'Development plan created successfully'
        })
        
    except json.JSONDecodeError:
        return JsonResponse({'error': 'Invalid JSON'}, status=400)
    except Exception as e:
        logger.error(f"Error in create_skill_development_plan_api: {str(e)}")
        return JsonResponse({'error': str(e)}, status=500)


@login_required
@require_http_methods(["GET"])
def get_skill_gaps_list_api(request, board_id):
    """
    Get list of active skill gaps for a board
    """
    try:
        board = get_object_or_404(Board, pk=board_id)
        
        # Check access
        if request.user not in board.members.all() and board.created_by != request.user:
            return JsonResponse({'error': 'Access denied'}, status=403)
        
        from kanban.models import SkillGap
        
        # Get active gaps
        gaps = SkillGap.objects.filter(
            board=board,
            status__in=['identified', 'acknowledged', 'in_progress']
        ).prefetch_related('affected_tasks').order_by('-severity', '-gap_count')
        
        gaps_list = []
        for gap in gaps:
            gaps_list.append({
                'id': gap.id,
                'skill_name': gap.skill_name,
                'proficiency_level': gap.proficiency_level,
                'required_count': gap.required_count,
                'available_count': gap.available_count,
                'gap_count': gap.gap_count,
                'severity': gap.severity,
                'status': gap.status,
                'affected_tasks_count': gap.affected_tasks.count(),
                'recommendations_count': len(gap.ai_recommendations) if gap.ai_recommendations else 0,
                'identified_at': gap.identified_at.isoformat()
            })
        
        return JsonResponse({
            'success': True,
            'gaps': gaps_list,
            'total': len(gaps_list)
        })
        
    except Exception as e:
        logger.error(f"Error in get_skill_gaps_list_api: {str(e)}")
        return JsonResponse({'error': str(e)}, status=500)


@login_required
@require_http_methods(["GET"])
def get_development_plans_api(request, board_id):
    """
    Get skill development plans for a board
    """
    try:
        board = get_object_or_404(Board, pk=board_id)
        
        # Check access
        if request.user not in board.members.all() and board.created_by != request.user:
            return JsonResponse({'error': 'Access denied'}, status=403)
        
        from kanban.models import SkillDevelopmentPlan
        
        # Get plans
        status_filter = request.GET.get('status')
        plans = SkillDevelopmentPlan.objects.filter(board=board)
        
        if status_filter:
            plans = plans.filter(status=status_filter)
        
        plans = plans.select_related('skill_gap', 'created_by').prefetch_related('target_users')
        
        plans_list = []
        for plan in plans:
            plans_list.append({
                'id': plan.id,
                'plan_type': plan.plan_type,
                'title': plan.title,
                'description': plan.description,
                'target_skill': plan.target_skill,
                'target_proficiency': plan.target_proficiency,
                'status': plan.status,
                'progress_percentage': plan.progress_percentage,
                'start_date': plan.start_date.isoformat() if plan.start_date else None,
                'target_completion_date': plan.target_completion_date.isoformat() if plan.target_completion_date else None,
                'estimated_cost': float(plan.estimated_cost) if plan.estimated_cost else None,
                'estimated_hours': float(plan.estimated_hours) if plan.estimated_hours else None,
                'target_users': [{'id': u.id, 'username': u.username} for u in plan.target_users.all()],
                'created_by': plan.created_by.username,
                'created_at': plan.created_at.isoformat(),
                'ai_suggested': plan.ai_suggested,
                'is_overdue': plan.is_overdue
            })
        
        return JsonResponse({
            'success': True,
            'plans': plans_list,
            'total': len(plans_list)
        })
        
    except Exception as e:
        logger.error(f"Error in get_development_plans_api: {str(e)}")
        return JsonResponse({'error': str(e)}, status=500)


@login_required
@require_http_methods(["GET"])
def get_skill_gap_detail_api(request, gap_id):
    """
    Get detailed information about a specific skill gap
    """
    try:
        from kanban.models import SkillGap
        
        gap = get_object_or_404(SkillGap, pk=gap_id)
        board = gap.board
        
        # Check access
        if request.user not in board.members.all() and board.created_by != request.user:
            return JsonResponse({'error': 'Access denied'}, status=403)
        
        # Get affected tasks
        affected_tasks = []
        for task in gap.affected_tasks.all():
            affected_tasks.append({
                'id': task.id,
                'title': task.title,
                'column': task.column.name,
                'due_date': task.due_date.isoformat() if task.due_date else None,
                'assigned_to': task.assigned_to.username if task.assigned_to else None
            })
        
        # Prepare response
        gap_data = {
            'id': gap.id,
            'skill_name': gap.skill_name,
            'proficiency_level': gap.proficiency_level,
            'required_count': gap.required_count,
            'available_count': gap.available_count,
            'gap_count': gap.gap_count,
            'severity': gap.severity,
            'status': gap.status,
            'affected_tasks': affected_tasks,
            'ai_recommendations': gap.ai_recommendations if gap.ai_recommendations else [],
            'identified_at': gap.identified_at.isoformat(),
            'resolved_at': gap.resolved_at.isoformat() if gap.resolved_at else None
        }
        
        return JsonResponse({
            'success': True,
            'gap': gap_data
        })
        
    except Exception as e:
        logger.error(f"Error in get_skill_gap_detail_api: {str(e)}")
        return JsonResponse({'error': str(e)}, status=500)
