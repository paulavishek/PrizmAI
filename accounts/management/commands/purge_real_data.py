"""
Management command to purge all real user accounts and their artifacts.

Keeps only the three demo personas and their demo board:
  - alex_chen_demo  (Alex Chen)
  - sam_rivera_demo (Sam Rivera)
  - jordan_taylor_demo (Jordan Taylor)
  - demo_admin_solo (Solo demo admin)

The "Demo - Acme Corporation" organisation and "Software Development" board
are fully preserved.

CRITICAL SAFETY NOTE
--------------------
The demo organisation's `created_by` is set to the first Django superuser by
`create_demo_organisation`.  Deleting that superuser would cascade-delete the
entire demo org.  This command first re-assigns `created_by` on the demo org
(and on any other demo artefacts that reference non-demo users) to
alex_chen_demo, so the CASCADE is harmless.

Usage:
    python manage.py purge_real_data
    python manage.py purge_real_data --no-confirm
    python manage.py purge_real_data --include-superusers
    python manage.py purge_real_data --no-confirm --include-superusers
"""

from django.core.management.base import BaseCommand
from django.contrib.auth.models import User
from django.db import transaction

# ---------------------------------------------------------------------------
# Demo identity constants  (must match create_demo_organization.py)
# ---------------------------------------------------------------------------
DEMO_USERNAMES = {
    'alex_chen_demo',
    'sam_rivera_demo',
    'jordan_taylor_demo',
    'demo_admin_solo',
}

DEMO_ORG_FLAG = 'is_demo'        # Boolean field on accounts.Organization
DEMO_BOARD_FLAG = 'is_official_demo_board'  # Boolean field on kanban.Board


