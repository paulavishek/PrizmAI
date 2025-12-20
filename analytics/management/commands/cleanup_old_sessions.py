"""
Management command to clean up old analytics sessions.
Run periodically via cron or Celery beat to maintain database performance.

Usage:
    python manage.py cleanup_old_sessions
    python manage.py cleanup_old_sessions --days 60
"""
from django.core.management.base import BaseCommand
from django.utils import timezone
from datetime import timedelta
from analytics.models import UserSession, AnalyticsEvent
import logging

logger = logging.getLogger('analytics')


class Command(BaseCommand):
    help = 'Delete analytics sessions and events older than specified days (default: 90 days)'

    def add_arguments(self, parser):
        parser.add_argument(
            '--days',
            type=int,
            default=90,
            help='Number of days to retain data (default: 90)'
        )
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Preview what would be deleted without actually deleting'
        )

    def handle(self, *args, **options):
        days = options['days']
        dry_run = options['dry_run']
        
        # Calculate cutoff date
        cutoff = timezone.now() - timedelta(days=days)
        
        self.stdout.write(
            self.style.WARNING(
                f'\n{"DRY RUN - " if dry_run else ""}Cleaning up analytics data older than {days} days...'
            )
        )
        self.stdout.write(f'Cutoff date: {cutoff.strftime("%Y-%m-%d %H:%M:%S")}\n')
        
        # Find old sessions
        old_sessions = UserSession.objects.filter(
            session_end__lt=cutoff
        )
        sessions_count = old_sessions.count()
        
        # Find old events
        old_events = AnalyticsEvent.objects.filter(
            timestamp__lt=cutoff
        )
        events_count = old_events.count()
        
        # Display what will be deleted
        self.stdout.write(f'Sessions to delete: {sessions_count}')
        self.stdout.write(f'Analytics events to delete: {events_count}')
        
        if sessions_count == 0 and events_count == 0:
            self.stdout.write(
                self.style.SUCCESS('\n✅ No old data found. Database is clean!')
            )
            return
        
        if dry_run:
            self.stdout.write(
                self.style.WARNING(
                    '\n⚠️  DRY RUN - No data was deleted. Remove --dry-run flag to perform deletion.'
                )
            )
            return
        
        # Confirm deletion for large datasets
        if sessions_count + events_count > 10000:
            confirm = input(
                f'\nThis will delete {sessions_count + events_count} records. '
                'Are you sure? (yes/no): '
            )
            if confirm.lower() != 'yes':
                self.stdout.write(self.style.WARNING('Deletion cancelled.'))
                return
        
        # Perform deletion
        try:
            # Delete events first (foreign key constraint)
            if events_count > 0:
                deleted_events = old_events.delete()
                self.stdout.write(
                    self.style.SUCCESS(
                        f'✅ Deleted {deleted_events[0]} analytics events'
                    )
                )
                logger.info(f'Deleted {deleted_events[0]} old analytics events')
            
            # Delete sessions
            if sessions_count > 0:
                deleted_sessions = old_sessions.delete()
                self.stdout.write(
                    self.style.SUCCESS(
                        f'✅ Deleted {deleted_sessions[0]} user sessions'
                    )
                )
                logger.info(f'Deleted {deleted_sessions[0]} old user sessions')
            
            self.stdout.write(
                self.style.SUCCESS(
                    f'\n✅ Cleanup completed successfully! '
                    f'Total records removed: {deleted_events[0] + deleted_sessions[0]}'
                )
            )
        
        except Exception as e:
            self.stdout.write(
                self.style.ERROR(f'\n❌ Error during cleanup: {str(e)}')
            )
            logger.error(f'Error during cleanup: {e}', exc_info=True)
            raise
