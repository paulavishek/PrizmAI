"""
Management Command: Populate Second-Project Organizational Memory
================================================================
Seeds a SECOND demo project into Organizational Memory so the "cross-project"
pitch ("have we done X before?") is actually demonstrable in the demo.

The demo has a single official board (Software Development). Standing up a full
second board with columns/tasks/sandbox-cloning is the fragile path; instead
this seeds a lightweight, ARCHIVED (wound-down / Exit-Protocol-style) board —
"Mobile App Launch" — that exists purely as a MEMORY SOURCE:

- The board carries no task board and is not cloned per user (it is archived and
  never listed by get_user_boards()).
- Its memory nodes are all ``is_org_wide=True`` and live in the demo workspace,
  so every demo user sees them via the workspace-wide visibility clause in
  ``knowledge_graph.views._accessible_memory_qs`` — no cloning required.
- A few cross-project MemoryConnections link Mobile App Launch lessons to the
  Software Development decisions/lessons they echo, so the knowledge graph shows
  real cross-project edges, not just intra-project ones.

Usage:
    python manage.py populate_second_project_memory
    python manage.py populate_second_project_memory --reset  # clear & recreate

Idempotent: fully owns the "Mobile App Launch" board's memory graph and wipes it
before reseeding (MemoryConnection rows cascade with their nodes).
"""
from django.core.management.base import BaseCommand
from django.contrib.auth.models import User
from django.utils import timezone
from datetime import timedelta

from kanban.models import Board
from accounts.models import Organization
from accounts.demo_personas import DEMO_PERSONAS
from knowledge_graph.models import MemoryNode, MemoryConnection

SECOND_BOARD_NAME = 'Mobile App Launch'


