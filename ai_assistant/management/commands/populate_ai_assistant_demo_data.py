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
                        'content': """Here's how to manage this dependency effectively:

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
| Sam Rivera | 11 tasks | 44 hours | ⚠️ 110% |
| Jordan Taylor | 12 tasks | 38 hours | ✅ 95% |
| Alex Chen | 7 tasks | 28 hours | ✅ 70% |

**⚠️ Alert: Sam Rivera is overloaded**

Sam has 11 active implementation tasks with an estimated 44 hours of work, which exceeds their 40-hour weekly capacity.

**Recommended Actions:**

1. **Immediate:** Reassign 1-2 tasks from Sam to Jordan or Alex (who have capacity)
2. **Tasks to consider moving:**
   - "Error Tracking & Monitoring" (Medium priority, 3 hours) → Jordan
   - "Security Audit & Fixes" (Medium priority, 4 hours) → Jordan

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

**1. "Error Tracking & Monitoring" → Jordan**
- **Current Owner:** Sam Rivera
- **Estimated Hours:** 3 hours
- **Priority:** Medium
- **Why Jordan:** 
  - Monitoring setup aligns with Jordan's QA skills
  - Task is well-defined with clear scope
  - No technical blockers

**2. "Security Audit & Fixes" → Jordan**
- **Current Owner:** Sam Rivera  
- **Estimated Hours:** 4 hours
- **Priority:** Medium
- **Why Jordan:**
  - Jordan has strong Quality Assurance skills
  - Testing-adjacent task, natural fit
  - Sam can provide context on security patterns

**After Reassignment:**

| Team Member | Tasks | Hours | Utilization |
|-------------|-------|-------|-------------|
| Sam Rivera | 9 | 37h | ✅ 92% |
| Jordan Taylor | 14 | 45h | ✅ 95% (shared across test/doc tasks) |

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
                        'content': """Here's how to access and use the Gantt chart:

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
            
            # Session 7: Release Planning
            {
                'title': 'Release Planning Strategy',
                'description': 'Planning the software release timeline',
                'is_active': False,
                'days_ago': 3,
                'board': 'software',
                'user': 'secondary',
                'messages': [
                    {
                        'role': 'user',
                        'content': 'Help me plan the release timeline for our software project',
                    },
                    {
                        'role': 'assistant',
                        'content': """Based on your current board progress and remaining tasks, here's a recommended release timeline:

**📅 Software Release Timeline**

**Phase 1: Complete Core Features (Weeks 1-2)**
- [ ] Finish Authentication System (currently 80%)
- [ ] Complete User Registration Flow (currently 60%)
- [ ] Finalize Database Schema & Migrations (currently 40%)
- [ ] Resolve all In Progress tasks

**Phase 2: Integration & Testing (Weeks 3-4)**
- [ ] Authentication Testing Suite
- [ ] Integration Testing Suite
- [ ] Core Features Code Review
- [ ] API Rate Limiting implementation

**Phase 3: Polish & Hardening (Weeks 5-6)**
- [ ] Performance Optimization
- [ ] Security Audit & Fixes
- [ ] UI/UX Polish
- [ ] Load Testing & Optimization

**Phase 4: Launch Preparation (Weeks 7-8)**
- [ ] User Onboarding Flow
- [ ] Error Tracking & Monitoring setup
- [ ] Accessibility Compliance
- [ ] Final Documentation
- [ ] Deployment Automation

**Phase 5: Go-Live (Week 9)**
- [ ] Final launch checklist
- [ ] DNS cutover
- [ ] Production deployment
- [ ] Post-launch monitoring

**Key Milestones:**
🎯 Week 2: Core Authentication Ready
🎯 Week 4: API Layer Complete
🎯 Week 6: Beta Release Checkpoint
🎯 Week 9: Go-Live Authorization

**Risk Assessment:**
- Authentication tasks are critical path — any delay impacts everything downstream
- Sam's workload needs redistribution before Phase 2
- Security audit should not be skipped for timeline pressure

Would you like me to create a detailed task breakdown for any of these phases?""",
                        'is_helpful': True,
                    },
                ]
            },
            
            # Session 8: Stakeholder Communication
            {
                'title': 'Stakeholder Update Strategy',
                'description': 'Help communicating project status to stakeholders',
                'is_active': True,
                'days_ago': 1,
                'board': 'software',
                'user': 'primary',
                'messages': [
                    {
                        'role': 'user',
                        'content': 'How should I communicate our project status to stakeholders?',
                    },
                    {
                        'role': 'assistant',
                        'content': """Based on your current project metrics, here's a stakeholder communication strategy:

**📊 Current Project Status Summary**

| Metric | Value | Status |
|--------|-------|--------|
| Tasks Completed | 7/30 | 🟡 23% |
| In Progress | 5/30 | ✅ On Track |
| Budget Spent | ~35% | ✅ On Track |
| Timeline | Phase 1 closing | 🟡 Minor delays |

**🎯 Recommended Communication Framework**

**1. Executive Summary (for Sarah Johnson, Product Owner)**
- Lead with outcomes, not activity
- Highlight: 7 foundation tasks complete, architecture approved
- Flag: Authentication system at 80%, needs 3 more days
- Next milestone: Core Authentication Ready

**2. Technical Update (for Mike Chen, Engineering Director)**
- Architecture design finalized and approved
- CI/CD pipeline operational
- Security architecture patterns defined
- Key risk: Database migrations blocking downstream tasks

**3. Quality Report (for Lisa Park, QA Lead)**
- Testing strategy defined for all phases
- Auth testing suite pending (blocked by auth completion)
- Integration testing framework selected

**Communication Cadence:**
- 📧 Weekly status email to all stakeholders
- 🗓️ Bi-weekly detailed review with Product Owner
- 🚨 Immediate escalation for blockers or scope changes

**Template for This Week's Update:**

> **Subject: Software Development - Week Update**
>
> **Progress:** 7 of 30 tasks complete (Phase 1: 70% done)
> **On Track:** ✅ Budget, Architecture, Environment
> **Attention Needed:** Authentication System (80% → targeting completion this week)
> **Next Week:** Complete auth, begin Phase 2 core features
> **Risks:** Sam's workload at 112% — redistribution planned

Would you like me to draft the full stakeholder email?""",
                        'is_helpful': True,
                    },
                ]
            },
            
            # Session 9: Technical Debt Analysis
            {
                'title': 'Technical Debt Assessment',
                'description': 'Analyzing and planning technical debt reduction',
                'is_active': False,
                'days_ago': 4,
                'board': 'software',
                'user': 'primary',
                'messages': [
                    {
                        'role': 'user',
                        'content': 'We have growing technical debt. Can you help assess and prioritize it?',
                    },
                    {
                        'role': 'assistant',
                        'content': """I've analyzed your codebase activity and task history to assess technical debt:

**📊 Technical Debt Assessment**

**Debt Category 1: Authentication Module (High Priority)**
- **Severity:** 🔴 High
- **Impact:** Security vulnerabilities, difficult to extend
- **Current State:** JWT implementation needs refactoring
- **Effort to Fix:** 8-12 hours
- **Business Risk:** Security audit will flag these issues

**Debt Category 2: Database Query Performance (Medium Priority)**
- **Severity:** 🟠 Medium
- **Impact:** Slow dashboard loading, poor user experience
- **Current State:** N+1 queries in task listing
- **Effort to Fix:** 6-8 hours
- **Business Risk:** Will worsen as data grows

**Debt Category 3: API Endpoint Consistency (Medium Priority)**
- **Severity:** 🟡 Medium
- **Impact:** Developer confusion, integration issues
- **Current State:** Mixed response formats across endpoints
- **Effort to Fix:** 4-6 hours
- **Business Risk:** Slows down new feature development

**Debt Category 4: Test Coverage Gaps (Low Priority)**
- **Severity:** 🟡 Low
- **Impact:** Regression risk on changes
- **Current State:** ~45% coverage, no integration tests
- **Effort to Fix:** 15-20 hours
- **Business Risk:** Increases bug rate over time

**Technical Debt Score: 6.5/10**

Would you like a detailed action plan for reducing this debt?""",
                        'is_helpful': True,
                    },
                    {
                        'role': 'user',
                        'content': 'Yes, give me an action plan to tackle the authentication debt first',
                    },
                    {
                        'role': 'assistant',
                        'content': """Here's a comprehensive plan for addressing the authentication technical debt:

**🎯 Authentication Module Refactoring Plan**

**Phase 1: Assessment & Planning (Day 1)**
- [ ] Document current auth flow and pain points
- [ ] Identify all endpoints using authentication
- [ ] Review security best practices for JWT
- [ ] Create test cases for current behavior

**Phase 2: Refactoring (Days 2-3)**
- [ ] Implement token refresh mechanism
- [ ] Standardize error responses for auth failures
- [ ] Add proper session management
- [ ] Implement rate limiting on auth endpoints

**Phase 3: Security Hardening (Day 4)**
- [ ] Add CSRF protection where missing
- [ ] Implement proper password hashing
- [ ] Add audit logging for auth events
- [ ] Review and fix token expiration policies

**Phase 4: Testing & Validation (Day 5)**
- [ ] Run the Authentication Testing Suite
- [ ] Perform security scanning
- [ ] Load test auth endpoints
- [ ] Update API documentation

**Assignment Recommendation:**
- **Lead:** Sam Rivera (Django/Python expert)
- **Review:** Alex Chen (project oversight)
- **Testing:** Jordan Taylor (business validation)

**Success Metrics:**
- ✅ Zero security vulnerabilities in auth module
- ✅ Token refresh working without user disruption
- ✅ 95%+ test coverage on auth code
- ✅ Response time < 200ms for auth endpoints

**Estimated Total Effort:** 5 developer-days
**Expected Impact:** 40% reduction in auth-related issues

Shall I create these as subtasks on your board?""",
                        'is_helpful': True,
                    },
                ]
            },
        ]
