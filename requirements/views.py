import csv
import json
import logging

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db.models import Count, Q
from django.http import HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_http_methods, require_POST

from kanban.models import Board, BoardMembership, Task, Strategy

from .forms import (
    ProjectObjectiveForm,
    RequirementCategoryForm,
    RequirementCommentForm,
    RequirementForm,
)
from .models import (
    ProjectObjective,
    Requirement,
    RequirementCategory,
    RequirementComment,
    RequirementHistory,
)

logger = logging.getLogger(__name__)


# ── Helpers ──────────────────────────────────────────────────────────
def _get_board_and_check_access(request, board_id, require_edit=False):
    """Return (board, membership) or raise 403."""
    board = get_object_or_404(Board, pk=board_id)
    membership = BoardMembership.objects.filter(user=request.user, board=board).first()

    # Demo boards always grant access
    is_demo = getattr(board, 'is_sandbox_copy', False) or (
        board.organization and board.organization.is_demo
    )
    if not is_demo:
        if not membership and board.created_by != request.user:
            from django.http import HttpResponseForbidden
            return None, None
        if require_edit:
            role = getattr(membership, 'role', None)
            role_name = getattr(role, 'name', '') if role else ''
            if role_name.lower() == 'viewer':
                from django.http import HttpResponseForbidden
                return None, None

    return board, membership


def _get_user_role(membership, board, user):
    """Return the user's role name for a board."""
    if membership:
        role = getattr(membership, 'role', None)
        return getattr(role, 'name', 'Member') if role else 'Member'
    if board.created_by == user:
        return 'Owner'
    return 'Viewer'


# ── Requirements Dashboard (list) ───────────────────────────────────
@login_required
def requirements_dashboard(request, board_id):
    board, membership = _get_board_and_check_access(request, board_id)
    if board is None:
        messages.error(request, "You don't have access to this board.")
        return redirect('board_list')

    requirements = Requirement.objects.filter(board=board).select_related(
        'category', 'created_by', 'assigned_reviewer', 'parent',
    )

    # Filters
    status_filter = request.GET.get('status', '')
    type_filter = request.GET.get('type', '')
    priority_filter = request.GET.get('priority', '')
    category_filter = request.GET.get('category', '')
    search = request.GET.get('q', '')

    if status_filter:
        requirements = requirements.filter(status=status_filter)
    if type_filter:
        requirements = requirements.filter(type=type_filter)
    if priority_filter:
        requirements = requirements.filter(priority=priority_filter)
    if category_filter:
        requirements = requirements.filter(category_id=category_filter)
    if search:
        requirements = requirements.filter(
            Q(title__icontains=search) | Q(identifier__icontains=search) | Q(description__icontains=search)
        )

    # Stats
    total = Requirement.objects.filter(board=board).count()
    status_counts = dict(
        Requirement.objects.filter(board=board)
        .values_list('status')
        .annotate(count=Count('id'))
    )
    categories = RequirementCategory.objects.filter(board=board)
    objectives = ProjectObjective.objects.filter(board=board)

    # Coverage: requirements with at least one linked task
    linked_count = Requirement.objects.filter(board=board, linked_tasks__isnull=False).distinct().count()
    coverage_pct = round((linked_count / total) * 100) if total > 0 else 0

    role = _get_user_role(membership, board, request.user)
    can_edit = role.lower() in ('owner', 'admin', 'member')

    context = {
        'board': board,
        'requirements': requirements,
        'total': total,
        'status_counts': status_counts,
        'categories': categories,
        'objectives': objectives,
        'coverage_pct': coverage_pct,
        'linked_count': linked_count,
        'can_edit': can_edit,
        'status_filter': status_filter,
        'type_filter': type_filter,
        'priority_filter': priority_filter,
        'category_filter': category_filter,
        'search': search,
        'status_choices': Requirement.STATUS_CHOICES,
        'type_choices': Requirement.TYPE_CHOICES,
        'priority_choices': Requirement.PRIORITY_CHOICES,
    }
    return render(request, 'requirements/requirements_dashboard.html', context)


