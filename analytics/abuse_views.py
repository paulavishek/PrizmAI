"""
Abuse Monitoring Dashboard Views

Provides admin interface for monitoring demo abuse, managing blocked IPs,
viewing suspicious activity, and tracking abuse prevention effectiveness.
"""
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.admin.views.decorators import staff_member_required
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.views.decorators.http import require_POST, require_http_methods
from django.utils import timezone
from django.db.models import Count, Sum, Avg, Q, F
from django.core.paginator import Paginator
from datetime import timedelta
import json
import logging

logger = logging.getLogger(__name__)


@staff_member_required
def abuse_dashboard(request):
    """
    Main abuse monitoring dashboard.
    Shows overview of abuse prevention metrics and suspicious activity.
    """
    from analytics.models import DemoAbusePrevention, DemoSession
    
    # Date range
    days = int(request.GET.get('days', 7))
    start_date = timezone.now() - timedelta(days=days)
    
    # === OVERVIEW STATS ===
    total_records = DemoAbusePrevention.objects.count()
    flagged_count = DemoAbusePrevention.objects.filter(is_flagged=True).count()
    blocked_count = DemoAbusePrevention.objects.filter(is_blocked=True).count()
    
    # Recent activity
    recent_records = DemoAbusePrevention.objects.filter(
        last_seen__gte=start_date
    ).count()
    
    # Aggregate stats
    aggregate_stats = DemoAbusePrevention.objects.aggregate(
        total_ai_generations=Sum('total_ai_generations'),
        total_projects=Sum('total_projects_created'),
        total_sessions=Sum('total_sessions_created'),
        avg_sessions_per_visitor=Avg('total_sessions_created'),
        avg_ai_per_visitor=Avg('total_ai_generations'),
    )
    
    # === HIGH RISK VISITORS ===
    high_risk_visitors = DemoAbusePrevention.objects.filter(
        Q(is_flagged=True) | Q(total_sessions_created__gte=5) | Q(total_ai_generations__gte=30)
    ).order_by('-last_seen')[:20]
    
    # === RECENT ABUSE ATTEMPTS ===
    recent_abuse = DemoAbusePrevention.objects.filter(
        last_seen__gte=start_date
    ).order_by('-total_sessions_created')[:10]
    
    # === SESSIONS BY HOUR ===
    sessions_by_hour = DemoSession.objects.filter(
        created_at__gte=start_date
    ).extra(
        select={'hour': 'STRFTIME("%%H", created_at)'}
    ).values('hour').annotate(
        count=Count('id')
    ).order_by('hour')
    
    # === DEMO MODE DISTRIBUTION ===
    mode_distribution = DemoSession.objects.filter(
        created_at__gte=start_date
    ).values('demo_mode').annotate(
        count=Count('id')
    )
    
    # === LIMITATIONS HIT ===
    # Count sessions that hit various limitations
    sessions_with_limits = DemoSession.objects.filter(
        created_at__gte=start_date
    )
    
    limitation_stats = {
        'project_limit': sessions_with_limits.filter(
            projects_created_in_demo__gte=2
        ).count(),
        'ai_limit': sessions_with_limits.filter(
            ai_generations_used__gte=20
        ).count(),
        'export_blocked': sessions_with_limits.filter(
            export_attempts__gt=0
        ).count(),
    }
    
    # === CONVERSION METRICS ===
    conversion_stats = DemoSession.objects.filter(
        created_at__gte=start_date
    ).aggregate(
        total_sessions=Count('id'),
        conversions=Count('id', filter=Q(converted_to_signup=True)),
    )
    
    if conversion_stats['total_sessions'] > 0:
        conversion_stats['rate'] = round(
            conversion_stats['conversions'] / conversion_stats['total_sessions'] * 100, 1
        )
    else:
        conversion_stats['rate'] = 0
    
    context = {
        'days': days,
        'total_records': total_records,
        'flagged_count': flagged_count,
        'blocked_count': blocked_count,
        'recent_records': recent_records,
        'aggregate_stats': aggregate_stats,
        'high_risk_visitors': high_risk_visitors,
        'recent_abuse': recent_abuse,
        'sessions_by_hour': list(sessions_by_hour),
        'mode_distribution': list(mode_distribution),
        'limitation_stats': limitation_stats,
        'conversion_stats': conversion_stats,
    }
    
    return render(request, 'admin/abuse_dashboard.html', context)


