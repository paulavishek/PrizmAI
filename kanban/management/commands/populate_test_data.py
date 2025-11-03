import random
from datetime import datetime, timedelta
from django.core.management.base import BaseCommand
from django.contrib.auth.models import User
from django.utils import timezone
from accounts.models import Organization, UserProfile
from kanban.models import (
    Board, Column, TaskLabel, Task, Comment, TaskActivity,
    ResourceDemandForecast, TeamCapacityAlert, WorkloadDistributionRecommendation
)
from kanban.stakeholder_models import (
    ProjectStakeholder, StakeholderTaskInvolvement, 
    StakeholderEngagementRecord, EngagementMetrics, StakeholderTag
)
from messaging.models import ChatRoom, ChatMessage

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
        
        # Create chat room demo data
        self.create_chat_rooms_demo_data()
        
        # Fix Gantt chart data with dynamic dates relative to current date
        self.stdout.write(self.style.NOTICE('\nFixing Gantt chart demo data with dynamic dates...'))
        from django.core.management import call_command
        call_command('fix_gantt_demo_data')
        
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
        self.stdout.write(self.style.SUCCESS('✅ Chat Rooms - Multiple chat rooms with messages'))
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

