"""
Management command to create demo organization with board and personas.

Structure:
- 1 Organization: "Demo - Acme Corporation"
- 1 Board: Software Development (5 columns: Backlog, To Do, In Progress, In Review, Done)
- 3 Personas: Priya Sharma (Owner/Backend), Marcus Chen (Member/Frontend), Elena Vasquez (Member/DevOps-QA)

Usage:
    python manage.py create_demo_organization
"""

from datetime import timedelta

from django.core.management.base import BaseCommand
from django.contrib.auth.models import User
from accounts.models import Organization, UserProfile
from kanban.models import Board, Column, BoardMembership
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
            # Step 1: Handle reset if requested (OUTSIDE transaction)
            if options['reset']:
                self.reset_demo_data()
            
            with transaction.atomic():
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
                self.stdout.write(self.style.SUCCESS('[OK] DEMO ORGANIZATION SETUP COMPLETE'))
                self.stdout.write(self.style.SUCCESS('='*80))
                self.stdout.write(f'  Organization: {demo_org.name}')
                self.stdout.write(f'  Boards: {len(boards)}')
                self.stdout.write(f'  Personas: {len(personas)}')
                self.stdout.write('')
                self.stdout.write('Next steps:')
                self.stdout.write('  1. Run: python manage.py populate_all_demo_data --reset')
                self.stdout.write('  2. Visit /demo/ in your browser to see the seeded board')
                self.stdout.write('')
                
        except Exception as e:
            self.stdout.write(self.style.ERROR(f'[FAIL] Error: {str(e)}'))
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
            
            # Delete demo users entirely (including their profiles)
            # This must be done first as Users may have references.
            # Includes legacy usernames so a half-migrated DB is cleaned up.
            demo_emails = [
                'priya.sharma@demo.prizmai.local',
                'marcus.chen@demo.prizmai.local',
                'elena.vasquez@demo.prizmai.local',
                # Legacy - remove old personas if still present
                'alex.chen@demo.prizmai.local',
                'sam.rivera@demo.prizmai.local',
                'jordan.taylor@demo.prizmai.local',
            ]
            legacy_usernames = ['alex_chen_demo', 'sam_rivera_demo', 'jordan_taylor_demo']

            for email in demo_emails:
                try:
                    user = User.objects.get(email=email)
                    self.stdout.write(f'  Deleting user: {user.email}')
                    user.delete()
                except User.DoesNotExist:
                    pass

            for uname in legacy_usernames:
                for user in User.objects.filter(username=uname):
                    self.stdout.write(f'  Deleting legacy user: {user.username}')
                    user.delete()
            
            # Now delete organization (will cascade to boards, tasks, etc.)
            self.stdout.write(f'  Deleting organization and all related data...')
            demo_org.delete()
            
            self.stdout.write(self.style.SUCCESS('  [OK] Demo data reset complete'))
        else:
            self.stdout.write('  No demo organization found (clean slate)')

    def create_demo_organization(self):
        """Create single demo organization"""
        self.stdout.write('\n1. Creating demo organization...')
        
        # Check if demo user exists to use as creator
        # If not, use first superuser
        creator = User.objects.filter(is_superuser=True).first()
        if not creator:
            self.stdout.write(self.style.ERROR('  [FAIL] No superuser found!'))
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
            self.stdout.write(self.style.SUCCESS(f'  [OK] Created: {demo_org.name}'))
        else:
            self.stdout.write(self.style.WARNING(f'  ! Already exists: {demo_org.name}'))
            # Update is_demo flag if it wasn't set
            if not demo_org.is_demo:
                demo_org.is_demo = True
                demo_org.save()
                self.stdout.write(self.style.SUCCESS('  [OK] Updated is_demo flag'))
        
        return demo_org

    def create_demo_personas(self, demo_org):
        """Create 3 demo personas as members of demo org"""
        self.stdout.write('\n2. Creating demo personas...')
        
        personas_data = [
            {
                'username': 'priya.sharma',
                'email': 'priya.sharma@demo.prizmai.local',
                'first_name': 'Priya',
                'last_name': 'Sharma',
                'org_role': 'admin',   # Owner of the Software Development board
                'skills': [
                    {'name': 'Python', 'level': 'Expert'},
                    {'name': 'Django', 'level': 'Expert'},
                    {'name': 'REST APIs', 'level': 'Expert'},
                    {'name': 'PostgreSQL', 'level': 'Advanced'},
                    {'name': 'System Architecture', 'level': 'Advanced'},
                ],
                'weekly_capacity': 40,
            },
            {
                'username': 'marcus.chen',
                'email': 'marcus.chen@demo.prizmai.local',
                'first_name': 'Marcus',
                'last_name': 'Chen',
                'org_role': 'member',  # Frontend / UX
                'skills': [
                    {'name': 'JavaScript', 'level': 'Expert'},
                    {'name': 'React', 'level': 'Advanced'},
                    {'name': 'CSS / Tailwind', 'level': 'Advanced'},
                    {'name': 'UX Design', 'level': 'Advanced'},
                    {'name': 'Accessibility (WCAG)', 'level': 'Intermediate'},
                ],
                'weekly_capacity': 40,
            },
            {
                'username': 'elena.vasquez',
                'email': 'elena.vasquez@demo.prizmai.local',
                'first_name': 'Elena',
                'last_name': 'Vasquez',
                'org_role': 'member',  # DevOps / QA
                'skills': [
                    {'name': 'Docker / Containers', 'level': 'Expert'},
                    {'name': 'CI/CD (GitHub Actions)', 'level': 'Expert'},
                    {'name': 'Google Cloud Platform', 'level': 'Advanced'},
                    {'name': 'Test Automation', 'level': 'Advanced'},
                    {'name': 'Security Scanning', 'level': 'Intermediate'},
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
                user.set_password('DemoUser@2026')
                user.save()
                self.stdout.write(self.style.SUCCESS(f'  [OK] Created: {user.get_full_name()} ({user.email})'))
            else:
                user.set_password('DemoUser@2026')
                user.save()
                self.stdout.write(self.style.WARNING(f'  ! Already exists: {user.get_full_name()} - password reset'))

            # Create or update user profile
            profile, profile_created = UserProfile.objects.get_or_create(
                user=user,
                defaults={
                    'organization': demo_org,
                    'is_admin': (persona_data['org_role'] == 'admin'),
                    'is_demo_account': True,
                    'skills': persona_data['skills'],
                    'weekly_capacity_hours': persona_data['weekly_capacity'],
                    'completed_wizard': True,  # Skip wizard for demo users
                    'wizard_completed_at': timezone.now(),
                }
            )

            if not profile_created:
                profile.organization = demo_org
                profile.is_admin = (persona_data['org_role'] == 'admin')
                profile.is_demo_account = True
                profile.skills = persona_data['skills']
                profile.weekly_capacity_hours = persona_data['weekly_capacity']
                profile.completed_wizard = True
                profile.save()
            
            personas.append(user)
        
        self.stdout.write(self.style.SUCCESS(f'  [OK] Created {len(personas)} personas'))
        return personas

    def create_demo_boards(self, demo_org, personas):
        """Create demo boards in the demo org"""
        self.stdout.write('\n3. Creating demo boards...')

        # Priya Sharma is the Owner of the Software Development board
        creator = personas[0]  # Priya Sharma

        boards_data = [
            {
                'name': 'Software Development',
                'description': 'Track features, sprints, and releases for our core product platform.',
                'columns': ['Backlog', 'To Do', 'In Progress', 'In Review', 'Done'],
            },
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
                    'is_seed_demo_data': True,
                    'created_by': creator,
                    'owner': creator,
                    'num_phases': 4,
                    'project_type': 'product_tech',
                    'project_type_confirmed': True,
                    'created_at': timezone.now(),
                    'project_deadline': (timezone.now() + timedelta(days=56)).date(),
                }
            )

            # Always ensure the flags & owner stay correct on re-runs
            board.is_official_demo_board = True
            board.is_seed_demo_data = True
            board.owner = creator
            board.num_phases = 4
            board.project_type = 'product_tech'
            board.project_type_confirmed = True
            board.project_deadline = (timezone.now() + timedelta(days=56)).date()
            board.save()

            # Ensure columns exist with WIP limits per spec.
            # Idempotent: keeps existing columns, fixes WIP limits and positions.
            wip_for = {'Backlog': None, 'To Do': 8, 'In Progress': 6, 'In Review': None, 'Done': None}
            for position, column_name in enumerate(board_data['columns']):
                col, col_created = Column.objects.get_or_create(
                    board=board,
                    name=column_name,
                    defaults={'position': position, 'wip_limit': wip_for.get(column_name)},
                )
                # Force position + wip_limit on each run
                col.position = position
                col.wip_limit = wip_for.get(column_name)
                col.save()
                if col_created:
                    self.stdout.write(f'    - Added column: {column_name}')

            if created:
                self.stdout.write(self.style.SUCCESS(f'  [OK] Created board: {board.name}'))
            else:
                self.stdout.write(self.style.WARNING(f'  ! Already exists: {board.name} (refreshed)'))

            boards.append(board)

        return boards

    def assign_board_memberships(self, boards, personas):
        """Assign all personas to all boards with appropriate roles.
        Preserves existing real user memberships (non-demo users)."""
        self.stdout.write('\n4. Assigning board memberships...')
        
        # Role mapping based on persona
        role_map = {
            'priya.sharma':   'owner',   # Priya Sharma - Backend/API lead, board owner
            'marcus.chen':    'member',  # Marcus Chen - Frontend/UX
            'elena.vasquez':  'member',  # Elena Vasquez - DevOps/QA
        }

        # Usernames that identify any demo persona (legacy or new) - preserved when
        # we scan existing membership for real users to keep around.
        demo_usernames = set(role_map.keys()) | {
            'alex_chen_demo', 'sam_rivera_demo', 'jordan_taylor_demo',  # legacy
        }

        total_assigned = 0

        for board in boards:
            # Get existing members (real users - not any demo persona, old or new)
            existing_real_user_ids = BoardMembership.objects.filter(
                board=board
            ).exclude(user__username__in=demo_usernames).values_list('user_id', flat=True)
            
            for persona in personas:
                # Create BoardMembership for persona
                role_name = role_map.get(persona.username, 'member')
                _, created = BoardMembership.objects.get_or_create(
                    board=board,
                    user=persona,
                    defaults={'role': role_name}
                )
                if created:
                    total_assigned += 1
            
            # Ensure all existing real users remain members
            from django.contrib.auth.models import User
            for real_user_id in existing_real_user_ids:
                real_user = User.objects.get(id=real_user_id)
                BoardMembership.objects.get_or_create(
                    board=board,
                    user=real_user,
                    defaults={'role': 'member'}
                )
        
        self.stdout.write(self.style.SUCCESS(f'  [OK] Assigned {len(personas)} demo personas to {len(boards)} boards'))
        self.stdout.write(f'    Total board memberships: {total_assigned}')
