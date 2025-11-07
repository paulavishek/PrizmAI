"""
API views for Wiki Meeting Hub - DISABLED (meetings feature removed)

All functions in this file have been commented out as the meetings feature has been removed.
The code is preserved for reference but is no longer active.
"""

# import json
# import logging
# from django.shortcuts import get_object_or_404
# from django.http import JsonResponse
# from django.views.decorators.http import require_http_methods
# from django.contrib.auth.decorators import login_required
# from django.contrib.auth.models import User
# from django.utils import timezone

# from kanban.models import Board, Task
# from .models import MeetingNotes
# from .ai_utils import extract_tasks_from_transcript, extract_text_from_file, get_file_type_from_filename

# logger = logging.getLogger(__name__)


# @login_required
# @require_http_methods(["POST"])
# def analyze_meeting_transcript_api(request):
#     """
#     API endpoint to analyze meeting transcript using AI
#     Supports both text and file uploads
#     """
#     try:
#         # Get organization
#         if not hasattr(request.user, 'profile') or not request.user.profile.organization:
#             return JsonResponse({'error': 'No organization found'}, status=400)
#         
#         org = request.user.profile.organization
#         data = json.loads(request.body)
#         
#         meeting_id = data.get('meeting_id')
#         transcript = data.get('transcript', '')
#         meeting_context = data.get('meeting_context', {})
#         board_id = data.get('board_id')
#         
#         if not meeting_id:
#             return JsonResponse({'error': 'meeting_id is required'}, status=400)
#         
#         # Get the meeting notes
#         meeting = get_object_or_404(MeetingNotes, id=meeting_id, organization=org)
#         
#         # Verify user can access this meeting
#         if meeting.created_by != request.user and request.user not in meeting.attendees.all():
#             # Check if user is board member (if board is linked)
#             if meeting.related_board and request.user not in meeting.related_board.members.all():
#                 return JsonResponse({'error': 'Access denied'}, status=403)
#         
#         # Get transcript text
#         if not transcript and meeting.transcript_text:
#             transcript = meeting.transcript_text
#         elif not transcript and meeting.transcript_file:
#             # Extract text from file
#             file_type = get_file_type_from_filename(meeting.transcript_file.name)
#             transcript = extract_text_from_file(meeting.transcript_file.path, file_type)
#             if not transcript:
#                 return JsonResponse({'error': 'Failed to extract text from file'}, status=500)
#         
#         if not transcript:
#             return JsonResponse({'error': 'No transcript text found'}, status=400)
#         
#         # Update meeting status
#         meeting.processing_status = 'processing'
#         meeting.save(update_fields=['processing_status'])
#         
#         # Extract tasks using AI
#         extraction_results = extract_tasks_from_transcript(
#             transcript=transcript,
#             meeting_context=meeting_context,
#             related_board=meeting.related_board,
#             organization=org
#         )
#         
#         if not extraction_results:
#             meeting.processing_status = 'failed'
#             meeting.save(update_fields=['processing_status'])
#             return JsonResponse({'error': 'Failed to extract tasks from transcript'}, status=500)
#         
#         # Store extraction results
#         meeting.extraction_results = extraction_results
#         meeting.tasks_extracted_count = extraction_results.get('extraction_summary', {}).get('total_tasks_found', 0)
#         meeting.processing_status = 'completed'
#         meeting.processed_at = timezone.now()
#         meeting.save()
#         
#         return JsonResponse({
#             'success': True,
#             'extraction_results': extraction_results,
#             'meeting_id': meeting_id
#         })
#         
#     except Exception as e:
#         logger.error(f"Error in analyze_meeting_transcript_api: {str(e)}")
#         return JsonResponse({'error': str(e)}, status=500)


