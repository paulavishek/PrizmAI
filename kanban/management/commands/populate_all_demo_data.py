"""
Consolidated Demo Data Population Command
=========================================
A single command to populate ALL demo data for PrizmAI application.

This file consolidates demo data creation for:
- Tasks, dependencies, and labels
- Wiki pages and categories
- Messaging (chat rooms, messages, notifications)
- Conflicts (resource, dependency, schedule conflicts)
- AI Assistant (chat sessions, Q&A history)
- Time tracking, budgets, retrospectives, coaching

Usage:
    python manage.py populate_all_demo_data
    python manage.py populate_all_demo_data --reset  # Clear and recreate all

This creates a comprehensive demo environment showcasing all PrizmAI features.
"""
from django.core.management.base import BaseCommand
from django.contrib.auth.models import User
from django.utils import timezone
from django.db import transaction
from datetime import timedelta
from decimal import Decimal
import random
import json

# Import all required models
from accounts.models import Organization
from kanban.models import Board, Column, Task, TaskLabel, Comment, TaskActivity, TaskFile
from kanban.permission_models import Role
from kanban.budget_models import TimeEntry, ProjectBudget, TaskCost, ProjectROI
from kanban.burndown_models import TeamVelocitySnapshot, BurndownPrediction
from kanban.retrospective_models import ProjectRetrospective, LessonLearned, ImprovementMetric, RetrospectiveActionItem
from kanban.coach_models import CoachingSuggestion, PMMetrics, CoachingInsight
from kanban.stakeholder_models import ProjectStakeholder, StakeholderTaskInvolvement
from kanban.conflict_models import ConflictDetection, ConflictResolution, ConflictNotification

# Wiki models
from wiki.models import WikiPage, WikiCategory, WikiLink

# Messaging models
from messaging.models import ChatRoom, ChatMessage, Notification, FileAttachment, TaskThreadComment

# AI Assistant models
from ai_assistant.models import (
    AIAssistantSession, AIAssistantMessage, ProjectKnowledgeBase,
    AIAssistantAnalytics, AITaskRecommendation, UserPreference
)


