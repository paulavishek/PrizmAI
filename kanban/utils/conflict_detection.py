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
            # Only analyze active boards with recent activity
            from django.utils import timezone
            thirty_days_ago = timezone.now() - timedelta(days=30)
            boards = Board.objects.filter(
                columns__tasks__updated_at__gte=thirty_days_ago
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
                        # Check if this conflict already exists and is active
                        existing = ConflictDetection.objects.filter(
                            board=board,
                            conflict_type='resource',
                            status='active',
                            tasks__in=[task1, task2]
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
                            title=f"Resource conflict: {user.get_full_name() or user.username} overbooked",
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
                # Check if conflict already exists
                existing = ConflictDetection.objects.filter(
                    board=board,
                    conflict_type='schedule',
                    status='active',
                    tasks=task
                ).first()
                
                if existing:
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
    
    def _suggest_resource_resolutions(self):
        """Suggest resolutions for resource conflicts."""
        suggestions = []
        data = self.conflict.conflict_data
        
        # Suggestion 1: Reassign one task to another user
        task1 = Task.objects.filter(id=data.get('task1_id')).first()
        task2 = Task.objects.filter(id=data.get('task2_id')).first()
        
        if task1 and task2:
            # Find users with lower workload
            board = self.conflict.board
            board_members = board.members.all()
            
            for member in board_members:
                if member.id != data.get('user_id'):
                    # Suggest reassigning task2 to this member
                    resolution = ConflictResolution.objects.create(
                        conflict=self.conflict,
                        resolution_type='reassign',
                        title=f"Reassign '{task2.title}' to {member.get_full_name() or member.username}",
                        description=f"Move task '{task2.title}' from {data.get('user_name')} to {member.get_full_name() or member.username} to balance workload.",
                        ai_confidence=70,
                        auto_applicable=True,
                        implementation_data={
                            'task_id': task2.id,
                            'old_assignee_id': data.get('user_id'),
                            'new_assignee_id': member.id
                        },
                        estimated_impact="Reduces workload conflict and balances team capacity"
                    )
                    suggestions.append(resolution)
                    break  # Only suggest first available member
        
        # Suggestion 2: Reschedule one task
        if task2:
            task1_due = data.get('task1_dates', {}).get('due')
            if task1_due:
                new_start = datetime.fromisoformat(task1_due.replace('Z', '+00:00')).date() + timedelta(days=1)
                resolution = ConflictResolution.objects.create(
                    conflict=self.conflict,
                    resolution_type='reschedule',
                    title=f"Reschedule '{task2.title}' to start after first task",
                    description=f"Delay start of '{task2.title}' until '{task1.title}' is complete.",
                    ai_confidence=85,
                    auto_applicable=True,
                    implementation_data={
                        'task_id': task2.id,
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
        
        task_id = data.get('task_id')
        task = Task.objects.filter(id=task_id).first()
        
        if not task:
            return suggestions
        
        # Suggestion 1: Extend due date
        if 'days_overdue' in data:
            new_due = timezone.now() + timedelta(days=7)
            resolution = ConflictResolution.objects.create(
                conflict=self.conflict,
                resolution_type='adjust_dates',
                title=f"Extend due date by 1 week",
                description=f"Extend due date for '{task.title}' to {new_due.strftime('%Y-%m-%d')} to allow completion.",
                ai_confidence=75,
                auto_applicable=True,
                implementation_data={
                    'task_id': task_id,
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
                auto_applicable=False,
                estimated_impact="Accelerates completion through collaboration"
            )
            suggestions.append(resolution)
        
        return suggestions
    
    def _suggest_dependency_resolutions(self):
        """Suggest resolutions for dependency conflicts."""
        suggestions = []
        data = self.conflict.conflict_data
        
        task_id = data.get('task_id')
        task = Task.objects.filter(id=task_id).first()
        
        if not task:
            return suggestions
        
        # Suggestion 1: Adjust dates to after dependencies
        resolution = ConflictResolution.objects.create(
            conflict=self.conflict,
            resolution_type='adjust_dates',
            title=f"Reschedule to after blocking tasks",
            description=f"Adjust dates for '{task.title}' to start after dependencies are complete.",
            ai_confidence=80,
            auto_applicable=False,
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
            auto_applicable=False,
            estimated_impact="May enable parallel work and faster completion"
        )
        suggestions.append(resolution)
        
        return suggestions
    
    def _apply_learned_patterns(self, suggestions):
        """Apply learned patterns to adjust confidence scores."""
        for suggestion in suggestions:
            boost = ResolutionPattern.get_confidence_boost(
                self.conflict.conflict_type,
                suggestion.resolution_type,
                self.conflict.board
            )
            
            # Apply boost (with bounds checking)
            new_confidence = max(0, min(100, suggestion.ai_confidence + boost))
            suggestion.ai_confidence = int(new_confidence)
            
            # Add reasoning about learning
            if boost > 0:
                suggestion.ai_reasoning = (
                    f"This resolution type has worked well in the past "
                    f"(+{boost:.0f}% confidence based on team history)."
                )
            elif boost < 0:
                suggestion.ai_reasoning = (
                    f"This resolution type has had mixed results in the past "
                    f"({boost:.0f}% confidence adjustment)."
                )
            
            suggestion.save()
        
        # Sort by confidence
        suggestions.sort(key=lambda s: s.ai_confidence, reverse=True)
        return suggestions