# @login_required
# @require_http_methods(["POST"])
# def create_tasks_from_extraction_api(request):
#     """
#     API endpoint to create tasks in a board from extracted meeting tasks
#     """
#     try:
#         if not hasattr(request.user, 'profile') or not request.user.profile.organization:
#             return JsonResponse({'error': 'No organization found'}, status=400)
#         
#         org = request.user.profile.organization
#         data = json.loads(request.body)
#         
#         meeting_id = data.get('meeting_id')
#         board_id = data.get('board_id')
#         selected_task_indices = data.get('selected_tasks', [])
#         
#         if not meeting_id or not board_id:
#             return JsonResponse({'error': 'meeting_id and board_id are required'}, status=400)
#         
#         # Get meeting and board
#         meeting = get_object_or_404(MeetingNotes, id=meeting_id, organization=org)
#         board = get_object_or_404(Board, id=board_id, organization=org)
#         
#         # Check board access
#         if board.created_by != request.user and request.user not in board.members.all():
#             return JsonResponse({'error': 'Access denied'}, status=403)
#         
#         if not meeting.extraction_results:
#             return JsonResponse({'error': 'No extraction results found'}, status=400)
#         
#         extracted_tasks = meeting.extraction_results.get('extracted_tasks', [])
#         created_tasks = []
#         failed_tasks = []
#         
#         # Get default column (usually "To Do")
#         default_column = board.columns.filter(name__icontains='todo').first() or board.columns.first()
#         if not default_column:
#             return JsonResponse({'error': 'No columns found in board'}, status=400)
#         
#         # Create tasks for selected indices
#         for idx in selected_task_indices:
#             try:
#                 if idx >= len(extracted_tasks):
#                     continue
#                 
#                 extracted = extracted_tasks[idx]
#                 
#                 # Parse priority
#                 priority_map = {
#                     'urgent': 'urgent',
#                     'high': 'high',
#                     'medium': 'medium',
#                     'low': 'low'
#                 }
#                 priority = priority_map.get(extracted.get('priority', 'medium'), 'medium')
#                 
#                 # Create task
#                 task = Task.objects.create(
#                     title=extracted['title'],
#                     description=extracted.get('description', ''),
#                     column=default_column,
#                     priority=priority,
#                     created_by=request.user
#                 )
#                 
#                 # Try to assign if suggested and user exists
#                 assignee = extracted.get('suggested_assignee')
#                 if assignee:
#                     try:
#                         user = User.objects.get(username=assignee)
#                         task.assigned_to = user
#                         task.save()
#                     except User.DoesNotExist:
#                         pass
#                 
#                 # Set due date if suggested
#                 due_date_str = extracted.get('due_date_suggestion')
#                 if due_date_str:
#                     from .ai_utils import parse_due_date
#                     due_date = parse_due_date(due_date_str)
#                     if due_date:
#                         task.due_date = due_date
#                         task.save()
#                 
#                 created_tasks.append({
#                     'id': task.id,
#                     'title': task.title,
#                     'url': task.get_absolute_url() if hasattr(task, 'get_absolute_url') else f'/tasks/{task.id}/'
#                 })
#                 
#             except Exception as e:
#                 logger.error(f"Error creating task from extraction {idx}: {str(e)}")
#                 failed_tasks.append(idx)
#         
#         # Update meeting with created task count
#         meeting.tasks_created_count = len(created_tasks)
#         meeting.save(update_fields=['tasks_created_count'])
#         
#         return JsonResponse({
#             'success': True,
#             'created_tasks': created_tasks,
#             'failed_tasks': failed_tasks,
#             'total_created': len(created_tasks)
#         })
#         
#     except Exception as e:
#         logger.error(f"Error in create_tasks_from_extraction_api: {str(e)}")
#         return JsonResponse({'error': str(e)}, status=500)


# @login_required
# @require_http_methods(["GET"])
# def get_meeting_details_api(request, meeting_id):
#     """
#     API endpoint to get detailed meeting information
#     """
#     try:
#         if not hasattr(request.user, 'profile') or not request.user.profile.organization:
#             return JsonResponse({'error': 'No organization found'}, status=400)
#         
#         org = request.user.profile.organization
#         meeting = get_object_or_404(MeetingNotes, id=meeting_id, organization=org)
#         
#         return JsonResponse({
#             'id': meeting.id,
#             'title': meeting.title,
#             'meeting_type': meeting.meeting_type,
#             'date': meeting.date.isoformat(),
#             'content': meeting.content,
#             'duration_minutes': meeting.duration_minutes,
#             'processing_status': meeting.processing_status,
#             'tasks_extracted_count': meeting.tasks_extracted_count,
#             'tasks_created_count': meeting.tasks_created_count,
#             'extraction_results': meeting.extraction_results,
#             'action_items': meeting.action_items,
#             'decisions': meeting.decisions
#         })
#         
#     except Exception as e:
#         logger.error(f"Error in get_meeting_details_api: {str(e)}")
#         return JsonResponse({'error': str(e)}, status=500)

# END OF DISABLED MEETING API FUNCTIONS