class Command(BaseCommand):
    help = 'Seed a second (archived) demo project into Organizational Memory for the cross-project story'

    def add_arguments(self, parser):
        parser.add_argument(
            '--reset',
            action='store_true',
            help='Clear existing Mobile App Launch memory before reseeding (default behaviour is already clear-and-replace).',
        )

    def handle(self, *args, **options):
        self.stdout.write('=' * 80)
        self.stdout.write('POPULATING SECOND-PROJECT ORGANIZATIONAL MEMORY')
        self.stdout.write('=' * 80)

        demo_org = Organization.objects.filter(is_demo=True).first()
        if not demo_org:
            self.stdout.write(self.style.ERROR('[FAIL] No demo organization found (is_demo=True)!'))
            self.stdout.write('   Please run: python manage.py create_demo_organization')
            return
        self.stdout.write(self.style.SUCCESS(f'[OK] Found organization: {demo_org.name}'))

        # Anchor to the existing Software Development template board so the second
        # project shares its workspace (visibility) and can link to its memories.
        sd_board = Board.objects.filter(
            is_official_demo_board=True, name='Software Development',
        ).first()
        if not sd_board:
            self.stdout.write(self.style.ERROR('[FAIL] Software Development demo board not found!'))
            self.stdout.write('   Please run: python manage.py populate_all_demo_data first')
            return

        demo_ws = sd_board.workspace
        self.stdout.write(f'   Demo workspace: {demo_ws} (id={getattr(demo_ws, "id", None)})')

        priya = User.objects.filter(username=DEMO_PERSONAS['lead']['username']).first()
        marcus = User.objects.filter(username=DEMO_PERSONAS['frontend']['username']).first()
        elena = User.objects.filter(username=DEMO_PERSONAS['devops']['username']).first()
        # Fall back to any demo user so a partial persona set never crashes the seed.
        fallback = priya or marcus or elena or User.objects.filter(profile__is_demo_account=True).first()
        priya = priya or fallback
        marcus = marcus or fallback
        elena = elena or fallback
        if not fallback:
            self.stdout.write(self.style.ERROR('[FAIL] No demo users found!'))
            return

        # ── The archived second board ─────────────────────────────────────────
        board, created = Board.objects.get_or_create(
            name=SECOND_BOARD_NAME,
            is_official_demo_board=True,
            defaults={
                'description': (
                    'Native mobile companion app (iOS/Android) for the platform. '
                    'Shipped v1 last year and has since been wound down — kept here '
                    'as an organizational-memory source of decisions and lessons.'
                ),
                'organization': demo_org,
                'workspace': demo_ws,
                'owner': priya,
                'created_by': priya,
                'is_archived': True,
                'is_seed_demo_data': True,
            },
        )
        # Enforce the invariants even if the board pre-existed with drift.
        Board.objects.filter(pk=board.pk).update(
            organization=demo_org,
            workspace=demo_ws,
            is_archived=True,
            is_official_demo_board=True,
            is_seed_demo_data=True,
            is_sandbox_copy=False,
        )
        board.refresh_from_db()
        self.stdout.write(self.style.SUCCESS(
            f'[OK] {"Created" if created else "Reusing"} board: {board.name} (id={board.pk}, archived)'
        ))

        # Clear-and-replace: this command fully owns this board's memory graph.
        deleted, _ = MemoryNode.objects.filter(board=board).delete()
        if deleted:
            self.stdout.write(self.style.WARNING(f'   Cleared {deleted} existing rows (nodes + connections)'))

        def past(days):
            return timezone.now() - timedelta(days=days)

        # ── Cross-project memories (all workspace-wide) ───────────────────────
        # Deliberately echo themes from Software Development (database migration
        # complexity, auth edge cases, notification fatigue, real-time load) so
        # "have we done X before?" returns a real second data point.
        entries = [
            {
                'node_type': 'decision',
                'title': 'React Native chosen over separate native iOS/Android builds',
                'content': (
                    'For the Mobile App Launch we evaluated fully-native (Swift + Kotlin) versus '
                    'React Native. Chose React Native to share ~80% of the codebase across platforms '
                    'with a three-person team. Trade-off: a few platform-specific modules (push, '
                    'biometrics) still needed native bridges, but the shared business logic and single '
                    'release cadence justified it for a v1.'
                ),
                'tags': ['mobile', 'react-native', 'architecture'],
                'importance': 0.86, 'author': marcus, 'days': 300,
            },
            {
                'node_type': 'decision',
                'title': 'Offline-first sync chosen for the mobile client',
                'content': (
                    'Mobile users are frequently on flaky connections, so we designed the app '
                    'offline-first: a local queue of mutations reconciled against the server on '
                    'reconnect. This mirrors the conflict-resolution thinking from the web platform '
                    'but had to handle much longer offline windows (hours, not seconds).'
                ),
                'tags': ['mobile', 'offline', 'sync', 'architecture'],
                'importance': 0.82, 'author': elena, 'days': 285,
            },
            {
                'node_type': 'lesson',
                'title': 'App-store review cycle added a hard 3-day tail to every mobile release',
                'content': (
                    'Unlike the web platform where we ship continuously, every Mobile App Launch '
                    'release had to clear Apple App Store review — routinely 24–72 hours, occasionally '
                    'a rejection round-trip. We under-planned this in the first two releases and missed '
                    'a marketing date. Lesson: bake the review tail into the release schedule and submit '
                    'a release candidate days before the announced date.'
                ),
                'tags': ['mobile', 'release', 'process', 'app-store'],
                'importance': 0.84, 'author': priya, 'days': 250,
            },
            {
                'node_type': 'lesson',
                'title': 'Database migration on mobile clients is far riskier than on the server',
                'content': (
                    'A schema migration to the on-device SQLite store bricked the app for a subset of '
                    'users who upgraded across two versions at once — the intermediate migration never '
                    'ran. This is the same "underestimated migration complexity" pattern we hit on the '
                    'web Database Schema & Migrations work, but with no ability to roll back once the '
                    'binary is on a user\'s phone. Always test multi-version upgrade paths, not just '
                    'the latest-to-next step.'
                ),
                'tags': ['mobile', 'database', 'migration', 'lesson'],
                'importance': 0.88, 'author': elena, 'days': 210,
            },
            {
                'node_type': 'lesson',
                'title': 'Push-notification opt-out mirrored the web notification-fatigue lesson',
                'content': (
                    'Within the first two weeks, 55% of mobile users disabled push notifications — '
                    'almost exactly the opt-out rate we saw with email on the web platform. The root '
                    'cause was identical: too many low-value pings. We should have carried the '
                    'digest-first, granular-controls lesson straight over to mobile instead of '
                    'relearning it.'
                ),
                'tags': ['mobile', 'notifications', 'ux', 'lesson'],
                'importance': 0.83, 'author': marcus, 'days': 190,
            },
            {
                'node_type': 'lesson',
                'title': 'Biometric auth edge cases echoed the JWT happy-path estimation miss',
                'content': (
                    'Face ID / fingerprint login looked simple but the edge cases — enrollment changes, '
                    'lockout after failed attempts, fallback to passcode, token refresh while backgrounded '
                    '— took three times the estimate. Same shape as the web Authentication System lesson: '
                    'auth is never as small as the happy path suggests.'
                ),
                'tags': ['mobile', 'authentication', 'biometrics', 'estimation'],
                'importance': 0.80, 'author': elena, 'days': 175,
            },
            {
                'node_type': 'risk_event',
                'title': 'Missed deadline: iOS 17 compatibility hotfix',
                'content': (
                    'An iOS point release changed keyboard behaviour and broke the mobile task-entry '
                    'form for a week before we shipped a hotfix — delayed by the app-store review tail. '
                    'Flagged as a recurring platform-dependency risk for any native client.'
                ),
                'tags': ['mobile', 'ios', 'risk', 'deadline'],
                'importance': 0.72, 'author': marcus, 'days': 160,
            },
            {
                'node_type': 'decision',
                'title': 'Real-time collaboration deferred on mobile for v1',
                'content': (
                    'The web platform ships real-time collaboration on Redis Pub/Sub, but on mobile the '
                    'battery and reconnect cost of a persistent socket was too high for v1. We deferred '
                    'live cursors to a later release and shipped offline-first sync instead — a deliberate '
                    'scope call, not an oversight.'
                ),
                'tags': ['mobile', 'real-time', 'scope', 'architecture'],
                'importance': 0.78, 'author': priya, 'days': 150,
            },
            {
                'node_type': 'milestone',
                'title': 'Milestone: Mobile App Launch v1 shipped to both stores',
                'content': (
                    'The native companion app reached general availability on the App Store and Google '
                    'Play. ~12k installs in the first month. This wound-down project is retained as an '
                    'organizational-memory reference for future native work.'
                ),
                'tags': ['mobile', 'launch', 'milestone'],
                'importance': 0.85, 'author': priya, 'days': 120,
            },
            {
                'node_type': 'lesson',
                'title': 'Crash-free rate is the mobile metric that mattered, not uptime',
                'content': (
                    'On the web we watch server uptime; on mobile the equivalent trust metric is the '
                    'crash-free session rate. We wired up crash reporting late and spent the first month '
                    'blind to a native-bridge crash affecting older Android devices. Instrument crash '
                    'reporting from day one on any future mobile project.'
                ),
                'tags': ['mobile', 'observability', 'quality', 'lesson'],
                'importance': 0.79, 'author': elena, 'days': 110,
            },
        ]

        nodes_by_title = {}
        for e in entries:
            node = MemoryNode.objects.create(
                board=board,
                node_type=e['node_type'],
                title=e['title'][:200],
                content=e['content'],
                tags=e['tags'],
                created_by=e['author'],
                is_auto_captured=e['node_type'] in ('risk_event', 'milestone'),
                is_org_wide=True,          # visible to every demo-workspace member
                importance_score=e['importance'],
                gaps_analyzed=True,        # don't trigger lazy analysis; curated
                has_gaps=False,
            )
            MemoryNode.objects.filter(pk=node.pk).update(created_at=past(e['days']))
            nodes_by_title[e['title']] = node
        self.stdout.write(self.style.SUCCESS(f'   Seeded {len(nodes_by_title)} workspace-wide memories'))

        # ── Cross-project connections to Software Development memories ─────────
        def sd_node(title_contains):
            return (
                MemoryNode.objects.filter(board=sd_board, title__icontains=title_contains)
                .order_by('pk').first()
            )

        cross_links = [
            {
                'from_title': 'Database migration on mobile clients is far riskier than on the server',
                'to_sd': 'Underestimated database migration complexity',
                'type': 'similar_to',
                'reason': (
                    'Both projects hit the same estimation failure on database migrations. The mobile '
                    'multi-version upgrade break is the web "always add buffer" lesson taken to its '
                    'harsher extreme, where a bad migration cannot be rolled back once installed.'
                ),
            },
            {
                'from_title': 'Push-notification opt-out mirrored the web notification-fatigue lesson',
                'to_sd': 'Notification fatigue is real',
                'type': 'similar_to',
                'reason': (
                    'The 55% mobile push opt-out almost exactly matches the web email opt-out. Same '
                    'root cause, same fix (digest-first, granular controls) — the web lesson should '
                    'have been carried straight over to mobile.'
                ),
            },
            {
                'from_title': 'Biometric auth edge cases echoed the JWT happy-path estimation miss',
                'to_sd': 'Authentication edge cases always take longer',
                'type': 'similar_to',
                'reason': (
                    'Biometric login and JWT auth both blew their estimates on edge cases (lockout, '
                    'refresh, fallback). Authentication is never as small as the happy path suggests, '
                    'on web or mobile.'
                ),
            },
            {
                'from_title': 'Real-time collaboration deferred on mobile for v1',
                'to_sd': 'Redis selected for real-time collaboration layer',
                'type': 'similar_to',
                'reason': (
                    'The web platform shipped real-time collaboration on Redis Pub/Sub; mobile '
                    'deliberately deferred it for v1 due to battery/reconnect cost. Same feature, '
                    'opposite scope call driven by the platform constraints.'
                ),
            },
        ]

        made = 0
        for link in cross_links:
            src = nodes_by_title.get(link['from_title'])
            dst = sd_node(link['to_sd'])
            if not src or not dst:
                self.stdout.write(self.style.WARNING(
                    f'   Skipped link (missing node): {link["from_title"][:40]} -> {link["to_sd"][:40]}'
                ))
                continue
            MemoryConnection.objects.get_or_create(
                from_node=src, to_node=dst, connection_type=link['type'],
                defaults={'reason': link['reason'], 'ai_generated': True},
            )
            made += 1
        self.stdout.write(self.style.SUCCESS(f'   Seeded {made} cross-project connections'))

        self.stdout.write('')
        self.stdout.write(self.style.SUCCESS('=' * 80))
        self.stdout.write(self.style.SUCCESS('[OK] SECOND-PROJECT MEMORY COMPLETE'))
        self.stdout.write(self.style.SUCCESS('=' * 80))
