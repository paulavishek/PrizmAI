"""
Dynamic Demo Date Refresh Service
Automatically refreshes all demo data dates to be relative to the current date.
This ensures demo data always appears fresh regardless of when users access it.

IMPORTANT ARCHITECTURAL NOTES:
------------------------------
1. This service ONLY refreshes SEED/ORIGINAL demo data, NOT user-created content.
   - Seed demo data: created_by_session is NULL or empty
   - User-created data: created_by_session is set to their session ID

2. The 48-hour demo reset system (cleanup_demo_sessions) handles user-created content.
   - After 48 hours, user-created tasks, boards, etc. are deleted
   - This service does NOT touch that user-created content
   
3. The refresh runs once per day (cached) to avoid performance impact.
   - First demo access of the day triggers the refresh
   - All subsequent accesses that day skip the refresh
"""

from datetime import timedelta, date
from django.utils import timezone
from django.db import transaction
from django.core.cache import cache
from django.conf import settings
import logging

logger = logging.getLogger(__name__)

# Cache key for last refresh timestamp
DEMO_DATE_REFRESH_CACHE_KEY = 'demo_data_last_refresh_date'


def should_refresh_demo_dates():
    """
    Check if demo dates need to be refreshed.
    Dates are refreshed once per day to keep demo data current.
    Returns True if refresh is needed.
    """
    last_refresh = cache.get(DEMO_DATE_REFRESH_CACHE_KEY)
    today = timezone.now().date()
    
    if last_refresh is None:
        return True
    
    # If last refresh was on a previous day, refresh is needed
    if isinstance(last_refresh, str):
        try:
            last_refresh = date.fromisoformat(last_refresh)
        except (ValueError, TypeError):
            return True
    
    return last_refresh < today


def mark_demo_dates_refreshed():
    """Mark that demo dates have been refreshed today."""
    today = timezone.now().date().isoformat()
    # Cache for 25 hours to ensure we refresh at least once per day
    cache.set(DEMO_DATE_REFRESH_CACHE_KEY, today, 60 * 60 * 25)


def refresh_all_demo_dates():
    """
    Refresh all SEED demo data dates to be relative to the current date.
    
    IMPORTANT: This only refreshes original demo data, not user-created content.
    User-created content (tasks, boards with created_by_session set) is preserved
    and will be cleaned up by the 48-hour reset system instead.
    
    This is the main entry point called by middleware or management command.
    Returns a dict of statistics about what was updated.
    """
    stats = {
        'tasks_updated': 0,
        'milestones_updated': 0,
        'time_entries_updated': 0,
        'engagement_records_updated': 0,
        'retrospectives_updated': 0,
        'velocity_snapshots_updated': 0,
        'coaching_suggestions_updated': 0,
        'pm_metrics_updated': 0,
        'conflicts_updated': 0,
        'wiki_pages_updated': 0,
        'ai_sessions_updated': 0,
        'improvement_metrics_updated': 0,
        'action_items_updated': 0,
        'burndown_predictions_updated': 0,
        'resource_leveling_updated': 0,
        'roi_snapshots_updated': 0,
        'trend_analysis_updated': 0,
        'sprint_milestones_updated': 0,
    }
    
    now = timezone.now()
    base_date = now.date()
    
    try:
        with transaction.atomic():
            # 1. Refresh Task dates
            stats['tasks_updated'] = _refresh_task_dates(now, base_date)
            
            # 2. Refresh Milestone dates
            stats['milestones_updated'] = _refresh_milestone_dates(now, base_date)
            
            # 3. Refresh Time Entry dates
            stats['time_entries_updated'] = _refresh_time_entry_dates(base_date)
            
            # 4. Refresh Stakeholder Engagement dates
            stats['engagement_records_updated'] = _refresh_engagement_dates(base_date)
            
            # 5. Refresh Retrospective dates
            stats['retrospectives_updated'] = _refresh_retrospective_dates(base_date)
            
            # 6. Refresh Velocity Snapshot dates
            stats['velocity_snapshots_updated'] = _refresh_velocity_snapshot_dates(base_date)
            
            # 7. Refresh Coaching Suggestion dates
            stats['coaching_suggestions_updated'] = _refresh_coaching_suggestion_dates(now)
            
            # 8. Refresh PM Metrics dates
            stats['pm_metrics_updated'] = _refresh_pm_metrics_dates(base_date)
            
            # 9. Refresh Conflict Detection dates
            stats['conflicts_updated'] = _refresh_conflict_dates(now)
            
            # 10. Refresh Wiki Page dates
            stats['wiki_pages_updated'] = _refresh_wiki_dates(now)
            
            # 11. Refresh AI Assistant Session dates
            stats['ai_sessions_updated'] = _refresh_ai_session_dates(now)
            
            # 12. Refresh Improvement Metrics dates
            stats['improvement_metrics_updated'] = _refresh_improvement_metrics_dates(base_date)
            
            # 13. Refresh Retrospective Action Items
            stats['action_items_updated'] = _refresh_action_item_dates(now, base_date)
            
            # 14. Refresh Burndown Predictions
            stats['burndown_predictions_updated'] = _refresh_burndown_prediction_dates(now, base_date)
            
            # 15. Refresh Resource Leveling Analysis
            stats['resource_leveling_updated'] = _refresh_resource_leveling_dates(now, base_date)
            
            # 16. Refresh ROI Snapshots
            stats['roi_snapshots_updated'] = _refresh_roi_snapshot_dates(base_date)
            
            # 17. Refresh Trend Analysis
            stats['trend_analysis_updated'] = _refresh_trend_analysis_dates(base_date)
            
            # 18. Refresh Sprint Milestones (burndown_models)
            stats['sprint_milestones_updated'] = _refresh_sprint_milestone_dates(base_date)
        
        # Mark refresh as complete
        mark_demo_dates_refreshed()
        
        logger.info(f"Demo dates refreshed: {stats}")
        return stats
        
    except Exception as e:
        logger.error(f"Error refreshing demo dates: {e}")
        raise


