"""
Management command to clean up stale AI suggestions
Run this to expire outdated resource leveling suggestions
"""
from django.core.management.base import BaseCommand
from django.utils import timezone
from kanban.resource_leveling_models import ResourceLevelingSuggestion, UserPerformanceProfile
from accounts.models import Organization


class Command(BaseCommand):
    help = 'Clean up stale and invalid AI resource leveling suggestions'

    def add_arguments(self, parser):
        parser.add_argument(
            '--organization',
            type=int,
            help='Only process suggestions for a specific organization ID',
        )
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Show what would be expired without actually doing it',
        )

    def handle(self, *args, **options):
        dry_run = options.get('dry_run', False)
        
        if dry_run:
            self.stdout.write(self.style.WARNING('DRY RUN MODE - No changes will be made'))
        
        self.stdout.write(self.style.SUCCESS('Cleaning up stale AI suggestions...'))
        
        # Determine which organizations to process
        if options['organization']:
            organizations = Organization.objects.filter(id=options['organization'])
            if not organizations.exists():
                self.stdout.write(self.style.ERROR(f'Organization ID {options["organization"]} not found'))
                return
        else:
            organizations = Organization.objects.all()
        
        total_expired = 0
        total_invalid = 0
        
        for org in organizations:
            self.stdout.write(f'\nProcessing organization: {org.name}')
            
            # Get all pending suggestions for this org
            pending = ResourceLevelingSuggestion.objects.filter(
                organization=org,
                status='pending'
            ).select_related('task', 'suggested_assignee', 'current_assignee')
            
            self.stdout.write(f'  Found {pending.count()} pending suggestions')
            
            expired_count = 0
            invalid_count = 0
            
            for suggestion in pending:
                # Check 1: Is it expired by time?
                if suggestion.is_expired():
                    if not dry_run:
                        suggestion.status = 'expired'
                        suggestion.save()
                    expired_count += 1
                    self.stdout.write(
                        f'    ⏰ Expired: Task "{suggestion.task.title}" -> {suggestion.suggested_assignee.username} (time expired)'
                    )
                    continue
                
                # Check 2: Does the task still exist and is incomplete?
                if suggestion.task.completed_at:
                    if not dry_run:
                        suggestion.status = 'expired'
                        suggestion.save()
                    invalid_count += 1
                    self.stdout.write(
                        f'    ✅ Invalid: Task "{suggestion.task.title}" is already completed'
                    )
                    continue
                
                # Check 3: Has the task already been assigned to the suggested person?
                if suggestion.task.assigned_to == suggestion.suggested_assignee:
                    if not dry_run:
                        suggestion.status = 'accepted'  # Mark as accepted since it happened
                        suggestion.save()
                    invalid_count += 1
                    self.stdout.write(
                        f'    ✓ Already Applied: Task "{suggestion.task.title}" -> {suggestion.suggested_assignee.username}'
                    )
                    continue
                
                # Check 4: Is the suggested assignee now overloaded?
                profile = UserPerformanceProfile.objects.filter(
                    user=suggestion.suggested_assignee,
                    organization=org
                ).first()
                
                if profile:
                    profile.update_current_workload()
                    
                    if profile.utilization_percentage > 85:
                        if not dry_run:
                            suggestion.status = 'expired'
                            suggestion.save()
                        invalid_count += 1
                        self.stdout.write(
                            f'    ⚠️  Invalid: {suggestion.suggested_assignee.username} now overloaded '
                            f'({profile.utilization_percentage:.1f}% utilization)'
                        )
                        continue
                
                # Check 5: Has the current assignee changed?
                if suggestion.current_assignee != suggestion.task.assigned_to:
                    if not dry_run:
                        suggestion.status = 'expired'
                        suggestion.save()
                    invalid_count += 1
                    self.stdout.write(
                        f'    🔄 Invalid: Task "{suggestion.task.title}" reassigned to someone else'
                    )
                    continue
            
            total_expired += expired_count
            total_invalid += invalid_count
            
            self.stdout.write(
                f'  Summary: {expired_count} time-expired, {invalid_count} invalid'
            )
        
        total_cleaned = total_expired + total_invalid
        
        if dry_run:
            self.stdout.write(
                self.style.WARNING(f'\nDRY RUN: Would have cleaned up {total_cleaned} suggestions')
            )
            self.stdout.write(
                self.style.WARNING('Run without --dry-run to actually expire them')
            )
        else:
            self.stdout.write(
                self.style.SUCCESS(f'\n✓ Successfully cleaned up {total_cleaned} stale suggestions')
            )
            self.stdout.write(
                self.style.SUCCESS('All suggestions are now up to date!')
            )
