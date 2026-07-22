"""
Tier 2a Automation Test Environment
===================================

Stands up (and resets) the manual-UI test environment for the Automation
**Tier 2a Action Battery** — the 13 "Task State" actions — on the live
``Software Development`` demo board.

What it does (all idempotent / re-runnable):
  - Resolves the demo org + ``Software Development`` board (NOT by hard-coded
    id 266 — the id is assigned dynamically by the seeder).
  - Ensures the ``Bug`` and ``Feature`` labels exist (the demo seed ships only
    technical labels, so the plan's labels are missing without this).
  - Ensures board membership: ``testuser1`` -> owner (so the tester can author
    rules), ``priya.sharma`` / ``marcus.chen`` -> member (assignee targets).
  - Creates / resets the ``TIER2A-TEST`` task to the canonical §3.2 state.
  - Optionally pre-creates the 13 ``TIER2A-A0X`` rules, all PAUSED, ready to
    activate one at a time in the UI (one-rule discipline).

Usage:
    python manage.py setup_tier2a_test                 # seed task + 13 paused rules
    python manage.py setup_tier2a_test --no-rules       # seed task only
    python manage.py setup_tier2a_test --pause-existing  # also pause stray active rules
    python manage.py setup_tier2a_test --reset-task      # reset task to canonical state
    python manage.py setup_tier2a_test --report          # print current state + last logs
    python manage.py setup_tier2a_test --teardown        # pause all TIER2A rules + reset task
    python manage.py setup_tier2a_test --teardown --revert-membership  # ...and drop testuser1 owner

Verification is manual/visual (Audit Log UI + task fields) per the test plan;
``--report`` is the fast verification aid.
"""
from datetime import timedelta

from django.contrib.auth.models import User
from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone


BOARD_NAME = 'Software Development'
TASK_NAME = 'TIER2A-TEST'
ORIGINAL_DESCRIPTION = 'Original description text — Tier 2a test task'
RULE_PREFIX = 'TIER2A-'

# Tester (real test user) and the two assignment targets used by the battery.
TESTER_EMAIL = 'paul.biotech10@gmail.com'   # testuser1
TARGET_USERNAMES = ['priya.sharma', 'marcus.chen']

# Labels the plan needs but the demo seed does not ship.
EXTRA_LABELS = [('Bug', '#ef4444'), ('Feature', '#3b82f6')]


def _rule_specs(priya_id):
    """The 13 Task State rules. action JSON matches kanban/automation_actions.py.

    All rules: trigger task_assigned, no conditions, single action, paused.
    """
    return [
        ('A01', 'Set priority',      [{'type': 'set_priority', 'target': 'urgent'}]),
        ('A02', 'Set progress',      [{'type': 'set_progress', 'target': '75'}]),
        ('A03', 'Set description',   [{'type': 'set_description',
                                       'message': 'AUTOMATED: This description was set by Tier 2a rule A-03'}]),
        ('A04', 'Append description', [{'type': 'append_to_description',
                                        'message': '\n[APPENDED by A-04 rule]'}]),
        ('A05', 'Add label',         [{'type': 'add_label', 'target': 'Feature'}]),
        ('A06', 'Remove label',      [{'type': 'remove_label', 'target': 'Bug'}]),
        ('A07', 'Assign to user',    [{'type': 'assign_to_user', 'target': str(priya_id)}]),
        ('A08', 'Clear assignee',    [{'type': 'clear_assignee'}]),
        ('A09', 'Move to column',    [{'type': 'move_to_column', 'target': 'In Review'}]),
        ('A10', 'Set due date',      [{'type': 'set_due_date', 'target': 'in_14_days'}]),
        ('A11', 'Set start date',    [{'type': 'set_start_date', 'target': 'today'}]),
        ('A12', 'Clear due date',    [{'type': 'clear_due_date'}]),
        ('A13', 'Close task',        [{'type': 'close_task'}]),
    ]


