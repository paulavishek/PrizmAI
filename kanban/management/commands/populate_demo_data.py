"""
Management command to populate demo boards with realistic tasks
Creates 90 tasks across 3 demo boards (30 per board) with proper assignments, dates, dependencies, and skills
Each board has 3 phases with 10 tasks per phase
Includes comprehensive demo data for all task fields including risk, skills, and collaboration
Also includes comments, activity logs, stakeholders, wiki links, and file attachment metadata
"""
from django.core.management.base import BaseCommand
from django.utils import timezone
from django.contrib.auth import get_user_model
from django.db import models
from datetime import timedelta, date
from decimal import Decimal
from kanban.models import (
    Board, Column, Task, TaskLabel, Organization, Comment, TaskActivity, TaskFile,
    TeamSkillProfile, SkillGap, ScopeChangeSnapshot, ScopeCreepAlert
)
from kanban.permission_models import Role
from kanban.budget_models import TimeEntry, ProjectBudget, TaskCost, ProjectROI
from kanban.burndown_models import TeamVelocitySnapshot, BurndownPrediction, SprintMilestone
from kanban.retrospective_models import ProjectRetrospective, LessonLearned, ImprovementMetric, RetrospectiveActionItem
from kanban.coach_models import CoachingSuggestion, PMMetrics, CoachingInsight
from kanban.stakeholder_models import ProjectStakeholder, StakeholderTaskInvolvement
import random
import os

User = get_user_model()

# Comment templates for realistic demo comments
COMMENT_TEMPLATES = [
    # Progress updates
    "Made good progress on this today. {progress_detail}",
    "Updated the implementation based on the latest requirements. Looking good so far!",
    "Just finished the initial draft. Ready for review.",
    "Ran into a small issue with {technical_detail}, but found a workaround.",
    "This is taking a bit longer than expected due to {complexity_reason}.",

    # Questions
    "@{mention} Could you take a look at this when you get a chance?",
    "Question: Should we prioritize performance or feature completeness here?",
    "Need clarification on the acceptance criteria for this task.",
    "Has anyone encountered this issue before? Looking for suggestions.",

    # Reviews and feedback
    "Code review complete. Left some minor suggestions for improvement.",
    "LGTM! Just a few minor style issues to address.",
    "Great work on this! The implementation is clean and well-documented.",
    "Approved with minor changes. Please update the documentation.",

    # Status updates
    "Blocked by dependency on {related_task}. Will resume once that's complete.",
    "Moving this to In Review - all tests passing.",
    "Deployed to staging for QA testing.",
    "All edge cases covered. This is ready for final review.",

    # Collaboration
    "Had a productive discussion with the team about this approach.",
    "Paired with @{mention} to work through the complex parts.",
    "Added comprehensive test coverage for the new functionality.",
    "Updated based on stakeholder feedback from yesterday's meeting.",
]

# Technical details for comment templates
TECHNICAL_DETAILS = [
    "the database connection pooling",
    "the authentication flow",
    "the API rate limiting",
    "the caching layer",
    "the WebSocket integration",
    "the file upload handler",
    "the search indexing",
    "the permission checks",
]

PROGRESS_DETAILS = [
    "Completed the core functionality and started on edge cases.",
    "The main feature is working, now adding polish and error handling.",
    "Integration with the existing system is complete.",
    "Unit tests are all passing, moving to integration tests.",
    "Documentation is updated with the new changes.",
]

COMPLEXITY_REASONS = [
    "some unexpected edge cases",
    "integration with legacy code",
    "performance optimization requirements",
    "additional security considerations",
    "cross-browser compatibility issues",
]

# Activity log templates
ACTIVITY_TEMPLATES = {
    'created': [
        "created this task",
        "added this task to the board",
    ],
    'moved': [
        "moved this task from {from_col} to {to_col}",
        "updated status to {to_col}",
    ],
    'assigned': [
        "assigned this task to {assignee}",
        "changed assignee to {assignee}",
    ],
    'updated': [
        "updated the description",
        "changed priority to {priority}",
        "updated the due date",
        "modified the complexity score",
        "added required skills",
        "updated progress to {progress}%",
    ],
    'commented': [
        "added a comment",
        "replied to a comment",
    ],
    'label_added': [
        "added label '{label}'",
    ],
    'label_removed': [
        "removed label '{label}'",
    ],
}

# Skill pools for different task categories
SOFTWARE_SKILLS = [
    {'name': 'Python', 'level': 'Advanced'},
    {'name': 'JavaScript', 'level': 'Advanced'},
    {'name': 'React', 'level': 'Intermediate'},
    {'name': 'Django', 'level': 'Advanced'},
    {'name': 'PostgreSQL', 'level': 'Intermediate'},
    {'name': 'REST API Design', 'level': 'Advanced'},
    {'name': 'Docker', 'level': 'Intermediate'},
    {'name': 'AWS', 'level': 'Intermediate'},
    {'name': 'CI/CD', 'level': 'Intermediate'},
    {'name': 'Git', 'level': 'Advanced'},
    {'name': 'TypeScript', 'level': 'Intermediate'},
    {'name': 'Testing', 'level': 'Intermediate'},
    {'name': 'Security', 'level': 'Intermediate'},
    {'name': 'System Design', 'level': 'Advanced'},
]

MARKETING_SKILLS = [
    {'name': 'Content Strategy', 'level': 'Advanced'},
    {'name': 'SEO/SEM', 'level': 'Intermediate'},
    {'name': 'Social Media Marketing', 'level': 'Advanced'},
    {'name': 'Email Marketing', 'level': 'Intermediate'},
    {'name': 'Analytics', 'level': 'Advanced'},
    {'name': 'Copywriting', 'level': 'Advanced'},
    {'name': 'Graphic Design', 'level': 'Intermediate'},
    {'name': 'Video Production', 'level': 'Intermediate'},
    {'name': 'Brand Management', 'level': 'Advanced'},
    {'name': 'Market Research', 'level': 'Intermediate'},
    {'name': 'Campaign Management', 'level': 'Advanced'},
    {'name': 'Public Relations', 'level': 'Intermediate'},
]

BUG_TRACKING_SKILLS = [
    {'name': 'Debugging', 'level': 'Advanced'},
    {'name': 'Root Cause Analysis', 'level': 'Advanced'},
    {'name': 'Testing', 'level': 'Intermediate'},
    {'name': 'Log Analysis', 'level': 'Intermediate'},
    {'name': 'Performance Profiling', 'level': 'Intermediate'},
    {'name': 'Database Troubleshooting', 'level': 'Intermediate'},
    {'name': 'Network Diagnostics', 'level': 'Intermediate'},
    {'name': 'Security Analysis', 'level': 'Advanced'},
    {'name': 'Code Review', 'level': 'Advanced'},
    {'name': 'Documentation', 'level': 'Intermediate'},
]

# Risk indicators pool
RISK_INDICATORS = [
    'Monitor task progress weekly',
    'Track team member availability',
    'Review dependencies status',
    'Check for scope changes',
    'Verify resource allocation',
    'Monitor technical blockers',
    'Track stakeholder feedback',
    'Review project deadlines',
    'Check integration points',
    'Monitor external dependencies',
    'Track skill availability',
    'Review budget constraints',
]

# Mitigation strategies pool
MITIGATION_STRATEGIES = [
    'Allocate additional resources if needed',
    'Conduct technical review early',
    'Break down into smaller subtasks',
    'Schedule regular check-ins',
    'Identify backup team members',
    'Create contingency timeline',
    'Document key decisions',
    'Set up automated alerts',
    'Plan for parallel work streams',
    'Establish clear escalation path',
    'Prepare fallback solutions',
    'Schedule buffer time',
]


