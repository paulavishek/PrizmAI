"""
Management command to create demo organization with boards and personas.

Structure:
- 1 Organization: "Demo - Acme Corporation"
- 3 Boards: Software Development, Marketing Campaign, Bug Tracking
- 3 Personas: Alex Chen (Admin), Sam Rivera (Member), Jordan Taylor (Viewer)

Usage:
    python manage.py create_demo_organization
"""

from django.core.management.base import BaseCommand
from django.contrib.auth.models import User
from accounts.models import Organization, UserProfile
from kanban.models import Board, Column
from kanban.permission_models import Role, BoardMembership
from django.utils import timezone
from django.db import transaction


class Command(BaseCommand):
    help = 'Create demo organization with boards and personas'

    def add_arguments(self, parser):
        parser.add_argument(
            '--reset',
            action='store_true',
            help='Delete existing demo org and recreate from scratch',
        )

    def handle(self, *args, **options):
        self.stdout.write('='*80)
        self.stdout.write('CREATING DEMO ORGANIZATION')
        self.stdout.write('='*80)
        
        try:
            with transaction.atomic():
                # Step 1: Handle reset if requested
                if options['reset']:
                    self.reset_demo_data()
                
                # Step 2: Create demo organization
                demo_org = self.create_demo_organization()
                
                # Step 3: Create demo users (personas)
                personas = self.create_demo_personas(demo_org)
                
                # Step 4: Create demo boards
                boards = self.create_demo_boards(demo_org, personas)
                
                # Step 5: Assign board memberships
                self.assign_board_memberships(boards, personas)
                
                # Success summary
                self.stdout.write('')
                self.stdout.write(self.style.SUCCESS('='*80))
                self.stdout.write(self.style.SUCCESS('✓ DEMO ORGANIZATION SETUP COMPLETE'))
                self.stdout.write(self.style.SUCCESS('='*80))
                self.stdout.write(f'  Organization: {demo_org.name}')
                self.stdout.write(f'  Boards: {len(boards)}')
                self.stdout.write(f'  Personas: {len(personas)}')
                self.stdout.write('')
                self.stdout.write('Next steps:')
                self.stdout.write('  1. Run: python manage.py populate_demo_data')
                self.stdout.write('  2. Test demo mode: Visit /demo/ in your browser')
                self.stdout.write('')
                
        except Exception as e:
            self.stdout.write(self.style.ERROR(f'✗ Error: {str(e)}'))
            import traceback
            traceback.print_exc()
            raise

    def reset_demo_data(self):
        """Delete existing demo organization and all related data"""
        self.stdout.write('\nResetting demo data...')
        
        # Find demo organization
        demo_org = Organization.objects.filter(is_demo=True).first()
        
        if demo_org:
            self.stdout.write(f'  Deleting demo organization: {demo_org.name}')
            
            # First, update all demo personas to point to no organization
            # This prevents foreign key constraint errors
            demo_emails = [
                'alex.chen@demo.prizmai.local',
                'sam.rivera@demo.prizmai.local',
                'jordan.taylor@demo.prizmai.local'
            ]
            
            for email in demo_emails:
                try:
                    user = User.objects.get(email=email)
                    if hasattr(user, 'profile'):
                        user.profile.organization = None
                        user.profile.save()
                except User.DoesNotExist:
                    pass
            
            # Now safe to delete organization (will cascade to boards, tasks, etc.)
            demo_org.delete()
            
            self.stdout.write(self.style.SUCCESS('  ✓ Demo data reset complete'))
        else:
            self.stdout.write('  No demo organization found (clean slate)')

    def create_demo_organization(self):
        """Create single demo organization"""
        self.stdout.write('\n1. Creating demo organization...')
        
        # Check if demo user exists to use as creator
        # If not, use first superuser
        creator = User.objects.filter(is_superuser=True).first()
        if not creator:
            self.stdout.write(self.style.ERROR('  ✗ No superuser found!'))
            self.stdout.write('  Please create a superuser first: python manage.py createsuperuser')
            raise Exception('No superuser available')
        
        demo_org, created = Organization.objects.get_or_create(
            name='Demo - Acme Corporation',
            defaults={
                'domain': 'demo.prizmai.local',
                'is_demo': True,
                'created_by': creator,
                'created_at': timezone.now()
            }
        )
        
        if created:
            self.stdout.write(self.style.SUCCESS(f'  ✓ Created: {demo_org.name}'))
        else:
            self.stdout.write(self.style.WARNING(f'  ! Already exists: {demo_org.name}'))
            # Update is_demo flag if it wasn't set
            if not demo_org.is_demo:
                demo_org.is_demo = True
                demo_org.save()
                self.stdout.write(self.style.SUCCESS('  ✓ Updated is_demo flag'))
        
        return demo_org

    def create_demo_personas(self, demo_org):
        """Create 3 demo personas as members of demo org"""
        self.stdout.write('\n2. Creating demo personas...')
        
        personas_data = [
            {
                'username': 'alex_chen_demo',
                'email': 'alex.chen@demo.prizmai.local',
                'first_name': 'Alex',
                'last_name': 'Chen',
                'org_role': 'admin',
                'skills': [
                    {'name': 'Project Management', 'level': 'Expert'},
                    {'name': 'Agile/Scrum', 'level': 'Expert'},
                    {'name': 'Leadership', 'level': 'Advanced'},
                ],
                'weekly_capacity': 40,
            },
            {
                'username': 'sam_rivera_demo',
                'email': 'sam.rivera@demo.prizmai.local',
                'first_name': 'Sam',
                'last_name': 'Rivera',
                'org_role': 'member',
                'skills': [
                    {'name': 'Python', 'level': 'Expert'},
                    {'name': 'JavaScript', 'level': 'Advanced'},
                    {'name': 'Django', 'level': 'Expert'},
                    {'name': 'React', 'level': 'Intermediate'},
                ],
                'weekly_capacity': 40,
            },
            {
                'username': 'jordan_taylor_demo',
                'email': 'jordan.taylor@demo.prizmai.local',
                'first_name': 'Jordan',
                'last_name': 'Taylor',
                'org_role': 'viewer',
                'skills': [
                    {'name': 'Strategic Planning', 'level': 'Expert'},
                    {'name': 'Business Analysis', 'level': 'Advanced'},
                ],
                'weekly_capacity': 40,
            }
        ]
        
        personas = []
        
        for persona_data in personas_data:
            # Create or get user
            user, created = User.objects.get_or_create(
                email=persona_data['email'],
                defaults={
                    'username': persona_data['username'],
                    'first_name': persona_data['first_name'],
                    'last_name': persona_data['last_name'],
                    'is_active': True,
                }
            )
            
            if created:
                # Set unusable password (demo users can't login directly)
                user.set_unusable_password()
                user.save()
                self.stdout.write(self.style.SUCCESS(f'  ✓ Created: {user.get_full_name()} ({user.email})'))
            else:
                self.stdout.write(self.style.WARNING(f'  ! Already exists: {user.get_full_name()}'))
            
            # Create or update user profile
            profile, profile_created = UserProfile.objects.get_or_create(
                user=user,
                defaults={
                    'organization': demo_org,
                    'is_admin': (persona_data['org_role'] == 'admin'),
                    'skills': persona_data['skills'],
                    'weekly_capacity_hours': persona_data['weekly_capacity'],
                    'completed_wizard': True,  # Skip wizard for demo users
                    'wizard_completed_at': timezone.now(),
                }
            )
            
            if not profile_created:
                # Update existing profile
                profile.organization = demo_org
                profile.is_admin = (persona_data['org_role'] == 'admin')
                profile.skills = persona_data['skills']
                profile.weekly_capacity_hours = persona_data['weekly_capacity']
                profile.completed_wizard = True
                profile.save()
            
            personas.append(user)
        
        self.stdout.write(self.style.SUCCESS(f'  ✓ Created {len(personas)} personas'))
        return personas

    def create_demo_boards(self, demo_org, personas):
        """Create 3 demo boards in the demo org"""
        self.stdout.write('\n3. Creating demo boards...')
        
        # Get Alex Chen as the board creator (admin)
        creator = personas[0]  # Alex Chen
        
        boards_data = [
            {
                'name': 'Software Development',
                'description': 'Track features, sprints, and releases for our product. Showcase AI-powered task management and burndown forecasting.',
                'columns': ['To Do', 'In Progress', 'Done'],
            },
            {
                'name': 'Marketing Campaign',
                'description': 'Plan and execute Q1 2025 marketing initiatives. Demonstrate collaboration and approval workflows.',
                'columns': ['To Do', 'In Progress', 'Done'],
            },
            {
                'name': 'Bug Tracking',
                'description': 'Triage and resolve customer-reported issues. Highlight priority management and resource leveling.',
                'columns': ['To Do', 'In Progress', 'Done'],
            }
        ]
        
        boards = []
        
        for board_data in boards_data:
            # Create board
            board, created = Board.objects.get_or_create(
                name=board_data['name'],
                organization=demo_org,
                defaults={
                    'description': board_data['description'],
                    'is_official_demo_board': True,
                    'created_by': creator,
                    'created_at': timezone.now(),
                }
            )
            
            if created:
                self.stdout.write(self.style.SUCCESS(f'  ✓ Created board: {board.name}'))
                
                # Create columns for this board
                for position, column_name in enumerate(board_data['columns']):
                    Column.objects.create(
                        board=board,
                        name=column_name,
                        position=position
                    )
                    self.stdout.write(f'    - Added column: {column_name}')
            else:
                self.stdout.write(self.style.WARNING(f'  ! Already exists: {board.name}'))
                # Ensure is_official_demo_board flag is set
                if not board.is_official_demo_board:
                    board.is_official_demo_board = True
                    board.save()
            
            boards.append(board)
        
        return boards

    def assign_board_memberships(self, boards, personas):
        """Assign all personas to all boards with appropriate roles"""
        self.stdout.write('\n4. Assigning board memberships...')
        
        # Role mapping based on persona
        role_map = {
            'alex_chen_demo': 'Admin',      # Alex Chen - Admin
            'sam_rivera_demo': 'Editor',    # Sam Rivera - Member/Editor
            'jordan_taylor_demo': 'Viewer', # Jordan Taylor - Viewer
        }
        
        total_assigned = 0
        
        for board in boards:
            for persona in personas:
                # Add persona to board members
                if persona not in board.members.all():
                    board.members.add(persona)
                    total_assigned += 1
                
                # Get or create role for this persona
                role_name = role_map.get(persona.username, 'Editor')
                role = Role.objects.filter(
                    organization=board.organization,
                    name=role_name
                ).first()
                
                if role:
                    # Create BoardMembership with role
                    BoardMembership.objects.get_or_create(
                        board=board,
                        user=persona,
                        defaults={'role': role}
                    )
        
        self.stdout.write(self.style.SUCCESS(f'  ✓ Assigned {len(personas)} personas to {len(boards)} boards'))
        self.stdout.write(f'    Total board memberships: {total_assigned}')
