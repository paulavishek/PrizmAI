"""
Management command to populate the New Office Construction Project board
with realistic critical path dependencies.

This creates a more realistic Gantt chart where:
- Some tasks run in parallel (not all tasks are on the critical path)
- Tasks have multiple dependencies (merge points/convergence)
- The critical path is the LONGEST path through the project network

Each phase has 10 tasks with intra-phase dependencies only.
"""
from django.core.management.base import BaseCommand
from django.utils import timezone
from django.contrib.auth import get_user_model
from datetime import timedelta, date
from kanban.models import Board, Column, Task, TaskLabel

User = get_user_model()


class Command(BaseCommand):
    help = 'Populate the New Office Construction Project board with realistic critical path demo data'

    def add_arguments(self, parser):
        parser.add_argument(
            '--reset',
            action='store_true',
            help='Delete existing tasks before creating new ones',
        )
        parser.add_argument(
            '--board-id',
            type=int,
            help='Specific board ID to populate (if not named "New Office Construction Project")',
        )

    def handle(self, *args, **options):
        self.stdout.write(self.style.SUCCESS('\n' + '='*70))
        self.stdout.write(self.style.SUCCESS('CONSTRUCTION PROJECT DEMO DATA'))
        self.stdout.write(self.style.SUCCESS('='*70 + '\n'))

        # Find the board
        board = None
        if options['board_id']:
            board = Board.objects.filter(id=options['board_id']).first()
        else:
            board = Board.objects.filter(name__icontains='New Office Construction').first()
            if not board:
                board = Board.objects.filter(name__icontains='Construction').first()

        if not board:
            self.stdout.write(self.style.ERROR(
                '❌ Board not found. Create "New Office Construction Project" board first or use --board-id'
            ))
            return

        self.stdout.write(f'📋 Found board: {board.name} (ID: {board.id})')

        # Ensure board has 3 phases configured
        board.num_phases = 3
        board.save()
        self.stdout.write('   ✅ Board configured for 3 phases')

        # Get or create columns
        columns = self.ensure_columns(board)
        self.stdout.write('   ✅ Columns verified')

        # Get a user to assign tasks (use board creator or first admin)
        user = board.created_by or User.objects.filter(is_staff=True).first() or User.objects.first()
        if not user:
            self.stdout.write(self.style.ERROR('❌ No user found to create tasks'))
            return

        # Check if board has an organization - needed for UserPerformanceProfile
        # If not, try to associate with demo org or skip assignees
        from accounts.models import Organization
        if not board.organization:
            demo_org = Organization.objects.filter(is_demo=True).first()
            if demo_org:
                board.organization = demo_org
                board.save()
                self.stdout.write('   ✅ Board associated with demo organization')
            else:
                self.stdout.write(self.style.WARNING(
                    '   ⚠️  No organization - tasks will be created without assignees'
                ))

        # Get demo users if available (only use if board has organization)
        if board.organization:
            alex = User.objects.filter(email='alex.chen@demo.prizmai.local').first() or user
            sam = User.objects.filter(email='sam.rivera@demo.prizmai.local').first() or user
            jordan = User.objects.filter(email='jordan.taylor@demo.prizmai.local').first() or user
        else:
            # No org, so don't assign users (would fail due to UserPerformanceProfile constraint)
            alex = sam = jordan = None

        # Reset if requested
        if options['reset']:
            deleted = Task.objects.filter(column__board=board).delete()[0]
            self.stdout.write(self.style.WARNING(f'   🔄 Deleted {deleted} existing tasks'))

        # Check for existing tasks
        existing = Task.objects.filter(column__board=board).count()
        if existing > 0 and not options['reset']:
            self.stdout.write(self.style.WARNING(
                f'⚠️  Board already has {existing} tasks. Use --reset to recreate.'
            ))
            return

        # Create tasks for each phase
        self.stdout.write('\n📝 Creating construction project tasks...\n')

        phase1_tasks = self.create_phase1_preconstruction(board, columns, user, alex, sam, jordan)
        self.stdout.write(f'   ✅ Phase 1 (Pre-Construction): {len(phase1_tasks)} tasks')

        phase2_tasks = self.create_phase2_structural(board, columns, user, alex, sam, jordan)
        self.stdout.write(f'   ✅ Phase 2 (Structural Work): {len(phase2_tasks)} tasks')

        phase3_tasks = self.create_phase3_finishing(board, columns, user, alex, sam, jordan)
        self.stdout.write(f'   ✅ Phase 3 (Finishing & Closeout): {len(phase3_tasks)} tasks')

        # Create dependencies with realistic critical path
        self.stdout.write('\n🔗 Creating realistic critical path dependencies...\n')

        self.create_phase1_dependencies(phase1_tasks)
        self.stdout.write('   ✅ Phase 1 dependencies created')

        self.create_phase2_dependencies(phase2_tasks)
        self.stdout.write('   ✅ Phase 2 dependencies created')

        self.create_phase3_dependencies(phase3_tasks)
        self.stdout.write('   ✅ Phase 3 dependencies created')

        total = len(phase1_tasks) + len(phase2_tasks) + len(phase3_tasks)
        self.stdout.write(self.style.SUCCESS(f'\n   📊 Total tasks created: {total}'))
        self.stdout.write(self.style.SUCCESS('\n' + '='*70))
        self.stdout.write(self.style.SUCCESS('✅ CONSTRUCTION DEMO DATA COMPLETE'))
        self.stdout.write(self.style.SUCCESS('='*70 + '\n'))
        self.stdout.write(self.style.SUCCESS(
            '💡 View the Gantt chart at: /boards/{}/gantt/'.format(board.id)
        ))
        self.stdout.write(self.style.SUCCESS(
            '   Enable "Show Critical Path" to see the longest dependency chain!\n'
        ))

    def ensure_columns(self, board):
        """Ensure the board has the necessary columns"""
        default_columns = ['To Do', 'In Progress', 'In Review', 'Done']
        columns = {}

        for i, name in enumerate(default_columns):
            col, created = Column.objects.get_or_create(
                board=board,
                name=name,
                defaults={'position': i}
            )
            columns[name] = col

        return columns

    def create_phase1_preconstruction(self, board, columns, creator, alex, sam, jordan):
        """
        Phase 1: Pre-Construction Planning (10 tasks)
        
        Dependency structure (creates parallel paths):
        
        [0] Site Survey ─────────────────┐
                                         ├──► [4] Site Preparation ──► [7] Foundation Excavation
        [1] Soil Testing ────────────────┘                                       │
                                                                                  │
        [2] Architectural Design ────────┐                                        │
                                         ├──► [5] Permit Applications ──► [8] Permit Approval ─┐
        [3] Structural Engineering ──────┘            │                                         │
                                                      │                                         │
                                                      └──► [6] Utility Coordination            │
                                                                                                │
                                                           [9] Foundation Pouring ◄─────────────┘
                                                             (depends on [7] AND [8])
        
        Critical Path: 0 → 4 → 7 → 9 (or through permits if permits take longer)
        Non-critical: Tasks 1, 2, 3, 6 can float (run in parallel without affecting end date)
        """
        todo = columns['To Do']
        in_progress = columns['In Progress']
        review = columns['In Review']
        done = columns['Done']
        
        now = timezone.now().date()
        tasks = []

        # Task definitions with realistic construction durations
        # Using calculated dates to create proper Gantt visualization
        phase1_data = [
            # Task 0: Start task - no dependencies
            {
                'title': 'Site Survey & Assessment',
                'desc': 'Complete topographical survey and site assessment for construction planning',
                'priority': 'high',
                'complexity': 5,
                'assignee': alex,
                'progress': 100,
                'column': done,
                'start_offset': 0,
                'duration': 5,
            },
            # Task 1: Parallel with Task 0
            {
                'title': 'Soil Testing & Analysis',
                'desc': 'Geotechnical soil testing to determine foundation requirements',
                'priority': 'high',
                'complexity': 6,
                'assignee': sam,
                'progress': 100,
                'column': done,
                'start_offset': 0,
                'duration': 4,  # Shorter than Task 0 - not on critical path
            },
            # Task 2: Parallel with Task 0
            {
                'title': 'Architectural Design',
                'desc': 'Complete architectural drawings and building design specifications',
                'priority': 'high',
                'complexity': 8,
                'assignee': jordan,
                'progress': 100,
                'column': done,
                'start_offset': 0,
                'duration': 10,  # Longer duration - potentially critical
            },
            # Task 3: Parallel with Tasks 0, 1, 2
            {
                'title': 'Structural Engineering Plans',
                'desc': 'Develop structural engineering plans and load calculations',
                'priority': 'high',
                'complexity': 7,
                'assignee': sam,
                'progress': 100,
                'column': done,
                'start_offset': 2,  # Starts a bit after architectural
                'duration': 8,
            },
            # Task 4: Depends on Tasks 0 and 1
            {
                'title': 'Site Preparation',
                'desc': 'Clear site, install temporary fencing, and prepare access roads',
                'priority': 'medium',
                'complexity': 5,
                'assignee': alex,
                'progress': 100,
                'column': done,
                'start_offset': 5,  # After site survey
                'duration': 6,
            },
            # Task 5: Depends on Tasks 2 and 3
            {
                'title': 'Permit Applications',
                'desc': 'Submit building permits and regulatory applications',
                'priority': 'high',
                'complexity': 4,
                'assignee': jordan,
                'progress': 80,
                'column': review,
                'start_offset': 10,  # After designs complete
                'duration': 3,
            },
            # Task 6: Depends on Task 5
            {
                'title': 'Utility Coordination',
                'desc': 'Coordinate with utility companies for water, electric, and gas connections',
                'priority': 'medium',
                'complexity': 4,
                'assignee': alex,
                'progress': 60,
                'column': in_progress,
                'start_offset': 13,
                'duration': 4,  # Shorter - not on critical path
            },
            # Task 7: Depends on Task 4
            {
                'title': 'Foundation Excavation',
                'desc': 'Excavate foundation footings and prepare for concrete pour',
                'priority': 'high',
                'complexity': 6,
                'assignee': sam,
                'progress': 40,
                'column': in_progress,
                'start_offset': 11,  # After site prep
                'duration': 7,
            },
            # Task 8: Depends on Task 5
            {
                'title': 'Permit Approval',
                'desc': 'Receive final permit approvals and address any revision requests',
                'priority': 'urgent',
                'complexity': 3,
                'assignee': jordan,
                'progress': 0,
                'column': todo,
                'start_offset': 13,  # After permit apps
                'duration': 10,  # Long wait time - could be critical
            },
            # Task 9: Depends on Tasks 7 AND 8 (convergence/merge point)
            {
                'title': 'Foundation Concrete Pour',
                'desc': 'Pour concrete foundation including footings, stem walls, and slab',
                'priority': 'urgent',
                'complexity': 7,
                'assignee': sam,
                'progress': 0,
                'column': todo,
                'start_offset': 23,  # After both excavation and permits
                'duration': 5,
            },
        ]

        # Create tasks
        from datetime import datetime
        for i, t in enumerate(phase1_data):
            start = now + timedelta(days=t['start_offset'])
            due_date_obj = start + timedelta(days=t['duration'])
            # Convert date to timezone-aware datetime for due_date field
            due_datetime = timezone.make_aware(
                datetime.combine(due_date_obj, datetime.min.time())
            )
            task = Task.objects.create(
                column=t['column'],
                title=t['title'],
                description=t['desc'],
                priority=t['priority'],
                complexity_score=t['complexity'],
                assigned_to=t['assignee'],
                created_by=creator,
                progress=t['progress'],
                start_date=start,
                due_date=due_datetime,
                phase='Phase 1',
                is_seed_demo_data=True,
            )
            tasks.append(task)

        return tasks

    def create_phase1_dependencies(self, tasks):
        """
        Create Phase 1 dependencies - realistic parallel paths and merge points
        
        Index mapping:
        0: Site Survey
        1: Soil Testing
        2: Architectural Design
        3: Structural Engineering
        4: Site Preparation (depends on 0, 1)
        5: Permit Applications (depends on 2, 3)
        6: Utility Coordination (depends on 5)
        7: Foundation Excavation (depends on 4)
        8: Permit Approval (depends on 5)
        9: Foundation Pour (depends on 7, 8) - MERGE POINT
        """
        if len(tasks) < 10:
            return

        # Task 4 (Site Preparation) depends on Task 0 (Site Survey) and Task 1 (Soil Testing)
        tasks[4].dependencies.add(tasks[0])
        tasks[4].dependencies.add(tasks[1])

        # Task 5 (Permit Applications) depends on Task 2 (Arch Design) and Task 3 (Structural Eng)
        tasks[5].dependencies.add(tasks[2])
        tasks[5].dependencies.add(tasks[3])

        # Task 6 (Utility Coord) depends on Task 5 (Permit Apps)
        tasks[6].dependencies.add(tasks[5])

        # Task 7 (Foundation Excavation) depends on Task 4 (Site Prep)
        tasks[7].dependencies.add(tasks[4])

        # Task 8 (Permit Approval) depends on Task 5 (Permit Apps)
        tasks[8].dependencies.add(tasks[5])

        # Task 9 (Foundation Pour) depends on BOTH Task 7 (Excavation) AND Task 8 (Permit Approval)
        # This is a MERGE POINT - critical for realistic critical path
        tasks[9].dependencies.add(tasks[7])
        tasks[9].dependencies.add(tasks[8])

    def create_phase2_structural(self, board, columns, creator, alex, sam, jordan):
        """
        Phase 2: Structural Construction (10 tasks)
        
        Dependency structure (branching and merging):
        
        [0] Steel Frame Erection ──┬──► [1] Exterior Wall Framing ──► [4] Roof Structure
                                   │                                        │
                                   ├──► [2] Electrical Rough-in ────────────┤
                                   │                    (parallel)          │
                                   └──► [3] Plumbing Rough-in ──────────────┤
                                                (parallel)                  │
                                                                            │
                                        [5] HVAC Ductwork ◄─────────────────┘
                                              │
                                              ▼
                                        [6] Insulation ──► [7] Exterior Sheathing
                                                                    │
                                                                    ▼
                                              [8] Building Inspection ◄── [9] Weather Barrier
                                                (depends on 6, 7, 9)
        
        Critical Path: The longest path determines project duration
        """
        todo = columns['To Do']
        in_progress = columns['In Progress']
        review = columns['In Review']
        done = columns['Done']
        
        now = timezone.now().date()
        phase_start = 28  # Days after phase 1 starts
        tasks = []

        phase2_data = [
            # Task 0: Start of Phase 2
            {
                'title': 'Steel Frame Erection',
                'desc': 'Erect main structural steel frame including columns and beams',
                'priority': 'urgent',
                'complexity': 8,
                'assignee': sam,
                'progress': 100,
                'column': done,
                'start_offset': phase_start,
                'duration': 10,
            },
            # Task 1: Depends on Task 0
            {
                'title': 'Exterior Wall Framing',
                'desc': 'Install exterior wall framing and structural sheathing',
                'priority': 'high',
                'complexity': 6,
                'assignee': alex,
                'progress': 80,
                'column': review,
                'start_offset': phase_start + 10,
                'duration': 8,
            },
            # Task 2: Depends on Task 0 (parallel with Task 1)
            {
                'title': 'Electrical Rough-in',
                'desc': 'Install electrical conduit, wiring, and panel boxes',
                'priority': 'high',
                'complexity': 7,
                'assignee': jordan,
                'progress': 70,
                'column': in_progress,
                'start_offset': phase_start + 10,
                'duration': 6,  # Shorter - not on critical path
            },
            # Task 3: Depends on Task 0 (parallel with Tasks 1, 2)
            {
                'title': 'Plumbing Rough-in',
                'desc': 'Install plumbing pipes, drains, and water lines',
                'priority': 'high',
                'complexity': 7,
                'assignee': sam,
                'progress': 75,
                'column': in_progress,
                'start_offset': phase_start + 10,
                'duration': 5,  # Shorter - not on critical path
            },
            # Task 4: Depends on Task 1
            {
                'title': 'Roof Structure Installation',
                'desc': 'Install roof trusses, decking, and initial waterproofing',
                'priority': 'urgent',
                'complexity': 7,
                'assignee': alex,
                'progress': 30,
                'column': in_progress,
                'start_offset': phase_start + 18,
                'duration': 7,
            },
            # Task 5: Depends on Tasks 2, 3, 4 (merge point)
            {
                'title': 'HVAC Ductwork Installation',
                'desc': 'Install HVAC ducts, vents, and main equipment',
                'priority': 'high',
                'complexity': 6,
                'assignee': jordan,
                'progress': 0,
                'column': todo,
                'start_offset': phase_start + 25,
                'duration': 6,
            },
            # Task 6: Depends on Task 5
            {
                'title': 'Insulation Installation',
                'desc': 'Install thermal and acoustic insulation in walls and ceiling',
                'priority': 'medium',
                'complexity': 4,
                'assignee': alex,
                'progress': 0,
                'column': todo,
                'start_offset': phase_start + 31,
                'duration': 5,
            },
            # Task 7: Depends on Task 4 (parallel with some tasks)
            {
                'title': 'Exterior Sheathing & Wrap',
                'desc': 'Complete exterior sheathing and install weather-resistant barrier',
                'priority': 'high',
                'complexity': 5,
                'assignee': sam,
                'progress': 0,
                'column': todo,
                'start_offset': phase_start + 25,
                'duration': 5,
            },
            # Task 8: Depends on Task 7
            {
                'title': 'Window & Door Frames',
                'desc': 'Install window frames and exterior door frames',
                'priority': 'medium',
                'complexity': 5,
                'assignee': jordan,
                'progress': 0,
                'column': todo,
                'start_offset': phase_start + 30,
                'duration': 4,
            },
            # Task 9: Depends on Tasks 6, 7, 8 (merge point - inspection)
            {
                'title': 'Structural Inspection',
                'desc': 'City inspection for structural, electrical, and plumbing rough-in',
                'priority': 'urgent',
                'complexity': 3,
                'assignee': alex,
                'progress': 0,
                'column': todo,
                'start_offset': phase_start + 36,
                'duration': 2,
            },
        ]

        from datetime import datetime
        for i, t in enumerate(phase2_data):
            start = now + timedelta(days=t['start_offset'])
            due_date_obj = start + timedelta(days=t['duration'])
            due_datetime = timezone.make_aware(
                datetime.combine(due_date_obj, datetime.min.time())
            )
            task = Task.objects.create(
                column=t['column'],
                title=t['title'],
                description=t['desc'],
                priority=t['priority'],
                complexity_score=t['complexity'],
                assigned_to=t['assignee'],
                created_by=creator,
                progress=t['progress'],
                start_date=start,
                due_date=due_datetime,
                phase='Phase 2',
                is_seed_demo_data=True,
            )
            tasks.append(task)

        return tasks

    def create_phase2_dependencies(self, tasks):
        """
        Create Phase 2 dependencies - branching from steel frame
        
        Index mapping:
        0: Steel Frame Erection
        1: Exterior Wall Framing (depends on 0)
        2: Electrical Rough-in (depends on 0) - PARALLEL
        3: Plumbing Rough-in (depends on 0) - PARALLEL
        4: Roof Structure (depends on 1)
        5: HVAC Ductwork (depends on 2, 3, 4) - MERGE
        6: Insulation (depends on 5)
        7: Exterior Sheathing (depends on 4)
        8: Window/Door Frames (depends on 7)
        9: Structural Inspection (depends on 6, 7, 8) - FINAL MERGE
        """
        if len(tasks) < 10:
            return

        # Tasks 1, 2, 3 all depend on Task 0 (branching)
        tasks[1].dependencies.add(tasks[0])
        tasks[2].dependencies.add(tasks[0])
        tasks[3].dependencies.add(tasks[0])

        # Task 4 depends on Task 1
        tasks[4].dependencies.add(tasks[1])

        # Task 5 (HVAC) depends on multiple predecessors (merge point)
        tasks[5].dependencies.add(tasks[2])  # Electrical
        tasks[5].dependencies.add(tasks[3])  # Plumbing
        tasks[5].dependencies.add(tasks[4])  # Roof

        # Task 6 depends on Task 5
        tasks[6].dependencies.add(tasks[5])

        # Task 7 depends on Task 4
        tasks[7].dependencies.add(tasks[4])

        # Task 8 depends on Task 7
        tasks[8].dependencies.add(tasks[7])

        # Task 9 (Inspection) depends on multiple - big merge point
        tasks[9].dependencies.add(tasks[6])
        tasks[9].dependencies.add(tasks[7])
        tasks[9].dependencies.add(tasks[8])

    def create_phase3_finishing(self, board, columns, creator, alex, sam, jordan):
        """
        Phase 3: Finishing & Closeout (10 tasks)
        
        Dependency structure:
        
        [0] Drywall Installation ──┬──► [2] Interior Painting
                                   │           │
                                   └──► [3] Trim & Millwork ◄─┘
                                              │
        [1] Flooring Prep ─────────────────────┤
                                               │
                                        [4] Flooring Installation
                                               │
               [5] Plumbing Fixtures ──────────┤
               (parallel)                      │
                                               │
               [6] Electrical Fixtures ────────┤
               (parallel)                      │
                                               │
                                        [7] Final Paint Touch-ups
                                               │
                                        [8] Final Cleaning
                                               │
                                        [9] Final Inspection & Handover
        """
        todo = columns['To Do']
        in_progress = columns['In Progress']
        review = columns['In Review']
        done = columns['Done']
        
        now = timezone.now().date()
        phase_start = 66  # Days after project start
        tasks = []

        phase3_data = [
            # Task 0: Start of Phase 3
            {
                'title': 'Drywall Installation',
                'desc': 'Install drywall, tape, mud, and texture on all interior surfaces',
                'priority': 'high',
                'complexity': 6,
                'assignee': alex,
                'progress': 0,
                'column': todo,
                'start_offset': phase_start,
                'duration': 8,
            },
            # Task 1: Parallel with Task 0
            {
                'title': 'Flooring Substrate Prep',
                'desc': 'Prepare and level floor substrates for flooring installation',
                'priority': 'medium',
                'complexity': 4,
                'assignee': sam,
                'progress': 0,
                'column': todo,
                'start_offset': phase_start,
                'duration': 4,  # Shorter - not on critical path
            },
            # Task 2: Depends on Task 0
            {
                'title': 'Interior Painting',
                'desc': 'Prime and paint all interior walls, ceilings, and trim',
                'priority': 'high',
                'complexity': 5,
                'assignee': jordan,
                'progress': 0,
                'column': todo,
                'start_offset': phase_start + 8,
                'duration': 6,
            },
            # Task 3: Depends on Tasks 0, 2
            {
                'title': 'Trim & Millwork',
                'desc': 'Install baseboards, crown molding, door casings, and built-ins',
                'priority': 'medium',
                'complexity': 5,
                'assignee': alex,
                'progress': 0,
                'column': todo,
                'start_offset': phase_start + 14,
                'duration': 5,
            },
            # Task 4: Depends on Tasks 1, 3
            {
                'title': 'Flooring Installation',
                'desc': 'Install flooring materials in all areas',
                'priority': 'high',
                'complexity': 6,
                'assignee': sam,
                'progress': 0,
                'column': todo,
                'start_offset': phase_start + 19,
                'duration': 6,
            },
            # Task 5: Depends on Task 2 (parallel with 3, 4)
            {
                'title': 'Plumbing Fixtures',
                'desc': 'Install sinks, toilets, faucets, and other plumbing fixtures',
                'priority': 'medium',
                'complexity': 4,
                'assignee': sam,
                'progress': 0,
                'column': todo,
                'start_offset': phase_start + 14,
                'duration': 3,  # Short - not on critical path
            },
            # Task 6: Depends on Task 2 (parallel with 3, 4, 5)
            {
                'title': 'Electrical Fixtures & Devices',
                'desc': 'Install light fixtures, outlets, switches, and panels',
                'priority': 'medium',
                'complexity': 4,
                'assignee': jordan,
                'progress': 0,
                'column': todo,
                'start_offset': phase_start + 14,
                'duration': 4,  # Short - not on critical path
            },
            # Task 7: Depends on Tasks 4, 5, 6
            {
                'title': 'Final Paint Touch-ups',
                'desc': 'Touch up paint after all fixture installations',
                'priority': 'low',
                'complexity': 2,
                'assignee': jordan,
                'progress': 0,
                'column': todo,
                'start_offset': phase_start + 25,
                'duration': 2,
            },
            # Task 8: Depends on Task 7
            {
                'title': 'Final Cleaning',
                'desc': 'Deep clean entire building, remove construction debris',
                'priority': 'medium',
                'complexity': 3,
                'assignee': alex,
                'progress': 0,
                'column': todo,
                'start_offset': phase_start + 27,
                'duration': 3,
            },
            # Task 9: Depends on Task 8
            {
                'title': 'Final Inspection & Handover',
                'desc': 'Final city inspection, certificate of occupancy, and owner handover',
                'priority': 'urgent',
                'complexity': 4,
                'assignee': alex,
                'progress': 0,
                'column': todo,
                'start_offset': phase_start + 30,
                'duration': 2,
            },
        ]

        from datetime import datetime
        for i, t in enumerate(phase3_data):
            start = now + timedelta(days=t['start_offset'])
            due_date_obj = start + timedelta(days=t['duration'])
            due_datetime = timezone.make_aware(
                datetime.combine(due_date_obj, datetime.min.time())
            )
            task = Task.objects.create(
                column=t['column'],
                title=t['title'],
                description=t['desc'],
                priority=t['priority'],
                complexity_score=t['complexity'],
                assigned_to=t['assignee'],
                created_by=creator,
                progress=t['progress'],
                start_date=start,
                due_date=due_datetime,
                phase='Phase 3',
                is_seed_demo_data=True,
            )
            tasks.append(task)

        return tasks

    def create_phase3_dependencies(self, tasks):
        """
        Create Phase 3 dependencies
        
        Index mapping:
        0: Drywall Installation
        1: Flooring Substrate Prep (parallel with 0)
        2: Interior Painting (depends on 0)
        3: Trim & Millwork (depends on 0, 2)
        4: Flooring Installation (depends on 1, 3)
        5: Plumbing Fixtures (depends on 2) - PARALLEL
        6: Electrical Fixtures (depends on 2) - PARALLEL
        7: Paint Touch-ups (depends on 4, 5, 6)
        8: Final Cleaning (depends on 7)
        9: Final Inspection (depends on 8)
        """
        if len(tasks) < 10:
            return

        # Task 2 depends on Task 0
        tasks[2].dependencies.add(tasks[0])

        # Task 3 depends on Tasks 0 and 2
        tasks[3].dependencies.add(tasks[0])
        tasks[3].dependencies.add(tasks[2])

        # Task 4 depends on Tasks 1 and 3
        tasks[4].dependencies.add(tasks[1])
        tasks[4].dependencies.add(tasks[3])

        # Tasks 5 and 6 depend on Task 2 (parallel branches)
        tasks[5].dependencies.add(tasks[2])
        tasks[6].dependencies.add(tasks[2])

        # Task 7 depends on Tasks 4, 5, and 6 (merge point)
        tasks[7].dependencies.add(tasks[4])
        tasks[7].dependencies.add(tasks[5])
        tasks[7].dependencies.add(tasks[6])

        # Task 8 depends on Task 7
        tasks[8].dependencies.add(tasks[7])

        # Task 9 depends on Task 8
        tasks[9].dependencies.add(tasks[8])
