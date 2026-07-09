"""
Sweep stale demo-persona BoardMembership rows off other users' sandbox copies.

Background
----------
Demo personas (priya.sharma / marcus.chen / elena.vasquez, @demo.prizmai.local)
are shared login credentials printed on-screen so any real user can test
cross-account flows (e.g. Messaging). ``_duplicate_board`` copies each
persona's membership onto every sandbox it clones, but — before this fix — it
never removed the persona's membership from *previously* cloned sandboxes.
Since every real user's sandbox persists indefinitely (no expiry), a persona
accumulated a permanent BoardMembership on every sandbox ever provisioned by
every real user, letting anyone signed in with the shared persona credentials
browse every other user's private sandbox boards indefinitely, and cluttering
the persona's own dashboard/Messaging Hub with dozens of stale duplicate
board cards.

``_duplicate_board`` now caps each persona to sandbox boards owned by
whichever REAL user most recently provisioned/reset their sandbox, and
``dashboard()`` / ``toggle_demo_mode()`` / ``reset_my_demo()`` no longer let a
persona account provision an independent sandbox of their own (personas are
guest-only). This command is the one-off cleanup for data that predates both
fixes:

1. A persona's guest membership on a board owned by ANOTHER persona (an
   artifact of a persona having once provisioned their own sandbox before the
   guard existed) is always stale — deleted unconditionally.
2. A persona's guest membership on more than one REAL user's sandbox is
   capped to whichever real user's ``DemoSandbox.last_accessed_at`` is most
   recent; the rest are deleted.

Official template board memberships, and any sandbox a persona owns
themselves, are never touched.

Dry-run by default: pass ``--apply`` to actually delete.
"""

from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = ("Delete stale demo-persona BoardMembership rows: unconditionally "
            "on boards owned by another persona, and capped to the most "
            "recently active real-user owner otherwise (dry-run unless "
            "--apply).")

    def add_arguments(self, parser):
        parser.add_argument(
            '--apply',
            action='store_true',
            help='Actually delete. Without this flag the command only reports counts.',
        )

    def handle(self, *args, **options):
        from django.contrib.auth.models import User
        from django.utils import timezone
        from kanban.models import BoardMembership, DemoSandbox

        apply = options['apply']
        _EPOCH = timezone.make_aware(timezone.datetime.min.replace(year=1970))
        _PERSONA_DOMAIN = '@demo.prizmai.local'

        personas = User.objects.filter(email__iendswith=_PERSONA_DOMAIN)
        persona_ids = set(personas.values_list('id', flat=True))
        if not personas.exists():
            self.stdout.write(self.style.SUCCESS('No demo persona accounts found — nothing to sweep.'))
            return

        total = 0
        for persona in personas:
            # A persona can end up owning their OWN sandbox (e.g. someone
            # logged in directly as marcus.chen and provisioned before the
            # guard existed). That board's owner-membership row must never
            # be touched — only cap the persona's GUEST memberships on
            # sandboxes owned by someone else.
            memberships = BoardMembership.objects.filter(
                user=persona,
                board__is_sandbox_copy=True,
            ).exclude(board__owner=persona).select_related('board')

            # Guest membership on a board owned by ANOTHER persona is always
            # an artifact of that persona's own (now-prevented) provisioning
            # — never a legitimate "current" board to keep.
            stale_ids = [m.id for m in memberships if m.board.owner_id in persona_ids]

            # Guest membership on real users' boards: cap to the one
            # most-recently accessed/provisioned.
            by_owner = {}
            for m in memberships:
                if m.board.owner_id in persona_ids:
                    continue
                by_owner.setdefault(m.board.owner_id, []).append(m)

            if len(by_owner) > 1:
                last_access = {
                    s.user_id: s.last_accessed_at
                    for s in DemoSandbox.objects.filter(user_id__in=by_owner.keys())
                }
                keep_owner_id = max(by_owner.keys(), key=lambda uid: last_access.get(uid) or _EPOCH)
                for owner_id, ms in by_owner.items():
                    if owner_id != keep_owner_id:
                        stale_ids.extend(m.id for m in ms)

            if not stale_ids:
                continue

            count = len(stale_ids)
            total += count
            self.stdout.write(self.style.WARNING(
                f'  {persona.username}: removing {count} stale membership(s)'
            ))
            if apply:
                BoardMembership.objects.filter(id__in=stale_ids).delete()

        if total == 0:
            self.stdout.write(self.style.SUCCESS('No stale persona memberships found — database is clean.'))
        elif not apply:
            self.stdout.write(self.style.WARNING(
                f'Total stale persona memberships: {total} (dry run — nothing deleted; re-run with --apply).'))
        else:
            self.stdout.write(self.style.SUCCESS(f'Swept {total} stale persona memberships.'))
