"""
Management command to populate AI Assistant demo data.
Creates chat sessions, Q&A history, analytics, and recommendations.

Usage:
    python manage.py populate_ai_assistant_demo_data
"""
from django.core.management.base import BaseCommand
from django.contrib.auth.models import User
from django.utils import timezone
from django.db import transaction
from datetime import timedelta
from decimal import Decimal
import random

from ai_assistant.models import (
    AIAssistantSession,
    AIAssistantMessage,
    ProjectKnowledgeBase,
    AIAssistantAnalytics,
    AITaskRecommendation,
    UserPreference,
)
from kanban.models import Board, Task
from accounts.models import Organization


class Command(BaseCommand):
    help = 'Populate AI Assistant demo data for the demo organization'

    def add_arguments(self, parser):
        parser.add_argument(
            '--reset',
            action='store_true',
            help='Delete existing AI Assistant demo data before creating new data',
        )

    def handle(self, *args, **options):
        self.stdout.write('=' * 80)
        self.stdout.write('POPULATING AI ASSISTANT DEMO DATA')
        self.stdout.write('=' * 80)

        # Get demo organization
        try:
            demo_org = Organization.objects.get(name='Demo - Acme Corporation')
            self.stdout.write(self.style.SUCCESS(f'✓ Found organization: {demo_org.name}'))
        except Organization.DoesNotExist:
            self.stdout.write(self.style.ERROR('✗ Demo - Acme Corporation not found!'))
            self.stdout.write('  Please run: python manage.py create_demo_organization')
            return

        # Get demo users (including solo demo admin)
        demo_users = User.objects.filter(profile__organization=demo_org)
        
        # Also include demo_admin_solo if it exists (used for solo demo mode)
        try:
            demo_admin_solo = User.objects.get(username='demo_admin_solo')
            demo_users = demo_users | User.objects.filter(pk=demo_admin_solo.pk)
            self.stdout.write(f'  Including solo demo admin: {demo_admin_solo.username}')
        except User.DoesNotExist:
            pass
        
        if not demo_users.exists():
            self.stdout.write(self.style.ERROR('✗ No demo users found!'))
            return

        self.stdout.write(f'  Found {demo_users.count()} demo users')

        # Get demo boards and tasks
        demo_boards = Board.objects.filter(organization=demo_org)
        demo_tasks = Task.objects.filter(column__board__in=demo_boards)

        self.stdout.write(f'  Found {demo_boards.count()} demo boards')
        self.stdout.write(f'  Found {demo_tasks.count()} demo tasks')

        # Reset if requested
        if options['reset']:
            self.reset_ai_data(demo_users, demo_boards)

        with transaction.atomic():
            # Create user preferences
            prefs_count = self.create_user_preferences(demo_users)
            
            # Create chat sessions and messages
            sessions_count, messages_count = self.create_chat_sessions(demo_users, demo_boards)
            
            # Create knowledge base entries
            kb_count = self.create_knowledge_base(demo_boards, demo_tasks)
            
            # Create analytics data
            analytics_count = self.create_analytics(demo_users, demo_boards)
            
            # Create task recommendations
            rec_count = self.create_recommendations(demo_boards, demo_tasks)

        # Summary
        self.stdout.write('')
        self.stdout.write(self.style.SUCCESS('=' * 80))
        self.stdout.write(self.style.SUCCESS('✓ AI ASSISTANT DEMO DATA COMPLETE'))
        self.stdout.write(self.style.SUCCESS('=' * 80))
        self.stdout.write(f'  User Preferences: {prefs_count}')
        self.stdout.write(f'  Chat Sessions: {sessions_count}')
        self.stdout.write(f'  Messages (Q&A): {messages_count}')
        self.stdout.write(f'  Knowledge Base Entries: {kb_count}')
        self.stdout.write(f'  Analytics Records: {analytics_count}')
        self.stdout.write(f'  Task Recommendations: {rec_count}')
        self.stdout.write('')

    def reset_ai_data(self, demo_users, demo_boards):
        """Delete existing AI Assistant demo data"""
        self.stdout.write('\nResetting AI Assistant demo data...')
        
        # Delete in order of dependencies
        AIAssistantMessage.objects.filter(session__user__in=demo_users).delete()
        sessions_deleted = AIAssistantSession.objects.filter(user__in=demo_users).delete()
        self.stdout.write(f'  Deleted {sessions_deleted[0]} sessions')
        
        kb_deleted = ProjectKnowledgeBase.objects.filter(board__in=demo_boards).delete()
        self.stdout.write(f'  Deleted {kb_deleted[0]} knowledge base entries')
        
        analytics_deleted = AIAssistantAnalytics.objects.filter(user__in=demo_users).delete()
        self.stdout.write(f'  Deleted {analytics_deleted[0]} analytics records')
        
        rec_deleted = AITaskRecommendation.objects.filter(board__in=demo_boards).delete()
        self.stdout.write(f'  Deleted {rec_deleted[0]} recommendations')
        
        self.stdout.write(self.style.SUCCESS('  ✓ AI data reset complete'))

    def create_user_preferences(self, demo_users):
        """Create user preferences for demo users"""
        self.stdout.write('\n1. Creating User Preferences...')
        
        count = 0
        for user in demo_users:
            pref, created = UserPreference.objects.get_or_create(
                user=user,
                defaults={
                    'enable_web_search': True,
                    'enable_task_insights': True,
                    'enable_risk_alerts': True,
                    'enable_resource_recommendations': True,
                    'notify_on_risk': True,
                    'notify_on_overload': True,
                    'messages_per_page': 20,
                }
            )
            if created:
                count += 1
                self.stdout.write(f'  Created preferences for: {user.username}')
        
        return count

    def create_chat_sessions(self, demo_users, demo_boards):
        """Create demo chat sessions with Q&A messages"""
        self.stdout.write('\n2. Creating Chat Sessions & Q&A...')
        
        # Prioritize demo_admin_solo for solo demo mode, fall back to alex_chen_demo
        primary_user = demo_users.filter(username='demo_admin_solo').first() or \
                       demo_users.filter(username='alex_chen_demo').first() or \
                       demo_users.first()
        secondary_user = demo_users.exclude(pk=primary_user.pk).first()
        
        # Get boards
        software_board = demo_boards.filter(name__icontains='software').first()
        marketing_board = demo_boards.filter(name__icontains='marketing').first()
        bug_board = demo_boards.filter(name__icontains='bug').first()
        
        sessions_data = self.get_sessions_data()
        
        sessions_count = 0
        messages_count = 0
        
        for session_data in sessions_data:
            # Determine user and board
            if session_data.get('user') == 'secondary' and secondary_user:
                user = secondary_user
            else:
                user = primary_user
            
            if session_data.get('board') == 'software' and software_board:
                board = software_board
            elif session_data.get('board') in ('marketing', 'bug'):
                # Marketing Campaign and Bug Tracking boards have been removed from the demo.
                # Skip sessions tied to these boards.
                continue
            else:
                board = None
            
            # Create session
            session = AIAssistantSession.objects.create(
                user=user,
                board=board,
                title=session_data['title'],
                description=session_data.get('description', ''),
                is_active=session_data.get('is_active', False),
                is_demo=True,  # Mark as demo session visible to all users
                message_count=len(session_data['messages']),
                total_tokens_used=random.randint(500, 3000),
            )
            
            # Backdate the session - use update() to bypass auto_now
            days_ago = session_data.get('days_ago', 0)
            hours_offset = random.randint(1, 8)
            backdated_created = timezone.now() - timedelta(days=days_ago, hours=hours_offset)
            backdated_updated = backdated_created + timedelta(minutes=random.randint(5, 60))
            AIAssistantSession.objects.filter(pk=session.pk).update(
                created_at=backdated_created,
                updated_at=backdated_updated
            )
            session.refresh_from_db()
            
            sessions_count += 1
            self.stdout.write(f'  Created session: {session.title}')
            
            # Create messages with proper sequential timestamps
            # Each message gets a timestamp that is progressively later
            base_time = session.created_at
            message_objects = []
            
            for msg_idx, msg_data in enumerate(session_data['messages']):
                # Calculate timestamp: each message is 10 seconds after the previous
                msg_timestamp = base_time + timedelta(seconds=msg_idx * 10)
                
                message = AIAssistantMessage.objects.create(
                    session=session,
                    role=msg_data['role'],
                    content=msg_data['content'],
                    model='gemini' if msg_data['role'] == 'assistant' else None,
                    tokens_used=random.randint(50, 500) if msg_data['role'] == 'assistant' else 0,
                    is_helpful=msg_data.get('is_helpful'),
                    used_web_search=msg_data.get('used_web_search', False),
                    search_sources=msg_data.get('search_sources', []),
                )
                message_objects.append((message.pk, msg_timestamp))
                messages_count += 1
            
            # Update all message timestamps using update() to bypass auto_now_add
            for msg_pk, msg_timestamp in message_objects:
                AIAssistantMessage.objects.filter(pk=msg_pk).update(created_at=msg_timestamp)
        
        return sessions_count, messages_count

    def create_knowledge_base(self, demo_boards, demo_tasks):
        """Create knowledge base entries for demo boards"""
        self.stdout.write('\n3. Creating Knowledge Base...')
        
        kb_entries = []
        
        for board in demo_boards:
            # Project overview
            kb_entries.append({
                'board': board,
                'content_type': 'project_overview',
                'title': f'{board.name} - Project Overview',
                'content': f"""Project: {board.name}
                
This project focuses on delivering high-quality solutions for the organization.
The team uses agile methodology with 2-week sprints.

Key Objectives:
- Deliver on-time with high quality
- Maintain clear communication
- Continuous improvement through retrospectives

Current Status: Active
Team Size: {board.members.count()} members
Total Tasks: {Task.objects.filter(column__board=board).count()}
""",
                'summary': f'Overview of the {board.name} project including objectives, methodology, and current status.',
            })
            
            # Resource plan
            kb_entries.append({
                'board': board,
                'content_type': 'resource_plan',
                'title': f'{board.name} - Resource Allocation',
                'content': f"""Resource Plan for {board.name}

Team Members:
{chr(10).join([f"- {m.get_full_name() or m.username}" for m in board.members.all()])}

Capacity: 40 hours/week per team member
Current Sprint Allocation: Balanced workload distribution

Resource Guidelines:
- No team member should exceed 100% utilization
- Critical tasks should have backup assignees
- Skills matrix should be updated monthly
""",
                'summary': f'Resource allocation and capacity planning for {board.name}.',
            })
            
            # Risk assessment
            kb_entries.append({
                'board': board,
                'content_type': 'risk_assessment',
                'title': f'{board.name} - Risk Assessment',
                'content': f"""Risk Assessment for {board.name}

Identified Risks:
1. Timeline Risk: Some tasks may be delayed due to dependencies
2. Resource Risk: Team members may become overloaded
3. Technical Risk: Complex implementations may require more time
4. External Risk: Third-party dependencies may cause blockers

Mitigation Strategies:
- Regular progress monitoring
- Clear escalation path for blockers
- Buffer time in estimates
- Cross-training for critical skills
""",
                'summary': f'Risk assessment and mitigation strategies for {board.name}.',
            })
        
        count = 0
        for entry_data in kb_entries:
            entry, created = ProjectKnowledgeBase.objects.update_or_create(
                board=entry_data['board'],
                content_type=entry_data['content_type'],
                title=entry_data['title'],
                defaults={
                    'content': entry_data['content'],
                    'summary': entry_data['summary'],
                    'is_active': True,
                }
            )
            if created:
                count += 1
        
        self.stdout.write(f'  Created {count} knowledge base entries')
        return count

    def create_analytics(self, demo_users, demo_boards):
        """Create analytics data - realistic summary records matching demo sessions"""
        self.stdout.write('\n4. Creating Analytics Data...')
        
        # Delete existing analytics for demo users
        AIAssistantAnalytics.objects.filter(user__in=demo_users).delete()
        
        count = 0
        # Get demo_admin_solo as the primary demo user
        demo_admin_solo = demo_users.filter(username='demo_admin_solo').first()
        
        if not demo_admin_solo:
            self.stdout.write('  Skipped (no demo_admin_solo user found)')
            return 0
        
        # Count actual messages for this user to base analytics on real data
        from ai_assistant.models import AIAssistantMessage, AIAssistantSession
        user_sessions = AIAssistantSession.objects.filter(user=demo_admin_solo)
        
        # Create per-board analytics with realistic values based on actual data
        boards_list = list(demo_boards)
        for board in boards_list:
            # Get sessions for this board
            board_sessions = user_sessions.filter(board=board)
            board_messages = AIAssistantMessage.objects.filter(session__in=board_sessions).count()
            
            if board_messages == 0:
                board_messages = 2  # Minimum for display purposes
            
            analytics = AIAssistantAnalytics.objects.create(
                user=demo_admin_solo,
                board=board,
                sessions_created=max(1, board_sessions.count()),
                messages_sent=board_messages,
                gemini_requests=board_messages // 2 + 1,
                web_searches_performed=random.randint(0, 2),
                knowledge_base_queries=random.randint(1, 4),
                total_tokens_used=board_messages * 450,
                input_tokens=board_messages * 150,
                output_tokens=board_messages * 300,
                helpful_responses=board_messages // 2,
                unhelpful_responses=0,
                avg_response_time_ms=random.randint(900, 1400),
            )
            count += 1
        
        # Create a record for sessions without a specific board (general queries)
        sessions_without_board = user_sessions.filter(board__isnull=True)
        general_messages = AIAssistantMessage.objects.filter(session__in=sessions_without_board).count()
        
        if general_messages > 0:
            analytics = AIAssistantAnalytics.objects.create(
                user=demo_admin_solo,
                board=None,  # General analytics for non-board sessions
                sessions_created=sessions_without_board.count(),
                messages_sent=general_messages,
                gemini_requests=general_messages // 2 + 1,
                web_searches_performed=1,
                knowledge_base_queries=2,
                total_tokens_used=general_messages * 450,
                input_tokens=general_messages * 150,
                output_tokens=general_messages * 300,
                helpful_responses=general_messages // 2,
                unhelpful_responses=0,
                avg_response_time_ms=1100,
            )
            count += 1
        
        self.stdout.write(f'  Created {count} analytics records')
        return count

    def create_recommendations(self, demo_boards, demo_tasks):
        """Create AI task recommendations"""
        self.stdout.write('\n5. Creating Task Recommendations...')
        
        recommendations_data = [
            {
                'type': 'optimization',
                'title': 'Consider breaking down large task',
                'description': 'This task has high complexity and multiple dependencies. Breaking it into smaller subtasks could improve tracking and reduce risk.',
                'suggested_action': 'Split this task into 3-4 smaller, more manageable subtasks with clear deliverables.',
                'expected_benefit': 'Better progress visibility, easier parallel work, and reduced risk of delays.',
                'impact': 'medium',
                'confidence': 0.85,
                'status': 'pending',
            },
            {
                'type': 'risk_mitigation',
                'title': 'High-risk task approaching deadline',
                'description': 'This task is marked as high priority but has low progress with the deadline approaching.',
                'suggested_action': 'Assign additional resources or consider extending the deadline to ensure quality.',
                'expected_benefit': 'Reduced risk of missing deadline, maintained quality standards.',
                'impact': 'high',
                'confidence': 0.92,
                'status': 'accepted',
            },
            {
                'type': 'resource_allocation',
                'title': 'Team member overload detected',
                'description': 'The assigned team member has high workload across multiple tasks. Consider redistributing.',
                'suggested_action': 'Reassign 2-3 lower priority tasks to team members with available capacity.',
                'expected_benefit': 'Balanced workload, reduced burnout risk, improved overall team velocity.',
                'impact': 'high',
                'confidence': 0.88,
                'status': 'implemented',
            },
            {
                'type': 'dependency',
                'title': 'Blocked by pending dependency',
                'description': 'This task is waiting on another task that is behind schedule, which may cause a cascade delay.',
                'suggested_action': 'Prioritize the blocking task or find an alternative approach to unblock this work.',
                'expected_benefit': 'Prevents cascade delays, keeps project timeline on track.',
                'impact': 'critical',
                'confidence': 0.95,
                'status': 'pending',
            },
            {
                'type': 'priority',
                'title': 'Priority adjustment suggested',
                'description': 'Based on current sprint goals and dependencies, this task may need higher priority.',
                'suggested_action': 'Consider elevating this task to high priority for the current sprint.',
                'expected_benefit': 'Better alignment with sprint goals, reduced dependency bottlenecks.',
                'impact': 'medium',
                'confidence': 0.78,
                'status': 'rejected',
            },
            {
                'type': 'timeline',
                'title': 'Timeline optimization opportunity',
                'description': 'This task and a related task could be done in parallel, potentially saving time.',
                'suggested_action': 'Assign these tasks to different team members to work simultaneously.',
                'expected_benefit': 'Potential 3-day reduction in overall timeline.',
                'impact': 'medium',
                'confidence': 0.82,
                'status': 'pending',
            },
        ]
        
        count = 0
        tasks_with_recs = list(demo_tasks[:10])  # Get up to 10 tasks
        
        for i, rec_data in enumerate(recommendations_data):
            if i >= len(tasks_with_recs):
                break
                
            task = tasks_with_recs[i]
            
            rec, created = AITaskRecommendation.objects.update_or_create(
                task=task,
                board=task.column.board,
                recommendation_type=rec_data['type'],
                title=rec_data['title'],
                defaults={
                    'description': rec_data['description'],
                    'potential_impact': rec_data['impact'],
                    'confidence_score': Decimal(str(rec_data['confidence'])),
                    'suggested_action': rec_data['suggested_action'],
                    'expected_benefit': rec_data['expected_benefit'],
                    'status': rec_data['status'],
                    'implemented_at': timezone.now() - timedelta(days=2) if rec_data['status'] == 'implemented' else None,
                    'implementation_notes': 'Successfully redistributed tasks to balance workload.' if rec_data['status'] == 'implemented' else None,
                }
            )
            if created:
                count += 1
                self.stdout.write(f'  Created: {rec.title}')
        
        return count

    def get_sessions_data(self):
        """Return demo chat session data with Q&A"""
        return [
            # Session 1: Sprint Planning Help (Active, Recent)
            {
                'title': 'Sprint Planning Help',
                'description': 'Getting help with sprint planning and task estimation',
                'is_active': True,
                'days_ago': 0,
                'board': 'software',
                'user': 'primary',
                'messages': [
                    {
                        'role': 'user',
                        'content': 'What tasks should I prioritize for this sprint?',
                    },
                    {
                        'role': 'assistant',
                        'content': """Based on your current board status, I recommend prioritizing the following tasks:

**High Priority (Complete First):**
1. **Implement user authentication system** - This is blocking several other features and is marked as high priority
2. **Design database schema for multi-tenancy** - Foundation task that other work depends on
3. **Fix critical security vulnerability** - Security issues should always be addressed promptly

**Medium Priority:**
4. **Build REST API endpoints** - Can proceed once authentication is in place
5. **Create responsive dashboard layout** - Good to start in parallel

**Considerations:**
- Your team has 3 members with a combined capacity of ~120 hours
- Current sprint has 2 weeks remaining
- I noticed 2 tasks are at risk of being overdue

Would you like me to help with task estimation or identify any blockers?""",
                        'is_helpful': True,
                    },
                    {
                        'role': 'user',
                        'content': 'How do I handle the dependency between the auth system and API endpoints?',
                    },
                    {
                        'role': 'assistant',
                        'content': """Great question! Here's how to manage this dependency effectively:

**Parallel Work Strategy:**

1. **Split the API work:**
   - Start with endpoints that don't require authentication (public routes)
   - Create the authentication middleware as a separate subtask
   - Use mock authentication during development

2. **Staging Approach:**
   - Week 1: Focus on auth system + API structure without auth
   - Week 2: Integrate auth into API endpoints + testing

**Practical Steps:**

```python
# API can use a simple decorator that will be enhanced later
@require_auth  # Initially a pass-through, then full auth
def protected_endpoint(request):
    pass
```

3. **Risk Mitigation:**
   - Create clear interface contracts between teams
   - Daily sync on integration points
   - Have auth team provide test tokens early

**Timeline Impact:** This approach could save 2-3 days vs. sequential development.

Would you like me to create subtasks for this parallel approach?""",
                        'is_helpful': True,
                    },
                ]
            },
            
            # Session 2: Team Workload Analysis
            {
                'title': 'Team Workload Analysis',
                'description': 'Analyzing team capacity and workload distribution',
                'is_active': False,
                'days_ago': 2,
                'board': 'software',
                'user': 'primary',
                'messages': [
                    {
                        'role': 'user',
                        'content': 'Is anyone on my team overloaded right now?',
                    },
                    {
                        'role': 'assistant',
                        'content': """I've analyzed the current workload distribution for your team. Here's what I found:

**Workload Overview:**

| Team Member | Assigned Tasks | Est. Hours | Utilization |
|-------------|----------------|------------|-------------|
| Sam Rivera | 8 tasks | 45 hours | ⚠️ 112% |
| Alex Chen | 5 tasks | 32 hours | ✅ 80% |
| Jordan Taylor | 3 tasks | 18 hours | ✅ 45% |

**⚠️ Alert: Sam Rivera is overloaded**

Sam has 8 active tasks with an estimated 45 hours of work, which exceeds their 40-hour weekly capacity.

**Recommended Actions:**

1. **Immediate:** Reassign 1-2 tasks from Sam to Jordan (who has capacity)
2. **Tasks to consider moving:**
   - "Update documentation" (Low priority, 4 hours)
   - "Write unit tests for auth" (Medium priority, 6 hours)

3. **Long-term:** 
   - Review task estimation accuracy
   - Consider breaking down Sam's complex tasks

Would you like me to suggest specific task reassignments?""",
                        'is_helpful': True,
                    },
                    {
                        'role': 'user',
                        'content': 'Yes, please suggest which tasks to move to Jordan',
                    },
                    {
                        'role': 'assistant',
                        'content': """Based on skills matching and current priorities, here are my recommendations:

**Recommended Reassignments:**

**1. "Update API documentation" → Jordan**
- **Current Owner:** Sam Rivera
- **Estimated Hours:** 4 hours
- **Priority:** Low
- **Why Jordan:** 
  - Jordan has strong documentation skills
  - Task is well-defined with clear scope
  - No technical blockers

**2. "Create data validation utilities" → Jordan**
- **Current Owner:** Sam Rivera  
- **Estimated Hours:** 5 hours
- **Priority:** Medium
- **Why Jordan:**
  - Jordan has intermediate Python skills
  - Good learning opportunity
  - Sam can provide quick code review

**After Reassignment:**

| Team Member | Tasks | Hours | Utilization |
|-------------|-------|-------|-------------|
| Sam Rivera | 6 | 36h | ✅ 90% |
| Jordan Taylor | 5 | 27h | ✅ 68% |

**New Team Balance:** ✅ Healthy distribution

Would you like me to help draft a message to the team about these changes?""",
                        'is_helpful': True,
                    },
                ]
            },
            
            # Session 3: Risk Assessment
            {
                'title': 'Project Risk Review',
                'description': 'Identifying and assessing project risks',
                'is_active': False,
                'days_ago': 5,
                'board': 'software',
                'user': 'primary',
                'messages': [
                    {
                        'role': 'user',
                        'content': 'What are the main risks in our current sprint?',
                    },
                    {
                        'role': 'assistant',
                        'content': """I've analyzed your sprint and identified the following risks:

**🔴 High Risks:**

1. **Timeline Risk - Authentication System**
   - Task is 20% complete with 5 days remaining
   - Blocking 3 dependent tasks
   - **Likelihood:** High | **Impact:** Critical
   - **Mitigation:** Consider adding a second developer

2. **Resource Risk - Sam's Workload**
   - 112% utilization detected
   - Risk of burnout or quality issues
   - **Likelihood:** Medium | **Impact:** High
   - **Mitigation:** Redistribute 2 tasks immediately

**🟡 Medium Risks:**

3. **Dependency Risk - Third-party API**
   - Waiting on external vendor response
   - Could block integration testing
   - **Likelihood:** Medium | **Impact:** Medium
   - **Mitigation:** Prepare mock services as fallback

4. **Scope Risk - Dashboard Features**
   - Requirements still being refined
   - Potential for scope creep
   - **Likelihood:** Medium | **Impact:** Medium
   - **Mitigation:** Lock requirements by Wednesday

**🟢 Low Risks:**

5. **Technical Debt**
   - Some shortcuts taken for speed
   - Manageable if addressed next sprint

**Risk Score: 7.2/10** (Above average - needs attention)

Would you like detailed mitigation plans for any of these risks?""",
                        'is_helpful': True,
                    },
                ]
            },
            
            # Session 4: General Questions (Secondary User)
            {
                'title': 'How to use Gantt charts',
                'description': 'Learning about project features',
                'is_active': False,
                'days_ago': 7,
                'board': 'software',
                'user': 'secondary',
                'messages': [
                    {
                        'role': 'user',
                        'content': 'How do I view the Gantt chart for my project?',
                    },
                    {
                        'role': 'assistant',
                        'content': """Great question! Here's how to access and use the Gantt chart:

**Accessing the Gantt Chart:**

1. Navigate to your board
2. Look for the **"Gantt"** tab in the top navigation
3. Click to open the Gantt view

**Gantt Chart Features:**

📊 **Timeline View:**
- See all tasks laid out on a timeline
- View start and end dates visually
- Identify overlapping work

🔗 **Dependencies:**
- Arrows show task dependencies
- Easily spot blocking relationships
- Drag to adjust timelines

👥 **Resource View:**
- Toggle to see tasks by assignee
- Identify workload conflicts
- Plan resource allocation

**Tips:**
- Use mouse scroll to zoom in/out
- Drag task bars to adjust dates
- Click tasks for details panel
- Use filters to focus on specific areas

**Keyboard Shortcuts:**
- `+`/`-` : Zoom in/out
- `T` : Jump to today
- `F` : Toggle filters

Would you like me to explain any specific Gantt chart feature in more detail?""",
                        'is_helpful': True,
                    },
                ]
            },
            
            # Session 5: Velocity and Metrics
            {
                'title': 'Sprint Velocity Analysis',
                'description': 'Understanding team velocity metrics',
                'is_active': False,
                'days_ago': 10,
                'board': 'software',
                'user': 'primary',
                'messages': [
                    {
                        'role': 'user',
                        'content': "What's our team's average velocity and how are we trending?",
                    },
                    {
                        'role': 'assistant',
                        'content': """I've analyzed your team's velocity over the past 6 sprints. Here's the breakdown:

**Velocity Trend:**

```
Sprint 40: ████████████░░░░ 24 pts
Sprint 41: ██████████████░░ 28 pts
Sprint 42: ████████████████ 32 pts ⬆️ Peak
Sprint 43: ██████████████░░ 28 pts
Sprint 44: ████████████░░░░ 22 pts ⬇️
Sprint 45: █████████░░░░░░░ 18 pts (in progress)
```

**Key Metrics:**
- **Average Velocity:** 26 story points/sprint
- **Current Sprint:** 18 pts completed (69% of average)
- **Trend:** 📉 Declining for 3 sprints

**Analysis:**

The velocity drop correlates with:
1. **Holiday period** - Reduced capacity in Sprint 44
2. **New team member** - Onboarding overhead
3. **Technical debt** - Cleanup tasks taking longer

**Recommendations:**

1. **Short-term:** Reduce Sprint 45 commitment to 22 pts
2. **Medium-term:** 
   - Complete onboarding activities
   - Schedule dedicated tech debt sprint
3. **Long-term:** Target 28-30 pts as sustainable velocity

**Forecast:**
- Sprint 46: ~24 pts (recovery)
- Sprint 47: ~26 pts (back to average)

Would you like suggestions for improving velocity?""",
                        'is_helpful': True,
                        'used_web_search': False,
                    },
                ]
            },
            
            # Session 6: Best Practices Question (with web search)
            {
                'title': 'Agile Best Practices',
                'description': 'Research on agile methodologies',
                'is_active': False,
                'days_ago': 14,
                'board': None,
                'user': 'primary',
                'messages': [
                    {
                        'role': 'user',
                        'content': 'What are the best practices for running effective sprint retrospectives?',
                    },
                    {
                        'role': 'assistant',
                        'content': """Based on agile best practices and research, here are the key elements of effective sprint retrospectives:

**🎯 Structure (60-90 minutes)**

1. **Set the Stage (5 min)**
   - Check-in activity
   - Review retro ground rules
   - Ensure psychological safety

2. **Gather Data (15-20 min)**
   - What went well? ✅
   - What didn't go well? ❌
   - What can we improve? 💡

3. **Generate Insights (15-20 min)**
   - Identify patterns
   - Root cause analysis
   - Group similar items

4. **Decide Actions (15-20 min)**
   - Vote on top improvements
   - Assign owners
   - Set measurable goals

5. **Close (5 min)**
   - Summarize action items
   - Appreciation round
   - Rate the retro

**💡 Best Practices:**

- **Rotate facilitators** - Fresh perspectives
- **Limit action items** - Max 2-3 per sprint
- **Follow up** - Review previous actions first
- **Vary formats** - Try different retro formats:
  - Start/Stop/Continue
  - 4 Ls (Liked, Learned, Lacked, Longed For)
  - Sailboat (Wind, Anchors, Rocks)
  - Mad/Sad/Glad

**🚫 Common Pitfalls:**
- Skipping retros when "too busy"
- Not acting on feedback
- Same people dominating
- Blaming individuals

**📈 Success Metrics:**
- Team satisfaction scores improving
- Recurring issues decreasing
- Action items completed rate > 80%

Would you like a template for your next retrospective?""",
                        'is_helpful': True,
                        'used_web_search': True,
                        'search_sources': [
                            {'title': 'Atlassian Agile Coach', 'url': 'https://atlassian.com/agile'},
                            {'title': 'Scrum.org Resources', 'url': 'https://scrum.org/resources'},
                        ],
                    },
                ]
            },
            
            # Session 7: Marketing Board Questions
            {
                'title': 'Campaign Timeline Planning',
                'description': 'Planning marketing campaign timeline',
                'is_active': False,
                'days_ago': 3,
                'board': 'marketing',
                'user': 'secondary',
                'messages': [
                    {
                        'role': 'user',
                        'content': 'Help me plan the timeline for our Q1 marketing campaign',
                    },
                    {
                        'role': 'assistant',
                        'content': """I'll help you create a timeline for your Q1 marketing campaign. Based on your board data and typical campaign phases:

**📅 Q1 2026 Campaign Timeline**

**Phase 1: Planning (Jan 1-15)**
Week 1-2:
- [ ] Define campaign objectives and KPIs
- [ ] Identify target audience segments
- [ ] Set budget allocation
- [ ] Competitive analysis

**Phase 2: Content Creation (Jan 15 - Feb 5)**
Week 3-4:
- [ ] Develop creative brief
- [ ] Create content calendar
- [ ] Design visual assets
- [ ] Write copy for all channels

Week 5:
- [ ] Review and approval process
- [ ] Final revisions

**Phase 3: Pre-Launch (Feb 5-15)**
Week 6-7:
- [ ] Set up tracking and analytics
- [ ] Configure ad platforms
- [ ] A/B test setup
- [ ] Landing page optimization

**Phase 4: Launch & Execution (Feb 15 - Mar 15)**
Week 8-12:
- [ ] Campaign launch
- [ ] Daily monitoring
- [ ] Optimization based on data
- [ ] Content adjustments

**Phase 5: Analysis (Mar 15-31)**
Week 13-14:
- [ ] Compile results
- [ ] ROI analysis
- [ ] Lessons learned
- [ ] Recommendations for Q2

**Key Milestones:**
🎯 Jan 15: Strategy approved
🎯 Feb 5: All content ready
🎯 Feb 15: Campaign launch
🎯 Mar 31: Final report

Would you like me to create tasks for each phase on your board?""",
                        'is_helpful': True,
                    },
                ]
            },
            
            # Session 8: Bug Tracking - Defect Prioritization
            {
                'title': 'Bug Prioritization Strategy',
                'description': 'Help prioritizing bugs for the current sprint',
                'is_active': True,
                'days_ago': 1,
                'board': 'bug',
                'user': 'primary',
                'messages': [
                    {
                        'role': 'user',
                        'content': 'How should I prioritize the bugs in our backlog?',
                    },
                    {
                        'role': 'assistant',
                        'content': """I've analyzed your bug backlog and here's a prioritization framework based on severity, impact, and effort:

**🔴 Critical Priority (Fix Immediately)**

1. **Login Authentication Failure** - P1
   - Users cannot access the system
   - Impact: 100% of users blocked
   - Est. Fix Time: 4 hours
   
2. **Data Loss on Form Submit** - P1
   - User data not being saved
   - Impact: All form submissions affected
   - Est. Fix Time: 6 hours

**🟠 High Priority (This Sprint)**

3. **Dashboard Performance Issue** - P2
   - Page load > 10 seconds
   - Impact: User experience degradation
   - Est. Fix Time: 8 hours

4. **Email Notifications Not Sending** - P2
   - Critical alerts not delivered
   - Impact: Communication breakdown
   - Est. Fix Time: 4 hours

**🟡 Medium Priority (Next Sprint)**

5. **UI Alignment Issues** - P3
   - Visual inconsistencies on mobile
   - Impact: Minor UX issues
   - Est. Fix Time: 3 hours

**Prioritization Matrix:**

| Bug | Severity | User Impact | Effort | Priority Score |
|-----|----------|-------------|--------|----------------|
| Login Failure | Critical | High | Low | 95/100 |
| Data Loss | Critical | High | Medium | 90/100 |
| Dashboard Perf | High | Medium | High | 70/100 |
| Email Issues | High | Medium | Low | 75/100 |
| UI Alignment | Low | Low | Low | 40/100 |

Would you like me to help create a bug fix sprint plan?""",
                        'is_helpful': True,
                    },
                ]
            },
            
            # Session 9: Bug Tracking - Root Cause Analysis
            {
                'title': 'Bug Root Cause Analysis',
                'description': 'Investigating recurring issues',
                'is_active': False,
                'days_ago': 4,
                'board': 'bug',
                'user': 'primary',
                'messages': [
                    {
                        'role': 'user',
                        'content': 'We keep seeing similar bugs. Can you help identify patterns?',
                    },
                    {
                        'role': 'assistant',
                        'content': """I've analyzed your bug history and found several recurring patterns:

**📊 Bug Pattern Analysis (Last 30 Days)**

**Pattern 1: Input Validation Issues (35% of bugs)**
- **Symptoms:** Invalid data accepted, crashes on edge cases
- **Affected Areas:** User forms, API endpoints
- **Root Cause:** Missing or incomplete input validation
- **Fix Strategy:** Implement comprehensive validation layer

**Pattern 2: Null Reference Errors (25% of bugs)**
- **Symptoms:** Crashes when data is missing
- **Affected Areas:** Data display, calculations
- **Root Cause:** Not handling optional/nullable fields
- **Fix Strategy:** Add null checks, use optional chaining

**Pattern 3: Race Conditions (20% of bugs)**
- **Symptoms:** Intermittent failures, data inconsistency
- **Affected Areas:** Concurrent operations, async processes
- **Root Cause:** Improper synchronization
- **Fix Strategy:** Review async patterns, add locks

**Pattern 4: UI State Management (20% of bugs)**
- **Symptoms:** Stale data, wrong UI state
- **Affected Areas:** Interactive components
- **Root Cause:** Complex state dependencies
- **Fix Strategy:** Simplify state, add state validation

**Recommendations:**

1. **Short-term:**
   - Add validation library for all inputs
   - Code review checklist for null handling

2. **Medium-term:**
   - Implement automated testing for edge cases
   - Add monitoring for race conditions

3. **Long-term:**
   - Refactor state management
   - Create reusable validated components

Would you like a detailed action plan for addressing these patterns?""",
                        'is_helpful': True,
                    },
                    {
                        'role': 'user',
                        'content': 'Yes, give me an action plan for the input validation issues',
                    },
                    {
                        'role': 'assistant',
                        'content': """Here's a comprehensive action plan for addressing input validation issues:

**🎯 Input Validation Improvement Plan**

**Phase 1: Assessment (Week 1)**
- [ ] Audit all user input points
- [ ] Document current validation coverage
- [ ] Identify high-risk endpoints
- [ ] Review recent validation-related bugs

**Phase 2: Framework Setup (Week 2)**
- [ ] Choose/implement validation library
- [ ] Define validation rules schema
- [ ] Create reusable validators
- [ ] Set up validation error handling

**Phase 3: Implementation (Weeks 3-4)**
- [ ] Apply validation to critical forms
- [ ] Add API request validation
- [ ] Implement frontend validation
- [ ] Add validation logging

**Phase 4: Testing (Week 5)**
- [ ] Write validation unit tests
- [ ] Create edge case test suite
- [ ] Perform security testing
- [ ] User acceptance testing

**Success Metrics:**
- ✅ 0 new validation bugs in next sprint
- ✅ 100% critical endpoint coverage
- ✅ < 2s validation response time

**Estimated Effort:** 3 developer-weeks
**Expected Bug Reduction:** 35% fewer defects

Would you like me to create tasks for this plan on your board?""",
                        'is_helpful': True,
                    },
                ]
            },
        ]