def _get_demo_organizations():
    """Get demo organization IDs for filtering."""
    try:
        from accounts.models import Organization
        demo_orgs = Organization.objects.filter(is_demo=True)
        return list(demo_orgs.values_list('id', flat=True))
    except Exception:
        return []


def _is_seed_demo_data(obj):
    """
    Check if an object is original seed demo data (not user-created).
    User-created content has created_by_session set to their session ID.
    Seed demo data has created_by_session as NULL or empty.
    """
    if hasattr(obj, 'created_by_session'):
        session = getattr(obj, 'created_by_session', None)
        return session is None or session == ''
    # If the model doesn't have created_by_session field, assume it's seed data
    return True


def _refresh_task_dates(now, base_date):
    """
    Refresh task due_date and start_date fields.
    ONLY refreshes original seed demo data, not user-created content.
    """
    try:
        from kanban.models import Task
        from django.db.models import Q
        
        demo_org_ids = _get_demo_organizations()
        if not demo_org_ids:
            # Fall back to name-based detection
            from accounts.models import Organization
            demo_org_ids = list(Organization.objects.filter(
                name__icontains='demo'
            ).values_list('id', flat=True))
        
        # Only get tasks that are SEED demo data (not user-created)
        # User-created tasks have created_by_session set
        tasks = list(Task.objects.filter(
            column__board__organization_id__in=demo_org_ids
        ).filter(
            Q(created_by_session__isnull=True) | Q(created_by_session='')
        ).select_related('column'))
        
        if not tasks:
            return 0
        
        # Identify tasks for overdue scenarios (keep a consistent small number overdue)
        incomplete_tasks = [t for t in tasks if t.progress < 100 and 
                          t.column and t.column.name.lower() not in ['done', 'closed', 'completed']]
        target_overdue_count = 5
        overdue_candidates = incomplete_tasks[:target_overdue_count]
        
        tasks_to_update = []
        overdue_set_count = 0
        
        for task in tasks:
            if not task.due_date and not task.start_date:
                continue
            
            column_name = task.column.name.lower() if task.column else ''
            
            # Determine if this should be an overdue task
            is_designated_overdue = (task in overdue_candidates and 
                                    overdue_set_count < target_overdue_count)
            
            if is_designated_overdue:
                days_offset = -(3 + (task.id % 8))  # -3 to -10 days
                overdue_set_count += 1
            elif column_name in ['done', 'closed', 'completed']:
                if task.progress == 100:
                    days_offset = -(task.id % 60 + 3)  # -3 to -63 days
                else:
                    days_offset = -(task.id % 10 + 1)  # -1 to -11 days
            elif column_name in ['review', 'testing', 'reviewing', 'in review']:
                days_offset = (task.id % 11) - 5  # -5 to +5 days
            elif column_name in ['in progress', 'in-progress', 'working', 'investigating']:
                days_offset = (task.id % 26) - 10  # -10 to +15 days
            elif column_name in ['to do', 'to-do', 'todo', 'planning', 'ready']:
                days_offset = (task.id % 19) + 2  # +2 to +20 days
            elif column_name in ['backlog', 'ideas', 'future', 'new']:
                days_offset = (task.id % 46) + 15  # +15 to +60 days
            else:
                days_offset = (task.id % 61) - 30  # -30 to +30 days
            
            # Set the new due date
            if task.due_date:
                task.due_date = now + timedelta(days=days_offset)
            
            # Set start_date based on complexity or fixed duration
            if task.start_date or task.due_date:
                duration = getattr(task, 'complexity_score', 5) or 5
                duration = max(3, min(duration * 2, 21))  # 3-21 days
                if task.due_date:
                    task.start_date = base_date + timedelta(days=days_offset - duration)
            
            tasks_to_update.append(task)
        
        if tasks_to_update:
            Task.objects.bulk_update(tasks_to_update, ['due_date', 'start_date'], batch_size=500)
        
        return len(tasks_to_update)
        
    except Exception as e:
        logger.warning(f"Error refreshing task dates: {e}")
        return 0


