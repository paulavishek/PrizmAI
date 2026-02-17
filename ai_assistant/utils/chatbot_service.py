import json
import logging
import re
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


# Temperature settings for Spectra's dual-mode responses
# Data/factual queries need low temperature for accuracy
# Conversational queries can use higher temperature for engagement
SPECTRA_TEMPERATURE_MAP = {
    'data_retrieval': 0.3,   # Factual queries - needs accuracy
    'analysis': 0.4,          # Analytical queries - consistent insights
    'action': 0.3,            # Action requests - precise instructions
    'help': 0.5,              # Help/guidance - clear but friendly
    'conversational': 0.7,    # General chat - natural, engaging
}


def classify_spectra_query(prompt: str) -> dict:
    """
    Classify user query to determine appropriate response mode and temperature.
    
    Returns:
        dict with 'type', 'temperature', and 'reasoning'
    """
    prompt_lower = prompt.lower().strip()
    
    # Data retrieval patterns - user wants specific facts/numbers
    data_patterns = [
        r'\bhow many\b', r'\bcount\b', r'\bnumber of\b', r'\btotal\b',
        r'\bstatus\b', r'\bprogress\b', r'\bcompletion\b', r'\blist\b',
        r'\bshow\b', r'\bwhat are\b', r'\bwhich\b', r'\bwho is\b',
        r'\bassigned to\b', r'\bdue date\b', r'\bdeadline\b', r'\boverdue\b',
        r'\bblocked\b', r'\bmetric\b', r'\bkpi\b', r'\bvelocity\b',
        r'\bthroughput\b', r'\bcycle time\b', r'\blead time\b',
        r'\btask[s]?\s+(in|on|for)\b', r'\bboard[s]?\b',
    ]
    
    # Analysis patterns - user wants insights/interpretation
    analysis_patterns = [
        r'\banalyze\b', r'\banalysis\b', r'\binsight\b', r'\btrend\b',
        r'\bpattern\b', r'\bpredict\b', r'\bforecast\b', r'\bestimate\b',
        r'\bcompare\b', r'\bcomparison\b', r'\bperformance\b', r'\brisk\b',
        r'\bbottleneck\b', r'\brecommend\b', r'\bsuggest\b', r'\badvise\b',
        r'\bwhy\s+(is|are|did|does)\b', r'\bshould\b',
    ]
    
    # Action patterns - user wants to do something
    action_patterns = [
        r'\bcreate\b', r'\badd\b', r'\bmake\b', r'\bnew\b', r'\bupdate\b',
        r'\bchange\b', r'\bmodify\b', r'\bedit\b', r'\bdelete\b', r'\bremove\b',
        r'\bmove\b', r'\bassign\b', r'\bset\b', r'\bstart\b', r'\bcomplete\b',
    ]
    
    # Help patterns - user needs guidance
    help_patterns = [
        r'\bhow (do|can|to)\b', r'\bhelp\b', r'\bexplain\b',
        r'\bwhat (is|does)\b', r'\bguide\b', r'\btutorial\b', r'\blearn\b',
    ]
    
    # Conversational patterns - greetings, small talk
    chat_patterns = [
        r'^(hi|hello|hey)\b', r'\bthanks?\b', r'\bthank you\b',
        r'\bgood (morning|afternoon|evening)\b', r'\bhow are you\b',
        r'^(yes|no|ok|okay|sure|great)\b', r'\bbye\b', r'\bwho are you\b',
    ]
    
    # Score each category
    scores = {'data_retrieval': 0, 'analysis': 0, 'action': 0, 'help': 0, 'conversational': 0}
    
    for pattern in data_patterns:
        if re.search(pattern, prompt_lower):
            scores['data_retrieval'] += 1
    for pattern in analysis_patterns:
        if re.search(pattern, prompt_lower):
            scores['analysis'] += 1
    for pattern in action_patterns:
        if re.search(pattern, prompt_lower):
            scores['action'] += 1
    for pattern in help_patterns:
        if re.search(pattern, prompt_lower):
            scores['help'] += 1
    for pattern in chat_patterns:
        if re.search(pattern, prompt_lower):
            scores['conversational'] += 1
    
    # Determine the highest scoring type
    max_score = max(scores.values())
    
    if max_score == 0:
        query_type = 'conversational'
        reasoning = "No specific patterns - using conversational mode"
    else:
        # Priority order for ties: data_retrieval > analysis > action > help > conversational
        priority = ['data_retrieval', 'analysis', 'action', 'help', 'conversational']
        for qtype in priority:
            if scores[qtype] == max_score:
                query_type = qtype
                reasoning = f"Matched {max_score} {qtype} pattern(s)"
                break
    
    return {
        'type': query_type,
        'temperature': SPECTRA_TEMPERATURE_MAP.get(query_type, 0.5),
        'reasoning': reasoning,
        'scores': scores
    }


