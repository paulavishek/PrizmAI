"""
AI-Powered Retrospective Generator
Analyzes project data and generates retrospective insights using Gemini AI
"""

import logging
from datetime import datetime, timedelta
from decimal import Decimal
from django.db.models import Avg, Count, Sum, Q, F, Max, Min
from django.utils import timezone
from ai_assistant.utils.ai_clients import GeminiClient

logger = logging.getLogger(__name__)


class RetrospectiveGenerator:
    """
    Generate AI-powered retrospectives from project data
    """
    
    def __init__(self, board, period_start, period_end):
        """
        Initialize retrospective generator
        
        Args:
            board: Board instance
            period_start: Start date of retrospective period
            period_end: End date of retrospective period
        """
        self.board = board
        self.period_start = period_start
        self.period_end = period_end
        self.gemini_client = GeminiClient()
    
    def collect_metrics(self):
        """
        Collect all relevant metrics for the retrospective period
        
        Returns:
            dict: Comprehensive metrics snapshot
        """
        from kanban.models import Task, Comment, TaskActivity
        from kanban.burndown_models import TeamVelocitySnapshot
        from django.utils.timezone import make_aware
        from datetime import datetime, time
        
        # Convert dates to timezone-aware datetime objects for proper comparison
        period_start_dt = make_aware(datetime.combine(self.period_start, time.min))
        period_end_dt = make_aware(datetime.combine(self.period_end, time.max))
        
        # Get tasks that were ACTIVE during the period (created before or during, and not completed before period start)
        # This is more useful for retrospectives than just tasks created during the period
        tasks = Task.objects.filter(
            column__board=self.board,
            created_at__lte=period_end_dt
        ).exclude(
            # Exclude tasks that were completed before the period started
            completed_at__lt=period_start_dt
        )
        
        # Detect "done"-type columns by name (case-insensitive) — tasks here count as completed
        from kanban.models import Column as KanbanColumn
        done_column_ids = list(KanbanColumn.objects.filter(
            board=self.board,
            name__iregex=r'(done|completed?|finished|closed)'
        ).values_list('id', flat=True))

        # Get completed tasks: progress=100 OR task is in a done-type column
        completed_tasks = tasks.filter(
            Q(progress=100) |
            Q(column_id__in=done_column_ids)
        ).distinct()
        
        # Calculate metrics
        metrics = {
            # Task metrics
            'total_tasks': tasks.count(),
            'completed_tasks': completed_tasks.count(),
            'in_progress_tasks': tasks.filter(progress__isnull=False, progress__gt=0, progress__lt=100).count(),
            'blocked_tasks': tasks.filter(Q(progress=0) | Q(progress__isnull=True)).count(),
            
            # Completion rate
            'completion_rate': (completed_tasks.count() / tasks.count() * 100) if tasks.count() > 0 else 0,
            
            # Complexity metrics
            'total_complexity': tasks.aggregate(Sum('complexity_score'))['complexity_score__sum'] or 0,
            'completed_complexity': completed_tasks.aggregate(Sum('complexity_score'))['complexity_score__sum'] or 0,
            'avg_complexity': tasks.aggregate(Avg('complexity_score'))['complexity_score__avg'] or 0,
            
            # Priority distribution
            'high_priority_tasks': tasks.filter(priority__in=['high', 'urgent']).count(),
            'urgent_tasks': tasks.filter(priority='urgent').count(),
            
            # Time metrics — use actual_duration_days where set, fallback to created_at → completed_at diff
            'avg_completion_time': self._calculate_avg_completion_time(completed_tasks),
            'overdue_tasks': tasks.filter(
                due_date__lt=timezone.now(),
                progress__lt=100
            ).count() if tasks.exists() else 0,
            
            # Quality indicators
            'tasks_with_comments': tasks.annotate(
                comment_count=Count('comments')
            ).filter(comment_count__gt=0).count(),
            'avg_comments_per_task': tasks.aggregate(
                avg=Avg('comments__id', distinct=True)
            )['avg'] or 0,
            
            # Risk metrics
            'high_risk_tasks': tasks.filter(
                Q(risk_level__in=['high', 'critical']) | Q(ai_risk_score__gte=70)
            ).count(),
            'tasks_with_dependencies': tasks.filter(dependencies__isnull=False).count(),
            
            # Activity level
            'total_activities': TaskActivity.objects.filter(
                task__in=tasks,
                created_at__range=(period_start_dt, period_end_dt)
            ).count(),
            
            # Team metrics
            'active_team_members': tasks.values('assigned_to').distinct().count(),
            'unassigned_tasks': tasks.filter(assigned_to__isnull=True).count(),
        }
        
        # Velocity data
        velocity_snapshots = TeamVelocitySnapshot.objects.filter(
            board=self.board,
            period_start__gte=self.period_start,
            period_end__lte=self.period_end
        )
        
        if velocity_snapshots.exists():
            metrics['avg_velocity'] = velocity_snapshots.aggregate(
                Avg('tasks_completed')
            )['tasks_completed__avg'] or 0
            metrics['velocity_trend'] = self._calculate_velocity_trend(velocity_snapshots)
        else:
            metrics['avg_velocity'] = 0
            metrics['velocity_trend'] = 'insufficient_data'
        
        # Scope creep indicators
        from kanban.models import ScopeChangeSnapshot
        scope_snapshots = ScopeChangeSnapshot.objects.filter(
            board=self.board,
            snapshot_date__range=(period_start_dt, period_end_dt)
        ).order_by('snapshot_date')
        
        if scope_snapshots.count() >= 2:
            first_snapshot = scope_snapshots.first()
            last_snapshot = scope_snapshots.last()
            metrics['scope_change_percentage'] = (
                ((last_snapshot.total_tasks - first_snapshot.total_tasks) / first_snapshot.total_tasks * 100)
                if first_snapshot.total_tasks > 0 else 0
            )
        else:
            metrics['scope_change_percentage'] = 0
        
        return metrics
    
    def _calculate_avg_completion_time(self, completed_tasks):
        """Calculate average completion time; try actual_duration_days first, fallback to date diff."""
        avg = completed_tasks.filter(
            actual_duration_days__isnull=False,
            actual_duration_days__gt=0
        ).aggregate(Avg('actual_duration_days'))['actual_duration_days__avg']
        if avg:
            return round(float(avg), 2)

        # Fallback: compute from completed_at - created_at
        task_dates = list(completed_tasks.filter(
            completed_at__isnull=False
        ).values_list('created_at', 'completed_at'))
        if task_dates:
            durations = [
                max(0.5, (ct - ca).total_seconds() / 86400)
                for ca, ct in task_dates
            ]
            return round(sum(durations) / len(durations), 2)
        return 0

    def _get_board_members_with_workload(self):
        """Return a list of board members with their current open-task count."""
        from kanban.models import Task
        members = []
        board_users = list(self.board.members.all())
        # Always include the board creator
        creator = self.board.created_by
        if not any(u.id == creator.id for u in board_users):
            board_users.append(creator)

        for member in board_users:
            open_tasks = Task.objects.filter(
                column__board=self.board,
                assigned_to=member,
                progress__lt=100
            ).count()
            members.append({
                'username': member.username,
                'full_name': member.get_full_name() or member.username,
                'open_tasks': open_tasks,
            })
        return members

    def _calculate_velocity_trend(self, velocity_snapshots):
        """Calculate velocity trend from snapshots"""
        snapshots_list = list(velocity_snapshots.order_by('period_end'))
        
        if len(snapshots_list) < 2:
            return 'insufficient_data'
        
        # Compare first half vs second half
        mid_point = len(snapshots_list) // 2
        first_half_avg = sum(s.tasks_completed for s in snapshots_list[:mid_point]) / mid_point
        second_half_avg = sum(s.tasks_completed for s in snapshots_list[mid_point:]) / (len(snapshots_list) - mid_point)
        
        change_percentage = ((second_half_avg - first_half_avg) / first_half_avg * 100) if first_half_avg > 0 else 0
        
        if change_percentage > 10:
            return 'increasing'
        elif change_percentage < -10:
            return 'decreasing'
        else:
            return 'stable'
    
    def analyze_task_patterns(self):
        """
        Analyze patterns in task completion, blockers, and issues
        
        Returns:
            dict: Pattern analysis
        """
        from kanban.models import Task
        from django.utils.timezone import make_aware
        from datetime import datetime, time
        
        # Convert dates to timezone-aware datetime objects
        period_start_dt = make_aware(datetime.combine(self.period_start, time.min))
        period_end_dt = make_aware(datetime.combine(self.period_end, time.max))
        
        # Use the same logic as collect_metrics - tasks that were active during the period
        tasks = Task.objects.filter(
            column__board=self.board,
            created_at__lte=period_end_dt
        ).exclude(
            completed_at__lt=period_start_dt
        )
        
        patterns = {
            'successes': [],
            'challenges': [],
            'insights': []
        }
        
        # Analyze completed tasks
        completed_tasks = tasks.filter(progress=100, completed_at__isnull=False)
        if completed_tasks.exists():
            avg_duration = completed_tasks.aggregate(Avg('actual_duration_days'))['actual_duration_days__avg']
            if avg_duration:
                patterns['successes'].append({
                    'type': 'completion_time',
                    'description': f"Average task completion time: {avg_duration:.1f} days",
                    'metric': avg_duration
                })
            
            # High performers
            top_assignees = completed_tasks.values('assigned_to__username').annotate(
                count=Count('id')
            ).order_by('-count')[:3]
            
            for assignee in top_assignees:
                if assignee['assigned_to__username']:
                    patterns['successes'].append({
                        'type': 'high_performer',
                        'description': f"{assignee['assigned_to__username']} completed {assignee['count']} tasks",
                        'count': assignee['count']
                    })
        
        # Analyze challenges
        overdue_tasks = tasks.filter(due_date__lt=timezone.now(), progress__lt=100)
        if overdue_tasks.exists():
            patterns['challenges'].append({
                'type': 'overdue',
                'description': f"{overdue_tasks.count()} tasks are overdue",
                'count': overdue_tasks.count(),
                'severity': 'high' if overdue_tasks.count() > 5 else 'medium'
            })
        
        # Unassigned tasks
        unassigned = tasks.filter(assigned_to__isnull=True)
        if unassigned.count() > 3:
            patterns['challenges'].append({
                'type': 'unassigned',
                'description': f"{unassigned.count()} tasks remain unassigned",
                'count': unassigned.count(),
                'severity': 'medium'
            })
        
        # High complexity tasks
        high_complexity = tasks.filter(complexity_score__gte=8)
        if high_complexity.exists():
            completed_high = high_complexity.filter(progress=100).count()
            patterns['insights'].append({
                'type': 'complexity',
                'description': f"{completed_high}/{high_complexity.count()} high-complexity tasks completed",
                'completion_rate': (completed_high / high_complexity.count() * 100) if high_complexity.count() > 0 else 0
            })
        
        return patterns
    
    def _get_ai_cache(self):
        """Get the AI cache manager."""
        try:
            from kanban_board.ai_cache import ai_cache_manager
            return ai_cache_manager
        except ImportError:
            return None
    
    def generate_ai_insights(self, metrics, patterns):
        """
        Generate AI insights using Gemini (with caching)
        
        Args:
            metrics: Metrics snapshot dict
            patterns: Pattern analysis dict
            
        Returns:
            dict: AI-generated insights
        """
        # Collect board members for AI-assisted action item assignment
        board_members = self._get_board_members_with_workload()

        # Build comprehensive prompt
        prompt = self._build_retrospective_prompt(metrics, patterns, board_members)
        
        # Create context ID for caching based on board and period
        context_id = f"board_{self.board.id}:{self.period_start.isoformat()}:{self.period_end.isoformat()}"
        
        # Try cache first
        ai_cache = self._get_ai_cache()
        if ai_cache:
            cached = ai_cache.get(prompt, 'retrospective', context_id)
            if cached:
                logger.debug("Retrospective AI cache HIT")
                return cached
        
        # Get AI response with complex task routing
        response = self.gemini_client.get_response(
            prompt=prompt,
            system_prompt="You are an expert agile coach and project management consultant specializing in retrospectives and continuous improvement.",
            task_complexity='complex'
        )
        
        if response.get('error'):
            logger.error(f"Error generating AI insights: {response['error']}")
            return self._generate_fallback_insights(metrics, patterns)
        
        # Parse AI response
        ai_content = response.get('content', '')
        
        # Extract structured insights from AI response
        insights = self._parse_ai_response(ai_content, metrics, patterns)
        insights['ai_model_used'] = response.get('model_used', 'gemini-2.0-flash-exp')
        insights['tokens_used'] = response.get('tokens', 0)
        
        # Cache the result
        if ai_cache and insights:
            ai_cache.set(prompt, insights, 'retrospective', context_id)
            logger.debug("Retrospective AI insights cached")
        
        return insights
    
    def _build_retrospective_prompt(self, metrics, patterns, board_members=None):
        """Build comprehensive prompt for AI retrospective generation"""

        # Pre-build board members text so it can be embedded cleanly in the f-string
        members_text = self._format_members_for_prompt(board_members or [])
        total_tasks = metrics.get('total_tasks', 0)
        in_progress_tasks = metrics.get('in_progress_tasks', 0)
        total_activities = metrics.get('total_activities', 0)

        prompt = f"""
Generate a comprehensive retrospective analysis for a project sprint/period.

**Period:** {self.period_start.strftime('%Y-%m-%d')} to {self.period_end.strftime('%Y-%m-%d')}
**Project/Board:** {self.board.name}

**Metrics Summary:**
- Total Tasks: {metrics['total_tasks']}
- Completed Tasks: {metrics['completed_tasks']} ({metrics['completion_rate']:.1f}% completion rate)
- In-Progress Tasks: {in_progress_tasks}
- Average Complexity: {metrics['avg_complexity']:.1f}/10
- Total Complexity Completed: {metrics['completed_complexity']}
- Average Completion Time: {metrics['avg_completion_time']:.1f} days
- High Priority Tasks: {metrics['high_priority_tasks']}
- Overdue Tasks: {metrics['overdue_tasks']}
- High Risk Tasks: {metrics['high_risk_tasks']}
- Active Team Members: {metrics['active_team_members']}
- Total Activities Logged: {total_activities}
- Team Velocity: {metrics.get('avg_velocity', 'N/A')} tasks/period
- Velocity Trend: {metrics.get('velocity_trend', 'unknown')}
- Scope Change: {metrics.get('scope_change_percentage', 0):.1f}%

**Board Team Members & Current Workload:**
{members_text}

**Observed Patterns:**

Successes:
{self._format_patterns_for_prompt(patterns.get('successes', []))}

Challenges:
{self._format_patterns_for_prompt(patterns.get('challenges', []))}

Insights:
{self._format_patterns_for_prompt(patterns.get('insights', []))}

**Please provide:**

1. **WHAT WENT WELL** — Provide exactly 2-3 specific positive observations. Each observation MUST reference actual data from the metrics above (e.g., number of tasks completed, team members who contributed, complexity points delivered, dependencies resolved, milestones hit, or activity levels). If the completion rate is 0%, do NOT use generic phrases like "Team made progress" — instead acknowledge concrete effort metrics: {total_tasks} tasks organised on the board, {in_progress_tasks} tasks actively in progress, {total_activities} activities logged showing team engagement. Never produce a single vague sentence for this section.
2. **WHAT NEEDS IMPROVEMENT** (3-5 areas for improvement with actionable details)
3. **LESSONS LEARNED** (Format as JSON array):
   [
     {{
       "title": "Lesson title",
       "description": "Detailed description",
       "category": "process|technical|communication|planning|quality|teamwork|tools|risk_management",
       "priority": "low|medium|high|critical",
       "recommended_action": "Specific action to take",
       "evidence": "Specific data or metrics that support this lesson",
       "confidence": 0.85
     }}
   ]
4. **KEY ACHIEVEMENTS** (JSON array of notable achievements)
5. **CHALLENGES FACED** (JSON array with impact assessment)
6. **IMPROVEMENT RECOMMENDATIONS** (5-7 specific, actionable recommendations as JSON array).
   For the "suggested_assignee" field, choose the most appropriate team member from the Board Team Members list above based on action type and their current workload. Prefer members with fewer open tasks for high-priority items. Use the exact username from the list, or null if no suitable match:
   [
     {{
       "title": "Recommendation title",
       "description": "Detailed description",
       "expected_impact": "Expected benefit",
       "priority": "low|medium|high|critical",
       "action_type": "process_change|tool_adoption|training|documentation|technical_improvement|team_building|communication",
       "suggested_assignee": "username_from_team_list_or_null",
       "evidence": "Data or observations supporting this recommendation",
       "confidence": 0.80
     }}
   ]
7. **OVERALL SENTIMENT SCORE** (0.0 to 1.0 where 0=negative, 1=positive)
8. **TEAM MORALE INDICATOR** (low|moderate|high|excellent)
9. **PERFORMANCE TREND** (improving|stable|declining)

Please provide detailed, data-driven insights based on the metrics. Be specific and actionable.
Format the response with clear sections using the headers above.
"""
        return prompt
    
    def _format_members_for_prompt(self, members):
        """Format board members list for AI prompt injection."""
        if not members:
            return '- No team members found (action items will be unassigned)'
        lines = []
        for m in members:
            lines.append(
                f"- {m['username']} ({m['full_name']}) — {m['open_tasks']} open tasks currently"
            )
        return '\n'.join(lines)

    def _format_patterns_for_prompt(self, patterns_list):
        """Format patterns for prompt"""
        if not patterns_list:
            return "- None identified"
        
        formatted = []
        for pattern in patterns_list:
            desc = pattern.get('description', 'Unknown pattern')
            formatted.append(f"- {desc}")
        
        return "\n".join(formatted)
    
    def _parse_ai_response(self, ai_content, metrics, patterns):
        """
        Parse AI-generated response into structured format
        
        Args:
            ai_content: Raw AI response text
            metrics: Original metrics
            patterns: Original patterns
            
        Returns:
            dict: Structured insights
        """
        import json
        import re
        
        insights = {
            'what_went_well': '',
            'what_needs_improvement': '',
            'lessons_learned': [],
            'key_achievements': [],
            'challenges_faced': [],
            'improvement_recommendations': [],
            'overall_sentiment_score': 0.75,
            'team_morale_indicator': 'moderate',
            'performance_trend': 'stable',
            'raw_analysis': ai_content
        }
        
        try:
            # Extract sections using regex
            sections = {
                'what_went_well': r'\*\*WHAT WENT WELL\*\*\s*(.*?)(?=\*\*|$)',
                'what_needs_improvement': r'\*\*WHAT NEEDS IMPROVEMENT\*\*\s*(.*?)(?=\*\*|$)',
                'lessons_learned': r'\*\*LESSONS LEARNED\*\*\s*(.*?)(?=\*\*|$)',
                'key_achievements': r'\*\*KEY ACHIEVEMENTS\*\*\s*(.*?)(?=\*\*|$)',
                'challenges_faced': r'\*\*CHALLENGES FACED\*\*\s*(.*?)(?=\*\*|$)',
                'improvement_recommendations': r'\*\*IMPROVEMENT RECOMMENDATIONS\*\*\s*(.*?)(?=\*\*|$)',
                'sentiment': r'\*\*OVERALL SENTIMENT SCORE\*\*\s*([0-9.]+)',
                'morale': r'\*\*TEAM MORALE INDICATOR\*\*\s*(\w+)',
                'trend': r'\*\*PERFORMANCE TREND\*\*\s*(\w+)',
            }
            
            for key, pattern in sections.items():
                match = re.search(pattern, ai_content, re.DOTALL | re.IGNORECASE)
                if match:
                    content = match.group(1).strip()
                    
                    if key in ['lessons_learned', 'key_achievements', 'challenges_faced', 'improvement_recommendations']:
                        # Try to parse as JSON
                        try:
                            # Find JSON array in content
                            json_match = re.search(r'\[.*\]', content, re.DOTALL)
                            if json_match:
                                insights[key] = json.loads(json_match.group(0))
                            else:
                                # Parse as bullet points
                                insights[key] = self._parse_bullet_points(content, key)
                        except json.JSONDecodeError:
                            # Fallback to bullet point parsing
                            insights[key] = self._parse_bullet_points(content, key)
                    elif key == 'sentiment':
                        try:
                            insights['overall_sentiment_score'] = float(content)
                        except ValueError:
                            pass
                    elif key == 'morale':
                        insights['team_morale_indicator'] = content.lower()
                    elif key == 'trend':
                        insights['performance_trend'] = content.lower()
                    else:
                        insights[key] = content
            
            # Ensure we have at least some data
            if not insights['what_went_well']:
                insights['what_went_well'] = self._generate_default_positives(metrics, patterns)
            
            if not insights['what_needs_improvement']:
                insights['what_needs_improvement'] = self._generate_default_improvements(metrics, patterns)
            
        except Exception as e:
            logger.error(f"Error parsing AI response: {e}")
            # Fall back to basic parsing
            insights['what_went_well'] = self._generate_default_positives(metrics, patterns)
            insights['what_needs_improvement'] = self._generate_default_improvements(metrics, patterns)
        
        return insights
    
    def _parse_bullet_points(self, content, section_type):
        """Parse bullet point content into structured format"""
        items = []
        lines = content.split('\n')
        
        current_item = {}
        for line in lines:
            line = line.strip()
            if line.startswith('-') or line.startswith('*'):
                if current_item:
                    items.append(current_item)
                current_item = {'description': line.lstrip('-*').strip()}
            elif line and current_item:
                current_item['description'] += ' ' + line
        
        if current_item:
            items.append(current_item)
        
        # Add default fields based on section type
        for item in items:
            if section_type == 'lessons_learned':
                item.setdefault('category', 'other')
                item.setdefault('priority', 'medium')
                item.setdefault('title', item['description'][:50])
            elif section_type == 'improvement_recommendations':
                item.setdefault('priority', 'medium')
                item.setdefault('action_type', 'other')
                item.setdefault('title', item['description'][:50])
        
        return items
    
    def _generate_default_positives(self, metrics, patterns):
        """Generate default positive feedback from metrics — always 2-3 specific observations."""
        positives = []

        total_tasks = metrics.get('total_tasks', 0)
        completed = metrics.get('completed_tasks', 0)
        in_progress = metrics.get('in_progress_tasks', 0)
        activities = metrics.get('total_activities', 0)
        completion_rate = metrics.get('completion_rate', 0)

        if completion_rate >= 80:
            positives.append(
                f"✓ Excellent completion rate of {completion_rate:.1f}% — "
                f"{completed} out of {total_tasks} tasks were successfully completed this period."
            )
        elif completion_rate >= 60:
            positives.append(
                f"✓ Good completion rate of {completion_rate:.1f}% — "
                f"{completed} out of {total_tasks} tasks were delivered."
            )
        elif completed > 0:
            positives.append(
                f"✓ {completed} task(s) completed out of {total_tasks} total "
                f"({completion_rate:.1f}% completion rate), demonstrating forward momentum."
            )
        else:
            # 0% completion — acknowledge effort metrics instead
            positives.append(
                f"✓ The team actively organised and tracked {total_tasks} task(s) on the board "
                f"during this period, demonstrating planning effort and board hygiene."
            )

        # In-progress work
        if in_progress > 0:
            positives.append(
                f"✓ {in_progress} task(s) are actively in progress, indicating ongoing team "
                f"engagement and continuity of work."
            )

        # Activity level
        if activities > 0:
            positives.append(
                f"✓ The team logged {activities} task activities during this period, "
                f"reflecting consistent collaboration and communication."
            )

        # High-performer data from patterns (avoid duplicates)
        successes = patterns.get('successes', [])
        for success in successes[:2]:
            desc = success.get('description', '')
            if desc and not any(desc in p for p in positives):
                positives.append(f"✓ {desc}")

        if metrics.get('velocity_trend') == 'increasing':
            positives.append("✓ Team velocity is on an upward trend compared to the previous period.")

        # Always guarantee at least 2 observations
        if len(positives) < 2:
            positives.append(
                f"✓ {total_tasks} task(s) are tracked on the board, demonstrating structured "
                f"project visibility and team awareness."
            )

        return '\n'.join(positives)
    
    def _generate_default_improvements(self, metrics, patterns):
        """Generate default improvement areas from metrics"""
        improvements = []
        
        if metrics['completion_rate'] < 60:
            improvements.append(f"• Low completion rate ({metrics['completion_rate']:.1f}%) - need to improve task throughput")
        
        if metrics['overdue_tasks'] > 3:
            improvements.append(f"• {metrics['overdue_tasks']} overdue tasks - improve time management and estimation")
        
        if metrics['unassigned_tasks'] > 3:
            improvements.append(f"• {metrics['unassigned_tasks']} unassigned tasks - improve task assignment process")
        
        if metrics.get('velocity_trend') == 'decreasing':
            improvements.append("• Team velocity is declining - investigate bottlenecks and blockers")
        
        challenges = patterns.get('challenges', [])
        for challenge in challenges[:3]:
            improvements.append(f"• {challenge['description']}")
        
        return '\n'.join(improvements) if improvements else "Continue current practices and monitor performance."
    
    def _generate_fallback_insights(self, metrics, patterns):
        """Generate basic insights when AI is unavailable"""
        return {
            'what_went_well': self._generate_default_positives(metrics, patterns),
            'what_needs_improvement': self._generate_default_improvements(metrics, patterns),
            'lessons_learned': [],
            'key_achievements': [],
            'challenges_faced': [],
            'improvement_recommendations': [],
            'overall_sentiment_score': 0.70,
            'team_morale_indicator': 'moderate',
            'performance_trend': 'stable',
            'raw_analysis': 'AI analysis unavailable - showing metrics-based summary',
            'ai_model_used': 'fallback',
            'tokens_used': 0
        }
    
    def _calculate_retrospective_confidence(self, metrics, patterns, insights):
        """
        Calculate a data-driven confidence score for the retrospective analysis
        instead of using a hardcoded value. The score reflects how much data
        was available for the AI to base its analysis on.
        
        Returns:
            float: Confidence score between 0.30 and 0.95
        """
        score = 0.35  # baseline — we always have at least period and board name
        
        # Task volume (more tasks = more reliable patterns)
        total_tasks = metrics.get('total_tasks', 0)
        if total_tasks >= 20:
            score += 0.12
        elif total_tasks >= 10:
            score += 0.08
        elif total_tasks >= 5:
            score += 0.04
        
        # Completion rate data present
        if metrics.get('completed_tasks', 0) > 0:
            score += 0.06
        
        # Velocity data present (indicates snapshot history)
        if metrics.get('avg_velocity') and metrics['avg_velocity'] != 'N/A':
            score += 0.08
        
        # Velocity trend available
        if metrics.get('velocity_trend') and metrics['velocity_trend'] != 'unknown':
            score += 0.04
        
        # Active team members known
        if metrics.get('active_team_members', 0) > 0:
            score += 0.04
        
        # Patterns detected
        pattern_count = (
            len(patterns.get('successes', []))
            + len(patterns.get('challenges', []))
            + len(patterns.get('insights', []))
        )
        if pattern_count >= 6:
            score += 0.10
        elif pattern_count >= 3:
            score += 0.06
        elif pattern_count >= 1:
            score += 0.03
        
        # Risk data present
        if metrics.get('high_risk_tasks', 0) > 0:
            score += 0.03
        
        # Scope change data
        if metrics.get('scope_change_percentage', 0) != 0:
            score += 0.02
        
        # AI insights quality (not fallback)
        if insights.get('ai_model_used') and insights['ai_model_used'] != 'fallback':
            score += 0.06
            # AI provided lessons and recommendations
            if insights.get('lessons_learned'):
                score += 0.03
            if insights.get('improvement_recommendations'):
                score += 0.03
        
        return min(score, 0.95)
    
    def create_retrospective(self, created_by, retrospective_type='sprint'):
        """
        Create complete retrospective with AI analysis
        
        Args:
            created_by: User creating the retrospective
            retrospective_type: Type of retrospective
            
        Returns:
            ProjectRetrospective instance
        """
        from kanban.retrospective_models import ProjectRetrospective
        
        logger.info(f"Generating retrospective for {self.board.name}: {self.period_start} to {self.period_end}")
        
        # Collect metrics
        metrics = self.collect_metrics()
        
        # Analyze patterns
        patterns = self.analyze_task_patterns()
        
        # Generate AI insights
        insights = self.generate_ai_insights(metrics, patterns)
        
        # Calculate data-driven confidence score based on data richness
        confidence = self._calculate_retrospective_confidence(metrics, patterns, insights)
        
        # Create retrospective
        retrospective = ProjectRetrospective.objects.create(
            board=self.board,
            title=f"{self.board.name} Retrospective - {self.period_start.strftime('%Y-%m-%d')}",
            retrospective_type=retrospective_type,
            status='generated',
            period_start=self.period_start,
            period_end=self.period_end,
            metrics_snapshot=metrics,
            what_went_well=insights['what_went_well'],
            what_needs_improvement=insights['what_needs_improvement'],
            lessons_learned=insights.get('lessons_learned', []),
            key_achievements=insights.get('key_achievements', []),
            challenges_faced=insights.get('challenges_faced', []),
            improvement_recommendations=insights.get('improvement_recommendations', []),
            overall_sentiment_score=Decimal(str(insights.get('overall_sentiment_score', 0.75))),
            team_morale_indicator=insights.get('team_morale_indicator', 'moderate'),
            performance_trend=insights.get('performance_trend', 'stable'),
            ai_generated_at=timezone.now(),
            ai_confidence_score=Decimal(str(round(confidence, 2))),
            ai_model_used=insights.get('ai_model_used', 'gemini-2.0-flash-exp'),
            created_by=created_by
        )
        
        logger.info(f"Retrospective created: {retrospective.id}")
        
        # Create related records
        self._create_lessons_learned(retrospective, insights.get('lessons_learned', []))
        self._create_action_items(retrospective, insights.get('improvement_recommendations', []))
        self._create_improvement_metrics(retrospective, metrics)
        
        return retrospective
    
    def _create_lessons_learned(self, retrospective, lessons_data):
        """Create LessonLearned records from AI insights"""
        from kanban.retrospective_models import LessonLearned
        
        # If no lessons from AI, create some basic ones from patterns
        if not lessons_data:
            logger.warning("No lessons from AI, generating basic lessons from data")
            lessons_data = self._generate_fallback_lessons()
        
        for lesson in lessons_data:
            try:
                # Use AI-provided confidence if available, else default to 0.75
                lesson_confidence = lesson.get('confidence', 0.75)
                if isinstance(lesson_confidence, (int, float)):
                    lesson_confidence = max(0.0, min(1.0, float(lesson_confidence)))
                else:
                    lesson_confidence = 0.75
                
                LessonLearned.objects.create(
                    retrospective=retrospective,
                    board=self.board,
                    title=lesson.get('title', lesson.get('description', 'Untitled')[:100]),
                    description=self._clean_lesson_description(
                        lesson.get('description', ''),
                        lesson.get('title', ''),
                        lesson.get('evidence', '')
                    ),
                    category=lesson.get('category', 'other'),
                    priority=lesson.get('priority', 'medium'),
                    recommended_action=lesson.get('recommended_action', 'Review and implement'),
                    ai_suggested=True,
                    ai_confidence=Decimal(str(round(lesson_confidence, 2)))
                )
            except Exception as e:
                logger.error(f"Error creating lesson learned: {e}")
    
    @staticmethod
    def _clean_lesson_description(description, title, evidence=''):
        """Avoid storing placeholder-like or title-duplicate descriptions."""
        desc = (description or '').strip()
        title_clean = (title or '').strip()
        # Detect placeholder patterns
        if (not desc
                or desc == title_clean
                or desc.startswith('Detailed insight about')
                or desc.startswith('No additional details')):
            # Fall back to evidence if available
            return (evidence or '').strip()
        return desc

    def _create_action_items(self, retrospective, recommendations_data):
        """Create RetrospectiveActionItem records from recommendations"""
        from kanban.retrospective_models import RetrospectiveActionItem
        
        # If no recommendations from AI, create some basic ones
        if not recommendations_data:
            logger.warning("No recommendations from AI, generating basic action items")
            recommendations_data = self._generate_fallback_actions()
        
        # Valid action_type choices from the model — normalise AI output to these
        valid_action_types = {
            'process_change', 'tool_adoption', 'training', 'documentation',
            'technical_improvement', 'team_building', 'communication', 'other'
        }
        # Mapping for common AI-generated non-standard values
        action_type_aliases = {
            'process_improvement': 'process_change',
            'process': 'process_change',
            'tool': 'tool_adoption',
            'teamwork': 'team_building',
            'collaboration': 'team_building',
            'planning': 'process_change',
            'technical': 'technical_improvement',
            'tech': 'technical_improvement',
            'docs': 'documentation',
            'communication_enhancement': 'communication',
        }

        for rec in recommendations_data:
            try:
                # Calculate target date based on priority
                priority = rec.get('priority', 'medium')
                days_offset = {'critical': 7, 'high': 14, 'medium': 30, 'low': 60}
                target_date = timezone.now().date() + timedelta(days=days_offset.get(priority, 30))

                # Normalise action_type to a valid model choice
                raw_type = rec.get('action_type', 'other').lower().strip()
                action_type = action_type_aliases.get(raw_type, raw_type)
                if action_type not in valid_action_types:
                    action_type = 'other'

                # Resolve suggested assignee to a User instance
                assigned_to = None
                suggested_username = rec.get('suggested_assignee', '')
                if suggested_username and str(suggested_username).lower() not in ('null', 'none', ''):
                    try:
                        from django.contrib.auth.models import User
                        assigned_to = User.objects.filter(
                            username__iexact=str(suggested_username).strip()
                        ).first()
                    except Exception:
                        assigned_to = None

                RetrospectiveActionItem.objects.create(
                    retrospective=retrospective,
                    board=self.board,
                    title=rec.get('title', rec.get('description', 'Untitled')[:100]),
                    description=rec.get('description', ''),
                    action_type=action_type,
                    priority=priority,
                    expected_impact=rec.get('expected_impact', 'Improve team performance'),
                    target_completion_date=target_date,
                    assigned_to=assigned_to,
                    ai_suggested=True,
                    ai_confidence=Decimal('0.75')
                )
            except Exception as e:
                logger.error(f"Error creating action item: {e}")
    
    def _create_improvement_metrics(self, retrospective, metrics):
        """Create ImprovementMetric records from collected metrics"""
        from kanban.retrospective_models import ImprovementMetric, ProjectRetrospective
        
        # Get previous retrospective for comparison
        previous_retro = ProjectRetrospective.objects.filter(
            board=self.board,
            period_end__lt=self.period_start,
            status__in=['reviewed', 'finalized']
        ).order_by('-period_end').first()
        
        previous_metrics = previous_retro.metrics_snapshot if previous_retro else {}
        
        # Key metrics to track
        metric_definitions = [
            {
                'type': 'velocity',
                'name': 'Team Velocity',
                'value': metrics.get('completed_tasks', 0),
                'unit': 'tasks',
                'higher_is_better': True
            },
            {
                'type': 'quality',
                'name': 'Completion Rate',
                'value': metrics.get('completion_rate', 0),
                'unit': 'percentage',
                'higher_is_better': True
            },
            {
                'type': 'cycle_time',
                'name': 'Average Completion Time',
                'value': metrics.get('avg_completion_time', 0),
                'unit': 'days',
                'higher_is_better': False
            },
        ]
        
        # Map metric_type code → metrics_snapshot key for previous-period comparison
        snapshot_key_map = {
            'velocity': 'completed_tasks',
            'quality': 'completion_rate',
            'cycle_time': 'avg_completion_time',
        }

        for metric_def in metric_definitions:
            try:
                snapshot_key = snapshot_key_map.get(metric_def['type'])
                previous_value = (
                    previous_metrics.get(snapshot_key)
                    if previous_metrics and snapshot_key
                    else None
                )
                
                ImprovementMetric.objects.create(
                    board=self.board,
                    retrospective=retrospective,
                    metric_type=metric_def['type'],
                    metric_name=metric_def['name'],
                    metric_value=Decimal(str(metric_def['value'])),
                    previous_value=Decimal(str(previous_value)) if previous_value else None,
                    unit_of_measure=metric_def['unit'],
                    higher_is_better=metric_def['higher_is_better'],
                    measured_at=self.period_end
                )
            except Exception as e:
                logger.error(f"Error creating improvement metric: {e}")
    
    def _generate_fallback_lessons(self):
        """Generate basic lessons when AI doesn't provide them"""
        lessons = []
        
        # Collect metrics for lesson generation
        metrics = self.collect_metrics()
        
        # Generate lessons based on data
        if metrics['completion_rate'] >= 70:
            lessons.append({
                'title': 'Good task completion rate achieved',
                'description': f"Team successfully completed {metrics['completed_tasks']} out of {metrics['total_tasks']} tasks ({metrics['completion_rate']:.1f}% completion rate).",
                'category': 'team_performance',
                'priority': 'medium',
                'recommended_action': 'Continue current practices and identify factors contributing to success'
            })
        elif metrics['completion_rate'] < 50:
            lessons.append({
                'title': 'Low completion rate needs attention',
                'description': f"Only {metrics['completion_rate']:.1f}% of tasks were completed. Investigate blockers and capacity issues.",
                'category': 'process',
                'priority': 'high',
                'recommended_action': 'Review task assignments and identify bottlenecks'
            })
        
        if metrics['overdue_tasks'] > metrics['total_tasks'] * 0.2:
            lessons.append({
                'title': 'Too many overdue tasks',
                'description': f"{metrics['overdue_tasks']} tasks are overdue. This suggests estimation or capacity issues.",
                'category': 'planning',
                'priority': 'high',
                'recommended_action': 'Review estimation process and team capacity planning'
            })
        
        if metrics['unassigned_tasks'] > 0:
            lessons.append({
                'title': 'Unassigned tasks detected',
                'description': f"{metrics['unassigned_tasks']} tasks remain unassigned, which may cause delays.",
                'category': 'teamwork',
                'priority': 'medium',
                'recommended_action': 'Implement clear task assignment process'
            })
        
        # Always add at least one generic lesson
        if not lessons:
            lessons.append({
                'title': 'Team made progress during this period',
                'description': f"The team worked on {metrics['total_tasks']} tasks and showed engagement.",
                'category': 'team_performance',
                'priority': 'low',
                'recommended_action': 'Continue monitoring progress and team dynamics'
            })
        
        return lessons
    
    def _generate_fallback_actions(self):
        """Generate basic action items when AI doesn't provide them"""
        actions = []
        
        metrics = self.collect_metrics()
        
        if metrics['completion_rate'] < 70:
            actions.append({
                'title': 'Improve task completion rate',
                'description': 'Identify and remove blockers preventing task completion',
                'action_type': 'process_improvement',
                'priority': 'high',
                'expected_impact': 'Increase completion rate by 20%'
            })
        
        if metrics['overdue_tasks'] > 0:
            actions.append({
                'title': 'Address overdue tasks',
                'description': 'Review and reprioritize overdue tasks, adjust estimates if needed',
                'action_type': 'planning',
                'priority': 'high',
                'expected_impact': 'Reduce overdue tasks to zero'
            })
        
        if metrics['unassigned_tasks'] > 0:
            actions.append({
                'title': 'Assign all tasks to team members',
                'description': 'Ensure every task has a clear owner',
                'action_type': 'teamwork',
                'priority': 'medium',
                'expected_impact': 'Improve accountability and task completion'
            })
        
        # Always add at least one generic action
        if not actions:
            actions.append({
                'title': 'Continue monitoring team performance',
                'description': 'Track key metrics and adjust processes as needed',
                'action_type': 'process_improvement',
                'priority': 'low',
                'expected_impact': 'Maintain or improve current performance levels'
            })
        
        return actions