def _refresh_milestone_dates(now, base_date):
    """
    Refresh milestone target_date and completed_date fields.
    
    NOTE: Milestones do not have created_by_session because users cannot
    create milestones in demo mode. All milestones are seed data.
    """
    try:
        from kanban.models import Milestone
        
        demo_org_ids = _get_demo_organizations()
        milestones = list(Milestone.objects.filter(
            board__organization_id__in=demo_org_ids
        ))
        
        if not milestones:
            return 0
        
        milestones_to_update = []
        
        for milestone in milestones:
            if not milestone.target_date:
                continue
            
            milestone_type = getattr(milestone, 'milestone_type', 'deliverable')
            
            if milestone.is_completed:
                if milestone_type == 'project_start':
                    days_offset = -60
                elif milestone_type == 'phase_completion':
                    days_offset = -(milestone.id % 40 + 10)
                elif milestone_type == 'deliverable':
                    days_offset = -(milestone.id % 30 + 5)
                else:
                    days_offset = -(milestone.id % 20 + 10)
                
                if milestone.completed_date:
                    milestone.completed_date = base_date + timedelta(days=days_offset + 2)
            else:
                if milestone_type == 'project_end':
                    days_offset = 60
                elif milestone_type == 'phase_completion':
                    days_offset = (milestone.id % 30) + 10
                elif milestone_type == 'deliverable':
                    days_offset = (milestone.id % 25) + 5
                elif milestone_type == 'review':
                    days_offset = (milestone.id % 20) + 3
                else:
                    days_offset = (milestone.id % 15) + 5
            
            milestone.target_date = base_date + timedelta(days=days_offset)
            milestones_to_update.append(milestone)
        
        if milestones_to_update:
            Milestone.objects.bulk_update(milestones_to_update, 
                                         ['target_date', 'completed_date'], batch_size=100)
        
        return len(milestones_to_update)
        
    except Exception as e:
        logger.warning(f"Error refreshing milestone dates: {e}")
        return 0


def _refresh_time_entry_dates(base_date):
    """
    Refresh time entry work_date fields.
    ONLY refreshes entries for original seed demo tasks, not user-created.
    """
    try:
        from kanban.budget_models import TimeEntry
        from django.db.models import Q
        
        demo_org_ids = _get_demo_organizations()
        # Only refresh time entries for SEED demo tasks (not user-created)
        entries = list(TimeEntry.objects.filter(
            task__column__board__organization_id__in=demo_org_ids
        ).filter(
            Q(task__created_by_session__isnull=True) | Q(task__created_by_session='')
        ))
        
        if not entries:
            return 0
        
        entries_to_update = []
        
        for entry in entries:
            if not entry.work_date:
                continue
            
            # Time entries in the past 30 days
            days_offset = -(entry.id % 30 + 1)
            entry.work_date = base_date + timedelta(days=days_offset)
            entries_to_update.append(entry)
        
        if entries_to_update:
            TimeEntry.objects.bulk_update(entries_to_update, ['work_date'], batch_size=500)
        
        return len(entries_to_update)
        
    except Exception as e:
        logger.warning(f"Error refreshing time entry dates: {e}")
        return 0