class TaskFlowChatbotService:
    """
    Chatbot service for PrizmAI project assistant
    Adapted from Nexus 360 for PrizmAI's project management data
    """
    
    def __init__(self, user=None, board=None):
        self.user = user
        self.board = board
        
        # Initialize clients with error handling
        try:
            self.gemini_client = GeminiClient()
        except Exception as e:
            logger.error(f"Failed to initialize GeminiClient: {e}")
            self.gemini_client = None
        
        try:
            self.search_client = GoogleSearchClient()
        except Exception as e:
            logger.warning(f"Failed to initialize GoogleSearchClient: {e}")
            self.search_client = None
        
        logger.debug(f"ChatbotService initialized for user: {user}, board: {board}")
    
    def get_taskflow_context(self, use_cache=True):
        """
        Get context from PrizmAI project data
        
        Args:
            use_cache (bool): Whether to use cached context
            
        Returns:
            str: Formatted project context
        """
        try:
            context = "**PrizmAI Project Context:**\n\n"
            
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
            logger.error(f"Error getting PrizmAI context: {e}")
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
            
            # Get high-risk tasks (exclude completed tasks)
            high_risk_tasks = board_tasks.filter(
                risk_level__in=['high', 'critical']
            ).exclude(
                Q(column__name__icontains='done') | Q(column__name__icontains='closed')
            ).select_related('assigned_to', 'column').order_by('-risk_score')[:10]
            
            if not high_risk_tasks.exists():
                # Try alternative: tasks with AI risk score
                high_risk_tasks = board_tasks.filter(
                    ai_risk_score__gte=70
                ).exclude(
                    Q(column__name__icontains='done') | Q(column__name__icontains='closed')
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
        Only triggers for genuinely external/industry knowledge queries,
        NOT for project-specific questions that can be answered from internal data.
        
        Args:
            prompt (str): User prompt
            
        Returns:
            bool: True if web search should be triggered
        """
        # First check if this is clearly a project-specific query — skip web search
        project_specific_indicators = [
            'my task', 'my board', 'assigned to me', 'our team', 'our project',
            'my project', 'how many tasks', 'workload', 'overdue', 'who is',
            'who has', 'which board', 'task distribution', 'sprint', 'burndown',
            'work on today', 'assigned', 'blocker', 'blocked', 'risk in my',
            'should i assign', 'reassign', 'team member',
        ]
        prompt_lower = prompt.lower()
        if any(indicator in prompt_lower for indicator in project_specific_indicators):
            return False
        
        search_triggers = [
            'latest', 'recent news', 'current trend', 'new release',
            'trend', 'news', 'web', 'online', 'internet', 'search for',
            'best practices in industry', 'industry standard', 'common practice',
            'proven method', 'methodology comparison',
            'what is the difference between', 'compare methodologies',
        ]
        
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
            
            # Get total unique users across all boards - use set to avoid duplicate issues
            from django.contrib.auth import get_user_model
            User = get_user_model()
            
            # Collect users from board members and creators separately to avoid query issues
            user_ids = set()
            for board in user_boards:
                # Add board creator
                if board.created_by_id:
                    user_ids.add(board.created_by_id)
                # Add board members
                for member in board.members.all():
                    user_ids.add(member.id)
            
            # Get all users by their IDs
            all_users = User.objects.filter(id__in=user_ids)
            total_users = len(user_ids)
            
            # Separate demo users from real users
            DEMO_EMAIL_DOMAIN = '@demo.prizmai.local'
            demo_user_count = 0
            real_user_count = 0
            demo_user_names = []
            real_user_names = []
            
            for user in all_users:
                display_name = user.get_full_name() or user.username
                if user.email and DEMO_EMAIL_DOMAIN in user.email.lower():
                    demo_user_count += 1
                    demo_user_names.append(display_name)
                else:
                    real_user_count += 1
                    real_user_names.append(display_name)
            
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
- **Total Users:** {total_users}
  - Demo Users: {demo_user_count} ({', '.join(demo_user_names) if demo_user_names else 'None'})
  - Real Users: {real_user_count} ({', '.join(real_user_names) if real_user_names else 'None'})

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
            'depend', 'blocked', 'blocker', 'blocking', 'related', 'subtask',
            'child task', 'parent task', 'chain', 'prerequisite',
            'waiting on', 'waiting for', 'holds up', 'holding up'
        ]
        return any(kw in prompt.lower() for kw in dependency_keywords)
    
    def _is_deadline_projection_query(self, prompt):
        """Detect if query is asking about completing tasks by a deadline"""
        projection_keywords = [
            'can we complete', 'will we finish', 'can we finish',
            'by the end of', 'by end of', 'by this month', 'by next week',
            'by friday', 'by monday', 'on track to', 'meet the deadline',
            'complete by', 'finish by', 'done by', 'deliverable by',
            'feasible', 'achievable', 'realistic'
        ]
        return any(kw in prompt.lower() for kw in projection_keywords)
    
    def _is_organization_query(self, prompt):
        """Detect if query is about organizations"""
        org_keywords = [
            'organization', 'organizations', 'org', 'company', 'companies',
            'client', 'clients', 'departments', 'teams', 'divisions'
        ]
        return any(kw in prompt.lower() for kw in org_keywords)
    
    def _is_user_info_query(self, prompt):
        """Detect if query is asking about users/team members (not the current user's tasks)"""
        prompt_lower = prompt.lower()
        
        # First, check if this is a self-referential query (me/my/I) - those go to user_task_query
        self_referential_keywords = [
            'my task', 'my tasks', 'assigned to me', 'tasks for me',
            'to me', 'for me', 'my work', 'my deadline', 'my overdue',
            'i have', 'i need', 'do i have', 'am i', 'what do i', 'what should i',
            'show me my', 'tell me my', 'give me my', 'list my'
        ]
        
        # If it's about "me", don't trigger user info query
        if any(kw in prompt_lower for kw in self_referential_keywords):
            return False
        
        user_keywords = [
            'user', 'users', 'member', 'members', 'team member', 'team members',
            'who is', 'who has', 'who are', 'who works', 'who should', 'who can',
            'person', 'people', 'assignee', 'developer', 'developers', 'colleague',
            'coworker', 'teammate', 'teammates', 'staff', 'employee',
            'alex', 'sam', 'jordan',  # Common demo user names
            'demo user', 'demo users', 'real user', 'real users',
            'tasks for', 'workload for', 'deadline for', 'overdue for',
            'assigned to alex', 'assigned to sam', 'assigned to jordan',
            'assign to', 'should i assign', 'team skill', 'team skills',
            'workload', 'current workload', 'team workload'
        ]
        return any(kw in prompt_lower for kw in user_keywords)
    
    def _get_user_info_context(self, prompt):
        """
        Get comprehensive user/team member information.
        Distinguishes between demo users and real users.
        Handles questions like:
        - "How many users are there?"
        - "Who has overdue tasks?"
        - "What tasks are assigned to Alex?"
        - "Show me Sam's workload"
        - "Which user has the most tasks?"
        """
        try:
            if not self._is_user_info_query(prompt):
                return None
            
            from django.contrib.auth import get_user_model
            from django.utils import timezone
            from datetime import timedelta
            
            User = get_user_model()
            
            # Get user's boards
            user_boards = self._get_user_boards()
            if not user_boards.exists():
                return "You don't have access to any boards yet."
            
            # Get all users associated with these boards - collect IDs first to avoid query issues
            user_ids = set()
            for board in user_boards:
                if board.created_by_id:
                    user_ids.add(board.created_by_id)
                for member in board.members.all():
                    user_ids.add(member.id)
            
            all_users = list(User.objects.filter(id__in=user_ids).select_related('profile'))
            
            # Separate demo users from real users
            DEMO_EMAIL_DOMAIN = '@demo.prizmai.local'
            demo_users = []
            real_users = []
            
            for user in all_users:
                if user.email and DEMO_EMAIL_DOMAIN in user.email.lower():
                    demo_users.append(user)
                else:
                    real_users.append(user)
            
            today = timezone.now().date()
            tomorrow = today + timedelta(days=1)
            next_week = today + timedelta(days=7)
            
            context = f"""**User & Team Member Information:**

**Summary:**
- **Total Users:** {len(all_users)}
- **Demo Users:** {len(demo_users)} (sample users for demonstration)
- **Real Users:** {len(real_users)} (registered users)

"""
            
            # Build detailed user information
            def get_user_stats(user):
                """Get detailed stats for a single user"""
                user_tasks = Task.objects.filter(
                    column__board__in=user_boards,
                    assigned_to=user
                ).select_related('column', 'column__board')
                
                total_tasks = user_tasks.count()
                completed_tasks = user_tasks.filter(progress=100).count()
                in_progress = user_tasks.filter(progress__gt=0, progress__lt=100).count()
                not_started = user_tasks.filter(progress=0).count()
                
                # Overdue tasks
                overdue_tasks = user_tasks.filter(
                    due_date__lt=today,
                    progress__lt=100
                )
                overdue_count = overdue_tasks.count()
                overdue_list = list(overdue_tasks[:5])  # Top 5 overdue
                
                # Tasks due soon (within 7 days)
                due_soon_tasks = user_tasks.filter(
                    due_date__gte=today,
                    due_date__lte=next_week,
                    progress__lt=100
                )
                due_soon_count = due_soon_tasks.count()
                due_soon_list = list(due_soon_tasks.order_by('due_date')[:5])
                
                # High priority tasks
                high_priority = user_tasks.filter(priority__in=['high', 'urgent', 'critical'])
                high_priority_count = high_priority.count()
                
                # Recent activity - tasks updated in last 7 days
                recent_updated = user_tasks.filter(
                    updated_at__gte=timezone.now() - timedelta(days=7)
                ).count()
                
                return {
                    'total': total_tasks,
                    'completed': completed_tasks,
                    'in_progress': in_progress,
                    'not_started': not_started,
                    'overdue_count': overdue_count,
                    'overdue_list': overdue_list,
                    'due_soon_count': due_soon_count,
                    'due_soon_list': due_soon_list,
                    'high_priority_count': high_priority_count,
                    'recent_updated': recent_updated
                }
            
            # Demo Users Section
            if demo_users:
                context += "---\n**🎭 Demo Users (Sample Data for Demonstration):**\n\n"
                for user in demo_users:
                    display_name = user.get_full_name() or user.username
                    stats = get_user_stats(user)
                    
                    context += f"**{display_name}** ({user.email})\n"
                    context += f"  • Total Tasks: {stats['total']}\n"
                    context += f"  • Completed: {stats['completed']} | In Progress: {stats['in_progress']} | Not Started: {stats['not_started']}\n"
                    
                    if stats['overdue_count'] > 0:
                        context += f"  • ⚠️ Overdue Tasks: {stats['overdue_count']}\n"
                        for task in stats['overdue_list']:
                            context += f"      - \"{task.title}\" (due: {task.due_date})\n"
                    
                    if stats['due_soon_count'] > 0:
                        context += f"  • 📅 Due Soon (next 7 days): {stats['due_soon_count']}\n"
                        for task in stats['due_soon_list']:
                            context += f"      - \"{task.title}\" (due: {task.due_date})\n"
                    
                    if stats['high_priority_count'] > 0:
                        context += f"  • 🔴 High Priority Tasks: {stats['high_priority_count']}\n"
                    
                    context += "\n"
            
            # Real Users Section
            if real_users:
                context += "---\n**👤 Real Users (Registered Accounts):**\n\n"
                for user in real_users:
                    display_name = user.get_full_name() or user.username
                    stats = get_user_stats(user)
                    
                    context += f"**{display_name}** ({user.email})\n"
                    context += f"  • Total Tasks: {stats['total']}\n"
                    context += f"  • Completed: {stats['completed']} | In Progress: {stats['in_progress']} | Not Started: {stats['not_started']}\n"
                    
                    if stats['overdue_count'] > 0:
                        context += f"  • ⚠️ Overdue Tasks: {stats['overdue_count']}\n"
                        for task in stats['overdue_list']:
                            context += f"      - \"{task.title}\" (due: {task.due_date})\n"
                    
                    if stats['due_soon_count'] > 0:
                        context += f"  • 📅 Due Soon (next 7 days): {stats['due_soon_count']}\n"
                        for task in stats['due_soon_list']:
                            context += f"      - \"{task.title}\" (due: {task.due_date})\n"
                    
                    if stats['high_priority_count'] > 0:
                        context += f"  • 🔴 High Priority Tasks: {stats['high_priority_count']}\n"
                    
                    context += "\n"
            
            # Team workload summary
            context += "---\n**📊 Team Workload Summary:**\n"
            all_user_stats = []
            for user in all_users:
                display_name = user.get_full_name() or user.username
                is_demo = user.email and DEMO_EMAIL_DOMAIN in user.email.lower()
                stats = get_user_stats(user)
                all_user_stats.append({
                    'name': display_name,
                    'is_demo': is_demo,
                    'stats': stats
                })
            
            # Sort by total tasks
            all_user_stats.sort(key=lambda x: x['stats']['total'], reverse=True)
            
            context += "\n| User | Type | Total | Completed | Overdue | Due Soon |\n"
            context += "|------|------|-------|-----------|---------|----------|\n"
            for u in all_user_stats:
                user_type = "Demo" if u['is_demo'] else "Real"
                context += f"| {u['name']} | {user_type} | {u['stats']['total']} | {u['stats']['completed']} | {u['stats']['overdue_count']} | {u['stats']['due_soon_count']} |\n"
            
            # Add skill information for team members
            context += "\n---\n**🛠️ Team Skills & Proficiencies:**\n"
            try:
                from accounts.models import UserProfile
                for user in all_users:
                    try:
                        profile = UserProfile.objects.get(user=user)
                        if profile.skills and isinstance(profile.skills, list) and len(profile.skills) > 0:
                            display_name = user.get_full_name() or user.username
                            skill_strs = [f"{s.get('name', 'Unknown')} ({s.get('level', 'N/A')})" for s in profile.skills]
                            context += f"  • **{display_name}**: {', '.join(skill_strs)}\n"
                    except UserProfile.DoesNotExist:
                        pass
            except Exception as e:
                logger.debug(f"Could not load skill data for user info: {e}")
            
            return context
            
        except Exception as e:
            logger.error(f"Error getting user info context: {e}", exc_info=True)
            return f"Error retrieving user information: {str(e)}"
    
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
        """Detect if query is asking for tasks assigned to the current user (me/my/I)"""
        prompt_lower = prompt.lower()
        
        # Keywords that indicate the user is asking about themselves
        user_task_keywords = [
            'my task', 'my tasks', 'assigned to me', 'tasks for me',
            'what am i working on', 'my work', 'my assignments',
            'tasks i have', 'tasks i need', 'my todo', 'my deadline',
            'my overdue', 'my pending', 'my workload', 'my progress',
            'i have', 'i need', 'i am working', 'i\'m working',
            'do i have', 'am i assigned', 'what do i', 'what should i',
            'show me my', 'list my', 'give me my', 'tell me my',
            'how many tasks do i', 'how many tasks have i',
            'tasks assigned to me', 'assigned tasks to me',
            'been assigned to me', 'have been assigned to me'
        ]
        
        # Also check for patterns like "to me" at the end of task-related queries
        if ' to me' in prompt_lower and any(kw in prompt_lower for kw in ['task', 'assign', 'deadline', 'overdue']):
            return True
        
        # Check for "for me" in task context
        if ' for me' in prompt_lower and any(kw in prompt_lower for kw in ['task', 'work', 'deadline', 'overdue']):
            return True
            
        return any(kw in prompt_lower for kw in user_task_keywords)
    
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
        Detect if query is asking for strategic advice, best practices, or how-to guidance.
        Only triggers for genuinely strategic/methodology questions, not project-specific ones.
        """
        # Skip if this is clearly about the user's own project data
        project_data_indicators = [
            'my task', 'assigned to me', 'our board', 'my board',
            'workload', 'who should', 'who has', 'overdue', 'what should i work on',
            'work on today', 'task assigned', 'blockers', 'risks in my',
        ]
        prompt_lower = prompt.lower()
        if any(indicator in prompt_lower for indicator in project_data_indicators):
            return False
        
        strategic_keywords = [
            'best practice', 'best practices', 'industry standard',
            'methodology', 'approach for complex', 'proven method',
            'expert advice on', 'strategy for scaling', 'how to implement agile',
            'optimize process', 'improve team productivity framework',
        ]
        return any(kw in prompt_lower for kw in strategic_keywords)
    
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
                        # Handle both datetime and date objects
                        due_date = task.due_date
                        if hasattr(due_date, 'date'):
                            due_date = due_date.date()
                        today = timezone.now().date()
                        if due_date < today:
                            context += f"    - Due: {due_date} ⚠️ OVERDUE\n"
                        else:
                            context += f"    - Due: {due_date}\n"
                    
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
            
            # Per-board breakdown for each team member
            context += "\n**Per-Board Breakdown:**\n"
            for board in user_boards:
                board_tasks = all_tasks.filter(column__board=board)
                if not board_tasks.exists():
                    continue
                board_distribution = board_tasks.values(
                    'assigned_to__first_name',
                    'assigned_to__last_name',
                    'assigned_to__username'
                ).annotate(task_count=Count('id')).order_by('-task_count')
                
                if board_distribution:
                    context += f"\n  **{board.name}** ({board_tasks.count()} tasks):\n"
                    for assignee in board_distribution:
                        first_name = assignee['assigned_to__first_name'] or ''
                        last_name = assignee['assigned_to__last_name'] or ''
                        username = assignee['assigned_to__username']
                        name = f"{first_name} {last_name}".strip() if (first_name or last_name) else (username or 'Unassigned')
                        context += f"    • {name}: {assignee['task_count']} tasks\n"
            
            # Add skill information for each team member (if available)
            try:
                from accounts.models import UserProfile
                context += "\n**Team Member Skills:**\n"
                for assignee in task_distribution:
                    username = assignee['assigned_to__username']
                    if not username:
                        continue
                    try:
                        profile = UserProfile.objects.get(user__username=username)
                        if profile.skills:
                            skills_list = profile.skills if isinstance(profile.skills, list) else []
                            if skills_list:
                                first_name = assignee['assigned_to__first_name'] or ''
                                last_name = assignee['assigned_to__last_name'] or ''
                                name = f"{first_name} {last_name}".strip() or username
                                skill_strs = [f"{s.get('name', 'Unknown')} ({s.get('level', 'N/A')})" for s in skills_list[:5]]
                                context += f"  • **{name}**: {', '.join(skill_strs)}\n"
                    except UserProfile.DoesNotExist:
                        pass
            except Exception as e:
                logger.debug(f"Could not load skill data: {e}")
            
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
        Detect if query is asking for strategic advice, best practices, or how-to guidance.
        Only triggers for genuinely strategic/methodology questions, not project-specific ones.
        """
        # Skip if this is clearly about the user's own project data
        project_data_indicators = [
            'my task', 'assigned to me', 'our board', 'my board',
            'workload', 'who should', 'who has', 'overdue', 'what should i work on',
            'work on today', 'task assigned', 'blockers', 'risks in my',
        ]
        prompt_lower = prompt.lower()
        if any(indicator in prompt_lower for indicator in project_data_indicators):
            return False
        
        strategic_keywords = [
            'best practice', 'best practices', 'industry standard',
            'methodology', 'approach for complex', 'proven method',
            'expert advice on', 'strategy for scaling', 'how to implement agile',
            'optimize process', 'improve team productivity framework',
        ]
        return any(kw in prompt_lower for kw in strategic_keywords)
    
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
            # Include demo boards for users without organization
            # Use Q objects to combine queries properly instead of queryset union
            return Board.objects.filter(
                Q(is_official_demo_board=True) |
                Q(created_by=self.user) | 
                Q(members=self.user)
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
            from accounts.models import Organization, UserProfile
            
            context = "**Organization Information:**\n\n"
            
            # Get ALL organizations the user has access to
            # Priority order:
            # 1. Organizations where user is a member (via UserProfile)
            # 2. Organizations where user is the creator
            # 3. Organizations accessible through boards
            
            # Get user's profile organization first
            user_org = None
            try:
                if hasattr(self.user, 'profile') and self.user.profile.organization:
                    user_org = self.user.profile.organization
            except:
                pass
            
            # Query organizations: user created OR user's profile belongs to
            if user_org:
                orgs = Organization.objects.filter(
                    Q(id=user_org.id) | Q(created_by=self.user)
                ).distinct()
            else:
                orgs = Organization.objects.filter(created_by=self.user).distinct()
            
            # If no direct membership, try to get from boards
            if not orgs.exists():
                user_boards = self._get_user_boards()
                if user_boards.exists():
                    orgs = Organization.objects.filter(boards__in=user_boards).distinct()
            
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
            
            # Query critical tasks by multiple criteria (exclude completed tasks)
            critical_tasks = Task.objects.filter(
                column__board__in=user_boards
            ).exclude(
                Q(column__name__icontains='done') | Q(column__name__icontains='closed')
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
            
            # Get high-risk tasks (exclude completed tasks)
            high_risk_tasks = Task.objects.filter(
                column__board__in=user_boards,
                risk_level__in=['high', 'critical']
            ).exclude(
                Q(column__name__icontains='done') | Q(column__name__icontains='closed')
            ).select_related('assigned_to', 'column').order_by('-risk_score')[:15]
            
            # If no explicitly high-risk tasks, try AI risk score
            if not high_risk_tasks.exists():
                high_risk_tasks = Task.objects.filter(
                    column__board__in=user_boards
                ).exclude(
                    Q(column__name__icontains='done') | Q(column__name__icontains='closed')
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
    
    def _get_full_dependency_chain(self, task, max_depth=10):
        """
        Recursively get the complete dependency chain for a task
        Returns list of tasks from root to current task
        """
        chain = []
        current = task
        depth = 0
        
        # Travel up the dependency chain
        while current and depth < max_depth:
            chain.insert(0, current)  # Add to beginning to maintain order
            current = current.parent_task if hasattr(current, 'parent_task') else None
            depth += 1
        
        return chain
    
    def _identify_bottleneck_in_chain(self, chain):
        """
        Analyze dependency chain and identify the biggest bottleneck
        Returns tuple of (bottleneck_task, reason)
        """
        if not chain:
            return None, "No dependencies found"
        
        bottlenecks = []
        
        for task in chain:
            bottleneck_score = 0
            reasons = []
            
            # Check if task is not done
            if task.column and 'done' not in task.column.name.lower() and 'closed' not in task.column.name.lower():
                bottleneck_score += 3
                reasons.append(f"Not completed (Status: {task.column.name})")
            
            # Check for high risk
            if hasattr(task, 'risk_level') and task.risk_level in ['high', 'critical']:
                bottleneck_score += 2
                reasons.append(f"High risk ({task.risk_level})")
            
            # Check progress
            if task.progress < 50:
                bottleneck_score += 2
                reasons.append(f"Low progress ({task.progress}%)")
            
            # Check if overdue
            if hasattr(task, 'due_date') and task.due_date:
                from django.utils import timezone
                # Handle both datetime and date objects
                due_date = task.due_date
                if hasattr(due_date, 'date'):
                    due_date = due_date.date()
                today = timezone.now().date()
                if due_date < today:
                    bottleneck_score += 3
                    reasons.append(f"Overdue by {(today - due_date).days} days")
            
            # Check if blocked
            if task.column and 'block' in task.column.name.lower():
                bottleneck_score += 4
                reasons.append("Currently blocked")
            
            # Check if unassigned
            if not task.assigned_to:
                bottleneck_score += 1
                reasons.append("Unassigned")
            
            if bottleneck_score > 0:
                bottlenecks.append((task, bottleneck_score, reasons))
        
        if bottlenecks:
            # Sort by score descending
            bottlenecks.sort(key=lambda x: x[1], reverse=True)
            task, score, reasons = bottlenecks[0]
            return task, reasons
        
        return None, "No significant bottlenecks identified"
    
    def _find_similar_items(self, query_text, items, get_name_func, threshold=0.6):
        """
        Find items with similar names using fuzzy matching
        
        Args:
            query_text: Text to match against
            items: List of items to search
            get_name_func: Function to extract name from item
            threshold: Minimum similarity score (0-1)
            
        Returns:
            List of (item, similarity_score) tuples, sorted by similarity
        """
        from difflib import SequenceMatcher
        
        similar = []
        query_lower = query_text.lower()
        
        for item in items:
            item_name = get_name_func(item).lower()
            similarity = SequenceMatcher(None, query_lower, item_name).ratio()
            
            if similarity >= threshold:
                similar.append((item, similarity))
        
        return sorted(similar, key=lambda x: x[1], reverse=True)
    
    def _is_temporal_meeting_query(self, prompt):
        """Detect queries about recent/last/latest meetings"""
        temporal_keywords = [
            'last meeting', 'recent meeting', 'latest meeting',
            'most recent', 'yesterday', 'today', 'this week',
            'last week', 'previous meeting', 'latest discussion'
        ]
        prompt_lower = prompt.lower()
        return any(kw in prompt_lower for kw in temporal_keywords)
    
    def _is_template_query(self, prompt):
        """Detect if query contains placeholder brackets like [topic] or [something]"""
        import re
        return bool(re.search(r'\[[\w\s\-]+\]', prompt))
    
    def _is_wiki_query(self, prompt):
        """Detect if query is about wiki/documentation"""
        wiki_keywords = [
            'wiki', 'documentation', 'docs', 'guide', 'reference',
            'article', 'page', 'knowledge base', 'kb', 'documentation',
            'how to', 'tutorial', 'best practice', 'guidelines',
            'onboarding', 'style guide', 'standards', 'architecture'
        ]
        prompt_lower = prompt.lower()
        return any(kw in prompt_lower for kw in wiki_keywords)
    
    def _is_meeting_query(self, prompt):
        """Detect if query is about meetings/discussions"""
        meeting_keywords = [
            'meeting', 'standup', 'sync', 'discussion', 'talked about',
            'discussed', 'action item', 'minutes', 'notes', 'transcript',
            'agenda', 'retrospective', 'planning meeting', 'sprint planning',
            'review meeting', 'what did we discuss', 'what was decided'
        ]
        prompt_lower = prompt.lower()
        return any(kw in prompt_lower for kw in meeting_keywords)
    
    def _get_wiki_context(self, prompt):
        """
        Get context from wiki pages and knowledge base
        
        Returns relevant wiki pages based on query content
        """
        try:
            from wiki.models import WikiPage, WikiCategory
            from accounts.models import Organization
            from django.db.models import Q
            
            if not self.user:
                logger.warning("Wiki query failed: No user context")
                return None
            
            # Get user's organization - use demo org as fallback
            org = None
            if hasattr(self.user, 'profile') and self.user.profile.organization:
                org = self.user.profile.organization
            else:
                # Fallback to demo organization for users without org
                org = Organization.objects.filter(name='Demo - Acme Corporation').first()
                if org:
                    logger.info(f"User {self.user.username} has no org, using demo org for wiki queries")
                else:
                    logger.warning(f"Wiki query failed: No demo organization found")
                    return None
            
            context = "**📚 Wiki & Documentation Context:**\n\n"
            
            logger.info(f"Wiki query by {self.user.username} in org '{org.name}'")
            
            # Check if this is a template query like "Find documentation about [topic]"
            if self._is_template_query(prompt):
                logger.info("Template/placeholder query detected - showing all documentation topics")
                
                # Show available documentation organized by category
                categories = WikiCategory.objects.filter(organization=org)
                
                if categories.exists():
                    context += "**USER ASKED ABOUT DOCUMENTATION USING A PLACEHOLDER [topic].**\n"
                    context += "**DO NOT ask them to clarify. Instead, show this list of all available documentation:**\n\n"
                    context += "**Available Documentation Topics:**\n\n"
                    
                    for category in categories:
                        pages = WikiPage.objects.filter(
                            category=category,
                            organization=org,
                            is_published=True
                        )[:10]
                        
                        if pages.exists():
                            context += f"**{category.name}** ({pages.count()} pages):\n"
                            for page in pages:
                                context += f"  • {page.title}"
                                if page.tags:
                                    context += f" [Tags: {', '.join(page.tags[:3])}]"
                                context += "\n"
                            context += "\n"
                    
                    context += "💡 **Tell the user they can ask about any specific topic above, like:**\n"
                    context += '  - "Show me the API documentation"\n'
                    context += '  - "What are our coding standards?"\n'
                    context += '  - "Find the deployment guide"\n'
                    context += "\n**IMPORTANT: Present this as the answer. Do not ask them to clarify what topic they want.**\n"
                    
                    return context
                else:
                    context += "No wiki pages found. You can create documentation from the Knowledge Hub.\n"
                    return context
            
            # Search wiki pages by title and content
            prompt_words = prompt.lower().split()
            wiki_pages = WikiPage.objects.filter(
                organization=org,
                is_published=True
            ).select_related('category', 'created_by')
            
            logger.info(f"Total wiki pages in org: {wiki_pages.count()}")
            logger.info(f"Search words (>3 chars): {[w for w in prompt_words if len(w) > 3]}")
            
            # Search in title, content, and tags
            matching_pages = []
            for page in wiki_pages:
                relevance_score = 0
                page_text = f"{page.title} {page.content}".lower()
                
                # Check for word matches
                for word in prompt_words:
                    if len(word) > 3:  # Skip short words
                        if word in page.title.lower():
                            relevance_score += 3  # Title matches are more important
                        elif word in page.content.lower():
                            relevance_score += 1
                        if page.tags and word in str(page.tags).lower():
                            relevance_score += 2
                
                if relevance_score > 0:
                    matching_pages.append((page, relevance_score))
            
            logger.info(f"Found {len(matching_pages)} pages with relevance > 0")
            
            # Sort by relevance
            matching_pages.sort(key=lambda x: x[1], reverse=True)
            
            if matching_pages:
                logger.info(f"Returning top {min(5, len(matching_pages))} wiki pages")
                context += f"Found {len(matching_pages)} relevant wiki page(s):\n\n"
                
                # Show top 5 most relevant pages
                for page, score in matching_pages[:5]:
                    context += f"**📄 {page.title}**\n"
                    context += f"  • Category: {page.category.name}\n"
                    context += f"  • Created by: {page.created_by.get_full_name() or page.created_by.username}\n"
                    context += f"  • Last updated: {page.updated_at.strftime('%Y-%m-%d')}\n"
                    if page.tags:
                        context += f"  • Tags: {', '.join(page.tags)}\n"
                    
                    # Include content excerpt (first 500 chars)
                    content_preview = page.content[:500]
                    if len(page.content) > 500:
                        content_preview += "..."
                    context += f"  • Content:\n{content_preview}\n\n"
                
                return context
            else:
                # No matches found - list all available wiki pages
                all_pages = list(wiki_pages[:10])
                if all_pages:
                    context += "No direct matches found. Available wiki pages:\n\n"
                    for page in all_pages:
                        context += f"• {page.title} ({page.category.name})\n"
                    context += "\n"
                    return context
                
            return None
            
        except Exception as e:
            logger.error(f"Error getting wiki context: {e}", exc_info=True)
            return None
    
    def _get_meeting_context(self, prompt):
        """
        Get context from meeting notes and transcripts
        
        Returns relevant meetings based on query content
        """
        try:
            from wiki.models import MeetingNotes
            from accounts.models import Organization
            from django.db.models import Q
            
            if not self.user:
                logger.warning("Meeting query failed: No user context")
                return None
            
            # Get user's organization - use demo org as fallback
            org = None
            if hasattr(self.user, 'profile') and self.user.profile.organization:
                org = self.user.profile.organization
            else:
                # Fallback to demo organization for users without org
                org = Organization.objects.filter(name='Demo - Acme Corporation').first()
                if org:
                    logger.info(f"User {self.user.username} has no org, using demo org for meeting queries")
                else:
                    logger.warning(f"Meeting query failed: No demo organization found")
                    return None
            
            context = "**🎤 Meeting & Discussion Context:**\n\n"
            
            # Get all organization meetings (knowledge should be shared across org)
            # More permissive than filtering by user - shows all org meetings
            meetings = MeetingNotes.objects.filter(
                organization=org
            ).select_related('created_by', 'related_board').prefetch_related('attendees').order_by('-date')
            
            logger.info(f"Meeting query by {self.user.username} in org '{org.name}'")
            logger.info(f"Total meetings available: {meetings.count()}")
            
            # If board is specified, prioritize board-related meetings
            if self.board:
                meetings = meetings.filter(
                    Q(related_board=self.board) | Q(related_board__isnull=True)
                )
                logger.info(f"Filtered to board '{self.board.name}': {meetings.count()} meetings")
            
            # Check for temporal queries (last meeting, recent, etc.)
            if self._is_temporal_meeting_query(prompt):
                logger.info("Temporal meeting query detected")
                latest = meetings.first()
                if latest:
                    context += "**Most Recent Meeting:**\n\n"
                    context += f"**🎤 {latest.title}**\n"
                    context += f"  • Type: {latest.get_meeting_type_display()}\n"
                    context += f"  • Date: {latest.date.strftime('%Y-%m-%d %H:%M')}\n"
                    
                    attendee_names = [att.get_full_name() or att.username for att in latest.attendees.all()]
                    if attendee_names:
                        context += f"  • Attendees: {', '.join(attendee_names)}\n"
                    
                    if latest.related_board:
                        context += f"  • Related Board: {latest.related_board.name}\n"
                    
                    if latest.duration_minutes:
                        context += f"  • Duration: {latest.duration_minutes} minutes\n"
                    
                    # Include action items
                    if latest.action_items:
                        context += f"\n**Action Items ({len(latest.action_items)}):**\n"
                        for item in latest.action_items:
                            if isinstance(item, dict):
                                task_desc = item.get('task', item.get('description', str(item)))
                                context += f"  - {task_desc}"
                                if item.get('assigned_to'):
                                    context += f" (Assigned: {item['assigned_to']})"
                                if item.get('due_date'):
                                    context += f" (Due: {item['due_date']})"
                                context += "\n"
                            else:
                                context += f"  - {item}\n"
                    
                    # Include decisions
                    if latest.decisions:
                        context += f"\n**Key Decisions ({len(latest.decisions)}):**\n"
                        for decision in latest.decisions:
                            if isinstance(decision, dict):
                                context += f"  - {decision.get('decision', str(decision))}\n"
                            else:
                                context += f"  - {decision}\n"
                    
                    # Include notes excerpt
                    if latest.content:
                        content_preview = latest.content[:400]
                        if len(latest.content) > 400:
                            content_preview += "..."
                        context += f"\n**Notes:**\n{content_preview}\n"
                    
                    return context
            
            # Search for relevant meetings
            prompt_words = prompt.lower().split()
            matching_meetings = []
            
            for meeting in meetings[:20]:  # Check last 20 meetings
                relevance_score = 0
                meeting_text = f"{meeting.title} {meeting.content}".lower()
                
                # Check transcript if available
                if meeting.transcript_text:
                    meeting_text += f" {meeting.transcript_text.lower()}"
                
                # Check for word matches
                for word in prompt_words:
                    if len(word) > 3:  # Skip short words
                        if word in meeting.title.lower():
                            relevance_score += 3
                        elif word in meeting_text:
                            relevance_score += 1
                
                if relevance_score > 0:
                    matching_meetings.append((meeting, relevance_score))
            
            # Sort by relevance, then by date
            matching_meetings.sort(key=lambda x: (x[1], x[0].date), reverse=True)
            
            if matching_meetings:
                context += f"Found {len(matching_meetings)} relevant meeting(s):\n\n"
                
                # Show top 5 most relevant meetings
                for meeting, score in matching_meetings[:5]:
                    context += f"**🎤 {meeting.title}**\n"
                    context += f"  • Type: {meeting.get_meeting_type_display()}\n"
                    context += f"  • Date: {meeting.date.strftime('%Y-%m-%d %H:%M')}\n"
                    
                    attendee_names = [att.get_full_name() or att.username for att in meeting.attendees.all()]
                    context += f"  • Attendees: {', '.join(attendee_names)}\n"
                    
                    if meeting.related_board:
                        context += f"  • Related Board: {meeting.related_board.name}\n"
                    
                    if meeting.duration_minutes:
                        context += f"  • Duration: {meeting.duration_minutes} minutes\n"
                    
                    # Include action items if available
                    if meeting.action_items:
                        context += f"  • Action Items: {len(meeting.action_items)}\n"
                        for item in meeting.action_items[:3]:  # Show first 3
                            if isinstance(item, dict):
                                context += f"    - {item.get('task', item.get('description', str(item)))}\n"
                    
                    # Include decisions if available
                    if meeting.decisions:
                        context += f"  • Key Decisions: {len(meeting.decisions)}\n"
                        for decision in meeting.decisions[:3]:  # Show first 3
                            if isinstance(decision, dict):
                                context += f"    - {decision.get('decision', str(decision))}\n"
                    
                    # Include extraction summary if available
                    if meeting.extraction_results and isinstance(meeting.extraction_results, dict):
                        summary = meeting.extraction_results.get('extraction_summary', {})
                        if summary.get('meeting_summary'):
                            context += f"  • Summary: {summary['meeting_summary']}\n"
                    
                    # Include content/notes excerpt
                    content_preview = meeting.content[:300]
                    if len(meeting.content) > 300:
                        content_preview += "..."
                    context += f"  • Notes:\n{content_preview}\n\n"
                
                return context
            else:
                # No matches found - provide helpful fallback
                logger.info(f"No meetings matched query: {prompt[:50]}")
                
                # Try fuzzy matching to find similar meeting names
                all_org_meetings = MeetingNotes.objects.filter(organization=org)[:30]
                similar_meetings = self._find_similar_items(
                    prompt, 
                    all_org_meetings, 
                    lambda m: m.title,
                    threshold=0.5  # Lower threshold for meeting names
                )
                
                if similar_meetings:
                    logger.info(f"Found {len(similar_meetings)} similar meetings via fuzzy matching")
                    context += "**No exact match found, but did you mean one of these meetings?**\n\n"
                    
                    for meeting, similarity in similar_meetings[:5]:
                        context += f"• **{meeting.title}** ({similarity:.0%} match)\n"
                        context += f"  - Date: {meeting.date.strftime('%Y-%m-%d %H:%M')}\n"
                        context += f"  - Type: {meeting.get_meeting_type_display()}\n"
                        
                        if meeting.action_items:
                            context += f"  - {len(meeting.action_items)} action items\n"
                        if meeting.decisions:
                            context += f"  - {len(meeting.decisions)} decisions\n"
                        context += "\n"
                    
                    context += "Please ask about a specific meeting from the list above.\n"
                    return context
                
                # Check if ANY meetings exist in the organization
                all_meetings_count = MeetingNotes.objects.filter(organization=org).count()
                
                if all_meetings_count == 0:
                    context += "**No meetings found in the knowledge base.**\n\n"
                    context += "Meeting notes can be created from the Knowledge Hub. "
                    context += "Once meetings are documented, I'll be able to help you find decisions, action items, and discussions.\n"
                    return context
                
                # Show recent meetings as suggestions
                recent_meetings = meetings[:5]
                if recent_meetings.exists():
                    context += f"**No meetings directly matching your query found.**\n\n"
                    context += f"Here are the {recent_meetings.count()} most recent meetings that may be relevant:\n\n"
                    for meeting in recent_meetings:
                        context += f"• **{meeting.title}**\n"
                        context += f"  - Date: {meeting.date.strftime('%Y-%m-%d %H:%M')}\n"
                        context += f"  - Type: {meeting.get_meeting_type_display()}\n"
                        if meeting.related_board:
                            context += f"  - Board: {meeting.related_board.name}\n"
                        
                        # Show action items count if available
                        if meeting.action_items:
                            context += f"  - Action Items: {len(meeting.action_items)}\n"
                        if meeting.decisions:
                            context += f"  - Decisions: {len(meeting.decisions)}\n"
                        context += "\n"
                    
                    context += "Please specify which meeting you're interested in, or try a different search term.\n"
                    return context
                else:
                    context += "**No meetings found** matching your criteria. Please check the meeting name or try a broader search.\n"
                    return context
            
            return None
            
        except Exception as e:
            logger.error(f"Error getting meeting context: {e}", exc_info=True)
            return None
    
    def _get_dependency_context(self, prompt):
        """
        Get task dependency and relationship data
        Includes critical chains, blocked tasks, subtasks
        Enhanced to show complete dependency chains and identify bottlenecks
        """
        try:
            if not self._is_dependency_query(prompt):
                return None
            
            # Get user's boards
            user_boards = self._get_user_boards()
            if not user_boards.exists():
                return None
            
            context = "**Task Dependencies & Relationships:**\n\n"
            
            # Check if asking about a specific task
            specific_task = None
            for board in user_boards:
                tasks = Task.objects.filter(column__board=board)
                for task in tasks:
                    if task.title.lower() in prompt.lower():
                        specific_task = task
                        break
                if specific_task:
                    break
            
            # If specific task mentioned, show its complete chain
            if specific_task:
                chain = self._get_full_dependency_chain(specific_task)
                
                context += f"**Complete Dependency Chain for '{specific_task.title}':**\n\n"
                
                if len(chain) == 1:
                    context += f"✓ This task has no dependencies\n\n"
                    context += f"**Task Details:**\n"
                    context += f"  - Status: {specific_task.column.name if specific_task.column else 'Unknown'}\n"
                    context += f"  - Assigned: {specific_task.assigned_to.get_full_name() or specific_task.assigned_to.username if specific_task.assigned_to else 'Unassigned'}\n"
                    context += f"  - Progress: {specific_task.progress}%\n"
                    if hasattr(specific_task, 'risk_level') and specific_task.risk_level:
                        context += f"  - Risk Level: {specific_task.risk_level.upper()}\n"
                else:
                    context += f"**Dependency Chain ({len(chain)} tasks):**\n\n"
                    for i, task in enumerate(chain):
                        indent = "  " * i
                        arrow = "└─> " if i > 0 else "• "
                        context += f"{indent}{arrow}**{task.title}**\n"
                        context += f"{indent}    - Status: {task.column.name if task.column else 'Unknown'}\n"
                        context += f"{indent}    - Assigned: {task.assigned_to.get_full_name() or task.assigned_to.username if task.assigned_to else 'Unassigned'}\n"
                        context += f"{indent}    - Progress: {task.progress}%\n"
                        
                        if hasattr(task, 'risk_level') and task.risk_level:
                            context += f"{indent}    - Risk Level: {task.risk_level.upper()}\n"
                        
                        if hasattr(task, 'due_date') and task.due_date:
                            from django.utils import timezone
                            # Handle both datetime and date objects
                            due_date = task.due_date
                            if hasattr(due_date, 'date'):
                                due_date = due_date.date()
                            today = timezone.now().date()
                            if due_date < today:
                                days_overdue = (today - due_date).days
                                context += f"{indent}    - ⚠️ OVERDUE by {days_overdue} days\n"
                            else:
                                context += f"{indent}    - Due: {due_date}\n"
                        
                        context += "\n"
                    
                    # Identify bottleneck
                    bottleneck_task, bottleneck_reasons = self._identify_bottleneck_in_chain(chain[:-1])  # Exclude the task itself
                    
                    if bottleneck_task:
                        context += f"**🚨 Biggest Bottleneck Identified:**\n"
                        context += f"  - **Task:** {bottleneck_task.title}\n"
                        context += f"  - **Reasons:**\n"
                        for reason in bottleneck_reasons:
                            context += f"    • {reason}\n"
                        context += f"\n  - **Recommendation:** Prioritize unblocking '{bottleneck_task.title}' to enable '{specific_task.title}'\n"
                    else:
                        context += f"**✓ No Critical Bottlenecks:**\n"
                        context += f"  All dependency tasks are on track or completed.\n"
                
                context += "\n"
            
            # Get general dependency overview
            # Get tasks with dependencies
            tasks_with_parent = Task.objects.filter(
                column__board__in=user_boards,
                parent_task__isnull=False
            ).select_related('parent_task', 'column', 'assigned_to')[:15]
            
            # Get tasks with child tasks (subtasks)
            tasks_with_children = Task.objects.filter(
                column__board__in=user_boards,
                subtasks__isnull=False
            ).select_related('column').distinct()[:10]
            
            if not specific_task and (tasks_with_parent.exists() or tasks_with_children.exists()):
                if tasks_with_parent.exists():
                    context += f"**Tasks with Dependencies ({len(tasks_with_parent)}):**\n"
                    for task in tasks_with_parent:
                        context += f"• **{task.title}**\n"
                        context += f"  - Depends On: {task.parent_task.title}\n"
                        context += f"  - Parent Status: {task.parent_task.column.name if task.parent_task.column else 'Unknown'}\n"
                        if task.column:
                            context += f"  - Task Status: {task.column.name}\n"
                        
                        # Check if parent is blocking
                        parent_done = task.parent_task.column and ('done' in task.parent_task.column.name.lower() or 'closed' in task.parent_task.column.name.lower())
                        if not parent_done:
                            context += f"  - ⚠️ Blocked: Waiting for '{task.parent_task.title}' to complete\n"
                        
                        context += "\n"
                
                if tasks_with_children.exists():
                    context += f"\n**Tasks with Subtasks ({len(tasks_with_children)}):**\n"
                    for task in tasks_with_children:
                        child_count = task.subtasks.count() if hasattr(task, 'subtasks') else 0
                        context += f"• {task.title} ({child_count} subtasks)\n"
            
            # If no dependencies found anywhere, return explicit message
            if context == "**Task Dependencies & Relationships:**\n\n":
                return "**Task Dependencies & Relationships:**\n\nNo task dependencies are currently configured in your boards. Tasks are independent and can be worked on in any order.\n\nTo set up dependencies, edit a task and set its 'Parent Task' field to create blocking relationships."
            
            return context
        
        except Exception as e:
            logger.error(f"Error getting dependency context: {e}", exc_info=True)
            return None
    
    def _get_deadline_projection_context(self, prompt):
        """
        Get deadline feasibility analysis for queries like "Can we complete X by Y date?"
        Analyzes high-priority tasks, their due dates, and workload capacity
        """
        try:
            if not self._is_deadline_projection_query(prompt):
                return None
            
            from django.utils import timezone
            from datetime import timedelta
            import calendar
            
            user_boards = self._get_user_boards()
            if not user_boards.exists():
                return None
            
            today = timezone.now().date()
            
            # Determine target date from prompt
            prompt_lower = prompt.lower()
            
            # End of this month
            if 'end of this month' in prompt_lower or 'by this month' in prompt_lower or 'end of the month' in prompt_lower:
                last_day = calendar.monthrange(today.year, today.month)[1]
                target_date = today.replace(day=last_day)
                target_label = f"end of {today.strftime('%B %Y')}"
            # End of next month
            elif 'end of next month' in prompt_lower or 'by next month' in prompt_lower:
                next_month = today.month + 1 if today.month < 12 else 1
                next_year = today.year if today.month < 12 else today.year + 1
                last_day = calendar.monthrange(next_year, next_month)[1]
                target_date = today.replace(year=next_year, month=next_month, day=last_day)
                target_label = f"end of {target_date.strftime('%B %Y')}"
            # Next week
            elif 'next week' in prompt_lower or 'by friday' in prompt_lower:
                days_until_friday = (4 - today.weekday()) % 7
                if days_until_friday == 0:
                    days_until_friday = 7
                target_date = today + timedelta(days=days_until_friday)
                target_label = f"{target_date.strftime('%A, %B %d')}"
            else:
                # Default to end of month
                last_day = calendar.monthrange(today.year, today.month)[1]
                target_date = today.replace(day=last_day)
                target_label = f"end of {today.strftime('%B %Y')}"
            
            days_remaining = (target_date - today).days
            
            # Get high-priority incomplete tasks
            high_priority_tasks = Task.objects.filter(
                column__board__in=user_boards,
                priority__in=['high', 'urgent']
            ).exclude(
                Q(column__name__icontains='done') | Q(column__name__icontains='closed')
            ).select_related('assigned_to', 'column', 'column__board').order_by('due_date', '-priority')
            
            # Split by due date relative to target
            due_before_target = []
            due_after_target = []
            no_due_date = []
            overdue = []
            
            for task in high_priority_tasks:
                if task.due_date:
                    task_due = task.due_date.date() if hasattr(task.due_date, 'date') else task.due_date
                    if task_due < today:
                        overdue.append(task)
                    elif task_due <= target_date:
                        due_before_target.append(task)
                    else:
                        due_after_target.append(task)
                else:
                    no_due_date.append(task)
            
            total_high_priority = high_priority_tasks.count()
            
            context = f"**Deadline Projection Analysis:**\n\n"
            context += f"**Target:** {target_label} ({days_remaining} days remaining)\n"
            context += f"**Total High-Priority Tasks:** {total_high_priority}\n\n"
            
            # Risk assessment
            risk_level = "LOW"
            if overdue:
                risk_level = "HIGH"
            elif len(due_before_target) > days_remaining * 2:  # More than 2 tasks per day
                risk_level = "MEDIUM"
            
            context += f"**Feasibility Assessment:** {risk_level} RISK\n\n"
            
            if overdue:
                context += f"**⚠️ OVERDUE ({len(overdue)} tasks):**\n"
                for task in overdue[:5]:
                    task_due = task.due_date.date() if hasattr(task.due_date, 'date') else task.due_date
                    days_late = (today - task_due).days
                    context += f"  • {task.title} - {days_late} days overdue (Assigned: {task.assigned_to.username if task.assigned_to else 'Unassigned'})\n"
                context += "\n"
            
            if due_before_target:
                context += f"**Due Before Target ({len(due_before_target)} tasks):**\n"
                for task in due_before_target[:8]:
                    task_due = task.due_date.date() if hasattr(task.due_date, 'date') else task.due_date
                    context += f"  • {task.title} - Due {task_due.strftime('%b %d')} ({task.column.name}) - {task.assigned_to.username if task.assigned_to else 'Unassigned'}\n"
                context += "\n"
            
            if no_due_date:
                context += f"**No Due Date Set ({len(no_due_date)} high-priority tasks):**\n"
                for task in no_due_date[:5]:
                    context += f"  • {task.title} ({task.column.name}) - {task.assigned_to.username if task.assigned_to else 'Unassigned'}\n"
                context += "\n"
            
            # Workload summary
            context += f"**Workload Summary:**\n"
            context += f"  • Tasks per day needed: {len(due_before_target) / max(days_remaining, 1):.1f}\n"
            context += f"  • Overdue tasks to clear: {len(overdue)}\n"
            context += f"  • Tasks without deadlines: {len(no_due_date)}\n"
            
            return context
            
        except Exception as e:
            logger.error(f"Error getting deadline projection context: {e}", exc_info=True)
            return None
    
    def generate_system_prompt(self):
        """Generate system prompt for AI model with dynamic context"""
        from django.utils import timezone
        
        # Dynamic context: current date, user identity, board
        current_date = timezone.now().strftime('%A, %B %d, %Y')
        current_time = timezone.now().strftime('%I:%M %p %Z')
        user_name = self.user.get_full_name() or self.user.username if self.user else 'Unknown User'
        user_username = self.user.username if self.user else 'unknown'
        board_name = self.board.name if self.board else 'All boards'
        
        return f"""You are Spectra, PrizmAI's AI Project Assistant — an intelligent project management assistant.

**CURRENT CONTEXT:**
- Today's Date: {current_date}
- Current Time: {current_time}
- Current User: {user_name} (username: {user_username})
- Active Board: {board_name}

Your role is to help project managers and team members with:
- Project planning and strategy
- Task management and prioritization
- Team resource allocation and workload management
- Risk identification and mitigation
- Timeline optimization and scheduling
- Report generation and insights
- Best practices and recommendations
- Wiki/Documentation search and knowledge retrieval
- Meeting notes analysis and action item tracking

CRITICAL INSTRUCTIONS FOR DATA-DRIVEN RESPONSES:
1. **ALWAYS USE PROVIDED CONTEXT DATA**: When project data is provided in the "Available Context Data" section, you MUST use it to answer questions directly and specifically
2. **NEVER ASK FOR INFORMATION YOU HAVE**: If context data contains the answer, provide it immediately without asking follow-up questions
3. **BE SPECIFIC AND CONCRETE**: Use actual numbers, names, dates from the context data - not general statements
4. **ANSWER DIRECTLY FIRST**: Start with the specific answer from the data, then provide additional insights or recommendations
5. **NO UNNECESSARY QUESTIONS**: Don't ask "What is your name?" or "Which board?" — you already know the user is {user_name} and the board context
6. **LEVERAGE WIKI & MEETINGS**: When wiki pages or meeting notes are provided, reference them directly and quote relevant sections
7. **DATE AWARENESS**: Always compare task due dates against today's date ({current_date}). Proactively flag overdue tasks (due date before today) and approaching deadlines (due within 7 days). If a task is overdue, ALWAYS highlight it with a warning, even if not explicitly asked.
8. **CROSS-REFERENCE DATA**: When answering resource allocation or task assignment questions, combine multiple data sources:
   - Check team members' current workloads (task counts)
   - Check skill proficiency levels (if available in context)
   - Check task priorities and deadlines
   - Provide a synthesized recommendation, not just raw data
9. **FILTER COMPLETED WORK**: When listing risks, blockers, or actionable items, exclude tasks that are already "Done" or "Closed" unless specifically asked about completed work. Completed tasks are not risks.
10. **CONCISE & ACTIONABLE**: Keep responses focused. Avoid generic productivity advice or filler content. Every sentence should add value.
11. **NEVER HALLUCINATE OR FABRICATE DATA**: ONLY use user names, task names, team members, skills, and numbers that are explicitly present in the "Available Context Data" section below. If the context data does not contain team member information, workload data, or skill data, you MUST say so clearly (e.g., "I don't have team member data available for this board"). NEVER invent or guess user names, task counts, or skill levels. If you cannot answer a question from the provided context, say what data is missing rather than making something up.

RESPONSE STRUCTURE:
- For data queries (counts, lists, status): Provide the specific data FIRST, then optionally add insights
- For "what should I work on?" queries: Prioritize by (1) overdue tasks, (2) due today, (3) due this week, (4) highest priority unstarted tasks
- For documentation queries: Cite specific wiki pages with titles and provide relevant excerpts
- For meeting queries: Reference specific meetings with dates and summarize key decisions/action items
- For strategic questions: Combine project-specific data with best practices — avoid generic web advice if project data answers the question
- For risk/mitigation: Focus ONLY on active (non-completed) tasks. Provide both specific actions and general best practices
- For task assignment questions: Recommend specific team members based on workload + skills (if available), don't ask for info you have
- Always be actionable - provide clear next steps

EXAMPLES OF CORRECT BEHAVIOR:
❌ WRONG: "To show your tasks, I need to know your username"
✓ RIGHT: "You have 5 tasks assigned: [list from context data]"

❌ WRONG: "How many organizations would you like to see?"
✓ RIGHT: "You have 1 organization: Dev Team (2 boards, 6 members)"

❌ WRONG: "I need more information about team member skills to recommend an assignee"
✓ RIGHT: "Based on current workloads, [team member from context data] (12 tasks) has the most capacity. They also have Python skills at Expert level. I recommend assigning to them."

❌ WRONG: Inventing team member names like "Maria Garcia", "Ben Carter" that don't exist in the provided context data
✓ RIGHT: Only mention users that appear in the Available Context Data section. If no team data is provided, say: "I don't have team member data for the current board. Please ensure team members are added to the board."

❌ WRONG: "Security audit fixes (Done) - CRITICAL Risk"
✓ RIGHT: (Don't include completed tasks in risk lists — they're resolved)

Format responses clearly with:
- Bullet points for lists
- **Bold** for emphasis and headers
- Specific numbers and metrics
- Actionable recommendations"""
    
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
            
            # Check if Gemini client is available
            if not self.gemini_client:
                return {
                    'response': "I apologize, but the AI service is temporarily unavailable. Please check that GEMINI_API_KEY is configured correctly and try again.",
                    'source': 'error',
                    'tokens': 0,
                    'error': 'Gemini client not initialized',
                    'used_web_search': False,
                    'search_sources': [],
                    'context': {}
                }
            
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
            is_user_info_query = self._is_user_info_query(prompt)
            is_critical_task_query = self._is_critical_task_query(prompt)
            is_mitigation_query = self._is_mitigation_query(prompt)
            is_user_task_query = self._is_user_task_query(prompt)
            is_incomplete_task_query = self._is_incomplete_task_query(prompt)
            is_board_comparison_query = self._is_board_comparison_query(prompt)
            is_task_distribution_query = self._is_task_distribution_query(prompt)
            is_progress_query = self._is_progress_query(prompt)
            is_overdue_query = self._is_overdue_query(prompt)
            is_wiki_query = self._is_wiki_query(prompt)
            is_meeting_query = self._is_meeting_query(prompt)
            is_deadline_projection_query = self._is_deadline_projection_query(prompt)
            
            # Build context in priority order
            context_parts = []
            
            # 1. Wiki context (documentation, guides, best practices)
            if is_wiki_query:
                wiki_context = self._get_wiki_context(prompt)
                if wiki_context:
                    context_parts.append(wiki_context)
                    logger.debug("Added wiki context")
            
            # 2. Meeting context (discussions, decisions, action items)
            if is_meeting_query:
                meeting_context = self._get_meeting_context(prompt)
                if meeting_context:
                    context_parts.append(meeting_context)
                    logger.debug("Added meeting context")
            
            # 3. Organization context (system-wide)
            if is_organization_query:
                org_context = self._get_organization_context(prompt)
                if org_context:
                    context_parts.append(org_context)
                    logger.debug("Added organization context")
            
            # 4. User info context (team members, demo vs real users, user-specific questions)
            if is_user_info_query:
                user_info_context = self._get_user_info_context(prompt)
                if user_info_context:
                    context_parts.append(user_info_context)
                    logger.debug("Added user info context")
            
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
            # Include critical tasks context when query is about critical/risk tasks
            # Also include it when mitigation is asked ALONG WITH critical/risk (user wants both)
            if is_critical_task_query or is_risk_query:
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
            
            # 11. Risk context (only if not already covered by critical tasks context)
            if is_risk_query and not is_critical_task_query:
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
            
            # 15b. Deadline projection context (can we complete by X date?)
            if is_deadline_projection_query:
                deadline_context = self._get_deadline_projection_context(prompt)
                if deadline_context:
                    context_parts.append(deadline_context)
                    logger.debug("Added deadline projection context")
            
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
            # SKIP web search if we already have strong internal context or wiki context
            search_context = ""
            used_web_search = False
            search_sources = []
            
            # Check if wiki context was already added (indicates query is about internal docs)
            has_wiki_context = is_wiki_query and any('wiki' in part.lower() or 'documentation' in part.lower() for part in context_parts)
            
            # Check if we already have strong internal context (project data answers the question)
            has_strong_internal_context = len(context_parts) >= 2 or any(
                indicator in '\n'.join(context_parts).lower() 
                for indicator in ['tasks assigned', 'task distribution', 'total tasks', 'workload', 'risk analysis', 'critical tasks', 'overdue']
            ) if context_parts else False
            
            # Trigger web search ONLY for queries that genuinely need external knowledge
            # Skip if: wiki context exists, OR strong internal context already answers the question
            if (is_search_query or is_strategic_query) and not has_wiki_context and not has_strong_internal_context and getattr(settings, 'ENABLE_WEB_SEARCH', False) and self.search_client:
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
            elif has_wiki_context:
                logger.info(f"Skipping web search - wiki context already found for this query")
            
            # Build system prompt
            system_prompt = self.generate_system_prompt()
            if context_parts:
                system_prompt += "\n\n**Available Context Data:**\n" + "\n".join(context_parts)
                logger.debug(f"Built context with {len(context_parts)} parts")
            else:
                logger.debug("No specific context found for query")
            
            # Classify query for dual-mode temperature selection
            query_classification = classify_spectra_query(prompt)
            query_type = query_classification['type']
            temperature = query_classification['temperature']
            
            logger.debug(f"Spectra query classified: {query_type}, temp: {temperature}")
            
            # Get response from Gemini with optimized temperature (STATELESS - no history maintained)
            response = self.gemini_client.get_response(prompt, system_prompt, temperature=temperature)
            
            return {
                'response': response['content'],
                'source': 'gemini',
                'tokens': response.get('tokens', 0),
                'error': response.get('error'),
                'used_web_search': used_web_search,
                'search_sources': search_sources,
                'query_type': query_type,
                'temperature_used': temperature,
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
                    'is_deadline_projection_query': is_deadline_projection_query,
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
