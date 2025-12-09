"""
Context processors for conflict detection
"""
from kanban.conflict_models import ConflictDetection


def conflict_count(request):
    """
    Add active conflict count to template context for all pages.
    """
    if not request.user.is_authenticated:
        return {'active_conflict_count': 0}
    
    try:
        from kanban.models import Board
        from django.db.models import Q
        
        # Get user's accessible boards
        profile = request.user.profile
        organization = profile.organization
        
        boards = Board.objects.filter(
            Q(organization=organization) &
            (Q(created_by=request.user) | Q(members=request.user))
        ).distinct()
        
        # Count active conflicts
        count = ConflictDetection.objects.filter(
            board__in=boards,
            status='active'
        ).count()
        
        return {'active_conflict_count': count}
    except:
        return {'active_conflict_count': 0}