# ── Requirement Detail ───────────────────────────────────────────────
@login_required
def requirement_detail(request, board_id, pk):
    board, membership = _get_board_and_check_access(request, board_id)
    if board is None:
        messages.error(request, "You don't have access to this board.")
        return redirect('board_list')

    requirement = get_object_or_404(Requirement, pk=pk, board=board)
    history = requirement.history.all()[:20]
    children = requirement.children.all()
    linked_tasks = requirement.linked_tasks.select_related('column', 'assigned_to').all()
    linked_strategies = requirement.linked_strategies.all()
    objectives = requirement.objectives.all()
    comments = requirement.comments.select_related('author').all()
    comment_form = RequirementCommentForm()

    role = _get_user_role(membership, board, request.user)
    can_edit = role.lower() in ('owner', 'admin', 'member')

    # Available tasks for linking (exclude already linked ones)
    from kanban.models import Task
    already_linked_ids = requirement.linked_tasks.values_list('id', flat=True)
    available_tasks = Task.objects.filter(
        column__board=board
    ).exclude(id__in=already_linked_ids).order_by('title')[:50]

    context = {
        'board': board,
        'requirement': requirement,
        'history': history,
        'children': children,
        'linked_tasks': linked_tasks,
        'linked_strategies': linked_strategies,
        'objectives': objectives,
        'comments': comments,
        'comment_form': comment_form,
        'can_edit': can_edit,
        'status_choices': Requirement.STATUS_CHOICES,
        'available_tasks': available_tasks,
    }
    return render(request, 'requirements/requirement_detail.html', context)


# ── Create Requirement ───────────────────────────────────────────────
@login_required
def requirement_create(request, board_id):
    board, membership = _get_board_and_check_access(request, board_id, require_edit=True)
    if board is None:
        messages.error(request, "You don't have permission to create requirements on this board.")
        return redirect('board_list')

    if request.method == 'POST':
        form = RequirementForm(request.POST, board=board)
        if form.is_valid():
            req = form.save(commit=False)
            req.board = board
            req.created_by = request.user
            req.save(user=request.user)
            form.save_m2m()
            RequirementHistory.objects.create(
                requirement=req,
                old_status='',
                new_status=req.status,
                changed_by=request.user,
                notes=f"Requirement created with status: {req.get_status_display()}",
            )
            messages.success(request, f'Requirement {req.identifier} created successfully!')
            return redirect('requirements:dashboard', board_id=board.id)
    else:
        form = RequirementForm(board=board)

    return render(request, 'requirements/requirement_form.html', {
        'board': board,
        'form': form,
        'is_edit': False,
    })


# ── Update Requirement ───────────────────────────────────────────────
@login_required
def requirement_update(request, board_id, pk):
    board, membership = _get_board_and_check_access(request, board_id, require_edit=True)
    if board is None:
        messages.error(request, "You don't have permission to edit requirements on this board.")
        return redirect('board_list')

    requirement = get_object_or_404(Requirement, pk=pk, board=board)

    if request.method == 'POST':
        form = RequirementForm(request.POST, instance=requirement, board=board)
        if form.is_valid():
            req = form.save(commit=False)
            req.updated_by = request.user
            req.save(user=request.user)
            form.save_m2m()
            messages.success(request, f'Requirement {req.identifier} updated successfully!')
            return redirect('requirements:requirement_detail', board_id=board.id, pk=req.pk)
    else:
        form = RequirementForm(instance=requirement, board=board)

    return render(request, 'requirements/requirement_form.html', {
        'board': board,
        'form': form,
        'requirement': requirement,
        'is_edit': True,
    })


# ── Delete Requirement ───────────────────────────────────────────────
@login_required
@require_POST
def requirement_delete(request, board_id, pk):
    board, membership = _get_board_and_check_access(request, board_id, require_edit=True)
    if board is None:
        messages.error(request, "You don't have permission to delete requirements.")
        return redirect('board_list')

    requirement = get_object_or_404(Requirement, pk=pk, board=board)
    identifier = requirement.identifier
    requirement.delete()
    messages.success(request, f'Requirement {identifier} deleted.')
    return redirect('requirements:dashboard', board_id=board.id)