def _refresh_engagement_dates(base_date):
    """Refresh stakeholder engagement record dates."""
    try:
        from kanban.stakeholder_models import StakeholderEngagementRecord
        
        demo_org_ids = _get_demo_organizations()
        records = list(StakeholderEngagementRecord.objects.filter(
            stakeholder__board__organization_id__in=demo_org_ids
        ))
        
        if not records:
            return 0
        
        records_to_update = []
        
        for record in records:
            if not record.date:
                continue
            
            # Engagement records in the past 60 days
            days_offset = -(record.id % 60 + 1)
            record.date = base_date + timedelta(days=days_offset)
            records_to_update.append(record)
        
        if records_to_update:
            StakeholderEngagementRecord.objects.bulk_update(records_to_update, 
                                                           ['date'], batch_size=500)
        
        return len(records_to_update)
        
    except Exception as e:
        logger.warning(f"Error refreshing engagement dates: {e}")
        return 0


def _refresh_retrospective_dates(base_date):
    """Refresh retrospective period_start and period_end fields."""
    try:
        from kanban.retrospective_models import ProjectRetrospective
        
        demo_org_ids = _get_demo_organizations()
        retrospectives = list(ProjectRetrospective.objects.filter(
            board__organization_id__in=demo_org_ids
        ))
        
        if not retrospectives:
            return 0
        
        retrospectives_to_update = []
        
        for retro in retrospectives:
            status = getattr(retro, 'status', 'finalized')
            retro_type = getattr(retro, 'retrospective_type', 'sprint')
            
            # Determine period based on status and type
            if status in ['finalized', 'archived']:
                # Past retrospectives
                if retro_type == 'quarterly':
                    period_end_offset = -(retro.id % 90 + 30)  # 30-120 days ago
                    period_duration = 90
                elif retro_type == 'project':
                    period_end_offset = -(retro.id % 60 + 15)  # 15-75 days ago
                    period_duration = 30
                else:  # sprint
                    period_end_offset = -(retro.id % 45 + 7)  # 7-52 days ago
                    period_duration = 14
            else:
                # Current/draft retrospectives
                period_end_offset = -(retro.id % 14)  # 0-14 days ago
                period_duration = 14
            
            retro.period_end = base_date + timedelta(days=period_end_offset)
            retro.period_start = retro.period_end - timedelta(days=period_duration)
            retrospectives_to_update.append(retro)
        
        if retrospectives_to_update:
            ProjectRetrospective.objects.bulk_update(retrospectives_to_update, 
                                                     ['period_start', 'period_end'], batch_size=100)
        
        return len(retrospectives_to_update)
        
    except Exception as e:
        logger.warning(f"Error refreshing retrospective dates: {e}")
        return 0


def _refresh_velocity_snapshot_dates(base_date):
    """Refresh velocity snapshot period dates."""
    try:
        from kanban.burndown_models import TeamVelocitySnapshot
        
        demo_org_ids = _get_demo_organizations()
        snapshots = list(TeamVelocitySnapshot.objects.filter(
            board__organization_id__in=demo_org_ids
        ))
        
        if not snapshots:
            return 0
        
        snapshots_to_update = []
        
        for i, snapshot in enumerate(snapshots):
            period_type = getattr(snapshot, 'period_type', 'weekly')
            
            # Spread snapshots across past periods
            if period_type == 'daily':
                period_end_offset = -(i + 1)
                period_duration = 1
            elif period_type == 'weekly':
                period_end_offset = -((i + 1) * 7)
                period_duration = 7
            elif period_type == 'sprint':
                period_end_offset = -((i + 1) * 14)
                period_duration = 14
            else:  # monthly
                period_end_offset = -((i + 1) * 30)
                period_duration = 30
            
            snapshot.period_end = base_date + timedelta(days=period_end_offset)
            snapshot.period_start = snapshot.period_end - timedelta(days=period_duration)
            snapshots_to_update.append(snapshot)
        
        if snapshots_to_update:
            TeamVelocitySnapshot.objects.bulk_update(snapshots_to_update, 
                                                     ['period_start', 'period_end'], batch_size=100)
        
        return len(snapshots_to_update)
        
    except Exception as e:
        logger.warning(f"Error refreshing velocity snapshot dates: {e}")
        return 0