class Command(BaseCommand):
    help = 'Set up / reset the Tier 2a automation manual-UI test environment.'

    def add_arguments(self, parser):
        parser.add_argument('--no-rules', action='store_true',
                            help='Seed the task only; do not create the 13 TIER2A rules.')
        parser.add_argument('--reset-task', action='store_true',
                            help='Reset TIER2A-TEST to canonical state and exit.')
        parser.add_argument('--pause-existing', action='store_true',
                            help='Pause all other active automation rules on the board.')
        parser.add_argument('--report', action='store_true',
                            help='Print current task state, active rules, and recent logs; exit.')
        parser.add_argument('--teardown', action='store_true',
                            help='Pause all TIER2A rules and reset the task (Definition of Done).')
        parser.add_argument('--revert-membership', action='store_true',
                            help='With --teardown: remove the testuser1 owner membership added at seed time.')

    # ─── helpers ────────────────────────────────────────────────────────────

    def _ok(self, msg):
        self.stdout.write(self.style.SUCCESS(msg))

    def _warn(self, msg):
        self.stdout.write(self.style.WARNING(msg))

    def _err(self, msg):
        self.stdout.write(self.style.ERROR(msg))

    def _resolve(self):
        """Resolve org, board, tester, target users, To Do / In Review columns.

        Returns a dict, or None (after printing guidance) if anything is missing.
        """
        from accounts.models import Organization
        from kanban.models import Board, Column

        demo_org = Organization.objects.filter(is_demo=True).first()
        if not demo_org:
            self._err('No demo organization found. Run: python manage.py create_demo_organization')
            return None

        board = Board.objects.filter(
            name=BOARD_NAME, organization=demo_org, is_official_demo_board=True,
        ).first()
        if not board:
            self._err(f"No '{BOARD_NAME}' demo board found. Run: "
                      'python manage.py create_demo_organization && '
                      'python manage.py populate_all_demo_data')
            return None

        tester = User.objects.filter(email=TESTER_EMAIL).first()
        if not tester:
            self._err(f'Tester (testuser1, {TESTER_EMAIL}) not found. Run: '
                      'python manage.py setup_test_environment')
            return None

        targets = {}
        for uname in TARGET_USERNAMES:
            u = User.objects.filter(username=uname).first()
            if not u:
                self._err(f"Demo persona '{uname}' not found. Run: "
                          'python manage.py create_demo_organization')
                return None
            targets[uname] = u

        todo = Column.objects.filter(board=board, name__iexact='To Do').first()
        in_review = Column.objects.filter(board=board, name__icontains='In Review').first()
        if not todo:
            self._err("Board is missing a 'To Do' column.")
            return None
        if not in_review:
            self._warn("Board is missing an 'In Review' column — A-09 (Move to column) "
                       "will have no target. Check column setup.")

        return {
            'org': demo_org, 'board': board, 'tester': tester,
            'targets': targets, 'todo': todo, 'in_review': in_review,
        }

    def _ensure_labels(self, board):
        from kanban.models import TaskLabel
        labels = {}
        for name, color in EXTRA_LABELS:
            obj, created = TaskLabel.objects.get_or_create(
                board=board, name=name,
                defaults={'color': color, 'category': 'regular'},
            )
            labels[name] = obj
            self._ok(f"   label '{name}' (id={obj.id}) {'created' if created else 'exists'}")
        return labels

    def _ensure_memberships(self, ctx):
        from kanban.models import BoardMembership
        board, tester = ctx['board'], ctx['tester']

        m, created = BoardMembership.objects.get_or_create(
            board=board, user=tester, defaults={'role': 'owner', 'added_by': tester},
        )
        if not created and m.role != 'owner':
            m.role = 'owner'
            m.save(update_fields=['role'])
        self._ok(f"   membership testuser1 -> owner {'created' if created else 'ensured'}")

        for uname, u in ctx['targets'].items():
            mm, c = BoardMembership.objects.get_or_create(
                board=board, user=u, defaults={'role': 'member', 'added_by': tester},
            )
            self._ok(f"   membership {uname} -> {mm.role} {'created' if c else 'exists'}")

    def _seed_task(self, ctx, labels):
        """Create or reset TIER2A-TEST to the canonical §3.2 state."""
        from kanban.models import Task
        from kanban.signals import automation_silent

        board, todo, tester = ctx['board'], ctx['todo'], ctx['tester']
        due = timezone.now() + timedelta(days=7)

        # automation_silent: changing the assignee must not fire active board rules.
        with automation_silent():
            task = Task.objects.filter(title=TASK_NAME, column__board=board).first()
            if task is None:
                task = Task(title=TASK_NAME, created_by=tester)
            task.column = todo
            task.priority = 'medium'
            task.progress = 30
            task.description = ORIGINAL_DESCRIPTION
            task.assigned_to = tester
            task.due_date = due
            task.start_date = None
            task.save()
            # Labels: exactly {Bug}.
            task.labels.set([labels['Bug']])

        self._ok(f"   task '{TASK_NAME}' (id={task.id}) seeded: To Do / Medium / 30% / "
                 f"testuser1 / [Bug] / due {due.date().isoformat()} / no start date")
        return task

    def _seed_rules(self, ctx):
        from kanban.automation_models import AutomationRule

        board, tester = ctx['board'], ctx['tester']
        priya = ctx['targets']['priya.sharma']
        for aid, label, actions in _rule_specs(priya.id):
            name = f'{RULE_PREFIX}{aid}: {label}'
            rule, created = AutomationRule.objects.update_or_create(
                board=board, name=name,
                defaults={
                    'created_by': tester,
                    'trigger_type': 'task_assigned',
                    'trigger_config': {},
                    'conditions': [],
                    'condition_logic': 'AND',
                    'actions': actions,
                    'otherwise_actions': [],
                    'is_active': False,
                },
            )
            self._ok(f"   rule '{name}' (id={rule.id}) {'created' if created else 'updated'} [PAUSED]")

    def _pause_existing(self, ctx):
        from kanban.automation_models import AutomationRule
        qs = AutomationRule.objects.filter(board=ctx['board'], is_active=True).exclude(
            name__startswith=RULE_PREFIX)
        names = list(qs.values_list('name', flat=True))
        count = qs.update(is_active=False)
        if count:
            self._warn(f'   paused {count} stray active rule(s): {", ".join(names)}')
        else:
            self._ok('   no stray active rules on the board (one-rule discipline OK)')

    def _print_rotation(self):
        self._ok('\nAssignee rotation (avoids the 3s/assignee dedupe between fires):')
        self.stdout.write('   priya.sharma -> marcus.chen -> priya.sharma -> ...  '
                          '(change to the NEXT user to fire each test)')

    def _report(self, ctx):
        from kanban.automation_models import AutomationLog, AutomationRule
        from kanban.models import Task

        task = Task.objects.filter(title=TASK_NAME, column__board=ctx['board']).first()
        self.stdout.write('\n--- TIER2A-TEST state ---')
        if task is None:
            self._warn('   (task not seeded yet — run without flags first)')
        else:
            labels = ', '.join(task.labels.values_list('name', flat=True)) or '(none)'
            assignee = task.assigned_to.username if task.assigned_to else '(unassigned)'
            due = task.due_date.date().isoformat() if task.due_date else '(none)'
            start = task.start_date.isoformat() if task.start_date else '(none)'
            self.stdout.write(
                f'   column={task.column.name} | priority={task.priority} | progress={task.progress}% | '
                f'assignee={assignee} | labels=[{labels}] | due={due} | start={start}')

        active = list(AutomationRule.objects.filter(
            board=ctx['board'], is_active=True).values_list('name', flat=True))
        self.stdout.write('\n--- Active rules on board ---')
        self.stdout.write('   ' + (', '.join(active) if active else '(none active)'))

        self.stdout.write('\n--- Last 15 AutomationLog rows for the task ---')
        if task is not None:
            logs = AutomationLog.objects.filter(task_affected=task).order_by('-triggered_at')[:15]
            if logs:
                for lg in logs:
                    self.stdout.write(
                        f'   {timezone.localtime(lg.triggered_at):%Y-%m-%d %H:%M:%S} | '
                        f'{lg.rule_name_snapshot or (lg.rule and lg.rule.name) or "?"} | {lg.outcome}')
            else:
                self.stdout.write('   (no logs yet)')

    def _teardown(self, ctx, revert_membership):
        from kanban.automation_models import AutomationRule
        from kanban.models import BoardMembership

        count = AutomationRule.objects.filter(
            board=ctx['board'], name__startswith=RULE_PREFIX, is_active=True,
        ).update(is_active=False)
        self._ok(f'   paused {count} active TIER2A rule(s)')

        if revert_membership:
            deleted, _ = BoardMembership.objects.filter(
                board=ctx['board'], user=ctx['tester'], role='owner',
            ).delete()
            if deleted:
                self._warn('   removed testuser1 owner membership '
                           '(testuser1 can no longer author rules on this board)')
            else:
                self._ok('   no testuser1 owner membership to remove')
        else:
            self._warn('   LEFT IN PLACE: testuser1 owner membership on the demo board.')
            self.stdout.write('   To revert it later: '
                              'python manage.py setup_tier2a_test --teardown --revert-membership')

    # ─── entrypoint ─────────────────────────────────────────────────────────

    def handle(self, *args, **options):
        from kanban.utils.demo_protection import allow_demo_writes

        self._ok('\n' + '=' * 78)
        self._ok('  TIER 2a AUTOMATION TEST ENVIRONMENT')
        self._ok('=' * 78)

        ctx = self._resolve()
        if ctx is None:
            return
        self._ok(f"\nResolved board '{ctx['board'].name}' (id={ctx['board'].id}) in "
                 f"org '{ctx['org'].name}'.")

        # Read-only / non-seeding modes.
        if options['report']:
            self._report(ctx)
            return

        if options['teardown']:
            with allow_demo_writes(), transaction.atomic():
                self.stdout.write('\nTeardown:')
                self._teardown(ctx, options['revert_membership'])
                self.stdout.write('\nResetting task to canonical state:')
                labels = self._ensure_labels(ctx['board'])
                self._seed_task(ctx, labels)
            self._ok('\nTeardown complete.')
            return

        if options['reset_task']:
            with allow_demo_writes(), transaction.atomic():
                self.stdout.write('\nResetting task to canonical state:')
                labels = self._ensure_labels(ctx['board'])
                self._seed_task(ctx, labels)
            self._ok('\nTask reset complete.')
            self._print_rotation()
            return

        # Full seed.
        with allow_demo_writes(), transaction.atomic():
            self.stdout.write('\n1. Ensuring labels (Bug, Feature):')
            labels = self._ensure_labels(ctx['board'])

            self.stdout.write('\n2. Ensuring board memberships:')
            self._ensure_memberships(ctx)

            if options['pause_existing']:
                self.stdout.write('\n3. Pausing stray active rules:')
                self._pause_existing(ctx)

            self.stdout.write('\n4. Seeding TIER2A-TEST task:')
            self._seed_task(ctx, labels)

            if not options['no_rules']:
                self.stdout.write('\n5. Creating 13 TIER2A rules (paused):')
                self._seed_rules(ctx)

        self._print_rotation()
        self._ok('\nSetup complete. Activate one TIER2A rule at a time in the UI, fire it by '
                 'changing the assignee per the rotation, verify, then pause + --reset-task.')
