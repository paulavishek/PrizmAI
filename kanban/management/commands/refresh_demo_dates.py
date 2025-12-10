"""
Management command to refresh all demo data dates to be relative to the current date.
This ensures demo data always appears fresh and relevant regardless of when it was created.
"""

from datetime import timedelta
from django.core.management.base import BaseCommand
from django.utils import timezone
from django.db.models import Q
from kanban.models import Task, Milestone
from kanban.budget_models import TimeEntry, ProjectBudget
from kanban.stakeholder_models import StakeholderEngagementRecord


class Command(BaseCommand):
    help = 'Refresh all demo data dates to be relative to the current date'

    def handle(self, *args, **options):
        self.stdout.write(self.style.NOTICE('=' * 70))
        self.stdout.write(self.style.NOTICE('Refreshing Demo Data Dates'))
        self.stdout.write(self.style.NOTICE('=' * 70))
        self.stdout.write('')

        # Get current date
        now = timezone.now()
        base_date = now.date()

        # Track statistics
        stats = {
            'tasks_updated': 0,
            'milestones_updated': 0,
            'time_entries_updated': 0,
            'budgets_updated': 0,
            'engagement_records_updated': 0
        }

        # Refresh task dates
        self.stdout.write(self.style.NOTICE('Refreshing task dates...'))
        tasks = list(Task.objects.all().select_related('column'))
        
        tasks_to_update = []
        for task in tasks:
            if not task.due_date:
                continue
                
            # Calculate how old the due date is relative to when it was created
            # We'll maintain the relative offset from the original due date
            old_due_date = task.due_date
            
            # Determine the offset based on column status
            column_name = task.column.name.lower() if task.column else ''
            
            # For completed/done tasks - put them in the past
            if column_name in ['done', 'closed', 'completed']:
                if task.progress == 100:
                    # Spread completed tasks across the past 60 days
                    days_offset = -(task.id % 60 + 3)  # -3 to -63 days
                else:
                    # Almost done tasks
                    days_offset = -(task.id % 10 + 1)  # -1 to -11 days
            
            # For review/testing tasks - recent past or very near future
            elif column_name in ['review', 'testing', 'reviewing']:
                # Spread across -5 to +5 days
                days_offset = (task.id % 11) - 5
            
            # For in-progress tasks - mostly current or near future
            elif column_name in ['in progress', 'in-progress', 'working', 'investigating']:
                # Spread from -10 to +15 days (mostly future)
                offset_range = (task.id % 26) - 10
                days_offset = offset_range
            
            # For to-do/planning tasks - near to mid future
            elif column_name in ['to do', 'to-do', 'todo', 'planning', 'ready']:
                # Spread from +2 to +20 days
                days_offset = (task.id % 19) + 2
            
            # For backlog/ideas - further future
            elif column_name in ['backlog', 'ideas', 'future', 'new']:
                # Spread from +15 to +60 days
                days_offset = (task.id % 46) + 15
            
            else:
                # Default: spread across -30 to +30 days
                days_offset = (task.id % 61) - 30
            
            # Set the new due date
            new_due_date = now + timedelta(days=days_offset)
            task.due_date = new_due_date
            
            # Set start_date if it exists (typically 3-7 days before due date)
            if task.start_date:
                # Maintain the duration between start and due date
                if old_due_date:
                    try:
                        original_duration = (old_due_date.date() - task.start_date).days
                        original_duration = max(1, min(original_duration, 30))  # Keep reasonable duration
                    except:
                        original_duration = 7
                else:
                    original_duration = 7
                
                task.start_date = base_date + timedelta(days=days_offset - original_duration)
            
            tasks_to_update.append(task)
            stats['tasks_updated'] += 1
            
            if stats['tasks_updated'] % 100 == 0:
                self.stdout.write(f'  Processed {stats["tasks_updated"]} tasks...')

        # Bulk update to avoid triggering signals for each task
        if tasks_to_update:
            Task.objects.bulk_update(tasks_to_update, ['due_date', 'start_date'], batch_size=500)
        
        self.stdout.write(self.style.SUCCESS(f'  ✅ Updated {stats["tasks_updated"]} tasks'))

        # Refresh milestone dates
        self.stdout.write(self.style.NOTICE('\nRefreshing milestone dates...'))
        milestones = list(Milestone.objects.all())
        milestones_to_update = []
        
        for milestone in milestones:
            if not milestone.target_date:
                continue
            
            # Determine offset based on milestone type and completion status
            if milestone.is_completed:
                # Completed milestones - put in past
                if milestone.milestone_type == 'project_start':
                    days_offset = -60
                elif milestone.milestone_type == 'phase_completion':
                    days_offset = -(milestone.id % 40 + 10)  # -10 to -50 days
                elif milestone.milestone_type == 'deliverable':
                    days_offset = -(milestone.id % 30 + 5)   # -5 to -35 days
                else:
                    days_offset = -(milestone.id % 20 + 10)  # -10 to -30 days
                
                # Set completed date slightly before target date
                if milestone.completed_date:
                    milestone.completed_date = base_date + timedelta(days=days_offset + 2)
            else:
                # Upcoming milestones - put in future
                if milestone.milestone_type == 'project_end':
                    days_offset = 60
                elif milestone.milestone_type == 'phase_completion':
                    days_offset = (milestone.id % 30) + 10   # +10 to +40 days
                elif milestone.milestone_type == 'deliverable':
                    days_offset = (milestone.id % 25) + 5    # +5 to +30 days
                elif milestone.milestone_type == 'review':
                    days_offset = (milestone.id % 20) + 3    # +3 to +23 days
                else:
                    days_offset = (milestone.id % 15) + 5    # +5 to +20 days
            
            milestone.target_date = base_date + timedelta(days=days_offset)
            milestones_to_update.append(milestone)
            stats['milestones_updated'] += 1

        # Bulk update milestones
        if milestones_to_update:
            Milestone.objects.bulk_update(milestones_to_update, ['target_date', 'completed_date'], batch_size=100)
        
        self.stdout.write(self.style.SUCCESS(f'  ✅ Updated {stats["milestones_updated"]} milestones'))

        # Refresh time entry dates
        self.stdout.write(self.style.NOTICE('\nRefreshing time entry dates...'))
        time_entries = list(TimeEntry.objects.all())
        entries_to_update = []
        
        for entry in time_entries:
            if not entry.work_date:
                continue
            
            # Time entries should be in the past (last 30 days)
            days_offset = -(entry.id % 30 + 1)  # -1 to -31 days
            entry.work_date = base_date + timedelta(days=days_offset)
            entries_to_update.append(entry)
            stats['time_entries_updated'] += 1

        # Bulk update time entries
        if entries_to_update:
            TimeEntry.objects.bulk_update(entries_to_update, ['work_date'], batch_size=500)
        
        self.stdout.write(self.style.SUCCESS(f'  ✅ Updated {stats["time_entries_updated"]} time entries'))

        # Refresh project budget dates (if applicable)
        # Note: ProjectBudget model doesn't have start_date/end_date fields
        # Skipping budget date updates
        self.stdout.write(self.style.SUCCESS(f'  ✅ Skipped {ProjectBudget.objects.count()} project budgets (no date fields)'))

        # Refresh stakeholder engagement record dates
        self.stdout.write(self.style.NOTICE('\nRefreshing stakeholder engagement dates...'))
        engagement_records = list(StakeholderEngagementRecord.objects.all())
        records_to_update = []
        
        for record in engagement_records:
            if not record.date:
                continue
            
            # Engagement records in the past 60 days
            days_offset = -(record.id % 60 + 1)  # -1 to -61 days
            record.date = base_date + timedelta(days=days_offset)
            records_to_update.append(record)
            stats['engagement_records_updated'] += 1

        # Bulk update engagement records
        if records_to_update:
            StakeholderEngagementRecord.objects.bulk_update(records_to_update, ['date'], batch_size=500)
        
        self.stdout.write(self.style.SUCCESS(f'  ✅ Updated {stats["engagement_records_updated"]} engagement records'))

        # Now optionally run the fix_gantt_demo_data command to ensure proper dependencies
        # Note: Skipping this to avoid signal conflicts during bulk updates
        self.stdout.write(self.style.NOTICE('\n💡 Note: Task dates have been refreshed.'))
        self.stdout.write(self.style.NOTICE('   Run "python manage.py fix_gantt_demo_data" separately if needed.'))

        # Print summary
        self.stdout.write('')
        self.stdout.write(self.style.SUCCESS('=' * 70))
        self.stdout.write(self.style.SUCCESS('✅ Demo Data Dates Refreshed Successfully!'))
        self.stdout.write(self.style.SUCCESS('=' * 70))
        self.stdout.write(self.style.SUCCESS(f'\n📊 Summary:'))
        self.stdout.write(self.style.SUCCESS(f'   • Tasks updated: {stats["tasks_updated"]}'))
        self.stdout.write(self.style.SUCCESS(f'   • Milestones updated: {stats["milestones_updated"]}'))
        self.stdout.write(self.style.SUCCESS(f'   • Time entries updated: {stats["time_entries_updated"]}'))
        self.stdout.write(self.style.SUCCESS(f'   • Budgets updated: {stats["budgets_updated"]}'))
        self.stdout.write(self.style.SUCCESS(f'   • Engagement records updated: {stats["engagement_records_updated"]}'))
        
        # Show date distribution
        self.stdout.write(self.style.SUCCESS(f'\n📅 Task Date Distribution:'))
        overdue = Task.objects.filter(due_date__lt=now, progress__lt=100).count()
        past = Task.objects.filter(due_date__lt=now).count()
        future = Task.objects.filter(due_date__gte=now).count()
        next_week = Task.objects.filter(due_date__gte=now, due_date__lt=now + timedelta(days=7)).count()
        next_month = Task.objects.filter(due_date__gte=now, due_date__lt=now + timedelta(days=30)).count()
        
        self.stdout.write(self.style.SUCCESS(f'   • Past due dates: {past} ({overdue} overdue and incomplete)'))
        self.stdout.write(self.style.SUCCESS(f'   • Future due dates: {future}'))
        self.stdout.write(self.style.SUCCESS(f'   • Due in next 7 days: {next_week}'))
        self.stdout.write(self.style.SUCCESS(f'   • Due in next 30 days: {next_month}'))
        self.stdout.write(self.style.SUCCESS('=' * 70))
        self.stdout.write(self.style.SUCCESS('\n💡 Tip: Run this command periodically to keep demo data fresh!'))
        self.stdout.write(self.style.SUCCESS('=' * 70 + '\n'))