def _refresh_coaching_suggestion_dates(now):
    """Refresh coaching suggestion created_at and updated_at fields."""
    try:
        from kanban.coach_models import CoachingSuggestion
        
        demo_org_ids = _get_demo_organizations()
        suggestions = list(CoachingSuggestion.objects.filter(
            board__organization_id__in=demo_org_ids
        ))
        
        if not suggestions:
            return 0
        
        suggestions_to_update = []
        
        for suggestion in suggestions:
            status = getattr(suggestion, 'status', 'active')
            
            # Distribute suggestions based on status
            if status in ['resolved', 'dismissed', 'expired']:
                days_offset = -(suggestion.id % 30 + 3)  # 3-33 days ago
            elif status in ['acknowledged', 'in_progress']:
                days_offset = -(suggestion.id % 7 + 1)  # 1-7 days ago
            else:  # active
                days_offset = -(suggestion.id % 3)  # 0-2 days ago
            
            suggestion.created_at = now + timedelta(days=days_offset)
            suggestions_to_update.append(suggestion)
        
        if suggestions_to_update:
            CoachingSuggestion.objects.bulk_update(suggestions_to_update, 
                                                   ['created_at'], batch_size=100)
        
        return len(suggestions_to_update)
        
    except Exception as e:
        logger.warning(f"Error refreshing coaching suggestion dates: {e}")
        return 0


def _refresh_pm_metrics_dates(base_date):
    """Refresh PM performance metrics dates."""
    try:
        from kanban.coach_models import PMMetrics
        
        demo_org_ids = _get_demo_organizations()
        metrics = list(PMMetrics.objects.filter(
            board__organization_id__in=demo_org_ids
        ))
        
        if not metrics:
            return 0
        
        metrics_to_update = []
        
        for i, metric in enumerate(metrics):
            # Metrics from various past periods
            days_offset = -(i * 7 + 1)  # Weekly intervals
            metric.period_start = base_date + timedelta(days=days_offset - 7)
            metric.period_end = base_date + timedelta(days=days_offset)
            metrics_to_update.append(metric)
        
        if metrics_to_update:
            PMMetrics.objects.bulk_update(metrics_to_update, 
                                          ['period_start', 'period_end'], batch_size=100)
        
        return len(metrics_to_update)
        
    except Exception as e:
        logger.warning(f"Error refreshing PM metrics dates: {e}")
        return 0


def _refresh_conflict_dates(now):
    """Refresh conflict detection detected_at and resolved_at fields."""
    try:
        from kanban.conflict_models import ConflictDetection, ConflictResolution
        
        demo_org_ids = _get_demo_organizations()
        
        # Refresh conflicts
        conflicts = list(ConflictDetection.objects.filter(
            board__organization_id__in=demo_org_ids
        ))
        
        conflicts_to_update = []
        for conflict in conflicts:
            status = getattr(conflict, 'status', 'active')
            
            if status in ['resolved', 'auto_resolved']:
                days_offset = -(conflict.id % 30 + 3)
            elif status == 'ignored':
                days_offset = -(conflict.id % 14 + 1)
            else:  # active
                days_offset = -(conflict.id % 3)
            
            # ConflictDetection uses detected_at, not created_at
            if hasattr(conflict, 'detected_at'):
                conflict.detected_at = now + timedelta(days=days_offset)
            if hasattr(conflict, 'resolved_at') and conflict.resolved_at:
                conflict.resolved_at = now + timedelta(days=days_offset + 1)
            conflicts_to_update.append(conflict)
        
        if conflicts_to_update:
            fields_to_update = []
            if hasattr(conflicts[0], 'detected_at'):
                fields_to_update.append('detected_at')
            if hasattr(conflicts[0], 'resolved_at'):
                fields_to_update.append('resolved_at')
            if fields_to_update:
                ConflictDetection.objects.bulk_update(conflicts_to_update, 
                                                      fields_to_update, batch_size=100)
        
        # Refresh resolutions
        resolutions = list(ConflictResolution.objects.filter(
            conflict__board__organization_id__in=demo_org_ids
        ))
        
        resolutions_to_update = []
        for resolution in resolutions:
            days_offset = -(resolution.id % 30 + 2)
            if hasattr(resolution, 'created_at'):
                resolution.created_at = now + timedelta(days=days_offset)
            resolutions_to_update.append(resolution)
        
        if resolutions_to_update and hasattr(resolutions[0], 'created_at'):
            ConflictResolution.objects.bulk_update(resolutions_to_update, 
                                                   ['created_at'], batch_size=100)
        
        return len(conflicts_to_update) + len(resolutions_to_update)
        
    except Exception as e:
        logger.warning(f"Error refreshing conflict dates: {e}")
        return 0


