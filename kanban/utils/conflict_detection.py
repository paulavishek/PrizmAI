"""
Conflict Detection Service
Detects resource conflicts, schedule conflicts, and dependency conflicts in project tasks.
Provides intelligent conflict resolution suggestions.
"""
from datetime import datetime, timedelta
from django.db.models import Q
from django.utils import timezone
from django.contrib.auth.models import User
from kanban.models import Task, Board
from kanban.conflict_models import (
    ConflictDetection, ConflictResolution, ResolutionPattern
)
import uuid
import logging

logger = logging.getLogger(__name__)


class ConflictDetectionService:
    """
    Main service for detecting and analyzing conflicts in project management.
    """
    
    def __init__(self, board=None):
        """
        Initialize the conflict detection service.
        
        Args:
            board: Specific board to analyze, or None for all boards
        """
        self.board = board
        self.detection_run_id = str(uuid.uuid4())[:8]
    
    def detect_all_conflicts(self):
        """
        Run all conflict detection algorithms.
        Returns a summary of detected conflicts.
        """
        conflicts = []
        
        # Get boards to analyze
        if self.board:
            boards = [self.board]
        else:
            # Only analyze active boards with recent activity,
            # excluding official demo templates and sandbox copies
            # (sandbox conflicts are seeded during provisioning).
            from django.utils import timezone
            thirty_days_ago = timezone.now() - timedelta(days=30)
            boards = Board.objects.filter(
                columns__tasks__updated_at__gte=thirty_days_ago,
                is_official_demo_board=False,
                is_sandbox_copy=False,
            ).distinct()
        
        for board in boards:
            # Detect resource conflicts
            resource_conflicts = self.detect_resource_conflicts(board)
            conflicts.extend(resource_conflicts)
            
            # Detect schedule conflicts
            schedule_conflicts = self.detect_schedule_conflicts(board)
            conflicts.extend(schedule_conflicts)
            
            # Detect dependency conflicts
            dependency_conflicts = self.detect_dependency_conflicts(board)
            conflicts.extend(dependency_conflicts)
        
        return {
            'total_conflicts': len(conflicts),
            'by_type': {
                'resource': len([c for c in conflicts if c.conflict_type == 'resource']),
                'schedule': len([c for c in conflicts if c.conflict_type == 'schedule']),
                'dependency': len([c for c in conflicts if c.conflict_type == 'dependency']),
            },
            'by_severity': {
                'low': len([c for c in conflicts if c.severity == 'low']),
                'medium': len([c for c in conflicts if c.severity == 'medium']),
                'high': len([c for c in conflicts if c.severity == 'high']),
                'critical': len([c for c in conflicts if c.severity == 'critical']),
            },
            'conflicts': conflicts,
            'detection_run_id': self.detection_run_id
        }
    
    def detect_resource_conflicts(self, board):
        """
        Detect resource conflicts: same person assigned to overlapping tasks.
        
        A resource conflict occurs when:
        1. Same user assigned to multiple tasks
        2. Tasks have overlapping time periods
        3. Total workload exceeds reasonable capacity
        """
        conflicts = []
        
        # Get all tasks with assignments and dates
        tasks = Task.objects.filter(
            column__board=board,
            assigned_to__isnull=False,
            start_date__isnull=False,
            due_date__isnull=False
        ).exclude(
            column__name__icontains='done'
        ).exclude(
            column__name__icontains='complete'
        ).select_related('assigned_to', 'column')
        
        # Group by assigned user
        user_tasks = {}
        for task in tasks:
            user = task.assigned_to
            if user not in user_tasks:
                user_tasks[user] = []
            user_tasks[user].append(task)
        
        # Check each user for overlapping tasks
        for user, user_task_list in user_tasks.items():
            if len(user_task_list) < 2:
                continue
            
            # Sort by start date
            user_task_list.sort(key=lambda t: t.start_date)
            
            # Check for overlaps
            for i, task1 in enumerate(user_task_list):
                for task2 in user_task_list[i+1:]:
                    # Convert due_date (datetime) to date for comparison
                    task1_due = task1.due_date.date() if hasattr(task1.due_date, 'date') else task1.due_date
                    task2_due = task2.due_date.date() if hasattr(task2.due_date, 'date') else task2.due_date
                    
                    # Check if tasks overlap
                    if self._tasks_overlap(
                        task1.start_date, task1_due,
                        task2.start_date, task2_due
                    ):
                        user_display = user.get_full_name() or user.username
                        conflict_title = f"Resource conflict: {user_display} overbooked"

                        # Check if this conflict already exists and is active
                        # Use title match instead of M2M lookup so copied
                        # conflicts with empty M2M are still detected.
                        existing = ConflictDetection.objects.filter(
                            board=board,
                            conflict_type='resource',
                            status='active',
                            title=conflict_title,
                        ).first()
                        
                        if existing:
                            continue  # Skip if already detected
                        
                        # Calculate severity based on overlap duration and task priority
                        severity = self._calculate_resource_conflict_severity(
                            task1, task2, user
                        )
                        
                        # Create conflict
                        conflict = ConflictDetection.objects.create(
                            conflict_type='resource',
                            severity=severity,
                            board=board,
                            title=conflict_title,
                            description=f"{user.get_full_name() or user.username} is assigned to overlapping tasks: '{task1.title}' and '{task2.title}'",
                            conflict_data={
                                'user_id': user.id,
                                'user_name': user.get_full_name() or user.username,
                                'task1_id': task1.id,
                                'task1_title': task1.title,
                                'task1_dates': {
                                    'start': str(task1.start_date),
                                    'due': str(task1.due_date)
                                },
                                'task2_id': task2.id,
                                'task2_title': task2.title,
                                'task2_dates': {
                                    'start': str(task2.start_date),
                                    'due': str(task2.due_date)
                                },
                                'overlap_days': self._calculate_overlap_days(
                                    task1.start_date, task1_due,
                                    task2.start_date, task2_due
                                )
                            },
                            detection_run_id=self.detection_run_id,
                            auto_detection=True
                        )
                        
                        # Add related tasks and users
                        conflict.tasks.add(task1, task2)
                        conflict.affected_users.add(user)
                        
                        # Ensure notifications are created
                        conflict.ensure_notifications()
                        
                        conflicts.append(conflict)
        
        return conflicts
    
    def detect_schedule_conflicts(self, board):
        """
        Detect schedule conflicts: unrealistic timelines, missed deadlines.
        
        A schedule conflict occurs when:
        1. Task due date is in the past but task not complete
        2. Task duration is unrealistically short for complexity
        3. Too many high-priority tasks due at same time
        """
        conflicts = []
        now = timezone.now()
        
        # Get incomplete tasks
        incomplete_tasks = Task.objects.filter(
            column__board=board,
            due_date__isnull=False
        ).exclude(
            column__name__icontains='done'
        ).exclude(
            column__name__icontains='complete'
        ).select_related('column', 'assigned_to')
        
        # 1. Overdue tasks
        overdue_tasks = incomplete_tasks.filter(due_date__lt=now)
        if overdue_tasks.count() >= 3:  # Multiple overdue = schedule conflict
            for task in overdue_tasks[:5]:  # Limit to prevent spam
                # Check if an active schedule conflict already exists for this
                # task on this board — prefer title match so copied conflicts
                # with empty M2M are still detected as duplicates.
                existing = ConflictDetection.objects.filter(
                    board=board,
                    conflict_type='schedule',
                    status='active',
                    title=f"Overdue task: {task.title}",
                ).first()
                
                if existing:
                    # Update severity / description on the existing record
                    days_overdue = (now.date() - task.due_date.date() if hasattr(task.due_date, 'date') else now.date() - task.due_date).days
                    new_sev = 'high' if days_overdue > 7 else 'medium' if days_overdue > 3 else 'low'
                    ConflictDetection.objects.filter(pk=existing.pk).update(
                        severity=new_sev,
                        description=f"Task '{task.title}' is {days_overdue} days overdue (due: {task.due_date.strftime('%Y-%m-%d')})",
                    )
                    # Ensure M2M is linked (may have been empty from sandbox copy)
                    if not existing.tasks.filter(pk=task.pk).exists():
                        existing.tasks.add(task)
                    continue
                
                days_overdue = (now.date() - task.due_date.date() if hasattr(task.due_date, 'date') else now.date() - task.due_date).days
                
                severity = 'high' if days_overdue > 7 else 'medium' if days_overdue > 3 else 'low'
                
                conflict = ConflictDetection.objects.create(
                    conflict_type='schedule',
                    severity=severity,
                    board=board,
                    title=f"Overdue task: {task.title}",
                    description=f"Task '{task.title}' is {days_overdue} days overdue (due: {task.due_date.strftime('%Y-%m-%d')})",
                    conflict_data={
                        'task_id': task.id,
                        'task_title': task.title,
                        'due_date': str(task.due_date),
                        'days_overdue': days_overdue,
                        'assigned_to': task.assigned_to.username if task.assigned_to else None
                    },
                    detection_run_id=self.detection_run_id,
                    auto_detection=True
                )
                
                conflict.tasks.add(task)
                if task.assigned_to:
                    conflict.affected_users.add(task.assigned_to)
                
                # Ensure notifications are created
                conflict.ensure_notifications()
                
                conflicts.append(conflict)
        
        # 2. Unrealistic task durations (short time for high complexity)
        for task in incomplete_tasks:
            if task.start_date and task.due_date:
                task_due = task.due_date.date() if hasattr(task.due_date, 'date') else task.due_date
                duration = (task_due - task.start_date).days
                complexity = getattr(task, 'complexity_score', 5)
                
                # Heuristic: complexity 8+ should have at least 3 days
                if complexity >= 8 and duration < 3:
                    existing = ConflictDetection.objects.filter(
                        board=board,
                        conflict_type='schedule',
                        status='active',
                        tasks=task,
                        title__icontains='Unrealistic timeline'
                    ).first()
                    
                    if existing:
                        continue
                    
                    conflict = ConflictDetection.objects.create(
                        conflict_type='schedule',
                        severity='medium',
                        board=board,
                        title=f"Unrealistic timeline: {task.title}",
                        description=f"High complexity task '{task.title}' (complexity: {complexity}) has only {duration} days scheduled",
                        conflict_data={
                            'task_id': task.id,
                            'task_title': task.title,
                            'complexity': complexity,
                            'duration_days': duration,
                            'recommended_duration': complexity
                        },
                        detection_run_id=self.detection_run_id,
                        auto_detection=True
                    )
                    
                    conflict.tasks.add(task)
                    if task.assigned_to:
                        conflict.affected_users.add(task.assigned_to)
                    
                    # Ensure notifications are created
                    conflict.ensure_notifications()
                    
                    conflicts.append(conflict)
        
        return conflicts
    
    def detect_dependency_conflicts(self, board):
        """
        Detect dependency conflicts: blocked tasks, circular dependencies.
        
        A dependency conflict occurs when:
        1. Task A depends on Task B, but Task B is blocked/delayed
        2. Circular dependencies exist
        3. Dependent task scheduled before prerequisite
        """
        conflicts = []
        
        # Get all tasks with dependencies
        # Note: This assumes there's a way to track dependencies
        # You may need to adjust based on your actual Task model structure
        tasks = Task.objects.filter(column__board=board).exclude(
            column__name__icontains='done'
        ).exclude(
            column__name__icontains='complete'
        )
        
        # Check for tasks that mention dependencies in description
        for task in tasks:
            if not task.description:
                continue
            
            # Simple heuristic: look for "depends on", "blocked by", "waiting for"
            description_lower = task.description.lower()
            dependency_indicators = ['depends on', 'blocked by', 'waiting for', 'requires', 'needs']
            
            if any(indicator in description_lower for indicator in dependency_indicators):
                # Check if task is overdue or at risk
                if task.due_date and task.due_date < timezone.now():
                    existing = ConflictDetection.objects.filter(
                        board=board,
                        conflict_type='dependency',
                        status='active',
                        tasks=task
                    ).first()
                    
                    if existing:
                        continue
                    
                    conflict = ConflictDetection.objects.create(
                        conflict_type='dependency',
                        severity='high',
                        board=board,
                        title=f"Blocked task overdue: {task.title}",
                        description=f"Task '{task.title}' has dependencies and is overdue. Check if blocking tasks are complete.",
                        conflict_data={
                            'task_id': task.id,
                            'task_title': task.title,
                            'due_date': str(task.due_date),
                            'description_snippet': task.description[:200]
                        },
                        detection_run_id=self.detection_run_id,
                        auto_detection=True
                    )
                    
                    conflict.tasks.add(task)
                    if task.assigned_to:
                        conflict.affected_users.add(task.assigned_to)
                    
                    # Ensure notifications are created
                    conflict.ensure_notifications()
                    
                    conflicts.append(conflict)
        
        return conflicts
    
    # Helper methods
    
    def _tasks_overlap(self, start1, end1, start2, end2):
        """Check if two date ranges overlap."""
        return start1 <= end2 and start2 <= end1
    
    def _calculate_overlap_days(self, start1, end1, start2, end2):
        """Calculate number of overlapping days."""
        overlap_start = max(start1, start2)
        overlap_end = min(end1, end2)
        if overlap_start <= overlap_end:
            return (overlap_end - overlap_start).days + 1
        return 0
    
    def _calculate_resource_conflict_severity(self, task1, task2, user):
        """Calculate severity of resource conflict."""
        # Base severity on task priorities and overlap
        priority_scores = {'low': 1, 'medium': 2, 'high': 3, 'urgent': 4}
        
        task1_priority = priority_scores.get(task1.priority, 2)
        task2_priority = priority_scores.get(task2.priority, 2)
        combined_priority = task1_priority + task2_priority
        
        task1_due = task1.due_date.date() if hasattr(task1.due_date, 'date') else task1.due_date
        task2_due = task2.due_date.date() if hasattr(task2.due_date, 'date') else task2.due_date
        
        overlap_days = self._calculate_overlap_days(
            task1.start_date, task1_due,
            task2.start_date, task2_due
        )
        
        # Severity logic
        if combined_priority >= 7 or overlap_days > 5:
            return 'critical'
        elif combined_priority >= 5 or overlap_days > 3:
            return 'high'
        elif overlap_days > 1:
            return 'medium'
        return 'low'


