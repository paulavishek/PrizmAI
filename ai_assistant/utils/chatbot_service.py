import json
import logging
from django.conf import settings
from django.db.models import Q, Count, Avg, Max
from kanban.models import Task, Board
from ai_assistant.models import ProjectKnowledgeBase
from .ai_clients import GeminiClient
from .google_search import GoogleSearchClient

# Conditional imports for optional features
try:
    from kanban.stakeholder_models import ProjectStakeholder, StakeholderTaskInvolvement
    HAS_STAKEHOLDER_MODELS = True
except ImportError:
    HAS_STAKEHOLDER_MODELS = False

try:
    from kanban.models import ResourceDemandForecast, TeamCapacityAlert, WorkloadDistributionRecommendation, MeetingTranscript
    HAS_RESOURCE_MODELS = True
except ImportError:
    HAS_RESOURCE_MODELS = False

logger = logging.getLogger(__name__)


class TaskFlowChatbotService:
    """
    Chatbot service for TaskFlow project assistant
    Adapted from Nexus 360 for TaskFlow's project management data
    """
    
    def __init__(self, user=None, board=None):
        self.user = user
        self.board = board
        self.gemini_client = GeminiClient()
        self.search_client = GoogleSearchClient()
        logger.debug(f"ChatbotService initialized for user: {user}, board: {board}")
    
    def get_taskflow_context(self, use_cache=True):
        """
        Get context from TaskFlow project data
        
        Args:
            use_cache (bool): Whether to use cached context
            
        Returns:
            str: Formatted project context
        """
        try:
            context = "**TaskFlow Project Context:**\n\n"
            
            if self.board:
                context += f"Board: {self.board.name}\n"
                if self.board.description:
                    context += f"Description: {self.board.description}\n"
                
                # Get tasks with comprehensive information
                tasks = Task.objects.filter(column__board=self.board).select_related(
                    'assigned_to', 'created_by', 'column', 'parent_task'
                ).prefetch_related('labels', 'subtasks', 'dependencies')
                
                if tasks.exists():
                    context += f"\n**Tasks Summary ({tasks.count()} total):**\n"
                    
                    # Group by status
                    from django.db.models import Count
                    status_counts = tasks.values('column__name').annotate(count=Count('id'))
                    for status in status_counts:
                        context += f"  - {status['column__name']}: {status['count']}\n"
                    
                    # Show sample tasks with key details
                    context += f"\n**Key Tasks (sample):**\n"
                    for task in tasks[:15]:  # Show top 15
                        status = task.column.name if task.column else 'Unknown'
                        priority = task.get_priority_display() if hasattr(task, 'get_priority_display') else task.priority
                        assignee = task.assigned_to.get_full_name() or task.assigned_to.username if task.assigned_to else 'Unassigned'
                        
                        context += f"- [{status}] {task.title}\n"
                        context += f"  • Priority: {priority}, Assigned: {assignee}, Progress: {task.progress}%\n"
                        
                        # Add risk info if available
                        if task.risk_level or task.ai_risk_score:
                            risk_info = f"Risk: {task.risk_level or 'Unknown'}"
                            if task.ai_risk_score:
                                risk_info += f" (Score: {task.ai_risk_score}/100)"
                            context += f"  • {risk_info}\n"
                        
                        # Add dependency info
                        if task.parent_task:
                            context += f"  • Depends on: {task.parent_task.title}\n"
                        if task.subtasks.exists():
                            context += f"  • Has {task.subtasks.count()} subtask(s)\n"
                
                # Get team members with skills
                members = self.board.members.select_related('profile').all()
                if members.exists():
                    context += f"\n**Team Members ({members.count()}):**\n"
                    for m in members[:10]:
                        member_info = m.get_full_name() or m.username
                        try:
                            if hasattr(m, 'profile') and m.profile.skills:
                                skills = [s.get('name', '') for s in m.profile.skills[:3]]
                                if skills:
                                    member_info += f" (Skills: {', '.join(skills)})"
                        except:
                            pass
                        context += f"  - {member_info}\n"
            
            elif self.user:
                # Get all user's boards and projects with aggregated stats
                boards = Board.objects.filter(
                    Q(created_by=self.user) | Q(members=self.user)
                ).distinct()[:5]
                
                if boards:
                    context += f"**User's Projects ({boards.count()} boards):**\n"
                    for board in boards:
                        task_count = Task.objects.filter(column__board=board).count()
                        context += f"- {board.name} ({task_count} tasks)\n"
            
            return context
        
        except Exception as e:
            logger.error(f"Error getting TaskFlow context: {e}")
            return "Project context unavailable."
    
    def get_risk_analysis_context(self, prompt):
        """
        Get risk analysis data for risk-related queries
        
        Args:
            prompt (str): User query
            
        Returns:
            str: Formatted risk analysis context
        """
        try:
            # Check if this is a risk-related query
            risk_keywords = ['risk', 'critical', 'blocker', 'issue', 'problem', 'delay', 'dependent']
            if not any(kw in prompt.lower() for kw in risk_keywords):
                return ""
            
            # Get boards based on context
            if self.board:
                board_tasks = Task.objects.filter(column__board=self.board)
            elif self.user:
                try:
                    organization = self.user.profile.organization
                    boards = Board.objects.filter(
                        Q(organization=organization) & 
                        (Q(created_by=self.user) | Q(members=self.user))
                    ).distinct()
                except:
                    boards = Board.objects.filter(
                        Q(created_by=self.user) | Q(members=self.user)
                    ).distinct()
                board_tasks = Task.objects.filter(column__board__in=boards)
            else:
                return ""
            
            # Get high-risk tasks
            high_risk_tasks = board_tasks.filter(
                risk_level__in=['high', 'critical']
            ).select_related('assigned_to', 'column').order_by('-risk_score')[:10]
            
            if not high_risk_tasks.exists():
                # Try alternative: tasks with AI risk score
                high_risk_tasks = board_tasks.filter(
                    ai_risk_score__gte=70
                ).select_related('assigned_to', 'column').order_by('-ai_risk_score')[:10]
            
            if not high_risk_tasks.exists():
                return ""
            
            context = "**Risk Analysis Data:**\n\n"
            context += f"High-Risk Tasks Found: {len(high_risk_tasks)}\n\n"
            
            for task in high_risk_tasks:
                context += f"**Task: {task.title}**\n"
                context += f"  Status: {task.column.name if task.column else 'Unknown'}\n"
                context += f"  Assigned: {task.assigned_to.username if task.assigned_to else 'Unassigned'}\n"
                
                # Risk level
                if task.risk_level:
                    context += f"  Risk Level: {task.risk_level.upper()}\n"
                if task.risk_score:
                    context += f"  Risk Score: {task.risk_score}/9\n"
                if task.ai_risk_score:
                    context += f"  AI Risk Score: {task.ai_risk_score}/100\n"
                
                # Risk indicators
                if task.risk_indicators:
                    context += f"  Risk Indicators: {', '.join(task.risk_indicators[:3])}\n"
                
                # Mitigation suggestions
                if task.mitigation_suggestions:
                    context += f"  Mitigation: {task.mitigation_suggestions[0] if task.mitigation_suggestions else 'N/A'}\n"
                
                # Dependencies
                if task.parent_task:
                    context += f"  Depends On: {task.parent_task.title}\n"
                
                context += "\n"
            
            return context
        
        except Exception as e:
            logger.error(f"Error getting risk analysis context: {e}")
            return ""
    
    def get_knowledge_base_context(self, query, max_results=3):
        """
        Get relevant knowledge base entries
        
        Args:
            query (str): Search query
            max_results (int): Max results to return
            
        Returns:
            str: Formatted KB context
        """
        try:
            # Simple keyword search in KB
            kb_entries = ProjectKnowledgeBase.objects.filter(
                is_active=True,
                content__icontains=query
            )
            
            if self.board:
                kb_entries = kb_entries.filter(board=self.board)
            
            if not kb_entries.exists():
                return ""
            
            context = "**From Project Knowledge Base:**\n\n"
            for entry in kb_entries[:max_results]:
                context += f"- {entry.title}: {entry.summary or entry.content[:200]}\n"
            
            return context
        
        except Exception as e:
            logger.error(f"Error getting KB context: {e}")
            return ""
    
    def _is_search_query(self, prompt):
        """
        Detect if query should trigger web search (RAG)
        
        Args:
            prompt (str): User prompt
            
        Returns:
            bool: True if web search should be triggered
        """
        search_triggers = [
            'latest', 'recent', 'current', 'new', 'today', '2025', '2024',
            'trend', 'news', 'update', 'web', 'online', 'internet',
            'what is the', 'how do', 'tell me about', 'find', 'search',
            'best practices', 'industry', 'methodology', 'tool', 'framework',
            'how to tackle', 'how to handle', 'how to manage', 'how to solve',
            'strategy for', 'strategies for', 'approach to', 'way to',
            'tips for', 'advice on', 'guidance on', 'recommendations for',
            'help me', 'suggest', 'what should', 'how can I', 'how can we',
            'industry standard', 'common practice', 'proven method', 
            'effective way', 'efficient way', 'optimal approach'
        ]
        
        prompt_lower = prompt.lower()
        return any(trigger in prompt_lower for trigger in search_triggers)
    
    def _is_project_query(self, prompt):
        """
        Detect if query is about project tasks/data
        """
        project_triggers = [
            'task', 'project', 'team', 'deadline', 'assigned',
            'priority', 'status', 'board', 'sprint', 'release',
            'milestone', 'member', 'resource', 'workload', 'risk',
            'risk', 'dependency', 'blocker', 'schedule', 'capacity'
        ]
        
        prompt_lower = prompt.lower()
        return any(trigger in prompt_lower for trigger in project_triggers)
    
    def _is_aggregate_query(self, prompt):
        """
        Detect if query is asking for aggregate/system-wide data
        Examples: "How many total tasks?", "Tasks across all boards?"
        """
        aggregate_keywords = [
            'total', 'all boards', 'across all', 'all projects',
            'sum', 'count all', 'how many tasks', 'how many',
            'total count', 'overall', 'entire', 'whole system'
        ]
        
        prompt_lower = prompt.lower()
        return any(kw in prompt_lower for kw in aggregate_keywords)
    
    def _get_aggregate_context(self, prompt):
        """
        Get system-wide aggregate data for queries like:
        - "How many tasks in all boards?"
        - "Total tasks?"
        - "Task count across all projects?"
        """
        try:
            # Only process if this looks like an aggregate query
            if not self._is_aggregate_query(prompt):
                return None
            
            # Get user's organization
            try:
                organization = self.user.profile.organization
            except:
                # Fallback if profile doesn't exist
                organization = None
            
            # Get user's boards (filtered by organization if available)
            if organization:
                user_boards = Board.objects.filter(
                    Q(organization=organization) & 
                    (Q(created_by=self.user) | Q(members=self.user))
                ).distinct()
            else:
                user_boards = Board.objects.filter(
                    Q(created_by=self.user) | Q(members=self.user)
                ).distinct()
            
            if not user_boards.exists():
                return "You don't have access to any boards yet."
            
            # Get aggregate data
            total_tasks = Task.objects.filter(
                column__board__in=user_boards
            ).count()
            
            # Get tasks by status
            tasks_by_status = Task.objects.filter(
                column__board__in=user_boards
            ).values('column__name').annotate(
                count=Count('id')
            ).order_by('column__name')
            
            # Get tasks by board
            tasks_by_board = Task.objects.filter(
                column__board__in=user_boards
            ).values('column__board__name').annotate(
                count=Count('id')
            ).order_by('-count')
            
            # Build context
            context = f"""**System-Wide Task Analytics (All Your Projects):**

- **Total Tasks:** {total_tasks}
- **Total Boards:** {user_boards.count()}

**Tasks by Status:**
"""
            for status in tasks_by_status:
                context += f"  - {status['column__name']}: {status['count']}\n"
            
            context += "\n**Tasks by Board:**\n"
            for board_stat in tasks_by_board:
                context += f"  - {board_stat['column__board__name']}: {board_stat['count']}\n"
            
            context += f"\n**All Boards:** {', '.join([b.name for b in user_boards])}\n"
            
            return context
        
        except Exception as e:
            logger.error(f"Error getting aggregate context: {e}")
            return None
    
    def _is_risk_query(self, prompt):
        """Detect if query is about risk management"""
        risk_keywords = [
            'risk', 'critical', 'blocker', 'issue', 'problem',
            'delay', 'dependent', 'high priority', 'urgent', 'alert'
        ]
        return any(kw in prompt.lower() for kw in risk_keywords)
    
    def _is_stakeholder_query(self, prompt):
        """Detect if query is about stakeholder management"""
        stakeholder_keywords = [
            'stakeholder', 'engagement', 'communication', 'involvement',
            'sponsor', 'participant', 'team', 'feedback', 'approval'
        ]
        return any(kw in prompt.lower() for kw in stakeholder_keywords)
    
    def _is_resource_query(self, prompt):
        """Detect if query is about resource management"""
        resource_keywords = [
            'resource', 'capacity', 'workload', 'forecast', 'availability',
            'team capacity', 'allocation', 'demand', 'utilization'
        ]
        return any(kw in prompt.lower() for kw in resource_keywords)
    
    def _is_lean_query(self, prompt):
        """Detect if query is about Lean Six Sigma"""
        lean_keywords = [
            'lean', 'six sigma', 'value-added', 'waste', 'efficiency',
            'muda', 'kaizen', 'waste elimination', 'va', 'nva'
        ]
        return any(kw in prompt.lower() for kw in lean_keywords)
    
    def _is_dependency_query(self, prompt):
        """Detect if query is about task dependencies"""
        dependency_keywords = [
            'depend', 'blocked', 'blocker', 'related', 'subtask',
            'child task', 'parent task', 'chain', 'prerequisite'
        ]
        return any(kw in prompt.lower() for kw in dependency_keywords)
    
    def _is_organization_query(self, prompt):
        """Detect if query is about organizations"""
        org_keywords = [
            'organization', 'organizations', 'org', 'company', 'companies',
            'client', 'clients', 'departments', 'teams', 'divisions'
        ]
        return any(kw in prompt.lower() for kw in org_keywords)
    
    def _is_critical_task_query(self, prompt):
        """Detect if query is about critical or high-priority tasks"""
        critical_keywords = [
            'critical', 'urgent', 'blocker', 'blocked', 'high risk',
            'high priority', 'emergency', 'ASAP', 'high-risk',
            'must do', 'must have'
        ]
        return any(kw in prompt.lower() for kw in critical_keywords)
    
    def _is_mitigation_query(self, prompt):
        """Detect if query is about risk mitigation strategies"""
        mitigation_keywords = [
            'mitigation', 'mitigate', 'mitigation strategy', 'mitigation plan',
            'mitigation strategies', 'how to reduce', 'how to manage', 'reduce risk',
            'manage risk', 'handle risk', 'prevent risk', 'strategy',
            'action plan', 'solution', 'resolution', 'remediation'
        ]
        return any(kw in prompt.lower() for kw in mitigation_keywords)
    
    def _is_user_task_query(self, prompt):
        """Detect if query is asking for tasks assigned to the current user"""
        user_task_keywords = [
            'my task', 'my tasks', 'assigned to me', 'tasks for me',
            'what am i working on', 'my work', 'my assignments',
            'tasks i have', 'tasks i need', 'my todo'
        ]
        return any(kw in prompt.lower() for kw in user_task_keywords)
    
    def _is_incomplete_task_query(self, prompt):
        """Detect if query is asking for incomplete/in-progress tasks"""
        incomplete_keywords = [
            'incomplete', 'not done', 'in progress', 'not completed',
            'not finished', 'pending', 'active', 'ongoing',
            'show incomplete', 'list incomplete', 'incomplete task'
        ]
        return any(kw in prompt.lower() for kw in incomplete_keywords)
    
    def _is_board_comparison_query(self, prompt):
        """Detect if query is asking for board comparisons"""
        comparison_keywords = [
            'compare board', 'compare project', 'comparison',
            'boards by', 'compare by', 'which board', 'most task',
            'most member', 'most active', 'least active', 'board stat'
        ]
        return any(kw in prompt.lower() for kw in comparison_keywords)
    
    def _is_task_distribution_query(self, prompt):
        """Detect if query is asking for task distribution by assignee"""
        distribution_keywords = [
            'task distribution', 'distribution by', 'tasks per person',
            'tasks per member', 'tasks per assignee', 'who has',
            'workload distribution', 'tasks assigned', 'assignment distribution'
        ]
        return any(kw in prompt.lower() for kw in distribution_keywords)
    
    def _is_progress_query(self, prompt):
        """Detect if query is asking for progress metrics"""
        progress_keywords = [
            'progress', 'completion', 'how complete', 'percentage',
            'average progress', 'overall progress', 'completion rate',
            'how far', 'status update'
        ]
        return any(kw in prompt.lower() for kw in progress_keywords)
    
    def _is_overdue_query(self, prompt):
        """Detect if query is asking for overdue tasks"""
        overdue_keywords = [
            'overdue', 'late', 'past due', 'missed deadline',
            'due soon', 'upcoming deadline', 'deadline', 'due date'
        ]
        return any(kw in prompt.lower() for kw in overdue_keywords)
    
    def _is_strategic_query(self, prompt):
        """
        Detect if query is asking for strategic advice, best practices, or how-to guidance
        These queries benefit from RAG + project context
        """
        strategic_keywords = [
            'how to', 'how can', 'how should', 'what should', 'best way to',
            'best practice', 'best practices', 'advice', 'guidance', 'recommend',
            'suggestion', 'tips', 'strategy', 'strategies', 'approach',
            'tackle', 'handle', 'manage', 'deal with', 'solve', 'improve',
            'optimize', 'enhance', 'better', 'effective', 'efficient',
            'successful', 'proven method', 'industry standard', 'expert advice'
        ]
        return any(kw in prompt.lower() for kw in strategic_keywords)
    
    def _get_user_tasks_context(self, prompt):
        """
        Get tasks assigned to the current user
        Handles questions like: "Show tasks assigned to me", "My tasks", etc.
        
        ALWAYS retrieves actual user tasks instead of asking for user identity
        """
        try:
            if not self._is_user_task_query(prompt):
                return None
            
            # Get user's boards
            user_boards = self._get_user_boards()
            if not user_boards.exists():
                return "You don't have access to any boards yet."
            
            # Get tasks assigned to current user
            user_tasks = Task.objects.filter(
                column__board__in=user_boards,
                assigned_to=self.user
            ).select_related('column', 'column__board').order_by('column__name', '-priority')
            
            if not user_tasks.exists():
                return f"No tasks currently assigned to you ({self.user.get_full_name() or self.user.username})."
            
            context = f"**Tasks Assigned to You ({self.user.get_full_name() or self.user.username}):**\n\n"
            context += f"**Total Tasks:** {user_tasks.count()}\n\n"
            
            # Group by status
            by_status = {}
            for task in user_tasks:
                status = task.column.name if task.column else 'Unknown'
                if status not in by_status:
                    by_status[status] = []
                by_status[status].append(task)
            
            for status, tasks in by_status.items():
                context += f"**{status} ({len(tasks)}):**\n"
                for task in tasks[:10]:  # Limit to 10 per status
                    context += f"  • {task.title}\n"
                    context += f"    - Board: {task.column.board.name if task.column else 'Unknown'}\n"
                    context += f"    - Priority: {task.get_priority_display()}\n"
                    context += f"    - Progress: {task.progress}%\n"
                    
                    if hasattr(task, 'due_date') and task.due_date:
                        from django.utils import timezone
                        if task.due_date < timezone.now().date():
                            context += f"    - Due: {task.due_date} ⚠️ OVERDUE\n"
                        else:
                            context += f"    - Due: {task.due_date}\n"
                    
                    context += "\n"
            
            return context
        
        except Exception as e:
            logger.error(f"Error getting user tasks context: {e}", exc_info=True)
            return f"Error retrieving your tasks: {str(e)}"
    
    def _get_incomplete_tasks_context(self, prompt):
        """
        Get incomplete tasks (not in Done/Closed status)
        Handles questions like: "Show incomplete tasks", "What's not done?", etc.
        
        ALWAYS retrieves actual incomplete tasks
        """
        try:
            if not self._is_incomplete_task_query(prompt):
                return None
            
            # Get user's boards
            user_boards = self._get_user_boards()
            if not user_boards.exists():
                return "You don't have access to any boards yet."
            
            # Get all incomplete tasks (exclude Done and Closed statuses)
            incomplete_tasks = Task.objects.filter(
                column__board__in=user_boards
            ).exclude(
                Q(column__name__icontains='done') | Q(column__name__icontains='closed')
            ).select_related('assigned_to', 'column', 'column__board').order_by(
                'column__board__name', 'column__name', '-priority'
            )
            
            if not incomplete_tasks.exists():
                return "All tasks are completed! 🎉"
            
            # Count completed tasks for comparison
            completed_tasks = Task.objects.filter(
                column__board__in=user_boards
            ).filter(
                Q(column__name__icontains='done') | Q(column__name__icontains='closed')
            ).count()
            
            total_tasks = incomplete_tasks.count() + completed_tasks
            
            context = f"**Incomplete Tasks Analysis:**\n\n"
            context += f"**Total Tasks:** {total_tasks}\n"
            context += f"**Completed:** {completed_tasks} ({100*completed_tasks/total_tasks:.1f}%)\n"
            context += f"**Incomplete:** {incomplete_tasks.count()} ({100*incomplete_tasks.count()/total_tasks:.1f}%)\n\n"
            
            # Group by board
            by_board = {}
            for task in incomplete_tasks:
                board_name = task.column.board.name if task.column else 'Unknown'
                if board_name not in by_board:
                    by_board[board_name] = []
                by_board[board_name].append(task)
            
            for board_name, tasks in by_board.items():
                context += f"**{board_name} Board ({len(tasks)} incomplete):**\n"
                
                # Group by status
                by_status = {}
                for task in tasks:
                    status = task.column.name if task.column else 'Unknown'
                    if status not in by_status:
                        by_status[status] = []
                    by_status[status].append(task)
                
                for status, status_tasks in by_status.items():
                    context += f"  {status}: {len(status_tasks)} tasks\n"
                    for task in status_tasks[:5]:  # Show top 5 per status
                        assignee = task.assigned_to.get_full_name() or task.assigned_to.username if task.assigned_to else 'Unassigned'
                        context += f"    • {task.title} ({assignee}, {task.get_priority_display()})\n"
                
                context += "\n"
            
            return context
        
        except Exception as e:
            logger.error(f"Error getting incomplete tasks context: {e}", exc_info=True)
            return f"Error retrieving incomplete tasks: {str(e)}"
    
    def _get_board_comparison_context(self, prompt):
        """
        Get board comparison data
        Handles questions like: "Compare boards", "Which board has most tasks?", etc.
        
        ALWAYS retrieves and compares actual board data
        """
        try:
            if not self._is_board_comparison_query(prompt):
                return None
            
            # Get user's boards
            user_boards = self._get_user_boards()
            if not user_boards.exists():
                return "You don't have access to any boards yet."
            
            if user_boards.count() == 1:
                return f"You only have access to one board: {user_boards.first().name}"
            
            context = f"**Board Comparison:**\n\n"
            context += f"**Total Boards:** {user_boards.count()}\n\n"
            
            # Collect metrics for each board
            board_stats = []
            for board in user_boards:
                tasks = Task.objects.filter(column__board=board)
                task_count = tasks.count()
                
                # Count completed vs incomplete
                completed = tasks.filter(
                    Q(column__name__icontains='done') | Q(column__name__icontains='closed')
                ).count()
                
                # Count members
                member_count = board.members.count()
                
                # Get last update
                last_task_update = tasks.order_by('-updated_at').first()
                last_update = last_task_update.updated_at if last_task_update else board.updated_at
                
                board_stats.append({
                    'name': board.name,
                    'tasks': task_count,
                    'completed': completed,
                    'incomplete': task_count - completed,
                    'members': member_count,
                    'last_update': last_update,
                    'completion_rate': (100 * completed / task_count) if task_count > 0 else 0
                })
            
            # Sort by task count (descending)
            board_stats.sort(key=lambda x: x['tasks'], reverse=True)
            
            context += "**By Number of Tasks:**\n"
            for i, board in enumerate(board_stats, 1):
                context += f"{i}. **{board['name']}**: {board['tasks']} tasks "
                context += f"({board['completed']} done, {board['incomplete']} incomplete, "
                context += f"{board['completion_rate']:.1f}% complete)\n"
            
            context += "\n**By Team Size:**\n"
            sorted_by_members = sorted(board_stats, key=lambda x: x['members'], reverse=True)
            for i, board in enumerate(sorted_by_members, 1):
                context += f"{i}. **{board['name']}**: {board['members']} members\n"
            
            context += "\n**By Recent Activity:**\n"
            sorted_by_update = sorted(board_stats, key=lambda x: x['last_update'], reverse=True)
            for i, board in enumerate(sorted_by_update, 1):
                from django.utils import timezone
                time_ago = timezone.now() - board['last_update']
                days_ago = time_ago.days
                if days_ago == 0:
                    time_str = "Today"
                elif days_ago == 1:
                    time_str = "Yesterday"
                else:
                    time_str = f"{days_ago} days ago"
                context += f"{i}. **{board['name']}**: Last updated {time_str}\n"
            
            return context
        
        except Exception as e:
            logger.error(f"Error getting board comparison context: {e}", exc_info=True)
            return f"Error comparing boards: {str(e)}"
    
    def _get_task_distribution_context(self, prompt):
        """
        Get task distribution by assignee
        Handles questions like: "Show task distribution", "Who has most tasks?", etc.
        
        ALWAYS retrieves and calculates actual task distribution
        """
        try:
            if not self._is_task_distribution_query(prompt):
                return None
            
            # Get user's boards
            user_boards = self._get_user_boards()
            if not user_boards.exists():
                return "You don't have access to any boards yet."
            
            # Get all tasks
            all_tasks = Task.objects.filter(column__board__in=user_boards)
            
            if not all_tasks.exists():
                return "No tasks found in your boards."
            
            # Count tasks by assignee
            from django.db.models import Count
            task_distribution = all_tasks.values(
                'assigned_to__first_name',
                'assigned_to__last_name',
                'assigned_to__username'
            ).annotate(
                task_count=Count('id')
            ).order_by('-task_count')
            
            # Count unassigned tasks
            unassigned_count = all_tasks.filter(assigned_to__isnull=True).count()
            
            context = f"**Task Distribution by Assignee:**\n\n"
            context += f"**Total Tasks:** {all_tasks.count()}\n"
            context += f"**Assigned:** {all_tasks.count() - unassigned_count}\n"
            context += f"**Unassigned:** {unassigned_count}\n\n"
            
            if task_distribution:
                context += "**Tasks per Team Member:**\n"
                for i, assignee in enumerate(task_distribution, 1):
                    first_name = assignee['assigned_to__first_name'] or ''
                    last_name = assignee['assigned_to__last_name'] or ''
                    username = assignee['assigned_to__username']
                    
                    if first_name or last_name:
                        name = f"{first_name} {last_name}".strip()
                    else:
                        name = username or 'Unassigned'
                    
                    task_count = assignee['task_count']
                    percentage = 100 * task_count / all_tasks.count()
                    
                    context += f"{i}. **{name}**: {task_count} tasks ({percentage:.1f}%)\n"
            
            # Check for workload imbalance
            if task_distribution:
                max_tasks = task_distribution[0]['task_count']
                min_tasks = task_distribution[len(task_distribution)-1]['task_count']
                if max_tasks > 2 * min_tasks and len(task_distribution) > 1:
                    context += "\n⚠️ **Workload Imbalance Detected:** "
                    context += f"Highest workload ({max_tasks} tasks) is more than 2x the lowest ({min_tasks} tasks)\n"
            
            return context
        
        except Exception as e:
            logger.error(f"Error getting task distribution context: {e}", exc_info=True)
            return f"Error calculating task distribution: {str(e)}"
    
    def _get_progress_metrics_context(self, prompt):
        """
        Get progress metrics across tasks
        Handles questions like: "What's the average progress?", "How complete are tasks?", etc.
        
        ALWAYS calculates and returns actual progress data
        """
        try:
            if not self._is_progress_query(prompt):
                return None
            
            # Get user's boards
            user_boards = self._get_user_boards()
            if not user_boards.exists():
                return "You don't have access to any boards yet."
            
            # Get all tasks
            all_tasks = Task.objects.filter(column__board__in=user_boards)
            
            if not all_tasks.exists():
                return "No tasks found in your boards."
            
            # Calculate progress metrics
            from django.db.models import Avg, Max, Min
            avg_progress = all_tasks.aggregate(Avg('progress'))['progress__avg'] or 0
            max_progress = all_tasks.aggregate(Max('progress'))['progress__max'] or 0
            min_progress = all_tasks.aggregate(Min('progress'))['progress__min'] or 0
            
            # Count by completion status
            completed = all_tasks.filter(
                Q(column__name__icontains='done') | Q(column__name__icontains='closed')
            ).count()
            in_progress = all_tasks.filter(progress__gt=0, progress__lt=100).exclude(
                Q(column__name__icontains='done') | Q(column__name__icontains='closed')
            ).count()
            not_started = all_tasks.filter(progress=0).count()
            
            total = all_tasks.count()
            
            context = f"**Progress Metrics:**\n\n"
            context += f"**Overall Statistics:**\n"
            context += f"  - Total Tasks: {total}\n"
            context += f"  - Average Progress: {avg_progress:.1f}%\n"
            context += f"  - Highest Progress: {max_progress}%\n"
            context += f"  - Lowest Progress: {min_progress}%\n\n"
            
            context += f"**Task Status Distribution:**\n"
            context += f"  - Completed: {completed} ({100*completed/total:.1f}%)\n"
            context += f"  - In Progress: {in_progress} ({100*in_progress/total:.1f}%)\n"
            context += f"  - Not Started: {not_started} ({100*not_started/total:.1f}%)\n\n"
            
            # Progress by board
            context += f"**Progress by Board:**\n"
            for board in user_boards:
                board_tasks = all_tasks.filter(column__board=board)
                if board_tasks.exists():
                    board_avg = board_tasks.aggregate(Avg('progress'))['progress__avg'] or 0
                    board_completed = board_tasks.filter(
                        Q(column__name__icontains='done') | Q(column__name__icontains='closed')
                    ).count()
                    board_total = board_tasks.count()
                    context += f"  - **{board.name}**: {board_avg:.1f}% average "
                    context += f"({board_completed}/{board_total} completed)\n"
            
            return context
        
        except Exception as e:
            logger.error(f"Error getting progress metrics context: {e}", exc_info=True)
            return f"Error calculating progress: {str(e)}"
    
    def _get_overdue_tasks_context(self, prompt):
        """
        Get overdue and upcoming deadline tasks
        Handles questions like: "Show overdue tasks", "What's due soon?", etc.
        
        ALWAYS retrieves tasks with due dates and calculates overdue status
        """
        try:
            if not self._is_overdue_query(prompt):
                return None
            
            # Get user's boards
            user_boards = self._get_user_boards()
            if not user_boards.exists():
                return "You don't have access to any boards yet."
            
            from django.utils import timezone
            from datetime import timedelta
            
            today = timezone.now().date()
            week_from_now = today + timedelta(days=7)
            
            # Get all tasks with due dates
            tasks_with_dates = Task.objects.filter(
                column__board__in=user_boards,
                due_date__isnull=False
            ).select_related('assigned_to', 'column', 'column__board').order_by('due_date')
            
            if not tasks_with_dates.exists():
                return "No tasks have due dates set."
            
            # Categorize tasks
            overdue = tasks_with_dates.filter(due_date__lt=today).exclude(
                Q(column__name__icontains='done') | Q(column__name__icontains='closed')
            )
            due_today = tasks_with_dates.filter(due_date=today).exclude(
                Q(column__name__icontains='done') | Q(column__name__icontains='closed')
            )
            due_soon = tasks_with_dates.filter(
                due_date__gt=today,
                due_date__lte=week_from_now
            ).exclude(
                Q(column__name__icontains='done') | Q(column__name__icontains='closed')
            )
            
            context = f"**Task Deadlines Analysis:**\n\n"
            
            if overdue.exists():
                context += f"⚠️ **OVERDUE TASKS ({overdue.count()}):**\n"
                for task in overdue[:10]:
                    days_overdue = (today - task.due_date).days
                    assignee = task.assigned_to.get_full_name() or task.assigned_to.username if task.assigned_to else 'Unassigned'
                    context += f"  • **{task.title}**\n"
                    context += f"    - Due: {task.due_date} ({days_overdue} day{'s' if days_overdue != 1 else ''} overdue)\n"
                    context += f"    - Assigned: {assignee}\n"
                    context += f"    - Board: {task.column.board.name if task.column else 'Unknown'}\n"
                    context += f"    - Status: {task.column.name if task.column else 'Unknown'}\n"
                    context += f"    - Priority: {task.get_priority_display()}\n\n"
            else:
                context += "✓ **No Overdue Tasks**\n\n"
            
            if due_today.exists():
                context += f"📅 **DUE TODAY ({due_today.count()}):**\n"
                for task in due_today:
                    assignee = task.assigned_to.get_full_name() or task.assigned_to.username if task.assigned_to else 'Unassigned'
                    context += f"  • {task.title} ({assignee}, {task.get_priority_display()})\n"
                context += "\n"
            
            if due_soon.exists():
                context += f"📆 **DUE WITHIN 7 DAYS ({due_soon.count()}):**\n"
                for task in due_soon[:10]:
                    days_until = (task.due_date - today).days
                    assignee = task.assigned_to.get_full_name() or task.assigned_to.username if task.assigned_to else 'Unassigned'
                    context += f"  • {task.title}\n"
                    context += f"    - Due: {task.due_date} (in {days_until} day{'s' if days_until != 1 else ''})\n"
                    context += f"    - Assigned: {assignee}, Priority: {task.get_priority_display()}\n"
                context += "\n"
            
            # Summary
            total_with_dates = tasks_with_dates.count()
            context += f"**Summary:**\n"
            context += f"  - Total Tasks with Due Dates: {total_with_dates}\n"
            context += f"  - Overdue: {overdue.count()}\n"
            context += f"  - Due Today: {due_today.count()}\n"
            context += f"  - Due Within 7 Days: {due_soon.count()}\n"
            
            return context
        
        except Exception as e:
            logger.error(f"Error getting overdue tasks context: {e}", exc_info=True)
            return f"Error retrieving deadline information: {str(e)}"
    
    def _is_strategic_query(self, prompt):
        """
        Detect if query is asking for strategic advice, best practices, or how-to guidance
        These queries benefit from RAG + project context
        """
        strategic_keywords = [
            'how to', 'how can', 'how should', 'what should', 'best way to',
            'best practice', 'best practices', 'advice', 'guidance', 'recommend',
            'suggestion', 'tips', 'strategy', 'strategies', 'approach',
            'tackle', 'handle', 'manage', 'deal with', 'solve', 'improve',
            'optimize', 'enhance', 'better', 'effective', 'efficient',
            'successful', 'proven method', 'industry standard', 'expert advice'
        ]
        return any(kw in prompt.lower() for kw in strategic_keywords)
    
    def _get_user_boards(self, organization=None):
        """Helper to get user's boards with optional organization filter"""
        try:
            if not organization:
                organization = self.user.profile.organization
        except:
            organization = None
        
        if organization:
            return Board.objects.filter(
                Q(organization=organization) & 
                (Q(created_by=self.user) | Q(members=self.user))
            ).distinct()
        else:
            return Board.objects.filter(
                Q(created_by=self.user) | Q(members=self.user)
            ).distinct()
    
    def _get_organization_context(self, prompt):
        """
        Get organization information for org-related queries
        Handles questions like: "How many organizations?", "List organizations", etc.
        
        ALWAYS retrieves and returns actual organization data instead of asking questions
        """
        try:
            if not self._is_organization_query(prompt):
                return None
            
            # Import Organization model
            from accounts.models import Organization
            
            context = "**Organization Information:**\n\n"
            
            # Get ALL organizations the user has access to
            # Priority order:
            # 1. Organizations where user is member or creator
            # 2. Organizations accessible through boards
            # 3. User's primary organization from profile
            
            orgs = Organization.objects.filter(
                Q(created_by=self.user) | Q(members=self.user)
            ).distinct()
            
            # If no direct membership, try to get from boards
            if not orgs.exists():
                user_boards = self._get_user_boards()
                if user_boards.exists():
                    orgs = Organization.objects.filter(boards__in=user_boards).distinct()
            
            # Final fallback: user's profile organization
            if not orgs.exists():
                try:
                    if hasattr(self.user, 'profile') and self.user.profile.organization:
                        orgs = Organization.objects.filter(id=self.user.profile.organization.id)
                except:
                    pass
            
            if not orgs.exists():
                context += "**You currently have no organizations.**\n"
                context += "You can create a new organization or join an existing one.\n"
                return context
            
            # Build comprehensive organization data
            context += f"**Total Organizations:** {orgs.count()}\n\n"
            
            for org in orgs:
                # Get detailed metrics
                boards_count = Board.objects.filter(organization=org).count()
                members_count = org.members.count()
                
                # Get user-accessible boards in this org
                user_boards_in_org = Board.objects.filter(
                    organization=org
                ).filter(
                    Q(created_by=self.user) | Q(members=self.user)
                ).distinct()
                
                context += f"**{org.name}**\n"
                if org.domain:
                    context += f"  - Domain: {org.domain}\n"
                context += f"  - Total Boards: {boards_count}\n"
                if user_boards_in_org.count() != boards_count:
                    context += f"  - Your Boards: {user_boards_in_org.count()}\n"
                context += f"  - Members: {members_count}\n"
                context += f"  - Created: {org.created_at.strftime('%Y-%m-%d')}\n"
                context += f"  - Created by: {org.created_by.get_full_name() or org.created_by.username}\n"
                
                # List board names if manageable
                if user_boards_in_org.count() > 0 and user_boards_in_org.count() <= 5:
                    board_names = [b.name for b in user_boards_in_org]
                    context += f"  - Board Names: {', '.join(board_names)}\n"
                
                context += "\n"
            
            return context
        
        except Exception as e:
            logger.error(f"Error getting organization context: {e}", exc_info=True)
            return f"Error retrieving organization data: {str(e)}"
    
    def _get_critical_tasks_context(self, prompt):
        """
        Get critical/high-risk/high-priority tasks
        Handles questions like: "How many tasks are critical?", "Show critical tasks", etc.
        """
        try:
            if not self._is_critical_task_query(prompt):
                return None
            
            # Get user's boards
            user_boards = self._get_user_boards()
            if not user_boards.exists():
                logger.warning(f"User {self.user} has no accessible boards")
                return None
            
            # Query critical tasks by multiple criteria
            critical_tasks = Task.objects.filter(
                column__board__in=user_boards
            ).filter(
                Q(risk_level__in=['high', 'critical']) |  # Explicit risk level
                Q(priority='urgent') |  # Urgent priority
                Q(ai_risk_score__gte=80) |  # High AI risk score
                Q(labels__name__icontains='critical') |  # Critical label
                Q(labels__name__icontains='blocker')  # Blocker label
            ).select_related('assigned_to', 'column', 'column__board').distinct().order_by('-ai_risk_score', '-priority')
            
            if not critical_tasks.exists():
                logger.info(f"No critical tasks found for user {self.user}")
                return "No critical tasks currently identified."
            
            context = f"**Critical Tasks Analysis:**\n\n"
            context += f"**Total Critical Tasks:** {critical_tasks.count()}\n\n"
            
            # Group by severity
            by_risk_level = {}
            for task in critical_tasks:
                risk_level = task.risk_level or 'Unknown'
                if risk_level not in by_risk_level:
                    by_risk_level[risk_level] = []
                by_risk_level[risk_level].append(task)
            
            for level in ['critical', 'high', 'medium', 'low', 'Unknown']:
                if level in by_risk_level:
                    context += f"\n**{level.upper()} Risk ({len(by_risk_level[level])}):**\n"
                    for task in by_risk_level[level][:5]:  # Show top 5 per level
                        context += f"  • **{task.title}**\n"
                        context += f"    - Board: {task.column.board.name if task.column else 'Unknown'}\n"
                        context += f"    - Status: {task.column.name if task.column else 'Unknown'}\n"
                        context += f"    - Assigned: {task.assigned_to.get_full_name() or task.assigned_to.username if task.assigned_to else 'Unassigned'}\n"
                        context += f"    - Priority: {task.get_priority_display()}\n"
                        
                        if task.risk_level:
                            context += f"    - Risk Level: {task.risk_level.upper()}\n"
                        if task.ai_risk_score:
                            context += f"    - AI Risk Score: {task.ai_risk_score}/100\n"
                        if task.risk_score:
                            context += f"    - Risk Score: {task.risk_score}/9\n"
                        
                        context += "\n"
            
            return context
        
        except Exception as e:
            logger.error(f"Error getting critical tasks context: {e}")
            return None
    
    def _get_risk_context(self, prompt):
        """
        Get risk management data for risk-related queries
        Includes high-risk tasks, indicators, and mitigation strategies
        """
        try:
            if not self._is_risk_query(prompt):
                return None
            
            # Get user's boards
            user_boards = self._get_user_boards()
            if not user_boards.exists():
                return None
            
            # Get high-risk tasks
            high_risk_tasks = Task.objects.filter(
                column__board__in=user_boards,
                risk_level__in=['high', 'critical']
            ).select_related('assigned_to', 'column').order_by('-risk_score')[:15]
            
            # If no explicitly high-risk tasks, try AI risk score
            if not high_risk_tasks.exists():
                high_risk_tasks = Task.objects.filter(
                    column__board__in=user_boards
                ).filter(ai_risk_score__gte=70).select_related(
                    'assigned_to', 'column'
                ).order_by('-ai_risk_score')[:15]
            
            if not high_risk_tasks.exists():
                return None
            
            context = f"""**Risk Management Analysis:**

**High-Risk Tasks:** {len(high_risk_tasks)} identified

"""
            
            for task in high_risk_tasks:
                context += f"• **{task.title}**\n"
                context += f"  - Board: {task.column.board.name if task.column else 'Unknown'}\n"
                context += f"  - Status: {task.column.name if task.column else 'Unknown'}\n"
                context += f"  - Assigned: {task.assigned_to.get_full_name() or task.assigned_to.username if task.assigned_to else 'Unassigned'}\n"
                
                if task.risk_level:
                    context += f"  - Risk Level: {task.risk_level.upper()}\n"
                if task.risk_score:
                    context += f"  - Risk Score: {task.risk_score}/9\n"
                if hasattr(task, 'ai_risk_score') and task.ai_risk_score:
                    context += f"  - AI Risk Score: {task.ai_risk_score}/100\n"
                
                # Risk indicators
                if hasattr(task, 'risk_indicators') and task.risk_indicators:
                    indicators = task.risk_indicators[:3] if isinstance(task.risk_indicators, list) else [task.risk_indicators]
                    context += f"  - Indicators: {', '.join(str(i) for i in indicators)}\n"
                
                # Mitigation
                if hasattr(task, 'mitigation_suggestions') and task.mitigation_suggestions:
                    mitigations = task.mitigation_suggestions if isinstance(task.mitigation_suggestions, list) else [task.mitigation_suggestions]
                    context += f"  - Mitigation: {mitigations[0]}\n"
                
                # Dependencies
                if task.parent_task:
                    context += f"  - Depends On: {task.parent_task.title}\n"
                
                context += "\n"
            
            return context
        
        except Exception as e:
            logger.error(f"Error getting risk context: {e}")
            return None
    
    def _get_mitigation_context(self, prompt, board=None):
        """
        Get risk mitigation strategies and action plans
        Handles questions like: "What are mitigation strategies?", "How to reduce risks?", etc.
        Can optionally filter by board if specified in the prompt
        """
        try:
            if not self._is_mitigation_query(prompt):
                return None
            
            # Get user's boards
            user_boards = self._get_user_boards()
            if not user_boards.exists():
                logger.debug(f"User {self.user} has no boards for mitigation context")
                return None
            
            # Check if user is asking about a specific board
            specific_board = None
            if board:
                specific_board = board
            else:
                # Try to extract board name from prompt
                for user_board in user_boards:
                    if user_board.name.lower() in prompt.lower():
                        specific_board = user_board
                        break
            
            # Get high-risk tasks that have mitigation suggestions
            if specific_board:
                risk_tasks = Task.objects.filter(
                    column__board=specific_board,
                    mitigation_suggestions__isnull=False
                ).exclude(
                    mitigation_suggestions__exact='[]'
                ).filter(
                    Q(risk_level__in=['high', 'critical']) |
                    Q(ai_risk_score__gte=70) |
                    Q(priority='urgent')
                ).select_related('assigned_to', 'column', 'column__board').order_by('-ai_risk_score', '-risk_score')
            else:
                # Get across all user's boards
                risk_tasks = Task.objects.filter(
                    column__board__in=user_boards,
                    mitigation_suggestions__isnull=False
                ).exclude(
                    mitigation_suggestions__exact='[]'
                ).filter(
                    Q(risk_level__in=['high', 'critical']) |
                    Q(ai_risk_score__gte=70) |
                    Q(priority='urgent')
                ).select_related('assigned_to', 'column', 'column__board').order_by('-ai_risk_score', '-risk_score')
            
            if not risk_tasks.exists():
                logger.debug(f"No tasks with mitigation strategies found for user {self.user}")
                return None
            
            # Build comprehensive mitigation context
            if specific_board:
                context = f"**Risk Mitigation Strategies - {specific_board.name} Board:**\n\n"
            else:
                context = "**Risk Mitigation Strategies (All Projects):**\n\n"
            
            context += f"**Tasks with Mitigation Plans:** {len(risk_tasks)}\n\n"
            
            # Group by risk level
            tasks_by_risk = {}
            for task in risk_tasks:
                risk_level = task.risk_level or 'Unknown'
                if risk_level not in tasks_by_risk:
                    tasks_by_risk[risk_level] = []
                tasks_by_risk[risk_level].append(task)
            
            # Present mitigation strategies organized by risk level
            for risk_level in ['critical', 'high', 'medium', 'low', 'Unknown']:
                if risk_level in tasks_by_risk:
                    risk_tasks_list = tasks_by_risk[risk_level]
                    context += f"**{risk_level.upper()} RISK TASKS ({len(risk_tasks_list)}):**\n\n"
                    
                    for task in risk_tasks_list[:10]:  # Limit to 10 per risk level
                        context += f"**Task:** {task.title}\n"
                        context += f"  - Board: {task.column.board.name if task.column else 'Unknown'}\n"
                        context += f"  - Status: {task.column.name if task.column else 'Unknown'}\n"
                        context += f"  - Assigned To: {task.assigned_to.get_full_name() or task.assigned_to.username if task.assigned_to else 'Unassigned'}\n"
                        
                        if task.risk_level:
                            context += f"  - Risk Level: {task.risk_level.upper()}\n"
                        if task.ai_risk_score:
                            context += f"  - AI Risk Score: {task.ai_risk_score}/100\n"
                        if task.risk_score:
                            context += f"  - Risk Score: {task.risk_score}/9\n"
                        
                        # Risk indicators/drivers
                        if hasattr(task, 'risk_indicators') and task.risk_indicators:
                            indicators = task.risk_indicators if isinstance(task.risk_indicators, list) else [task.risk_indicators]
                            context += f"  - Risk Indicators: {', '.join(str(i) for i in indicators[:3])}\n"
                        
                        # Comprehensive mitigation strategies
                        if hasattr(task, 'mitigation_suggestions') and task.mitigation_suggestions:
                            mitigations = task.mitigation_suggestions if isinstance(task.mitigation_suggestions, list) else [task.mitigation_suggestions]
                            context += f"  - Mitigation Strategies:\n"
                            for i, mitigation in enumerate(mitigations[:5], 1):  # Show up to 5 strategies per task
                                context += f"    {i}. {mitigation}\n"
                        
                        # Risk analysis details
                        if hasattr(task, 'risk_analysis') and task.risk_analysis and isinstance(task.risk_analysis, dict):
                            if 'analysis' in task.risk_analysis:
                                context += f"  - Risk Analysis: {task.risk_analysis['analysis']}\n"
                            if 'factors' in task.risk_analysis:
                                factors = task.risk_analysis['factors']
                                if isinstance(factors, list):
                                    context += f"  - Contributing Factors: {', '.join(factors[:3])}\n"
                        
                        # Impact summary
                        if hasattr(task, 'risk_impact') and task.risk_impact:
                            context += f"  - Potential Impact: {dict([(1, 'Low'), (2, 'Medium'), (3, 'High')]).get(task.risk_impact, 'Unknown')}\n"
                        
                        if hasattr(task, 'risk_likelihood') and task.risk_likelihood:
                            context += f"  - Likelihood: {dict([(1, 'Low'), (2, 'Medium'), (3, 'High')]).get(task.risk_likelihood, 'Unknown')}\n"
                        
                        context += "\n"
            
            return context
        
        except Exception as e:
            logger.error(f"Error getting mitigation context: {e}", exc_info=True)
            return None
    
    def _get_stakeholder_context(self, prompt):
        """
        Get stakeholder management data
        Includes stakeholders, involvement, engagement metrics
        """
        if not HAS_STAKEHOLDER_MODELS:
            return None
        
        try:
            if not self._is_stakeholder_query(prompt):
                return None
            
            # Get user's boards
            user_boards = self._get_user_boards()
            if not user_boards.exists():
                return None
            
            # Get stakeholders for user's projects
            stakeholders = ProjectStakeholder.objects.filter(
                board__in=user_boards
            ).select_related('user', 'board').order_by('board', 'engagement_level')[:20]
            
            if not stakeholders.exists():
                return None
            
            context = f"""**Stakeholder Management:**

**Stakeholders:** {len(stakeholders)} identified

"""
            
            for stakeholder in stakeholders:
                context += f"• **{stakeholder.user.get_full_name() or stakeholder.user.username}**\n"
                context += f"  - Board: {stakeholder.board.name}\n"
                context += f"  - Role: {stakeholder.role if hasattr(stakeholder, 'role') else 'Team Member'}\n"
                
                if hasattr(stakeholder, 'engagement_level'):
                    context += f"  - Engagement Level: {stakeholder.engagement_level}\n"
                if hasattr(stakeholder, 'engagement_score'):
                    context += f"  - Engagement Score: {stakeholder.engagement_score}\n"
                
                # Get task involvement
                if HAS_STAKEHOLDER_MODELS:
                    try:
                        involvement = StakeholderTaskInvolvement.objects.filter(
                            stakeholder=stakeholder
                        ).count()
                        if involvement > 0:
                            context += f"  - Tasks Involved: {involvement}\n"
                    except:
                        pass
                
                context += "\n"
            
            return context
        
        except Exception as e:
            logger.error(f"Error getting stakeholder context: {e}")
            return None
    
    def _get_resource_context(self, prompt):
        """
        Get resource management and forecasting data
        Includes capacity alerts, demand forecasts, workload recommendations
        """
        if not HAS_RESOURCE_MODELS:
            return None
        
        try:
            if not self._is_resource_query(prompt):
                return None
            
            # Get user's boards
            user_boards = self._get_user_boards()
            if not user_boards.exists():
                return None
            
            context = "**Resource Management & Forecasting:**\n\n"
            
            # Get capacity alerts
            try:
                alerts = TeamCapacityAlert.objects.filter(
                    board__in=user_boards,
                    is_resolved=False
                ).select_related('board', 'team_member').order_by('-created_at')[:10]
                
                if alerts.exists():
                    context += f"**Team Capacity Alerts ({len(alerts)}):**\n"
                    for alert in alerts:
                        context += f"  - {alert.team_member.get_full_name() if hasattr(alert, 'team_member') else 'Team'}: "
                        context += f"{alert.alert_message if hasattr(alert, 'alert_message') else 'Capacity alert'}\n"
                    context += "\n"
            except:
                pass
            
            # Get demand forecasts
            try:
                forecasts = ResourceDemandForecast.objects.filter(
                    board__in=user_boards
                ).order_by('-forecast_date')[:10]
                
                if forecasts.exists():
                    context += f"**Resource Demand Forecasts ({len(forecasts)}):**\n"
                    for forecast in forecasts:
                        context += f"  - Period: {forecast.forecast_date if hasattr(forecast, 'forecast_date') else 'Unknown'}\n"
                        if hasattr(forecast, 'expected_resource_requirement'):
                            context += f"    Resources Needed: {forecast.expected_resource_requirement}\n"
                        if hasattr(forecast, 'confidence_level'):
                            context += f"    Confidence: {forecast.confidence_level}%\n"
                    context += "\n"
            except:
                pass
            
            # Get workload recommendations
            try:
                recommendations = WorkloadDistributionRecommendation.objects.filter(
                    board__in=user_boards
                ).order_by('-created_at')[:5]
                
                if recommendations.exists():
                    context += f"**Workload Recommendations ({len(recommendations)}):**\n"
                    for rec in recommendations:
                        if hasattr(rec, 'recommendation_text'):
                            context += f"  - {rec.recommendation_text}\n"
                        if hasattr(rec, 'expected_impact'):
                            context += f"    Impact: {rec.expected_impact}\n"
            except:
                pass
            
            return context if "**Resource" in context else None
        
        except Exception as e:
            logger.error(f"Error getting resource context: {e}")
            return None
    
    def _get_lean_context(self, prompt):
        """
        Get Lean Six Sigma data
        Includes value-added vs waste analysis, efficiency metrics
        """
        try:
            if not self._is_lean_query(prompt):
                return None
            
            # Get user's boards
            user_boards = self._get_user_boards()
            if not user_boards.exists():
                return None
            
            # Get all tasks
            all_tasks = Task.objects.filter(column__board__in=user_boards)
            
            # Try to get tasks by label category (Lean Six Sigma)
            va_tasks = all_tasks.filter(
                labels__name__icontains='value-added'
            ).distinct().count()
            
            nva_tasks = all_tasks.filter(
                labels__name__icontains='necessary'
            ).distinct().count()
            
            waste_tasks = all_tasks.filter(
                labels__name__icontains='waste'
            ).distinct().count()
            
            if va_tasks + nva_tasks + waste_tasks == 0:
                return None
            
            total_categorized = va_tasks + nva_tasks + waste_tasks
            
            context = f"""**Lean Six Sigma Analysis:**

**Task Value Classification:**
- **Value-Added Tasks:** {va_tasks} ({100*va_tasks/total_categorized:.1f}%)
- **Necessary Non-Value-Added:** {nva_tasks} ({100*nva_tasks/total_categorized:.1f}%)
- **Waste/Eliminate:** {waste_tasks} ({100*waste_tasks/total_categorized:.1f}%)

**Recommendations:**
1. Focus on increasing Value-Added work (currently {100*va_tasks/total_categorized:.1f}%)
2. Review Necessary NVA tasks for optimization opportunities
3. Prioritize elimination of waste tasks ({waste_tasks} identified)
"""
            
            return context
        
        except Exception as e:
            logger.error(f"Error getting lean context: {e}")
            return None
    
    def _get_dependency_context(self, prompt):
        """
        Get task dependency and relationship data
        Includes critical chains, blocked tasks, subtasks
        """
        try:
            if not self._is_dependency_query(prompt):
                return None
            
            # Get user's boards
            user_boards = self._get_user_boards()
            if not user_boards.exists():
                return None
            
            # Get tasks with dependencies
            tasks_with_parent = Task.objects.filter(
                column__board__in=user_boards,
                parent_task__isnull=False
            ).select_related('parent_task', 'column')[:15]
            
            # Get tasks with child tasks (subtasks)
            tasks_with_children = Task.objects.filter(
                column__board__in=user_boards,
                subtasks__isnull=False
            ).select_related('column').distinct()[:10]
            
            if not tasks_with_parent.exists() and not tasks_with_children.exists():
                return None
            
            context = "**Task Dependencies & Relationships:**\n\n"
            
            if tasks_with_parent.exists():
                context += f"**Tasks with Dependencies ({len(tasks_with_parent)}):**\n"
                for task in tasks_with_parent:
                    context += f"• {task.title}\n"
                    context += f"  - Depends On: {task.parent_task.title}\n"
                    context += f"  - Parent Status: {task.parent_task.column.name if task.parent_task.column else 'Unknown'}\n"
                    if task.column:
                        context += f"  - Status: {task.column.name}\n"
                    context += "\n"
            
            if tasks_with_children.exists():
                context += f"\n**Tasks with Subtasks ({len(tasks_with_children)}):**\n"
                for task in tasks_with_children:
                    child_count = task.subtasks.count() if hasattr(task, 'subtasks') else 0
                    context += f"• {task.title} ({child_count} subtasks)\n"
            
            return context
        
        except Exception as e:
            logger.error(f"Error getting dependency context: {e}")
            return None
    
    def generate_system_prompt(self):
        """Generate system prompt for AI model"""
        return """You are TaskFlow AI Project Assistant, an intelligent project management assistant. 
Your role is to help project managers and team members with:
- Project planning and strategy
- Task management and prioritization
- Team resource allocation and workload management
- Risk identification and mitigation
- Timeline optimization and scheduling
- Report generation and insights
- Best practices and recommendations

CRITICAL INSTRUCTIONS FOR DATA-DRIVEN RESPONSES:
1. **ALWAYS USE PROVIDED CONTEXT DATA**: When project data is provided in the "Available Context Data" section, you MUST use it to answer questions directly and specifically
2. **NEVER ASK FOR INFORMATION YOU HAVE**: If context data contains the answer, provide it immediately without asking follow-up questions
3. **BE SPECIFIC AND CONCRETE**: Use actual numbers, names, dates from the context data - not general statements
4. **ANSWER DIRECTLY FIRST**: Start with the specific answer from the data, then provide additional insights or recommendations
5. **NO UNNECESSARY QUESTIONS**: Don't ask "What is your name?" or "Which board?" if the context already identifies the user or scope

RESPONSE STRUCTURE:
- For data queries (counts, lists, status): Provide the specific data FIRST, then optionally add insights
- For strategic questions (how-to, best practices): Combine web search results (if available) with project-specific recommendations
- For risk/mitigation: Give both general best practices AND specific actions based on actual project data
- Always be actionable - provide clear next steps

EXAMPLES OF CORRECT BEHAVIOR:
❌ WRONG: "To show your tasks, I need to know your username"
✓ RIGHT: "You have 5 tasks assigned: [list from context data]"

❌ WRONG: "How many organizations would you like to see?"
✓ RIGHT: "You have 1 organization: Dev Team (2 boards, 6 members)"

❌ WRONG: "I'm ready to help. What would you like to know?"
✓ RIGHT: [Directly provide the requested data from context]

Format responses clearly with:
- Bullet points for lists
- **Bold** for emphasis and headers
- Specific numbers and metrics
- Actionable recommendations

When context data is limited, acknowledge it briefly but still provide valuable strategic guidance based on project management best practices."""
    
    def get_response(self, prompt, use_cache=True):
        """
        Get response from chatbot using Gemini in STATELESS mode.
        Each request is completely independent to prevent token accumulation.
        
        Intelligently routes to appropriate context builders based on query type
        
        Args:
            prompt (str): User message
            use_cache (bool): Use cached data for context building (NOT for AI responses)
            
        Returns:
            dict: Response with content, source, and metadata
        """
        try:
            logger.debug(f"Processing prompt: {prompt[:100]}...")
            
            # Detect query types
            is_search_query = self._is_search_query(prompt)
            is_strategic_query = self._is_strategic_query(prompt)
            is_project_query = self._is_project_query(prompt)
            is_aggregate_query = self._is_aggregate_query(prompt)
            is_risk_query = self._is_risk_query(prompt)
            is_stakeholder_query = self._is_stakeholder_query(prompt)
            is_resource_query = self._is_resource_query(prompt)
            is_lean_query = self._is_lean_query(prompt)
            is_dependency_query = self._is_dependency_query(prompt)
            is_organization_query = self._is_organization_query(prompt)
            is_critical_task_query = self._is_critical_task_query(prompt)
            is_mitigation_query = self._is_mitigation_query(prompt)
            is_user_task_query = self._is_user_task_query(prompt)
            is_incomplete_task_query = self._is_incomplete_task_query(prompt)
            is_board_comparison_query = self._is_board_comparison_query(prompt)
            is_task_distribution_query = self._is_task_distribution_query(prompt)
            is_progress_query = self._is_progress_query(prompt)
            is_overdue_query = self._is_overdue_query(prompt)
            
            # Build context in priority order
            context_parts = []
            
            # 1. Organization context (system-wide)
            if is_organization_query:
                org_context = self._get_organization_context(prompt)
                if org_context:
                    context_parts.append(org_context)
                    logger.debug("Added organization context")
            
            # 2. User-specific tasks (high priority - user asking about their tasks)
            if is_user_task_query:
                user_tasks_context = self._get_user_tasks_context(prompt)
                if user_tasks_context:
                    context_parts.append(user_tasks_context)
                    logger.debug("Added user tasks context")
            
            # 3. Incomplete tasks query
            if is_incomplete_task_query:
                incomplete_context = self._get_incomplete_tasks_context(prompt)
                if incomplete_context:
                    context_parts.append(incomplete_context)
                    logger.debug("Added incomplete tasks context")
            
            # 4. Board comparison
            if is_board_comparison_query:
                comparison_context = self._get_board_comparison_context(prompt)
                if comparison_context:
                    context_parts.append(comparison_context)
                    logger.debug("Added board comparison context")
            
            # 5. Task distribution
            if is_task_distribution_query:
                distribution_context = self._get_task_distribution_context(prompt)
                if distribution_context:
                    context_parts.append(distribution_context)
                    logger.debug("Added task distribution context")
            
            # 6. Progress metrics
            if is_progress_query:
                progress_context = self._get_progress_metrics_context(prompt)
                if progress_context:
                    context_parts.append(progress_context)
                    logger.debug("Added progress metrics context")
            
            # 7. Overdue tasks
            if is_overdue_query:
                overdue_context = self._get_overdue_tasks_context(prompt)
                if overdue_context:
                    context_parts.append(overdue_context)
                    logger.debug("Added overdue tasks context")
            
            # 8. Mitigation context (high priority - directly answers mitigation questions)
            if is_mitigation_query:
                mitigation_context = self._get_mitigation_context(prompt, board=self.board)
                if mitigation_context:
                    context_parts.append(mitigation_context)
                    logger.debug("Added mitigation context")
            
            # 9. Critical tasks context
            if (is_critical_task_query or is_risk_query) and not is_mitigation_query:
                critical_context = self._get_critical_tasks_context(prompt)
                if critical_context:
                    context_parts.append(critical_context)
                    logger.debug("Added critical tasks context")
            
            # 10. Aggregate context (system-wide queries)
            if is_aggregate_query:
                aggregate_context = self._get_aggregate_context(prompt)
                if aggregate_context:
                    context_parts.append(aggregate_context)
                    logger.debug("Added aggregate context")
            
            # 11. Risk context
            if is_risk_query and not is_critical_task_query and not is_mitigation_query:  # Avoid duplication
                risk_context = self._get_risk_context(prompt)
                if risk_context:
                    context_parts.append(risk_context)
                    logger.debug("Added risk context")
            
            # 12. Stakeholder context
            if is_stakeholder_query:
                stakeholder_context = self._get_stakeholder_context(prompt)
                if stakeholder_context:
                    context_parts.append(stakeholder_context)
                    logger.debug("Added stakeholder context")
            
            # 13. Resource context
            if is_resource_query:
                resource_context = self._get_resource_context(prompt)
                if resource_context:
                    context_parts.append(resource_context)
                    logger.debug("Added resource context")
            
            # 14. Lean context
            if is_lean_query:
                lean_context = self._get_lean_context(prompt)
                if lean_context:
                    context_parts.append(lean_context)
                    logger.debug("Added lean context")
            
            # 15. Dependency context
            if is_dependency_query:
                dependency_context = self._get_dependency_context(prompt)
                if dependency_context:
                    context_parts.append(dependency_context)
                    logger.debug("Added dependency context")
            
            # 16. General project context (if not already covered by specialized contexts)
            if is_project_query and not context_parts:
                taskflow_context = self.get_taskflow_context(use_cache)
                if taskflow_context:
                    context_parts.append(taskflow_context)
                    logger.debug("Added general project context")
            
            # 17. Knowledge base context
            kb_context = self.get_knowledge_base_context(prompt)
            if kb_context:
                context_parts.append(kb_context)
                logger.debug("Added KB context")
            
            # 18. Web search context for research and strategic queries
            search_context = ""
            used_web_search = False
            search_sources = []
            
            # Trigger web search for search queries OR strategic queries (how-to, best practices, etc.)
            if (is_search_query or is_strategic_query) and getattr(settings, 'ENABLE_WEB_SEARCH', False):
                try:
                    search_context = self.search_client.get_search_context(prompt, max_results=3)
                    if search_context:  # Only add if we got results (None = failed)
                        context_parts.append(search_context)
                        used_web_search = True
                        # Extract sources
                        for line in search_context.split('\n'):
                            if 'Source' in line or 'URL:' in line:
                                search_sources.append(line)
                        logger.debug(f"Added web search context (triggered by: {'strategic query' if is_strategic_query else 'search query'})")
                    else:
                        logger.info(f"Web search failed or returned no results - AI will use project data and general knowledge")
                except Exception as e:
                    logger.warning(f"Web search failed: {e} - AI will provide answer using project data and general knowledge")
            
            # Build system prompt
            system_prompt = self.generate_system_prompt()
            if context_parts:
                system_prompt += "\n\n**Available Context Data:**\n" + "\n".join(context_parts)
                logger.debug(f"Built context with {len(context_parts)} parts")
            else:
                logger.debug("No specific context found for query")
            
            # Get response from Gemini (STATELESS - no history maintained)
            response = self.gemini_client.get_response(prompt, system_prompt)
            
            return {
                'response': response['content'],
                'source': 'gemini',
                'tokens': response.get('tokens', 0),
                'error': response.get('error'),
                'used_web_search': used_web_search,
                'search_sources': search_sources,
                'context': {
                    'is_project_query': is_project_query,
                    'is_search_query': is_search_query,
                    'is_strategic_query': is_strategic_query,
                    'is_aggregate_query': is_aggregate_query,
                    'is_risk_query': is_risk_query,
                    'is_stakeholder_query': is_stakeholder_query,
                    'is_resource_query': is_resource_query,
                    'is_lean_query': is_lean_query,
                    'is_dependency_query': is_dependency_query,
                    'is_organization_query': is_organization_query,
                    'is_critical_task_query': is_critical_task_query,
                    'is_mitigation_query': is_mitigation_query,
                    'is_user_task_query': is_user_task_query,
                    'is_incomplete_task_query': is_incomplete_task_query,
                    'is_board_comparison_query': is_board_comparison_query,
                    'is_task_distribution_query': is_task_distribution_query,
                    'is_progress_query': is_progress_query,
                    'is_overdue_query': is_overdue_query,
                    'context_provided': bool(context_parts)
                }
            }
        
        except Exception as e:
            logger.error(f"Error in chatbot service: {e}", exc_info=True)
            return {
                'response': f"I encountered an error: {str(e)}. Please try again.",
                'source': 'error',
                'tokens': 0,
                'error': str(e),
                'used_web_search': False,
                'search_sources': [],
                'context': {}
            }
    
    def generate_project_report(self, board_id):
        """Generate AI-powered project report"""
        try:
            board = Board.objects.get(id=board_id)
            tasks = Task.objects.filter(column__board=board)
            
            report_prompt = f"""Generate a comprehensive project status report for "{board.name}" based on:
            - Total tasks: {tasks.count()}
            - Completed: {tasks.filter(column__name__icontains='done').count()}
            - In Progress: {tasks.filter(column__name__icontains='progress').count()}
            - Not Started: {tasks.filter(column__name__icontains='todo').count()}
            
            Provide: 1. Overall status, 2. Key achievements, 3. Risks/Blockers, 4. Recommendations
            """
            
            response = self.gemini_client.get_response(report_prompt)
            return response['content']
        
        except Exception as e:
            logger.error(f"Error generating report: {e}")
            return f"Unable to generate report: {str(e)}"