@staff_member_required
def abuse_visitor_list(request):
    """
    List all visitors with abuse prevention records.
    Supports filtering and pagination.
    """
    from analytics.models import DemoAbusePrevention
    
    # Filters
    filter_type = request.GET.get('filter', 'all')
    search = request.GET.get('search', '')
    sort = request.GET.get('sort', '-last_seen')
    
    queryset = DemoAbusePrevention.objects.all()
    
    # Apply filters
    if filter_type == 'flagged':
        queryset = queryset.filter(is_flagged=True)
    elif filter_type == 'blocked':
        queryset = queryset.filter(is_blocked=True)
    elif filter_type == 'high_usage':
        queryset = queryset.filter(total_sessions_created__gte=5)
    elif filter_type == 'high_ai':
        queryset = queryset.filter(total_ai_generations__gte=30)
    
    # Search by IP
    if search:
        queryset = queryset.filter(ip_address__icontains=search)
    
    # Sorting
    valid_sorts = ['last_seen', '-last_seen', 'total_sessions_created', 
                   '-total_sessions_created', 'total_ai_generations', '-total_ai_generations']
    if sort in valid_sorts:
        queryset = queryset.order_by(sort)
    
    # Pagination
    paginator = Paginator(queryset, 50)
    page = request.GET.get('page', 1)
    visitors = paginator.get_page(page)
    
    context = {
        'visitors': visitors,
        'filter_type': filter_type,
        'search': search,
        'sort': sort,
        'total_count': queryset.count(),
    }
    
    return render(request, 'admin/abuse_visitor_list.html', context)


@staff_member_required
def abuse_visitor_detail(request, visitor_id):
    """
    Detailed view of a specific visitor's abuse record.
    """
    from analytics.models import DemoAbusePrevention, DemoSession
    
    visitor = get_object_or_404(DemoAbusePrevention, id=visitor_id)
    
    # Get associated sessions
    sessions = DemoSession.objects.filter(
        ip_address=visitor.ip_address
    ).order_by('-created_at')[:20]
    
    # VPN check
    vpn_info = None
    try:
        from kanban.utils.vpn_detection import comprehensive_ip_check
        vpn_info = comprehensive_ip_check(visitor.ip_address)
    except Exception as e:
        logger.warning(f"VPN check failed: {e}")
    
    context = {
        'visitor': visitor,
        'sessions': sessions,
        'vpn_info': vpn_info,
    }
    
    return render(request, 'admin/abuse_visitor_detail.html', context)


@staff_member_required
@require_POST
def abuse_action(request):
    """
    Handle abuse management actions (flag, block, unblock).
    """
    from analytics.models import DemoAbusePrevention
    
    action = request.POST.get('action')
    visitor_id = request.POST.get('visitor_id')
    ip_address = request.POST.get('ip_address')
    reason = request.POST.get('reason', '')
    
    try:
        if visitor_id:
            visitor = get_object_or_404(DemoAbusePrevention, id=visitor_id)
        elif ip_address:
            visitor = DemoAbusePrevention.objects.filter(ip_address=ip_address).first()
            if not visitor:
                return JsonResponse({'success': False, 'error': 'IP not found'})
        else:
            return JsonResponse({'success': False, 'error': 'No visitor specified'})
        
        if action == 'flag':
            visitor.is_flagged = True
            visitor.flag_reason = reason or f"Manually flagged by {request.user.username}"
            visitor.save()
            message = f"Flagged IP {visitor.ip_address}"
            
        elif action == 'block':
            visitor.is_blocked = True
            visitor.is_flagged = True
            visitor.flag_reason = reason or f"Blocked by {request.user.username}"
            visitor.save()
            message = f"Blocked IP {visitor.ip_address}"
            
        elif action == 'unblock':
            visitor.is_blocked = False
            visitor.save()
            message = f"Unblocked IP {visitor.ip_address}"
            
        elif action == 'unflag':
            visitor.is_flagged = False
            visitor.flag_reason = ''
            visitor.save()
            message = f"Unflagged IP {visitor.ip_address}"
            
        elif action == 'reset_counters':
            visitor.total_ai_generations = 0
            visitor.total_projects_created = 0
            visitor.sessions_last_hour = 0
            visitor.sessions_last_24h = 0
            visitor.save()
            message = f"Reset counters for IP {visitor.ip_address}"
            
        else:
            return JsonResponse({'success': False, 'error': 'Invalid action'})
        
        logger.info(f"Abuse action: {action} on {visitor.ip_address} by {request.user.username}")
        
        return JsonResponse({'success': True, 'message': message})
        
    except Exception as e:
        logger.error(f"Abuse action error: {e}")
        return JsonResponse({'success': False, 'error': str(e)})