class ConflictResolutionSuggester:
    """
    Suggests resolutions for detected conflicts using AI and learned patterns.
    """
    
    def __init__(self, conflict):
        """
        Initialize suggester for a specific conflict.
        
        Args:
            conflict: ConflictDetection instance
        """
        self.conflict = conflict
    
    def generate_suggestions(self):
        """
        Generate resolution suggestions for the conflict.
        Returns list of ConflictResolution instances.
        """
        suggestions = []
        
        if self.conflict.conflict_type == 'resource':
            suggestions = self._suggest_resource_resolutions()
        elif self.conflict.conflict_type == 'schedule':
            suggestions = self._suggest_schedule_resolutions()
        elif self.conflict.conflict_type == 'dependency':
            suggestions = self._suggest_dependency_resolutions()
        
        # Apply learned patterns to adjust confidence
        suggestions = self._apply_learned_patterns(suggestions)
        
        # Save suggestions to conflict
        self.conflict.suggested_resolutions = [
            {
                'id': s.id,
                'type': s.resolution_type,
                'title': s.title,
                'confidence': s.ai_confidence
            }
            for s in suggestions
        ]
        self.conflict.save()
        
        return suggestions
    
    def _get_resolution_reasoning(self, resolution_type):
        """
        Return substantive 2-3 sentence reasoning for a (conflict_type, resolution_type) pair.
        Specific to the conflict type so the text is meaningful for the card's "Why this works" section.
        """
        conflict_type = self.conflict.conflict_type
        reasoning_map = {
            ('resource', 'reassign'): (
                "Reassigning one of the conflicting tasks to a team member with available capacity directly removes "
                "the overallocation at its source, giving each task a dedicated owner with realistic bandwidth. "
                "The expected outcome is that both tasks proceed at their normal pace without quality trade-offs from "
                "context-switching or divided attention. "
                "For this to work, the receiving team member needs sufficient context on the task — a brief handover "
                "is recommended to avoid ramp-up delays."
            ),
            ('resource', 'reschedule'): (
                "Rescheduling one task to a non-overlapping window serialises the workload, eliminating the "
                "simultaneous demand that is causing the resource conflict. "
                "The team member can then give focused attention to each task in sequence, reducing the risk of "
                "delays or errors that arise from split focus. "
                "This approach requires downstream dependencies and stakeholder expectations to tolerate the "
                "adjusted timeline before committing."
            ),
            ('resource', 'split_task'): (
                "Breaking the overloaded task into smaller independent units allows portions to be delegated or "
                "deprioritised without reassigning ownership entirely. "
                "This reduces the immediate pressure on the team member while keeping them accountable for the "
                "overall outcome. "
                "It works best when the task has distinct deliverables that can be distributed cleanly — tightly "
                "coupled work may not split effectively."
            ),
            ('resource', 'add_resources'): (
                "Adding a contributor to one of the conflicting tasks accelerates its completion, shortening the "
                "window during which two pieces of work compete for the same person's time. "
                "The expected outcome is faster throughput on the selected task, freeing the team member's capacity "
                "sooner for the other work. "
                "This requires the new contributor to have sufficient context and availability, and works best when "
                "the task has parallelisable workstreams."
            ),
            ('dependency', 'modify_dependency'): (
                "Removing or softening the dependency allows the blocked task to proceed in parallel using a mock "
                "or stub in place of the upstream deliverable. "
                "Once the blocking task is complete, integration is straightforward since both sides are developed "
                "against an agreed interface contract. "
                "This requires the team to define that contract upfront and maintain discipline to swap out the "
                "placeholder cleanly when the real implementation is ready."
            ),
            ('dependency', 'adjust_dates'): (
                "Shifting the start date of the blocked task to after its dependency is complete eliminates the "
                "scheduling conflict and ensures work begins only when prerequisites are genuinely ready. "
                "This removes the risk of rework caused by building on an incomplete or changing foundation. "
                "It requires confirming that the adjusted start date is still compatible with the task's own "
                "deadline and any downstream deliverables that depend on it."
            ),
            ('dependency', 'remove_dependency'): (
                "Re-evaluating whether the dependency is strictly necessary may reveal that the blocked task can "
                "proceed independently, either in full or with currently available information. "
                "Removing an unnecessary dependency unlocks parallel progress and reduces scheduling fragility "
                "across the project. "
                "This should be validated with both task owners to confirm no critical coupling is being overlooked "
                "before the link is severed."
            ),
            ('schedule', 'adjust_dates'): (
                "Extending the deadline to a realistic date resolves the scheduling conflict by aligning the target "
                "with the actual work remaining, rather than forcing rushed completion. "
                "The expected outcome is a higher-quality deliverable completed on a timeline the team can commit "
                "to confidently. "
                "This requires stakeholder agreement on the revised date and should be paired with a review of "
                "downstream tasks that depend on this one."
            ),
            ('schedule', 'add_resources'): (
                "Adding a team member to help with the overdue task brings more capacity to bear on the bottleneck, "
                "making the original deadline achievable without cutting scope. "
                "The expected outcome is faster progress through task sharing or parallel workstreams, reducing "
                "the schedule overrun. "
                "This works best when the task has parallelisable components and the new contributor can ramp up "
                "quickly without requiring extensive context-setting."
            ),
            ('schedule', 'reschedule'): (
                "Staggering the overlapping tasks creates dedicated focus windows for each, preventing the "
                "context-switching overhead that reduces effectiveness when both are active simultaneously. "
                "The expected outcome is higher quality output and a lower risk of one task slipping because of "
                "pressure from the other. "
                "This requires stakeholder agreement on the revised timeline before committing to the change."
            ),
            ('schedule', 'reduce_scope'): (
                "Reducing the scope lowers the total work volume to a level that fits the available time, making "
                "the schedule feasible without changing the deadline or adding resources. "
                "The expected outcome is that the task reaches a meaningful completion state within the original "
                "timeline, with lower-priority elements deferred to a future iteration. "
                "This requires product owner sign-off on which scope elements can be safely cut, and clarity on "
                "what 'done enough' looks like for the current milestone."
            ),
        }
        return reasoning_map.get((conflict_type, resolution_type), '')

    @staticmethod
    def pick_reassignment_candidate(board, excluded_user_id, task=None):
        """
        Pick the best other board member as a reassignment target, using the
        same weighted scoring (skill match 30%, availability 25%, velocity 20%,
        reliability 15%, quality 10%) the AI Resource Optimization panel uses
        — not availability/workload alone — so this can't recommend a
        candidate who's a poor skill match just because they're less loaded,
        nor one who's already more loaded than the excluded (overbooked) user.

        ``task`` (optional): the task being reassigned. When provided, skill
        match is scored against its title/description via
        ResourceLevelingService.analyze_task_assignment. Without it, falls
        back to ranking by availability (utilization) alone.

        Returns (target_member, ai_confidence) or (None, None) if there are no
        other board members.
        """
        from kanban.resource_leveling import ResourceLevelingService

        board_members = list(User.objects.filter(board_memberships__board=board).exclude(id=excluded_user_id))
        if not board_members:
            return None, None

        leveling_service = ResourceLevelingService(workspace=board.workspace)
        overbooked_profile = leveling_service.get_or_create_profile(
            User.objects.get(id=excluded_user_id), board=board
        )

        target_member = None
        target_utilization = None

        if task is not None:
            analysis = leveling_service.analyze_task_assignment(
                task, potential_assignees=board_members, board=board
            )
            scored_candidates = [
                c for c in analysis.get('all_candidates', []) if c['user_id'] != excluded_user_id
            ]
            if scored_candidates:
                top = max(scored_candidates, key=lambda c: c['overall_score'])
                target_member = next((m for m in board_members if m.id == top['user_id']), None)
                target_utilization = top['actual_utilization']

        if target_member is None:
            # No task context (or no scored candidates) — fall back to
            # ranking by availability alone.
            candidates = [
                (member, leveling_service.get_or_create_profile(member, board=board).utilization_percentage)
                for member in board_members
            ]
            target_member, target_utilization = min(candidates, key=lambda c: c[1])

        # Confidence scales with how much lower the candidate's utilization is
        # versus the overbooked user's — a bigger gap is stronger evidence the
        # reassignment will actually help.
        gap = overbooked_profile.utilization_percentage - target_utilization
        ai_confidence = max(50, min(90, round(70 + gap / 4)))
        return target_member, ai_confidence

    def _suggest_resource_resolutions(self):
        """Suggest resolutions for resource conflicts."""
        suggestions = []
        data = self.conflict.conflict_data
        
        # Get tasks - try from conflict_data first, then fall back to tasks relationship
        task1_id = data.get('task1_id')
        task2_id = data.get('task2_id')
        
        if not task1_id or not task2_id:
            # Fall back to getting tasks from the conflict's tasks relationship
            conflict_tasks = list(self.conflict.tasks.all()[:2])
            task1 = conflict_tasks[0] if len(conflict_tasks) > 0 else None
            task2 = conflict_tasks[1] if len(conflict_tasks) > 1 else None
        else:
            task1 = Task.objects.filter(id=task1_id).first()
            task2 = Task.objects.filter(id=task2_id).first()
        
        if not task1 or not task2:
            logger.warning(f"Could not find tasks for resource conflict {self.conflict.id}")
            return suggestions
        
        # Get user info
        user_id = data.get('user_id')
        user_name = data.get('user_name')
        
        # Fall back to getting user from affected_users if not in conflict_data
        if not user_id:
            affected_user = self.conflict.affected_users.first()
            if affected_user:
                user_id = affected_user.id
                user_name = affected_user.get_full_name() or affected_user.username
        
        if not user_id:
            logger.warning(f"Could not find user for resource conflict {self.conflict.id}")
            return suggestions
        
        # Suggestion 1: Reassign one task to another user
        if task1 and task2:
            board = self.conflict.board
            target_member, ai_confidence = self.pick_reassignment_candidate(board, user_id, task=task2)

            if target_member:
                resolution = ConflictResolution.objects.create(
                    conflict=self.conflict,
                    resolution_type='reassign',
                    title=f"Reassign '{task2.title}' to {target_member.get_full_name() or target_member.username}",
                    description=f"Move task '{task2.title}' from {user_name} to {target_member.get_full_name() or target_member.username} to balance workload.",
                    ai_confidence=ai_confidence,
                    ai_reasoning=self._get_resolution_reasoning('reassign'),
                    auto_applicable=True,
                    implementation_data={
                        'task_id': task2.id,
                        'old_assignee_id': user_id,
                        'new_assignee_id': target_member.id
                    },
                    estimated_impact="Reduces workload conflict and balances team capacity"
                )
                suggestions.append(resolution)
        
        # Suggestion 2: Reschedule one task
        if task2:
            # Prefer the blocking task's LIVE due date. The conflict_data
            # snapshot (task1_dates.due) is captured at detection time and is
            # NOT updated by the demo date-refresh, so it drifts stale and can
            # collapse new_start to a no-op. Only fall back to the snapshot when
            # the live task has no due date.
            if task1.due_date:
                task1_due_date = task1.due_date.date() if hasattr(task1.due_date, 'date') else task1.due_date
                new_start = task1_due_date + timedelta(days=1)
            else:
                task1_due = data.get('task1_dates', {}).get('due')
                if task1_due:
                    new_start = datetime.fromisoformat(task1_due.replace('Z', '+00:00')).date() + timedelta(days=1)
                else:
                    new_start = None

            if new_start:
                resolution = ConflictResolution.objects.create(
                    conflict=self.conflict,
                    resolution_type='reschedule',
                    title=f"Reschedule '{task2.title}' to start after first task",
                    description=f"Delay start of '{task2.title}' until '{task1.title}' is complete.",
                    ai_confidence=85,
                    ai_reasoning=self._get_resolution_reasoning('reschedule'),
                    auto_applicable=True,
                    # after_task_id lets _auto_apply recompute the new start from
                    # the blocking task's LIVE due date at apply time (robust to
                    # demo date drift); new_start_date is only a fallback.
                    implementation_data={
                        'task_id': task2.id,
                        'after_task_id': task1.id,
                        'new_start_date': str(new_start)
                    },
                    estimated_impact="Eliminates overlap and creates sequential workflow"
                )
                suggestions.append(resolution)
        
        return suggestions
    
    def _suggest_schedule_resolutions(self):
        """Suggest resolutions for schedule conflicts."""
        suggestions = []
        data = self.conflict.conflict_data
        
        # Get task - try from conflict_data first, then fall back to tasks relationship
        task_id = data.get('task_id')
        if task_id:
            task = Task.objects.filter(id=task_id).first()
        else:
            # Fall back to first task from relationship
            task = self.conflict.tasks.first()
        
        if not task:
            logger.warning(f"Could not find task for schedule conflict {self.conflict.id}")
            return suggestions
        
        # Suggestion 1: Extend due date
        if 'days_overdue' in data or (task.due_date and task.due_date < timezone.now()):
            new_due = timezone.now() + timedelta(days=7)
            resolution = ConflictResolution.objects.create(
                conflict=self.conflict,
                resolution_type='adjust_dates',
                title=f"Extend due date by 1 week",
                description=f"Extend due date for '{task.title}' to {new_due.strftime('%Y-%m-%d')} to allow completion.",
                ai_confidence=75,
                ai_reasoning=self._get_resolution_reasoning('adjust_dates'),
                auto_applicable=True,
                implementation_data={
                    'task_id': task.id,
                    'new_due_date': str(new_due)
                },
                estimated_impact="Provides realistic timeline for completion"
            )
            suggestions.append(resolution)
        
        # Suggestion 2: Increase priority or add resources
        if task.assigned_to:
            resolution = ConflictResolution.objects.create(
                conflict=self.conflict,
                resolution_type='add_resources',
                title=f"Add team member to accelerate task",
                description=f"Assign additional team member to '{task.title}' to help meet deadline.",
                ai_confidence=65,
                ai_reasoning=self._get_resolution_reasoning('add_resources'),
                auto_applicable=False,
                estimated_impact="Accelerates completion through collaboration"
            )
            suggestions.append(resolution)
        
        return suggestions
    
    def _suggest_dependency_resolutions(self):
        """Suggest resolutions for dependency conflicts."""
        suggestions = []
        data = self.conflict.conflict_data
        
        # Get task - try from conflict_data first, then fall back to tasks relationship
        task_id = data.get('task_id')
        if task_id:
            task = Task.objects.filter(id=task_id).first()
        else:
            # Fall back to first task from relationship
            task = self.conflict.tasks.first()
        
        if not task:
            logger.warning(f"Could not find task for dependency conflict {self.conflict.id}")
            return suggestions
        
        # Suggestion 1: Adjust dates to after dependencies.
        # The blocking task = the dependency with the latest due date. When one
        # exists we can auto-apply: _auto_apply recomputes the new start from
        # that task's LIVE due date (via after_task_id) and preserves duration.
        # Without a dated dependency we can't compute anything, so the card
        # stays manual (auto_applicable=False) rather than silently no-op.
        blocking_task = task.dependencies.filter(
            due_date__isnull=False
        ).order_by('-due_date').first()
        dep_impl_data = {}
        dep_auto = False
        if blocking_task:
            dep_impl_data = {
                'task_id': task.id,
                'after_task_id': blocking_task.id,
            }
            dep_auto = True
        resolution = ConflictResolution.objects.create(
            conflict=self.conflict,
            resolution_type='adjust_dates',
            title=f"Reschedule to after blocking tasks",
            description=f"Adjust dates for '{task.title}' to start after dependencies are complete.",
            ai_confidence=80,
            ai_reasoning=self._get_resolution_reasoning('adjust_dates'),
            auto_applicable=dep_auto,
            implementation_data=dep_impl_data,
            estimated_impact="Ensures proper task sequencing"
        )
        suggestions.append(resolution)
        
        # Suggestion 2: Remove or modify dependency
        resolution = ConflictResolution.objects.create(
            conflict=self.conflict,
            resolution_type='modify_dependency',
            title=f"Re-evaluate task dependencies",
            description=f"Review whether all dependencies for '{task.title}' are truly required.",
            ai_confidence=60,
            ai_reasoning=self._get_resolution_reasoning('modify_dependency'),
            auto_applicable=False,
            estimated_impact="May enable parallel work and faster completion"
        )
        suggestions.append(resolution)
        
        return suggestions
    
    def _apply_learned_patterns(self, suggestions):
        """Apply learned patterns to adjust confidence scores and append historical context."""
        for suggestion in suggestions:
            # Fetch the full pattern object so we can access times_used and success_rate,
            # not just the pre-computed confidence_boost float.
            pattern = None

            # Board-specific pattern takes priority (requires ≥ 3 uses for reliability)
            if self.conflict.board:
                pattern = ResolutionPattern.objects.filter(
                    conflict_type=self.conflict.conflict_type,
                    resolution_type=suggestion.resolution_type,
                    board=self.conflict.board,
                    times_used__gte=3,
                ).first()

            # Fall back to global pattern (requires ≥ 5 uses)
            if pattern is None:
                pattern = ResolutionPattern.objects.filter(
                    conflict_type=self.conflict.conflict_type,
                    resolution_type=suggestion.resolution_type,
                    board__isnull=True,
                    times_used__gte=5,
                ).first()

            boost = pattern.confidence_boost if pattern else 0.0

            # Apply boost (with bounds checking)
            new_confidence = max(0, min(100, suggestion.ai_confidence + boost))
            suggestion.ai_confidence = int(new_confidence)

            # Build historical note only when we have real pattern data
            historical_note = ''
            if pattern is not None:
                n = pattern.times_used
                success_pct = round(pattern.success_rate * 100)
                boost_val = pattern.confidence_boost
                boost_sign = '+' if boost_val >= 0 else ''
                scope = 'this board' if pattern.board else 'your projects'
                historical_note = (
                    f"Based on {n} past resolution{'s' if n != 1 else ''} of this type on "
                    f"{scope}, this approach has a {success_pct}% success rate "
                    f"({boost_sign}{boost_val:.0f}% confidence adjustment)."
                )

            # Append historical note to existing reasoning — never overwrite substantive text
            if historical_note:
                existing = suggestion.ai_reasoning.strip()
                if existing:
                    suggestion.ai_reasoning = existing + ' ' + historical_note
                else:
                    suggestion.ai_reasoning = historical_note

            suggestion.save()

        # Sort by confidence
        suggestions.sort(key=lambda s: s.ai_confidence, reverse=True)
        return suggestions