class Command(BaseCommand):
    help = (
        'Remove all real user accounts and their artefacts, '
        'keeping only demo users and demo data.'
    )

    def add_arguments(self, parser):
        parser.add_argument(
            '--no-confirm',
            action='store_true',
            help='Skip interactive confirmation prompt.',
        )
        parser.add_argument(
            '--include-superusers',
            action='store_true',
            help=(
                'Also delete superuser accounts that are not demo users. '
                'By default superusers are spared so site admin access is preserved.'
            ),
        )

    # ------------------------------------------------------------------
    # Entry point
    # ------------------------------------------------------------------
    def handle(self, *args, **options):
        no_confirm = options['no_confirm']
        include_superusers = options['include_superusers']

        self._header('PURGE REAL USER DATA')

        # ---- 1. Locate demo anchor objects --------------------------------
        try:
            from accounts.models import Organization
            from kanban.models import Board
        except ImportError as exc:
            self.stdout.write(self.style.ERROR(f'Import error: {exc}'))
            return

        demo_org = Organization.objects.filter(is_demo=True).first()
        if not demo_org:
            self.stdout.write(self.style.ERROR(
                'No demo organisation found (is_demo=True). '
                'Run: python manage.py create_demo_organization first.'
            ))
            return

        alex = User.objects.filter(username='alex_chen_demo').first()
        if not alex:
            self.stdout.write(self.style.ERROR(
                'Demo user alex_chen_demo not found. '
                'Run: python manage.py create_demo_organization first.'
            ))
            return

        # ---- 2. Identify real users ----------------------------------------
        real_users_qs = User.objects.exclude(username__in=DEMO_USERNAMES)
        if not include_superusers:
            real_users_qs = real_users_qs.filter(is_superuser=False)

        real_users = list(real_users_qs.values('id', 'username', 'email', 'is_superuser'))
        skipped_superusers = []
        if not include_superusers:
            skipped_superusers = list(
                User.objects.filter(is_superuser=True)
                .exclude(username__in=DEMO_USERNAMES)
                .values('username', 'email')
            )

        # ---- 3. Count non-demo organisations --------------------------------
        non_demo_orgs = list(
            Organization.objects.filter(is_demo=False)
            .values('id', 'name')
        )

        # ---- 4. Show summary -----------------------------------------------
        self.stdout.write('')
        self.stdout.write(self.style.WARNING('What will be DELETED:'))
        self.stdout.write(f'  Real user accounts  : {len(real_users)}')
        if real_users:
            for u in real_users[:10]:
                flag = ' [superuser]' if u['is_superuser'] else ''
                self.stdout.write(f'      • {u["username"]} <{u["email"]}>{flag}')
            if len(real_users) > 10:
                self.stdout.write(f'      … and {len(real_users) - 10} more')
        self.stdout.write(
            f'  Non-demo organisations: {len(non_demo_orgs)} '
            f'(+ all their boards, tasks, comments, etc.)'
        )

        self.stdout.write('')
        self.stdout.write(self.style.SUCCESS('What will be KEPT:'))
        self.stdout.write(f'  Demo organisation   : {demo_org.name}')
        demo_boards = Board.objects.filter(is_official_demo_board=True)
        for b in demo_boards:
            self.stdout.write(f'  Demo board          : {b.name}')
        self.stdout.write(f'  Demo users          : {", ".join(sorted(DEMO_USERNAMES))}')
        if skipped_superusers:
            self.stdout.write('')
            self.stdout.write(self.style.WARNING('Superusers that will NOT be deleted (use --include-superusers to remove):'))
            for su in skipped_superusers:
                self.stdout.write(f'      • {su["username"]} <{su["email"]}>')

        if not real_users and not non_demo_orgs:
            self.stdout.write('')
            self.stdout.write(self.style.SUCCESS('Database is already clean — nothing to do.'))
            return

        # ---- 5. Confirmation -----------------------------------------------
        self.stdout.write('')
        if not no_confirm:
            self.stdout.write(self.style.WARNING(
                'This is IRREVERSIBLE. All real user data will be permanently deleted.'
            ))
            answer = input('Type "yes" to proceed: ').strip().lower()
            if answer != 'yes':
                self.stdout.write(self.style.ERROR('Aborted — no changes made.'))
                return

        # ---- 6. Execute inside a transaction --------------------------------
        self._header('EXECUTING CLEANUP')
        try:
            with transaction.atomic():
                self._step1_protect_demo_org(demo_org, alex)
                self._step2_delete_real_users(real_users_qs)
                self._step3_delete_non_demo_orgs()
                self._step4_clean_orphans()

            self._header('COMPLETE')
            self.stdout.write(self.style.SUCCESS(
                f'✓ Deleted {len(real_users)} real user(s) and '
                f'{len(non_demo_orgs)} non-demo organisation(s).'
            ))
            self.stdout.write(self.style.SUCCESS(
                f'  Demo organisation "{demo_org.name}" and all demo '
                f'board data are intact.'
            ))
            if skipped_superusers:
                self.stdout.write(self.style.WARNING(
                    f'  ⚠ {len(skipped_superusers)} superuser(s) were NOT deleted.'
                    f' Re-run with --include-superusers to remove them.'
                ))

        except Exception as exc:
            self.stdout.write(self.style.ERROR(f'✗ Error — transaction rolled back: {exc}'))
            import traceback
            traceback.print_exc()

    # ------------------------------------------------------------------
    # Internal steps
    # ------------------------------------------------------------------

    def _step1_protect_demo_org(self, demo_org, alex):
        """
        Re-assign created_by on the demo organisation to alex_chen_demo if it
        currently points to a non-demo user (e.g., a superuser created by
        `create_demo_organization`).  Without this, deleting that superuser
        would CASCADE-delete the demo org.
        """
        self.stdout.write('[1/4] Protecting demo organisation from cascade deletion ...')
        changed = False

        if demo_org.created_by_id != alex.pk and demo_org.created_by.username not in DEMO_USERNAMES:
            old = demo_org.created_by.username
            demo_org.created_by = alex
            demo_org.save(update_fields=['created_by'])
            self.stdout.write(
                self.style.SUCCESS(f'  ✓ demo org created_by reassigned: {old} → alex_chen_demo')
            )
            changed = True

        # Also protect any demo boards whose created_by points to a non-demo user
        try:
            from kanban.models import Board
            qs = Board.objects.filter(
                is_official_demo_board=True
            ).exclude(created_by__username__in=DEMO_USERNAMES)
            count = qs.count()
            if count:
                qs.update(created_by=alex)
                self.stdout.write(
                    self.style.SUCCESS(
                        f'  ✓ {count} demo Board(s) reassigned to alex_chen_demo'
                    )
                )
                changed = True
        except Exception as exc:
            self.stdout.write(self.style.WARNING(f'  ⚠ Could not reassign demo boards: {exc}'))

        if not changed:
            self.stdout.write('  (demo org created_by already a demo user — no change needed)')

    def _step2_delete_real_users(self, real_users_qs):
        """
        Delete all real users.  Django CASCADE handles:
          - UserProfile (accounts)
          - Organisations they created (non-demo)
          - Boards / Columns / Tasks / Comments / Activities they created
          - BoardMembership entries in demo boards
          - AI assistant sessions and messages
          - Analytics sessions
          - Messaging notifications / chat messages
          - API tokens and request logs
          - Decision center items
          - Wiki pages (if CASCADE)
          - Knowledge graph nodes (if CASCADE)
          etc.

        Celery tasks are suppressed during deletion because Redis may not be
        running in dev mode.  The deletion signals still fire but their
        apply_async calls become no-ops, avoiding 20-retry Redis timeout loops.
        """
        self.stdout.write('[2/4] Deleting real user accounts (and CASCADE artefacts) ...')
        count = real_users_qs.count()
        if count == 0:
            self.stdout.write('  (no real users found)')
            return

        # Suppress Celery task dispatch: signals will still fire but won't
        # block trying to reach a Redis broker that isn't available.
        import celery.app.task as _celery_task_mod
        _orig_apply_async = _celery_task_mod.Task.apply_async

        def _noop_apply_async(self_task, *args, **kwargs):
            return None

        _celery_task_mod.Task.apply_async = _noop_apply_async
        try:
            real_users_qs.delete()
        finally:
            _celery_task_mod.Task.apply_async = _orig_apply_async

        self.stdout.write(self.style.SUCCESS(f'  ✓ Deleted {count} real user account(s)'))

    def _step3_delete_non_demo_orgs(self):
        """
        Delete any remaining non-demo organisations.  This is a safety net for
        organisations whose created_by was already null or pointed to a demo user
        but the org itself is not a demo org.  CASCADE removes all boards/tasks
        beneath them.
        """
        self.stdout.write('[3/4] Deleting remaining non-demo organisations ...')
        from accounts.models import Organization
        qs = Organization.objects.filter(is_demo=False)
        count = qs.count()
        if count == 0:
            self.stdout.write('  (none found)')
            return
        for org in qs:
            self.stdout.write(f'  Deleting: {org.name}')
        qs.delete()
        self.stdout.write(self.style.SUCCESS(f'  ✓ Deleted {count} non-demo organisation(s)'))

    def _step4_clean_orphans(self):
        """
        Clean up records that survived because their user FK is SET_NULL.
        These are records with no owner that are not part of the demo data.
        """
        self.stdout.write('[4/4] Cleaning up orphaned records (SET_NULL fields) ...')
        total = 0

        cleanups = []

        # ai_assistant
        try:
            from ai_assistant.models import AIAssistantSession
            qs = AIAssistantSession.objects.filter(user__isnull=True)
            n = qs.count()
            if n:
                qs.delete()
                cleanups.append(f'AIAssistantSession (null user): {n}')
                total += n
        except Exception:
            pass

        # analytics
        try:
            from analytics.models import UserSession
            qs = UserSession.objects.filter(user__isnull=True)
            n = qs.count()
            if n:
                qs.delete()
                cleanups.append(f'UserSession (null user): {n}')
                total += n
        except Exception:
            pass

        # messaging – Notifications with no recipient
        try:
            from messaging.models import Notification
            qs = Notification.objects.filter(recipient__isnull=True)
            n = qs.count()
            if n:
                qs.delete()
                cleanups.append(f'Notification (null recipient): {n}')
                total += n
        except Exception:
            pass

        # wiki – pages with no author fall outside the demo org anyway
        # (demo wiki data is org-scoped and was protected in step 1)

        # api – request logs without a user
        try:
            from api.models import APIRequestLog
            qs = APIRequestLog.objects.filter(user__isnull=True)
            n = qs.count()
            if n:
                qs.delete()
                cleanups.append(f'APIRequestLog (null user): {n}')
                total += n
        except Exception:
            pass

        if cleanups:
            for msg in cleanups:
                self.stdout.write(self.style.SUCCESS(f'  ✓ Removed {msg}'))
        else:
            self.stdout.write('  (no orphaned records found)')

        if total:
            self.stdout.write(self.style.SUCCESS(f'  ✓ Total orphaned records removed: {total}'))

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------
    def _header(self, title):
        line = '=' * 70
        self.stdout.write('')
        self.stdout.write(self.style.WARNING(line))
        self.stdout.write(self.style.WARNING(f'  {title}'))
        self.stdout.write(self.style.WARNING(line))