# ── Quick Status Update ─────────────────────────────────────────────
@login_required
@require_POST
def requirement_status_update(request, board_id, pk):
    board, membership = _get_board_and_check_access(request, board_id, require_edit=True)
    if board is None:
        return JsonResponse({'error': 'Permission denied'}, status=403)

    requirement = get_object_or_404(Requirement, pk=pk, board=board)
    new_status = request.POST.get('status', '')

    valid_statuses = dict(Requirement.STATUS_CHOICES)
    if new_status not in valid_statuses:
        return JsonResponse({'error': f'Invalid status: {new_status}'}, status=400)

    old_status = requirement.status
    requirement.status = new_status
    requirement.updated_by = request.user
    requirement.save(user=request.user)

    messages.success(request, f'{requirement.identifier} status updated to {valid_statuses[new_status]}.')
    return redirect('requirements:requirement_detail', board_id=board.id, pk=pk)


# ── Add Comment ──────────────────────────────────────────────────────
@login_required
@require_POST
def requirement_add_comment(request, board_id, pk):
    board, membership = _get_board_and_check_access(request, board_id)
    if board is None:
        return JsonResponse({'error': 'Permission denied'}, status=403)

    requirement = get_object_or_404(Requirement, pk=pk, board=board)
    form = RequirementCommentForm(request.POST)
    if form.is_valid():
        comment = form.save(commit=False)
        comment.requirement = requirement
        comment.author = request.user
        comment.save()
        messages.success(request, 'Comment added.')
    return redirect('requirements:requirement_detail', board_id=board.id, pk=pk)


# ── Category Create ──────────────────────────────────────────────────
@login_required
def category_create(request, board_id):
    board, membership = _get_board_and_check_access(request, board_id, require_edit=True)
    if board is None:
        messages.error(request, "You don't have permission.")
        return redirect('board_list')

    if request.method == 'POST':
        form = RequirementCategoryForm(request.POST)
        if form.is_valid():
            cat = form.save(commit=False)
            cat.board = board
            cat.save()
            messages.success(request, f'Category "{cat.name}" created!')
            return redirect('requirements:dashboard', board_id=board.id)
    else:
        form = RequirementCategoryForm()

    return render(request, 'requirements/category_form.html', {
        'board': board,
        'form': form,
    })


# ── Objective Create ─────────────────────────────────────────────────
@login_required
def objective_create(request, board_id):
    board, membership = _get_board_and_check_access(request, board_id, require_edit=True)
    if board is None:
        messages.error(request, "You don't have permission.")
        return redirect('board_list')

    if request.method == 'POST':
        form = ProjectObjectiveForm(request.POST)
        if form.is_valid():
            obj = form.save(commit=False)
            obj.board = board
            obj.created_by = request.user
            obj.save()
            messages.success(request, f'Objective "{obj.title}" created!')
            return redirect('requirements:traceability_matrix', board_id=board.id)
    else:
        form = ProjectObjectiveForm()

    return render(request, 'requirements/objective_form.html', {
        'board': board,
        'form': form,
    })


# ── Traceability Matrix ─────────────────────────────────────────────
@login_required
def traceability_matrix(request, board_id):
    board, membership = _get_board_and_check_access(request, board_id)
    if board is None:
        messages.error(request, "You don't have access to this board.")
        return redirect('board_list')

    objectives = ProjectObjective.objects.filter(board=board)
    requirements = list(Requirement.objects.filter(board=board).prefetch_related(
        'objectives', 'linked_tasks', 'linked_strategies',
    ))
    tasks = list(Task.objects.filter(column__board=board).select_related('column', 'assigned_to'))

    # Build objectives × requirements matrix
    obj_matrix = []
    for obj in objectives:
        obj_req_ids = set(obj.requirements.values_list('id', flat=True))
        links = [req.id in obj_req_ids for req in requirements]
        obj_matrix.append({'objective': obj, 'links': links})

    # Build requirements × tasks matrix
    task_matrix = []
    covered_count = 0
    for req in requirements:
        req_task_ids = set(req.linked_tasks.values_list('id', flat=True))
        links = [t.id in req_task_ids for t in tasks]
        task_matrix.append({'requirement': req, 'links': links})
        if any(links):
            covered_count += 1

    total = len(requirements)
    uncovered_count = total - covered_count
    coverage_pct = round((covered_count / total) * 100) if total > 0 else 0

    role = _get_user_role(membership, board, request.user)
    can_edit = role.lower() in ('owner', 'admin', 'member')

    context = {
        'board': board,
        'objectives': objectives,
        'requirements': requirements,
        'tasks': tasks,
        'obj_matrix': obj_matrix,
        'task_matrix': task_matrix,
        'covered_count': covered_count,
        'uncovered_count': uncovered_count,
        'coverage_pct': coverage_pct,
        'can_edit': can_edit,
    }
    return render(request, 'requirements/traceability_matrix.html', context)