def _refresh_wiki_dates(now):
    """Refresh wiki page created_at and updated_at fields."""
    try:
        from wiki.models import WikiPage, WikiPageVersion
        
        demo_org_ids = _get_demo_organizations()
        pages = list(WikiPage.objects.filter(
            organization_id__in=demo_org_ids
        ))
        
        if not pages:
            return 0
        
        pages_to_update = []
        
        for i, page in enumerate(pages):
            # Distribute page dates - newer pages more recently updated
            created_days_ago = (i + 1) * 3 + 10  # 13, 16, 19, ... days ago
            updated_days_ago = i % 14  # 0-13 days ago
            
            page.created_at = now - timedelta(days=created_days_ago)
            page.updated_at = now - timedelta(days=updated_days_ago)
            pages_to_update.append(page)
        
        if pages_to_update:
            WikiPage.objects.bulk_update(pages_to_update, 
                                        ['created_at', 'updated_at'], batch_size=100)
        
        # Also update wiki page versions
        versions = list(WikiPageVersion.objects.filter(
            page__organization_id__in=demo_org_ids
        ))
        
        for i, version in enumerate(versions):
            days_offset = -(i + 1)
            version.created_at = now + timedelta(days=days_offset)
        
        if versions:
            WikiPageVersion.objects.bulk_update(versions, ['created_at'], batch_size=100)
        
        return len(pages_to_update)
        
    except Exception as e:
        logger.warning(f"Error refreshing wiki dates: {e}")
        return 0


def _refresh_ai_session_dates(now):
    """Refresh AI assistant session dates."""
    try:
        from ai_assistant.models import AIAssistantSession, AIAssistantMessage
        
        # Get demo users
        from django.contrib.auth.models import User
        demo_usernames = ['demo_admin_solo', 'alex_chen_demo', 'sam_rivera_demo', 
                         'jordan_taylor_demo', 'john_doe', 'jane_smith']
        demo_users = list(User.objects.filter(username__in=demo_usernames).values_list('id', flat=True))
        
        if not demo_users:
            return 0
        
        sessions = list(AIAssistantSession.objects.filter(user_id__in=demo_users))
        
        sessions_to_update = []
        for i, session in enumerate(sessions):
            # Recent sessions
            days_offset = -(i % 14)  # 0-13 days ago
            hours_offset = -(i % 8)  # 0-7 hours ago
            
            session.created_at = now + timedelta(days=days_offset, hours=hours_offset)
            session.updated_at = now + timedelta(days=days_offset) + timedelta(hours=hours_offset + 1)
            sessions_to_update.append(session)
        
        if sessions_to_update:
            AIAssistantSession.objects.bulk_update(sessions_to_update, 
                                                   ['created_at', 'updated_at'], batch_size=100)
        
        # Update messages too
        messages = list(AIAssistantMessage.objects.filter(session__user_id__in=demo_users))
        
        for i, message in enumerate(messages):
            days_offset = -(i % 14)
            minutes_offset = i % 60
            message.created_at = now + timedelta(days=days_offset, minutes=minutes_offset)
        
        if messages:
            AIAssistantMessage.objects.bulk_update(messages, ['created_at'], batch_size=500)
        
        return len(sessions_to_update)
        
    except Exception as e:
        logger.warning(f"Error refreshing AI session dates: {e}")
        return 0


def _refresh_improvement_metrics_dates(base_date):
    """Refresh improvement metrics dates from retrospectives."""
    try:
        from kanban.retrospective_models import ImprovementMetric
        
        demo_org_ids = _get_demo_organizations()
        metrics = list(ImprovementMetric.objects.filter(
            retrospective__board__organization_id__in=demo_org_ids
        ))
        
        if not metrics:
            return 0
        
        metrics_to_update = []
        
        for i, metric in enumerate(metrics):
            # Metrics from past periods
            days_offset = -(i * 14 + 7)  # Two-week intervals
            metric.measured_at = base_date + timedelta(days=days_offset)
            metrics_to_update.append(metric)
        
        if metrics_to_update:
            ImprovementMetric.objects.bulk_update(metrics_to_update, 
                                                  ['measured_at'], batch_size=100)
        
        return len(metrics_to_update)
        
    except Exception as e:
        logger.warning(f"Error refreshing improvement metrics dates: {e}")
        return 0


