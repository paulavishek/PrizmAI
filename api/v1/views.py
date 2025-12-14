"""
API Views for v1
RESTful endpoints for external integrations
"""
from rest_framework import viewsets, status, permissions
from rest_framework.decorators import action, api_view, permission_classes, authentication_classes
from rest_framework.response import Response
from rest_framework.pagination import PageNumberPagination
from django.shortcuts import get_object_or_404
from django.db.models import Q
from django.utils import timezone
from datetime import timedelta

from kanban.models import Board, Column, Task, TaskLabel, Comment
from accounts.models import Organization
from api.models import APIToken
from api.v1.serializers import (
    BoardSerializer, BoardListSerializer,
    TaskSerializer, TaskListSerializer,
    ColumnSerializer, TaskLabelSerializer,
    CommentSerializer, UserSerializer,
    OrganizationSerializer, APITokenSerializer
)
from api.v1.authentication import APITokenAuthentication, ScopePermission


class StandardResultsSetPagination(PageNumberPagination):
    """Standard pagination class"""
    page_size = 50
    page_size_query_param = 'page_size'
    max_page_size = 100


class BoardViewSet(viewsets.ModelViewSet):
    """
    API endpoint for managing boards.
    
    Scopes required:
    - boards.read: GET requests
    - boards.write: POST, PUT, PATCH, DELETE requests
    """
    serializer_class = BoardSerializer
    pagination_class = StandardResultsSetPagination
    authentication_classes = [APITokenAuthentication]
    permission_classes = [permissions.IsAuthenticated, ScopePermission]
    
    def get_queryset(self):
        """Return boards accessible to the authenticated user"""
        user = self.request.user
        # Return boards where user is member or creator
        return Board.objects.filter(
            Q(members=user) | Q(created_by=user)
        ).distinct().select_related('organization', 'created_by').prefetch_related('columns')
    
    def get_serializer_class(self):
        """Use lightweight serializer for list view"""
        if self.action == 'list':
            return BoardListSerializer
        return BoardSerializer
    
    def get_required_scopes(self):
        """Get required scopes based on action"""
        if self.action in ['list', 'retrieve']:
            return ['boards.read']
        return ['boards.write']
    
    @action(detail=True, methods=['get'])
    def tasks(self, request, pk=None):
        """Get all tasks for a board"""
        board = self.get_object()
        tasks = Task.objects.filter(column__board=board).select_related(
            'column', 'assigned_to', 'created_by'
        ).prefetch_related('labels')
        
        serializer = TaskListSerializer(tasks, many=True)
        return Response(serializer.data)
    
    @action(detail=True, methods=['get'])
    def columns(self, request, pk=None):
        """Get all columns for a board"""
        board = self.get_object()
        columns = board.columns.all()
        serializer = ColumnSerializer(columns, many=True)
        return Response(serializer.data)


