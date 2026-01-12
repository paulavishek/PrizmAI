"""
Management command to reset demo abuse prevention limits for development.
"""
from django.core.management.base import BaseCommand
from django.utils import timezone
from analytics.models import DemoAbusePrevention


class Command(BaseCommand):
    help = 'Reset demo abuse prevention limits (for development)'

    def add_arguments(self, parser):
        parser.add_argument(
            '--all',
            action='store_true',
            help='Reset all records',
        )
        parser.add_argument(
            '--ip',
            type=str,
            help='Reset specific IP address',
        )

    def handle(self, *args, **options):
        if options['all']:
            # Reset all records
            count = DemoAbusePrevention.objects.all().count()
            DemoAbusePrevention.objects.all().delete()
            self.stdout.write(
                self.style.SUCCESS(
                    f'Successfully deleted {count} demo abuse prevention records'
                )
            )
        elif options['ip']:
            # Reset specific IP
            ip = options['ip']
            count = DemoAbusePrevention.objects.filter(ip_address=ip).count()
            DemoAbusePrevention.objects.filter(ip_address=ip).delete()
            self.stdout.write(
                self.style.SUCCESS(
                    f'Successfully deleted {count} records for IP {ip}'
                )
            )
        else:
            # Show current stats
            records = DemoAbusePrevention.objects.all()
            self.stdout.write('\nCurrent Demo Abuse Prevention Records:\n')
            self.stdout.write('=' * 80)
            
            for record in records[:10]:  # Show first 10
                self.stdout.write(
                    f'\nIP: {record.ip_address}'
                )
                self.stdout.write(
                    f'  Sessions: {record.total_sessions_created}'
                )
                self.stdout.write(
                    f'  AI Generations: {record.total_ai_generations}'
                )
                self.stdout.write(
                    f'  Projects: {record.total_projects_created}'
                )
                self.stdout.write(
                    f'  First Seen: {record.first_seen}'
                )
                self.stdout.write(
                    f'  Last Seen: {record.last_seen}'
                )
                if record.is_flagged:
                    self.stdout.write(
                        self.style.WARNING(f'  FLAGGED: {record.flag_reason}')
                    )
                if record.is_blocked:
                    self.stdout.write(
                        self.style.ERROR('  BLOCKED')
                    )
            
            total = records.count()
            if total > 10:
                self.stdout.write(f'\n... and {total - 10} more records')
            
            self.stdout.write('\n' + '=' * 80)
            self.stdout.write(
                self.style.WARNING(
                    '\nTo reset all records, run: python manage.py reset_demo_limits --all'
                )
            )
            self.stdout.write(
                self.style.WARNING(
                    'To reset specific IP, run: python manage.py reset_demo_limits --ip <IP_ADDRESS>\n'
                )
            )