def _refresh_action_item_dates(now, base_date):
    """Refresh retrospective action item dates."""
    try:
        from kanban.retrospective_models import RetrospectiveActionItem
        
        demo_org_ids = _get_demo_organizations()
        action_items = list(RetrospectiveActionItem.objects.filter(
            retrospective__board__organization_id__in=demo_org_ids
        ))
        
        if not action_items:
            return 0
        
        items_to_update = []
        
        for item in action_items:
            status = getattr(item, 'status', 'pending')
            
            if status == 'completed':
                # Completed items in the past
                created_offset = -(item.id % 30 + 7)
                due_offset = -(item.id % 20 + 3)
            elif status == 'in_progress':
                # In-progress items recent
                created_offset = -(item.id % 14 + 3)
                due_offset = (item.id % 7) + 3  # Due in near future
            else:  # pending
                created_offset = -(item.id % 7 + 1)
                due_offset = (item.id % 14) + 7  # Due in 1-2 weeks
            
            item.created_at = now + timedelta(days=created_offset)
            if hasattr(item, 'due_date'):
                item.due_date = base_date + timedelta(days=due_offset)
            items_to_update.append(item)
        
        if items_to_update:
            fields_to_update = ['created_at']
            if hasattr(action_items[0], 'due_date'):
                fields_to_update.append('due_date')
            RetrospectiveActionItem.objects.bulk_update(items_to_update, 
                                                        fields_to_update, batch_size=100)
        
        return len(items_to_update)
        
    except Exception as e:
        logger.warning(f"Error refreshing action item dates: {e}")
        return 0


def _refresh_burndown_prediction_dates(now, base_date):
    """Refresh burndown prediction date fields."""
    try:
        from kanban.burndown_models import BurndownPrediction
        
        demo_org_ids = _get_demo_organizations()
        predictions = list(BurndownPrediction.objects.filter(
            board__organization_id__in=demo_org_ids
        ))
        
        if not predictions:
            return 0
        
        predictions_to_update = []
        
        for i, prediction in enumerate(predictions):
            # Adjust the completion date predictions to be future-relative
            if i == 0:
                # Current sprint - completing soon
                target_date_offset = 7
            else:
                target_date_offset = 7 + (i * 14)
            
            # Update the completion date predictions
            prediction.predicted_completion_date = base_date + timedelta(days=target_date_offset)
            prediction.completion_date_lower_bound = base_date + timedelta(days=target_date_offset - 3)
            prediction.completion_date_upper_bound = base_date + timedelta(days=target_date_offset + 7)
            predictions_to_update.append(prediction)
        
        if predictions_to_update:
            BurndownPrediction.objects.bulk_update(predictions_to_update, 
                ['predicted_completion_date', 'completion_date_lower_bound', 'completion_date_upper_bound'], 
                batch_size=100)
        
        return len(predictions_to_update)
        
    except Exception as e:
        logger.warning(f"Error refreshing burndown prediction dates: {e}")
        return 0


def _refresh_resource_leveling_dates(now, base_date):
    """Refresh resource leveling suggestion dates."""
    try:
        from kanban.resource_leveling_models import ResourceLevelingSuggestion, TaskAssignmentHistory
        
        demo_org_ids = _get_demo_organizations()
        
        # Update ResourceLevelingSuggestion
        suggestions = list(ResourceLevelingSuggestion.objects.filter(
            organization_id__in=demo_org_ids
        ))
        
        suggestions_to_update = []
        for i, suggestion in enumerate(suggestions):
            status = getattr(suggestion, 'status', 'pending')
            
            if status in ['accepted', 'rejected']:
                created_offset = -(suggestion.id % 30 + 3)
            elif status == 'expired':
                created_offset = -(suggestion.id % 14 + 5)
            else:  # pending
                created_offset = -(suggestion.id % 2)  # Recent
            
            # expires_at is 48 hours after creation
            suggestion.expires_at = now + timedelta(days=created_offset) + timedelta(hours=48)
            
            # Update projected dates if they exist
            if suggestion.current_projected_date:
                suggestion.current_projected_date = now + timedelta(days=7 + (suggestion.id % 14))
            if suggestion.suggested_projected_date:
                suggestion.suggested_projected_date = now + timedelta(days=5 + (suggestion.id % 10))
            
            suggestions_to_update.append(suggestion)
        
        if suggestions_to_update:
            fields = ['expires_at']
            if hasattr(suggestions[0], 'current_projected_date') and suggestions[0].current_projected_date:
                fields.append('current_projected_date')
            if hasattr(suggestions[0], 'suggested_projected_date') and suggestions[0].suggested_projected_date:
                fields.append('suggested_projected_date')
            ResourceLevelingSuggestion.objects.bulk_update(suggestions_to_update, fields, batch_size=100)
        
        # Update TaskAssignmentHistory
        histories = list(TaskAssignmentHistory.objects.filter(
            task__column__board__organization_id__in=demo_org_ids
        ))
        
        histories_to_update = []
        for i, history in enumerate(histories):
            days_offset = -(i + 1)  # Sequential days in past
            if hasattr(history, 'changed_at'):
                history.changed_at = now + timedelta(days=days_offset)
            histories_to_update.append(history)
        
        if histories_to_update and hasattr(histories[0], 'changed_at'):
            TaskAssignmentHistory.objects.bulk_update(histories_to_update, ['changed_at'], batch_size=100)
        
        return len(suggestions_to_update) + len(histories_to_update)
        
    except Exception as e:
        logger.warning(f"Error refreshing resource leveling dates: {e}")
        return 0