class TaskViewSet(viewsets.ModelViewSet):
    """
    API endpoint for managing tasks.
    
    Scopes required:
    - tasks.read: GET requests
    - tasks.write: POST, PUT, PATCH, DELETE requests
    """
    serializer_class = TaskSerializer
    pagination_class = StandardResultsSetPagination
    authentication_classes = [APITokenAuthentication]
    permission_classes = [permissions.IsAuthenticated, ScopePermission]
    
    def get_queryset(self):
        """Return tasks accessible to the authenticated user"""
        user = self.request.user
        # Return tasks from boards where user is member or creator
        queryset = Task.objects.filter(
            Q(column__board__members=user) | Q(column__board__created_by=user)
        ).distinct().select_related(
            'column', 'column__board', 'assigned_to', 'created_by'
        ).prefetch_related('labels')
        
        # Filter by board_id if provided
        board_id = self.request.query_params.get('board_id')
        if board_id:
            queryset = queryset.filter(column__board_id=board_id)
        
        # Filter by assigned_to if provided
        assigned_to = self.request.query_params.get('assigned_to')
        if assigned_to:
            if assigned_to.lower() == 'me':
                queryset = queryset.filter(assigned_to_id=self.request.user.id)
            else:
                queryset = queryset.filter(assigned_to_id=assigned_to)
        
        # Filter by priority if provided
        priority = self.request.query_params.get('priority')
        if priority:
            queryset = queryset.filter(priority=priority)
        
        # Filter by status (column) if provided
        column_id = self.request.query_params.get('column_id')
        if column_id:
            queryset = queryset.filter(column_id=column_id)
        
        return queryset
    
    def get_serializer_class(self):
        """Use lightweight serializer for list view"""
        if self.action == 'list':
            return TaskListSerializer
        return TaskSerializer
    
    def get_required_scopes(self):
        """Get required scopes based on action"""
        if self.action in ['list', 'retrieve']:
            return ['tasks.read']
        return ['tasks.write']
    
    @action(detail=True, methods=['post'])
    def move(self, request, pk=None):
        """Move task to a different column"""
        task = self.get_object()
        column_id = request.data.get('column_id')
        
        if not column_id:
            return Response(
                {'error': 'column_id is required'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        try:
            column = Column.objects.get(id=column_id, board=task.column.board)
            task.column = column
            task.save()
            
            serializer = self.get_serializer(task)
            return Response(serializer.data)
        except Column.DoesNotExist:
            return Response(
                {'error': 'Column not found or not in same board'},
                status=status.HTTP_404_NOT_FOUND
            )
    
    @action(detail=True, methods=['post'])
    def assign(self, request, pk=None):
        """Assign task to a user"""
        task = self.get_object()
        user_id = request.data.get('user_id')
        
        if not user_id:
            return Response(
                {'error': 'user_id is required'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Verify user has access to board
        if not task.column.board.members.filter(id=user_id).exists():
            return Response(
                {'error': 'User is not a member of this board'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        task.assigned_to_id = user_id
        task.save()
        
        serializer = self.get_serializer(task)
        return Response(serializer.data)


class CommentViewSet(viewsets.ModelViewSet):
    """
    API endpoint for task comments.
    
    Scopes required:
    - comments.read: GET requests
    - comments.write: POST, PUT, PATCH, DELETE requests
    """
    serializer_class = CommentSerializer
    authentication_classes = [APITokenAuthentication]
    permission_classes = [permissions.IsAuthenticated, ScopePermission]
    
    def get_queryset(self):
        """Return comments for tasks accessible to the authenticated user"""
        user = self.request.user
        queryset = Comment.objects.filter(
            Q(task__column__board__members=user) | Q(task__column__board__created_by=user)
        ).distinct().select_related('task', 'user')
        
        # Filter by task_id if provided
        task_id = self.request.query_params.get('task_id')
        if task_id:
            queryset = queryset.filter(task_id=task_id)
        
        return queryset
    
    def get_required_scopes(self):
        """Get required scopes based on action"""
        if self.action in ['list', 'retrieve']:
            return ['comments.read']
        return ['comments.write']


@api_view(['POST'])
@authentication_classes([])
@permission_classes([permissions.IsAuthenticated])
def create_api_token(request):
    """
    Create a new API token for the authenticated user.
    
    This endpoint requires session authentication (not API token auth).
    Users can create tokens via the web interface.
    """
    serializer = APITokenSerializer(data=request.data)
    
    if not serializer.is_valid():
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    
    data = serializer.validated_data
    
    # Calculate expiration date if provided
    expires_at = None
    if 'expires_in_days' in data:
        expires_at = timezone.now() + timedelta(days=data['expires_in_days'])
    
    # Create token
    token = APIToken.objects.create(
        user=request.user,
        name=data['name'],
        scopes=data.get('scopes', []),
        expires_at=expires_at
    )
    
    return Response({
        'id': token.id,
        'name': token.name,
        'token': token.token,
        'scopes': token.scopes,
        'created_at': token.created_at,
        'expires_at': token.expires_at,
        'rate_limit_per_hour': token.rate_limit_per_hour
    }, status=status.HTTP_201_CREATED)


@api_view(['GET'])
@authentication_classes([])
@permission_classes([permissions.IsAuthenticated])
def list_api_tokens(request):
    """
    List all API tokens for the authenticated user.
    
    This endpoint requires session authentication (not API token auth).
    """
    tokens = APIToken.objects.filter(user=request.user)
    
    return Response([
        {
            'id': token.id,
            'name': token.name,
            'token': token.token[:8] + '...' + token.token[-4:],  # Masked token
            'scopes': token.scopes,
            'is_active': token.is_active,
            'created_at': token.created_at,
            'last_used': token.last_used,
            'expires_at': token.expires_at,
            'rate_limit_per_hour': token.rate_limit_per_hour,
            'request_count_current_hour': token.request_count_current_hour
        }
        for token in tokens
    ])


@api_view(['DELETE'])
@authentication_classes([])
@permission_classes([permissions.IsAuthenticated])
def delete_api_token(request, token_id):
    """
    Delete an API token.
    
    This endpoint requires session authentication (not API token auth).
    """
    token = get_object_or_404(APIToken, id=token_id, user=request.user)
    token.delete()
    
    return Response(status=status.HTTP_204_NO_CONTENT)


@api_view(['GET'])
@authentication_classes([APITokenAuthentication])
@permission_classes([permissions.IsAuthenticated])
def api_status(request):
    """
    Check API status and token information.
    """
    token_info = None
    if hasattr(request, 'api_token'):
        token = request.api_token
        token_info = {
            'name': token.name,
            'scopes': token.scopes,
            'rate_limit_per_hour': token.rate_limit_per_hour,
            'requests_remaining': token.rate_limit_per_hour - token.request_count_current_hour,
            'rate_limit_reset_at': token.rate_limit_reset_at
        }
    
    return Response({
        'status': 'ok',
        'version': 'v1',
        'authenticated': True,
        'user': request.user.username,
        'token_info': token_info
    })


from django.shortcuts import render
from django.contrib.auth.decorators import login_required


@login_required
def rate_limit_dashboard(request):
    """
    Dashboard view showing rate limiting statistics and monitoring.
    Requires session authentication.
    """
    from api.models import APIRequestLog
    from datetime import datetime, timedelta
    
    # Get all tokens for user
    tokens = APIToken.objects.filter(user=request.user).order_by('-created_at')
    
    # Get recent request stats
    last_hour = timezone.now() - timedelta(hours=1)
    last_24h = timezone.now() - timedelta(hours=24)
    
    recent_requests = APIRequestLog.objects.filter(
        token__user=request.user,
        timestamp__gte=last_24h
    )
    
    # Calculate total monthly usage across all tokens
    total_monthly_usage = sum(token.request_count_current_month for token in tokens)
    total_monthly_quota = sum(token.monthly_quota for token in tokens)
    monthly_usage_percent = round((total_monthly_usage / total_monthly_quota * 100), 1) if total_monthly_quota > 0 else 0
    
    # Get prediction for primary token (if exists)
    primary_token = tokens.first()
    prediction = primary_token.predict_monthly_usage() if primary_token else None
    
    context = {
        'tokens': tokens,
        'total_tokens': tokens.count(),
        'active_tokens': tokens.filter(is_active=True).count(),
        'requests_last_hour': recent_requests.filter(timestamp__gte=last_hour).count(),
        'requests_last_24h': recent_requests.count(),
        'total_monthly_usage': total_monthly_usage,
        'total_monthly_quota': total_monthly_quota,
        'monthly_usage_percent': monthly_usage_percent,
        'monthly_remaining': total_monthly_quota - total_monthly_usage,
        'prediction': prediction,
    }
    
    return render(request, 'api/rate_limit_dashboard.html', context)


@api_view(['GET'])
@permission_classes([permissions.IsAuthenticated])
def rate_limit_stats(request):
    """
    AJAX endpoint for real-time rate limit statistics.
    Uses session authentication for logged-in users.
    """
    from api.models import APIRequestLog
    from datetime import datetime, timedelta
    from django.db.models import Count, Avg
    from django.db.models.functions import TruncHour, TruncMinute
    
    token_id = request.GET.get('token_id')
    
    # Get token stats
    if token_id:
        try:
            token = APIToken.objects.get(id=token_id, user=request.user)
            tokens = [token]
        except APIToken.DoesNotExist:
            return Response({'error': 'Token not found'}, status=status.HTTP_404_NOT_FOUND)
    else:
        tokens = APIToken.objects.filter(user=request.user, is_active=True)
    
    # Calculate stats for each token
    token_stats = []
    for token in tokens:
        usage_percent = (token.request_count_current_hour / token.rate_limit_per_hour) * 100
        time_until_reset = (token.rate_limit_reset_at - timezone.now()).total_seconds()
        
        # Get monthly stats
        monthly_usage_percent = token.get_monthly_usage_percent()
        prediction = token.predict_monthly_usage()
        
        token_stats.append({
            'id': token.id,
            'name': token.name,
            # Hourly stats
            'rate_limit': token.rate_limit_per_hour,
            'current_usage': token.request_count_current_hour,
            'remaining': token.rate_limit_per_hour - token.request_count_current_hour,
            'usage_percent': round(usage_percent, 1),
            'reset_at': token.rate_limit_reset_at.isoformat(),
            'seconds_until_reset': max(0, int(time_until_reset)),
            # Monthly stats
            'monthly_quota': token.monthly_quota,
            'monthly_usage': token.request_count_current_month,
            'monthly_remaining': token.get_monthly_remaining(),
            'monthly_usage_percent': monthly_usage_percent,
            'monthly_reset_at': token.monthly_reset_at.isoformat(),
            'days_until_monthly_reset': token.get_days_until_reset(),
            'prediction': prediction,
            # General
            'last_used': token.last_used.isoformat() if token.last_used else None,
        })
    
    # Get historical data for charts (last 24 hours)
    last_24h = timezone.now() - timedelta(hours=24)
    
    # Requests per hour for the last 24 hours
    hourly_requests = APIRequestLog.objects.filter(
        token__user=request.user,
        timestamp__gte=last_24h
    ).annotate(
        hour=TruncHour('timestamp')
    ).values('hour').annotate(
        count=Count('id')
    ).order_by('hour')
    
    # Requests per minute for the last hour
    last_hour = timezone.now() - timedelta(hours=1)
    minute_requests = APIRequestLog.objects.filter(
        token__user=request.user,
        timestamp__gte=last_hour
    ).annotate(
        minute=TruncMinute('timestamp')
    ).values('minute').annotate(
        count=Count('id')
    ).order_by('minute')
    
    # Status code distribution
    status_distribution = APIRequestLog.objects.filter(
        token__user=request.user,
        timestamp__gte=last_24h
    ).values('status_code').annotate(
        count=Count('id')
    ).order_by('status_code')
    
    # Top endpoints
    top_endpoints = APIRequestLog.objects.filter(
        token__user=request.user,
        timestamp__gte=last_24h
    ).values('endpoint', 'method').annotate(
        count=Count('id'),
        avg_response_time=Avg('response_time_ms')
    ).order_by('-count')[:10]
    
    return Response({
        'tokens': token_stats,
        'charts': {
            'hourly_requests': [
                {
                    'hour': item['hour'].isoformat(),
                    'count': item['count']
                }
                for item in hourly_requests
            ],
            'minute_requests': [
                {
                    'minute': item['minute'].isoformat(),
                    'count': item['count']
                }
                for item in minute_requests
            ],
            'status_distribution': [
                {
                    'status': item['status_code'],
                    'count': item['count']
                }
                for item in status_distribution
            ],
            'top_endpoints': [
                {
                    'endpoint': f"{item['method']} {item['endpoint']}",
                    'count': item['count'],
                    'avg_response_time': round(item['avg_response_time'], 2)
                }
                for item in top_endpoints
            ]
        },
        'timestamp': timezone.now().isoformat()
    })