@staff_member_required
@require_POST
def abuse_bulk_action(request):
    """
    Handle bulk actions on multiple visitors.
    """
    from analytics.models import DemoAbusePrevention
    
    action = request.POST.get('action')
    visitor_ids = request.POST.getlist('visitor_ids[]') or json.loads(request.POST.get('visitor_ids', '[]'))
    
    if not visitor_ids:
        return JsonResponse({'success': False, 'error': 'No visitors selected'})
    
    try:
        visitors = DemoAbusePrevention.objects.filter(id__in=visitor_ids)
        count = visitors.count()
        
        if action == 'flag':
            visitors.update(
                is_flagged=True,
                flag_reason=f"Bulk flagged by {request.user.username}"
            )
            message = f"Flagged {count} visitors"
            
        elif action == 'block':
            visitors.update(
                is_blocked=True,
                is_flagged=True,
                flag_reason=f"Bulk blocked by {request.user.username}"
            )
            message = f"Blocked {count} visitors"
            
        elif action == 'unblock':
            visitors.update(is_blocked=False)
            message = f"Unblocked {count} visitors"
            
        elif action == 'delete':
            visitors.delete()
            message = f"Deleted {count} visitors"
            
        else:
            return JsonResponse({'success': False, 'error': 'Invalid action'})
        
        logger.info(f"Bulk abuse action: {action} on {count} visitors by {request.user.username}")
        
        return JsonResponse({'success': True, 'message': message})
        
    except Exception as e:
        logger.error(f"Bulk abuse action error: {e}")
        return JsonResponse({'success': False, 'error': str(e)})


@staff_member_required
def abuse_ip_lookup(request):
    """
    Look up information about a specific IP address.
    """
    ip_address = request.GET.get('ip', '')
    
    if not ip_address:
        return render(request, 'admin/abuse_ip_lookup.html', {'ip': None})
    
    from analytics.models import DemoAbusePrevention, DemoSession
    
    # Get abuse record
    abuse_record = DemoAbusePrevention.objects.filter(ip_address=ip_address).first()
    
    # Get sessions from this IP
    sessions = DemoSession.objects.filter(ip_address=ip_address).order_by('-created_at')[:20]
    
    # VPN check
    vpn_info = None
    try:
        from kanban.utils.vpn_detection import comprehensive_ip_check
        vpn_info = comprehensive_ip_check(ip_address)
    except Exception as e:
        logger.warning(f"VPN check failed: {e}")
    
    context = {
        'ip': ip_address,
        'abuse_record': abuse_record,
        'sessions': sessions,
        'vpn_info': vpn_info,
        'session_count': sessions.count(),
    }
    
    return render(request, 'admin/abuse_ip_lookup.html', context)


@staff_member_required
def abuse_realtime_monitor(request):
    """
    Real-time abuse monitoring view.
    Shows live session activity and alerts.
    """
    from analytics.models import DemoSession, DemoAbusePrevention
    
    # Recent sessions (last hour)
    one_hour_ago = timezone.now() - timedelta(hours=1)
    recent_sessions = DemoSession.objects.filter(
        created_at__gte=one_hour_ago
    ).order_by('-created_at')[:50]
    
    # Active flagged visitors
    active_flagged = DemoAbusePrevention.objects.filter(
        is_flagged=True,
        last_seen__gte=one_hour_ago
    ).order_by('-last_seen')[:10]
    
    # Sessions per minute (last 10 minutes)
    ten_minutes_ago = timezone.now() - timedelta(minutes=10)
    sessions_last_10_min = DemoSession.objects.filter(
        created_at__gte=ten_minutes_ago
    ).count()
    
    # Alert conditions
    alerts = []
    
    # High session rate alert
    if sessions_last_10_min > 50:
        alerts.append({
            'level': 'warning',
            'message': f'High session rate: {sessions_last_10_min} sessions in last 10 minutes'
        })
    
    # Multiple sessions from same IP
    duplicate_ips = DemoSession.objects.filter(
        created_at__gte=one_hour_ago
    ).values('ip_address').annotate(
        count=Count('id')
    ).filter(count__gte=3).order_by('-count')[:5]
    
    for dup in duplicate_ips:
        if dup['count'] >= 5:
            alerts.append({
                'level': 'danger',
                'message': f"IP {dup['ip_address']} created {dup['count']} sessions in last hour"
            })
        else:
            alerts.append({
                'level': 'warning',
                'message': f"IP {dup['ip_address']} created {dup['count']} sessions in last hour"
            })
    
    context = {
        'recent_sessions': recent_sessions,
        'active_flagged': active_flagged,
        'sessions_last_10_min': sessions_last_10_min,
        'alerts': alerts,
        'duplicate_ips': duplicate_ips,
    }
    
    return render(request, 'admin/abuse_realtime_monitor.html', context)