def _refresh_roi_snapshot_dates(base_date):
    """Refresh ProjectROI snapshot dates."""
    try:
        from kanban.budget_models import ProjectROI
        
        demo_org_ids = _get_demo_organizations()
        snapshots = list(ProjectROI.objects.filter(
            board__organization_id__in=demo_org_ids
        ))
        
        if not snapshots:
            return 0
        
        snapshots_to_update = []
        
        for i, snapshot in enumerate(snapshots):
            # Weekly snapshots over past months
            days_offset = -(i * 7 + 1)
            snapshot.snapshot_date = timezone.now() + timedelta(days=days_offset)
            snapshots_to_update.append(snapshot)
        
        if snapshots_to_update:
            ProjectROI.objects.bulk_update(snapshots_to_update, 
                                           ['snapshot_date'], batch_size=100)
        
        return len(snapshots_to_update)
        
    except Exception as e:
        logger.warning(f"Error refreshing ROI snapshot dates: {e}")
        return 0


def _refresh_trend_analysis_dates(base_date):
    """Refresh retrospective trend analysis dates."""
    try:
        from kanban.retrospective_models import RetrospectiveTrend
        
        demo_org_ids = _get_demo_organizations()
        trends = list(RetrospectiveTrend.objects.filter(
            board__organization_id__in=demo_org_ids
        ))
        
        if not trends:
            return 0
        
        trends_to_update = []
        
        for i, trend in enumerate(trends):
            # Trend analysis dates
            if hasattr(trend, 'analysis_date'):
                trend.analysis_date = base_date - timedelta(days=i * 14)
            if hasattr(trend, 'period_start'):
                trend.period_start = base_date - timedelta(days=(i + 1) * 90)
            if hasattr(trend, 'period_end'):
                trend.period_end = base_date - timedelta(days=i * 14)
            trends_to_update.append(trend)
        
        if trends_to_update:
            fields = []
            if hasattr(trends[0], 'analysis_date'):
                fields.append('analysis_date')
            if hasattr(trends[0], 'period_start'):
                fields.append('period_start')
            if hasattr(trends[0], 'period_end'):
                fields.append('period_end')
            if fields:
                RetrospectiveTrend.objects.bulk_update(trends_to_update, fields, batch_size=100)
        
        return len(trends_to_update)
        
    except Exception as e:
        logger.warning(f"Error refreshing trend analysis dates: {e}")
        return 0


def _refresh_sprint_milestone_dates(base_date):
    """Refresh sprint milestone target_date and actual_date fields."""
    try:
        from kanban.burndown_models import SprintMilestone
        
        demo_org_ids = _get_demo_organizations()
        milestones = list(SprintMilestone.objects.filter(
            board__organization_id__in=demo_org_ids
        ))
        
        if not milestones:
            return 0
        
        milestones_to_update = []
        
        for i, milestone in enumerate(milestones):
            if milestone.is_completed:
                # Completed milestones in the past
                target_offset = -(milestone.id % 30 + 7)  # 7-37 days ago
                actual_offset = target_offset + (milestone.id % 3)  # Completed around target date
                milestone.target_date = base_date + timedelta(days=target_offset)
                if milestone.actual_date:
                    milestone.actual_date = base_date + timedelta(days=actual_offset)
            else:
                # Future milestones
                target_offset = (milestone.id % 45) + 7  # 7-52 days in future
                milestone.target_date = base_date + timedelta(days=target_offset)
                milestone.actual_date = None  # Not completed yet
            
            milestones_to_update.append(milestone)
        
        if milestones_to_update:
            SprintMilestone.objects.bulk_update(milestones_to_update, 
                                                ['target_date', 'actual_date'], batch_size=100)
        
        return len(milestones_to_update)
        
    except Exception as e:
        logger.warning(f"Error refreshing sprint milestone dates: {e}")
        return 0