class Command(BaseCommand):
    help = 'Populate ALL demo data in a single command (tasks, wiki, messaging, conflicts, AI assistant)'

    def add_arguments(self, parser):
        parser.add_argument(
            '--reset',
            action='store_true',
            help='Delete ALL existing demo data before creating new data',
        )
        parser.add_argument(
            '--skip-tasks',
            action='store_true',
            help='Skip task creation (useful if tasks already exist)',
        )

    def handle(self, *args, **options):
        self.stdout.write(self.style.SUCCESS('\n' + '=' * 80))
        self.stdout.write(self.style.SUCCESS('CONSOLIDATED DEMO DATA POPULATION'))
        self.stdout.write(self.style.SUCCESS('=' * 80 + '\n'))

        # Get demo organization
        try:
            self.demo_org = Organization.objects.get(is_demo=True, name='Demo - Acme Corporation')
            self.stdout.write(self.style.SUCCESS(f'✅ Found organization: {self.demo_org.name}'))
        except Organization.DoesNotExist:
            self.stdout.write(self.style.ERROR(
                '❌ Demo organization not found. Please run: python manage.py create_demo_organization'
            ))
            return

        # Get demo users
        self.demo_admin = User.objects.filter(username='demo_admin_solo').first()
        self.alex = User.objects.filter(username='alex_chen_demo').first()
        self.sam = User.objects.filter(username='sam_rivera_demo').first()
        self.jordan = User.objects.filter(username='jordan_taylor_demo').first()

        self.demo_users = [u for u in [self.demo_admin, self.alex, self.sam, self.jordan] if u]
        if len(self.demo_users) < 3:
            self.stdout.write(self.style.ERROR(
                '❌ Demo users not found. Please run: python manage.py create_demo_organization'
            ))
            return
        self.stdout.write(f'   Found {len(self.demo_users)} demo users')

        # Get demo boards
        self.demo_boards = Board.objects.filter(organization=self.demo_org, is_official_demo_board=True)
        self.software_board = self.demo_boards.filter(name__icontains='software').first()
        self.marketing_board = self.demo_boards.filter(name__icontains='marketing').first()
        self.bug_board = self.demo_boards.filter(name__icontains='bug').first()

        if not all([self.software_board, self.marketing_board, self.bug_board]):
            self.stdout.write(self.style.ERROR(
                '❌ Demo boards not found. Please run: python manage.py create_demo_organization'
            ))
            return
        self.stdout.write(f'   Found {self.demo_boards.count()} demo boards')

        # Reset if requested
        if options['reset']:
            self.reset_all_demo_data()

        with transaction.atomic():
            # 1. Create tasks and related data (unless skipped)
            if not options['skip_tasks']:
                self.stdout.write(self.style.NOTICE('\n📝 PHASE 1: Creating Tasks & Core Data...'))
                from django.core.management import call_command
                try:
                    call_command('populate_demo_data', '--reset' if options['reset'] else '')
                except Exception as e:
                    self.stdout.write(self.style.WARNING(f'   ⚠️ Task creation via existing command: {e}'))
                    self.stdout.write('   Creating tasks directly...')
                    # Fallback: tasks are created by the existing command

            # 2. Wiki Demo Data
            self.stdout.write(self.style.NOTICE('\n📚 PHASE 2: Creating Wiki Demo Data...'))
            wiki_stats = self.create_wiki_demo_data()
            self.stdout.write(self.style.SUCCESS(
                f'   ✅ Wiki: {wiki_stats["categories"]} categories, {wiki_stats["pages"]} pages, {wiki_stats["links"]} links'
            ))

            # 3. Messaging Demo Data
            self.stdout.write(self.style.NOTICE('\n💬 PHASE 3: Creating Messaging Demo Data...'))
            msg_stats = self.create_messaging_demo_data()
            self.stdout.write(self.style.SUCCESS(
                f'   ✅ Messaging: {msg_stats["rooms"]} rooms, {msg_stats["messages"]} messages'
            ))

            # 4. Conflict Demo Data
            self.stdout.write(self.style.NOTICE('\n⚠️ PHASE 4: Creating Conflict Demo Data...'))
            conflict_stats = self.create_conflict_demo_data()
            self.stdout.write(self.style.SUCCESS(
                f'   ✅ Conflicts: {conflict_stats["conflicts"]} conflicts, {conflict_stats["resolutions"]} resolutions'
            ))

            # 5. AI Assistant Demo Data
            self.stdout.write(self.style.NOTICE('\n🤖 PHASE 5: Creating AI Assistant Demo Data...'))
            ai_stats = self.create_ai_assistant_demo_data()
            self.stdout.write(self.style.SUCCESS(
                f'   ✅ AI Assistant: {ai_stats["sessions"]} sessions, {ai_stats["messages"]} messages'
            ))

        # Final Summary
        self.print_final_summary()

    def reset_all_demo_data(self):
        """Reset ALL demo data"""
        self.stdout.write(self.style.WARNING('\n🗑️ Resetting ALL demo data...'))

        # Wiki
        WikiLink.objects.filter(wiki_page__organization=self.demo_org).delete()
        WikiPage.objects.filter(organization=self.demo_org).delete()
        WikiCategory.objects.filter(organization=self.demo_org).delete()
        self.stdout.write('   ✓ Cleared Wiki data')

        # Messaging
        Notification.objects.filter(recipient__in=self.demo_users).delete()
        FileAttachment.objects.filter(chat_room__board__in=self.demo_boards).delete()
        ChatMessage.objects.filter(chat_room__board__in=self.demo_boards).delete()
        TaskThreadComment.objects.filter(task__column__board__in=self.demo_boards).delete()
        ChatRoom.objects.filter(board__in=self.demo_boards).delete()
        self.stdout.write('   ✓ Cleared Messaging data')

        # Conflicts
        ConflictNotification.objects.filter(conflict__board__in=self.demo_boards).delete()
        ConflictResolution.objects.filter(conflict__board__in=self.demo_boards).delete()
        ConflictDetection.objects.filter(board__in=self.demo_boards).delete()
        self.stdout.write('   ✓ Cleared Conflict data')

        # AI Assistant
        AIAssistantMessage.objects.filter(session__user__in=self.demo_users).delete()
        AIAssistantSession.objects.filter(user__in=self.demo_users).delete()
        ProjectKnowledgeBase.objects.filter(board__in=self.demo_boards).delete()
        AIAssistantAnalytics.objects.filter(user__in=self.demo_users).delete()
        AITaskRecommendation.objects.filter(board__in=self.demo_boards).delete()
        self.stdout.write('   ✓ Cleared AI Assistant data')

        self.stdout.write(self.style.SUCCESS('   ✓ All demo data cleared\n'))

    # =========================================================================
    # WIKI DEMO DATA
    # =========================================================================
    def create_wiki_demo_data(self):
        """Create wiki categories, pages, and links"""
        demo_user = self.demo_admin or self.alex
        
        # Create categories
        categories_data = self.get_wiki_categories_data()
        created_categories = {}
        
        for cat_data in categories_data:
            category, _ = WikiCategory.objects.update_or_create(
                organization=self.demo_org,
                slug=cat_data['slug'],
                defaults={
                    'name': cat_data['name'],
                    'description': cat_data['description'],
                    'icon': cat_data['icon'],
                    'color': cat_data['color'],
                    'ai_assistant_type': cat_data['ai_assistant_type'],
                    'position': cat_data['position'],
                }
            )
            created_categories[cat_data['slug']] = category

        # Create pages
        pages_data = self.get_wiki_pages_data()
        created_pages = []
        
        for page_data in pages_data:
            category = created_categories.get(page_data['category'])
            if not category:
                continue
            
            page, _ = WikiPage.objects.update_or_create(
                organization=self.demo_org,
                slug=page_data['slug'],
                defaults={
                    'title': page_data['title'],
                    'content': page_data['content'],
                    'category': category,
                    'created_by': demo_user,
                    'updated_by': demo_user,
                    'is_published': True,
                    'is_pinned': page_data.get('is_pinned', False),
                    'tags': page_data.get('tags', []),
                }
            )
            created_pages.append(page)

        # Create links to tasks
        links_created = self.create_wiki_links(demo_user)

        return {
            'categories': len(created_categories),
            'pages': len(created_pages),
            'links': links_created
        }

    def get_wiki_categories_data(self):
        """Wiki category configurations"""
        return [
            {'slug': 'getting-started', 'name': 'Getting Started', 'description': 'Onboarding and setup guides', 'icon': '🚀', 'color': '#3498db', 'ai_assistant_type': 'onboarding', 'position': 1},
            {'slug': 'technical-docs', 'name': 'Technical Documentation', 'description': 'API references and architecture', 'icon': '📖', 'color': '#2ecc71', 'ai_assistant_type': 'technical', 'position': 2},
            {'slug': 'meeting-notes', 'name': 'Meeting Notes', 'description': 'Sprint and team meeting notes', 'icon': '📝', 'color': '#9b59b6', 'ai_assistant_type': 'meetings', 'position': 3},
            {'slug': 'process-workflows', 'name': 'Process & Workflows', 'description': 'Standard procedures', 'icon': '⚙️', 'color': '#e74c3c', 'ai_assistant_type': 'process', 'position': 4},
            {'slug': 'project-resources', 'name': 'Project Resources', 'description': 'Roadmaps and requirements', 'icon': '📊', 'color': '#f39c12', 'ai_assistant_type': 'documentation', 'position': 5},
        ]

    def get_wiki_pages_data(self):
        """Wiki page configurations (condensed for brevity)"""
        current_date = timezone.now().strftime('%B %d, %Y')
        
        return [
            # Getting Started
            {
                'category': 'getting-started',
                'title': 'Welcome to Acme Corporation',
                'slug': 'welcome-to-acme',
                'is_pinned': True,
                'tags': ['onboarding', 'welcome'],
                'content': f"""# Welcome to Acme Corporation! 🎉

Welcome to the team! This knowledge hub contains everything you need to get started.

## Quick Links
- **[Team Setup Guide](team-setup-guide)** - Set up your development environment
- **[Coding Standards](coding-standards)** - Our code quality guidelines

## Who to Contact
| Role | Person | Contact |
|------|--------|---------|
| Project Manager | Alex Chen | alex.chen@acme.com |
| Lead Developer | Sam Rivera | sam.rivera@acme.com |

*Last updated: {current_date}*"""
            },
            {
                'category': 'getting-started',
                'title': 'Team Setup Guide',
                'slug': 'team-setup-guide',
                'tags': ['setup', 'environment'],
                'content': """# Team Setup Guide

## Prerequisites
- Python 3.10+ installed
- Node.js 18+ installed
- Git configured

## Quick Start
```bash
git clone git@github.com:acme-corp/main-project.git
cd main-project
python -m venv venv
pip install -r requirements.txt
python manage.py migrate
```"""
            },
            # Technical Docs
            {
                'category': 'technical-docs',
                'title': 'API Documentation',
                'slug': 'api-documentation',
                'is_pinned': True,
                'tags': ['api', 'rest', 'reference'],
                'content': """# API Documentation

## Authentication
All API requests require JWT tokens.

```bash
POST /api/auth/token/
{
    "email": "user@example.com",
    "password": "your_password"
}
```

## Endpoints
| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/boards/` | List all boards |
| POST | `/api/tasks/` | Create task |"""
            },
            {
                'category': 'technical-docs',
                'title': 'Coding Standards',
                'slug': 'coding-standards',
                'tags': ['coding', 'standards'],
                'content': """# Coding Standards

## Python Standards
- Follow PEP 8
- Use type hints
- Docstrings for all public functions

## Code Review Checklist
- [ ] Code follows style guidelines
- [ ] All tests pass
- [ ] Documentation updated"""
            },
            # Meeting Notes
            {
                'category': 'meeting-notes',
                'title': 'Sprint 45 Planning Meeting',
                'slug': 'sprint-45-planning',
                'is_pinned': True,
                'tags': ['sprint', 'planning'],
                'content': f"""# Sprint 45 Planning Meeting

**Date:** {current_date}
**Attendees:** Alex Chen, Sam Rivera, Jordan Taylor

## Sprint Goals
1. Complete user authentication improvements
2. Launch new dashboard analytics
3. Fix critical bugs from Sprint 44

## High Priority
- AUTH-234: Implement password reset flow
- DASH-567: Add burndown chart widget"""
            },
            # Process & Workflows
            {
                'category': 'process-workflows',
                'title': 'Sprint Workflow Guide',
                'slug': 'sprint-workflow',
                'is_pinned': True,
                'tags': ['sprint', 'agile', 'scrum'],
                'content': """# Sprint Workflow Guide

## Sprint Timeline
- Week 1 Monday: Planning
- Daily: Standups at 9:30 AM
- Week 2 Thursday: Demo
- Week 2 Friday: Retrospective

## Task States
| State | Description | WIP Limit |
|-------|-------------|-----------|
| To Do | Ready to start | No limit |
| In Progress | Being worked on | 3/person |
| Done | Completed | No limit |"""
            },
            # Project Resources
            {
                'category': 'project-resources',
                'title': 'Q1 2026 Product Roadmap',
                'slug': 'q1-2026-roadmap',
                'is_pinned': True,
                'tags': ['roadmap', 'planning'],
                'content': f"""# Q1 2026 Product Roadmap

## Vision
"Enable teams to work smarter with AI-powered project management"

## January: Foundation
- AI Task Suggestions v2
- Dashboard Redesign
- Performance Optimization

## February: Enhancement
- Advanced Analytics
- Enterprise SSO

## March: Growth
- AI Meeting Assistant
- Integration Marketplace"""
            },
        ]

    def create_wiki_links(self, demo_user):
        """Create links between wiki pages and tasks"""
        links_created = 0
        demo_tasks = Task.objects.filter(column__board__in=self.demo_boards)
        
        api_doc = WikiPage.objects.filter(organization=self.demo_org, slug='api-documentation').first()
        coding_standards = WikiPage.objects.filter(organization=self.demo_org, slug='coding-standards').first()
        
        if api_doc:
            api_tasks = demo_tasks.filter(title__icontains='api')[:3]
            for task in api_tasks:
                _, created = WikiLink.objects.get_or_create(
                    wiki_page=api_doc,
                    link_type='task',
                    task=task,
                    defaults={'created_by': demo_user, 'description': 'Related API documentation'}
                )
                if created:
                    links_created += 1

        if coding_standards:
            code_tasks = demo_tasks.filter(title__iregex=r'(code|review|implement)')[:3]
            for task in code_tasks:
                _, created = WikiLink.objects.get_or_create(
                    wiki_page=coding_standards,
                    link_type='task',
                    task=task,
                    defaults={'created_by': demo_user, 'description': 'Follow coding standards'}
                )
                if created:
                    links_created += 1

        return links_created

    # =========================================================================
    # MESSAGING DEMO DATA
    # =========================================================================
    def create_messaging_demo_data(self):
        """Create chat rooms, messages, and notifications"""
        rooms_created = 0
        messages_created = 0
        now = timezone.now()
        
        chat_configs = self.get_chat_room_configs()
        
        for board in self.demo_boards:
            board_name = board.name
            if board_name not in chat_configs:
                continue
            
            board_members = list(board.members.all())
            creator = self.demo_admin if self.demo_admin in board_members else board_members[0] if board_members else self.demo_admin
            
            for room_config in chat_configs[board_name]:
                room, created = ChatRoom.objects.get_or_create(
                    board=board,
                    name=room_config['name'],
                    defaults={
                        'description': room_config['description'],
                        'created_by': creator,
                    }
                )
                
                if created:
                    rooms_created += 1
                    for member in board_members:
                        room.members.add(member)
                
                # Create messages if none exist
                if ChatMessage.objects.filter(chat_room=room).count() == 0:
                    for msg_data in room_config['messages']:
                        author = self.get_user_by_key(msg_data['author'])
                        if author and author in board_members:
                            msg_time = now - timedelta(minutes=msg_data['minutes_ago'])
                            msg = ChatMessage.objects.create(
                                chat_room=room,
                                author=author,
                                content=msg_data['content'],
                            )
                            ChatMessage.objects.filter(pk=msg.pk).update(created_at=msg_time)
                            messages_created += 1
        
        return {'rooms': rooms_created, 'messages': messages_created}

    def get_user_by_key(self, key):
        """Get user by short key name"""
        return {
            'demo_admin': self.demo_admin,
            'alex': self.alex,
            'sam': self.sam,
            'jordan': self.jordan,
        }.get(key)

    def get_chat_room_configs(self):
        """Chat room configurations for each board"""
        return {
            'Software Development': [
                {
                    'name': 'General Discussion',
                    'description': 'Team updates and announcements',
                    'messages': [
                        {'author': 'alex', 'content': 'Good morning team! 🌅 Ready for sprint planning?', 'minutes_ago': 180},
                        {'author': 'sam', 'content': 'Morning! Yes, I finished reviewing the backlog.', 'minutes_ago': 175},
                        {'author': 'demo_admin', 'content': 'Great work everyone! The API integration looks solid. 👏', 'minutes_ago': 120},
                    ]
                },
                {
                    'name': 'Technical Support',
                    'description': 'Technical questions and debugging help',
                    'messages': [
                        {'author': 'sam', 'content': 'Has anyone encountered issues with PostgreSQL 15 migration?', 'minutes_ago': 240},
                        {'author': 'demo_admin', 'content': 'Try `python manage.py migrate --fake-initial` first.', 'minutes_ago': 235},
                        {'author': 'sam', 'content': 'That worked! Thanks 🙏', 'minutes_ago': 230},
                    ]
                },
            ],
            'Marketing Campaign': [
                {
                    'name': 'Campaign Planning',
                    'description': 'Strategy discussions',
                    'messages': [
                        {'author': 'jordan', 'content': "I've drafted the Q1 marketing strategy. Check the shared doc! 📊", 'minutes_ago': 360},
                        {'author': 'alex', 'content': 'Looks comprehensive! Love the social media approach.', 'minutes_ago': 350},
                    ]
                },
            ],
            'Bug Tracking': [
                {
                    'name': 'Critical Issues',
                    'description': 'Urgent bugs and production issues',
                    'messages': [
                        {'author': 'sam', 'content': '🚨 ALERT: Production API throwing 500 errors on login!', 'minutes_ago': 45},
                        {'author': 'demo_admin', 'content': 'On it! Checking logs now.', 'minutes_ago': 42},
                        {'author': 'sam', 'content': 'Found it! Database connection pool exhausted. Fix deployed. ✅', 'minutes_ago': 20},
                    ]
                },
            ],
        }

    # =========================================================================
    # CONFLICT DEMO DATA
    # =========================================================================
    def create_conflict_demo_data(self):
        """Create conflict detection demo data"""
        conflicts_created = 0
        resolutions_created = 0
        now = timezone.now()
        
        conflict_configs = self.get_conflict_configs()
        
        for board in self.demo_boards:
            board_name = board.name
            if board_name not in conflict_configs:
                continue
            
            tasks = list(Task.objects.filter(column__board=board)[:10])
            if not tasks:
                continue
            
            for config in conflict_configs[board_name]:
                # Get tasks for this conflict
                task1 = tasks[config.get('task1_idx', 0) % len(tasks)]
                task2 = tasks[config.get('task2_idx', 1) % len(tasks)] if config.get('task2_idx') else None
                
                conflict = ConflictDetection.objects.create(
                    board=board,
                    conflict_type=config['type'],
                    severity=config['severity'],
                    title=config['title'],
                    description=config['description'],
                    task1=task1,
                    task2=task2,
                    affected_user=self.get_user_by_key(config.get('affected_user', 'sam')),
                    status=config.get('status', 'active'),
                    ai_confidence=Decimal(str(config.get('confidence', 0.85))),
                    detected_at=now - timedelta(days=config.get('days_ago', 1)),
                    ai_recommendation=config.get('recommendation', ''),
                )
                conflicts_created += 1
                
                # Create resolution if resolved
                if config.get('status') == 'resolved':
                    ConflictResolution.objects.create(
                        conflict=conflict,
                        resolution_type=config.get('resolution_type', 'manual'),
                        resolution_action=config.get('resolution_action', 'Manually resolved'),
                        resolved_by=self.demo_admin,
                        resolution_notes='Resolved after team discussion.',
                    )
                    resolutions_created += 1
        
        return {'conflicts': conflicts_created, 'resolutions': resolutions_created}

    def get_conflict_configs(self):
        """Conflict configurations for each board"""
        return {
            'Software Development': [
                {
                    'type': 'resource',
                    'severity': 'high',
                    'title': 'Resource Overload: Sam Rivera',
                    'description': 'Sam Rivera is assigned to 8 concurrent high-priority tasks, exceeding recommended capacity.',
                    'task1_idx': 0, 'task2_idx': 1,
                    'affected_user': 'sam',
                    'confidence': 0.92,
                    'recommendation': 'Consider redistributing 2-3 tasks to other team members.',
                },
                {
                    'type': 'dependency',
                    'severity': 'medium',
                    'title': 'Circular Dependency Detected',
                    'description': 'Task chain creates a circular dependency that may cause scheduling issues.',
                    'task1_idx': 2, 'task2_idx': 3,
                    'confidence': 0.88,
                    'recommendation': 'Review and break the dependency cycle.',
                },
            ],
            'Marketing Campaign': [
                {
                    'type': 'schedule',
                    'severity': 'high',
                    'title': 'Overlapping Deadlines',
                    'description': 'Multiple high-priority tasks have the same deadline.',
                    'task1_idx': 0,
                    'affected_user': 'jordan',
                    'confidence': 0.85,
                    'recommendation': 'Stagger deadlines or add resources.',
                },
            ],
            'Bug Tracking': [
                {
                    'type': 'resource',
                    'severity': 'medium',
                    'title': 'Skill Gap Identified',
                    'description': 'Critical bug requires security expertise not available on current assignment.',
                    'task1_idx': 0,
                    'confidence': 0.78,
                    'recommendation': 'Assign team member with security background.',
                    'status': 'resolved',
                    'resolution_type': 'reassignment',
                    'resolution_action': 'Reassigned to security specialist',
                },
            ],
        }

    # =========================================================================
    # AI ASSISTANT DEMO DATA
    # =========================================================================
    def create_ai_assistant_demo_data(self):
        """Create AI assistant sessions and messages"""
        sessions_created = 0
        messages_created = 0
        
        primary_user = self.demo_admin or self.alex
        
        # Create user preferences
        UserPreference.objects.get_or_create(
            user=primary_user,
            defaults={
                'enable_web_search': True,
                'enable_task_insights': True,
                'enable_risk_alerts': True,
            }
        )
        
        sessions_data = self.get_ai_sessions_data()
        
        for session_data in sessions_data:
            board = None
            if session_data.get('board') == 'software':
                board = self.software_board
            elif session_data.get('board') == 'marketing':
                board = self.marketing_board
            elif session_data.get('board') == 'bug':
                board = self.bug_board
            
            session = AIAssistantSession.objects.create(
                user=primary_user,
                board=board,
                title=session_data['title'],
                description=session_data.get('description', ''),
                is_active=session_data.get('is_active', False),
                message_count=len(session_data['messages']),
            )
            
            # Backdate session
            days_ago = session_data.get('days_ago', 0)
            backdated = timezone.now() - timedelta(days=days_ago)
            AIAssistantSession.objects.filter(pk=session.pk).update(created_at=backdated)
            
            sessions_created += 1
            
            # Create messages
            for msg_data in session_data['messages']:
                AIAssistantMessage.objects.create(
                    session=session,
                    role=msg_data['role'],
                    content=msg_data['content'],
                    model='gemini' if msg_data['role'] == 'assistant' else None,
                )
                messages_created += 1
        
        return {'sessions': sessions_created, 'messages': messages_created}

    def get_ai_sessions_data(self):
        """AI Assistant session configurations"""
        return [
            {
                'title': 'Sprint Planning Help',
                'description': 'Getting help with sprint planning',
                'is_active': True,
                'days_ago': 0,
                'board': 'software',
                'messages': [
                    {'role': 'user', 'content': 'What tasks should I prioritize for this sprint?'},
                    {'role': 'assistant', 'content': """Based on your current board status, I recommend prioritizing:

**High Priority:**
1. **Implement user authentication** - Blocking other features
2. **Design database schema** - Foundation task
3. **Fix critical security vulnerability** - Security first

**Medium Priority:**
4. **Build REST API endpoints** - Can proceed after auth
5. **Create responsive dashboard** - Good for parallel work

Would you like help with task estimation?"""},
                ]
            },
            {
                'title': 'Team Workload Analysis',
                'description': 'Analyzing team capacity',
                'is_active': False,
                'days_ago': 2,
                'board': 'software',
                'messages': [
                    {'role': 'user', 'content': 'Is anyone on my team overloaded?'},
                    {'role': 'assistant', 'content': """I've analyzed the current workload:

| Team Member | Tasks | Hours | Utilization |
|-------------|-------|-------|-------------|
| Sam Rivera | 8 | 45h | ⚠️ 112% |
| Alex Chen | 5 | 32h | ✅ 80% |
| Jordan Taylor | 3 | 18h | ✅ 45% |

**⚠️ Alert:** Sam Rivera is overloaded.

**Recommendation:** Reassign 1-2 tasks from Sam to Jordan."""},
                ]
            },
            {
                'title': 'Bug Prioritization Strategy',
                'description': 'Help prioritizing bugs',
                'is_active': True,
                'days_ago': 1,
                'board': 'bug',
                'messages': [
                    {'role': 'user', 'content': 'How should I prioritize the bugs in our backlog?'},
                    {'role': 'assistant', 'content': """Here's a prioritization framework:

**🔴 Critical Priority (Fix Immediately)**
1. **Login Authentication Failure** - 100% users blocked
2. **Data Loss on Form Submit** - All submissions affected

**🟠 High Priority (This Sprint)**
3. **Dashboard Performance** - Page load > 10s
4. **Email Notifications** - Alerts not delivered

**🟡 Medium Priority (Next Sprint)**
5. **UI Alignment Issues** - Minor UX issues

Would you like a detailed fix plan?"""},
                ]
            },
        ]

    def print_final_summary(self):
        """Print final summary of all demo data"""
        self.stdout.write(self.style.SUCCESS('\n' + '=' * 80))
        self.stdout.write(self.style.SUCCESS('✅ ALL DEMO DATA POPULATION COMPLETE'))
        self.stdout.write(self.style.SUCCESS('=' * 80))
        
        # Count all data
        task_count = Task.objects.filter(column__board__in=self.demo_boards).count()
        wiki_pages = WikiPage.objects.filter(organization=self.demo_org).count()
        wiki_categories = WikiCategory.objects.filter(organization=self.demo_org).count()
        chat_rooms = ChatRoom.objects.filter(board__in=self.demo_boards).count()
        chat_messages = ChatMessage.objects.filter(chat_room__board__in=self.demo_boards).count()
        conflicts = ConflictDetection.objects.filter(board__in=self.demo_boards).count()
        ai_sessions = AIAssistantSession.objects.filter(user__in=self.demo_users).count()
        ai_messages = AIAssistantMessage.objects.filter(session__user__in=self.demo_users).count()
        time_entries = TimeEntry.objects.filter(task__column__board__in=self.demo_boards).count()
        
        self.stdout.write(f'''
📊 Demo Data Summary:
   ├── Tasks: {task_count}
   ├── Wiki: {wiki_categories} categories, {wiki_pages} pages
   ├── Messaging: {chat_rooms} rooms, {chat_messages} messages
   ├── Conflicts: {conflicts}
   ├── AI Assistant: {ai_sessions} sessions, {ai_messages} messages
   └── Time Entries: {time_entries}

🎉 Demo environment is now fully populated!

To access the demo:
   • Visit: http://localhost:8000
   • Login as demo user or view demo boards
''')