@staff_member_required
def abuse_api_sessions(request):
    """
    API endpoint for real-time session data.
    Used by AJAX polling in the realtime monitor.
    """
    from analytics.models import DemoSession
    
    since = request.GET.get('since')
    if since:
        try:
            since_dt = timezone.datetime.fromisoformat(since.replace('Z', '+00:00'))
        except:
            since_dt = timezone.now() - timedelta(minutes=1)
    else:
        since_dt = timezone.now() - timedelta(minutes=1)
    
    sessions = DemoSession.objects.filter(
        created_at__gte=since_dt
    ).order_by('-created_at')[:20]
    
    data = [{
        'id': s.id,
        'session_id': s.session_id[:8],
        'ip_address': s.ip_address,
        'demo_mode': s.demo_mode,
        'device_type': s.device_type,
        'created_at': s.created_at.isoformat(),
        'ai_used': s.ai_generations_used,
        'projects': s.projects_created_in_demo,
    } for s in sessions]
    
    return JsonResponse({
        'sessions': data,
        'count': len(data),
        'timestamp': timezone.now().isoformat(),
    })


@staff_member_required
def abuse_stats_api(request):
    """
    API endpoint for abuse statistics.
    """
    from analytics.models import DemoAbusePrevention, DemoSession
    from kanban.utils.demo_abuse_prevention import get_abuse_stats
    from kanban.utils.email_validation import get_blocklist_stats
    from kanban.utils.vpn_detection import get_vpn_detection_stats
    
    days = int(request.GET.get('days', 7))
    start_date = timezone.now() - timedelta(days=days)
    
    # Abuse prevention stats
    abuse_stats = {}
    try:
        abuse_stats = get_abuse_stats()
    except:
        pass
    
    # Email blocklist stats
    email_stats = {}
    try:
        email_stats = get_blocklist_stats()
    except:
        pass
    
    # VPN detection stats
    vpn_stats = {}
    try:
        vpn_stats = get_vpn_detection_stats()
    except:
        pass
    
    # Session stats
    session_stats = DemoSession.objects.filter(
        created_at__gte=start_date
    ).aggregate(
        total=Count('id'),
        solo=Count('id', filter=Q(demo_mode='solo')),
        team=Count('id', filter=Q(demo_mode='team')),
        conversions=Count('id', filter=Q(converted_to_signup=True)),
        avg_ai=Avg('ai_generations_used'),
    )
    
    return JsonResponse({
        'abuse': abuse_stats,
        'email': email_stats,
        'vpn': vpn_stats,
        'sessions': session_stats,
        'period_days': days,
    })


@staff_member_required
def abuse_export(request):
    """
    Export abuse data as CSV.
    """
    import csv
    from django.http import HttpResponse
    from analytics.models import DemoAbusePrevention
    
    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = f'attachment; filename="abuse_data_{timezone.now().strftime("%Y%m%d")}.csv"'
    
    writer = csv.writer(response)
    writer.writerow([
        'IP Address', 'Fingerprint', 'Total Sessions', 'Total AI Generations',
        'Total Projects', 'Is Flagged', 'Is Blocked', 'Flag Reason',
        'First Seen', 'Last Seen'
    ])
    
    for record in DemoAbusePrevention.objects.all().order_by('-last_seen'):
        writer.writerow([
            record.ip_address,
            record.browser_fingerprint[:16] + '...' if record.browser_fingerprint else '',
            record.total_sessions_created,
            record.total_ai_generations,
            record.total_projects_created,
            'Yes' if record.is_flagged else 'No',
            'Yes' if record.is_blocked else 'No',
            record.flag_reason,
            record.first_seen.strftime('%Y-%m-%d %H:%M'),
            record.last_seen.strftime('%Y-%m-%d %H:%M'),
        ])
    
    return response
