"""
Management command to cleanup expired demo sessions
Should be run periodically via cron/celery beat
"""
from django.core.management.base import BaseCommand
from django.utils import timezone
from analytics.models import DemoSession, DemoAnalytics


class Command(BaseCommand):
    help = 'Cleanup expired demo sessions and associated data'

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Show what would be deleted without actually deleting',
        )
        parser.add_argument(
            '--keep-analytics',
            action='store_true',
            help='Keep analytics data even after deleting sessions',
        )

    def handle(self, *args, **options):
        dry_run = options['dry_run']
        keep_analytics = options['keep_analytics']
        
        if dry_run:
            self.stdout.write(self.style.WARNING('DRY RUN MODE - No data will be deleted'))
        
        # Find expired demo sessions
        now = timezone.now()
        expired_sessions = DemoSession.objects.filter(expires_at__lt=now)
        
        expired_count = expired_sessions.count()
        self.stdout.write(f'Found {expired_count} expired demo sessions')
        
        if expired_count == 0:
            self.stdout.write(self.style.SUCCESS('No expired sessions to cleanup'))
            return
        
        # Get session IDs before deletion
        expired_session_ids = list(expired_sessions.values_list('session_id', flat=True))
        
        # Delete expired sessions
        if not dry_run:
            deleted_sessions, _ = expired_sessions.delete()
            self.stdout.write(self.style.SUCCESS(f'Deleted {deleted_sessions} expired demo sessions'))
        else:
            self.stdout.write(f'Would delete {expired_count} demo sessions')
        
        # Optionally cleanup analytics data
        if not keep_analytics:
            analytics_to_delete = DemoAnalytics.objects.filter(
                session_id__in=expired_session_ids
            )
            analytics_count = analytics_to_delete.count()
            
            if analytics_count > 0:
                if not dry_run:
                    deleted_analytics, _ = analytics_to_delete.delete()
                    self.stdout.write(self.style.SUCCESS(f'Deleted {deleted_analytics} analytics records'))
                else:
                    self.stdout.write(f'Would delete {analytics_count} analytics records')
        
        # Cleanup session-created content (tasks, boards, etc.)
        if not dry_run:
            self.cleanup_session_content(expired_session_ids)
        else:
            self.stdout.write(f'Would cleanup content from {len(expired_session_ids)} sessions')
        
        self.stdout.write(self.style.SUCCESS('Cleanup complete!'))
    
    def cleanup_session_content(self, session_ids):
        """Delete content created during demo sessions"""
        from kanban.models import Task, Board, Comment
        
        # Delete tasks created by these sessions
        deleted_tasks = Task.objects.filter(created_by_session__in=session_ids).delete()[0]
        if deleted_tasks > 0:
            self.stdout.write(f'Deleted {deleted_tasks} session-created tasks')
        
        # Delete boards created by these sessions
        deleted_boards = Board.objects.filter(created_by_session__in=session_ids).delete()[0]
        if deleted_boards > 0:
            self.stdout.write(f'Deleted {deleted_boards} session-created boards')
        
        # Delete comments created by these sessions
        deleted_comments = Comment.objects.filter(created_by_session__in=session_ids).delete()[0]
        if deleted_comments > 0:
            self.stdout.write(f'Deleted {deleted_comments} session-created comments')
