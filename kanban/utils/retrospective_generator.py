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
        
        # Get tasks within the period
        tasks = Task.objects.filter(
            column__board=self.board,
            created_at__range=(self.period_start, self.period_end)
        )
        
        # Get completed tasks
        completed_tasks = tasks.filter(progress=100, completed_at__isnull=False)
        
        # Calculate metrics
        metrics = {
            # Task metrics
            'total_tasks': tasks.count(),
            'completed_tasks': completed_tasks.count(),
            'in_progress_tasks': tasks.filter(progress__gt=0, progress__lt=100).count(),
            'blocked_tasks': tasks.filter(progress=0).count(),
            
            # Completion rate
            'completion_rate': (completed_tasks.count() / tasks.count() * 100) if tasks.count() > 0 else 0,
            
            # Complexity metrics
            'total_complexity': tasks.aggregate(Sum('complexity_score'))['complexity_score__sum'] or 0,
            'completed_complexity': completed_tasks.aggregate(Sum('complexity_score'))['complexity_score__sum'] or 0,
            'avg_complexity': tasks.aggregate(Avg('complexity_score'))['complexity_score__avg'] or 0,
            
            # Priority distribution
            'high_priority_tasks': tasks.filter(priority__in=['high', 'urgent']).count(),
            'urgent_tasks': tasks.filter(priority='urgent').count(),
            
            # Time metrics
            'avg_completion_time': completed_tasks.aggregate(Avg('actual_duration_days'))['actual_duration_days__avg'] or 0,
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
                created_at__range=(self.period_start, self.period_end)
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
            snapshot_date__range=(self.period_start, self.period_end)
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
        
        tasks = Task.objects.filter(
            column__board=self.board,
            created_at__range=(self.period_start, self.period_end)
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
    
    def generate_ai_insights(self, metrics, patterns):
        """
        Generate AI insights using Gemini
        
        Args:
            metrics: Metrics snapshot dict
            patterns: Pattern analysis dict
            
        Returns:
            dict: AI-generated insights
        """
        # Build comprehensive prompt
        prompt = self._build_retrospective_prompt(metrics, patterns)
        
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
        
        return insights
    
    def _build_retrospective_prompt(self, metrics, patterns):
        """Build comprehensive prompt for AI retrospective generation"""
        
        prompt = f"""
Generate a comprehensive retrospective analysis for a project sprint/period.

**Period:** {self.period_start.strftime('%Y-%m-%d')} to {self.period_end.strftime('%Y-%m-%d')}
**Project/Board:** {self.board.name}

**Metrics Summary:**
- Total Tasks: {metrics['total_tasks']}
- Completed Tasks: {metrics['completed_tasks']} ({metrics['completion_rate']:.1f}% completion rate)
- Average Complexity: {metrics['avg_complexity']:.1f}/10
- Total Complexity Completed: {metrics['completed_complexity']}
- Average Completion Time: {metrics['avg_completion_time']:.1f} days
- High Priority Tasks: {metrics['high_priority_tasks']}
- Overdue Tasks: {metrics['overdue_tasks']}
- High Risk Tasks: {metrics['high_risk_tasks']}
- Active Team Members: {metrics['active_team_members']}
- Team Velocity: {metrics.get('avg_velocity', 'N/A')} tasks/period
- Velocity Trend: {metrics.get('velocity_trend', 'unknown')}
- Scope Change: {metrics.get('scope_change_percentage', 0):.1f}%

**Observed Patterns:**

Successes:
{self._format_patterns_for_prompt(patterns.get('successes', []))}

Challenges:
{self._format_patterns_for_prompt(patterns.get('challenges', []))}

Insights:
{self._format_patterns_for_prompt(patterns.get('insights', []))}

**Please provide:**

1. **WHAT WENT WELL** (3-5 key positive points with specific examples)
2. **WHAT NEEDS IMPROVEMENT** (3-5 areas for improvement with actionable details)
3. **LESSONS LEARNED** (Format as JSON array):
   [
     {{
       "title": "Lesson title",
       "description": "Detailed description",
       "category": "process|technical|communication|planning|quality|teamwork|tools|risk_management",
       "priority": "low|medium|high|critical",
       "recommended_action": "Specific action to take"
     }}
   ]
4. **KEY ACHIEVEMENTS** (JSON array of notable achievements)
5. **CHALLENGES FACED** (JSON array with impact assessment)
6. **IMPROVEMENT RECOMMENDATIONS** (5-7 specific, actionable recommendations as JSON array):
   [
     {{
       "title": "Recommendation title",
       "description": "Detailed description",
       "expected_impact": "Expected benefit",
       "priority": "low|medium|high|critical",
       "action_type": "process_change|tool_adoption|training|documentation|technical_improvement"
     }}
   ]
7. **OVERALL SENTIMENT SCORE** (0.0 to 1.0 where 0=negative, 1=positive)
8. **TEAM MORALE INDICATOR** (low|moderate|high|excellent)
9. **PERFORMANCE TREND** (improving|stable|declining)

Please provide detailed, data-driven insights based on the metrics. Be specific and actionable.
Format the response with clear sections using the headers above.
"""
        return prompt
    
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
        """Generate default positive feedback from metrics"""
        positives = []
        
        if metrics['completion_rate'] >= 80:
            positives.append(f"✓ Excellent completion rate of {metrics['completion_rate']:.1f}%")
        elif metrics['completion_rate'] >= 60:
            positives.append(f"✓ Good completion rate of {metrics['completion_rate']:.1f}%")
        
        if metrics['completed_tasks'] > 0:
            positives.append(f"✓ Successfully completed {metrics['completed_tasks']} tasks")
        
        if metrics.get('velocity_trend') == 'increasing':
            positives.append("✓ Team velocity is improving over time")
        
        successes = patterns.get('successes', [])
        for success in successes[:3]:
            positives.append(f"✓ {success['description']}")
        
        return '\n'.join(positives) if positives else "Team made progress during this period."
    
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
            ai_confidence_score=Decimal('0.80'),
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
        
        for lesson in lessons_data:
            try:
                LessonLearned.objects.create(
                    retrospective=retrospective,
                    board=self.board,
                    title=lesson.get('title', lesson.get('description', 'Untitled')[:100]),
                    description=lesson.get('description', ''),
                    category=lesson.get('category', 'other'),
                    priority=lesson.get('priority', 'medium'),
                    recommended_action=lesson.get('recommended_action', 'Review and implement'),
                    ai_suggested=True,
                    ai_confidence=Decimal('0.75')
                )
            except Exception as e:
                logger.error(f"Error creating lesson learned: {e}")
    
    def _create_action_items(self, retrospective, recommendations_data):
        """Create RetrospectiveActionItem records from recommendations"""
        from kanban.retrospective_models import RetrospectiveActionItem
        
        for rec in recommendations_data:
            try:
                # Calculate target date based on priority
                priority = rec.get('priority', 'medium')
                days_offset = {'critical': 7, 'high': 14, 'medium': 30, 'low': 60}
                target_date = timezone.now().date() + timedelta(days=days_offset.get(priority, 30))
                
                RetrospectiveActionItem.objects.create(
                    retrospective=retrospective,
                    board=self.board,
                    title=rec.get('title', rec.get('description', 'Untitled')[:100]),
                    description=rec.get('description', ''),
                    action_type=rec.get('action_type', 'other'),
                    priority=priority,
                    expected_impact=rec.get('expected_impact', 'Improve team performance'),
                    target_completion_date=target_date,
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
        
        for metric_def in metric_definitions:
            try:
                previous_value = previous_metrics.get(metric_def['type']) if previous_metrics else None
                
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
