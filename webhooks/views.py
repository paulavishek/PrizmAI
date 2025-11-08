"""
Views for Webhook Management
"""
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import JsonResponse
from django.views.decorators.http import require_http_methods
from django.utils import timezone
from django.db.models import Count, Q
from datetime import timedelta

from kanban.models import Board
from webhooks.models import Webhook, WebhookDelivery, WebhookEvent
from webhooks.forms import WebhookForm, WebhookTestForm
from webhooks.tasks import deliver_webhook


@login_required
def webhook_list(request, board_id):
    """List all webhooks for a board"""
    board = get_object_or_404(Board, id=board_id)
    
    # Check if user has access to this board
    if not (board.created_by == request.user or board.members.filter(id=request.user.id).exists()):
        messages.error(request, "You don't have permission to access this board.")
        return redirect('dashboard')
    
    webhooks = Webhook.objects.filter(board=board).order_by('-created_at')
    
    context = {
        'board': board,
        'webhooks': webhooks
    }
    return render(request, 'webhooks/webhook_list.html', context)


@login_required
def webhook_create(request, board_id):
    """Create a new webhook"""
    board = get_object_or_404(Board, id=board_id)
    
    # Check if user has access to this board
    if not (board.created_by == request.user or board.members.filter(id=request.user.id).exists()):
        messages.error(request, "You don't have permission to access this board.")
        return redirect('dashboard')
    
    if request.method == 'POST':
        form = WebhookForm(request.POST)
        if form.is_valid():
            webhook = form.save(commit=False)
            webhook.board = board
            webhook.created_by = request.user
            webhook.save()
            messages.success(request, f'Webhook "{webhook.name}" created successfully!')
            return redirect('webhooks:webhook_list', board_id=board.id)
    else:
        form = WebhookForm()
    
    context = {
        'board': board,
        'form': form
    }
    return render(request, 'webhooks/webhook_form.html', context)


@login_required
def webhook_detail(request, webhook_id):
    """View webhook details and delivery history"""
    webhook = get_object_or_404(Webhook, id=webhook_id)
    board = webhook.board
    
    # Check if user has access
    if not (board.created_by == request.user or board.members.filter(id=request.user.id).exists()):
        messages.error(request, "You don't have permission to access this webhook.")
        return redirect('dashboard')
    
    # Get recent deliveries
    deliveries = webhook.deliveries.all()[:50]
    
    # Get delivery statistics
    last_24h = timezone.now() - timedelta(hours=24)
    stats = {
        'total': webhook.total_deliveries,
        'successful': webhook.successful_deliveries,
        'failed': webhook.failed_deliveries,
        'success_rate': webhook.success_rate,
        'last_24h': webhook.deliveries.filter(created_at__gte=last_24h).count(),
    }
    
    context = {
        'webhook': webhook,
        'board': board,
        'deliveries': deliveries,
        'stats': stats
    }
    return render(request, 'webhooks/webhook_detail.html', context)


@login_required
def webhook_edit(request, webhook_id):
    """Edit an existing webhook"""
    webhook = get_object_or_404(Webhook, id=webhook_id)
    board = webhook.board
    
    # Check if user has access
    if not (board.created_by == request.user or board.members.filter(id=request.user.id).exists()):
        messages.error(request, "You don't have permission to access this webhook.")
        return redirect('dashboard')
    
    if request.method == 'POST':
        form = WebhookForm(request.POST, instance=webhook)
        if form.is_valid():
            form.save()
            messages.success(request, f'Webhook "{webhook.name}" updated successfully!')
            return redirect('webhooks:webhook_detail', webhook_id=webhook.id)
    else:
        form = WebhookForm(instance=webhook)
    
    context = {
        'board': board,
        'webhook': webhook,
        'form': form
    }
    return render(request, 'webhooks/webhook_form.html', context)


@login_required
@require_http_methods(["POST"])
def webhook_delete(request, webhook_id):
    """Delete a webhook"""
    webhook = get_object_or_404(Webhook, id=webhook_id)
    board = webhook.board
    
    # Check if user has access
    if not (board.created_by == request.user or board.members.filter(id=request.user.id).exists()):
        messages.error(request, "You don't have permission to delete this webhook.")
        return redirect('dashboard')
    
    webhook_name = webhook.name
    webhook.delete()
    messages.success(request, f'Webhook "{webhook_name}" deleted successfully!')
    return redirect('webhooks:webhook_list', board_id=board.id)


@login_required
@require_http_methods(["POST"])
def webhook_toggle(request, webhook_id):
    """Toggle webhook active status"""
    webhook = get_object_or_404(Webhook, id=webhook_id)
    board = webhook.board
    
    # Check if user has access
    if not (board.created_by == request.user or board.members.filter(id=request.user.id).exists()):
        return JsonResponse({'error': 'Permission denied'}, status=403)
    
    webhook.is_active = not webhook.is_active
    if webhook.is_active and webhook.status == 'failed':
        webhook.status = 'active'
        webhook.consecutive_failures = 0
    webhook.save()
    
    return JsonResponse({
        'success': True,
        'is_active': webhook.is_active,
        'status': webhook.status
    })


@login_required
@require_http_methods(["POST"])
def webhook_test(request, webhook_id):
    """Send a test webhook"""
    webhook = get_object_or_404(Webhook, id=webhook_id)
    board = webhook.board
    
    # Check if user has access
    if not (board.created_by == request.user or board.members.filter(id=request.user.id).exists()):
        return JsonResponse({'error': 'Permission denied'}, status=403)
    
    # Create test payload
    test_data = {
        'id': 999999,
        'title': 'Test Webhook Event',
        'description': 'This is a test webhook delivery from PrizmAI',
        'board': {
            'id': board.id,
            'name': board.name
        },
        'test': True,
        'timestamp': timezone.now().isoformat()
    }
    
    # Create delivery record
    delivery = WebhookDelivery.objects.create(
        webhook=webhook,
        event_type='test.event',
        payload=test_data,
        status='pending'
    )
    
    # Queue delivery task
    deliver_webhook.delay(delivery.id)
    
    messages.success(request, 'Test webhook queued for delivery!')
    return JsonResponse({
        'success': True,
        'delivery_id': delivery.id,
        'message': 'Test webhook sent'
    })


@login_required
def webhook_events(request, board_id):
    """View recent webhook events for a board"""
    board = get_object_or_404(Board, id=board_id)
    
    # Check if user has access
    if not (board.created_by == request.user or board.members.filter(id=request.user.id).exists()):
        messages.error(request, "You don't have permission to access this board.")
        return redirect('dashboard')
    
    # Get recent events
    events = WebhookEvent.objects.filter(board=board).order_by('-created_at')[:100]
    
    # Get event statistics
    last_24h = timezone.now() - timedelta(hours=24)
    stats = {
        'total_events': events.count(),
        'last_24h': WebhookEvent.objects.filter(board=board, created_at__gte=last_24h).count(),
        'by_type': WebhookEvent.objects.filter(board=board, created_at__gte=last_24h).values('event_type').annotate(count=Count('id'))
    }
    
    context = {
        'board': board,
        'events': events,
        'stats': stats
    }
    return render(request, 'webhooks/webhook_events.html', context)
