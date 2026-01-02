"""
Management command to refresh all demo data dates to be relative to the current date.
This ensures demo data always appears fresh and relevant regardless of when it was created.

This command can be run manually or scheduled via cron/celery for automatic updates.
The middleware also handles automatic daily refreshes when demo users access the system.
"""

from django.core.management.base import BaseCommand
from django.utils import timezone


class Command(BaseCommand):
    help = 'Refresh all demo data dates to be relative to the current date'

    def add_arguments(self, parser):
        parser.add_argument(
            '--force',
            action='store_true',
            help='Force refresh even if already refreshed today',
        )

    def handle(self, *args, **options):
        self.stdout.write(self.style.NOTICE('=' * 70))
        self.stdout.write(self.style.NOTICE('Refreshing Demo Data Dates'))
        self.stdout.write(self.style.NOTICE('=' * 70))
        self.stdout.write('')

        # Import the refresh service
        from kanban.utils.demo_date_refresh import (
            should_refresh_demo_dates,
            refresh_all_demo_dates,
            mark_demo_dates_refreshed
        )

        # Check if refresh is needed
        if not options['force'] and not should_refresh_demo_dates():
            self.stdout.write(self.style.SUCCESS(
                '✅ Demo dates were already refreshed today. Use --force to refresh anyway.'
            ))
            return

        # Perform the refresh
        try:
            stats = refresh_all_demo_dates()
            
            # Print summary
            self.stdout.write('')
            self.stdout.write(self.style.SUCCESS('=' * 70))
            self.stdout.write(self.style.SUCCESS('✅ Demo Data Dates Refreshed Successfully!'))
            self.stdout.write(self.style.SUCCESS('=' * 70))
            self.stdout.write(self.style.SUCCESS(f'\n📊 Summary:'))
            
            for key, value in stats.items():
                formatted_key = key.replace('_', ' ').title()
                self.stdout.write(self.style.SUCCESS(f'   • {formatted_key}: {value}'))
            
            # Show current date distribution
            self._show_date_distribution()
            
            self.stdout.write(self.style.SUCCESS('=' * 70))
            self.stdout.write(self.style.SUCCESS('\n💡 Tip: Demo dates refresh automatically when users access demo mode!'))
            self.stdout.write(self.style.SUCCESS('=' * 70 + '\n'))
            
        except Exception as e:
            self.stdout.write(self.style.ERROR(f'❌ Error refreshing demo dates: {e}'))
            raise
    
    def _show_date_distribution(self):
        """Show the current date distribution of tasks."""
        try:
            from kanban.models import Task
            from datetime import timedelta
            
            now = timezone.now()
            
            overdue = Task.objects.filter(due_date__lt=now, progress__lt=100).count()
            past = Task.objects.filter(due_date__lt=now).count()
            future = Task.objects.filter(due_date__gte=now).count()
            next_week = Task.objects.filter(
                due_date__gte=now, 
                due_date__lt=now + timedelta(days=7)
            ).count()
            next_month = Task.objects.filter(
                due_date__gte=now, 
                due_date__lt=now + timedelta(days=30)
            ).count()
            
            self.stdout.write(self.style.SUCCESS(f'\n📅 Task Date Distribution:'))
            self.stdout.write(self.style.SUCCESS(f'   • Past due dates: {past} ({overdue} overdue and incomplete)'))
            self.stdout.write(self.style.SUCCESS(f'   • Future due dates: {future}'))
            self.stdout.write(self.style.SUCCESS(f'   • Due in next 7 days: {next_week}'))
            self.stdout.write(self.style.SUCCESS(f'   • Due in next 30 days: {next_month}'))
        except Exception:
            pass
