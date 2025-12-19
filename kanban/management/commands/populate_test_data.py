import random
from datetime import datetime, timedelta
from django.core.management.base import BaseCommand
from django.contrib.auth.models import User
from django.utils import timezone
from accounts.models import Organization, UserProfile
from kanban.models import (
    Board, Column, TaskLabel, Task, Comment, TaskActivity,
    ResourceDemandForecast, TeamCapacityAlert, WorkloadDistributionRecommendation, Milestone
)
from kanban.priority_models import PriorityDecision
from kanban.budget_models import (
    ProjectBudget, TaskCost, TimeEntry, ProjectROI,
    BudgetRecommendation, CostPattern
)
from kanban.stakeholder_models import (
    ProjectStakeholder, StakeholderTaskInvolvement, 
    StakeholderEngagementRecord, EngagementMetrics, StakeholderTag
)
from kanban.retrospective_models import (
    ProjectRetrospective, LessonLearned, ImprovementMetric, 
    RetrospectiveActionItem
)
from messaging.models import ChatRoom, ChatMessage
from wiki.models import WikiCategory, WikiPage, WikiAttachment, MeetingNotes

class Command(BaseCommand):
    help = 'Populate the database with test data'

    def handle(self, *args, **options):
        self.stdout.write(self.style.NOTICE('Starting to populate database with test data...'))

        # Create test users if they don't exist
        self.create_users()
        
        # Create test organizations
        self.create_organizations()
        
        # Create test boards with columns, labels, tasks, and comments
        self.create_boards_and_content()
        
        # Create new feature demo data
        self.create_risk_management_demo_data()
        self.create_resource_management_demo_data()
        self.create_stakeholder_management_demo_data()
        self.create_task_dependency_demo_data()
        
        # Create budget and ROI demo data
        self.create_budget_roi_demo_data()
        
        # Create milestone demo data
        self.create_milestone_demo_data()
        
        # Create chat room demo data
        self.create_chat_rooms_demo_data()
        
        # Create wiki and knowledge base demo data
        self.create_wiki_demo_data()
        
        # Create meeting transcript demo data
        self.create_meeting_transcript_demo_data()
        
        # Create retrospective demo data
        self.create_retrospective_demo_data()
        
        # Create historical task data for predictive analytics
        self.create_historical_task_data()
        
        # Create priority decision history for intelligent priority suggestions
        self.create_priority_decision_history()
        
        # Fix Gantt chart data with dynamic dates relative to current date
        self.stdout.write(self.style.NOTICE('\nFixing Gantt chart demo data with dynamic dates...'))
        from django.core.management import call_command
        call_command('fix_gantt_demo_data')
        
        # Create scope baselines for all demo boards
        self.create_scope_baselines()
        
        # Create conflict scenarios for demo
        self.create_conflict_scenarios()
        
        # Refresh all demo data dates to be relative to current date
        # This ensures that even if demo data creation took time, all dates are current
        self.stdout.write(self.style.NOTICE('\nRefreshing all demo data dates to current date...'))
        call_command('refresh_demo_dates')
        
        self.stdout.write(self.style.SUCCESS('Successfully populated the database with all features!'))
        
        # Print login credentials for easy testing
        self.stdout.write(self.style.SUCCESS('\n' + '='*70))
        self.stdout.write(self.style.SUCCESS('LOGIN CREDENTIALS FOR TESTING'))
        self.stdout.write(self.style.SUCCESS('='*70))
        
        # Admin user
        self.stdout.write(self.style.SUCCESS('\n👤 ADMIN USER:'))
        self.stdout.write(self.style.SUCCESS('   Username: admin | Password: admin123'))
        
        # Dev Team Users
        self.stdout.write(self.style.SUCCESS('\n👥 DEV TEAM USERS:'))
        self.stdout.write(self.style.SUCCESS('   Username: john_doe | Password: JohnDoe@2024'))
        self.stdout.write(self.style.SUCCESS('   Username: jane_smith | Password: JaneSmith@2024'))
        self.stdout.write(self.style.SUCCESS('   Username: robert_johnson | Password: RobertJ@2024'))
        self.stdout.write(self.style.SUCCESS('   Username: alice_williams | Password: AliceW@2024'))
        self.stdout.write(self.style.SUCCESS('   Username: bob_martinez | Password: BobM@2024'))
        
        # Marketing Team Users
        self.stdout.write(self.style.SUCCESS('\n🎨 MARKETING TEAM USERS:'))
        self.stdout.write(self.style.SUCCESS('   Username: carol_anderson | Password: CarolA@2024'))
        self.stdout.write(self.style.SUCCESS('   Username: david_taylor | Password: DavidT@2024'))
        
        # Features created
        self.stdout.write(self.style.SUCCESS('\n' + '='*70))
        self.stdout.write(self.style.SUCCESS('FEATURES CREATED:'))
        self.stdout.write(self.style.SUCCESS('='*70))
        self.stdout.write(self.style.SUCCESS('✅ Kanban Boards - Multiple boards with tasks'))
        self.stdout.write(self.style.SUCCESS('✅ Risk Management - Task risk assessments'))
        self.stdout.write(self.style.SUCCESS('✅ Resource Management - Team workload forecasts'))
        self.stdout.write(self.style.SUCCESS('✅ Stakeholder Management - Stakeholder engagement'))
        self.stdout.write(self.style.SUCCESS('✅ Requirements Management - Task dependencies'))
        self.stdout.write(self.style.SUCCESS('✅ Milestones - Project milestones and deliverables'))
        self.stdout.write(self.style.SUCCESS('✅ Chat Rooms demo data created'))
        self.stdout.write(self.style.SUCCESS('✅ Retrospectives - AI-generated retrospectives with lessons learned'))
        self.stdout.write(self.style.SUCCESS('✅ Predictive Analytics - Historical task completion data'))
        self.stdout.write(self.style.SUCCESS('✅ Intelligent Priority Suggestions - Priority decision history'))
        self.stdout.write(self.style.SUCCESS('✅ Scope Tracking - Baseline snapshots for all boards'))
        self.stdout.write(self.style.SUCCESS('✅ Budget & ROI Tracking - Complete financial analysis with AI'))
        self.stdout.write(self.style.SUCCESS('✅ Conflict Detection - Realistic conflict scenarios created'))
        self.stdout.write(self.style.SUCCESS('='*70 + '\n'))

    def create_users(self):
        self.stdout.write('Creating users...')
        
        # Create admin user if it doesn't exist
        if not User.objects.filter(username='admin').exists():
            admin_user = User.objects.create_superuser(
                username='admin',
                email='admin@taskflow.com',
                password='admin123',
                first_name='Admin',
                last_name='User'
            )
            self.stdout.write(f'Created admin user: {admin_user.username}')
        else:
            admin_user = User.objects.get(username='admin')
            self.stdout.write('Admin user already exists')
        
        # Create regular users - Development Team
        test_users = [
            {
                'username': 'john_doe',
                'email': 'john.doe@devteam.com',
                'password': 'JohnDoe@2024',
                'first_name': 'John',
                'last_name': 'Doe',
                'org': 'dev'
            },
            {
                'username': 'jane_smith',
                'email': 'jane.smith@devteam.com',
                'password': 'JaneSmith@2024',
                'first_name': 'Jane',
                'last_name': 'Smith',
                'org': 'dev'
            },
            {
                'username': 'robert_johnson',
                'email': 'robert.johnson@devteam.com',
                'password': 'RobertJ@2024',
                'first_name': 'Robert',
                'last_name': 'Johnson',
                'org': 'dev'
            },
            {
                'username': 'alice_williams',
                'email': 'alice.williams@devteam.com',
                'password': 'AliceW@2024',
                'first_name': 'Alice',
                'last_name': 'Williams',
                'org': 'dev'
            },
            {
                'username': 'bob_martinez',
                'email': 'bob.martinez@devteam.com',
                'password': 'BobM@2024',
                'first_name': 'Bob',
                'last_name': 'Martinez',
                'org': 'dev'
            },
            # Marketing Team
            {
                'username': 'carol_anderson',
                'email': 'carol.anderson@marketingteam.com',
                'password': 'CarolA@2024',
                'first_name': 'Carol',
                'last_name': 'Anderson',
                'org': 'marketing'
            },
            {
                'username': 'david_taylor',
                'email': 'david.taylor@marketingteam.com',
                'password': 'DavidT@2024',
                'first_name': 'David',
                'last_name': 'Taylor',
                'org': 'marketing'
            }
        ]
        
        self.users = {}
        for user_data in test_users:
            username = user_data['username']
            if not User.objects.filter(username=username).exists():
                user = User.objects.create_user(
                    username=username,
                    email=user_data['email'],
                    password=user_data['password'],
                    first_name=user_data['first_name'],
                    last_name=user_data['last_name']
                )
                self.stdout.write(f'Created user: {user.username} ({user.get_full_name()})')
            else:
                user = User.objects.get(username=username)
                self.stdout.write(f'User {user.username} already exists')
            
            self.users[username] = user
        
        # Add admin to users dictionary
        self.users['admin'] = admin_user

    def create_organizations(self):
        self.stdout.write('Creating organizations...')
        
        # Create dev team organization
        if not Organization.objects.filter(name='Dev Team').exists():
            dev_org = Organization.objects.create(
                name='Dev Team',
                domain='devteam.com',
                created_by=self.users['admin']
            )
            self.stdout.write(f'Created organization: {dev_org.name}')
        else:
            dev_org = Organization.objects.get(name='Dev Team')
            self.stdout.write(f'Organization {dev_org.name} already exists')
        
        # Create second organization
        if not Organization.objects.filter(name='Marketing Team').exists():
            marketing_org = Organization.objects.create(
                name='Marketing Team',
                domain='marketingteam.com',
                created_by=self.users['admin']
            )
            self.stdout.write(f'Created organization: {marketing_org.name}')
        else:
            marketing_org = Organization.objects.get(name='Marketing Team')
            self.stdout.write(f'Organization {marketing_org.name} already exists')
        
        # Store organizations
        self.organizations = {
            'dev': dev_org,
            'marketing': marketing_org
        }
        
        # Create profiles for users if they don't exist
        for username, user in self.users.items():
            if not hasattr(user, 'profile'):
                # Assign users to organizations based on their domain
                if username in ['admin', 'john_doe', 'jane_smith', 'robert_johnson', 'alice_williams', 'bob_martinez']:
                    org = dev_org
                else:
                    org = marketing_org
                
                is_admin = username in ['admin', 'jane_smith', 'carol_anderson']
                
                profile = UserProfile.objects.create(
                    user=user,
                    organization=org,
                    is_admin=is_admin
                )
                self.stdout.write(f'Created profile for: {user.username} in {org.name}')
            else:
                self.stdout.write(f'Profile for {user.username} already exists')

    def create_boards_and_content(self):
        self.stdout.write('Creating boards, columns, labels, and tasks...')
        
        # Create boards for Dev Team
        self.create_software_project_board()
        self.create_bug_tracking_board()
        
        # Create board for Marketing Team
        self.create_marketing_campaign_board()

    def create_software_project_board(self):
        # Create Software Project board if it doesn't exist
        if not Board.objects.filter(name='Software Project').exists():
            board = Board.objects.create(
                name='Software Project',
                description='Main product development board with Lean Six Sigma features',
                organization=self.organizations['dev'],
                created_by=self.users['admin']
            )
            self.stdout.write(f'Created board: {board.name}')
            
            # Add all dev team members including admin
            board.members.add(
                self.users['admin'],
                self.users['john_doe'],
                self.users['jane_smith'],
                self.users['robert_johnson'],
                self.users['alice_williams'],
                self.users['bob_martinez']
            )
            
            # Create columns
            columns = [
                {'name': 'Backlog', 'position': 0},
                {'name': 'To Do', 'position': 1},
                {'name': 'In Progress', 'position': 2},
                {'name': 'Review', 'position': 3},
                {'name': 'Done', 'position': 4}
            ]
            
            board_columns = {}
            for col_data in columns:
                column = Column.objects.create(
                    name=col_data['name'],
                    board=board,
                    position=col_data['position']
                )
                board_columns[col_data['name']] = column
                self.stdout.write(f'Created column: {column.name}')
            
            # Create Lean Six Sigma labels
            lean_labels = [
                {'name': 'Value-Added', 'color': '#28a745', 'category': 'lean'},
                {'name': 'Necessary NVA', 'color': '#ffc107', 'category': 'lean'},
                {'name': 'Waste/Eliminate', 'color': '#dc3545', 'category': 'lean'}
            ]
            
            board_lean_labels = {}
            for label_data in lean_labels:
                label = TaskLabel.objects.create(
                    name=label_data['name'],
                    color=label_data['color'],
                    board=board,
                    category=label_data['category']
                )
                board_lean_labels[label_data['name']] = label
                self.stdout.write(f'Created label: {label.name}')
            
            # Create regular labels
            regular_labels = [
                {'name': 'Front-end', 'color': '#17a2b8'},
                {'name': 'Back-end', 'color': '#6f42c1'},
                {'name': 'Bug', 'color': '#dc3545'},
                {'name': 'Feature', 'color': '#28a745'},
                {'name': 'Documentation', 'color': '#6c757d'}
            ]
            
            board_regular_labels = {}
            for label_data in regular_labels:
                label = TaskLabel.objects.create(
                    name=label_data['name'],
                    color=label_data['color'],
                    board=board,
                    category='regular'
                )
                board_regular_labels[label_data['name']] = label
                self.stdout.write(f'Created label: {label.name}')
            
            # Create tasks for backlog
            backlog_tasks = [
                {
                    'title': 'Implement user authentication',
                    'description': 'Add login, registration, and password reset functionality',
                    'priority': 'high',
                    'due_date': timezone.now() + timedelta(days=7),
                    'progress': 0,
                    'created_by': self.users['admin'],
                    'assigned_to': self.users['john_doe'],
                    'labels': [board_regular_labels['Back-end'], board_lean_labels['Value-Added']]
                },
                {
                    'title': 'Design database schema',
                    'description': 'Create ER diagrams and plan the database structure',
                    'priority': 'high',
                    'due_date': timezone.now() + timedelta(days=5),
                    'progress': 0,
                    'created_by': self.users['admin'],
                    'assigned_to': self.users['robert_johnson'],
                    'labels': [board_regular_labels['Back-end'], board_lean_labels['Value-Added']]
                },
                {
                    'title': 'Setup CI/CD pipeline',
                    'description': 'Configure GitHub Actions for automated testing and deployment',
                    'priority': 'medium',
                    'due_date': timezone.now() + timedelta(days=10),
                    'progress': 0,
                    'created_by': self.users['robert_johnson'],
                    'assigned_to': None,
                    'labels': [board_lean_labels['Necessary NVA']]
                }
            ]
            
            self.create_tasks(backlog_tasks, board_columns['Backlog'])
            
            # Create tasks for To Do
            todo_tasks = [
                {
                    'title': 'Create component library',
                    'description': 'Develop reusable UI components for the application',
                    'priority': 'medium',
                    'due_date': timezone.now() + timedelta(days=8),
                    'progress': 0,
                    'created_by': self.users['admin'],
                    'assigned_to': self.users['john_doe'],
                    'labels': [board_regular_labels['Front-end'], board_lean_labels['Value-Added']]
                },
                {
                    'title': 'Write documentation for API endpoints',
                    'description': 'Document all API endpoints with examples and response formats',
                    'priority': 'low',
                    'due_date': timezone.now() + timedelta(days=15),
                    'progress': 0,
                    'created_by': self.users['robert_johnson'],
                    'assigned_to': self.users['robert_johnson'],
                    'labels': [board_regular_labels['Documentation'], board_lean_labels['Necessary NVA']]
                }
            ]
            
            self.create_tasks(todo_tasks, board_columns['To Do'])
            
            # Create tasks for In Progress
            in_progress_tasks = [
                {
                    'title': 'Implement dashboard layout',
                    'description': 'Create the main dashboard layout with sidebar and main content area',
                    'priority': 'high',
                    'due_date': timezone.now() + timedelta(days=3),
                    'progress': 30,
                    'created_by': self.users['john_doe'],
                    'assigned_to': self.users['john_doe'],
                    'labels': [board_regular_labels['Front-end'], board_lean_labels['Value-Added']]
                },
                {
                    'title': 'Setup authentication middleware',
                    'description': 'Create middleware for JWT token validation and user authentication',
                    'priority': 'urgent',
                    'due_date': timezone.now() + timedelta(days=2),
                    'progress': 65,
                    'created_by': self.users['admin'],
                    'assigned_to': self.users['robert_johnson'],
                    'labels': [board_regular_labels['Back-end'], board_lean_labels['Value-Added']]
                }
            ]
            
            self.create_tasks(in_progress_tasks, board_columns['In Progress'])
            
            # Create tasks for Review
            review_tasks = [
                {
                    'title': 'Review homepage design',
                    'description': 'Review and provide feedback on the new homepage design',
                    'priority': 'medium',
                    'due_date': timezone.now() + timedelta(days=1),
                    'progress': 90,
                    'created_by': self.users['john_doe'],
                    'assigned_to': self.users['admin'],
                    'labels': [board_regular_labels['Front-end'], board_lean_labels['Necessary NVA']]
                }
            ]
            
            self.create_tasks(review_tasks, board_columns['Review'])
            
            # Create tasks for Done
            done_tasks = [
                {
                    'title': 'Setup project repository',
                    'description': 'Create GitHub repository and initial project structure',
                    'priority': 'high',
                    'due_date': timezone.now() - timedelta(days=5),
                    'progress': 100,
                    'created_by': self.users['admin'],
                    'assigned_to': self.users['admin'],
                    'labels': [board_lean_labels['Necessary NVA']]
                },
                {
                    'title': 'Create UI mockups',
                    'description': 'Design UI mockups for the main application screens',
                    'priority': 'medium',
                    'due_date': timezone.now() - timedelta(days=8),
                    'progress': 100,
                    'created_by': self.users['john_doe'],
                    'assigned_to': self.users['john_doe'],
                    'labels': [board_regular_labels['Front-end'], board_lean_labels['Value-Added']]
                },
                {
                    'title': 'Remove legacy code',
                    'description': 'Remove deprecated functions and clean up the codebase',
                    'priority': 'low',
                    'due_date': timezone.now() - timedelta(days=2),
                    'progress': 100,
                    'created_by': self.users['robert_johnson'],
                    'assigned_to': self.users['robert_johnson'],
                    'labels': [board_lean_labels['Waste/Eliminate']]
                }
            ]
            
            self.create_tasks(done_tasks, board_columns['Done'])
            
        else:
            self.stdout.write('Software Project board already exists')

    def create_bug_tracking_board(self):
        # Create Bug Tracking board if it doesn't exist
        if not Board.objects.filter(name='Bug Tracking').exists():
            board = Board.objects.create(
                name='Bug Tracking',
                description='Track and manage bugs and issues',
                organization=self.organizations['dev'],
                created_by=self.users['robert_johnson']
            )
            self.stdout.write(f'Created board: {board.name}')
            
            # Add members
            board.members.add(
                self.users['admin'],
                self.users['john_doe'],
                self.users['jane_smith'],
                self.users['alice_williams']
            )
            
            # Create columns
            columns = [
                {'name': 'New', 'position': 0},
                {'name': 'Investigating', 'position': 1},
                {'name': 'In Progress', 'position': 2},
                {'name': 'Testing', 'position': 3},
                {'name': 'Closed', 'position': 4}
            ]
            
            board_columns = {}
            for col_data in columns:
                column = Column.objects.create(
                    name=col_data['name'],
                    board=board,
                    position=col_data['position']
                )
                board_columns[col_data['name']] = column
                self.stdout.write(f'Created column: {column.name}')
            
            # Create Lean Six Sigma labels
            lean_labels = [
                {'name': 'Value-Added', 'color': '#28a745', 'category': 'lean'},
                {'name': 'Necessary NVA', 'color': '#ffc107', 'category': 'lean'},
                {'name': 'Waste/Eliminate', 'color': '#dc3545', 'category': 'lean'}
            ]
            
            board_lean_labels = {}
            for label_data in lean_labels:
                label = TaskLabel.objects.create(
                    name=label_data['name'],
                    color=label_data['color'],
                    board=board,
                    category=label_data['category']
                )
                board_lean_labels[label_data['name']] = label
                self.stdout.write(f'Created label: {label.name}')
            
            # Create regular labels
            regular_labels = [
                {'name': 'Critical', 'color': '#dc3545'},
                {'name': 'Major', 'color': '#fd7e14'},
                {'name': 'Minor', 'color': '#ffc107'},
                {'name': 'UI/UX', 'color': '#20c997'},
                {'name': 'Backend', 'color': '#6610f2'},
                {'name': 'Performance', 'color': '#17a2b8'}
            ]
            
            board_regular_labels = {}
            for label_data in regular_labels:
                label = TaskLabel.objects.create(
                    name=label_data['name'],
                    color=label_data['color'],
                    board=board,
                    category='regular'
                )
                board_regular_labels[label_data['name']] = label
                self.stdout.write(f'Created label: {label.name}')
            
            # Create tasks for New
            new_bugs = [
                {
                    'title': 'Login page not working on Safari',
                    'description': 'Users report they cannot login when using Safari browser',
                    'priority': 'high',
                    'due_date': timezone.now() + timedelta(days=2),
                    'progress': 0,
                    'created_by': self.users['john_doe'],
                    'assigned_to': None,
                    'labels': [board_regular_labels['Critical'], board_lean_labels['Value-Added']]
                },
                {
                    'title': 'Slow response time on search feature',
                    'description': 'Search feature takes more than 5 seconds to return results',
                    'priority': 'medium',
                    'due_date': timezone.now() + timedelta(days=5),
                    'progress': 0,
                    'created_by': self.users['robert_johnson'],
                    'assigned_to': None,
                    'labels': [board_regular_labels['Performance'], board_lean_labels['Value-Added']]
                }
            ]
            
            self.create_tasks(new_bugs, board_columns['New'])
            
            # Create tasks for Investigating
            investigating_bugs = [
                {
                    'title': 'Inconsistent data in reports',
                    'description': 'Reports sometimes show different totals for the same data',
                    'priority': 'high',
                    'due_date': timezone.now() + timedelta(days=3),
                    'progress': 20,
                    'created_by': self.users['admin'],
                    'assigned_to': self.users['robert_johnson'],
                    'labels': [board_regular_labels['Major'], board_regular_labels['Backend'], board_lean_labels['Value-Added']]
                }
            ]
            
            self.create_tasks(investigating_bugs, board_columns['Investigating'])
            
            # Create tasks for In Progress
            in_progress_bugs = [
                {
                    'title': 'Button alignment issue on mobile',
                    'description': 'Save and Cancel buttons are misaligned on mobile view',
                    'priority': 'low',
                    'due_date': timezone.now() + timedelta(days=7),
                    'progress': 50,
                    'created_by': self.users['john_doe'],
                    'assigned_to': self.users['john_doe'],
                    'labels': [board_regular_labels['Minor'], board_regular_labels['UI/UX'], board_lean_labels['Necessary NVA']]
                }
            ]
            
            self.create_tasks(in_progress_bugs, board_columns['In Progress'])
            
            # Create tasks for Testing
            testing_bugs = [
                {
                    'title': 'Fixed pagination on user list',
                    'description': 'Fixed bug where pagination showed incorrect number of pages',
                    'priority': 'medium',
                    'due_date': timezone.now() + timedelta(days=1),
                    'progress': 90,
                    'created_by': self.users['robert_johnson'],
                    'assigned_to': self.users['admin'],
                    'labels': [board_regular_labels['Minor'], board_lean_labels['Value-Added']]
                }
            ]
            
            self.create_tasks(testing_bugs, board_columns['Testing'])
            
            # Create tasks for Closed
            closed_bugs = [
                {
                    'title': 'Error 500 when uploading large files',
                    'description': 'Server returns 500 error when uploading files larger than 10MB',
                    'priority': 'urgent',
                    'due_date': timezone.now() - timedelta(days=3),
                    'progress': 100,
                    'created_by': self.users['admin'],
                    'assigned_to': self.users['robert_johnson'],
                    'labels': [board_regular_labels['Critical'], board_regular_labels['Backend'], board_lean_labels['Value-Added']]
                },
                {
                    'title': 'Typo on welcome screen',
                    'description': 'The welcome message has a spelling mistake',
                    'priority': 'low',
                    'due_date': timezone.now() - timedelta(days=5),
                    'progress': 100,
                    'created_by': self.users['john_doe'],
                    'assigned_to': self.users['john_doe'],
                    'labels': [board_regular_labels['Minor'], board_lean_labels['Waste/Eliminate']]
                }
            ]
            
            self.create_tasks(closed_bugs, board_columns['Closed'])
            
        else:
            self.stdout.write('Bug Tracking board already exists')

    def create_marketing_campaign_board(self):
        # Create Marketing Campaign board if it doesn't exist
        if not Board.objects.filter(name='Marketing Campaign').exists():
            board = Board.objects.create(
                name='Marketing Campaign',
                description='Plan and track marketing campaigns',
                organization=self.organizations['marketing'],
                created_by=self.users['carol_anderson']
            )
            self.stdout.write(f'Created board: {board.name}')
            
            # Add members (marketing team + admin for oversight)
            board.members.add(
                self.users['admin'],
                self.users['carol_anderson'],
                self.users['david_taylor']
            )
            
            # Create columns
            columns = [
                {'name': 'Ideas', 'position': 0},
                {'name': 'Planning', 'position': 1},
                {'name': 'In Progress', 'position': 2},
                {'name': 'Review', 'position': 3},
                {'name': 'Completed', 'position': 4}
            ]
            
            board_columns = {}
            for col_data in columns:
                column = Column.objects.create(
                    name=col_data['name'],
                    board=board,
                    position=col_data['position']
                )
                board_columns[col_data['name']] = column
                self.stdout.write(f'Created column: {column.name}')
            
            # Create Lean Six Sigma labels
            lean_labels = [
                {'name': 'Value-Added', 'color': '#28a745', 'category': 'lean'},
                {'name': 'Necessary NVA', 'color': '#ffc107', 'category': 'lean'},
                {'name': 'Waste/Eliminate', 'color': '#dc3545', 'category': 'lean'}
            ]
            
            board_lean_labels = {}
            for label_data in lean_labels:
                label = TaskLabel.objects.create(
                    name=label_data['name'],
                    color=label_data['color'],
                    board=board,
                    category=label_data['category']
                )
                board_lean_labels[label_data['name']] = label
                self.stdout.write(f'Created label: {label.name}')
            
            # Create regular labels
            regular_labels = [
                {'name': 'Social Media', 'color': '#007bff'},
                {'name': 'Email', 'color': '#6f42c1'},
                {'name': 'Content', 'color': '#fd7e14'},
                {'name': 'Design', 'color': '#20c997'},
                {'name': 'Analytics', 'color': '#17a2b8'}
            ]
            
            board_regular_labels = {}
            for label_data in regular_labels:
                label = TaskLabel.objects.create(
                    name=label_data['name'],
                    color=label_data['color'],
                    board=board,
                    category='regular'
                )
                board_regular_labels[label_data['name']] = label
                self.stdout.write(f'Created label: {label.name}')
            
            # Create tasks for Ideas
            ideas_tasks = [
                {
                    'title': 'Holiday social campaign concept',
                    'description': 'Brainstorm ideas for the upcoming holiday social media campaign',
                    'priority': 'medium',
                    'due_date': timezone.now() + timedelta(days=14),
                    'progress': 0,
                    'created_by': self.users['carol_anderson'],
                    'assigned_to': self.users['carol_anderson'],
                    'labels': [board_regular_labels['Social Media'], board_lean_labels['Value-Added']]
                },
                {
                    'title': 'Video content strategy',
                    'description': 'Explore video content ideas for product demonstrations',
                    'priority': 'low',
                    'due_date': timezone.now() + timedelta(days=21),
                    'progress': 0,
                    'created_by': self.users['david_taylor'],
                    'assigned_to': self.users['david_taylor'],
                    'labels': [board_regular_labels['Content'], board_lean_labels['Value-Added']]
                }
            ]
            self.create_tasks(ideas_tasks, board_columns['Ideas'])
            
            # Create tasks for Planning
            planning_tasks = [
                {
                    'title': 'Q3 Email newsletter schedule',
                    'description': 'Create content calendar for Q3 email newsletters',
                    'priority': 'high',
                    'due_date': timezone.now() + timedelta(days=5),
                    'progress': 15,
                    'created_by': self.users['carol_anderson'],
                    'assigned_to': self.users['carol_anderson'],
                    'labels': [board_regular_labels['Email'], board_lean_labels['Value-Added']]
                }
            ]
            self.create_tasks(planning_tasks, board_columns['Planning'])
            
            # Create tasks for In Progress
            in_progress_tasks = [
                {
                    'title': 'Website redesign for Q4 launch',
                    'description': 'Update website design to highlight new features',
                    'priority': 'high',
                    'due_date': timezone.now() + timedelta(days=10),
                    'progress': 40,
                    'created_by': self.users['carol_anderson'],
                    'assigned_to': self.users['david_taylor'],
                    'labels': [board_regular_labels['Design'], board_lean_labels['Value-Added']]
                },
                {
                    'title': 'Monthly performance report',
                    'description': 'Compile social media and email campaign metrics for the month',
                    'priority': 'medium',
                    'due_date': timezone.now() + timedelta(days=3),
                    'progress': 60,
                    'created_by': self.users['david_taylor'],
                    'assigned_to': self.users['carol_anderson'],
                    'labels': [board_regular_labels['Analytics'], board_lean_labels['Necessary NVA']]
                }
            ]
            self.create_tasks(in_progress_tasks, board_columns['In Progress'])
            
            # Create tasks for Review
            review_tasks = [
                {
                    'title': 'New product announcement email',
                    'description': 'Email campaign for the upcoming product launch',
                    'priority': 'urgent',
                    'due_date': timezone.now() + timedelta(days=1),
                    'progress': 95,
                    'created_by': self.users['carol_anderson'],
                    'assigned_to': self.users['david_taylor'],
                    'labels': [board_regular_labels['Email'], board_lean_labels['Value-Added']]
                }
            ]
            self.create_tasks(review_tasks, board_columns['Review'])
            
            # Create tasks for Completed
            completed_tasks = [
                {
                    'title': 'Summer campaign graphics',
                    'description': 'Create social media graphics for summer campaign',
                    'priority': 'high',
                    'due_date': timezone.now() - timedelta(days=7),
                    'progress': 100,
                    'created_by': self.users['carol_anderson'],
                    'assigned_to': self.users['carol_anderson'],
                    'labels': [board_regular_labels['Design'], board_regular_labels['Social Media'], board_lean_labels['Value-Added']]
                },
                {
                    'title': 'Competitor analysis report',
                    'description': 'Research and document marketing strategies of main competitors',
                    'priority': 'medium',
                    'due_date': timezone.now() - timedelta(days=10),
                    'progress': 100,
                    'created_by': self.users['david_taylor'],
                    'assigned_to': self.users['david_taylor'],
                    'labels': [board_regular_labels['Analytics'], board_lean_labels['Value-Added']]
                },
                {
                    'title': 'Remove outdated content',
                    'description': 'Archive or remove outdated content from the website',
                    'priority': 'low',
                    'due_date': timezone.now() - timedelta(days=3),
                    'progress': 100,
                    'created_by': self.users['carol_anderson'],
                    'assigned_to': self.users['carol_anderson'],
                    'labels': [board_regular_labels['Content'], board_lean_labels['Waste/Eliminate']]
                }
            ]
            self.create_tasks(completed_tasks, board_columns['Completed'])
            
        else:
            self.stdout.write('Marketing Campaign board already exists')

    def create_tasks(self, tasks_data, column):
        # Helper function to create tasks with comments and activity
        position = 0
        for task_data in tasks_data:
            task = Task.objects.create(
                title=task_data['title'],
                description=task_data['description'],
                column=column,
                position=position,
                due_date=task_data['due_date'],
                assigned_to=task_data['assigned_to'],
                created_by=task_data['created_by'],
                priority=task_data['priority'],
                progress=task_data['progress']
            )
            position += 1
            self.stdout.write(f'Created task: {task.title}')
            
            # Add labels
            if 'labels' in task_data:
                for label in task_data['labels']:
                    task.labels.add(label)
            
            # Create task activity
            TaskActivity.objects.create(
                task=task,
                user=task_data['created_by'],
                activity_type='created',
                description=f"Created task '{task.title}'"
            )
            
            # If assigned, create assignment activity
            if task_data['assigned_to']:
                TaskActivity.objects.create(
                    task=task,
                    user=task_data['created_by'],
                    activity_type='assigned',
                    description=f"Assigned to {task_data['assigned_to'].get_full_name() or task_data['assigned_to'].username}"
                )
            
            # Add some comments to random tasks (around 30% chance)
            if random.random() < 0.3:
                Comment.objects.create(
                    task=task,
                    user=task_data['created_by'],
                    content=f"Let's make sure we prioritize this correctly."
                )
                
                # Record comment activity
                TaskActivity.objects.create(
                    task=task,
                    user=task_data['created_by'],
                    activity_type='commented',
                    description=f"{task_data['created_by'].get_full_name() or task_data['created_by'].username} commented on this task"
                )
                
            if random.random() < 0.2 and task_data['assigned_to']:
                Comment.objects.create(
                    task=task,
                    user=task_data['assigned_to'],
                    content=f"I'll work on this as soon as possible."
                )
                
                # Record comment activity
                TaskActivity.objects.create(
                    task=task,
                    user=task_data['assigned_to'],
                    activity_type='commented',
                    description=f"{task_data['assigned_to'].get_full_name() or task_data['assigned_to'].username} commented on this task"
                )

    def create_risk_management_demo_data(self):
        """Create demo data for risk management features"""
        self.stdout.write(self.style.NOTICE('Creating Risk Management demo data...'))
        
        # Get all tasks and assign risk assessments to some of them
        tasks = Task.objects.all()[:15]  # Get first 15 tasks
        
        for task in tasks:
            if random.random() < 0.7:  # 70% of tasks get risk data
                # Risk assessment data
                task.risk_likelihood = random.randint(1, 3)
                task.risk_impact = random.randint(1, 3)
                task.risk_score = task.risk_likelihood * task.risk_impact
                
                # Determine risk level
                if task.risk_score <= 2:
                    task.risk_level = 'low'
                elif task.risk_score <= 4:
                    task.risk_level = 'medium'
                elif task.risk_score <= 6:
                    task.risk_level = 'high'
                else:
                    task.risk_level = 'critical'
                
                # Risk indicators
                task.risk_indicators = [
                    'Monitor task progress weekly',
                    'Track team member availability',
                    'Check for dependencies',
                    'Verify resource allocation'
                ]
                
                # Mitigation suggestions
                task.mitigation_suggestions = [
                    {
                        'strategy': 'Mitigate',
                        'description': 'Allocate additional resources to reduce timeline',
                        'timeline': '2 weeks',
                        'effectiveness': '75%'
                    },
                    {
                        'strategy': 'Mitigate',
                        'description': 'Conduct technical review to identify potential issues early',
                        'timeline': '1 week',
                        'effectiveness': '60%'
                    }
                ]
                
                # Risk analysis details
                task.risk_analysis = {
                    'factors': ['Complexity', 'Team capacity', 'Timeline pressure', 'Dependencies'],
                    'assessment': 'Task has moderate risk factors',
                    'reasoning': f'Priority {task.priority} with {len(task.labels.all())} labels'
                }
                
                task.last_risk_assessment = timezone.now()
                task.save()
                self.stdout.write(f'  Added risk assessment to: {task.title}')
        
        self.stdout.write(self.style.SUCCESS('✅ Risk Management demo data created'))

    def create_resource_management_demo_data(self):
        """Create demo data for resource management features"""
        self.stdout.write(self.style.NOTICE('Creating Resource Management demo data...'))
        
        # Get boards for resource forecasting
        for board in self.organizations['dev'].boards.all():
            # Create forecasts for each team member
            for user in [self.users['john_doe'], self.users['robert_johnson']]:
                # Create a forecast for the next 4 weeks
                forecast = ResourceDemandForecast.objects.create(
                    board=board,
                    resource_user=user,
                    resource_role=user.get_full_name() or user.username,
                    period_start=timezone.now().date(),
                    period_end=(timezone.now() + timedelta(days=28)).date(),
                    predicted_workload_hours=random.uniform(120, 160),
                    available_capacity_hours=160.0,
                    confidence_score=round(random.uniform(0.7, 0.95), 2)
                )
                self.stdout.write(f'  Created forecast for {user.username}')
                
                # Create capacity alerts if overloaded
                if forecast.is_overloaded:
                    alert_level = 'critical' if forecast.utilization_percentage > 120 else 'warning'
                    TeamCapacityAlert.objects.create(
                        board=board,
                        forecast=forecast,
                        alert_type='individual',
                        alert_level=alert_level,
                        resource_user=user,
                        message=f'{user.get_full_name()} is at {forecast.utilization_percentage:.0f}% capacity',
                        workload_percentage=int(forecast.utilization_percentage),
                        status='active'
                    )
                    self.stdout.write(f'  Created capacity alert for {user.username}')
            
            # Create workload distribution recommendations
            recommendation = WorkloadDistributionRecommendation.objects.create(
                board=board,
                recommendation_type='distribute',
                priority=random.randint(5, 10),
                title='Optimize Task Distribution',
                description='Consider distributing high-priority tasks across multiple team members to balance workload',
                status='pending',
                expected_capacity_savings_hours=random.uniform(10, 30),
                confidence_score=round(random.uniform(0.6, 0.9), 2)
            )
            self.stdout.write(f'  Created distribution recommendation')
        
        self.stdout.write(self.style.SUCCESS('✅ Resource Management demo data created'))

    def create_stakeholder_management_demo_data(self):
        """Create demo data for stakeholder engagement tracking"""
        self.stdout.write(self.style.NOTICE('Creating Stakeholder Management demo data...'))
        
        # Get dev team board
        board = self.organizations['dev'].boards.first()
        if not board:
            return
        
        # Create stakeholders
        stakeholder_data = [
            {
                'name': 'Sarah Mitchell',
                'role': 'Product Manager',
                'organization': 'Product Team',
                'email': 'sarah.mitchell@example.com',
                'phone': '+1-555-0101',
                'influence_level': 'high',
                'interest_level': 'high',
                'current_engagement': 'collaborate',
                'desired_engagement': 'empower'
            },
            {
                'name': 'Michael Chen',
                'role': 'Tech Lead',
                'organization': 'Dev Team',
                'email': 'michael.chen@example.com',
                'phone': '+1-555-0102',
                'influence_level': 'high',
                'interest_level': 'high',
                'current_engagement': 'involve',
                'desired_engagement': 'collaborate'
            },
            {
                'name': 'Emily Rodriguez',
                'role': 'QA Lead',
                'organization': 'QA Team',
                'email': 'emily.rodriguez@example.com',
                'phone': '+1-555-0103',
                'influence_level': 'medium',
                'interest_level': 'high',
                'current_engagement': 'consult',
                'desired_engagement': 'involve'
            },
            {
                'name': 'David Park',
                'role': 'DevOps Engineer',
                'organization': 'Infrastructure',
                'email': 'david.park@example.com',
                'phone': '+1-555-0104',
                'influence_level': 'medium',
                'interest_level': 'medium',
                'current_engagement': 'inform',
                'desired_engagement': 'involve'
            },
            {
                'name': 'Lisa Thompson',
                'role': 'UX Designer',
                'organization': 'Design Team',
                'email': 'lisa.thompson@example.com',
                'phone': '+1-555-0105',
                'influence_level': 'medium',
                'interest_level': 'high',
                'current_engagement': 'involve',
                'desired_engagement': 'collaborate'
            }
        ]
        
        stakeholders = []
        for data in stakeholder_data:
            stakeholder, created = ProjectStakeholder.objects.get_or_create(
                board=board,
                email=data['email'],
                defaults={
                    'name': data['name'],
                    'role': data['role'],
                    'organization': data['organization'],
                    'phone': data['phone'],
                    'influence_level': data['influence_level'],
                    'interest_level': data['interest_level'],
                    'current_engagement': data['current_engagement'],
                    'desired_engagement': data['desired_engagement'],
                    'created_by': self.users['admin'],
                    'is_active': True
                }
            )
            stakeholders.append(stakeholder)
            if created:
                self.stdout.write(f'  Created stakeholder: {stakeholder.name}')
        
        # Create stakeholder tags
        tags_data = ['Key Stakeholder', 'Executive', 'Technical', 'Quality Focus', 'Design Focus']
        tags = []
        for tag_name in tags_data:
            tag, created = StakeholderTag.objects.get_or_create(
                board=board,
                name=tag_name,
                defaults={
                    'color': f'#{random.randint(0, 0xFFFFFF):06x}',
                    'created_by': self.users['admin']
                }
            )
            tags.append(tag)
            if created:
                self.stdout.write(f'  Created tag: {tag_name}')
        
        # Assign tags to stakeholders randomly
        for stakeholder in stakeholders:
            for _ in range(random.randint(1, 3)):
                tag = random.choice(tags)
                # Using the through model
                from kanban.stakeholder_models import ProjectStakeholderTag
                ProjectStakeholderTag.objects.get_or_create(
                    stakeholder=stakeholder,
                    tag=tag
                )
        
        # Create task-stakeholder involvement for some tasks
        tasks = Task.objects.filter(column__board=board)[:10]
        for task in tasks:
            for _ in range(random.randint(1, 3)):
                stakeholder = random.choice(stakeholders)
                involvement, created = StakeholderTaskInvolvement.objects.get_or_create(
                    stakeholder=stakeholder,
                    task=task,
                    defaults={
                        'involvement_type': random.choice(['owner', 'contributor', 'reviewer', 'stakeholder']),
                        'engagement_status': random.choice(['informed', 'consulted', 'involved']),
                        'satisfaction_rating': random.randint(3, 5),
                        'engagement_count': random.randint(1, 5)
                    }
                )
                if created:
                    self.stdout.write(f'  Added {stakeholder.name} to task: {task.title}')
        
        # Create engagement records
        from django.db import models as django_models
        for stakeholder in stakeholders:
            for _ in range(random.randint(2, 4)):
                engagement = StakeholderEngagementRecord.objects.create(
                    stakeholder=stakeholder,
                    date=(timezone.now() - timedelta(days=random.randint(0, 30))).date(),
                    description=random.choice([
                        'Status update meeting',
                        'Review session for deliverables',
                        'Risk discussion and mitigation planning',
                        'Feedback collection on current progress',
                        'Planning session for next phase'
                    ]),
                    communication_channel=random.choice(['email', 'phone', 'meeting', 'video']),
                    outcome='Discussed project status and next steps',
                    engagement_sentiment=random.choice(['positive', 'neutral', 'positive']),
                    satisfaction_rating=random.randint(3, 5),
                    created_by=self.users['admin'],
                    follow_up_required=random.choice([True, False])
                )
                self.stdout.write(f'  Created engagement record for {stakeholder.name}')
        
        # Create engagement metrics
        from django.db import models as django_models
        for stakeholder in stakeholders:
            engagement_records = StakeholderEngagementRecord.objects.filter(stakeholder=stakeholder)
            avg_satisfaction = engagement_records.aggregate(django_models.Avg('satisfaction_rating'))['satisfaction_rating__avg'] or 4
            
            metrics, created = EngagementMetrics.objects.get_or_create(
                board=board,
                stakeholder=stakeholder,
                defaults={
                    'total_engagements': engagement_records.count(),
                    'engagements_this_month': engagement_records.filter(
                        date__gte=(timezone.now() - timedelta(days=30)).date()
                    ).count(),
                    'average_satisfaction': round(avg_satisfaction, 2),
                    'engagement_gap': stakeholder.get_engagement_gap(),
                    'period_start': (timezone.now() - timedelta(days=90)).date(),
                    'period_end': timezone.now().date()
                }
            )
            if created:
                self.stdout.write(f'  Created engagement metrics for {stakeholder.name}')
        
        self.stdout.write(self.style.SUCCESS('✅ Stakeholder Management demo data created'))

    def create_task_dependency_demo_data(self):
        """Create demo data for task dependencies and requirements management"""
        self.stdout.write(self.style.NOTICE('Creating Task Dependencies demo data...'))
        
        # Get all tasks
        all_tasks = list(Task.objects.all())
        if len(all_tasks) < 5:
            self.stdout.write('Not enough tasks for dependency demo data')
            return
        
        # Create parent-child relationships (task hierarchy)
        for i in range(0, min(10, len(all_tasks) - 1), 2):
            parent_task = all_tasks[i]
            child_task = all_tasks[i + 1]
            
            # Make child task a subtask
            child_task.parent_task = parent_task
            child_task.save()
            child_task.update_dependency_chain()
            
            self.stdout.write(f'  Created dependency: {parent_task.title} -> {child_task.title}')
        
        # Create related task relationships (non-hierarchical)
        for task in all_tasks[10:15]:
            related_tasks = random.sample([t for t in all_tasks if t.id != task.id], k=min(2, len(all_tasks) - 1))
            for related_task in related_tasks:
                task.related_tasks.add(related_task)
            self.stdout.write(f'  Added {len(related_tasks)} related tasks to: {task.title}')
        
        # Add resource skill requirements and AI suggestions
        for task in all_tasks[:12]:
            if task.priority in ['high', 'urgent']:
                # Add required skills
                task.required_skills = [
                    {'name': random.choice(['Python', 'JavaScript', 'SQL', 'DevOps']), 'level': random.choice(['Intermediate', 'Advanced'])},
                    {'name': random.choice(['Problem Solving', 'Communication', 'Team Work']), 'level': random.choice(['Intermediate', 'Advanced'])}
                ]
                
                # Add skill match score
                task.skill_match_score = random.randint(60, 95)
                
                # Add optimal assignee suggestions
                available_users = [u for u in self.users.values() if u.id != task.created_by.id]
                task.optimal_assignee_suggestions = [
                    {
                        'user_id': user.id,
                        'username': user.username,
                        'match_score': random.randint(70, 100),
                        'reason': 'Skills match with task requirements'
                    }
                    for user in random.sample(available_users, k=min(2, len(available_users)))
                ]
                
                # Add collaboration indicators
                task.collaboration_required = random.choice([True, False])
                if task.collaboration_required:
                    task.suggested_team_members = [
                        {
                            'user_id': user.id,
                            'username': user.username,
                            'role': 'Collaborator'
                        }
                        for user in random.sample(available_users, k=min(2, len(available_users)))
                    ]
                
                # Add complexity score
                task.complexity_score = random.randint(1, 10)
                
                # Add suggested dependencies
                other_tasks = [t for t in all_tasks if t.id != task.id]
                if other_tasks:
                    suggested_deps = random.sample(other_tasks, k=min(2, len(other_tasks)))
                    task.suggested_dependencies = [
                        {
                            'task_id': dep.id,
                            'title': dep.title,
                            'reason': 'May need to be completed before this task',
                            'confidence': round(random.uniform(0.6, 0.95), 2)
                        }
                        for dep in suggested_deps
                    ]
                    task.last_dependency_analysis = timezone.now()
                
                task.save()
                self.stdout.write(f'  Enhanced task with resource and dependency data: {task.title}')
        
        self.stdout.write(self.style.SUCCESS('✅ Task Dependencies demo data created'))

    def create_milestone_demo_data(self):
        """Create demo data for milestone features"""
        self.stdout.write(self.style.NOTICE('Creating Milestones demo data...'))
        
        # Get all boards
        software_board = Board.objects.filter(name='Software Project').first()
        bug_board = Board.objects.filter(name='Bug Tracking').first()
        marketing_board = Board.objects.filter(name='Marketing Campaign').first()
        
        # Software Project Milestones
        if software_board:
            self.stdout.write(f'Creating milestones for {software_board.name}...')
            
            # Get some tasks to link to milestones
            software_tasks = Task.objects.filter(column__board=software_board)
            
            milestones_data = [
                {
                    'title': 'Project Kickoff',
                    'description': 'Official start of the Software Project development phase',
                    'target_date': timezone.now().date() - timedelta(days=60),
                    'milestone_type': 'project_start',
                    'is_completed': True,
                    'completed_date': timezone.now().date() - timedelta(days=60),
                    'color': '#28a745',
                    'created_by': self.users['admin'],
                    'related_tasks': []
                },
                {
                    'title': 'Authentication Module Complete',
                    'description': 'Complete implementation of user authentication, including login, registration, and password reset',
                    'target_date': timezone.now().date() - timedelta(days=30),
                    'milestone_type': 'phase_completion',
                    'is_completed': True,
                    'completed_date': timezone.now().date() - timedelta(days=28),
                    'color': '#28a745',
                    'created_by': self.users['john_doe'],
                    'related_tasks': list(software_tasks.filter(title__icontains='auth')[:2])
                },
                {
                    'title': 'Database Schema Finalized',
                    'description': 'Complete database design and schema implementation',
                    'target_date': timezone.now().date() - timedelta(days=20),
                    'milestone_type': 'deliverable',
                    'is_completed': True,
                    'completed_date': timezone.now().date() - timedelta(days=18),
                    'color': '#17a2b8',
                    'created_by': self.users['robert_johnson'],
                    'related_tasks': list(software_tasks.filter(title__icontains='database')[:2])
                },
                {
                    'title': 'Dashboard MVP Ready',
                    'description': 'Minimum viable product of the main dashboard with key features',
                    'target_date': timezone.now().date() + timedelta(days=5),
                    'milestone_type': 'deliverable',
                    'is_completed': False,
                    'completed_date': None,
                    'color': '#ffc107',
                    'created_by': self.users['john_doe'],
                    'related_tasks': list(software_tasks.filter(title__icontains='dashboard')[:3])
                },
                {
                    'title': 'Code Review & Testing Phase',
                    'description': 'Complete code review of all modules and comprehensive testing',
                    'target_date': timezone.now().date() + timedelta(days=15),
                    'milestone_type': 'review',
                    'is_completed': False,
                    'completed_date': None,
                    'color': '#6f42c1',
                    'created_by': self.users['admin'],
                    'related_tasks': list(software_tasks.filter(title__icontains='review')[:2])
                },
                {
                    'title': 'Beta Release',
                    'description': 'First beta release of the application to selected users',
                    'target_date': timezone.now().date() + timedelta(days=30),
                    'milestone_type': 'deliverable',
                    'is_completed': False,
                    'completed_date': None,
                    'color': '#fd7e14',
                    'created_by': self.users['admin'],
                    'related_tasks': list(software_tasks[:5])
                },
                {
                    'title': 'Production Deployment',
                    'description': 'Final deployment to production environment',
                    'target_date': timezone.now().date() + timedelta(days=60),
                    'milestone_type': 'project_end',
                    'is_completed': False,
                    'completed_date': None,
                    'color': '#dc3545',
                    'created_by': self.users['admin'],
                    'related_tasks': []
                },
            ]
            
            for milestone_data in milestones_data:
                related_tasks = milestone_data.pop('related_tasks', [])
                milestone = Milestone.objects.create(
                    board=software_board,
                    **milestone_data
                )
                if related_tasks:
                    milestone.related_tasks.set(related_tasks)
                self.stdout.write(f'  Created milestone: {milestone.title}')
        
        # Bug Tracking Board Milestones
        if bug_board:
            self.stdout.write(f'Creating milestones for {bug_board.name}...')
            
            bug_tasks = Task.objects.filter(column__board=bug_board)
            
            milestones_data = [
                {
                    'title': 'Bug Tracking System Launch',
                    'description': 'Official launch of the bug tracking board',
                    'target_date': timezone.now().date() - timedelta(days=45),
                    'milestone_type': 'project_start',
                    'is_completed': True,
                    'completed_date': timezone.now().date() - timedelta(days=45),
                    'color': '#28a745',
                    'created_by': self.users['robert_johnson'],
                    'related_tasks': []
                },
                {
                    'title': 'All Critical Bugs Resolved',
                    'description': 'Resolution of all critical priority bugs',
                    'target_date': timezone.now().date() - timedelta(days=10),
                    'milestone_type': 'phase_completion',
                    'is_completed': True,
                    'completed_date': timezone.now().date() - timedelta(days=8),
                    'color': '#28a745',
                    'created_by': self.users['robert_johnson'],
                    'related_tasks': list(bug_tasks.filter(title__icontains='500')[:1])
                },
                {
                    'title': 'Safari Compatibility Fixed',
                    'description': 'All Safari browser compatibility issues resolved',
                    'target_date': timezone.now().date() + timedelta(days=3),
                    'milestone_type': 'deliverable',
                    'is_completed': False,
                    'completed_date': None,
                    'color': '#ffc107',
                    'created_by': self.users['john_doe'],
                    'related_tasks': list(bug_tasks.filter(title__icontains='Safari')[:1])
                },
                {
                    'title': 'Performance Optimization Complete',
                    'description': 'All performance-related bugs and optimizations completed',
                    'target_date': timezone.now().date() + timedelta(days=12),
                    'milestone_type': 'phase_completion',
                    'is_completed': False,
                    'completed_date': None,
                    'color': '#17a2b8',
                    'created_by': self.users['robert_johnson'],
                    'related_tasks': list(bug_tasks.filter(title__icontains='performance')[:1])
                },
                {
                    'title': 'UI/UX Issues Resolved',
                    'description': 'All user interface and user experience bugs fixed',
                    'target_date': timezone.now().date() + timedelta(days=20),
                    'milestone_type': 'deliverable',
                    'is_completed': False,
                    'completed_date': None,
                    'color': '#20c997',
                    'created_by': self.users['john_doe'],
                    'related_tasks': list(bug_tasks.filter(title__icontains='button')[:1])
                },
            ]
            
            for milestone_data in milestones_data:
                related_tasks = milestone_data.pop('related_tasks', [])
                milestone = Milestone.objects.create(
                    board=bug_board,
                    **milestone_data
                )
                if related_tasks:
                    milestone.related_tasks.set(related_tasks)
                self.stdout.write(f'  Created milestone: {milestone.title}')
        
        # Marketing Campaign Board Milestones
        if marketing_board:
            self.stdout.write(f'Creating milestones for {marketing_board.name}...')
            
            marketing_tasks = Task.objects.filter(column__board=marketing_board)
            
            milestones_data = [
                {
                    'title': 'Q3 Campaign Planning Complete',
                    'description': 'Finalize all Q3 marketing campaign strategies and plans',
                    'target_date': timezone.now().date() - timedelta(days=25),
                    'milestone_type': 'phase_completion',
                    'is_completed': True,
                    'completed_date': timezone.now().date() - timedelta(days=23),
                    'color': '#28a745',
                    'created_by': self.users['carol_anderson'],
                    'related_tasks': list(marketing_tasks.filter(title__icontains='Q3')[:1])
                },
                {
                    'title': 'Website Redesign Launch',
                    'description': 'Launch the newly redesigned website for Q4',
                    'target_date': timezone.now().date() + timedelta(days=12),
                    'milestone_type': 'deliverable',
                    'is_completed': False,
                    'completed_date': None,
                    'color': '#fd7e14',
                    'created_by': self.users['carol_anderson'],
                    'related_tasks': list(marketing_tasks.filter(title__icontains='Website')[:1])
                },
                {
                    'title': 'Social Media Campaign Launch',
                    'description': 'Official launch of holiday social media campaign',
                    'target_date': timezone.now().date() + timedelta(days=18),
                    'milestone_type': 'deliverable',
                    'is_completed': False,
                    'completed_date': None,
                    'color': '#007bff',
                    'created_by': self.users['carol_anderson'],
                    'related_tasks': list(marketing_tasks.filter(title__icontains='social')[:1])
                },
                {
                    'title': 'Q3 Performance Review',
                    'description': 'Complete review and analysis of Q3 marketing performance',
                    'target_date': timezone.now().date() + timedelta(days=4),
                    'milestone_type': 'review',
                    'is_completed': False,
                    'completed_date': None,
                    'color': '#6f42c1',
                    'created_by': self.users['david_taylor'],
                    'related_tasks': list(marketing_tasks.filter(title__icontains='report')[:1])
                },
                {
                    'title': 'Video Content Series Complete',
                    'description': 'Complete production of all video content for product demonstrations',
                    'target_date': timezone.now().date() + timedelta(days=25),
                    'milestone_type': 'deliverable',
                    'is_completed': False,
                    'completed_date': None,
                    'color': '#20c997',
                    'created_by': self.users['david_taylor'],
                    'related_tasks': list(marketing_tasks.filter(title__icontains='Video')[:1])
                },
                {
                    'title': 'Q4 Campaign Kickoff',
                    'description': 'Launch of Q4 marketing campaigns and initiatives',
                    'target_date': timezone.now().date() + timedelta(days=35),
                    'milestone_type': 'project_start',
                    'is_completed': False,
                    'completed_date': None,
                    'color': '#28a745',
                    'created_by': self.users['carol_anderson'],
                    'related_tasks': []
                },
            ]
            
            for milestone_data in milestones_data:
                related_tasks = milestone_data.pop('related_tasks', [])
                milestone = Milestone.objects.create(
                    board=marketing_board,
                    **milestone_data
                )
                if related_tasks:
                    milestone.related_tasks.set(related_tasks)
                self.stdout.write(f'  Created milestone: {milestone.title}')
        
        # Print summary
        total_milestones = Milestone.objects.count()
        completed_milestones = Milestone.objects.filter(is_completed=True).count()
        upcoming_milestones = Milestone.objects.filter(is_completed=False, target_date__gte=timezone.now().date()).count()
        overdue_milestones = Milestone.objects.filter(is_completed=False, target_date__lt=timezone.now().date()).count()
        
        self.stdout.write(self.style.SUCCESS(f'✅ Milestones demo data created:'))
        self.stdout.write(self.style.SUCCESS(f'   Total: {total_milestones} milestones'))
        self.stdout.write(self.style.SUCCESS(f'   Completed: {completed_milestones}'))
        self.stdout.write(self.style.SUCCESS(f'   Upcoming: {upcoming_milestones}'))
        self.stdout.write(self.style.SUCCESS(f'   Overdue: {overdue_milestones}'))


    def create_chat_rooms_demo_data(self):
        """Create demo data for chat rooms and messaging features"""
        self.stdout.write(self.style.NOTICE('Creating Chat Rooms demo data...'))
        
        # Create chat rooms for each board
        for board in Board.objects.all():
            # Define chat rooms for this board
            chat_room_configs = [
                {
                    'name': 'General Discussion',
                    'description': 'General discussion and announcements for the team',
                },
                {
                    'name': 'Technical Support',
                    'description': 'Technical questions and support',
                },
                {
                    'name': 'Feature Planning',
                    'description': 'Discuss and plan new features',
                },
                {
                    'name': 'Random Chat',
                    'description': 'Off-topic conversations and fun stuff',
                }
            ]
            
            for room_config in chat_room_configs:
                # Create or get chat room
                chat_room, created = ChatRoom.objects.get_or_create(
                    board=board,
                    name=room_config['name'],
                    defaults={
                        'description': room_config['description'],
                        'created_by': self.users['admin']
                    }
                )
                
                if created:
                    self.stdout.write(f'  Created chat room: {chat_room.name} in {board.name}')
                    
                    # Add board members to the chat room
                    for member in board.members.all():
                        chat_room.members.add(member)
                    
                    # Add admin to all rooms
                    chat_room.members.add(self.users['admin'])
                    
                    # Create sample messages in the chat room
                    self.create_sample_chat_messages(chat_room)
        
        self.stdout.write(self.style.SUCCESS('✅ Chat Rooms demo data created'))
    
    def create_sample_chat_messages(self, chat_room):
        """Create sample messages in a chat room"""
        # Sample message templates
        messages_templates = {
            'General Discussion': [
                'Hi everyone! Let\'s keep each other updated on our progress.',
                'I\'ll start working on the frontend components today.',
                'Great work on the backend API! It\'s working perfectly.',
                'Let\'s schedule a sync meeting for tomorrow morning.',
                'Just deployed the latest changes to staging. Please test when you get a chance.'
            ],
            'Technical Support': [
                'Can someone help me with the database migration?',
                'I\'m getting an error on line 45. Any ideas?',
                'Try updating your npm packages, that should fix it.',
                'The API endpoint is throwing a 500 error. Working on it now.',
                'Quick fix: Make sure your environment variables are properly set.'
            ],
            'Feature Planning': [
                'We should add user authentication next sprint.',
                'What about implementing a notification system?',
                'I like the idea. Let\'s create a technical spec for it.',
                'I can work on the UI components for notifications.',
                'Sounds good! Let\'s plan this in the next refinement session.'
            ],
            'Random Chat': [
                'Anyone up for coffee later?',
                'Great news! We shipped the new feature! 🎉',
                'Looking forward to the team lunch on Friday!',
                'Anyone caught the latest tech news?',
                'Just finished my morning jog. Feeling energized!'
            ]
        }
        
        # Get messages for this room
        room_messages = messages_templates.get(chat_room.name, [])
        if not room_messages:
            return
        
        # Create messages from different users
        available_users = list(chat_room.members.all())
        if not available_users:
            return
        
        # Create 3-5 messages per room
        for i, message_content in enumerate(room_messages[:5]):
            # Rotate through available users
            author = available_users[i % len(available_users)]
            
            # Create message with timestamp spread across the past week
            message_date = timezone.now() - timedelta(
                days=random.randint(0, 7),
                hours=random.randint(0, 23),
                minutes=random.randint(0, 59)
            )
            
            chat_message = ChatMessage.objects.create(
                chat_room=chat_room,
                author=author,
                content=message_content,
                created_at=message_date
            )
            
            self.stdout.write(f'    Created message from {author.username} in {chat_room.name}')

    def create_wiki_demo_data(self):
        """Create demo data for wiki and knowledge base features"""
        self.stdout.write(self.style.NOTICE('Creating Wiki & Knowledge Base demo data...'))
        
        # Create wiki categories for each organization
        for org_key, org in self.organizations.items():
            self.stdout.write(f'  Creating wiki categories for {org.name}...')
            
            # Define categories based on organization type
            if org_key == 'dev':
                categories_data = [
                    {
                        'name': 'Technical Documentation',
                        'description': 'API docs, architecture guides, and technical specifications',
                        'icon': 'code',
                        'color': '#3498db',
                        'position': 1
                    },
                    {
                        'name': 'Best Practices',
                        'description': 'Coding standards, design patterns, and development guidelines',
                        'icon': 'star',
                        'color': '#f39c12',
                        'position': 2
                    },
                    {
                        'name': 'Onboarding',
                        'description': 'Getting started guides for new team members',
                        'icon': 'user-plus',
                        'color': '#2ecc71',
                        'position': 3
                    },
                    {
                        'name': 'Meeting Notes',
                        'description': 'Sprint planning, retrospectives, and standup notes',
                        'icon': 'calendar',
                        'color': '#9b59b6',
                        'position': 4
                    }
                ]
            else:  # marketing
                categories_data = [
                    {
                        'name': 'Campaign Planning',
                        'description': 'Marketing campaign strategies and plans',
                        'icon': 'bullhorn',
                        'color': '#e74c3c',
                        'position': 1
                    },
                    {
                        'name': 'Brand Guidelines',
                        'description': 'Logo usage, color palettes, and brand voice',
                        'icon': 'palette',
                        'color': '#1abc9c',
                        'position': 2
                    },
                    {
                        'name': 'Meeting Notes',
                        'description': 'Campaign reviews and planning sessions',
                        'icon': 'calendar',
                        'color': '#9b59b6',
                        'position': 3
                    }
                ]
            
            # Create categories
            categories = {}
            for cat_data in categories_data:
                category, created = WikiCategory.objects.get_or_create(
                    organization=org,
                    name=cat_data['name'],
                    defaults={
                        'description': cat_data['description'],
                        'icon': cat_data['icon'],
                        'color': cat_data['color'],
                        'position': cat_data['position']
                    }
                )
                categories[cat_data['name']] = category
                if created:
                    self.stdout.write(f'    Created category: {category.name}')
                else:
                    self.stdout.write(f'    Category {category.name} already exists')
            
            # Create wiki pages for each category
            self.stdout.write(f'  Creating wiki pages for {org.name}...')
            
            if org_key == 'dev':
                # Technical Documentation pages
                pages_data = [
                    {
                        'category': 'Technical Documentation',
                        'title': 'API Reference Guide',
                        'content': '''# API Reference Guide

## Overview
This document provides comprehensive API documentation for our PrizmAI application.

## Authentication
All API requests require authentication using JWT tokens.

```python
headers = {
    'Authorization': 'Bearer YOUR_TOKEN_HERE'
}
```

## Endpoints

### Tasks API
- `GET /api/tasks/` - List all tasks
- `POST /api/tasks/` - Create a new task
- `GET /api/tasks/{id}/` - Get task details
- `PUT /api/tasks/{id}/` - Update a task
- `DELETE /api/tasks/{id}/` - Delete a task

### Boards API
- `GET /api/boards/` - List all boards
- `POST /api/boards/` - Create a new board

## Rate Limiting
API requests are limited to 100 requests per minute per user.

## Error Handling
All errors return a JSON response with an error message and status code.
''',
                        'tags': ['api', 'documentation', 'reference'],
                        'is_pinned': True
                    },
                    {
                        'category': 'Technical Documentation',
                        'title': 'Database Schema Documentation',
                        'content': '''# Database Schema

## Core Models

### Task Model
- `id` (Primary Key)
- `title` (CharField)
- `description` (TextField)
- `column` (ForeignKey to Column)
- `assigned_to` (ForeignKey to User)
- `due_date` (DateTimeField)
- `priority` (CharField with choices)

### Board Model
- `id` (Primary Key)
- `name` (CharField)
- `organization` (ForeignKey to Organization)
- `created_by` (ForeignKey to User)

## Relationships
- One Board has many Columns
- One Column has many Tasks
- Tasks can be assigned to Users
- Tasks belong to Organizations through Boards
''',
                        'tags': ['database', 'schema', 'models'],
                        'is_pinned': False
                    },
                    {
                        'category': 'Best Practices',
                        'title': 'Python Code Style Guide',
                        'content': '''# Python Code Style Guide

## General Guidelines
- Follow PEP 8 style guide
- Use meaningful variable names
- Keep functions small and focused
- Write docstrings for all functions and classes

## Code Examples

### Good Example
```python
def calculate_task_priority(task, risk_score, deadline):
    """
    Calculate task priority based on risk and deadline.
    
    Args:
        task: Task object
        risk_score: Integer (0-100)
        deadline: datetime object
    
    Returns:
        str: Priority level ('low', 'medium', 'high', 'urgent')
    """
    if risk_score > 80 or is_deadline_near(deadline):
        return 'urgent'
    elif risk_score > 50:
        return 'high'
    else:
        return 'medium'
```

## Testing
- Write unit tests for all business logic
- Use pytest for testing
- Aim for >80% code coverage
''',
                        'tags': ['python', 'coding-standards', 'best-practices'],
                        'is_pinned': True
                    },
                    {
                        'category': 'Onboarding',
                        'title': 'Developer Onboarding Checklist',
                        'content': '''# Developer Onboarding Checklist

## Week 1: Setup & Introduction
- [ ] Get access to GitHub repository
- [ ] Set up local development environment
- [ ] Install required tools (Python, PostgreSQL, Redis)
- [ ] Run the application locally
- [ ] Meet the team members
- [ ] Review codebase structure

## Week 2: First Tasks
- [ ] Fix your first bug
- [ ] Submit your first pull request
- [ ] Attend sprint planning
- [ ] Read all technical documentation
- [ ] Set up your IDE with project settings

## Week 3: Integration
- [ ] Take on a feature task
- [ ] Participate in code reviews
- [ ] Join team standups
- [ ] Learn about deployment process

## Key Information
- Complete source code is available in the GitHub repository
- Technical documentation is maintained in the team wiki
- Database schemas are documented in our internal documentation
- Our code follows PEP 8 style guidelines
''',
                        'tags': ['onboarding', 'new-hire', 'checklist'],
                        'is_pinned': True
                    },
                    {
                        'category': 'Meeting Notes',
                        'title': 'Sprint Planning - November 2025',
                        'content': '''# Sprint Planning Meeting
**Date:** November 1, 2025  
**Duration:** 2 hours  
**Attendees:** John, Jane, Robert, Alice, Bob

## Sprint Goals
1. Complete risk management feature enhancements
2. Implement real-time chat notifications
3. Fix critical bugs in Gantt chart view

## Tasks Committed
- **John:** Implement chat notifications (Story Points: 8)
- **Jane:** Risk management UI improvements (Story Points: 5)
- **Robert:** Gantt chart bug fixes (Story Points: 3)
- **Alice:** API endpoint optimization (Story Points: 5)
- **Bob:** Write unit tests for new features (Story Points: 3)

## Total Story Points: 24

## Notes
- Need to schedule technical design review for chat feature
- Database migration required for new notification system
- QA testing window: November 10-12

## Action Items
- [ ] John to create technical design doc by Nov 3
- [ ] Jane to update Figma designs by Nov 2
- [ ] Robert to investigate Gantt performance issues
''',
                        'tags': ['sprint-planning', 'meeting-notes', 'november'],
                        'is_pinned': False
                    }
                ]
            else:  # marketing
                pages_data = [
                    {
                        'category': 'Campaign Planning',
                        'title': 'Q4 2025 Campaign Strategy',
                        'content': '''# Q4 2025 Marketing Campaign Strategy

## Campaign Overview
Launch a comprehensive marketing campaign to increase user acquisition by 30%.

## Target Audience
- Small to medium-sized tech companies
- Project managers and team leads
- Age range: 25-45
- Tech-savvy professionals

## Campaign Channels
1. **Social Media** (Budget: $10,000)
   - LinkedIn ads targeting project managers
   - Twitter engagement campaign
   - Instagram visual storytelling

2. **Content Marketing** (Budget: $5,000)
   - Blog posts about project management
   - Case studies from existing customers
   - Video tutorials and demos

3. **Email Marketing** (Budget: $3,000)
   - Newsletter campaigns
   - Drip campaigns for leads
   - Re-engagement campaigns

## Timeline
- November: Campaign launch
- December: Optimization phase
- January: Analysis and reporting

## Success Metrics
- 10,000 new website visits
- 500 new trial sign-ups
- 30% increase in social media engagement
''',
                        'tags': ['campaign', 'strategy', 'q4-2025'],
                        'is_pinned': True
                    },
                    {
                        'category': 'Brand Guidelines',
                        'title': 'PrizmAI Brand Style Guide',
                        'content': '''# PrizmAI Brand Style Guide

## Logo Usage
Always use the full-color logo on white backgrounds.
Use the white logo on dark backgrounds.

### Logo Specifications
- Minimum size: 120px width
- Clear space: 20px on all sides
- File formats: SVG (preferred), PNG

## Color Palette

### Primary Colors
- **Blue:** #3498db - Primary brand color
- **Dark Blue:** #2980b9 - Text and accents

### Secondary Colors
- **Green:** #2ecc71 - Success states
- **Orange:** #f39c12 - Warnings
- **Red:** #e74c3c - Errors
- **Purple:** #9b59b6 - Highlights

## Typography
- **Headings:** Inter Bold
- **Body Text:** Inter Regular
- **Code:** Source Code Pro

## Voice & Tone
- Professional but friendly
- Clear and concise
- Action-oriented
- Helpful and supportive

## Examples
✅ "Complete your task in minutes"
❌ "Our advanced task completion functionality enables rapid workflow optimization"
''',
                        'tags': ['brand', 'style-guide', 'design'],
                        'is_pinned': True
                    },
                    {
                        'category': 'Meeting Notes',
                        'title': 'Marketing Team Sync - November 2025',
                        'content': '''# Marketing Team Weekly Sync
**Date:** November 4, 2025  
**Attendees:** Carol (Manager), David

## Updates
- **Carol:** Q4 campaign is live, initial metrics looking good
- **David:** Completed social media content calendar for November

## Discussion Points
1. Social media engagement up 15% this week
2. Need to create more video content
3. Planning webinar series for December

## Action Items
- [ ] Carol: Review campaign analytics by end of week
- [ ] David: Create 3 new video scripts by Friday
- [ ] Both: Brainstorm webinar topics for next meeting

## Next Meeting
November 11, 2025 at 2:00 PM
''',
                        'tags': ['meeting-notes', 'marketing', 'weekly-sync'],
                        'is_pinned': False
                    }
                ]
            
            # Create wiki pages
            for page_data in pages_data:
                category = categories[page_data['category']]
                page, created = WikiPage.objects.get_or_create(
                    organization=org,
                    title=page_data['title'],
                    defaults={
                        'category': category,
                        'content': page_data['content'],
                        'tags': page_data.get('tags', []),
                        'is_pinned': page_data.get('is_pinned', False),
                        'is_published': True,
                        'created_by': self.users['admin'],
                        'updated_by': self.users['admin'],
                        'view_count': random.randint(5, 50)
                    }
                )
                if created:
                    self.stdout.write(f'    Created wiki page: {page.title}')
                else:
                    self.stdout.write(f'    Wiki page {page.title} already exists')
        
        self.stdout.write(self.style.SUCCESS('  ✓ Wiki & Knowledge Base demo data created!'))

    def create_meeting_transcript_demo_data(self):
        """Create demo data for meeting transcripts"""
        self.stdout.write(self.style.NOTICE('Creating Meeting Transcript demo data...'))
        
        # Get boards for creating meeting transcripts
        for org_key, org in self.organizations.items():
            boards = org.boards.all()
            
            for board in boards:
                self.stdout.write(f'  Creating meeting transcripts for {board.name}...')
                
                # Define meeting transcripts based on board type
                if 'Software' in board.name or 'Bug' in board.name:
                    meetings_data = [
                        {
                            'title': 'Sprint Planning - November Sprint',
                            'meeting_type': 'planning',
                            'transcript_text': '''Team: John, Jane, Robert, Alice, Bob
Duration: 90 minutes

John: Let's kick off sprint planning. We have 24 story points capacity this sprint.

Jane: I'd like to take the risk management UI improvements. That's about 5 points.

Robert: I can handle the Gantt chart bugs. Should be around 3 points.

Alice: I'll work on API optimization. Estimate 5 points.

Bob: I'll focus on writing tests for the new features - 3 points.

John: That leaves me with the chat notifications feature at 8 points. Total is 24.

Jane: Sounds good. When's the technical review?

John: I'll schedule it for Wednesday. Any blockers?

Robert: Need access to production logs for debugging.

Alice: I'll get you access by end of day.

John: Great! Let's make this a successful sprint.
''',
                            'participants': ['john_doe', 'jane_smith', 'robert_johnson', 'alice_williams', 'bob_martinez'],
                            'tasks_count': 3
                        },
                        {
                            'title': 'Daily Standup - November 5',
                            'meeting_type': 'standup',
                            'transcript_text': '''Daily Standup - 15 minutes

John: Yesterday I completed the authentication flow for chat. Today working on notifications. No blockers.

Jane: Finished the risk UI mockups. Today implementing the frontend components. Need design review.

Robert: Fixed two critical Gantt bugs yesterday. Today investigating the performance issue. Blocked by production logs access.

Alice: Completed API endpoint refactoring. Today starting on optimization. No blockers.

Bob: Wrote unit tests for authentication module. Today continuing with chat tests. No blockers.

Action items:
- Jane schedules design review with team
- Robert gets production logs access from Alice
- Team to review pull requests by end of day
''',
                            'participants': ['john_doe', 'jane_smith', 'robert_johnson', 'alice_williams', 'bob_martinez'],
                            'tasks_count': 2
                        },
                        {
                            'title': 'Technical Design Review - Chat Notifications',
                            'meeting_type': 'review',
                            'transcript_text': '''Technical Design Review
Topic: Real-time Chat Notifications
Duration: 60 minutes

John: Presenting the technical design for chat notifications using WebSockets.

Architecture:
- Django Channels for WebSocket support
- Redis as message broker
- Celery for background tasks
- Push notifications via Firebase

Jane: How do we handle offline users?

John: Messages are queued and sent when user reconnects. We also store notification history.

Robert: What about scalability?

John: Redis pub/sub can handle thousands of concurrent connections. We can horizontally scale the channels workers.

Alice: Security concerns?

John: All WebSocket connections are authenticated with JWT tokens. Messages are encrypted in transit.

Bob: Testing strategy?

John: Unit tests for message handlers, integration tests for WebSocket connections, load testing with 1000 concurrent users.

Approved: Team approved the design with minor modifications to error handling.
''',
                            'participants': ['john_doe', 'jane_smith', 'robert_johnson', 'alice_williams', 'bob_martinez'],
                            'tasks_count': 1
                        }
                    ]
                elif 'Marketing' in board.name:
                    meetings_data = [
                        {
                            'title': 'Q4 Campaign Planning Meeting',
                            'meeting_type': 'planning',
                            'transcript_text': '''Marketing Campaign Planning
Attendees: Carol, David
Duration: 60 minutes

Carol: Let's plan our Q4 marketing campaign. Goal is 30% user growth.

David: I've prepared a content calendar. We're focusing on LinkedIn and Twitter.

Carol: Great. What's the budget breakdown?

David: Social media ads $10k, content creation $5k, email campaigns $3k.

Carol: Approved. What about content themes?

David: Week 1-2: Product features
Week 3-4: Customer success stories
Week 5-6: Industry trends
Week 7-8: Year-end promotions

Carol: I like it. Let's also do a webinar series.

David: Good idea. I'll draft topics for next week.

Carol: Timeline?

David: Campaign launches November 15. First webinar December 1.

Action items:
- David creates detailed content calendar
- Carol approves social media creatives
- Both brainstorm webinar topics
''',
                            'participants': ['carol_anderson', 'david_taylor'],
                            'tasks_count': 2
                        },
                        {
                            'title': 'Weekly Marketing Sync',
                            'meeting_type': 'general',
                            'transcript_text': '''Weekly Marketing Team Sync
Date: November 4, 2025

Carol: Let's review this week's metrics.

David: Social media engagement up 15%. LinkedIn performing best.

Carol: Excellent! How about email campaigns?

David: Open rate 22%, click rate 4.5%. Above industry average.

Carol: What's working?

David: Personalized subject lines and customer testimonials.

Carol: Keep that up. Any challenges?

David: Video content creation is taking longer than expected.

Carol: Let's allocate more budget for freelance videographers.

David: That would help. I'll get quotes.

Carol: Next week priorities?

David: Finish November content, start December planning.

Carol: Sounds good. Great work this week!
''',
                            'participants': ['carol_anderson', 'david_taylor'],
                            'tasks_count': 1
                        }
                    ]
                else:
                    continue
                
                # Create meeting notes
                for meeting_data in meetings_data:
                    # Calculate meeting date (within last 2 weeks)
                    meeting_date = timezone.now() - timedelta(days=random.randint(1, 14))
                    
                    # Get participants as User objects
                    participants = [self.users[username] for username in meeting_data['participants'] if username in self.users]
                    
                    meeting, created = MeetingNotes.objects.get_or_create(
                        organization=org,
                        title=meeting_data['title'],
                        date=meeting_date,
                        defaults={
                            'meeting_type': meeting_data['meeting_type'],
                            'content': f"# {meeting_data['title']}\n\n{meeting_data['transcript_text']}",
                            'transcript_text': meeting_data['transcript_text'],
                            'created_by': participants[0] if participants else self.users['admin'],
                            'related_board': board,
                            'duration_minutes': random.randint(15, 120),
                            'processing_status': 'completed',
                            'processed_at': timezone.now(),
                            'tasks_extracted_count': meeting_data['tasks_count'],
                            'tasks_created_count': random.randint(0, meeting_data['tasks_count']),
                            'action_items': [
                                {'task': 'Complete assigned tasks', 'assigned_to': p.username, 'status': 'pending'} 
                                for p in participants[:meeting_data['tasks_count']]
                            ],
                            'decisions': ['Approved technical design', 'Set sprint goals', 'Allocated resources'],
                            'extraction_results': {
                                'summary': f"Meeting about {meeting_data['title']}",
                                'action_items': meeting_data['tasks_count'],
                                'key_decisions': ['Approved technical design', 'Set sprint goals'],
                                'next_steps': ['Complete assigned tasks', 'Review progress next meeting']
                            }
                        }
                    )
                    
                    # Add attendees
                    if created:
                        meeting.attendees.set(participants)
                        self.stdout.write(f'    Created meeting notes: {meeting.title}')
                    else:
                        self.stdout.write(f'    Meeting notes {meeting.title} already exists')
        
        self.stdout.write(self.style.SUCCESS('  ✓ Meeting notes demo data created!'))

    def create_historical_task_data(self):
        """Create historical completed tasks for predictive analytics (6 months of data)"""
        self.stdout.write(self.style.NOTICE('Creating historical task completion data for predictions...'))
        
        # Priority factors affect completion speed
        priority_factors = {
            'urgent': 0.7,   # Completed 30% faster (high focus)
            'high': 0.85,    # 15% faster
            'medium': 1.0,   # Baseline
            'low': 1.3       # 30% slower (less attention)
        }
        
        # Task type templates for realistic titles
        task_types = [
            'Implement {feature}',
            'Fix bug in {component}',
            'Refactor {module}',
            'Add tests for {feature}',
            'Update documentation for {component}',
            'Optimize {feature} performance',
            'Review and merge {feature}',
            'Deploy {feature} to production',
            'Design {component} UI',
            'Research {technology} integration'
        ]
        
        features = ['authentication', 'dashboard', 'reporting', 'notifications', 'API endpoints', 
                   'user profile', 'search', 'filters', 'export', 'settings']
        components = ['login', 'navbar', 'sidebar', 'modal', 'form', 'table', 'chart', 'menu']
        modules = ['user module', 'task module', 'board module', 'analytics module']
        technologies = ['Redis', 'WebSockets', 'REST API', 'GraphQL', 'Docker']
        
        # CRITICAL: Only create historical tasks for DEMO BOARDS to avoid polluting user boards
        # Get only the official demo boards in demo organizations
        demo_org_names = ['Dev Team', 'Marketing Team']
        demo_board_names = ['Software Project', 'Bug Tracking', 'Marketing Campaign']
        
        demo_orgs = Organization.objects.filter(name__in=demo_org_names)
        demo_boards = Board.objects.filter(
            organization__in=demo_orgs,
            name__in=demo_board_names
        )
        
        if not demo_boards.exists():
            self.stdout.write(self.style.WARNING('  ⚠️  No demo boards found. Skipping historical task creation.'))
            return
        
        self.stdout.write(f'  Creating historical tasks for {demo_boards.count()} demo boards only')
        
        # Create historical tasks for each DEMO board only
        for board in demo_boards:
            self.stdout.write(f'  Creating historical tasks for board: {board.name}')
            
            # Get or create Done column
            done_column = board.columns.filter(
                name__in=['Done', 'Completed', 'Closed']
            ).first()
            
            if not done_column:
                # Create Done column if it doesn't exist
                max_position = board.columns.aggregate(Max('position'))['position__max'] or 0
                done_column = Column.objects.create(
                    name='Done',
                    board=board,
                    position=max_position + 1
                )
                self.stdout.write(f'    Created Done column for {board.name}')
            
            # Get board members for assignment
            members = list(board.members.all())
            if not members:
                members = [self.users['admin']]
            
            # Check if this board already has historical tasks (for idempotency)
            existing_historical_tasks = done_column.tasks.filter(
                description__contains='Historical completed task'
            ).count()
            
            if existing_historical_tasks > 20:
                self.stdout.write(f'    ⏭️  Board {board.name} already has {existing_historical_tasks} historical tasks, skipping...')
                continue
            
            # Create 20-25 historical tasks per board for manageable demo (total ~70 across 3 boards)
            num_tasks = random.randint(20, 25)
            
            for i in range(num_tasks):
                # Random date in past 6 months (180 days)
                days_ago = random.randint(7, 180)  # At least 7 days ago
                created_date = timezone.now() - timedelta(
                    days=days_ago,
                    hours=random.randint(0, 23),
                    minutes=random.randint(0, 59)
                )
                
                # Random complexity (1-10)
                complexity = random.randint(1, 10)
                
                # Random priority
                priority = random.choice(['urgent', 'high', 'medium', 'low'])
                
                # Calculate realistic completion time
                # Base: complexity * 1.5 days per complexity point
                base_days = complexity * 1.5
                
                # Apply priority factor
                adjusted_days = base_days * priority_factors[priority]
                
                # Add natural variation (±30%)
                variation = random.uniform(0.7, 1.3)
                actual_days = adjusted_days * variation
                
                # Apply team member velocity variation (some are faster/slower)
                team_member = random.choice(members)
                velocity_variation = random.uniform(0.8, 1.2)  # ±20% per person
                actual_days *= velocity_variation
                
                # Minimum 0.5 days, maximum 30 days
                actual_days = max(0.5, min(30, actual_days))
                
                # Calculate dates
                start_date = created_date.date()
                completed_date = created_date + timedelta(days=actual_days)
                
                # Due date was estimated as base_days * 1.2 (20% buffer)
                estimated_due_date = created_date + timedelta(days=base_days * 1.2)
                
                # Generate realistic task title
                task_template = random.choice(task_types)
                task_title = task_template.format(
                    feature=random.choice(features),
                    component=random.choice(components),
                    module=random.choice(modules),
                    technology=random.choice(technologies)
                )
                
                # Create historical task
                task = Task.objects.create(
                    title=task_title,
                    description=f"Historical completed task for predictive analytics.\nComplexity: {complexity}/10\nCompleted in {actual_days:.1f} days.",
                    column=done_column,
                    position=i,
                    created_at=created_date,
                    updated_at=completed_date,
                    start_date=start_date,
                    due_date=estimated_due_date,
                    assigned_to=team_member,
                    created_by=random.choice(members),
                    priority=priority,
                    progress=100,
                    complexity_score=complexity,
                    completed_at=completed_date,
                    actual_duration_days=round(actual_days, 2)
                )
                
                # Add some realistic attributes
                if random.random() < 0.3:  # 30% have risk scores
                    task.risk_score = random.randint(1, 9)
                    task.save()
                
                if random.random() < 0.2:  # 20% require collaboration
                    task.collaboration_required = True
                    task.save()
                
                # Create minimal activity records
                TaskActivity.objects.create(
                    task=task,
                    user=task.created_by,
                    activity_type='created',
                    description=f"Created task",
                    created_at=created_date
                )
                
                TaskActivity.objects.create(
                    task=task,
                    user=task.assigned_to,
                    activity_type='updated',
                    description=f"Completed task",
                    created_at=completed_date
                )
            
            self.stdout.write(f'    ✓ Created {num_tasks} historical tasks for {board.name}')
        
        # Update predictions for active tasks
        self.stdout.write(self.style.NOTICE('  Generating predictions for active tasks...'))
        from kanban.utils.task_prediction import bulk_update_predictions
        
        for org in self.organizations.values():
            result = bulk_update_predictions(organization=org)
            self.stdout.write(
                f'    ✓ Updated {result["updated"]} predictions for {org.name} '
                f'({result["total_tasks"]} active tasks)'
            )
        
        self.stdout.write(self.style.SUCCESS('✅ Historical task data and predictions created!'))
        
        # Create and update performance profiles for all demo board members
        self.create_performance_profiles()

    def create_performance_profiles(self):
        """Create and update UserPerformanceProfile for all demo board members"""
        self.stdout.write(self.style.NOTICE('\nCreating Resource Optimization performance profiles...'))
        
        from kanban.resource_leveling_models import UserPerformanceProfile
        
        # Get demo boards
        demo_org_names = ['Dev Team', 'Marketing Team']
        demo_board_names = ['Software Project', 'Bug Tracking', 'Marketing Campaign']
        
        demo_orgs = Organization.objects.filter(name__in=demo_org_names)
        demo_boards = Board.objects.filter(
            organization__in=demo_orgs,
            name__in=demo_board_names
        )
        
        if not demo_boards.exists():
            self.stdout.write(self.style.WARNING('  ⚠️  No demo boards found. Skipping profile creation.'))
            return
        
        total_profiles_created = 0
        total_profiles_updated = 0
        
        # Process each demo board
        for board in demo_boards:
            self.stdout.write(f'  Processing board: {board.name}')
            
            # Get all board members
            board_members = board.members.all()
            
            if not board_members.exists():
                self.stdout.write(f'    ⚠️  No members found for {board.name}')
                continue
            
            # Create/update profile for each member
            for member in board_members:
                try:
                    profile, created = UserPerformanceProfile.objects.get_or_create(
                        user=member,
                        organization=board.organization,
                        defaults={
                            'weekly_capacity_hours': 40.0,
                            'velocity_score': 1.0,
                            'quality_score': 3.0
                        }
                    )
                    
                    # Update metrics from historical task data
                    profile.update_metrics()
                    profile.update_current_workload()
                    
                    if created:
                        total_profiles_created += 1
                        self.stdout.write(
                            f'    ✓ Created profile for {member.username}: '
                            f'{profile.total_tasks_completed} completed tasks, '
                            f'velocity: {profile.velocity_score:.2f} tasks/week'
                        )
                    else:
                        total_profiles_updated += 1
                        self.stdout.write(
                            f'    ✓ Updated profile for {member.username}: '
                            f'{profile.total_tasks_completed} completed tasks, '
                            f'velocity: {profile.velocity_score:.2f} tasks/week'
                        )
                        
                except Exception as e:
                    self.stdout.write(
                        self.style.ERROR(f'    ✗ Error processing {member.username}: {str(e)}')
                    )
        
        self.stdout.write(
            self.style.SUCCESS(
                f'\n✅ Performance profiles ready! '
                f'Created: {total_profiles_created}, Updated: {total_profiles_updated}'
            )
        )
        self.stdout.write(
            self.style.SUCCESS('   AI Resource Optimization widget will now show team performance data!')
        )

    def create_priority_decision_history(self):
        """Create comprehensive priority decision history for ML training (40-60 decisions per board)"""
        self.stdout.write(self.style.NOTICE('Creating Priority Decision History for AI training...'))
        
        # Realistic task contexts for various scenarios
        task_scenarios = {
            'urgent': [
                {
                    'title': 'Critical production bug - payment gateway failing',
                    'description': 'Users unable to complete purchases. Revenue impact: high',
                    'has_due_date': True,
                    'days_until_due': 1,
                    'has_dependencies': False,
                    'complexity': 7,
                    'risk_score': 9,
                    'ai_suggested': 'urgent',
                    'user_chosen': 'urgent',
                    'accepted_suggestion': True,
                    'reasoning': 'Critical revenue-impacting bug with immediate customer impact',
                    'label_names': ['Bug', 'Critical', 'Backend']
                },
                {
                    'title': 'Security vulnerability patch needed urgently',
                    'description': 'CVE-2024-XXXX affects our authentication system',
                    'has_due_date': True,
                    'days_until_due': 2,
                    'has_dependencies': False,
                    'complexity': 8,
                    'risk_score': 9,
                    'ai_suggested': 'urgent',
                    'user_chosen': 'urgent',
                    'accepted_suggestion': True,
                    'reasoning': 'Security vulnerabilities must be patched immediately',
                    'label_names': ['Security', 'Critical']
                },
                {
                    'title': 'Database migration blocking deployment',
                    'description': 'Cannot deploy new features until migration completes',
                    'has_due_date': True,
                    'days_until_due': 1,
                    'has_dependencies': True,
                    'complexity': 6,
                    'risk_score': 8,
                    'ai_suggested': 'high',
                    'user_chosen': 'urgent',
                    'accepted_suggestion': False,
                    'reasoning': 'Blocking deployment is more urgent than AI suggested',
                    'label_names': ['Backend', 'Deployment']
                }
            ],
            'high': [
                {
                    'title': 'Implement OAuth2 authentication flow',
                    'description': 'Key feature for enterprise customers. Due next week',
                    'has_due_date': True,
                    'days_until_due': 7,
                    'has_dependencies': True,
                    'complexity': 8,
                    'risk_score': 6,
                    'ai_suggested': 'high',
                    'user_chosen': 'high',
                    'accepted_suggestion': True,
                    'reasoning': 'Important enterprise feature with clear deadline',
                    'label_names': ['Feature', 'Backend', 'Authentication']
                },
                {
                    'title': 'Performance optimization for dashboard loading',
                    'description': 'Dashboard takes 8+ seconds to load. Multiple user complaints',
                    'has_due_date': True,
                    'days_until_due': 5,
                    'has_dependencies': False,
                    'complexity': 7,
                    'risk_score': 5,
                    'ai_suggested': 'high',
                    'user_chosen': 'high',
                    'accepted_suggestion': True,
                    'reasoning': 'User experience issue affecting all users',
                    'label_names': ['Performance', 'Frontend']
                },
                {
                    'title': 'API rate limiting implementation',
                    'description': 'Prevent API abuse and ensure service stability',
                    'has_due_date': True,
                    'days_until_due': 10,
                    'has_dependencies': False,
                    'complexity': 6,
                    'risk_score': 7,
                    'ai_suggested': 'medium',
                    'user_chosen': 'high',
                    'accepted_suggestion': False,
                    'reasoning': 'Security implications make this higher priority',
                    'label_names': ['Backend', 'Security']
                },
                {
                    'title': 'Fix mobile responsive layout issues',
                    'description': 'Several UI elements broken on mobile devices',
                    'has_due_date': True,
                    'days_until_due': 6,
                    'has_dependencies': False,
                    'complexity': 5,
                    'risk_score': 4,
                    'ai_suggested': 'high',
                    'user_chosen': 'medium',
                    'accepted_suggestion': False,
                    'reasoning': 'Can wait until after more critical features',
                    'label_names': ['UI/UX', 'Mobile', 'Frontend']
                }
            ],
            'medium': [
                {
                    'title': 'Add user preference settings page',
                    'description': 'Allow users to customize notifications and themes',
                    'has_due_date': True,
                    'days_until_due': 14,
                    'has_dependencies': False,
                    'complexity': 5,
                    'risk_score': 3,
                    'ai_suggested': 'medium',
                    'user_chosen': 'medium',
                    'accepted_suggestion': True,
                    'reasoning': 'Nice-to-have feature with reasonable timeline',
                    'label_names': ['Feature', 'Frontend']
                },
                {
                    'title': 'Implement data export functionality',
                    'description': 'Users want to export data to CSV/Excel',
                    'has_due_date': True,
                    'days_until_due': 20,
                    'has_dependencies': False,
                    'complexity': 6,
                    'risk_score': 2,
                    'ai_suggested': 'medium',
                    'user_chosen': 'medium',
                    'accepted_suggestion': True,
                    'reasoning': 'Requested feature with manageable scope',
                    'label_names': ['Feature', 'Backend']
                },
                {
                    'title': 'Refactor legacy code in reporting module',
                    'description': 'Technical debt cleanup to improve maintainability',
                    'has_due_date': False,
                    'days_until_due': None,
                    'has_dependencies': False,
                    'complexity': 7,
                    'risk_score': 3,
                    'ai_suggested': 'low',
                    'user_chosen': 'medium',
                    'accepted_suggestion': False,
                    'reasoning': 'Technical debt is accumulating, should prioritize',
                    'label_names': ['Refactoring', 'Technical Debt']
                },
                {
                    'title': 'Add tooltips to complex UI elements',
                    'description': 'Improve user onboarding with contextual help',
                    'has_due_date': True,
                    'days_until_due': 21,
                    'has_dependencies': False,
                    'complexity': 3,
                    'risk_score': 2,
                    'ai_suggested': 'medium',
                    'user_chosen': 'low',
                    'accepted_suggestion': False,
                    'reasoning': 'Can defer for more important features',
                    'label_names': ['UI/UX', 'Documentation']
                }
            ],
            'low': [
                {
                    'title': 'Update UI color scheme to match new branding',
                    'description': 'Marketing wants updated colors across the app',
                    'has_due_date': True,
                    'days_until_due': 30,
                    'has_dependencies': False,
                    'complexity': 4,
                    'risk_score': 1,
                    'ai_suggested': 'low',
                    'user_chosen': 'low',
                    'accepted_suggestion': True,
                    'reasoning': 'Cosmetic change with no urgency',
                    'label_names': ['UI/UX', 'Design']
                },
                {
                    'title': 'Add Easter egg animation for fun',
                    'description': 'Hidden animation when certain key combo is pressed',
                    'has_due_date': False,
                    'days_until_due': None,
                    'has_dependencies': False,
                    'complexity': 2,
                    'risk_score': 1,
                    'ai_suggested': 'low',
                    'user_chosen': 'low',
                    'accepted_suggestion': True,
                    'reasoning': 'Fun but non-essential feature',
                    'label_names': ['Fun', 'Frontend']
                },
                {
                    'title': 'Update third-party library versions',
                    'description': 'Keep dependencies up to date for security',
                    'has_due_date': False,
                    'days_until_due': None,
                    'has_dependencies': False,
                    'complexity': 3,
                    'risk_score': 2,
                    'ai_suggested': 'low',
                    'user_chosen': 'medium',
                    'accepted_suggestion': False,
                    'reasoning': 'Security updates should be higher priority',
                    'label_names': ['Maintenance', 'Security']
                },
                {
                    'title': 'Write additional unit tests for edge cases',
                    'description': 'Increase code coverage from 75% to 85%',
                    'has_due_date': False,
                    'days_until_due': None,
                    'has_dependencies': False,
                    'complexity': 5,
                    'risk_score': 2,
                    'ai_suggested': 'medium',
                    'user_chosen': 'low',
                    'accepted_suggestion': False,
                    'reasoning': 'Current coverage is acceptable for now',
                    'label_names': ['Testing', 'Quality']
                }
            ]
        }
        
        # Additional mixed scenarios for variety
        mixed_scenarios = [
            {
                'title': 'Implement real-time notifications',
                'description': 'WebSocket-based notifications for task updates',
                'has_due_date': True,
                'days_until_due': 12,
                'has_dependencies': True,
                'complexity': 8,
                'risk_score': 5,
                'ai_suggested': 'high',
                'user_chosen': 'high',
                'accepted_suggestion': True,
                'reasoning': 'Key feature with technical complexity',
                'label_names': ['Feature', 'Backend', 'Real-time']
            },
            {
                'title': 'Add dark mode theme support',
                'description': 'Popular user request for dark theme option',
                'has_due_date': True,
                'days_until_due': 25,
                'has_dependencies': False,
                'complexity': 6,
                'risk_score': 2,
                'ai_suggested': 'medium',
                'user_chosen': 'high',
                'accepted_suggestion': False,
                'reasoning': 'Highly requested by users, boosting priority',
                'label_names': ['Feature', 'UI/UX']
            },
            {
                'title': 'Create API documentation with examples',
                'description': 'Comprehensive API docs for external developers',
                'has_due_date': True,
                'days_until_due': 15,
                'has_dependencies': False,
                'complexity': 4,
                'risk_score': 3,
                'ai_suggested': 'medium',
                'user_chosen': 'medium',
                'accepted_suggestion': True,
                'reasoning': 'Important for developer experience',
                'label_names': ['Documentation', 'API']
            },
            {
                'title': 'Optimize database query performance',
                'description': 'Some queries taking 2-3 seconds, need optimization',
                'has_due_date': True,
                'days_until_due': 8,
                'has_dependencies': False,
                'complexity': 7,
                'risk_score': 6,
                'ai_suggested': 'high',
                'user_chosen': 'high',
                'accepted_suggestion': True,
                'reasoning': 'Performance degradation affecting users',
                'label_names': ['Performance', 'Backend', 'Database']
            },
            {
                'title': 'Implement automated backup system',
                'description': 'Daily automated backups to prevent data loss',
                'has_due_date': True,
                'days_until_due': 10,
                'has_dependencies': False,
                'complexity': 6,
                'risk_score': 8,
                'ai_suggested': 'high',
                'user_chosen': 'urgent',
                'accepted_suggestion': False,
                'reasoning': 'Data protection is critical, elevating priority',
                'label_names': ['Infrastructure', 'Backup', 'Critical']
            },
            {
                'title': 'Add keyboard shortcuts for power users',
                'description': 'Vim-style keyboard navigation for efficiency',
                'has_due_date': False,
                'days_until_due': None,
                'has_dependencies': False,
                'complexity': 5,
                'risk_score': 2,
                'ai_suggested': 'low',
                'user_chosen': 'medium',
                'accepted_suggestion': False,
                'reasoning': 'Power user feature worth prioritizing',
                'label_names': ['Feature', 'UI/UX', 'Accessibility']
            },
            {
                'title': 'Setup monitoring and alerting system',
                'description': 'Monitor application health and get alerts for issues',
                'has_due_date': True,
                'days_until_due': 14,
                'has_dependencies': False,
                'complexity': 7,
                'risk_score': 7,
                'ai_suggested': 'high',
                'user_chosen': 'high',
                'accepted_suggestion': True,
                'reasoning': 'Essential for production reliability',
                'label_names': ['Infrastructure', 'Monitoring']
            },
            {
                'title': 'Implement two-factor authentication',
                'description': 'Add 2FA for enhanced security',
                'has_due_date': True,
                'days_until_due': 18,
                'has_dependencies': False,
                'complexity': 7,
                'risk_score': 6,
                'ai_suggested': 'high',
                'user_chosen': 'high',
                'accepted_suggestion': True,
                'reasoning': 'Security enhancement requested by enterprise clients',
                'label_names': ['Security', 'Authentication', 'Feature']
            },
            {
                'title': 'Create onboarding tutorial for new users',
                'description': 'Interactive walkthrough for first-time users',
                'has_due_date': True,
                'days_until_due': 22,
                'has_dependencies': False,
                'complexity': 5,
                'risk_score': 3,
                'ai_suggested': 'medium',
                'user_chosen': 'medium',
                'accepted_suggestion': True,
                'reasoning': 'Improves user activation rates',
                'label_names': ['Feature', 'Onboarding', 'UI/UX']
            },
            {
                'title': 'Add analytics dashboard for admins',
                'description': 'Visualize user engagement and usage metrics',
                'has_due_date': True,
                'days_until_due': 30,
                'has_dependencies': True,
                'complexity': 8,
                'risk_score': 4,
                'ai_suggested': 'medium',
                'user_chosen': 'high',
                'accepted_suggestion': False,
                'reasoning': 'Business intelligence feature valuable for decision-making',
                'label_names': ['Feature', 'Analytics', 'Dashboard']
            }
        ]
        
        # Create priority decisions for each board
        for board in Board.objects.all():
            self.stdout.write(f'  Creating priority decisions for board: {board.name}')
            
            # Get board members for realistic decision-making
            members = list(board.members.all())
            if not members:
                members = [self.users['admin']]
            
            # Determine number of decisions to create (40-60 per board)
            num_decisions = random.randint(40, 60)
            
            decisions_created = 0
            
            # Get available labels for this board
            available_labels = list(board.labels.all())
            
            # Cycle through scenarios and mixed scenarios
            all_scenarios = []
            for priority_level, scenarios in task_scenarios.items():
                all_scenarios.extend(scenarios)
            all_scenarios.extend(mixed_scenarios)
            
            # Create decisions with varied timestamps over past 6 months
            for i in range(num_decisions):
                # Pick a scenario (cycle through all available scenarios)
                scenario = all_scenarios[i % len(all_scenarios)]
                
                # Add some randomization to make each instance unique
                days_variation = random.randint(-3, 3) if scenario['days_until_due'] else 0
                complexity_variation = random.randint(-1, 1)
                risk_variation = random.randint(-1, 1)
                
                # Calculate decision timestamp (spread over past 180 days)
                days_ago = random.randint(1, 180)
                decision_date = timezone.now() - timedelta(
                    days=days_ago,
                    hours=random.randint(8, 18),  # During work hours
                    minutes=random.randint(0, 59)
                )
                
                # Prepare task context
                adjusted_days_until_due = None
                if scenario['has_due_date']:
                    base_days = scenario['days_until_due']
                    adjusted_days_until_due = max(1, base_days + days_variation)
                
                adjusted_complexity = max(1, min(10, scenario['complexity'] + complexity_variation))
                adjusted_risk = max(1, min(10, scenario['risk_score'] + risk_variation))
                
                # Build task context
                task_context = {
                    'title': scenario['title'],
                    'description': scenario['description'],
                    'has_due_date': scenario['has_due_date'],
                    'complexity': adjusted_complexity,
                    'risk_score': adjusted_risk,
                    'has_dependencies': scenario['has_dependencies']
                }
                
                if adjusted_days_until_due:
                    task_context['days_until_due'] = adjusted_days_until_due
                
                # Prepare AI reasoning
                ai_reasoning = {
                    'factors_considered': [
                        f"Complexity: {adjusted_complexity}/10",
                        f"Risk score: {adjusted_risk}/10",
                        f"Has dependencies: {'Yes' if scenario['has_dependencies'] else 'No'}"
                    ],
                    'explanation': scenario['reasoning']
                }
                
                if adjusted_days_until_due:
                    ai_reasoning['factors_considered'].insert(0, f"Due in {adjusted_days_until_due} days")
                    if adjusted_days_until_due <= 2:
                        ai_reasoning['factors_considered'].append("Imminent deadline")
                    elif adjusted_days_until_due <= 7:
                        ai_reasoning['factors_considered'].append("Approaching deadline")
                
                # Occasionally add label information to reasoning
                if available_labels and random.random() < 0.3:
                    matching_labels = [l for l in available_labels if any(
                        name.lower() in l.name.lower() for name in scenario['label_names']
                    )]
                    if matching_labels:
                        ai_reasoning['factors_considered'].append(
                            f"Labels: {', '.join([l.name for l in matching_labels[:2]])}"
                        )
                
                # Select a team member who made the decision
                decision_maker = random.choice(members)
                
                # Create priority decision using the model's log_decision method
                try:
                    # Determine decision type based on scenario
                    if scenario['accepted_suggestion']:
                        decision_type = 'ai_accepted'
                    else:
                        decision_type = 'ai_rejected'
                    
                    # Get a random existing task from the board for context
                    # (Priority decisions need a task reference)
                    existing_tasks = Task.objects.filter(column__board=board)
                    if not existing_tasks.exists():
                        continue  # Skip if no tasks available
                    
                    sample_task = random.choice(list(existing_tasks))
                    
                    # Create the decision directly
                    decision = PriorityDecision.objects.create(
                        board=board,
                        task=sample_task,  # Reference an existing task
                        suggested_priority=scenario['ai_suggested'],
                        actual_priority=scenario['user_chosen'],
                        previous_priority=None,
                        decision_type=decision_type,
                        decided_by=decision_maker,
                        task_context=task_context,
                        confidence_score=0.85 + random.uniform(-0.15, 0.10),  # Realistic confidence
                        reasoning=ai_reasoning,
                        was_correct=scenario['accepted_suggestion']
                    )
                    
                    # Adjust the timestamp to the past
                    decision.created_at = decision_date
                    decision.save()
                    
                    decisions_created += 1
                    
                except Exception as e:
                    self.stdout.write(
                        self.style.WARNING(f'    Could not create decision: {str(e)}')
                    )
            
            self.stdout.write(
                self.style.SUCCESS(f'    ✓ Created {decisions_created} priority decisions for {board.name}')
            )
            
            # Calculate acceptance rate for reporting
            board_decisions = PriorityDecision.objects.filter(board=board)
            total = board_decisions.count()
            accepted = board_decisions.filter(was_correct=True).count()
            acceptance_rate = (accepted / total * 100) if total > 0 else 0
            
            self.stdout.write(
                f'    📊 AI Suggestion Acceptance Rate: {acceptance_rate:.1f}% ({accepted}/{total})'
            )
        
        # Report summary
        total_decisions = PriorityDecision.objects.count()
        self.stdout.write(
            self.style.SUCCESS(
                f'\n✅ Priority Decision History created! Total: {total_decisions} decisions'
            )
        )
        
        # Report readiness for ML training
        from collections import defaultdict
        boards_with_enough_data = 0
        board_decision_counts = defaultdict(int)
        
        for board in Board.objects.all():
            count = PriorityDecision.objects.filter(board=board).count()
            board_decision_counts[board.name] = count
            if count >= 20:
                boards_with_enough_data += 1
        
        self.stdout.write(
            self.style.SUCCESS(
                f'✅ {boards_with_enough_data} boards ready for ML training (20+ decisions)'
            )
        )
        self.stdout.write(
            self.style.NOTICE(
                '\n💡 Run "python manage.py train_priority_models --all" to train ML models'
            )
        )
    
    def create_scope_baselines(self):
        """Create scope baseline snapshots for all demo boards"""
        self.stdout.write(self.style.NOTICE('\nCreating Scope Baselines for demo boards...'))
        
        # Get admin user for snapshot creation
        admin_user = User.objects.filter(username='admin').first()
        if not admin_user:
            admin_user = User.objects.first()
        
        # Get all demo boards
        boards = Board.objects.filter(
            name__in=['Software Project', 'Marketing Campaign', 'Bug Tracking']
        )
        
        if not boards.exists():
            self.stdout.write(self.style.WARNING('  No demo boards found to create baselines'))
            return
        
        baselines_created = 0
        
        for board in boards:
            try:
                # Create baseline snapshot
                snapshot = board.create_scope_snapshot(
                    user=admin_user,
                    snapshot_type='manual',
                    is_baseline=True,
                    notes=f'Initial baseline snapshot for {board.name}'
                )
                
                baselines_created += 1
                
                self.stdout.write(
                    self.style.SUCCESS(
                        f'  ✓ Created baseline for "{board.name}": '
                        f'{snapshot.total_tasks} tasks, '
                        f'{snapshot.total_complexity_points} complexity points'
                    )
                )
                
            except Exception as e:
                self.stdout.write(
                    self.style.ERROR(f'  ✗ Failed to create baseline for "{board.name}": {str(e)}')
                )
        
        self.stdout.write(
            self.style.SUCCESS(
                f'\n✅ Scope baselines created! Total: {baselines_created} boards'
            )
        )
        self.stdout.write(
            self.style.NOTICE(
                '📝 Run "python manage.py simulate_scope_creep" to test scope tracking'
            )
        )

    def create_budget_roi_demo_data(self):
        """Create budget and ROI tracking demo data"""
        from decimal import Decimal
        
        self.stdout.write(self.style.NOTICE('\nCreating Budget & ROI demo data...'))
        
        # Get demo boards
        software_board = Board.objects.filter(name='Software Project').first()
        marketing_board = Board.objects.filter(name='Marketing Campaign').first()
        bug_board = Board.objects.filter(name='Bug Tracking').first()
        
        if not software_board and not marketing_board and not bug_board:
            self.stdout.write(self.style.WARNING('  No demo boards found'))
            return
        
        boards_to_process = []
        if software_board:
            boards_to_process.append(software_board)
        if marketing_board:
            boards_to_process.append(marketing_board)
        if bug_board:
            boards_to_process.append(bug_board)
        
        for board in boards_to_process:
            # Create Project Budget with different amounts for each board
            budget_amounts = {
                'Software Project': {'budget': Decimal('50000.00'), 'hours': Decimal('800.0')},
                'Marketing Campaign': {'budget': Decimal('25000.00'), 'hours': Decimal('400.0')},
                'Bug Tracking': {'budget': Decimal('30000.00'), 'hours': Decimal('600.0')},
            }
            
            board_config = budget_amounts.get(board.name, {'budget': Decimal('30000.00'), 'hours': Decimal('600.0')})
            
            budget, created = ProjectBudget.objects.get_or_create(
                board=board,
                defaults={
                    'allocated_budget': board_config['budget'],
                    'currency': 'USD',
                    'allocated_hours': board_config['hours'],
                    'warning_threshold': 80,
                    'critical_threshold': 95,
                    'ai_optimization_enabled': True,
                    'created_by': User.objects.first(),
                }
            )
            
            if created:
                self.stdout.write(self.style.SUCCESS(f'  ✓ Created budget for "{board.name}": ${budget.allocated_budget}'))
            
            # Get tasks for this board
            tasks = Task.objects.filter(column__board=board)[:15]  # Limit to first 15 tasks
            
            # Create task costs and time entries
            users = list(User.objects.all()[:5])
            time_entries_created = 0
            task_costs_created = 0
            
            for i, task in enumerate(tasks):
                # Create TaskCost
                estimated_cost = Decimal(random.uniform(100, 2000))
                estimated_hours = Decimal(random.uniform(2, 40))
                
                # Make some tasks over budget for demo
                is_over_budget = i % 4 == 0  # Every 4th task
                variance_factor = Decimal(random.uniform(1.1, 1.4)) if is_over_budget else Decimal(random.uniform(0.7, 1.0))
                
                actual_cost = estimated_cost * variance_factor
                hourly_rate = Decimal(random.choice(['50.00', '75.00', '100.00', '125.00']))
                resource_cost = Decimal(random.uniform(0, 500)) if i % 3 == 0 else Decimal('0.00')
                
                task_cost, created = TaskCost.objects.get_or_create(
                    task=task,
                    defaults={
                        'estimated_cost': estimated_cost,
                        'estimated_hours': estimated_hours,
                        'actual_cost': actual_cost,
                        'hourly_rate': hourly_rate,
                        'resource_cost': resource_cost,
                    }
                )
                
                if created:
                    task_costs_created += 1
                
                # Create multiple time entries for each task
                num_entries = random.randint(2, 5)
                for j in range(num_entries):
                    user = random.choice(users)
                    hours_spent = Decimal(random.uniform(1, 8))
                    work_date = timezone.now().date() - timedelta(days=random.randint(1, 30))
                    
                    descriptions = [
                        'Implemented core functionality',
                        'Fixed bugs and edge cases',
                        'Code review and testing',
                        'Updated documentation',
                        'Refactored for performance',
                        'Integration testing',
                        'UI/UX improvements',
                        'Database optimization',
                        'Security enhancements',
                        'API development',
                    ]
                    
                    TimeEntry.objects.create(
                        task=task,
                        user=user,
                        hours_spent=hours_spent,
                        work_date=work_date,
                        description=random.choice(descriptions)
                    )
                    time_entries_created += 1
            
            self.stdout.write(self.style.SUCCESS(f'  ✓ Created {task_costs_created} task costs for "{board.name}"'))
            self.stdout.write(self.style.SUCCESS(f'  ✓ Created {time_entries_created} time entries for "{board.name}"'))
            
            # Create ROI snapshots
            # Query completed tasks by progress (100% = complete)
            completed_tasks = Task.objects.filter(
                column__board=board,
                progress=100
            ).count()
            
            total_tasks = Task.objects.filter(column__board=board).count()
            
            # Calculate total cost from task costs
            total_cost = sum([tc.get_total_actual_cost() for tc in TaskCost.objects.filter(task__column__board=board)])
            
            # Create initial ROI snapshot
            expected_value = budget.allocated_budget * Decimal('1.5')  # 50% ROI expected
            realized_value = expected_value * Decimal(random.uniform(0.8, 1.2))  # Some variation
            
            roi_percentage = None
            if total_cost > 0:
                roi_percentage = ((realized_value - total_cost) / total_cost) * 100
            
            roi_snapshot = ProjectROI.objects.create(
                board=board,
                expected_value=expected_value,
                realized_value=realized_value,
                total_cost=total_cost,
                roi_percentage=roi_percentage,
                completed_tasks=completed_tasks,
                total_tasks=total_tasks,
                snapshot_date=timezone.now(),
                created_by=User.objects.first(),
                ai_insights={
                    'health': 'Good',
                    'risks': ['Resource allocation needs optimization', 'Some tasks showing cost overruns'],
                    'opportunities': ['Strong completion rate', 'Good ROI projection']
                },
                ai_risk_score=35  # Low-medium risk
            )
            
            self.stdout.write(self.style.SUCCESS(
                f'  ✓ Created ROI snapshot for "{board.name}": ROI {roi_percentage:.1f}%' if roi_percentage else 
                f'  ✓ Created ROI snapshot for "{board.name}"'
            ))
            
            # Create AI recommendations
            recommendations_data = [
                {
                    'type': 'resource_optimization',
                    'title': 'Optimize Senior Developer Allocation',
                    'description': 'Reallocate senior developer time to critical path tasks. Current allocation shows senior developers spending 30% of time on low-priority tasks.',
                    'savings': Decimal('2500.00'),
                    'confidence': 85,
                    'priority': 'high',
                    'reasoning': 'Analysis of time entries shows inefficient resource allocation. Senior developers are spending time on tasks that could be handled by junior team members.',
                },
                {
                    'type': 'timeline_change',
                    'title': 'Extend Sprint by 3 Days to Reduce Overtime',
                    'description': 'Current burn rate suggests team is working overtime. Extending sprint by 3 days would reduce overtime costs and improve quality.',
                    'savings': Decimal('1800.00'),
                    'confidence': 72,
                    'priority': 'medium',
                    'reasoning': 'Time entry patterns show consistent late-night work. Extending timeline would reduce overtime costs while maintaining quality.',
                },
                {
                    'type': 'scope_cut',
                    'title': 'Defer Low-Priority Feature to Next Release',
                    'description': 'Feature "Advanced Reporting" has high cost variance and low business impact. Consider moving to next release.',
                    'savings': Decimal('3200.00'),
                    'confidence': 78,
                    'priority': 'medium',
                    'reasoning': 'Cost-benefit analysis shows this feature consuming 15% of budget with minimal immediate value. Deferring would ensure on-budget completion.',
                },
                {
                    'type': 'efficiency_improvement',
                    'title': 'Implement Code Review Automation',
                    'description': 'Code reviews are taking 20% longer than industry average. Implementing automated checks could save significant time.',
                    'savings': Decimal('1500.00'),
                    'confidence': 65,
                    'priority': 'low',
                    'reasoning': 'Time tracking shows code reviews averaging 3.2 hours per task vs industry standard of 2.5 hours. Automation could improve efficiency.',
                },
            ]
            
            for rec_data in recommendations_data:
                BudgetRecommendation.objects.create(
                    board=board,
                    recommendation_type=rec_data['type'],
                    title=rec_data['title'],
                    description=rec_data['description'],
                    estimated_savings=rec_data.get('savings'),
                    confidence_score=rec_data['confidence'],
                    priority=rec_data['priority'],
                    ai_reasoning=rec_data['reasoning'],
                    status='pending',
                    based_on_patterns={
                        'time_entries_analyzed': time_entries_created,
                        'tasks_analyzed': task_costs_created,
                        'pattern_confidence': rec_data['confidence']
                    }
                )
            
            self.stdout.write(self.style.SUCCESS(f'  ✓ Created {len(recommendations_data)} AI recommendations for "{board.name}"'))
            
            # Create cost patterns
            patterns_data = [
                {
                    'name': 'Backend Tasks Consistently Over Budget',
                    'type': 'task_overrun',
                    'confidence': Decimal('82.5'),
                    'occurrences': 5,
                    'data': {
                        'task_category': 'backend',
                        'average_overrun': '25%',
                        'frequency': 'high',
                        'root_cause': 'Underestimation of complexity'
                    }
                },
                {
                    'name': 'Friday Afternoon Productivity Dip',
                    'type': 'time_pattern',
                    'confidence': Decimal('71.0'),
                    'occurrences': 8,
                    'data': {
                        'time_period': 'Friday 2pm-5pm',
                        'productivity_drop': '35%',
                        'recommendation': 'Schedule less complex tasks for Friday afternoons'
                    }
                },
                {
                    'name': 'UI/UX Tasks Exceeding Time Estimates',
                    'type': 'task_overrun',
                    'confidence': Decimal('76.3'),
                    'occurrences': 6,
                    'data': {
                        'task_category': 'ui_ux',
                        'time_overrun': '40%',
                        'cost_impact': 'medium',
                        'pattern': 'Design iteration cycles not accounted for in estimates'
                    }
                }
            ]
            
            for pattern_data in patterns_data:
                CostPattern.objects.create(
                    board=board,
                    pattern_name=pattern_data['name'],
                    pattern_type=pattern_data['type'],
                    pattern_data=pattern_data['data'],
                    confidence=pattern_data['confidence'],
                    occurrence_count=pattern_data['occurrences'],
                    last_occurred=timezone.now() - timedelta(days=random.randint(1, 7))
                )
            
            self.stdout.write(self.style.SUCCESS(f'  ✓ Created {len(patterns_data)} cost patterns for "{board.name}"'))
        
        self.stdout.write(self.style.SUCCESS('\n✅ Budget & ROI demo data created successfully!'))
        self.stdout.write(self.style.NOTICE('   Navigate to any board and click "Budget & ROI" to explore the feature'))

    def create_conflict_scenarios(self):
        """
        Create realistic conflict scenarios for demonstration:
        - Resource conflicts (same person assigned to overlapping tasks)
        - Schedule conflicts (overdue tasks, unrealistic timelines)
        - Dependency conflicts (blocked tasks)
        """
        self.stdout.write(self.style.NOTICE('\n📋 Creating Conflict Detection Demo Data...'))
        
        # Get test users
        john = User.objects.get(username='john_doe')
        jane = User.objects.get(username='jane_smith')
        robert = User.objects.get(username='robert_johnson')
        alice = User.objects.get(username='alice_williams')
        
        # Get dev organization and board
        dev_org = Organization.objects.filter(name='TechCorp Solutions').first()
        if not dev_org:
            self.stdout.write(self.style.WARNING('  ⚠️ Dev organization not found, skipping conflict scenarios'))
            return
        
        boards = Board.objects.filter(organization=dev_org).order_by('created_at')
        if not boards.exists():
            self.stdout.write(self.style.WARNING('  ⚠️ No boards found, skipping conflict scenarios'))
            return
        
        # Use the first board for conflict scenarios
        board = boards.first()
        
        # Get columns
        todo_column = Column.objects.filter(board=board, name__icontains='To Do').first()
        in_progress_column = Column.objects.filter(board=board, name__icontains='In Progress').first()
        
        if not (todo_column and in_progress_column):
            self.stdout.write(self.style.WARNING('  ⚠️ Required columns not found, skipping conflict scenarios'))
            return
        
        self.stdout.write(f'  Creating conflict scenarios for board: {board.name}')
        
        # Scenario 1: Resource Conflict - John assigned to overlapping tasks
        now = timezone.now()
        task1 = Task.objects.create(
            title="Critical Bug Fix in Authentication System",
            description="Fix security vulnerability in login flow. High priority.",
            column=in_progress_column,
            assigned_to=john,
            created_by=john,
            priority='urgent',
            start_date=now.date(),
            due_date=now + timedelta(days=3),
            progress=30,
            complexity_score=8
        )
        
        task2 = Task.objects.create(
            title="Implement Real-time Notifications Feature",
            description="Build WebSocket-based notification system.",
            column=in_progress_column,
            assigned_to=john,  # Same person!
            created_by=robert,
            priority='high',
            start_date=now.date(),
            due_date=now + timedelta(days=4),
            progress=15,
            complexity_score=9
        )
        
        task3 = Task.objects.create(
            title="Database Performance Optimization",
            description="Optimize slow queries and add indexes.",
            column=in_progress_column,
            assigned_to=john,  # Same person again!
            created_by=jane,
            priority='high',
            start_date=(now + timedelta(days=1)).date(),
            due_date=now + timedelta(days=3),
            progress=0,
            complexity_score=7
        )
        
        self.stdout.write(self.style.SUCCESS(f'    ✓ Created resource conflict scenario: {john.username} overbooked with 3 overlapping tasks'))
        
        # Scenario 2: Schedule Conflict - Overdue task
        overdue_task = Task.objects.create(
            title="Update API Documentation",
            description="Documentation is outdated and needs to be refreshed.",
            column=in_progress_column,
            assigned_to=jane,
            created_by=robert,
            priority='medium',
            start_date=(now - timedelta(days=10)).date(),
            due_date=now - timedelta(days=3),  # Overdue by 3 days
            progress=60,
            complexity_score=4
        )
        
        self.stdout.write(self.style.SUCCESS(f'    ✓ Created schedule conflict: Task overdue by 3 days'))
        
        # Scenario 3: Schedule Conflict - Unrealistic timeline for complex task
        unrealistic_task = Task.objects.create(
            title="Migrate to New Database Architecture",
            description="Complete migration from PostgreSQL to distributed database system.",
            column=todo_column,
            assigned_to=alice,
            created_by=robert,
            priority='high',
            start_date=now.date(),
            due_date=now + timedelta(days=2),  # Only 2 days for complexity 9 task!
            progress=0,
            complexity_score=9
        )
        
        self.stdout.write(self.style.SUCCESS(f'    ✓ Created schedule conflict: Complex task with unrealistic 2-day timeline'))
        
        # Scenario 4: Another resource conflict - Alice overbooked
        task4 = Task.objects.create(
            title="Frontend Performance Audit",
            description="Analyze and improve frontend loading times.",
            column=in_progress_column,
            assigned_to=alice,
            created_by=john,
            priority='medium',
            start_date=now.date(),
            due_date=now + timedelta(days=5),
            progress=25,
            complexity_score=6
        )
        
        task5 = Task.objects.create(
            title="Mobile App Responsive Design Updates",
            description="Fix responsive issues across different screen sizes.",
            column=in_progress_column,
            assigned_to=alice,
            created_by=jane,
            priority='high',
            start_date=now.date(),
            due_date=now + timedelta(days=4),
            progress=10,
            complexity_score=7
        )
        
        self.stdout.write(self.style.SUCCESS(f'    ✓ Created resource conflict scenario: {alice.username} assigned to multiple overlapping tasks'))
        
        # Scenario 5: Dependency Conflict - Task with dependencies in description
        blocked_task = Task.objects.create(
            title="Deploy to Production Environment",
            description="Deploy new features. BLOCKED: Depends on completion of database migration and security audit. Waiting for infrastructure team approval.",
            column=todo_column,
            assigned_to=robert,
            created_by=john,
            priority='urgent',
            start_date=(now - timedelta(days=2)).date(),
            due_date=now + timedelta(days=1),  # Due soon but blocked
            progress=0,
            complexity_score=5
        )
        
        self.stdout.write(self.style.SUCCESS(f'    ✓ Created dependency conflict: Blocked task with dependencies'))
        
        # Scenario 6: More overdue tasks to trigger schedule conflicts
        overdue_task2 = Task.objects.create(
            title="User Feedback Analysis Report",
            description="Compile and analyze Q4 user feedback data.",
            column=in_progress_column,
            assigned_to=jane,
            created_by=alice,
            priority='medium',
            start_date=(now - timedelta(days=7)).date(),
            due_date=now - timedelta(days=1),  # Overdue by 1 day
            progress=75,
            complexity_score=3
        )
        
        overdue_task3 = Task.objects.create(
            title="Security Vulnerability Patch",
            description="Apply security patch for identified vulnerabilities.",
            column=in_progress_column,
            assigned_to=robert,
            created_by=john,
            priority='urgent',
            start_date=(now - timedelta(days=5)).date(),
            due_date=now - timedelta(days=2),  # Overdue by 2 days
            progress=40,
            complexity_score=6
        )
        
        self.stdout.write(self.style.SUCCESS(f'    ✓ Created additional schedule conflicts: 2 more overdue tasks'))
        
        # Summary
        self.stdout.write(self.style.SUCCESS('\n✅ Conflict scenarios created successfully!'))
        self.stdout.write(self.style.NOTICE('  📊 Conflict Summary:'))
        self.stdout.write(self.style.NOTICE('    • Resource Conflicts: 2 scenarios (John with 3 tasks, Alice with 3 tasks)'))
        self.stdout.write(self.style.NOTICE('    • Schedule Conflicts: 4 scenarios (3 overdue tasks, 1 unrealistic timeline)'))
        self.stdout.write(self.style.NOTICE('    • Dependency Conflicts: 1 scenario (blocked deployment task)'))
        self.stdout.write(self.style.NOTICE('  '))
        self.stdout.write(self.style.NOTICE('  🔍 Run conflict detection with:'))
        self.stdout.write(self.style.NOTICE('     python manage.py detect_conflicts --all-boards'))
        self.stdout.write(self.style.NOTICE('  or with AI suggestions:'))
        self.stdout.write(self.style.NOTICE('     python manage.py detect_conflicts --all-boards --with-ai'))

    def create_retrospective_demo_data(self):
        """Create demo data for retrospective features"""
        from decimal import Decimal
        
        self.stdout.write(self.style.NOTICE('\nCreating Retrospective demo data...'))
        
        # Get demo boards
        software_board = Board.objects.filter(name='Software Project').first()
        marketing_board = Board.objects.filter(name='Marketing Campaign').first()
        bug_board = Board.objects.filter(name='Bug Tracking').first()
        
        boards_data = []
        if software_board:
            boards_data.append(('software', software_board))
        if marketing_board:
            boards_data.append(('marketing', marketing_board))
        if bug_board:
            boards_data.append(('bug', bug_board))
        
        if not boards_data:
            self.stdout.write(self.style.WARNING('  No demo boards found'))
            return
        
        now = timezone.now()
        
        for board_type, board in boards_data:
            self.stdout.write(f'\n  Creating retrospectives for {board.name}...')
            
            # Get board members for assignments
            board_members = list(board.members.all())
            if not board_members:
                board_members = [self.users.get('admin', User.objects.first())]
            
            if board_type == 'software':
                # Sprint Retrospective 1 - Completed sprint (30 days ago)
                retro1 = ProjectRetrospective.objects.create(
                    board=board,
                    title='Sprint 23 Retrospective - Authentication Module',
                    retrospective_type='sprint',
                    status='finalized',
                    period_start=(now - timedelta(days=44)).date(),
                    period_end=(now - timedelta(days=30)).date(),
                    metrics_snapshot={
                        'tasks_completed': 18,
                        'tasks_planned': 20,
                        'velocity': 45,
                        'completion_rate': 90,
                        'average_cycle_time': 3.5,
                        'quality_score': 8.5
                    },
                    what_went_well='Team collaboration was excellent with daily standups keeping everyone aligned. Code review process worked smoothly with most PRs reviewed within 4 hours. Authentication module was delivered ahead of schedule with comprehensive test coverage (94%). Documentation was completed alongside implementation.',
                    what_needs_improvement='Testing environment had intermittent issues causing delays. Some tasks had unclear requirements requiring multiple clarification rounds. Tech debt from previous sprint affected implementation speed in some areas.',
                    lessons_learned=[
                        {'lesson': 'Early integration testing catches issues faster', 'priority': 'high', 'category': 'quality'},
                        {'lesson': 'Detailed acceptance criteria reduce rework', 'priority': 'high', 'category': 'planning'},
                        {'lesson': 'Pair programming accelerates complex features', 'priority': 'medium', 'category': 'teamwork'}
                    ],
                    key_achievements=[
                        'Authentication module completed with OAuth2 integration',
                        'Test coverage increased from 78% to 94%',
                        'Zero critical bugs in production',
                        'All sprint goals met ahead of schedule'
                    ],
                    challenges_faced=[
                        {'challenge': 'Testing environment instability', 'impact': 'medium'},
                        {'challenge': 'Unclear requirements for password reset flow', 'impact': 'low'}
                    ],
                    improvement_recommendations=[
                        'Set up dedicated staging environment for testing',
                        'Create requirement checklist template',
                        'Allocate time for tech debt in each sprint'
                    ],
                    overall_sentiment_score=Decimal('0.82'),
                    team_morale_indicator='high',
                    performance_trend='improving',
                    ai_generated_at=now - timedelta(days=30),
                    ai_confidence_score=Decimal('0.88'),
                    created_by=board_members[0],
                    finalized_by=board_members[0],
                    finalized_at=now - timedelta(days=29)
                )
                self.stdout.write(f'    ✓ Created: {retro1.title}')
                
                # Create lessons learned for retro1
                lesson1 = LessonLearned.objects.create(
                    retrospective=retro1,
                    board=board,
                    title='Early Integration Testing Prevents Late-Stage Issues',
                    description='Running integration tests early in the sprint helped us catch authentication flow issues before they became blockers. This saved approximately 2 days of debugging time.',
                    category='quality',
                    priority='high',
                    implementation_status='implemented',
                    implementation_date=(now - timedelta(days=15)).date(),
                    expected_benefit='Reduce bug discovery time by 40%',
                    actual_benefit='Reduced debugging time by 50% in subsequent sprint',
                    ai_suggested=True,
                    ai_confidence=Decimal('0.92'),
                    action_owner=board_members[0]
                )
                
                lesson2 = LessonLearned.objects.create(
                    retrospective=retro1,
                    board=board,
                    title='Detailed Acceptance Criteria Reduce Rework',
                    description='Tasks with comprehensive acceptance criteria had 60% less rework compared to vague requirements. Password reset feature required 3 iterations due to unclear requirements.',
                    category='planning',
                    priority='high',
                    implementation_status='in_progress',
                    expected_benefit='Reduce rework by 50%',
                    ai_suggested=True,
                    ai_confidence=Decimal('0.87'),
                    action_owner=board_members[1] if len(board_members) > 1 else board_members[0]
                )
                
                # Create improvement metrics for retro1
                ImprovementMetric.objects.create(
                    retrospective=retro1,
                    board=board,
                    metric_type='velocity',
                    metric_name='Team Velocity',
                    metric_value=Decimal('45'),
                    previous_value=Decimal('38'),
                    target_value=Decimal('50'),
                    change_amount=Decimal('7'),
                    change_percentage=Decimal('18.42'),
                    trend='improving',
                    unit_of_measure='story points',
                    measured_at=(now - timedelta(days=30)).date()
                )
                
                ImprovementMetric.objects.create(
                    retrospective=retro1,
                    board=board,
                    metric_type='quality',
                    metric_name='Code Coverage',
                    metric_value=Decimal('94'),
                    previous_value=Decimal('78'),
                    target_value=Decimal('90'),
                    change_amount=Decimal('16'),
                    change_percentage=Decimal('20.51'),
                    trend='improving',
                    unit_of_measure='percentage',
                    measured_at=(now - timedelta(days=30)).date()
                )
                
                # Create action items for retro1
                RetrospectiveActionItem.objects.create(
                    retrospective=retro1,
                    board=board,
                    title='Set up Dedicated Staging Environment',
                    description='Configure separate staging environment with production-like data to avoid testing environment conflicts.',
                    action_type='technical_improvement',
                    status='completed',
                    assigned_to=board_members[0],
                    target_completion_date=(now - timedelta(days=20)).date(),
                    actual_completion_date=(now - timedelta(days=18)).date(),
                    priority='high',
                    expected_impact='Eliminate 80% of testing environment issues',
                    actual_impact='Reduced testing blockers from 12 to 2 per sprint',
                    progress_percentage=100,
                    ai_suggested=True,
                    ai_confidence=Decimal('0.91'),
                    related_lesson=lesson1
                )
                
                # Sprint Retrospective 2 - Recent sprint (2 weeks ago)
                retro2 = ProjectRetrospective.objects.create(
                    board=board,
                    title='Sprint 24 Retrospective - Dashboard Development',
                    retrospective_type='sprint',
                    status='reviewed',
                    period_start=(now - timedelta(days=28)).date(),
                    period_end=(now - timedelta(days=14)).date(),
                    metrics_snapshot={
                        'tasks_completed': 22,
                        'tasks_planned': 24,
                        'velocity': 52,
                        'completion_rate': 91.7,
                        'average_cycle_time': 3.2,
                        'quality_score': 9.1
                    },
                    what_went_well='Velocity improved significantly (+15%). Dashboard MVP delivered with all core features. Staging environment eliminated testing delays. Team member onboarding went smoothly with updated documentation. Cross-team collaboration with UX team was productive.',
                    what_needs_improvement='Some features took longer than estimated due to API complexity. One team member was overburdened with code reviews. Real-time updates feature had performance issues requiring optimization. Communication gaps with product team on feature priorities.',
                    lessons_learned=[
                        {'lesson': 'Dedicated staging environment eliminates testing bottlenecks', 'priority': 'high', 'category': 'technical'},
                        {'lesson': 'Distribute code review responsibility across team', 'priority': 'high', 'category': 'process'},
                        {'lesson': 'Early performance testing for real-time features', 'priority': 'medium', 'category': 'quality'}
                    ],
                    key_achievements=[
                        'Dashboard MVP launched to beta users',
                        'Velocity increased by 15% from previous sprint',
                        'Zero testing environment blockers',
                        'Real-time notifications implemented successfully'
                    ],
                    challenges_faced=[
                        {'challenge': 'API integration complexity underestimated', 'impact': 'medium'},
                        {'challenge': 'Code review bottleneck with single reviewer', 'impact': 'medium'},
                        {'challenge': 'Performance issues with WebSocket implementation', 'impact': 'high'}
                    ],
                    improvement_recommendations=[
                        'Add buffer time for complex API integrations',
                        'Rotate code review duties among senior developers',
                        'Include performance testing in definition of done',
                        'Schedule weekly sync with product team'
                    ],
                    overall_sentiment_score=Decimal('0.78'),
                    team_morale_indicator='high',
                    performance_trend='improving',
                    previous_retrospective=retro1,
                    ai_generated_at=now - timedelta(days=14),
                    ai_confidence_score=Decimal('0.85'),
                    created_by=board_members[0]
                )
                self.stdout.write(f'    ✓ Created: {retro2.title}')
                
                # Create lessons and action items for retro2
                lesson3 = LessonLearned.objects.create(
                    retrospective=retro2,
                    board=board,
                    title='Staging Environment Eliminates Testing Bottlenecks',
                    description='Dedicated staging environment completely eliminated testing conflicts. Zero environment-related delays this sprint vs. 5 incidents in previous sprint.',
                    category='technical',
                    priority='high',
                    implementation_status='validated',
                    implementation_date=(now - timedelta(days=25)).date(),
                    validation_date=(now - timedelta(days=14)).date(),
                    expected_benefit='Eliminate testing environment issues',
                    actual_benefit='100% reduction in testing blockers, saved ~8 hours of debugging time',
                    success_metrics=[
                        {'metric': 'environment_issues', 'before': 5, 'after': 0},
                        {'metric': 'debugging_hours', 'before': 8, 'after': 0}
                    ],
                    ai_suggested=False,
                    action_owner=board_members[0]
                )
                
                RetrospectiveActionItem.objects.create(
                    retrospective=retro2,
                    board=board,
                    title='Implement Code Review Rotation Policy',
                    description='Create rotation schedule for code reviews to distribute workload and knowledge sharing among all senior developers.',
                    action_type='process_change',
                    status='in_progress',
                    assigned_to=board_members[1] if len(board_members) > 1 else board_members[0],
                    target_completion_date=(now + timedelta(days=7)).date(),
                    priority='high',
                    expected_impact='Balance review workload, improve knowledge sharing',
                    progress_percentage=60,
                    progress_notes='Draft rotation schedule created, gathering team feedback',
                    ai_suggested=True,
                    ai_confidence=Decimal('0.88')
                )
                
                # Sprint Retrospective 3 - Current/ongoing sprint
                retro3 = ProjectRetrospective.objects.create(
                    board=board,
                    title='Sprint 25 Mid-Sprint Checkpoint',
                    retrospective_type='sprint',
                    status='draft',
                    period_start=(now - timedelta(days=7)).date(),
                    period_end=now.date(),
                    metrics_snapshot={
                        'tasks_completed': 8,
                        'tasks_planned': 26,
                        'tasks_in_progress': 12,
                        'velocity_tracking': 24,
                        'projected_velocity': 55,
                        'completion_rate': 30.8
                    },
                    what_went_well='Code review rotation working well. API documentation improvements helping new team members. Performance optimization efforts showing good results.',
                    what_needs_improvement='Still tracking preliminary data for ongoing sprint.',
                    team_morale_indicator='high',
                    performance_trend='improving',
                    previous_retrospective=retro2,
                    created_by=board_members[0]
                )
                self.stdout.write(f'    ✓ Created: {retro3.title}')
                
            elif board_type == 'marketing':
                # Marketing Campaign Retrospective
                retro1 = ProjectRetrospective.objects.create(
                    board=board,
                    title='Q3 Campaign Retrospective',
                    retrospective_type='quarterly',
                    status='finalized',
                    period_start=(now - timedelta(days=90)).date(),
                    period_end=(now - timedelta(days=7)).date(),
                    metrics_snapshot={
                        'campaigns_completed': 12,
                        'engagement_rate': 4.8,
                        'conversion_rate': 2.3,
                        'roi': 285,
                        'leads_generated': 1847,
                        'content_pieces': 45
                    },
                    what_went_well='Social media engagement increased by 67%. Video content performed exceptionally well with 3x engagement vs. static posts. Email campaigns had 25% higher open rates with personalized subject lines. Cross-functional collaboration with sales team improved lead quality.',
                    what_needs_improvement='Content approval process too slow, creating bottlenecks. Analytics reporting scattered across multiple tools. Some campaigns launched without proper A/B testing. Budget tracking needs better real-time visibility.',
                    lessons_learned=[
                        {'lesson': 'Video content drives 3x engagement', 'priority': 'high', 'category': 'other'},
                        {'lesson': 'Personalization improves email performance', 'priority': 'high', 'category': 'customer'},
                        {'lesson': 'Early sales alignment improves lead quality', 'priority': 'medium', 'category': 'communication'}
                    ],
                    key_achievements=[
                        '67% increase in social media engagement',
                        'Generated 1,847 qualified leads (45% above target)',
                        '285% ROI on campaign investments',
                        'Launched 12 successful campaigns across all channels'
                    ],
                    challenges_faced=[
                        {'challenge': 'Slow content approval workflow', 'impact': 'high'},
                        {'challenge': 'Fragmented analytics tools', 'impact': 'medium'},
                        {'challenge': 'Insufficient A/B testing', 'impact': 'medium'}
                    ],
                    improvement_recommendations=[
                        'Streamline content approval with automated workflow',
                        'Consolidate analytics into unified dashboard',
                        'Make A/B testing mandatory for all campaigns',
                        'Implement real-time budget tracking dashboard'
                    ],
                    overall_sentiment_score=Decimal('0.85'),
                    team_morale_indicator='excellent',
                    performance_trend='improving',
                    ai_generated_at=now - timedelta(days=7),
                    ai_confidence_score=Decimal('0.89'),
                    created_by=board_members[0],
                    finalized_by=board_members[0],
                    finalized_at=now - timedelta(days=5)
                )
                self.stdout.write(f'    ✓ Created: {retro1.title}')
                
                # Create lessons for marketing
                LessonLearned.objects.create(
                    retrospective=retro1,
                    board=board,
                    title='Video Content Drives 3x Higher Engagement',
                    description='Analysis shows video posts generate 3x more engagement than static images. Video content also has 2x higher shareability and longer average view time.',
                    category='other',
                    priority='high',
                    implementation_status='in_progress',
                    expected_benefit='Increase overall engagement by 40%',
                    success_metrics=[
                        {'metric': 'engagement_rate', 'before': 2.8, 'after': 4.8},
                        {'metric': 'video_vs_static', 'ratio': 3.0}
                    ],
                    ai_suggested=True,
                    ai_confidence=Decimal('0.94'),
                    action_owner=board_members[0]
                )
                
                ImprovementMetric.objects.create(
                    retrospective=retro1,
                    board=board,
                    metric_type='customer_satisfaction',
                    metric_name='Social Media Engagement Rate',
                    metric_value=Decimal('4.8'),
                    previous_value=Decimal('2.8'),
                    target_value=Decimal('5.0'),
                    change_amount=Decimal('2.0'),
                    change_percentage=Decimal('71.43'),
                    trend='improving',
                    unit_of_measure='percentage',
                    measured_at=(now - timedelta(days=7)).date()
                )
                
                RetrospectiveActionItem.objects.create(
                    retrospective=retro1,
                    board=board,
                    title='Increase Video Content Production to 60%',
                    description='Shift content mix to 60% video, 40% static/text based on engagement data. Partner with video production team for resources.',
                    action_type='process_change',
                    status='in_progress',
                    assigned_to=board_members[0],
                    target_completion_date=(now + timedelta(days=30)).date(),
                    priority='high',
                    expected_impact='Increase overall engagement by 40-50%',
                    progress_percentage=35,
                    progress_notes='Video production capacity increased, training content team',
                    ai_suggested=True,
                    ai_confidence=Decimal('0.92')
                )
                
            elif board_type == 'bug':
                # Bug Tracking Retrospective
                retro1 = ProjectRetrospective.objects.create(
                    board=board,
                    title='Bug Resolution Performance Review',
                    retrospective_type='milestone',
                    status='finalized',
                    period_start=(now - timedelta(days=60)).date(),
                    period_end=(now - timedelta(days=10)).date(),
                    metrics_snapshot={
                        'bugs_resolved': 87,
                        'critical_bugs': 5,
                        'average_resolution_time': 2.3,
                        'first_response_time': 0.8,
                        'reopened_bugs': 7,
                        'regression_rate': 8
                    },
                    what_went_well='Response time improved significantly with on-call rotation. Critical bugs resolved within 4 hours average. Root cause analysis prevented recurring issues. Bug triage process working effectively.',
                    what_needs_improvement='Regression rate still higher than target. Some bugs lack sufficient reproduction steps. Documentation of fixes could be better. Need better tooling for bug tracking analytics.',
                    lessons_learned=[
                        {'lesson': 'Root cause analysis prevents recurrence', 'priority': 'high', 'category': 'quality'},
                        {'lesson': 'On-call rotation improves response time', 'priority': 'high', 'category': 'process'},
                        {'lesson': 'Detailed reproduction steps accelerate fixes', 'priority': 'medium', 'category': 'process'}
                    ],
                    key_achievements=[
                        'Resolved 87 bugs (12% above target)',
                        'Critical bug response time under 1 hour',
                        'Reduced average resolution time by 30%',
                        'Implemented effective triage process'
                    ],
                    challenges_faced=[
                        {'challenge': 'Higher than expected regression rate', 'impact': 'medium'},
                        {'challenge': 'Inconsistent bug report quality', 'impact': 'medium'}
                    ],
                    improvement_recommendations=[
                        'Expand automated regression testing',
                        'Create bug report template with required fields',
                        'Implement fix documentation checklist',
                        'Set up bug analytics dashboard'
                    ],
                    overall_sentiment_score=Decimal('0.76'),
                    team_morale_indicator='moderate',
                    performance_trend='improving',
                    ai_generated_at=now - timedelta(days=10),
                    ai_confidence_score=Decimal('0.84'),
                    created_by=board_members[0],
                    finalized_by=board_members[0],
                    finalized_at=now - timedelta(days=8)
                )
                self.stdout.write(f'    ✓ Created: {retro1.title}')
                
                LessonLearned.objects.create(
                    retrospective=retro1,
                    board=board,
                    title='Root Cause Analysis Prevents Bug Recurrence',
                    description='Implementing thorough root cause analysis for all critical bugs reduced recurrence rate from 15% to 5%. Time invested in analysis pays off long-term.',
                    category='quality',
                    priority='high',
                    implementation_status='implemented',
                    implementation_date=(now - timedelta(days=45)).date(),
                    expected_benefit='Reduce bug recurrence by 60%',
                    actual_benefit='Reduced recurrence from 15% to 5% (67% reduction)',
                    success_metrics=[
                        {'metric': 'recurrence_rate', 'before': 15, 'after': 5}
                    ],
                    ai_suggested=True,
                    ai_confidence=Decimal('0.91'),
                    action_owner=board_members[0]
                )
                
                ImprovementMetric.objects.create(
                    retrospective=retro1,
                    board=board,
                    metric_type='cycle_time',
                    metric_name='Average Bug Resolution Time',
                    metric_value=Decimal('2.3'),
                    previous_value=Decimal('3.3'),
                    target_value=Decimal('2.0'),
                    change_amount=Decimal('-1.0'),
                    change_percentage=Decimal('-30.30'),
                    trend='improving',
                    unit_of_measure='days',
                    higher_is_better=False,
                    measured_at=(now - timedelta(days=10)).date()
                )
        
        # Count totals
        total_retrospectives = ProjectRetrospective.objects.filter(
            board__in=[b for _, b in boards_data]
        ).count()
        total_lessons = LessonLearned.objects.filter(
            board__in=[b for _, b in boards_data]
        ).count()
        total_metrics = ImprovementMetric.objects.filter(
            board__in=[b for _, b in boards_data]
        ).count()
        total_actions = RetrospectiveActionItem.objects.filter(
            board__in=[b for _, b in boards_data]
        ).count()
        
        self.stdout.write(self.style.SUCCESS('\n✅ Retrospective demo data created!'))
        self.stdout.write(self.style.SUCCESS(f'   Retrospectives: {total_retrospectives}'))
        self.stdout.write(self.style.SUCCESS(f'   Lessons Learned: {total_lessons}'))
        self.stdout.write(self.style.SUCCESS(f'   Improvement Metrics: {total_metrics}'))
        self.stdout.write(self.style.SUCCESS(f'   Action Items: {total_actions}'))