class Command(BaseCommand):
    help = 'Populate demo boards with realistic tasks for demonstration purposes'

    def get_random_skills(self, skill_pool, min_skills=1, max_skills=3):
        """Get random skills from a skill pool"""
        num_skills = random.randint(min_skills, max_skills)
        return random.sample(skill_pool, min(num_skills, len(skill_pool)))

    def calculate_risk_data(self, complexity, priority, progress):
        """Calculate comprehensive risk data based on task characteristics"""
        # Base risk likelihood on complexity and priority
        if priority in ['urgent', 'high'] and complexity >= 7:
            likelihood = 3  # High
        elif priority in ['urgent', 'high'] or complexity >= 6:
            likelihood = 2  # Medium
        else:
            likelihood = 1  # Low

        # Base risk impact on priority and complexity
        if priority == 'urgent' or complexity >= 8:
            impact = 3  # High
        elif priority == 'high' or complexity >= 5:
            impact = 2  # Medium
        else:
            impact = 1  # Low

        # If task is mostly complete, reduce risk
        if progress >= 80:
            likelihood = max(1, likelihood - 1)
            impact = max(1, impact - 1)

        risk_score = likelihood * impact

        # Determine risk level
        if risk_score <= 2:
            risk_level = 'low'
        elif risk_score <= 4:
            risk_level = 'medium'
        elif risk_score <= 6:
            risk_level = 'high'
        else:
            risk_level = 'critical'

        # Select relevant risk indicators (2-4 indicators)
        num_indicators = random.randint(2, 4)
        indicators = random.sample(RISK_INDICATORS, num_indicators)

        # Select mitigation strategies (2-3 strategies)
        num_strategies = random.randint(2, 3)
        strategies = random.sample(MITIGATION_STRATEGIES, num_strategies)

        return {
            'likelihood': likelihood,
            'impact': impact,
            'score': risk_score,
            'level': risk_level,
            'indicators': indicators,
            'strategies': strategies,
        }

    def get_workload_impact(self, complexity, priority):
        """Determine workload impact based on complexity and priority"""
        if priority == 'urgent' or complexity >= 8:
            return 'critical'
        elif priority == 'high' or complexity >= 6:
            return 'high'
        elif complexity >= 4:
            return 'medium'
        else:
            return 'low'

    def get_skill_match_score(self, has_assignee, complexity):
        """Generate a realistic skill match score"""
        if not has_assignee:
            return None
        # Higher complexity tasks might have lower match scores
        base_score = random.randint(60, 95)
        complexity_penalty = max(0, (complexity - 5) * 3)
        return max(50, base_score - complexity_penalty)

    def should_require_collaboration(self, complexity, priority):
        """Determine if task should require collaboration"""
        # High complexity or urgent tasks more likely to need collaboration
        if complexity >= 8 or priority == 'urgent':
            return random.random() < 0.7  # 70% chance
        elif complexity >= 6 or priority == 'high':
            return random.random() < 0.4  # 40% chance
        else:
            return random.random() < 0.2  # 20% chance

    def add_arguments(self, parser):
        parser.add_argument(
            '--reset',
            action='store_true',
            help='Delete existing demo tasks before creating new ones',
        )

    def handle(self, *args, **options):
        self.stdout.write(self.style.SUCCESS('\n' + '='*70))
        self.stdout.write(self.style.SUCCESS('DEMO DATA POPULATION'))
        self.stdout.write(self.style.SUCCESS('='*70 + '\n'))

        # Get demo organization
        try:
            demo_org = Organization.objects.get(is_demo=True, name='Demo - Acme Corporation')
        except Organization.DoesNotExist:
            self.stdout.write(self.style.ERROR(
                '❌ Demo organization not found. Please run: python manage.py create_demo_organization'
            ))
            return

        # Create default roles for demo organization if they don't exist
        self.stdout.write('🔐 Setting up roles and permissions...')
        roles = Role.create_default_roles(demo_org)
        self.stdout.write(self.style.SUCCESS(f'   ✅ Created/verified {len(roles)} system roles\n'))

        # Get demo personas
        alex = User.objects.filter(email='alex.chen@demo.prizmai.local').first()
        sam = User.objects.filter(email='sam.rivera@demo.prizmai.local').first()
        jordan = User.objects.filter(email='jordan.taylor@demo.prizmai.local').first()

        if not all([alex, sam, jordan]):
            self.stdout.write(self.style.ERROR(
                '❌ Demo personas not found. Please run: python manage.py create_demo_organization'
            ))
            return

        # Get demo boards
        software_board = Board.objects.filter(
            name='Software Development',
            is_official_demo_board=True,
            organization=demo_org
        ).first()

        marketing_board = Board.objects.filter(
            name='Marketing Campaign',
            is_official_demo_board=True,
            organization=demo_org
        ).first()

        bug_board = Board.objects.filter(
            name='Bug Tracking',
            is_official_demo_board=True,
            organization=demo_org
        ).first()

        if not all([software_board, marketing_board, bug_board]):
            self.stdout.write(self.style.ERROR(
                '❌ Demo boards not found. Please run: python manage.py create_demo_organization'
            ))
            return

        # Update boards to have 3 phases each
        self.stdout.write('🔧 Configuring phases for demo boards...')
        for board in [software_board, marketing_board, bug_board]:
            board.num_phases = 3
            board.save()
        self.stdout.write(self.style.SUCCESS('   ✅ All demo boards set to 3 phases\n'))

        # Reset existing demo tasks if requested
        if options['reset']:
            self.stdout.write(self.style.WARNING('🔄 Resetting demo data...'))
            
            # Delete ALL user-created boards in demo org
            # This includes:
            # 1. Boards with is_official_demo_board=False
            # 2. Boards with is_seed_demo_data=False (user-created, even if marked as official)
            # We protect only the 3 official seed boards: Software Development, Marketing Campaign, Bug Tracking
            from django.db.models import Q
            from kanban.models import Column, Comment, TaskActivity, TaskFile
            from kanban.resource_leveling_models import TaskAssignmentHistory
            from kanban.stakeholder_models import StakeholderTaskInvolvement
            
            official_board_names = ['Software Development', 'Marketing Campaign', 'Bug Tracking']
            
            # Find user-created boards to delete
            user_boards = Board.objects.filter(
                organization=demo_org
            ).exclude(
                name__in=official_board_names,
                is_official_demo_board=True
            )
            
            if user_boards.exists():
                # First delete all tasks on these boards (to handle FK constraints)
                user_board_tasks = Task.objects.filter(column__board__in=user_boards)
                task_ids = list(user_board_tasks.values_list('id', flat=True))
                
                if task_ids:
                    # Delete related records first
                    TaskActivity.objects.filter(task_id__in=task_ids).delete()
                    Comment.objects.filter(task_id__in=task_ids).delete()
                    TaskFile.objects.filter(task_id__in=task_ids).delete()
                    TaskAssignmentHistory.objects.filter(task_id__in=task_ids).delete()
                    StakeholderTaskInvolvement.objects.filter(task_id__in=task_ids).delete()
                    
                    # Clear dependencies
                    for task in Task.objects.filter(id__in=task_ids):
                        task.dependencies.clear()
                        task.dependent_tasks.clear()
                        task.related_tasks.clear()
                    
                    # Delete the tasks
                    user_board_tasks.delete()
                
                # Now delete the boards (columns will cascade)
                deleted_boards = user_boards.delete()[0]
                self.stdout.write(self.style.WARNING(f'   Deleted {deleted_boards} user-created boards'))
            
            # Delete ALL tasks on official demo boards (both user-created and demo data)
            deleted_count = Task.objects.filter(
                column__board__in=[software_board, marketing_board, bug_board]
            ).delete()[0]
            self.stdout.write(self.style.WARNING(f'   Deleted {deleted_count} existing tasks\n'))

        # Check if tasks already exist
        existing_task_count = Task.objects.filter(
            column__board__in=[software_board, marketing_board, bug_board]
        ).count()

        if existing_task_count > 0 and not options['reset']:
            self.stdout.write(self.style.WARNING(
                f'⚠️  Demo boards already have {existing_task_count} tasks.'
            ))
            self.stdout.write(self.style.WARNING(
                '   Use --reset flag to delete and recreate: python manage.py populate_demo_data --reset\n'
            ))
            return

        # Create tasks for each board (30 tasks per board)
        self.stdout.write(self.style.SUCCESS('📝 Creating demo tasks...\n'))

        software_tasks = self.create_software_tasks(software_board, alex, sam, jordan)
        self.stdout.write(self.style.SUCCESS(
            f'   ✅ Software Development: {len(software_tasks)} items created'
        ))

        marketing_tasks = self.create_marketing_tasks(marketing_board, alex, sam, jordan)
        self.stdout.write(self.style.SUCCESS(
            f'   ✅ Marketing Campaign: {len(marketing_tasks)} items created'
        ))

        bug_tasks = self.create_bug_tasks(bug_board, alex, sam, jordan)
        self.stdout.write(self.style.SUCCESS(
            f'   ✅ Bug Tracking: {len(bug_tasks)} items created'
        ))

        total_tasks = len(software_tasks) + len(marketing_tasks) + len(bug_tasks)
        self.stdout.write(self.style.SUCCESS(f'\n   📊 Total items created: {total_tasks}'))

        # Create task dependencies
        self.stdout.write(self.style.SUCCESS('\n🔗 Creating task dependencies...\n'))
        self.create_dependencies(software_tasks, marketing_tasks, bug_tasks)

        # Create and assign Lean Six Sigma labels
        self.stdout.write(self.style.SUCCESS('\n🏷️  Creating Lean Six Sigma labels...\n'))
        self.create_lean_labels(software_board, marketing_board, bug_board)
        self.assign_lean_labels(software_tasks, marketing_tasks, bug_tasks)

        # Enhance tasks with comprehensive demo data
        self.stdout.write(self.style.SUCCESS('\n📊 Enriching tasks with comprehensive demo data...\n'))
        self.enhance_tasks_with_demo_data(software_tasks, SOFTWARE_SKILLS, 'software')
        self.enhance_tasks_with_demo_data(marketing_tasks, MARKETING_SKILLS, 'marketing')
        self.enhance_tasks_with_demo_data(bug_tasks, BUG_TRACKING_SKILLS, 'bug_tracking')

        # Create related task relationships
        self.stdout.write(self.style.SUCCESS('\n🔄 Creating related task relationships...\n'))
        self.create_related_tasks(software_tasks)
        self.create_related_tasks(marketing_tasks)
        self.create_related_tasks(bug_tasks)

        # Create time tracking data for all demo users
        self.stdout.write(self.style.SUCCESS('\n⏱️  Creating time tracking data...\n'))
        all_tasks = software_tasks + marketing_tasks + bug_tasks
        self.create_time_tracking_data(all_tasks, alex, sam, jordan)

        # Create budget and ROI data
        self.stdout.write(self.style.SUCCESS('\n💰 Creating budget and ROI data...\n'))
        self.create_budget_roi_data(software_board, marketing_board, bug_board, alex)

        # Create burndown/velocity data
        self.stdout.write(self.style.SUCCESS('\n📉 Creating burndown velocity data...\n'))
        self.create_burndown_data(software_board, marketing_board, bug_board)

        # Create sprint milestones
        self.stdout.write(self.style.SUCCESS('\n🎯 Creating sprint milestones...\n'))
        self.create_sprint_milestones(software_board, marketing_board, bug_board)

        # Create team skill profiles and skill gaps
        self.stdout.write(self.style.SUCCESS('\n🎓 Creating skill profiles and skill gaps...\n'))
        self.create_skill_data(software_board, marketing_board, bug_board, all_tasks)

        # Create scope change snapshots
        self.stdout.write(self.style.SUCCESS('\n📐 Creating scope change snapshots...\n'))
        self.create_scope_snapshots(software_board, marketing_board, bug_board, alex)

        # Create retrospective data
        self.stdout.write(self.style.SUCCESS('\n🔄 Creating retrospective data...\n'))
        self.create_retrospective_data(software_board, marketing_board, bug_board, alex, sam, jordan)

        # Create AI coaching suggestions
        self.stdout.write(self.style.SUCCESS('\n🤖 Creating AI coaching suggestions...\n'))
        self.create_coaching_data(software_board, marketing_board, bug_board)

        # Create comments for all tasks
        self.stdout.write(self.style.SUCCESS('\n💬 Creating task comments...\n'))
        self.create_comments(all_tasks, alex, sam, jordan)

        # Create activity logs for all tasks
        self.stdout.write(self.style.SUCCESS('\n📋 Creating activity logs...\n'))
        self.create_activity_logs(all_tasks, alex, sam, jordan)

        # Create stakeholders and link them to tasks
        self.stdout.write(self.style.SUCCESS('\n👥 Creating stakeholders...\n'))
        self.create_stakeholders(software_board, marketing_board, bug_board, all_tasks, alex, sam, jordan)

        # Create file attachment metadata (simulated attachments)
        self.stdout.write(self.style.SUCCESS('\n📎 Creating file attachments...\n'))
        self.create_file_attachments(all_tasks, alex, sam, jordan)

        # Populate Wiki demo data (pages, categories, links)
        self.stdout.write(self.style.SUCCESS('\n📚 Creating Wiki demo data...\n'))
        from django.core.management import call_command
        try:
            call_command('populate_wiki_demo_data', '--reset')
        except Exception as e:
            self.stdout.write(self.style.WARNING(f'   ⚠️  Wiki demo data skipped: {e}'))

        # Populate Messaging demo data (chat rooms, messages, notifications)
        self.stdout.write(self.style.SUCCESS('\n💬 Creating Messaging demo data...\n'))
        try:
            call_command('populate_messaging_demo_data', '--clear')
        except Exception as e:
            self.stdout.write(self.style.WARNING(f'   ⚠️  Messaging demo data skipped: {e}'))

        # Populate Conflict demo data
        self.stdout.write(self.style.SUCCESS('\n⚠️  Creating Conflict demo data...\n'))
        try:
            call_command('populate_conflict_demo_data', '--reset')
        except Exception as e:
            self.stdout.write(self.style.WARNING(f'   ⚠️  Conflict demo data skipped: {e}'))

        # Populate AI Assistant demo data (chat sessions and messages)
        self.stdout.write(self.style.SUCCESS('\n🤖 Creating AI Assistant chat sessions...\n'))
        try:
            call_command('populate_ai_assistant_demo_data', '--reset')
        except Exception as e:
            self.stdout.write(self.style.WARNING(f'   ⚠️  AI Assistant demo data skipped: {e}'))

        self.stdout.write(self.style.SUCCESS('\n' + '='*70))
        self.stdout.write(self.style.SUCCESS('✅ DEMO DATA POPULATION COMPLETE'))
        self.stdout.write(self.style.SUCCESS('='*70 + '\n'))

    def create_software_tasks(self, board, alex, sam, jordan):
        """
        Create 30 tasks for Software Development board (3 phases)
        Uses same structure as construction demo with parallel paths and merge points
        for realistic critical path calculation.
        """
        columns = {col.name: col for col in Column.objects.filter(board=board)}
        todo = columns.get('To Do') or columns.get('Backlog') or list(columns.values())[0]
        in_progress = columns.get('In Progress') or todo
        review = columns.get('In Review') or in_progress
        done = columns.get('Done') or review
        items = []
        now = timezone.now().date()
        from datetime import datetime

        # =====================================================================
        # Phase 1: Foundation & Setup (10 tasks)
        # Dependency structure:
        # [0] Requirements ──────────────────┐
        #                                    ├──► [4] Base API ──► [7] Database Migrations
        # [1] Environment Setup ─────────────┘                            │
        #                                                                  │
        # [2] Architecture Design ───────────┐                             │
        #                                    ├──► [5] Auth System ──► [8] Auth Testing ─┐
        # [3] Security Patterns ─────────────┘            │                              │
        #                                                 │                              │
        #                                                 └──► [6] User Registration     │
        #                                                                                │
        #                                     [9] Documentation Setup ◄──────────────────┘
        # =====================================================================
        phase1_data = [
            {'title': 'Requirements Analysis & Planning', 'desc': 'Gather requirements, define scope, and create project roadmap', 'priority': 'high', 'complexity': 5, 'assignee': alex, 'progress': 100, 'column': done, 'start_offset': 0, 'duration': 5},
            {'title': 'Development Environment Setup', 'desc': 'Configure Docker, CI/CD pipelines, and development tools', 'priority': 'high', 'complexity': 6, 'assignee': sam, 'progress': 100, 'column': done, 'start_offset': 0, 'duration': 4},
            {'title': 'System Architecture Design', 'desc': 'Design microservices architecture and define API contracts', 'priority': 'high', 'complexity': 8, 'assignee': jordan, 'progress': 100, 'column': done, 'start_offset': 0, 'duration': 10},
            {'title': 'Security Architecture Patterns', 'desc': 'Define security patterns, encryption standards, and access control', 'priority': 'high', 'complexity': 7, 'assignee': sam, 'progress': 100, 'column': done, 'start_offset': 2, 'duration': 8},
            {'title': 'Base API Structure', 'desc': 'Set up REST API framework with versioning and documentation', 'priority': 'medium', 'complexity': 5, 'assignee': alex, 'progress': 100, 'column': done, 'start_offset': 5, 'duration': 6},
            {'title': 'Authentication System', 'desc': 'Build secure login with JWT tokens and session management', 'priority': 'high', 'complexity': 4, 'assignee': jordan, 'progress': 80, 'column': review, 'start_offset': 10, 'duration': 3},
            {'title': 'User Registration Flow', 'desc': 'Build signup with email verification and onboarding', 'priority': 'medium', 'complexity': 4, 'assignee': alex, 'progress': 60, 'column': in_progress, 'start_offset': 13, 'duration': 4},
            {'title': 'Database Schema & Migrations', 'desc': 'Create ERD and define core database models with migrations', 'priority': 'high', 'complexity': 6, 'assignee': sam, 'progress': 40, 'column': in_progress, 'start_offset': 11, 'duration': 7},
            {'title': 'Authentication Testing Suite', 'desc': 'Comprehensive test coverage for auth system with security tests', 'priority': 'urgent', 'complexity': 3, 'assignee': jordan, 'progress': 0, 'column': todo, 'start_offset': 13, 'duration': 10},
            {'title': 'Project Documentation Setup', 'desc': 'Set up documentation site with API reference and dev guides', 'priority': 'urgent', 'complexity': 7, 'assignee': sam, 'progress': 0, 'column': todo, 'start_offset': 23, 'duration': 5},
        ]

        for i, t in enumerate(phase1_data):
            start = now + timedelta(days=t['start_offset'])
            due_date_obj = start + timedelta(days=t['duration'])
            due_datetime = timezone.make_aware(datetime.combine(due_date_obj, datetime.min.time()))
            task = Task.objects.create(
                column=t['column'], title=t['title'], description=t['desc'],
                priority=t['priority'], complexity_score=t['complexity'],
                assigned_to=t['assignee'], created_by=alex, progress=t['progress'],
                start_date=start, due_date=due_datetime, phase='Phase 1',
                is_seed_demo_data=True,
            )
            items.append(task)

        # =====================================================================
        # Phase 2: Core Features (10 tasks)
        # =====================================================================
        phase_start = 28
        phase2_data = [
            {'title': 'Dashboard UI Development', 'desc': 'Create responsive dashboard with charts and widgets', 'priority': 'urgent', 'complexity': 8, 'assignee': sam, 'progress': 100, 'column': done, 'start_offset': phase_start, 'duration': 10},
            {'title': 'File Upload System', 'desc': 'Support multiple file types with S3 storage integration', 'priority': 'high', 'complexity': 6, 'assignee': alex, 'progress': 80, 'column': review, 'start_offset': phase_start + 10, 'duration': 8},
            {'title': 'Notification Service', 'desc': 'Real-time notifications via WebSocket and email queues', 'priority': 'high', 'complexity': 7, 'assignee': jordan, 'progress': 70, 'column': in_progress, 'start_offset': phase_start + 10, 'duration': 6},
            {'title': 'User Management API', 'desc': 'CRUD operations for users with role-based access control', 'priority': 'high', 'complexity': 7, 'assignee': sam, 'progress': 75, 'column': in_progress, 'start_offset': phase_start + 10, 'duration': 5},
            {'title': 'Search & Indexing Engine', 'desc': 'Full-text search with Elasticsearch and filters', 'priority': 'urgent', 'complexity': 7, 'assignee': alex, 'progress': 30, 'column': in_progress, 'start_offset': phase_start + 18, 'duration': 7},
            {'title': 'Real-time Collaboration', 'desc': 'WebSocket-based real-time editing and presence features', 'priority': 'high', 'complexity': 6, 'assignee': jordan, 'progress': 0, 'column': todo, 'start_offset': phase_start + 25, 'duration': 6},
            {'title': 'Data Caching Layer', 'desc': 'Redis-based caching for improved performance', 'priority': 'medium', 'complexity': 4, 'assignee': alex, 'progress': 0, 'column': todo, 'start_offset': phase_start + 31, 'duration': 5},
            {'title': 'API Rate Limiting', 'desc': 'Implement rate limiting and throttling for API endpoints', 'priority': 'high', 'complexity': 5, 'assignee': sam, 'progress': 0, 'column': todo, 'start_offset': phase_start + 25, 'duration': 5},
            {'title': 'Integration Testing Suite', 'desc': 'End-to-end integration tests for all core features', 'priority': 'medium', 'complexity': 5, 'assignee': jordan, 'progress': 0, 'column': todo, 'start_offset': phase_start + 30, 'duration': 4},
            {'title': 'Core Features Code Review', 'desc': 'Comprehensive code review and refactoring', 'priority': 'urgent', 'complexity': 3, 'assignee': alex, 'progress': 0, 'column': todo, 'start_offset': phase_start + 36, 'duration': 2},
        ]

        for i, t in enumerate(phase2_data):
            start = now + timedelta(days=t['start_offset'])
            due_date_obj = start + timedelta(days=t['duration'])
            due_datetime = timezone.make_aware(datetime.combine(due_date_obj, datetime.min.time()))
            task = Task.objects.create(
                column=t['column'], title=t['title'], description=t['desc'],
                priority=t['priority'], complexity_score=t['complexity'],
                assigned_to=t['assignee'], created_by=alex, progress=t['progress'],
                start_date=start, due_date=due_datetime, phase='Phase 2',
                is_seed_demo_data=True,
            )
            items.append(task)

        # =====================================================================
        # Phase 3: Polish & Launch (10 tasks)
        # =====================================================================
        phase_start = 66
        phase3_data = [
            {'title': 'Performance Optimization', 'desc': 'Database query optimization and caching improvements', 'priority': 'high', 'complexity': 6, 'assignee': alex, 'progress': 0, 'column': todo, 'start_offset': phase_start, 'duration': 8},
            {'title': 'Security Audit & Fixes', 'desc': 'Address findings from penetration testing', 'priority': 'medium', 'complexity': 4, 'assignee': sam, 'progress': 0, 'column': todo, 'start_offset': phase_start, 'duration': 4},
            {'title': 'UI/UX Polish', 'desc': 'Final UI polish and mobile responsive improvements', 'priority': 'high', 'complexity': 5, 'assignee': jordan, 'progress': 0, 'column': todo, 'start_offset': phase_start + 8, 'duration': 6},
            {'title': 'Load Testing & Optimization', 'desc': 'Conduct load tests and fix performance bottlenecks', 'priority': 'medium', 'complexity': 5, 'assignee': alex, 'progress': 0, 'column': todo, 'start_offset': phase_start + 14, 'duration': 5},
            {'title': 'User Onboarding Flow', 'desc': 'Interactive tutorial and onboarding experience', 'priority': 'high', 'complexity': 6, 'assignee': sam, 'progress': 0, 'column': todo, 'start_offset': phase_start + 19, 'duration': 6},
            {'title': 'Error Tracking & Monitoring', 'desc': 'Configure Sentry, APM and alerting systems', 'priority': 'medium', 'complexity': 4, 'assignee': sam, 'progress': 0, 'column': todo, 'start_offset': phase_start + 14, 'duration': 3},
            {'title': 'Accessibility Compliance', 'desc': 'WCAG 2.1 AA compliance updates and testing', 'priority': 'medium', 'complexity': 4, 'assignee': jordan, 'progress': 0, 'column': todo, 'start_offset': phase_start + 14, 'duration': 4},
            {'title': 'Final Documentation', 'desc': 'Complete user guides and API documentation', 'priority': 'low', 'complexity': 2, 'assignee': jordan, 'progress': 0, 'column': todo, 'start_offset': phase_start + 25, 'duration': 2},
            {'title': 'Deployment Automation', 'desc': 'One-click deployment pipeline to production', 'priority': 'medium', 'complexity': 3, 'assignee': alex, 'progress': 0, 'column': todo, 'start_offset': phase_start + 27, 'duration': 3},
            {'title': 'Launch & Go-Live', 'desc': 'Final checklist, DNS cutover, and production deployment', 'priority': 'urgent', 'complexity': 3, 'assignee': alex, 'progress': 0, 'column': todo, 'start_offset': phase_start + 30, 'duration': 2},
        ]

        for i, t in enumerate(phase3_data):
            start = now + timedelta(days=t['start_offset'])
            due_date_obj = start + timedelta(days=t['duration'])
            due_datetime = timezone.make_aware(datetime.combine(due_date_obj, datetime.min.time()))
            task = Task.objects.create(
                column=t['column'], title=t['title'], description=t['desc'],
                priority=t['priority'], complexity_score=t['complexity'],
                assigned_to=t['assignee'], created_by=alex, progress=t['progress'],
                start_date=start, due_date=due_datetime, phase='Phase 3',
                is_seed_demo_data=True,
            )
            items.append(task)

        return items

    def create_marketing_tasks(self, board, alex, sam, jordan):
        """
        Create 30 tasks for Marketing Campaign board (3 phases)
        Uses same structure as construction demo with parallel paths and merge points.
        """
        columns = {col.name: col for col in Column.objects.filter(board=board)}
        todo = columns.get('To Do') or columns.get('Backlog') or list(columns.values())[0]
        in_progress = columns.get('In Progress') or todo
        review = columns.get('In Review') or in_progress
        done = columns.get('Done') or review
        items = []
        now = timezone.now().date()
        from datetime import datetime

        # =====================================================================
        # Phase 1: Planning & Strategy (10 tasks) - Same dependency pattern
        # =====================================================================
        phase1_data = [
            {'title': 'Market Research & Analysis', 'desc': 'Analyze target audience, competitors, and market trends', 'priority': 'high', 'complexity': 5, 'assignee': alex, 'progress': 100, 'column': done, 'start_offset': 0, 'duration': 5},
            {'title': 'Customer Survey Design', 'desc': 'Design and distribute customer feedback surveys', 'priority': 'high', 'complexity': 6, 'assignee': sam, 'progress': 100, 'column': done, 'start_offset': 0, 'duration': 4},
            {'title': 'Brand Positioning Strategy', 'desc': 'Define brand positioning and unique value proposition', 'priority': 'high', 'complexity': 8, 'assignee': jordan, 'progress': 100, 'column': done, 'start_offset': 0, 'duration': 10},
            {'title': 'Competitor Campaign Study', 'desc': 'Analyze competitor marketing campaigns and strategies', 'priority': 'high', 'complexity': 7, 'assignee': sam, 'progress': 100, 'column': done, 'start_offset': 2, 'duration': 8},
            {'title': 'Target Audience Definition', 'desc': 'Create detailed buyer personas and customer journey maps', 'priority': 'medium', 'complexity': 5, 'assignee': alex, 'progress': 100, 'column': done, 'start_offset': 5, 'duration': 6},
            {'title': 'Campaign Objectives & KPIs', 'desc': 'Set SMART goals and key performance indicators', 'priority': 'high', 'complexity': 4, 'assignee': jordan, 'progress': 80, 'column': review, 'start_offset': 10, 'duration': 3},
            {'title': 'Channel Strategy Planning', 'desc': 'Select primary and secondary marketing channels', 'priority': 'medium', 'complexity': 4, 'assignee': alex, 'progress': 60, 'column': in_progress, 'start_offset': 13, 'duration': 4},
            {'title': 'Budget Allocation Plan', 'desc': 'Distribute budget across channels and activities', 'priority': 'high', 'complexity': 6, 'assignee': sam, 'progress': 40, 'column': in_progress, 'start_offset': 11, 'duration': 7},
            {'title': 'Campaign Brief Document', 'desc': 'Document comprehensive campaign overview for team', 'priority': 'urgent', 'complexity': 3, 'assignee': jordan, 'progress': 0, 'column': todo, 'start_offset': 13, 'duration': 10},
            {'title': 'Strategy Approval Meeting', 'desc': 'Present strategy to stakeholders for final approval', 'priority': 'urgent', 'complexity': 7, 'assignee': sam, 'progress': 0, 'column': todo, 'start_offset': 23, 'duration': 5},
        ]

        for i, t in enumerate(phase1_data):
            start = now + timedelta(days=t['start_offset'])
            due_date_obj = start + timedelta(days=t['duration'])
            due_datetime = timezone.make_aware(datetime.combine(due_date_obj, datetime.min.time()))
            task = Task.objects.create(
                column=t['column'], title=t['title'], description=t['desc'],
                priority=t['priority'], complexity_score=t['complexity'],
                assigned_to=t['assignee'], created_by=alex, progress=t['progress'],
                start_date=start, due_date=due_datetime, phase='Phase 1',
                is_seed_demo_data=True,
            )
            items.append(task)

        # =====================================================================
        # Phase 2: Content Creation (10 tasks)
        # =====================================================================
        phase_start = 28
        phase2_data = [
            {'title': 'Content Strategy Framework', 'desc': 'Define content themes, formats, and editorial calendar', 'priority': 'urgent', 'complexity': 8, 'assignee': sam, 'progress': 100, 'column': done, 'start_offset': phase_start, 'duration': 10},
            {'title': 'Blog Content Production', 'desc': 'Create 5 SEO-optimized blog articles and posts', 'priority': 'high', 'complexity': 6, 'assignee': alex, 'progress': 80, 'column': review, 'start_offset': phase_start + 10, 'duration': 8},
            {'title': 'Social Media Assets', 'desc': 'Design visual content for all social platforms', 'priority': 'high', 'complexity': 7, 'assignee': jordan, 'progress': 70, 'column': in_progress, 'start_offset': phase_start + 10, 'duration': 6},
            {'title': 'Video Content Production', 'desc': 'Script, shoot, and edit promotional videos', 'priority': 'high', 'complexity': 7, 'assignee': sam, 'progress': 75, 'column': in_progress, 'start_offset': phase_start + 10, 'duration': 5},
            {'title': 'Email Campaign Design', 'desc': 'Create automated email nurture sequences', 'priority': 'urgent', 'complexity': 7, 'assignee': alex, 'progress': 30, 'column': in_progress, 'start_offset': phase_start + 18, 'duration': 7},
            {'title': 'Landing Page Development', 'desc': 'Build conversion-optimized landing pages', 'priority': 'high', 'complexity': 6, 'assignee': jordan, 'progress': 0, 'column': todo, 'start_offset': phase_start + 25, 'duration': 6},
            {'title': 'Ad Creative Production', 'desc': 'Design PPC and social ad creatives with copy', 'priority': 'medium', 'complexity': 4, 'assignee': alex, 'progress': 0, 'column': todo, 'start_offset': phase_start + 31, 'duration': 5},
            {'title': 'Infographic Design', 'desc': 'Create data-driven infographics for sharing', 'priority': 'high', 'complexity': 5, 'assignee': sam, 'progress': 0, 'column': todo, 'start_offset': phase_start + 25, 'duration': 5},
            {'title': 'Case Study Development', 'desc': 'Document customer success stories', 'priority': 'medium', 'complexity': 5, 'assignee': jordan, 'progress': 0, 'column': todo, 'start_offset': phase_start + 30, 'duration': 4},
            {'title': 'Content Review & Approval', 'desc': 'Final review and stakeholder approval of all content', 'priority': 'urgent', 'complexity': 3, 'assignee': alex, 'progress': 0, 'column': todo, 'start_offset': phase_start + 36, 'duration': 2},
        ]

        for i, t in enumerate(phase2_data):
            start = now + timedelta(days=t['start_offset'])
            due_date_obj = start + timedelta(days=t['duration'])
            due_datetime = timezone.make_aware(datetime.combine(due_date_obj, datetime.min.time()))
            task = Task.objects.create(
                column=t['column'], title=t['title'], description=t['desc'],
                priority=t['priority'], complexity_score=t['complexity'],
                assigned_to=t['assignee'], created_by=alex, progress=t['progress'],
                start_date=start, due_date=due_datetime, phase='Phase 2',
                is_seed_demo_data=True,
            )
            items.append(task)

        # =====================================================================
        # Phase 3: Launch & Optimization (10 tasks)
        # =====================================================================
        phase_start = 66
        phase3_data = [
            {'title': 'Campaign Launch Preparation', 'desc': 'Final checklist and platform configurations', 'priority': 'high', 'complexity': 6, 'assignee': alex, 'progress': 0, 'column': todo, 'start_offset': phase_start, 'duration': 8},
            {'title': 'Analytics Setup & Testing', 'desc': 'Configure GA4, UTM tracking, and conversion pixels', 'priority': 'medium', 'complexity': 4, 'assignee': sam, 'progress': 0, 'column': todo, 'start_offset': phase_start, 'duration': 4},
            {'title': 'Social Campaign Activation', 'desc': 'Launch campaigns across all social platforms', 'priority': 'high', 'complexity': 5, 'assignee': jordan, 'progress': 0, 'column': todo, 'start_offset': phase_start + 8, 'duration': 6},
            {'title': 'Paid Media Activation', 'desc': 'Launch PPC and paid social campaigns', 'priority': 'medium', 'complexity': 5, 'assignee': alex, 'progress': 0, 'column': todo, 'start_offset': phase_start + 14, 'duration': 5},
            {'title': 'Email Sequence Launch', 'desc': 'Activate automated email nurture campaigns', 'priority': 'high', 'complexity': 6, 'assignee': sam, 'progress': 0, 'column': todo, 'start_offset': phase_start + 19, 'duration': 6},
            {'title': 'Performance Monitoring', 'desc': 'Daily monitoring of KPIs and campaign health', 'priority': 'medium', 'complexity': 4, 'assignee': sam, 'progress': 0, 'column': todo, 'start_offset': phase_start + 14, 'duration': 3},
            {'title': 'A/B Testing & Optimization', 'desc': 'Run conversion optimization tests and iterate', 'priority': 'medium', 'complexity': 4, 'assignee': jordan, 'progress': 0, 'column': todo, 'start_offset': phase_start + 14, 'duration': 4},
            {'title': 'Budget Reallocation', 'desc': 'Optimize spend based on channel performance', 'priority': 'low', 'complexity': 2, 'assignee': jordan, 'progress': 0, 'column': todo, 'start_offset': phase_start + 25, 'duration': 2},
            {'title': 'Performance Reporting', 'desc': 'Compile comprehensive campaign performance report', 'priority': 'medium', 'complexity': 3, 'assignee': alex, 'progress': 0, 'column': todo, 'start_offset': phase_start + 27, 'duration': 3},
            {'title': 'Campaign Retrospective', 'desc': 'Document learnings and recommendations for future', 'priority': 'urgent', 'complexity': 3, 'assignee': alex, 'progress': 0, 'column': todo, 'start_offset': phase_start + 30, 'duration': 2},
        ]

        for i, t in enumerate(phase3_data):
            start = now + timedelta(days=t['start_offset'])
            due_date_obj = start + timedelta(days=t['duration'])
            due_datetime = timezone.make_aware(datetime.combine(due_date_obj, datetime.min.time()))
            task = Task.objects.create(
                column=t['column'], title=t['title'], description=t['desc'],
                priority=t['priority'], complexity_score=t['complexity'],
                assigned_to=t['assignee'], created_by=alex, progress=t['progress'],
                start_date=start, due_date=due_datetime, phase='Phase 3',
                is_seed_demo_data=True,
            )
            items.append(task)

        return items

    def create_bug_tasks(self, board, alex, sam, jordan):
        """
        Create 30 tasks for Bug Tracking board (3 phases)
        Uses same structure as construction demo with parallel paths and merge points.
        """
        columns = {col.name: col for col in Column.objects.filter(board=board)}
        todo = columns.get('To Do') or columns.get('Backlog') or list(columns.values())[0]
        in_progress = columns.get('In Progress') or todo
        review = columns.get('In Review') or in_progress
        done = columns.get('Done') or review
        items = []
        now = timezone.now().date()
        from datetime import datetime

        # =====================================================================
        # Phase 1: Critical & Security Bugs (10 tasks) - Same dependency pattern
        # =====================================================================
        phase1_data = [
            {'title': 'Security Audit & Assessment', 'desc': 'Comprehensive security assessment and vulnerability scanning', 'priority': 'high', 'complexity': 5, 'assignee': alex, 'progress': 100, 'column': done, 'start_offset': 0, 'duration': 5},
            {'title': 'SQL Injection Vulnerability', 'desc': 'Patch user input sanitization in search module', 'priority': 'high', 'complexity': 6, 'assignee': sam, 'progress': 100, 'column': done, 'start_offset': 0, 'duration': 4},
            {'title': 'Authentication Bypass Fix', 'desc': 'Close security hole in session handling', 'priority': 'high', 'complexity': 8, 'assignee': jordan, 'progress': 100, 'column': done, 'start_offset': 0, 'duration': 10},
            {'title': 'XSS Vulnerability Patches', 'desc': 'Sanitize all HTML output in user content areas', 'priority': 'high', 'complexity': 7, 'assignee': sam, 'progress': 100, 'column': done, 'start_offset': 2, 'duration': 8},
            {'title': 'Password Security Upgrade', 'desc': 'Upgrade to bcrypt with proper cost factor and salting', 'priority': 'medium', 'complexity': 5, 'assignee': alex, 'progress': 100, 'column': done, 'start_offset': 5, 'duration': 6},
            {'title': 'CSRF Token Implementation', 'desc': 'Implement proper CSRF protection across all forms', 'priority': 'high', 'complexity': 4, 'assignee': jordan, 'progress': 80, 'column': review, 'start_offset': 10, 'duration': 3},
            {'title': 'Session Security Hardening', 'desc': 'Fix session fixation and regenerate IDs on login', 'priority': 'medium', 'complexity': 4, 'assignee': alex, 'progress': 60, 'column': in_progress, 'start_offset': 13, 'duration': 4},
            {'title': 'Database Connection Leak Fix', 'desc': 'Properly close DB connections in all code paths', 'priority': 'high', 'complexity': 6, 'assignee': sam, 'progress': 40, 'column': in_progress, 'start_offset': 11, 'duration': 7},
            {'title': 'File Upload Security', 'desc': 'Validate file types, scan for malware, and sandbox', 'priority': 'urgent', 'complexity': 3, 'assignee': jordan, 'progress': 0, 'column': todo, 'start_offset': 13, 'duration': 10},
            {'title': 'Security Patch Verification', 'desc': 'Verify all security patches and penetration testing', 'priority': 'urgent', 'complexity': 7, 'assignee': sam, 'progress': 0, 'column': todo, 'start_offset': 23, 'duration': 5},
        ]

        for i, t in enumerate(phase1_data):
            start = now + timedelta(days=t['start_offset'])
            due_date_obj = start + timedelta(days=t['duration'])
            due_datetime = timezone.make_aware(datetime.combine(due_date_obj, datetime.min.time()))
            task = Task.objects.create(
                column=t['column'], title=t['title'], description=t['desc'],
                priority=t['priority'], complexity_score=t['complexity'],
                assigned_to=t['assignee'], created_by=sam, progress=t['progress'],
                start_date=start, due_date=due_datetime, phase='Phase 1',
                is_seed_demo_data=True,
            )
            items.append(task)

        # =====================================================================
        # Phase 2: High Priority Performance & Stability (10 tasks)
        # =====================================================================
        phase_start = 28
        phase2_data = [
            {'title': 'Memory Leak Investigation', 'desc': 'Profile and fix memory leaks in background workers', 'priority': 'urgent', 'complexity': 8, 'assignee': sam, 'progress': 100, 'column': done, 'start_offset': phase_start, 'duration': 10},
            {'title': 'Dashboard Load Optimization', 'desc': 'Optimize slow-loading dashboard (10+ seconds)', 'priority': 'high', 'complexity': 6, 'assignee': alex, 'progress': 80, 'column': review, 'start_offset': phase_start + 10, 'duration': 8},
            {'title': 'Email Delivery Fix', 'desc': 'Fix emails not sending to certain domains', 'priority': 'high', 'complexity': 7, 'assignee': jordan, 'progress': 70, 'column': in_progress, 'start_offset': phase_start + 10, 'duration': 6},
            {'title': 'Image Processing Crash', 'desc': 'Fix app crash on large image uploads', 'priority': 'high', 'complexity': 7, 'assignee': sam, 'progress': 75, 'column': in_progress, 'start_offset': phase_start + 10, 'duration': 5},
            {'title': 'Timezone Handling Bug', 'desc': 'Fix incorrect date display for non-UTC users', 'priority': 'urgent', 'complexity': 7, 'assignee': alex, 'progress': 30, 'column': in_progress, 'start_offset': phase_start + 18, 'duration': 7},
            {'title': 'Search Results Pagination', 'desc': 'Fix wrong results on page 2+ of search', 'priority': 'high', 'complexity': 6, 'assignee': jordan, 'progress': 0, 'column': todo, 'start_offset': phase_start + 25, 'duration': 6},
            {'title': 'Notification Duplicates', 'desc': 'Fix users receiving duplicate notifications', 'priority': 'medium', 'complexity': 4, 'assignee': alex, 'progress': 0, 'column': todo, 'start_offset': phase_start + 31, 'duration': 5},
            {'title': 'Export Timeout Issue', 'desc': 'Fix large exports timing out before completion', 'priority': 'high', 'complexity': 5, 'assignee': sam, 'progress': 0, 'column': todo, 'start_offset': phase_start + 25, 'duration': 5},
            {'title': 'Race Condition in Payments', 'desc': 'Add proper locking for payment processing', 'priority': 'medium', 'complexity': 5, 'assignee': jordan, 'progress': 0, 'column': todo, 'start_offset': phase_start + 30, 'duration': 4},
            {'title': 'Performance Bug Verification', 'desc': 'Verify all performance fixes with load testing', 'priority': 'urgent', 'complexity': 3, 'assignee': alex, 'progress': 0, 'column': todo, 'start_offset': phase_start + 36, 'duration': 2},
        ]

        for i, t in enumerate(phase2_data):
            start = now + timedelta(days=t['start_offset'])
            due_date_obj = start + timedelta(days=t['duration'])
            due_datetime = timezone.make_aware(datetime.combine(due_date_obj, datetime.min.time()))
            task = Task.objects.create(
                column=t['column'], title=t['title'], description=t['desc'],
                priority=t['priority'], complexity_score=t['complexity'],
                assigned_to=t['assignee'], created_by=sam, progress=t['progress'],
                start_date=start, due_date=due_datetime, phase='Phase 2',
                is_seed_demo_data=True,
            )
            items.append(task)

        # =====================================================================
        # Phase 3: UI/UX & Polish Bugs (10 tasks)
        # =====================================================================
        phase_start = 66
        phase3_data = [
            {'title': 'Form Validation Messages', 'desc': 'Fix error messages not displaying correctly', 'priority': 'high', 'complexity': 6, 'assignee': alex, 'progress': 0, 'column': todo, 'start_offset': phase_start, 'duration': 8},
            {'title': 'Print Stylesheet Fix', 'desc': 'Fix reports not printing correctly', 'priority': 'medium', 'complexity': 4, 'assignee': sam, 'progress': 0, 'column': todo, 'start_offset': phase_start, 'duration': 4},
            {'title': 'Keyboard Navigation', 'desc': 'Fix incorrect tab order on forms', 'priority': 'high', 'complexity': 5, 'assignee': jordan, 'progress': 0, 'column': todo, 'start_offset': phase_start + 8, 'duration': 6},
            {'title': 'Tooltip Positioning', 'desc': 'Fix tooltips clipping off screen edge', 'priority': 'medium', 'complexity': 5, 'assignee': alex, 'progress': 0, 'column': todo, 'start_offset': phase_start + 14, 'duration': 5},
            {'title': 'Date Picker Locale', 'desc': 'Fix date format for non-US users', 'priority': 'high', 'complexity': 6, 'assignee': sam, 'progress': 0, 'column': todo, 'start_offset': phase_start + 19, 'duration': 6},
            {'title': 'Safari Drag & Drop', 'desc': 'Fix DnD not working on Safari browser', 'priority': 'medium', 'complexity': 4, 'assignee': sam, 'progress': 0, 'column': todo, 'start_offset': phase_start + 14, 'duration': 3},
            {'title': 'Chart Rendering Flicker', 'desc': 'Fix charts flickering on data update', 'priority': 'medium', 'complexity': 4, 'assignee': jordan, 'progress': 0, 'column': todo, 'start_offset': phase_start + 14, 'duration': 4},
            {'title': 'Modal Close Behavior', 'desc': 'Fix Escape key not closing modals', 'priority': 'low', 'complexity': 2, 'assignee': jordan, 'progress': 0, 'column': todo, 'start_offset': phase_start + 25, 'duration': 2},
            {'title': 'Mobile Menu Fix', 'desc': 'Fix menu not collapsing properly on mobile', 'priority': 'medium', 'complexity': 3, 'assignee': alex, 'progress': 0, 'column': todo, 'start_offset': phase_start + 27, 'duration': 3},
            {'title': 'Final Bug Verification', 'desc': 'Final QA pass and bug verification', 'priority': 'urgent', 'complexity': 3, 'assignee': alex, 'progress': 0, 'column': todo, 'start_offset': phase_start + 30, 'duration': 2},
        ]

        for i, t in enumerate(phase3_data):
            start = now + timedelta(days=t['start_offset'])
            due_date_obj = start + timedelta(days=t['duration'])
            due_datetime = timezone.make_aware(datetime.combine(due_date_obj, datetime.min.time()))
            task = Task.objects.create(
                column=t['column'], title=t['title'], description=t['desc'],
                priority=t['priority'], complexity_score=t['complexity'],
                assigned_to=t['assignee'], created_by=sam, progress=t['progress'],
                start_date=start, due_date=due_datetime, phase='Phase 3',
                is_seed_demo_data=True,
            )
            items.append(task)

        return items

    def create_dependencies(self, software_tasks, marketing_tasks, bug_tasks):
        """
        Create realistic task dependencies with parallel paths and merge points.
        Uses the same pattern as the construction demo for proper critical path visualization.
        
        Dependency structure per phase (same for all boards):
        [0] Start Task ──────────────────┐
                                         ├──► [4] Merge Point 1 ──► [7] Work Item
        [1] Parallel Task 1 ─────────────┘                               │
                                                                         │
        [2] Parallel Task 2 ─────────────┐                               │
                                         ├──► [5] Gate ──► [8] Work Item ─┐
        [3] Parallel Task 3 ─────────────┘        │                       │
                                                  │                       │
                                                  └──► [6] Side Task     │
                                                                         │
                                              [9] Final Task ◄───────────┘
                                                (depends on [7] AND [8])
        """
        def create_phase_dependencies(tasks, phase_offset):
            """Create dependencies for a single phase (10 tasks)"""
            if len(tasks) < phase_offset + 10:
                return
            
            base = phase_offset
            # Task 4 depends on Tasks 0 and 1
            tasks[base + 4].dependencies.add(tasks[base + 0])
            tasks[base + 4].dependencies.add(tasks[base + 1])
            
            # Task 5 depends on Tasks 2 and 3
            tasks[base + 5].dependencies.add(tasks[base + 2])
            tasks[base + 5].dependencies.add(tasks[base + 3])
            
            # Task 6 depends on Task 5
            tasks[base + 6].dependencies.add(tasks[base + 5])
            
            # Task 7 depends on Task 4
            tasks[base + 7].dependencies.add(tasks[base + 4])
            
            # Task 8 depends on Task 5
            tasks[base + 8].dependencies.add(tasks[base + 5])
            
            # Task 9 depends on Tasks 7 and 8 (merge point)
            tasks[base + 9].dependencies.add(tasks[base + 7])
            tasks[base + 9].dependencies.add(tasks[base + 8])

        # Software Development
        if len(software_tasks) >= 30:
            create_phase_dependencies(software_tasks, 0)   # Phase 1
            create_phase_dependencies(software_tasks, 10)  # Phase 2
            create_phase_dependencies(software_tasks, 20)  # Phase 3
        self.stdout.write('   ✅ Software Development dependencies created (parallel paths with merge points)')

        # Marketing Campaign
        if len(marketing_tasks) >= 30:
            create_phase_dependencies(marketing_tasks, 0)   # Phase 1
            create_phase_dependencies(marketing_tasks, 10)  # Phase 2
            create_phase_dependencies(marketing_tasks, 20)  # Phase 3
        self.stdout.write('   ✅ Marketing Campaign dependencies created (parallel paths with merge points)')

        # Bug Tracking
        if len(bug_tasks) >= 30:
            create_phase_dependencies(bug_tasks, 0)   # Phase 1
            create_phase_dependencies(bug_tasks, 10)  # Phase 2
            create_phase_dependencies(bug_tasks, 20)  # Phase 3
        self.stdout.write('   ✅ Bug Tracking dependencies created (parallel paths with merge points)')

    def create_lean_labels(self, software_board, marketing_board, bug_board):
        """Create Lean Six Sigma labels for all boards"""
        # Main Lean Six Sigma category labels (for analytics chart)
        main_lean_labels = [
            {'name': 'Value-Added', 'color': '#28a745'},
            {'name': 'Necessary NVA', 'color': '#ffc107'},
            {'name': 'Waste/Eliminate', 'color': '#dc3545'},
        ]
        
        # Additional Lean Six Sigma methodology labels
        lean_labels = [
            {'name': 'Muda', 'color': '#dc3545'},
            {'name': 'Mura', 'color': '#fd7e14'},
            {'name': 'Muri', 'color': '#ffc107'},
            {'name': 'Kaizen', 'color': '#28a745'},
            {'name': '5S', 'color': '#17a2b8'},
            {'name': 'Poka-yoke', 'color': '#6f42c1'},
        ]

        for board in [software_board, marketing_board, bug_board]:
            # Create main category labels first (essential for analytics)
            for label_data in main_lean_labels:
                TaskLabel.objects.get_or_create(
                    board=board,
                    name=label_data['name'],
                    defaults={
                        'color': label_data['color'],
                        'category': 'lean',
                    }
                )
            
            # Create additional methodology labels
            for label_data in lean_labels:
                TaskLabel.objects.get_or_create(
                    board=board,
                    name=label_data['name'],
                    defaults={
                        'color': label_data['color'],
                        'category': 'lean',
                    }
                )

        self.stdout.write('   ✅ Lean Six Sigma labels created for all boards (including analytics categories)')

    def assign_lean_labels(self, software_tasks, marketing_tasks, bug_tasks):
        """Assign Lean Six Sigma labels to appropriate tasks"""
        all_tasks = software_tasks + marketing_tasks + bug_tasks

        for task in all_tasks:
            board = task.column.board
            labels = list(TaskLabel.objects.filter(board=board, category='lean'))

            if not labels:
                continue

            # Get the three main category labels
            value_added = next((l for l in labels if l.name == 'Value-Added'), None)
            necessary_nva = next((l for l in labels if l.name == 'Necessary NVA'), None)
            waste = next((l for l in labels if l.name == 'Waste/Eliminate'), None)

            # IMPORTANT: Assign ONE of the three main categories to EVERY task
            # This ensures the analytics chart always has data
            rand = random.random()
            if rand < 0.5:  # 50% Value-Added
                if value_added:
                    task.labels.add(value_added)
            elif rand < 0.8:  # 30% Necessary NVA
                if necessary_nva:
                    task.labels.add(necessary_nva)
            else:  # 20% Waste/Eliminate
                if waste:
                    task.labels.add(waste)

            # Assign additional methodology labels based on task characteristics
            if task.complexity_score and task.complexity_score >= 7:
                kaizen_label = next((l for l in labels if l.name == 'Kaizen'), None)
                if kaizen_label:
                    task.labels.add(kaizen_label)

            if task.priority in ['urgent', 'high'] and random.random() < 0.3:
                muri_label = next((l for l in labels if l.name == 'Muri'), None)
                if muri_label:
                    task.labels.add(muri_label)

            # Random chance for other methodology labels
            if random.random() < 0.15:
                methodology_labels = [l for l in labels if l.name in ['Muda', 'Mura', '5S', 'Poka-yoke']]
                if methodology_labels:
                    random_label = random.choice(methodology_labels)
                    task.labels.add(random_label)

        self.stdout.write('   ✅ Lean Six Sigma labels assigned to all tasks (with analytics categories)')

    def enhance_tasks_with_demo_data(self, tasks, skill_pool, board_type):
        """Add comprehensive demo data to tasks including risk, skills, collaboration, and AI analysis"""
        now = timezone.now()
        
        # LSS classification choices aligned with model
        lss_choices = ['value_added', 'necessary_nva', 'waste']
        lss_display = {
            'value_added': 'Value-Added',
            'necessary_nva': 'Necessary NVA',
            'waste': 'Waste/Eliminate'
        }
        
        for task in tasks:
            complexity = task.complexity_score or random.randint(3, 8)
            priority = task.priority or 'medium'
            progress = task.progress or 0

            # Add skills required
            skills = self.get_random_skills(skill_pool, 1, 3)
            task.required_skills = skills

            # Calculate and add risk data
            risk_data = self.calculate_risk_data(complexity, priority, progress)
            task.risk_likelihood = risk_data['likelihood']
            task.risk_impact = risk_data['impact']
            task.risk_score = risk_data['score']
            task.risk_level = risk_data['level']
            task.risk_indicators = risk_data['indicators']
            task.mitigation_suggestions = risk_data['strategies']  # Fixed: was risk_mitigation
            
            # Add comprehensive risk analysis JSON
            task.risk_analysis = {
                'overall_risk': risk_data['level'],
                'factors': [
                    {'name': 'Complexity', 'score': complexity, 'weight': 0.3},
                    {'name': 'Priority Pressure', 'score': 3 if priority in ['urgent', 'high'] else 1, 'weight': 0.25},
                    {'name': 'Progress Status', 'score': max(1, 10 - progress // 10), 'weight': 0.25},
                    {'name': 'Resource Availability', 'score': random.randint(2, 8), 'weight': 0.2},
                ],
                'reasoning': f"Task has {'high' if complexity >= 7 else 'moderate' if complexity >= 4 else 'low'} complexity with {priority} priority. "
                            f"Current progress at {progress}% {'reduces' if progress >= 50 else 'maintains'} overall risk.",
                'last_updated': now.isoformat(),
            }
            task.last_risk_assessment = now - timedelta(hours=random.randint(1, 72))
            
            # AI Risk Score (0-100 scale)
            task.ai_risk_score = min(100, max(0, risk_data['score'] * 10 + random.randint(-10, 10)))
            task.ai_recommendations = f"Based on analysis: {'; '.join(risk_data['strategies'][:2])}"
            task.last_ai_analysis = now - timedelta(hours=random.randint(1, 48))

            # Add workload impact
            task.workload_impact = self.get_workload_impact(complexity, priority)

            # Add skill match score if assigned
            task.skill_match_score = self.get_skill_match_score(
                task.assigned_to is not None,
                complexity
            )

            # Set collaboration requirement (Fixed: was requires_collaboration)
            task.collaboration_required = self.should_require_collaboration(complexity, priority)
            
            # Add suggested team members for collaborative tasks
            if task.collaboration_required:
                task.suggested_team_members = [
                    {'user_id': random.randint(1, 3), 'reason': 'Complementary skills', 'confidence': round(random.uniform(0.7, 0.95), 2)},
                    {'user_id': random.randint(1, 3), 'reason': 'Domain expertise', 'confidence': round(random.uniform(0.6, 0.85), 2)},
                ]
            
            # Add optimal assignee suggestions
            task.optimal_assignee_suggestions = [
                {
                    'user_id': task.assigned_to.id if task.assigned_to else random.randint(1, 3),
                    'match_score': task.skill_match_score or random.randint(70, 95),
                    'reasoning': 'Best skill match for required competencies',
                    'workload_status': 'available' if random.random() > 0.3 else 'busy'
                }
            ]
            
            # Add resource conflicts for some tasks
            if random.random() < 0.2:  # 20% of tasks have conflicts
                task.resource_conflicts = [
                    {
                        'type': random.choice(['schedule_overlap', 'skill_mismatch', 'overallocation']),
                        'severity': random.choice(['low', 'medium', 'high']),
                        'description': 'Potential conflict with other assigned tasks',
                        'suggested_resolution': 'Review task assignments and priorities'
                    }
                ]
            
            # Lean Six Sigma Classification
            # Distribute realistically: 50% value-added, 30% necessary NVA, 20% waste
            rand = random.random()
            if rand < 0.5:
                task.lss_classification = 'value_added'
            elif rand < 0.8:
                task.lss_classification = 'necessary_nva'
            else:
                task.lss_classification = 'waste'
            
            task.lss_classification_confidence = round(random.uniform(0.70, 0.95), 2)
            task.lss_classification_reasoning = {
                'classification': task.lss_classification,
                'display_name': lss_display[task.lss_classification],
                'confidence': task.lss_classification_confidence,
                'factors': [
                    'Task directly contributes to customer deliverables' if task.lss_classification == 'value_added' else
                    'Required for compliance/process but no direct customer value' if task.lss_classification == 'necessary_nva' else
                    'Can be eliminated or automated for efficiency gains'
                ],
                'ai_reasoning': f"Based on task description and context, classified as {lss_display[task.lss_classification]} with {task.lss_classification_confidence:.0%} confidence.",
                'suggested_actions': [
                    'Continue with planned execution' if task.lss_classification == 'value_added' else
                    'Look for automation opportunities' if task.lss_classification == 'necessary_nva' else
                    'Consider elimination or significant simplification'
                ]
            }
            
            # Prediction fields for tasks with progress
            if progress > 0 and task.start_date:
                # Calculate predicted completion based on progress and complexity
                days_elapsed = (now.date() - task.start_date).days if task.start_date else 0
                if progress > 0 and days_elapsed > 0:
                    estimated_total_days = int((days_elapsed / progress) * 100)
                    remaining_days = max(1, estimated_total_days - days_elapsed)
                    task.predicted_completion_date = now + timedelta(days=remaining_days)
                    task.prediction_confidence = round(random.uniform(0.65, 0.92), 2)
                    task.prediction_metadata = {
                        'based_on_tasks': random.randint(10, 50),
                        'confidence_interval': [remaining_days - 2, remaining_days + 4],
                        'factors': ['historical_velocity', 'complexity_score', 'assignee_performance'],
                        'model_version': '2.1',
                        'calculation_date': now.isoformat()
                    }
                    task.last_prediction_update = now - timedelta(hours=random.randint(1, 24))
            
            # Dependency suggestions
            if random.random() < 0.3:  # 30% of tasks get dependency suggestions
                task.suggested_dependencies = [
                    {
                        'task_id': random.randint(1, 90),
                        'confidence': round(random.uniform(0.6, 0.9), 2),
                        'reason': 'Similar title/description suggests logical dependency'
                    }
                ]
                task.last_dependency_analysis = now - timedelta(hours=random.randint(1, 48))

            task.save()

        self.stdout.write(f'   ✅ Enhanced {len(tasks)} {board_type} tasks with comprehensive demo data')

    def create_related_tasks(self, tasks):
        """Create related task relationships between similar tasks"""
        if len(tasks) < 5:
            return

        # Group tasks by phase
        phase_groups = {}
        for task in tasks:
            phase = task.phase or 'No Phase'
            if phase not in phase_groups:
                phase_groups[phase] = []
            phase_groups[phase].append(task)

        # Create relationships within phases
        for phase, phase_tasks in phase_groups.items():
            if len(phase_tasks) >= 3:
                for i in range(min(5, len(phase_tasks) - 1)):
                    task = phase_tasks[i]
                    related = random.choice([t for t in phase_tasks if t != task])
                    task.related_tasks.add(related)

    def create_time_tracking_data(self, tasks, alex, sam, jordan):
        """Create time entries for tasks"""
        users = [alex, sam, jordan]
        now = timezone.now().date()
        entries_created = 0

        for task in tasks:
            if task.progress > 0:
                # Create 1-3 time entries for tasks in progress or done
                num_entries = random.randint(1, 3)
                for i in range(num_entries):
                    user = task.assigned_to or random.choice(users)
                    hours = Decimal(str(random.uniform(0.5, 4))).quantize(Decimal('0.01'))

                    entry_date = now - timedelta(days=random.randint(1, 14))

                    TimeEntry.objects.create(
                        task=task,
                        user=user,
                        hours_spent=hours,
                        description=f"Worked on {task.title[:30]}",
                        work_date=entry_date,
                    )
                    entries_created += 1

        self.stdout.write(f'   ✅ Created {entries_created} time entries')

    def create_budget_roi_data(self, software_board, marketing_board, bug_board, admin_user):
        """Create budget and ROI data for all demo boards"""
        now = timezone.now().date()
        budget_configs = [
            {'board': software_board, 'budget': Decimal('75000.00'), 'hours': Decimal('1200.0'), 'name': 'Software Development'},
            {'board': marketing_board, 'budget': Decimal('35000.00'), 'hours': Decimal('600.0'), 'name': 'Marketing Campaign'},
            {'board': bug_board, 'budget': Decimal('25000.00'), 'hours': Decimal('500.0'), 'name': 'Bug Tracking'},
        ]

        for config in budget_configs:
            board = config['board']

            # Create or get budget
            budget, created = ProjectBudget.objects.get_or_create(
                board=board,
                defaults={
                    'allocated_budget': config['budget'],
                    'currency': 'USD',
                    'allocated_hours': config['hours'],
                    'warning_threshold': 80,
                    'critical_threshold': 95,
                    'ai_optimization_enabled': True,
                    'created_by': admin_user,
                }
            )

            if created:
                self.stdout.write(f'   ✅ Created budget for {config["name"]}: ${config["budget"]}')

            # Create task costs for ALL tasks (not just first 15)
            tasks = Task.objects.filter(column__board=board)
            task_costs_created = 0
            
            # Define board-specific cost and hour ranges for realistic demo data
            board_name = config['name']
            if board_name == 'Software Development':
                # Higher costs and hours for development work
                min_cost, max_cost = 800, 8000
                min_hours, max_hours = 8, 60
                hourly_rate_range = (75, 150)  # Developer rates
            elif board_name == 'Marketing Campaign':
                # Moderate costs for marketing
                min_cost, max_cost = 500, 5000
                min_hours, max_hours = 4, 40
                hourly_rate_range = (50, 100)  # Marketing rates
            else:  # Bug Tracking
                # Lower costs for bug fixes
                min_cost, max_cost = 200, 3000
                min_hours, max_hours = 2, 24
                hourly_rate_range = (60, 120)  # QA/Dev rates

            for i, task in enumerate(tasks):
                # Base estimated cost and hours
                estimated_cost = Decimal(random.uniform(min_cost, max_cost)).quantize(Decimal('0.01'))
                estimated_hours = Decimal(random.uniform(min_hours, max_hours)).quantize(Decimal('0.01'))
                hourly_rate = Decimal(random.uniform(*hourly_rate_range)).quantize(Decimal('0.01'))
                
                # Adjust based on task complexity if available
                complexity = getattr(task, 'complexity_score', 5)
                if complexity >= 8:
                    # Complex tasks cost more
                    estimated_cost = estimated_cost * Decimal('1.3')
                    estimated_hours = estimated_hours * Decimal('1.4')
                elif complexity <= 3:
                    # Simple tasks cost less
                    estimated_cost = estimated_cost * Decimal('0.6')
                    estimated_hours = estimated_hours * Decimal('0.5')

                # Some tasks over budget for realistic demo (every 5th task)
                if i % 5 == 0:
                    actual_cost = estimated_cost * Decimal('1.25')
                else:
                    actual_cost = estimated_cost * Decimal(random.uniform(0.7, 1.1))

                TaskCost.objects.get_or_create(
                    task=task,
                    defaults={
                        'estimated_cost': estimated_cost.quantize(Decimal('0.01')),
                        'actual_cost': actual_cost.quantize(Decimal('0.01')),
                        'estimated_hours': estimated_hours.quantize(Decimal('0.01')),
                        'hourly_rate': hourly_rate,
                    }
                )
                task_costs_created += 1
            
            self.stdout.write(f'   ✅ Created {task_costs_created} task costs for {config["name"]}')

            # Create historical ROI snapshots (10 months of data)
            total_tasks = Task.objects.filter(column__board=board).count()
            completed_tasks = Task.objects.filter(column__board=board, progress=100).count()
            
            # Delete existing ROI snapshots for this board to recreate fresh
            ProjectROI.objects.filter(board=board).delete()
            
            # Calculate actual costs for this board
            task_costs_qs = TaskCost.objects.filter(task__column__board=board)
            total_cost = sum([tc.actual_cost or Decimal('0.00') for tc in task_costs_qs]) if task_costs_qs else config['budget'] * Decimal('0.8')
            
            # Set initial values based on board type for realistic data
            board_name = config['name']
            if board_name == 'Software Development':
                base_expected = config['budget'] * Decimal('2.0')  # 100% ROI expected
                base_realized_ratio = Decimal('0.4')  # Starting at 40% realization
            elif board_name == 'Marketing Campaign':
                base_expected = config['budget'] * Decimal('1.8')  # 80% ROI expected
                base_realized_ratio = Decimal('0.35')  # Starting at 35% realization
            else:  # Bug Tracking
                base_expected = config['budget'] * Decimal('1.5')  # 50% ROI expected
                base_realized_ratio = Decimal('0.45')  # Starting at 45% realization
            
            # Create 10 historical snapshots over the past 10 months
            for i in range(10):
                snapshot_date = now - timedelta(days=30 * (9 - i))  # Go back 9 months, then forward
                
                # Calculate progressive improvement
                progress_factor = Decimal(str(i / 9))  # 0 to 1 over time
                
                # Realized value improves over time (from base to 80% of expected)
                realized_value = base_expected * (base_realized_ratio + (Decimal('0.4') * progress_factor))
                
                # Cost also increases progressively
                snapshot_cost = total_cost * (Decimal('0.3') + (Decimal('0.7') * progress_factor))
                
                # Calculate ROI percentage
                if snapshot_cost > 0:
                    roi_percentage = ((realized_value - snapshot_cost) / snapshot_cost) * 100
                else:
                    roi_percentage = Decimal('0.00')
                
                # Create snapshot
                ProjectROI.objects.create(
                    board=board,
                    snapshot_date=snapshot_date,
                    expected_value=base_expected,
                    realized_value=realized_value,
                    roi_percentage=roi_percentage,
                    total_cost=snapshot_cost,
                    total_tasks=total_tasks,
                    completed_tasks=int(completed_tasks * float(progress_factor)),  # Progressive completion
                    created_by=admin_user
                )

        self.stdout.write('   ✅ Budget and ROI data created (10 historical snapshots per board)')

    def create_burndown_data(self, software_board, marketing_board, bug_board):
        """
        Create burndown and velocity snapshot data with proper historical data.
        This ensures the burndown chart displays correctly with historical progress,
        projected completion, and confidence bands.
        """
        from kanban.utils.burndown_predictor import BurndownPredictor
        
        now = timezone.now()
        
        for board in [software_board, marketing_board, bug_board]:
            self.stdout.write(f'     Processing {board.name}...')
            
            # Step 1: Populate historical completion dates for completed tasks
            completed_tasks = list(Task.objects.filter(column__board=board, progress=100))
            
            if completed_tasks:
                # Distribute completion dates across past 6 weeks
                weeks_back = 6
                tasks_per_week = len(completed_tasks) // weeks_back if weeks_back > 0 else len(completed_tasks)
                
                task_index = 0
                for week in range(weeks_back, 0, -1):
                    # Calculate date range for this week
                    week_end = now - timedelta(weeks=week-1)
                    week_start = week_end - timedelta(days=7)
                    
                    # Determine how many tasks to complete this week (with variation)
                    base_count = tasks_per_week
                    variation = random.randint(-2, 3)
                    tasks_this_week = max(1, base_count + variation)
                    tasks_this_week = min(tasks_this_week, len(completed_tasks) - task_index)
                    
                    for i in range(tasks_this_week):
                        if task_index >= len(completed_tasks):
                            break
                            
                        task = completed_tasks[task_index]
                        
                        # Random completion time within the week
                        days_offset = random.randint(0, 6)
                        hours_offset = random.randint(0, 23)
                        minutes_offset = random.randint(0, 59)
                        
                        completion_date = week_start + timedelta(
                            days=days_offset,
                            hours=hours_offset,
                            minutes=minutes_offset
                        )
                        
                        task.completed_at = completion_date
                        task.progress = 100
                        task.save(update_fields=['completed_at', 'progress'])
                        
                        task_index += 1
                
                # Mark remaining tasks as completed recently (current week)
                current_week_start = now - timedelta(days=7)
                while task_index < len(completed_tasks):
                    task = completed_tasks[task_index]
                    days_offset = random.randint(0, 6)
                    hours_offset = random.randint(0, 23)
                    
                    completion_date = current_week_start + timedelta(
                        days=days_offset,
                        hours=hours_offset
                    )
                    
                    task.completed_at = completion_date
                    task.progress = 100
                    task.save(update_fields=['completed_at', 'progress'])
                    task_index += 1
            
            # Step 2: Clean up old burndown data
            BurndownPrediction.objects.filter(board=board).delete()
            TeamVelocitySnapshot.objects.filter(board=board).delete()
            
            # Step 3: Create velocity snapshots based on actual task completions
            predictor = BurndownPredictor()
            predictor._ensure_velocity_snapshots(board)
            
            # Step 4: Generate burndown prediction with proper chart data
            result = predictor.generate_burndown_prediction(board)
            
            prediction = result.get('prediction')
            if prediction:
                curve = prediction.burndown_curve_data
                self.stdout.write(
                    f'       ✓ {len(curve.get("historical", []))} historical, '
                    f'{len(curve.get("projected", []))} projected points'
                )
            else:
                self.stdout.write(self.style.WARNING('       ⚠ Prediction generation failed'))

        self.stdout.write('   ✅ Burndown and velocity data created with full chart data')

    def create_retrospective_data(self, software_board, marketing_board, bug_board, alex, sam, jordan):
        """Create retrospective data for demo boards"""
        now = timezone.now().date()
        boards = [
            (software_board, 'Software Development Sprint'),
            (marketing_board, 'Marketing Campaign Review'),
            (bug_board, 'Bug Fix Retrospective'),
        ]

        for board, title_prefix in boards:
            week_num = random.randint(1, 12)
            retro, created = ProjectRetrospective.objects.get_or_create(
                board=board,
                title=f'{title_prefix} - Week {week_num}',
                defaults={
                    'retrospective_type': 'sprint',
                    'status': 'finalized',
                    'period_start': now - timedelta(weeks=2),
                    'period_end': now - timedelta(weeks=1),
                    'what_went_well': f'Team showed good collaboration and met sprint goals for {board.name}.',
                    'what_needs_improvement': 'Consider improving code review turnaround time.',
                    'lessons_learned': [
                        {'title': 'Daily standups improve coordination', 'category': 'process'},
                        {'title': 'Clear requirements reduce rework', 'category': 'communication'}
                    ],
                    'improvement_recommendations': [
                        {'title': 'Add code review guidelines', 'priority': 'high'},
                        {'title': 'Implement pair programming for complex tasks', 'priority': 'medium'}
                    ],
                    'created_by': alex,
                }
            )

            if created:
                # Add lessons learned
                lessons = [
                    {'category': 'process', 'title': 'Daily standups improve coordination'},
                    {'category': 'technical', 'title': 'Code reviews catch bugs early'},
                    {'category': 'communication', 'title': 'Clear requirements reduce rework'},
                ]

                for lesson in lessons:
                    LessonLearned.objects.create(
                        retrospective=retro,
                        board=board,
                        category=lesson['category'],
                        title=lesson['title'],
                        description=f'Detailed insight about {lesson["title"].lower()}',
                        recommended_action=f'Apply {lesson["title"].lower()} in next sprint',
                        priority='high' if random.random() > 0.5 else 'medium',
                        status='identified',
                    )

                # Add action items with meaningful titles based on board type
                action_items_by_board = {
                    'Software Development Sprint': [
                        {
                            'title': 'Implement automated code review checklist',
                            'description': 'Create and integrate automated checklist for code reviews to ensure consistent quality standards',
                            'action_type': 'process_change',
                            'priority': 'high'
                        },
                        {
                            'title': 'Reduce technical debt in authentication module',
                            'description': 'Allocate 20% of sprint capacity to refactor and document authentication code',
                            'action_type': 'technical_improvement',
                            'priority': 'medium'
                        }
                    ],
                    'Marketing Campaign Review': [
                        {
                            'title': 'Improve campaign performance tracking',
                            'description': 'Set up automated dashboards for real-time campaign metrics and ROI tracking',
                            'action_type': 'tool_adoption',
                            'priority': 'high'
                        },
                        {
                            'title': 'Enhance team collaboration on content creation',
                            'description': 'Schedule weekly brainstorming sessions and implement shared content calendar',
                            'action_type': 'team_building',
                            'priority': 'medium'
                        }
                    ],
                    'Bug Fix Retrospective': [
                        {
                            'title': 'Establish bug triage process',
                            'description': 'Create priority matrix and daily triage meetings to handle critical bugs faster',
                            'action_type': 'process_change',
                            'priority': 'high'
                        },
                        {
                            'title': 'Improve bug documentation standards',
                            'description': 'Create bug report template with reproduction steps and impact assessment',
                            'action_type': 'documentation',
                            'priority': 'medium'
                        }
                    ]
                }
                
                # Select appropriate action items based on title prefix
                action_items = action_items_by_board.get(title_prefix, [
                    {
                        'title': 'Implement process improvements',
                        'description': 'Follow up on retrospective discussion and implement agreed changes',
                        'action_type': 'process_change',
                        'priority': 'high'
                    }
                ])
                
                # Create the action items only if they don't already exist for this board
                for idx, action_data in enumerate(action_items):
                    # Check if this action already exists for this board (avoid duplicates)
                    existing_action = RetrospectiveActionItem.objects.filter(
                        board=board,
                        title=action_data['title'],
                        assigned_to=sam if idx == 0 else (jordan if idx == 1 else alex)
                    ).first()
                    
                    if not existing_action:
                        days_offset = 14 if action_data['priority'] == 'high' else 30
                        RetrospectiveActionItem.objects.create(
                            retrospective=retro,
                            board=board,
                            title=action_data['title'],
                            description=action_data['description'],
                            action_type=action_data['action_type'],
                            assigned_to=sam if idx == 0 else (jordan if idx == 1 else alex),
                            target_completion_date=(timezone.now() + timedelta(days=days_offset)).date(),
                            priority=action_data['priority'],
                            status='in_progress' if idx == 0 else 'pending',
                            expected_impact=f'Improve team efficiency and {board.name.lower()} outcomes'
                        )

        self.stdout.write('   ✅ Retrospective data created')

    def create_coaching_data(self, software_board, marketing_board, bug_board):
        """Create AI-enhanced coaching suggestions for demo boards
        
        This creates detailed suggestions matching the AI-enhanced format:
        - Comprehensive reasoning (why this matters)
        - 3-5 detailed action steps with rationale, expected outcomes, and implementation hints
        - Expected impact with quantifiable outcomes
        - Proper metrics snapshot
        """
        # Delete existing suggestions first to avoid duplicates
        CoachingSuggestion.objects.filter(
            board__in=[software_board, marketing_board, bug_board]
        ).delete()
        
        # AI-Enhanced suggestions with detailed format
        suggestions = [
            # Suggestion 1: Resource Overload (High Severity)
            {
                'suggestion_type': 'resource_overload',
                'title': 'Team workload imbalance detected',
                'message': 'Sam has 60% more tasks than other team members. Consider redistributing work to prevent burnout and ensure timely delivery.',
                'severity': 'high',
                'reasoning': 'Workload imbalances can lead to burnout, reduced productivity, and potential project delays. When one team member has significantly more tasks than others, it creates a single point of failure. If Sam becomes unavailable or overwhelmed, critical work could stall. Additionally, uneven workloads can impact team morale as other members may feel underutilized.',
                'recommended_actions': [
                    "Conduct a workload review meeting with the team • Rationale: Creates transparency about current assignments and identifies immediate redistribution opportunities • Expected outcome: Identify 3-5 tasks that can be reassigned immediately • How to: Schedule 30-minute meeting, use task board to visualize assignments per person",
                    "Prioritize Sam's tasks and identify which can be delegated • Rationale: Not all high-priority tasks require Sam's specific expertise • Expected outcome: Reduce Sam's workload by 30% without impacting critical deliverables • How to: Review each task for skill requirements, pair junior members with Sam for knowledge transfer",
                    "Implement work-in-progress (WIP) limits • Rationale: Prevents any team member from accumulating too many tasks • Expected outcome: Even distribution of work across the team • How to: Set WIP limit of 5 tasks per person, add to team working agreement",
                    "Schedule regular capacity planning reviews • Rationale: Proactive monitoring prevents future imbalances • Expected outcome: Early detection of workload issues • How to: Weekly 15-minute standup focused on capacity, rotate facilitator role"
                ],
                'expected_impact': 'Rebalancing workload can improve team velocity by 15-20%, reduce burnout risk, and improve overall team satisfaction. Even task distribution also builds redundancy into the team.',
                'confidence_score': 0.88,
                'metrics_snapshot': {'imbalanced_member': 'Sam', 'task_variance': '60%', 'team_avg_tasks': 8, 'overloaded_tasks': 13}
            },
            # Suggestion 2: Deadline Risk (Medium Severity)
            {
                'suggestion_type': 'deadline_risk',
                'title': 'Deadline risk identified',
                'message': 'Based on current velocity, the beta release may slip by 3 days. Immediate attention needed to mitigate timeline risk.',
                'severity': 'medium',
                'reasoning': 'Current velocity metrics show the team completing 8 tasks per week, but 12 tasks remain for the beta release with only 1 week left. This 3-day projected slip could cascade into downstream dependencies including marketing launch dates and customer commitments. Early identification allows for scope adjustment or resource reallocation.',
                'recommended_actions': [
                    "Review remaining tasks and identify scope reduction opportunities • Rationale: Some features may be deferrable to post-beta without impacting core functionality • Expected outcome: Reduce remaining work by 20-30% • How to: Hold scope review with product owner, use MoSCoW prioritization",
                    "Identify and remove blockers immediately • Rationale: Blocked tasks directly impact velocity and create uncertainty • Expected outcome: Increase effective velocity by 15% • How to: Daily blocker review, escalate dependencies same-day",
                    "Consider focused sprint with reduced meetings • Rationale: Meeting overhead reduces productive coding time • Expected outcome: Gain 2-3 hours per developer per day • How to: Cancel non-essential meetings, move standups to async format",
                    "Communicate proactively with stakeholders • Rationale: Managing expectations early preserves trust and allows for contingency planning • Expected outcome: Stakeholder alignment on realistic timeline • How to: Send status update email, propose adjusted date with confidence level"
                ],
                'expected_impact': 'Addressing deadline risk early can reduce actual slip from 3 days to 1 day or less. Proactive communication maintains stakeholder trust and allows for better planning.',
                'confidence_score': 0.82,
                'metrics_snapshot': {'current_velocity': 8, 'remaining_tasks': 12, 'days_remaining': 7, 'projected_slip_days': 3}
            },
            # Suggestion 3: Best Practice (Low Severity)
            {
                'suggestion_type': 'best_practice',
                'title': 'Process improvement opportunity',
                'message': 'Tasks in review stage average 4 days. Consider adding reviewers or streamlining the review process.',
                'severity': 'low',
                'reasoning': 'A 4-day average review time creates bottlenecks and slows down delivery. Industry best practice targets 1-2 days for code review. Extended review periods indicate potential issues with reviewer availability, unclear acceptance criteria, or overly complex code changes. Long reviews also increase context-switching costs when changes are requested.',
                'recommended_actions': [
                    "Establish a reviewer rotation schedule • Rationale: Dedicated review time ensures consistent throughput • Expected outcome: Reduce review wait time by 50% • How to: Assign review slots (morning/afternoon) to specific team members, update working agreement",
                    "Create a review checklist and guidelines • Rationale: Clear criteria speeds up reviews and reduces back-and-forth • Expected outcome: More consistent, faster reviews • How to: Document 5-10 key items to check, include in PR template",
                    "Implement automated pre-review checks • Rationale: Catches common issues before human review, reducing cognitive load • Expected outcome: 20% fewer review comments on trivial issues • How to: Set up linting, formatting, and basic test gates in CI/CD",
                    "Consider pair programming for complex changes • Rationale: Real-time collaboration eliminates post-hoc review delays • Expected outcome: Near-zero review time for paired work • How to: Identify complex tasks upfront, schedule pairing sessions"
                ],
                'expected_impact': 'Reducing review time from 4 days to 2 days can improve team velocity by 15-20%, accelerate feature delivery, and reduce developer frustration with waiting.',
                'confidence_score': 0.85,
                'metrics_snapshot': {'avg_review_days': 4, 'target_review_days': 2, 'tasks_in_review': 5, 'longest_review_days': 7}
            },
        ]

        # Board-specific additional suggestions
        software_specific = {
            'suggestion_type': 'dependency_blocker',
            'title': 'Dependency chain creating risk',
            'message': 'Three tasks have dependencies that could delay the API integration milestone.',
            'severity': 'high',
            'reasoning': 'Sequential dependencies create a critical path where delays compound. The current dependency chain (Database Schema → API Structure → Authentication) means any slip in early tasks directly impacts all downstream work. This pattern also limits parallel work opportunities.',
            'recommended_actions': [
                "Map and visualize the complete dependency chain • Rationale: Understanding the full impact helps prioritize interventions • Expected outcome: Clear view of critical path and risk points • How to: Use Gantt chart or dependency graph, mark critical path items",
                "Identify opportunities to parallelize work • Rationale: Breaking dependencies enables concurrent progress • Expected outcome: Reduce critical path length by 20% • How to: Mock interfaces early, use feature flags for partial integration",
                "Add buffer time to critical path estimates • Rationale: Dependencies have higher uncertainty requiring risk buffer • Expected outcome: More realistic project timeline • How to: Add 20% buffer to dependent task estimates",
                "Daily sync on dependency status • Rationale: Early warning of slips enables faster response • Expected outcome: Issues identified within 24 hours • How to: Add dependency check to daily standup agenda"
            ],
            'expected_impact': 'Proactive dependency management can reduce schedule risk by 30% and enable more parallel work streams.',
            'confidence_score': 0.80,
            'metrics_snapshot': {'dependent_tasks': 3, 'max_chain_length': 4, 'critical_path_days': 12}
        }

        marketing_specific = {
            'suggestion_type': 'scope_creep',
            'title': 'Campaign scope expanding',
            'message': 'The marketing campaign has grown by 25% since initial planning. Consider a scope review.',
            'severity': 'medium',
            'reasoning': 'Scope creep often occurs gradually through well-intentioned additions. A 25% growth indicates potential misalignment between resources and objectives. Without adjustment, this leads to quality compromises, missed deadlines, or team burnout.',
            'recommended_actions': [
                "Conduct a scope review session with stakeholders • Rationale: Realign expectations with available resources • Expected outcome: Clear agreement on essential vs nice-to-have deliverables • How to: List all additions since kickoff, apply MoSCoW prioritization",
                "Document and communicate the scope baseline • Rationale: Creates shared understanding and change control process • Expected outcome: Reduced ad-hoc scope additions • How to: Create scope document, require sign-off for changes",
                "Evaluate resource needs if scope must stay • Rationale: Expanding scope requires expanding capacity • Expected outcome: Realistic plan with adequate resources • How to: Calculate effort for additions, identify resource gaps",
                "Implement a change request process • Rationale: Formal process slows uncontrolled growth • Expected outcome: Deliberate decisions about scope changes • How to: Create simple change request form, require impact assessment"
            ],
            'expected_impact': 'Managing scope creep can improve delivery success rate by 40% and maintain team sustainable pace.',
            'confidence_score': 0.78,
            'metrics_snapshot': {'original_tasks': 20, 'current_tasks': 25, 'scope_growth_percent': 25}
        }

        bug_specific = {
            'suggestion_type': 'quality_issue',
            'title': 'Bug recurrence pattern detected',
            'message': 'Similar bugs are reappearing in the authentication module. Root cause analysis recommended.',
            'severity': 'high',
            'reasoning': 'Recurring bugs indicate systemic issues rather than isolated defects. The authentication module pattern suggests potential gaps in testing coverage, unclear requirements, or architectural weaknesses. Each recurrence wastes fix time and erodes user trust.',
            'recommended_actions': [
                "Conduct root cause analysis on recurring bugs • Rationale: Surface fixes don't address underlying issues • Expected outcome: Identify systemic causes and prevention strategies • How to: Use 5 Whys technique, involve senior engineers",
                "Increase test coverage for authentication module • Rationale: Gaps in testing allow regressions • Expected outcome: Prevent 80% of bug recurrence • How to: Add integration tests, implement mutation testing",
                "Review and clarify authentication requirements • Rationale: Ambiguous requirements lead to implementation gaps • Expected outcome: Clearer acceptance criteria • How to: Document edge cases, validate with security team",
                "Consider architectural review of authentication • Rationale: Pattern may indicate design issues • Expected outcome: More robust implementation • How to: Schedule architecture review session, consider refactoring"
            ],
            'expected_impact': 'Addressing root causes can reduce bug recurrence by 70% and improve overall code quality.',
            'confidence_score': 0.85,
            'metrics_snapshot': {'recurring_bugs': 5, 'affected_module': 'authentication', 'recurrence_rate': '30%'}
        }

        # Create suggestions for each board
        created_count = 0
        
        for board, specific_suggestion in [
            (software_board, software_specific),
            (marketing_board, marketing_specific),
            (bug_board, bug_specific)
        ]:
            # Create common suggestions for each board
            for suggestion in suggestions:
                CoachingSuggestion.objects.create(
                    board=board,
                    suggestion_type=suggestion['suggestion_type'],
                    title=suggestion['title'],
                    message=suggestion['message'],
                    severity=suggestion['severity'],
                    status='active',
                    reasoning=suggestion['reasoning'],
                    recommended_actions=suggestion['recommended_actions'],
                    expected_impact=suggestion['expected_impact'],
                    confidence_score=suggestion['confidence_score'],
                    metrics_snapshot=suggestion['metrics_snapshot'],
                    ai_model_used='gemini-2.0-flash-exp',
                    generation_method='hybrid',  # Indicates AI-enhanced format
                )
                created_count += 1
            
            # Create board-specific suggestion
            CoachingSuggestion.objects.create(
                board=board,
                suggestion_type=specific_suggestion['suggestion_type'],
                title=specific_suggestion['title'],
                message=specific_suggestion['message'],
                severity=specific_suggestion['severity'],
                status='active',
                reasoning=specific_suggestion['reasoning'],
                recommended_actions=specific_suggestion['recommended_actions'],
                expected_impact=specific_suggestion['expected_impact'],
                confidence_score=specific_suggestion['confidence_score'],
                metrics_snapshot=specific_suggestion['metrics_snapshot'],
                ai_model_used='gemini-2.0-flash-exp',
                generation_method='hybrid',
            )
            created_count += 1

        self.stdout.write(f'   ✅ AI coaching suggestions created ({created_count} total, all AI-enhanced)')
        
        # Create PM Metrics for analytics dashboard
        self.create_pm_metrics(software_board, marketing_board, bug_board)

    def create_pm_metrics(self, software_board, marketing_board, bug_board):
        """Create PM performance metrics for analytics dashboard
        
        Creates historical metrics data so the coaching analytics page has
        meaningful data to display immediately.
        """
        from django.contrib.auth import get_user_model
        User = get_user_model()
        
        # Get demo users
        demo_admin = User.objects.filter(
            username__in=['demo_pm', 'alex_demo', 'admin']
        ).first()
        
        if not demo_admin:
            self.stdout.write('   ⚠️  PM metrics skipped (no demo user found)')
            return
        
        # Delete existing metrics
        PMMetrics.objects.filter(
            board__in=[software_board, marketing_board, bug_board]
        ).delete()
        
        now = timezone.now().date()
        
        # Create 4 weeks of historical metrics for each board
        metrics_created = 0
        
        for board in [software_board, marketing_board, bug_board]:
            for week_offset in range(4):
                period_end = now - timedelta(weeks=week_offset)
                period_start = period_end - timedelta(days=7)
                
                # Vary metrics to show realistic patterns
                if week_offset == 0:  # Current week
                    suggestions_received = random.randint(3, 5)
                    suggestions_acted = random.randint(2, 4)
                    velocity_trend = 'stable'
                    risk_rate = random.uniform(70, 85)
                    deadline_rate = random.uniform(80, 95)
                    effectiveness = random.uniform(70, 85)
                elif week_offset == 1:  # Last week
                    suggestions_received = random.randint(4, 6)
                    suggestions_acted = random.randint(3, 5)
                    velocity_trend = 'improving'
                    risk_rate = random.uniform(65, 80)
                    deadline_rate = random.uniform(75, 90)
                    effectiveness = random.uniform(65, 80)
                else:  # Older weeks
                    suggestions_received = random.randint(2, 4)
                    suggestions_acted = random.randint(1, 3)
                    velocity_trend = random.choice(['stable', 'improving', 'declining'])
                    risk_rate = random.uniform(60, 75)
                    deadline_rate = random.uniform(70, 85)
                    effectiveness = random.uniform(55, 70)
                
                PMMetrics.objects.create(
                    board=board,
                    pm_user=demo_admin,
                    period_start=period_start,
                    period_end=period_end,
                    suggestions_received=suggestions_received,
                    suggestions_acted_on=suggestions_acted,
                    avg_response_time_hours=Decimal(str(round(random.uniform(4, 48), 2))),
                    velocity_trend=velocity_trend,
                    risk_mitigation_success_rate=Decimal(str(round(risk_rate, 2))),
                    deadline_hit_rate=Decimal(str(round(deadline_rate, 2))),
                    team_satisfaction_score=Decimal(str(round(random.uniform(3.5, 4.5), 1))),
                    improvement_areas=['communication', 'planning'] if week_offset < 2 else ['risk management'],
                    struggle_areas=['scope management'] if week_offset == 0 else [],
                    coaching_effectiveness_score=Decimal(str(round(effectiveness, 2))),
                    calculated_by='demo_data_population',
                )
                metrics_created += 1
        
        self.stdout.write(f'   ✅ PM metrics created ({metrics_created} total)')
        
        # Create coaching insights for analytics
        self.create_coaching_insights()

    def create_coaching_insights(self):
        """Create coaching insights for analytics dashboard
        
        Insights represent learned patterns from coaching interactions
        that help improve future suggestions.
        """
        # Delete existing insights
        CoachingInsight.objects.all().delete()
        
        insights_data = [
            {
                'insight_type': 'pattern',
                'title': 'Resource overload correlates with deadline misses',
                'description': 'Teams with workload imbalances above 50% show a 35% higher rate of deadline misses. Early intervention when imbalance exceeds 40% significantly improves outcomes.',
                'confidence_score': Decimal('0.85'),
                'sample_size': 150,
                'applicable_to_suggestion_types': ['resource_overload', 'deadline_risk'],
                'rule_adjustments': {'threshold_adjustment': -10, 'severity_boost': True},
                'is_active': True,
            },
            {
                'insight_type': 'effectiveness',
                'title': 'Review time suggestions have high action rate',
                'description': 'Suggestions about reducing review time are acted upon 78% of the time, with 82% of users reporting positive outcomes. This category of suggestions is highly effective.',
                'confidence_score': Decimal('0.82'),
                'sample_size': 95,
                'applicable_to_suggestion_types': ['best_practice', 'quality_issue'],
                'rule_adjustments': {},
                'is_active': True,
            },
            {
                'insight_type': 'pm_behavior',
                'title': 'PMs respond faster to high-severity suggestions',
                'description': 'Average response time for critical/high severity suggestions is 4.2 hours compared to 18.5 hours for low severity. Consider severity escalation for time-sensitive issues.',
                'confidence_score': Decimal('0.90'),
                'sample_size': 280,
                'applicable_to_suggestion_types': ['deadline_risk', 'resource_overload', 'quality_issue'],
                'rule_adjustments': {'auto_escalate_after_days': 2},
                'is_active': True,
            },
            {
                'insight_type': 'team_dynamics',
                'title': 'Small teams respond better to specific recommendations',
                'description': 'Teams of 3-5 members show 40% higher action rate on specific, actionable recommendations compared to general guidance. Larger teams prefer strategic suggestions.',
                'confidence_score': Decimal('0.75'),
                'sample_size': 120,
                'applicable_to_suggestion_types': ['best_practice', 'communication_gap'],
                'rule_adjustments': {'team_size_threshold': 5},
                'is_active': True,
            },
            {
                'insight_type': 'context_factor',
                'title': 'End-of-sprint suggestions less effective',
                'description': 'Suggestions generated in the final 2 days of a sprint have 45% lower action rates. Teams are focused on completion rather than process improvements during this time.',
                'confidence_score': Decimal('0.78'),
                'sample_size': 200,
                'applicable_to_suggestion_types': ['best_practice', 'scope_creep'],
                'rule_adjustments': {'suppress_in_final_days': 2},
                'is_active': True,
            },
        ]
        
        for insight in insights_data:
            CoachingInsight.objects.create(**insight)
        
        self.stdout.write(f'   ✅ Coaching insights created ({len(insights_data)} total)')

    def create_comments(self, tasks, alex, sam, jordan):
        """Create realistic comments for tasks"""
        users = [alex, sam, jordan]
        comments_created = 0
        now = timezone.now().date()

        for task in tasks:
            # Create 0-4 comments per task
            num_comments = random.randint(0, 4)

            for i in range(num_comments):
                user = random.choice(users)
                template = random.choice(COMMENT_TEMPLATES)

                # Fill in template variables
                comment_text = template.format(
                    progress_detail=random.choice(PROGRESS_DETAILS),
                    technical_detail=random.choice(TECHNICAL_DETAILS),
                    complexity_reason=random.choice(COMPLEXITY_REASONS),
                    mention=random.choice([u.username for u in users if u != user]),
                    related_task=random.choice(tasks).title[:30] if tasks else 'another task',
                )

                comment_date = now - timedelta(days=random.randint(1, 30), hours=random.randint(0, 23))

                Comment.objects.create(
                    task=task,
                    user=user,
                    content=comment_text,
                    created_at=comment_date,
                )
                comments_created += 1

        self.stdout.write(f'   ✅ Created {comments_created} comments')

    def create_activity_logs(self, tasks, alex, sam, jordan):
        """Create activity logs for tasks"""
        users = [alex, sam, jordan]
        activities_created = 0
        now = timezone.now().date()

        for task in tasks:
            # Always create a 'created' activity
            TaskActivity.objects.create(
                task=task,
                user=task.created_by or alex,
                activity_type='created',
                description=random.choice(ACTIVITY_TEMPLATES['created']),
            )
            activities_created += 1

            # Add 1-3 more activities based on task progress
            if task.progress > 0:
                num_activities = random.randint(1, 3)

                for i in range(num_activities):
                    activity_type = random.choice(['updated', 'moved', 'commented'])
                    templates = ACTIVITY_TEMPLATES.get(activity_type, ['performed an action'])
                    description = random.choice(templates)

                    # Fill in template variables
                    description = description.format(
                        from_col='To Do',
                        to_col='In Progress',
                        assignee=random.choice([u.username for u in users]),
                        priority=task.priority or 'medium',
                        progress=task.progress,
                        label='Kaizen',
                    )

                    TaskActivity.objects.create(
                        task=task,
                        user=random.choice(users),
                        activity_type=activity_type,
                        description=description,
                    )
                    activities_created += 1

        self.stdout.write(f'   ✅ Created {activities_created} activity logs')

    def create_stakeholders(self, software_board, marketing_board, bug_board, tasks, alex, sam, jordan):
        """Create stakeholders and link them to tasks"""
        stakeholder_data = [
            {'name': 'Sarah Johnson', 'role': 'Product Owner', 'email': 'sarah.j@example.com', 'influence': 'high'},
            {'name': 'Mike Chen', 'role': 'Engineering Director', 'email': 'mike.c@example.com', 'influence': 'high'},
            {'name': 'Lisa Park', 'role': 'QA Lead', 'email': 'lisa.p@example.com', 'influence': 'medium'},
            {'name': 'David Wilson', 'role': 'UX Designer', 'email': 'david.w@example.com', 'influence': 'medium'},
            {'name': 'Emma Davis', 'role': 'Marketing Manager', 'email': 'emma.d@example.com', 'influence': 'medium'},
        ]

        for board in [software_board, marketing_board, bug_board]:
            for data in stakeholder_data:
                stakeholder, created = ProjectStakeholder.objects.get_or_create(
                    board=board,
                    email=data['email'],
                    name=data['name'],
                    defaults={
                        'role': data['role'],
                        'influence_level': data['influence'],
                        'interest_level': 'medium',
                        'created_by': alex,
                    }
                )

        # Link stakeholders to some tasks
        stakeholders = list(ProjectStakeholder.objects.filter(
            board__in=[software_board, marketing_board, bug_board]
        ))

        for task in tasks[:20]:  # Link to first 20 tasks
            stakeholder = random.choice(stakeholders)
            StakeholderTaskInvolvement.objects.get_or_create(
                stakeholder=stakeholder,
                task=task,
                defaults={
                    'involvement_type': random.choice(['reviewer', 'observer', 'contributor']),
                    'engagement_status': random.choice(['informed', 'consulted', 'involved']),
                    'feedback': f'Involved in {task.title[:30]}',
                }
            )

        self.stdout.write('   ✅ Stakeholders created and linked to tasks')

    def create_sprint_milestones(self, software_board, marketing_board, bug_board):
        """Create sprint milestones for burndown tracking"""
        from kanban.burndown_models import SprintMilestone
        
        now = timezone.now().date()
        milestones_created = 0
        
        for board in [software_board, marketing_board, bug_board]:
            # Delete existing milestones
            SprintMilestone.objects.filter(board=board).delete()
            
            # Create 3 milestones per board
            task_count = Task.objects.filter(column__board=board).count()
            
            milestone_configs = [
                {
                    'name': 'Sprint Mid-Point',
                    'target_date': now + timedelta(days=7),
                    'target_tasks': int(task_count * 0.4),
                    'is_completed': False,
                },
                {
                    'name': 'Feature Freeze',
                    'target_date': now + timedelta(days=12),
                    'target_tasks': int(task_count * 0.7),
                    'is_completed': False,
                },
                {
                    'name': 'Sprint End',
                    'target_date': now + timedelta(days=14),
                    'target_tasks': task_count,
                    'is_completed': False,
                },
            ]
            
            for config in milestone_configs:
                SprintMilestone.objects.create(
                    board=board,
                    name=config['name'],
                    target_date=config['target_date'],
                    target_tasks_completed=config['target_tasks'],
                    is_completed=config['is_completed'],
                )
                milestones_created += 1
        
        self.stdout.write(f'   ✅ Created {milestones_created} sprint milestones')

    def create_skill_data(self, software_board, marketing_board, bug_board, all_tasks):
        """Create team skill profiles and skill gaps for boards"""
        from kanban.models import TeamSkillProfile, SkillGap
        
        now = timezone.now()
        
        skill_configs = {
            software_board: {
                'skills': SOFTWARE_SKILLS,
                'inventory': {
                    'Python': {'expert': 1, 'advanced': 2, 'intermediate': 1, 'beginner': 0},
                    'JavaScript': {'expert': 0, 'advanced': 2, 'intermediate': 2, 'beginner': 0},
                    'React': {'expert': 0, 'advanced': 1, 'intermediate': 2, 'beginner': 0},
                    'Django': {'expert': 1, 'advanced': 1, 'intermediate': 0, 'beginner': 0},
                    'PostgreSQL': {'expert': 0, 'advanced': 0, 'intermediate': 2, 'beginner': 1},
                    'Docker': {'expert': 0, 'advanced': 0, 'intermediate': 2, 'beginner': 0},
                    'AWS': {'expert': 0, 'advanced': 0, 'intermediate': 1, 'beginner': 1},
                },
                'gaps': [
                    {'skill': 'Kubernetes', 'level': 'intermediate', 'required': 2, 'available': 0, 'severity': 'high'},
                    {'skill': 'Security', 'level': 'advanced', 'required': 1, 'available': 0, 'severity': 'critical'},
                    {'skill': 'Machine Learning', 'level': 'intermediate', 'required': 1, 'available': 0, 'severity': 'medium'},
                ],
                'capacity': Decimal('120.0'),
                'utilized': Decimal('95.0'),
            },
            marketing_board: {
                'skills': MARKETING_SKILLS,
                'inventory': {
                    'Content Strategy': {'expert': 0, 'advanced': 2, 'intermediate': 1, 'beginner': 0},
                    'SEO/SEM': {'expert': 0, 'advanced': 1, 'intermediate': 2, 'beginner': 0},
                    'Social Media Marketing': {'expert': 1, 'advanced': 2, 'intermediate': 0, 'beginner': 0},
                    'Analytics': {'expert': 0, 'advanced': 2, 'intermediate': 1, 'beginner': 0},
                    'Copywriting': {'expert': 0, 'advanced': 2, 'intermediate': 1, 'beginner': 0},
                },
                'gaps': [
                    {'skill': 'Video Production', 'level': 'advanced', 'required': 1, 'available': 0, 'severity': 'high'},
                    {'skill': 'Paid Advertising', 'level': 'expert', 'required': 1, 'available': 0, 'severity': 'medium'},
                ],
                'capacity': Decimal('80.0'),
                'utilized': Decimal('72.0'),
            },
            bug_board: {
                'skills': BUG_TRACKING_SKILLS,
                'inventory': {
                    'Debugging': {'expert': 2, 'advanced': 1, 'intermediate': 0, 'beginner': 0},
                    'Root Cause Analysis': {'expert': 0, 'advanced': 2, 'intermediate': 1, 'beginner': 0},
                    'Testing': {'expert': 0, 'advanced': 2, 'intermediate': 2, 'beginner': 0},
                    'Performance Profiling': {'expert': 0, 'advanced': 0, 'intermediate': 2, 'beginner': 0},
                },
                'gaps': [
                    {'skill': 'Security Analysis', 'level': 'expert', 'required': 1, 'available': 0, 'severity': 'critical'},
                ],
                'capacity': Decimal('100.0'),
                'utilized': Decimal('85.0'),
            },
        }
        
        profiles_created = 0
        gaps_created = 0
        
        for board, config in skill_configs.items():
            if not board:
                continue
                
            # Delete existing skill data
            TeamSkillProfile.objects.filter(board=board).delete()
            SkillGap.objects.filter(board=board).delete()
            
            # Create team skill profile
            TeamSkillProfile.objects.create(
                board=board,
                skill_inventory=config['inventory'],
                total_capacity_hours=config['capacity'],
                utilized_capacity_hours=config['utilized'],
                last_analysis=now - timedelta(hours=random.randint(1, 24)),
            )
            profiles_created += 1
            
            # Create skill gaps
            board_tasks = [t for t in all_tasks if t.column.board == board]
            for gap_config in config['gaps']:
                gap = SkillGap.objects.create(
                    board=board,
                    skill_name=gap_config['skill'],
                    proficiency_level=gap_config['level'],
                    required_count=gap_config['required'],
                    available_count=gap_config['available'],
                    gap_count=gap_config['required'] - gap_config['available'],
                    severity=gap_config['severity'],
                    status='identified',
                    sprint_period_start=now.date() - timedelta(days=7),
                    sprint_period_end=now.date() + timedelta(days=7),
                    ai_recommendations=[
                        {
                            'type': 'training',
                            'details': f'Upskill existing team member in {gap_config["skill"]}',
                            'priority': 1,
                            'estimated_time': '2-4 weeks'
                        },
                        {
                            'type': 'hire',
                            'details': f'Consider hiring contractor with {gap_config["skill"]} expertise',
                            'priority': 2,
                            'estimated_time': '4-6 weeks'
                        },
                    ],
                    estimated_impact_hours=Decimal(str(random.randint(20, 80))),
                    confidence_score=Decimal(str(round(random.uniform(0.7, 0.95), 2))),
                )
                
                # Link affected tasks (tasks with matching skills)
                affected = [t for t in board_tasks if any(
                    s.get('name', '').lower() == gap_config['skill'].lower() 
                    for s in (t.required_skills or [])
                )][:5]
                for task in affected:
                    gap.affected_tasks.add(task)
                    
                gaps_created += 1
        
        self.stdout.write(f'   ✅ Created {profiles_created} skill profiles and {gaps_created} skill gaps')

    def create_scope_snapshots(self, software_board, marketing_board, bug_board, admin_user):
        """Create scope change snapshots for boards"""
        from kanban.models import ScopeChangeSnapshot, ScopeCreepAlert
        
        now = timezone.now()
        snapshots_created = 0
        alerts_created = 0
        
        for board in [software_board, marketing_board, bug_board]:
            if not board:
                continue
                
            # Delete existing snapshots
            ScopeChangeSnapshot.objects.filter(board=board).delete()
            ScopeCreepAlert.objects.filter(board=board).delete()
            
            tasks = Task.objects.filter(column__board=board)
            total_tasks = tasks.count()
            completed_tasks = tasks.filter(progress=100).count()
            in_progress_tasks = tasks.filter(progress__gt=0, progress__lt=100).count()
            
            # Overall complexity
            avg_complexity = tasks.aggregate(avg=models.Avg('complexity_score'))['avg'] or 5.0
            total_complexity = int(avg_complexity * total_tasks)
            
            # Calculate baseline values with different scope creep scenarios per board
            # Software Development: ~20% scope creep (moderate increase)
            # Marketing Campaign: ~12% scope creep (mild increase)  
            # Bug Tracking: ~35% scope creep (critical increase)
            if board == software_board:
                baseline_ratio = 0.833  # Results in ~20% scope creep
                complexity_ratio = 0.85
            elif board == marketing_board:
                baseline_ratio = 0.893  # Results in ~12% scope creep
                complexity_ratio = 0.90
            else:  # bug_board
                baseline_ratio = 0.741  # Results in ~35% scope creep
                complexity_ratio = 0.78
                
            baseline_tasks = int(total_tasks * baseline_ratio)
            baseline_complexity = int(total_complexity * complexity_ratio)
            
            # Create board-specific baseline notes
            if board == software_board:
                baseline_notes = 'Sprint 1 baseline - Development phase kickoff'
            elif board == marketing_board:
                baseline_notes = 'Campaign baseline - Initial planning complete'
            else:  # bug_board
                baseline_notes = 'Bug tracking baseline - Post-release monitoring'
            
            # Create baseline snapshot (from 2 weeks ago)
            baseline = ScopeChangeSnapshot.objects.create(
                board=board,
                total_tasks=baseline_tasks,
                total_complexity_points=baseline_complexity,
                avg_complexity=round(avg_complexity * 0.95, 2),
                high_priority_tasks=max(0, tasks.filter(priority='high').count() - 2),
                urgent_priority_tasks=max(0, tasks.filter(priority='urgent').count() - 1),
                todo_tasks=int(baseline_tasks * 0.5),
                in_progress_tasks=int(baseline_tasks * 0.25),
                completed_tasks=int(baseline_tasks * 0.1),
                is_baseline=True,
                baseline_snapshot=None,
                created_by=admin_user,
                snapshot_type='baseline',
                notes=baseline_notes,
            )
            # Backdate the snapshot
            ScopeChangeSnapshot.objects.filter(pk=baseline.pk).update(
                snapshot_date=now - timedelta(days=14)
            )
            snapshots_created += 1
            
            # IMPORTANT: Set the board's baseline fields so get_current_scope_status() works
            # This was missing and caused scope creep alert to show without baseline on dashboard
            board.baseline_task_count = baseline_tasks
            board.baseline_complexity_total = baseline_complexity
            board.baseline_set_date = now - timedelta(days=14)
            board.baseline_set_by = admin_user
            board.save(update_fields=['baseline_task_count', 'baseline_complexity_total', 
                                      'baseline_set_date', 'baseline_set_by'])
            
            # Calculate scope change percentage  
            scope_change_pct = round(((total_tasks - baseline_tasks) / baseline_tasks) * 100, 1) if baseline_tasks > 0 else 0
            complexity_change_pct = round(((total_complexity - baseline_complexity) / baseline_complexity) * 100, 1) if baseline_complexity > 0 else 0
            
            # Vary AI analysis based on scope change severity
            if scope_change_pct < 15:
                risk_level = 'low'
                trend = 'stable'
                recommendations = [
                    'Continue monitoring scope changes',
                    'Maintain regular backlog grooming sessions',
                    'Keep stakeholders informed of project status'
                ]
            elif scope_change_pct < 25:
                risk_level = 'medium'
                trend = 'increasing'
                recommendations = [
                    'Review new requirements carefully before adding',
                    'Consider deferring lower priority items',
                    'Communicate scope changes to stakeholders'
                ]
            else:
                risk_level = 'high'
                trend = 'rapidly_increasing'
                recommendations = [
                    'Immediate review of all added tasks required',
                    'Consider removing non-essential tasks from current sprint',
                    'Schedule urgent stakeholder meeting to discuss scope',
                    'Implement strict change control process'
                ]
            
            # Create current snapshot
            current = ScopeChangeSnapshot.objects.create(
                board=board,
                total_tasks=total_tasks,
                total_complexity_points=total_complexity,
                avg_complexity=round(avg_complexity, 2),
                high_priority_tasks=tasks.filter(priority='high').count(),
                urgent_priority_tasks=tasks.filter(priority='urgent').count(),
                todo_tasks=total_tasks - in_progress_tasks - completed_tasks,
                in_progress_tasks=in_progress_tasks,
                completed_tasks=completed_tasks,
                is_baseline=False,
                baseline_snapshot=baseline,
                created_by=admin_user,
                snapshot_type='scheduled',
                notes='Auto-generated snapshot',
                scope_change_percentage=scope_change_pct,
                complexity_change_percentage=complexity_change_pct,
                ai_analysis={
                    'trend': trend,
                    'risk_level': risk_level,
                    'tasks_added': total_tasks - baseline_tasks,
                    'complexity_added': total_complexity - baseline_complexity,
                    'recommendations': recommendations,
                    'confidence': round(random.uniform(0.75, 0.92), 2)
                }
            )
            snapshots_created += 1
            
            # Calculate tasks added for alerts
            tasks_added = total_tasks - baseline_tasks
            
            # Create scope creep alert with severity based on scope change percentage
            if scope_change_pct > 5:
                # Determine severity dynamically
                if scope_change_pct >= 30:
                    severity = 'critical'
                    predicted_delay = random.randint(5, 10)
                elif scope_change_pct >= 15:
                    severity = 'warning'
                    predicted_delay = random.randint(2, 5)
                else:
                    severity = 'info'
                    predicted_delay = None
                
                # Vary recommendations based on severity
                if severity == 'critical':
                    immediate_actions = ['URGENT: Review all newly added tasks', 'Schedule emergency stakeholder meeting']
                    short_term_actions = ['Remove non-critical tasks', 'Extend timeline or reduce scope']
                    prevention_actions = ['Implement mandatory change request process', 'Weekly scope reviews required']
                elif severity == 'warning':
                    immediate_actions = ['Review all newly added tasks', 'Validate priorities with product owner']
                    short_term_actions = ['Consider scope reduction', 'Discuss timeline impact with stakeholders']
                    prevention_actions = ['Implement stricter change control', 'Regular backlog grooming']
                else:
                    immediate_actions = ['Monitor scope trends', 'Document new additions']
                    short_term_actions = ['Continue regular planning', 'Keep stakeholders informed']
                    prevention_actions = ['Maintain current change process', 'Monthly scope reviews']
                
                ScopeCreepAlert.objects.create(
                    board=board,
                    snapshot=current,
                    severity=severity,
                    scope_increase_percentage=scope_change_pct,
                    complexity_increase_percentage=complexity_change_pct,
                    tasks_added=tasks_added,
                    predicted_delay_days=predicted_delay,
                    timeline_at_risk=scope_change_pct > 20,
                    recommendations={
                        'immediate': immediate_actions,
                        'short_term': short_term_actions,
                        'prevention': prevention_actions
                    },
                    ai_summary=f'Scope has increased by {scope_change_pct:.1f}% since baseline. '
                              f'{tasks_added} new tasks added.',
                )
                alerts_created += 1
        
        self.stdout.write(f'   ✅ Created {snapshots_created} scope snapshots and {alerts_created} alerts')
        self.stdout.write(f'   📊 Scope creep variation: Software Dev (~20%), Marketing (~12%), Bug Tracking (~35%)')

    def create_file_attachments(self, tasks, alex, sam, jordan):
        """Create simulated file attachment metadata for tasks"""
        # Skip file attachments since they require actual file uploads
        # which can't be simulated in demo data
        self.stdout.write('   ✅ File attachments skipped (requires actual file uploads)')

    def create_wiki_links(self, tasks, demo_org, alex):
        """Create wiki links for tasks (if wiki system exists)"""
        # This is a placeholder - implement if wiki system is available
        self.stdout.write('   ✅ Wiki links skipped (wiki system not configured)')
