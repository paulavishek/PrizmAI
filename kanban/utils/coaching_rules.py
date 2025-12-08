"""
AI Coach Rule Engine

Detects patterns and situations that warrant coaching suggestions
Proactive detection of common PM challenges
"""

import logging
from datetime import datetime, timedelta, date
from decimal import Decimal
from typing import List, Dict, Optional
from django.db.models import Count, Avg, Q, Sum
from django.utils import timezone

logger = logging.getLogger(__name__)


class CoachingRuleEngine:
    """
    Rule-based system for detecting coaching opportunities
    Analyzes project metrics and patterns to generate proactive suggestions
    """
    
    def __init__(self, board):
        """
        Initialize rule engine for a specific board
        
        Args:
            board: Board object to analyze
        """
        self.board = board
        self.suggestions = []
    
    def analyze_and_generate_suggestions(self) -> List[Dict]:
        """
        Run all rule checks and generate suggestions
        
        Returns:
            List of suggestion dictionaries ready to create CoachingSuggestion objects
        """
        self.suggestions = []
        
        # Run all detection rules
        self._check_velocity_drop()
        self._check_resource_overload()
        self._check_risk_convergence()
        self._check_skill_development_opportunities()
        self._check_scope_creep()
        self._check_deadline_risk()
        self._check_team_burnout()
        self._check_quality_issues()
        self._check_dependency_blockers()
        self._check_communication_gaps()
        
        logger.info(f"Generated {len(self.suggestions)} suggestions for board {self.board.name}")
        return self.suggestions
    
    def _add_suggestion(self, suggestion_type: str, severity: str, title: str, 
                       message: str, reasoning: str, recommended_actions: List[str],
                       expected_impact: str, metrics_snapshot: Dict, 
                       confidence_score: float = 0.75, task=None):
        """Helper to add a suggestion to the list"""
        self.suggestions.append({
            'board': self.board,
            'task': task,
            'suggestion_type': suggestion_type,
            'severity': severity,
            'title': title,
            'message': message,
            'reasoning': reasoning,
            'recommended_actions': recommended_actions,
            'expected_impact': expected_impact,
            'metrics_snapshot': metrics_snapshot,
            'confidence_score': Decimal(str(confidence_score)),
            'ai_model_used': 'rule-engine',
            'generation_method': 'rule',
            'expires_at': timezone.now() + timedelta(days=7),  # Suggestions expire in 7 days
        })
    
    def _check_velocity_drop(self):
        """Detect significant velocity drops"""
        from kanban.burndown_models import TeamVelocitySnapshot
        
        # Get recent velocity snapshots
        snapshots = TeamVelocitySnapshot.objects.filter(
            board=self.board
        ).order_by('-period_end')[:4]
        
        if snapshots.count() < 3:
            return  # Need at least 3 data points
        
        snapshots_list = list(snapshots)
        latest = snapshots_list[0]
        previous = snapshots_list[1:3]
        
        avg_previous = sum(s.tasks_completed if s.tasks_completed is not None else 0 for s in previous) / len(previous)
        latest_completed = latest.tasks_completed if latest.tasks_completed is not None else 0
        
        if avg_previous == 0:
            return
        
        drop_percentage = ((avg_previous - latest_completed) / avg_previous) * 100
        
        if drop_percentage > 30:
            # Significant drop detected
            self._add_suggestion(
                suggestion_type='velocity_drop',
                severity='high',
                title=f"Team velocity dropped by {drop_percentage:.0f}%",
                message=f"Your team's velocity has significantly decreased from an average of "
                       f"{avg_previous:.1f} tasks/week to {latest_completed} tasks/week. "
                       f"This suggests potential blockers or team capacity issues.",
                reasoning=f"Velocity dropped from {avg_previous:.1f} to {latest_completed} "
                         f"({drop_percentage:.0f}% decrease) over the past period.",
                recommended_actions=[
                    "Schedule 1-on-1 check-ins with team members to identify blockers",
                    "Review current workload distribution across the team",
                    "Identify and remove impediments blocking task completion",
                    "Consider reducing work-in-progress to improve focus",
                    "Check if team members need additional support or resources"
                ],
                expected_impact="Addressing velocity drops early can prevent project delays and "
                              "help identify systemic issues before they compound.",
                metrics_snapshot={
                    'current_velocity': latest_completed,
                    'avg_previous_velocity': float(avg_previous),
                    'drop_percentage': float(drop_percentage),
                    'period': f"{latest.period_start} to {latest.period_end}"
                },
                confidence_score=0.85
            )
        elif drop_percentage > 15:
            # Moderate drop - warning
            self._add_suggestion(
                suggestion_type='velocity_drop',
                severity='medium',
                title=f"Team velocity declining ({drop_percentage:.0f}% drop)",
                message=f"Your team's velocity has decreased by {drop_percentage:.0f}%. "
                       f"This is worth monitoring to prevent further decline.",
                reasoning=f"Velocity dropped from {avg_previous:.1f} to {latest_completed}.",
                recommended_actions=[
                    "Monitor velocity trend over the next sprint",
                    "Ask team about any emerging challenges or blockers",
                    "Review task complexity - are estimates accurate?"
                ],
                expected_impact="Early intervention can prevent minor slowdowns from becoming major issues.",
                metrics_snapshot={
                    'current_velocity': latest_completed,
                    'avg_previous_velocity': float(avg_previous),
                    'drop_percentage': float(drop_percentage)
                },
                confidence_score=0.75
            )
    
    def _check_resource_overload(self):
        """Detect team members with excessive workload"""
        from kanban.models import Task
        
        # Get active tasks per team member
        team_workload = Task.objects.filter(
            column__board=self.board,
            progress__isnull=False,
            progress__lt=100
        ).values('assigned_to__username', 'assigned_to__id').annotate(
            active_tasks=Count('id'),
            high_priority_tasks=Count('id', filter=Q(priority='high'))
        ).filter(assigned_to__isnull=False)
        
        for member in team_workload:
            active = member['active_tasks']
            high_priority = member['high_priority_tasks']
            
            if active > 10 or high_priority > 5:
                severity = 'high' if active > 15 or high_priority > 7 else 'medium'
                
                self._add_suggestion(
                    suggestion_type='resource_overload',
                    severity=severity,
                    title=f"{member['assigned_to__username']} is overloaded",
                    message=f"{member['assigned_to__username']} has {active} active tasks "
                           f"(including {high_priority} high priority). This may lead to burnout "
                           f"and reduced quality.",
                    reasoning=f"Team member has {active} concurrent tasks, exceeding recommended "
                             f"limit of 8-10 tasks for optimal focus and quality.",
                    recommended_actions=[
                        f"Meet with {member['assigned_to__username']} to prioritize work",
                        "Redistribute lower-priority tasks to other team members",
                        "Consider extending deadlines for non-critical items",
                        "Identify tasks that can be deferred or delegated",
                        "Ensure the team member isn't blocked on dependencies"
                    ],
                    expected_impact="Reducing overload improves quality, reduces burnout risk, "
                                  "and helps team members focus on high-impact work.",
                    metrics_snapshot={
                        'username': member['assigned_to__username'],
                        'active_tasks': active,
                        'high_priority_tasks': high_priority,
                        'recommended_max': 10
                    },
                    confidence_score=0.90
                )
    
    def _check_risk_convergence(self):
        """Detect multiple high-risk tasks converging in time"""
        from kanban.models import Task
        
        # Get high-risk tasks with deadlines in next 2 weeks
        two_weeks = date.today() + timedelta(days=14)
        
        high_risk_tasks = Task.objects.filter(
            column__board=self.board,
            progress__isnull=False,
            progress__lt=100,
            risk_level__in=['high', 'critical'],
            due_date__isnull=False,
            due_date__lte=two_weeks
        ).order_by('due_date')
        
        # Group by week
        from collections import defaultdict
        weeks = defaultdict(list)
        
        for task in high_risk_tasks:
            week_start = task.due_date - timedelta(days=task.due_date.weekday())
            weeks[week_start].append(task)
        
        # Check for weeks with 3+ high-risk tasks
        for week_start, tasks in weeks.items():
            if len(tasks) >= 3:
                task_titles = [t.title for t in tasks[:5]]
                
                self._add_suggestion(
                    suggestion_type='risk_convergence',
                    severity='critical',
                    title=f"{len(tasks)} high-risk tasks converging in same week",
                    message=f"You have {len(tasks)} high-risk tasks all due the week of "
                           f"{week_start.strftime('%B %d')}. This creates compounding risk "
                           f"and puts significant pressure on the team.",
                    reasoning=f"Multiple high-risk items converging in a short time window "
                             f"increases probability of cascading failures and team stress.",
                    recommended_actions=[
                        "Create explicit risk mitigation plan for this week",
                        "Consider staggering deadlines if possible",
                        "Identify which tasks can start early to reduce crunch",
                        "Assign backup resources for critical tasks",
                        "Schedule daily stand-ups during this high-risk period",
                        "Communicate timeline risks to stakeholders now"
                    ],
                    expected_impact="Proactive risk planning can prevent crisis situations and "
                                  "improve team's ability to handle complex work periods.",
                    metrics_snapshot={
                        'week_start': week_start.isoformat(),
                        'high_risk_task_count': len(tasks),
                        'task_titles': task_titles
                    },
                    confidence_score=0.95
                )
    
    def _check_skill_development_opportunities(self):
        """Identify opportunities for skill development based on task assignments"""
        from kanban.models import Task
        from accounts.models import UserProfile
        
        # Get team members with their skill profiles
        team_members = self.board.members.select_related('profile').all()
        
        for member in team_members:
            try:
                profile = member.profile
                
                # Check if member has skills that are developing
                developing_skills = []
                for skill, level in profile.skills.items():
                    if level in ['learning', 'beginner', 'intermediate']:
                        developing_skills.append(skill)
                
                if not developing_skills:
                    continue
                
                # Find tasks matching developing skills
                member_tasks = Task.objects.filter(
                    column__board=self.board,
                    assigned_to=member,
                    progress__isnull=False,
                    progress__lt=100
                )
                
                # Check task count and complexity
                task_count = member_tasks.count()
                avg_complexity = member_tasks.aggregate(Avg('complexity_score'))['complexity_score__avg'] or 5
                
                # If member has capacity and skills to develop, suggest challenging assignments
                if task_count < 6 and developing_skills:
                    self._add_suggestion(
                        suggestion_type='skill_opportunity',
                        severity='low',
                        title=f"Skill development opportunity for {member.username}",
                        message=f"{member.username} is developing skills in {', '.join(developing_skills[:3])} "
                               f"and has capacity for more challenging work (current: {task_count} tasks, "
                               f"avg complexity: {avg_complexity:.1f}/10).",
                        reasoning=f"Team member is actively building skills and has workload capacity. "
                                 f"Assigning appropriate stretch assignments accelerates growth.",
                        recommended_actions=[
                            f"Assign tasks involving {developing_skills[0]} to help build expertise",
                            "Pair with senior team member for mentoring on complex tasks",
                            "Consider tasks one complexity level above their current average",
                            "Provide regular feedback on skill development progress"
                        ],
                        expected_impact="Strategic skill development improves team capability, increases "
                                      "member engagement, and builds stronger bench strength.",
                        metrics_snapshot={
                            'username': member.username,
                            'developing_skills': developing_skills,
                            'current_tasks': task_count,
                            'avg_complexity': float(avg_complexity)
                        },
                        confidence_score=0.70
                    )
            except Exception as e:
                logger.debug(f"Could not analyze skill development for {member.username}: {e}")
                continue
    
    def _check_scope_creep(self):
        """Detect scope creep patterns"""
        from kanban.models import ScopeChangeSnapshot
        
        # Get recent scope snapshots
        recent_snapshot = ScopeChangeSnapshot.objects.filter(
            board=self.board
        ).order_by('-snapshot_date').first()
        
        if not recent_snapshot:
            return
        
        # Check for significant scope increases
        scope_change = recent_snapshot.scope_change_percentage if recent_snapshot.scope_change_percentage is not None else 0
        
        # Calculate tasks and complexity added from baseline
        tasks_added = 0
        complexity_added = 0
        if recent_snapshot.baseline_snapshot:
            tasks_added = recent_snapshot.total_tasks - recent_snapshot.baseline_snapshot.total_tasks
            complexity_added = recent_snapshot.total_complexity_points - recent_snapshot.baseline_snapshot.total_complexity_points
        
        if scope_change > 15:
            severity = 'high' if scope_change > 25 else 'medium'
            
            self._add_suggestion(
                suggestion_type='scope_creep',
                severity=severity,
                title=f"Scope increased by {scope_change:.0f}%",
                message=f"Your project scope has grown by {scope_change:.0f}% "
                       f"({tasks_added} new tasks, {complexity_added:.0f} "
                       f"complexity points added). This may impact your timeline and team capacity.",
                reasoning=f"Scope creep of this magnitude typically delays projects and can lead "
                         f"to missed deadlines if not managed proactively.",
                recommended_actions=[
                    "Review newly added tasks - are they all truly necessary for this release?",
                    "Consider moving lower-priority additions to next sprint/phase",
                    "Communicate timeline impact to stakeholders",
                    "Implement stricter change control process",
                    "Update project timeline based on new scope"
                ],
                expected_impact="Managing scope creep prevents timeline slips and helps maintain "
                              "team focus on highest-priority work.",
                metrics_snapshot={
                    'scope_change_percentage': float(scope_change),
                    'tasks_added': tasks_added,
                    'complexity_added': float(complexity_added),
                    'snapshot_date': recent_snapshot.snapshot_date.isoformat()
                },
                confidence_score=0.85
            )
    
    def _check_deadline_risk(self):
        """Check if project deadlines are at risk based on burndown predictions"""
        from kanban.burndown_models import BurndownPrediction
        
        # Get latest prediction
        latest_prediction = BurndownPrediction.objects.filter(
            board=self.board
        ).order_by('-prediction_date').first()
        
        if not latest_prediction or not latest_prediction.target_completion_date:
            return
        
        # Check if we're at risk of missing deadline
        delay_prob = latest_prediction.delay_probability if latest_prediction.delay_probability is not None else 0
        days_behind = latest_prediction.days_ahead_behind_target if latest_prediction.days_ahead_behind_target is not None else 0
        current_vel = latest_prediction.current_velocity if latest_prediction.current_velocity is not None else 0
        remaining = latest_prediction.remaining_tasks if latest_prediction.remaining_tasks is not None else 0
        
        if latest_prediction.will_meet_target == False and delay_prob > 30:
            self._add_suggestion(
                suggestion_type='deadline_risk',
                severity='critical',
                title=f"{delay_prob:.0f}% chance of missing deadline",
                message=f"Current projections show {delay_prob:.0f}% probability "
                       f"of missing your target date ({latest_prediction.target_completion_date.strftime('%B %d, %Y')}). "
                       f"You're estimated to finish {abs(days_behind)} days late.",
                reasoning=f"Based on current velocity ({current_vel} tasks/week) "
                         f"and remaining work ({remaining} tasks), deadline is at risk.",
                recommended_actions=[
                    "Review and cut scope - what can move to next phase?",
                    "Add resources if budget allows",
                    "Identify and eliminate team blockers",
                    "Communicate timeline risk to stakeholders immediately",
                    "Consider reducing task scope/complexity where possible"
                ],
                expected_impact="Early escalation and corrective action can help recover timeline "
                              "or reset stakeholder expectations before it's too late.",
                metrics_snapshot={
                    'delay_probability': float(delay_prob),
                    'days_behind': abs(days_behind),
                    'target_date': latest_prediction.target_completion_date.isoformat(),
                    'remaining_tasks': remaining,
                    'current_velocity': float(current_vel)
                },
                confidence_score=0.90
            )
    
    def _check_team_burnout(self):
        """Detect signs of team burnout"""
        from kanban.burndown_models import TeamVelocitySnapshot
        
        # Check for declining velocity AND increasing work hours
        recent_snapshots = TeamVelocitySnapshot.objects.filter(
            board=self.board
        ).order_by('-period_end')[:4]
        
        if recent_snapshots.count() < 3:
            return
        
        snapshots_list = list(recent_snapshots)
        
        # Check velocity trend
        velocities = [s.tasks_completed if s.tasks_completed is not None else 0 for s in snapshots_list]
        if len(velocities) >= 3:
            # Simple trend check: are we declining?
            recent_avg = sum(velocities[:2]) / 2
            older_avg = sum(velocities[2:]) / len(velocities[2:])
            
            if older_avg > 0 and recent_avg < older_avg * 0.85:
                # Also check quality score
                latest = snapshots_list[0]
                if latest.quality_score is not None and latest.quality_score < 90:
                    self._add_suggestion(
                        suggestion_type='team_burnout',
                        severity='high',
                        title="Potential team burnout detected",
                        message=f"Your team's velocity is declining AND quality score has dropped to "
                               f"{latest.quality_score:.0f}/100. These are common signs of burnout or "
                               f"sustained overwork.",
                        reasoning=f"Velocity dropped from {older_avg:.1f} to {recent_avg:.1f} while "
                                 f"quality metrics declined, suggesting team is struggling.",
                        recommended_actions=[
                            "Schedule team check-in to discuss workload and stress levels",
                            "Consider lightening sprint commitments temporarily",
                            "Ensure team is taking breaks and time off",
                            "Review work-life balance indicators",
                            "Address any toxic team dynamics or pressure sources",
                            "Celebrate wins to boost morale"
                        ],
                        expected_impact="Addressing burnout early preserves team health, prevents turnover, "
                                      "and maintains sustainable productivity.",
                        metrics_snapshot={
                            'velocity_decline': float((older_avg - recent_avg) / older_avg * 100),
                            'quality_score': float(latest.quality_score),
                            'recent_velocity': float(recent_avg),
                            'previous_velocity': float(older_avg)
                        },
                        confidence_score=0.80
                    )
    
    def _check_quality_issues(self):
        """Detect quality degradation"""
        from kanban.burndown_models import TeamVelocitySnapshot
        
        latest = TeamVelocitySnapshot.objects.filter(
            board=self.board
        ).order_by('-period_end').first()
        
        if not latest:
            return
        
        if latest.quality_score is not None and latest.quality_score < 85:
            severity = 'high' if latest.quality_score < 75 else 'medium'
            tasks_reopened = latest.tasks_reopened if latest.tasks_reopened is not None else 0
            
            self._add_suggestion(
                suggestion_type='quality_issue',
                severity=severity,
                title=f"Quality score dropped to {latest.quality_score:.0f}/100",
                message=f"Your team's quality score is {latest.quality_score:.0f}/100, indicating "
                       f"an unusual number of tasks being reopened or rejected. This suggests "
                       f"potential quality issues.",
                reasoning=f"{tasks_reopened} tasks were reopened in the recent period, "
                         f"affecting overall quality metrics.",
                recommended_actions=[
                    "Review why tasks are being reopened - definition of done clear?",
                    "Consider adding peer reviews or QA checkpoints",
                    "Check if team is rushing due to deadline pressure",
                    "Verify acceptance criteria are well-defined",
                    "Ensure team has adequate time for testing"
                ],
                expected_impact="Improving quality reduces rework, prevents customer issues, "
                              "and improves team morale.",
                metrics_snapshot={
                    'quality_score': float(latest.quality_score),
                    'tasks_reopened': tasks_reopened,
                    'period': f"{latest.period_start} to {latest.period_end}"
                },
                confidence_score=0.85
            )
    
    def _check_dependency_blockers(self):
        """Detect tasks blocked by dependencies"""
        from kanban.models import Task
        
        # Find tasks that have been in same status for > 5 days with dependencies
        stale_threshold = timezone.now() - timedelta(days=5)
        
        potentially_blocked = Task.objects.filter(
            column__board=self.board,
            progress__isnull=False,
            progress__lt=100,
            progress__gt=0,  # Started but not finished
            updated_at__lt=stale_threshold
        ).select_related('column')
        
        if potentially_blocked.count() >= 3:
            task_list = list(potentially_blocked[:5])
            
            self._add_suggestion(
                suggestion_type='dependency_blocker',
                severity='medium',
                title=f"{potentially_blocked.count()} tasks appear stalled",
                message=f"You have {potentially_blocked.count()} tasks that haven't progressed in 5+ days. "
                       f"These may be blocked by dependencies or waiting on external inputs.",
                reasoning=f"Tasks with no recent updates often indicate blocked work that's consuming "
                         f"team capacity without producing value.",
                recommended_actions=[
                    "Review stalled tasks in daily standup",
                    "Identify and resolve blocking dependencies",
                    "Check if tasks need to be reassigned",
                    "Consider moving blocked tasks to 'Blocked' status for visibility",
                    "Reach out to dependencies to expedite their work"
                ],
                expected_impact="Unblocking tasks improves flow, reduces idle time, and helps "
                              "team maintain momentum.",
                metrics_snapshot={
                    'stalled_task_count': potentially_blocked.count(),
                    'sample_tasks': [{'title': t.title, 'days_stalled': (timezone.now() - t.updated_at).days} 
                                    for t in task_list]
                },
                confidence_score=0.70
            )
    
    def _check_communication_gaps(self):
        """Detect potential communication issues"""
        from kanban.models import Task, Comment
        
        # Check for tasks with no comments/updates in last 7 days
        week_ago = timezone.now() - timedelta(days=7)
        
        active_tasks = Task.objects.filter(
            column__board=self.board,
            progress__isnull=False,
            progress__gt=0,
            progress__lt=100,
            created_at__lt=week_ago
        )
        
        # Check which tasks have no recent comments
        tasks_without_updates = []
        for task in active_tasks:
            recent_comments = Comment.objects.filter(
                task=task,
                created_at__gte=week_ago
            ).count()
            
            if recent_comments == 0 and (timezone.now() - task.updated_at).days >= 7:
                tasks_without_updates.append(task)
        
        if len(tasks_without_updates) >= 5:
            self._add_suggestion(
                suggestion_type='communication_gap',
                severity='medium',
                title=f"{len(tasks_without_updates)} tasks lack recent updates",
                message=f"You have {len(tasks_without_updates)} active tasks with no comments or updates "
                       f"in the past week. This might indicate communication gaps or orphaned work.",
                reasoning=f"Regular updates and communication are key to project visibility and "
                         f"team coordination. Silent tasks often hide problems.",
                recommended_actions=[
                    "Require daily/weekly status updates on active tasks",
                    "Check if assignees need help or clarification",
                    "Ensure team knows to update task status regularly",
                    "Consider implementing daily standups if not already doing so",
                    "Review task assignments - are they still relevant?"
                ],
                expected_impact="Better communication prevents surprises, improves coordination, "
                              "and helps catch issues early.",
                metrics_snapshot={
                    'tasks_without_updates': len(tasks_without_updates),
                    'threshold_days': 7
                },
                confidence_score=0.65
            )