# ── Link Requirement ↔ Task ──────────────────────────────────────────
@login_required
@require_POST
def requirement_link_task(request, board_id, pk):
    board, membership = _get_board_and_check_access(request, board_id, require_edit=True)
    if board is None:
        return JsonResponse({'error': 'Permission denied'}, status=403)

    requirement = get_object_or_404(Requirement, pk=pk, board=board)
    task_id = request.POST.get('task_id')
    task = get_object_or_404(Task, pk=task_id, column__board=board)
    requirement.linked_tasks.add(task)
    messages.success(request, f'Task "{task.title}" linked to {requirement.identifier}.')
    return redirect('requirements:requirement_detail', board_id=board.id, pk=pk)


# ── Unlink Requirement ↔ Task ────────────────────────────────────────
@login_required
@require_POST
def requirement_unlink_task(request, board_id, pk):
    board, membership = _get_board_and_check_access(request, board_id, require_edit=True)
    if board is None:
        return JsonResponse({'error': 'Permission denied'}, status=403)

    requirement = get_object_or_404(Requirement, pk=pk, board=board)
    task_id = request.POST.get('task_id')
    task = get_object_or_404(Task, pk=task_id, column__board=board)
    requirement.linked_tasks.remove(task)
    messages.success(request, f'Task "{task.title}" unlinked from {requirement.identifier}.')
    return redirect('requirements:requirement_detail', board_id=board.id, pk=pk)


# ── Link Requirement ↔ Objective ─────────────────────────────────────
@login_required
@require_POST
def requirement_link_objective(request, board_id, pk):
    board, membership = _get_board_and_check_access(request, board_id, require_edit=True)
    if board is None:
        return JsonResponse({'error': 'Permission denied'}, status=403)

    requirement = get_object_or_404(Requirement, pk=pk, board=board)
    objective_id = request.POST.get('objective_id')
    objective = get_object_or_404(ProjectObjective, pk=objective_id, board=board)
    requirement.objectives.add(objective)
    messages.success(request, f'Objective linked to {requirement.identifier}.')
    return redirect('requirements:requirement_detail', board_id=board.id, pk=pk)


# ── Export CSV ───────────────────────────────────────────────────────
@login_required
def export_requirements_csv(request, board_id):
    board, membership = _get_board_and_check_access(request, board_id)
    if board is None:
        messages.error(request, "You don't have access.")
        return redirect('board_list')

    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = f'attachment; filename="requirements-{board.name}.csv"'

    writer = csv.writer(response)
    writer.writerow([
        'ID', 'Title', 'Type', 'Status', 'Priority', 'Category',
        'Description', 'Acceptance Criteria', 'Linked Tasks',
        'Created By', 'Created At', 'Updated At',
    ])

    requirements = Requirement.objects.filter(board=board).select_related(
        'category', 'created_by',
    ).prefetch_related('linked_tasks')

    for req in requirements:
        linked = ', '.join(t.title for t in req.linked_tasks.all())
        writer.writerow([
            req.identifier,
            req.title,
            req.get_type_display(),
            req.get_status_display(),
            req.get_priority_display(),
            req.category.name if req.category else '',
            req.description,
            req.acceptance_criteria,
            linked,
            req.created_by.username if req.created_by else '',
            req.created_at.strftime('%Y-%m-%d %H:%M'),
            req.updated_at.strftime('%Y-%m-%d %H:%M'),
        ])

    return response


# ── API: Requirements data for Spectra / JSON ────────────────────────
@login_required
@require_http_methods(["GET"])
def api_requirements_data(request, board_id):
    """JSON endpoint for Spectra and frontend to fetch requirement data."""
    board, membership = _get_board_and_check_access(request, board_id)
    if board is None:
        return JsonResponse({'error': 'Access denied'}, status=403)

    from .spectra_data import get_requirements_context_for_board
    data = get_requirements_context_for_board(board)
    return JsonResponse(data)
