"""
Idempotent Test Environment Setup
==================================
Sets up a comprehensive test environment for 3 test users with:
- Real workspaces with Enterprise preset
- Cross-board RBAC memberships (Owner/Member/Viewer rotation)
- Demo sandboxes provisioned

Re-runnable: uses get_or_create / update_or_create throughout.

Usage:
    python manage.py setup_test_environment
"""
from django.core.management.base import BaseCommand
from django.contrib.auth.models import User
from django.db import transaction
from django.utils import timezone


TEST_USERS = [
    {'username': 'testuser1', 'email': 'paul.biotech10@gmail.com'},
    {'username': 'testuser2', 'email': 'avip3310@gmail.com'},
    {'username': 'testuser3', 'email': 'avishekpaul1310@gmail.com'},
]


class Command(BaseCommand):
    help = 'Idempotent test environment setup for 3 test users'

    def handle(self, *args, **options):
        from accounts.models import Organization, UserProfile
        from kanban.models import (
            Board, BoardMembership, DemoSandbox, Workspace, WorkspacePreset,
        )
        from kanban.sandbox_views import _duplicate_board
        from kanban.utils.demo_protection import allow_demo_writes

        self.stdout.write(self.style.SUCCESS('\n' + '=' * 80))
        self.stdout.write(self.style.SUCCESS('  TEST ENVIRONMENT SETUP (idempotent)'))
        self.stdout.write(self.style.SUCCESS('=' * 80 + '\n'))

        # ------------------------------------------------------------------
        # Step 1: Verify test users exist
        # ------------------------------------------------------------------
        self.stdout.write('1. Verifying test users...')
        users = []
        for td in TEST_USERS:
            try:
                user = User.objects.get(email=td['email'])
                self.stdout.write(f'   [EXISTS] {user.username} ({user.email})')
                users.append(user)
            except User.DoesNotExist:
                self.stdout.write(self.style.ERROR(
                    f'   [MISSING] {td["username"]} ({td["email"]}) — '
                    f'please sign up first at /accounts/signup/'
                ))
                return

        # ------------------------------------------------------------------
        # Step 2: Ensure each user has a real (non-demo) organization + workspace
        # ------------------------------------------------------------------
        self.stdout.write('\n2. Ensuring real organizations & workspaces...')
        for user in users:
            profile = user.profile

            # Check for an existing real org
            real_org = Organization.objects.filter(
                created_by=user, is_demo=False,
            ).first()

            if not real_org:
                # Check if user's profile org is non-demo
                if profile.organization and not profile.organization.is_demo:
                    real_org = profile.organization
                else:
                    real_org = Organization.objects.create(
                        name=f"{user.username}'s Workspace",
                        created_by=user,
                        is_demo=False,
                    )
                    self.stdout.write(self.style.SUCCESS(
                        f'   [CREATED] Organization: {real_org.name}'
                    ))

            if real_org and (profile.organization is None or profile.organization.is_demo):
                profile.organization = real_org
                profile.save(update_fields=['organization'])
                self.stdout.write(f'   [UPDATED] {user.username} profile → org: {real_org.name}')
            else:
                self.stdout.write(f'   [EXISTS] {user.username} → org: {real_org.name}')

            # Workspace
            has_workspace = Workspace.objects.filter(
                created_by=user, is_demo=False,
            ).exists()

            if has_workspace:
                ws = Workspace.objects.filter(created_by=user, is_demo=False).first()
                self.stdout.write(f'   [EXISTS] Workspace: {ws.name}')
            else:
                ws = Workspace.objects.create(
                    name=f"{user.username}'s Workspace",
                    organization=real_org,
                    created_by=user,
                    is_demo=False,
                )
                self.stdout.write(self.style.SUCCESS(
                    f'   [CREATED] Workspace: {ws.name}'
                ))
                # Set as active workspace
                profile.active_workspace = ws
                profile.save(update_fields=['active_workspace'])

        # ------------------------------------------------------------------
        # Step 3: Set Enterprise preset for each user's organization
        # ------------------------------------------------------------------
        self.stdout.write('\n3. Setting Enterprise preset...')
        for user in users:
            org = user.profile.organization
            if org and not org.is_demo:
                preset, created = WorkspacePreset.objects.update_or_create(
                    organization=org,
                    defaults={'global_preset': 'enterprise'},
                )
                tag = '[CREATED]' if created else '[UPDATED]'
                self.stdout.write(f'   {tag} {org.name} → Enterprise')

        # ------------------------------------------------------------------
        # Step 4: Ensure each user has at least one board in their workspace
        # ------------------------------------------------------------------
        self.stdout.write('\n4. Ensuring each user has boards...')
        user_boards = {}  # user → first board (used for cross-RBAC)
        for user in users:
            ws = Workspace.objects.filter(created_by=user, is_demo=False).first()
            if not ws:
                continue
            boards = Board.objects.filter(
                workspace=ws, is_sandbox_copy=False, is_official_demo_board=False,
            )
            if boards.exists():
                user_boards[user.id] = boards.first()
                self.stdout.write(
                    f'   [EXISTS] {user.username} has {boards.count()} board(s) '
                    f'(first: "{boards.first().name}")'
                )
            else:
                from kanban.models import Column
                board = Board.objects.create(
                    name=f"{user.username}'s Test Board",
                    description='Auto-created by setup_test_environment',
                    workspace=ws,
                    organization=user.profile.organization,
                    created_by=user,
                    owner=user,
                )
                for i, col_name in enumerate(['To Do', 'In Progress', 'Review', 'Done']):
                    Column.objects.create(board=board, name=col_name, position=i)
                BoardMembership.objects.get_or_create(
                    board=board, user=user, defaults={'role': 'owner'},
                )
                user_boards[user.id] = board
                self.stdout.write(self.style.SUCCESS(
                    f'   [CREATED] Board: {board.name} (4 columns)'
                ))

        # ------------------------------------------------------------------
        # Step 5: Cross-board RBAC rotation
        #   user1's board → user2=member, user3=viewer
        #   user2's board → user3=member, user1=viewer
        #   user3's board → user1=member, user2=viewer
        # ------------------------------------------------------------------
        self.stdout.write('\n5. Cross-board RBAC memberships...')
        rotation = [
            # (board_owner_idx, member_idx, viewer_idx)
            (0, 1, 2),
            (1, 2, 0),
            (2, 0, 1),
        ]
        for owner_idx, member_idx, viewer_idx in rotation:
            owner_user = users[owner_idx]
            member_user = users[member_idx]
            viewer_user = users[viewer_idx]
            board = user_boards.get(owner_user.id)
            if not board:
                self.stdout.write(
                    f'   ⚠️ No board for {owner_user.username}, skipping rotation'
                )
                continue

            # Ensure owner membership
            BoardMembership.objects.get_or_create(
                board=board, user=owner_user, defaults={'role': 'owner'},
            )

            # Member
            mem, created = BoardMembership.objects.update_or_create(
                board=board, user=member_user,
                defaults={'role': 'member'},
            )
            tag = '[CREATED]' if created else '[UPDATED]'
            self.stdout.write(
                f'   {tag} {board.name}: {member_user.username}=member'
            )

            # Viewer
            mem, created = BoardMembership.objects.update_or_create(
                board=board, user=viewer_user,
                defaults={'role': 'viewer'},
            )
            tag = '[CREATED]' if created else '[UPDATED]'
            self.stdout.write(
                f'   {tag} {board.name}: {viewer_user.username}=viewer'
            )

        # ------------------------------------------------------------------
        # Step 6: Demo sandboxes
        # ------------------------------------------------------------------
        self.stdout.write('\n6. Provisioning demo sandboxes...')
        template_boards = list(
            Board.objects.filter(is_official_demo_board=True).order_by('name')
        )
        if not template_boards:
            self.stdout.write('   ⚠️ No demo template boards found — run create_demo_organization first')
        else:
            self.stdout.write(f'   Template boards: {[b.name for b in template_boards]}')

            for user in users:
                try:
                    user.demo_sandbox
                    existing_count = Board.objects.filter(
                        owner=user, is_sandbox_copy=True,
                    ).count()
                    template_count = len(template_boards)
                    if existing_count < template_count:
                        self.stdout.write(
                            f'   [PARTIAL] {user.username} has sandbox but only '
                            f'{existing_count}/{template_count} boards — '
                            f'duplicating missing boards'
                        )
                        existing_clones = set(
                            Board.objects.filter(
                                owner=user, is_sandbox_copy=True,
                            ).values_list('cloned_from_id', flat=True)
                        )
                        with allow_demo_writes():
                            for tmpl in template_boards:
                                if tmpl.id not in existing_clones:
                                    _duplicate_board(tmpl, user)
                                    self.stdout.write(
                                        f'      [CREATED] sandbox copy: {tmpl.name}'
                                    )
                    else:
                        self.stdout.write(
                            f'   [EXISTS] {user.username} has full sandbox '
                            f'({existing_count} boards)'
                        )
                except DemoSandbox.DoesNotExist:
                    self.stdout.write(
                        f'   [CREATING] Sandbox for {user.username}...'
                    )
                    with allow_demo_writes():
                        new_boards = []
                        for tmpl in template_boards:
                            try:
                                new_board = _duplicate_board(tmpl, user)
                                new_boards.append(new_board)
                            except Exception as e:
                                self.stdout.write(self.style.ERROR(
                                    f'      ✗ Failed to clone {tmpl.name}: {e}'
                                ))
                        if new_boards:
                            DemoSandbox.objects.create(user=user)
                            self.stdout.write(self.style.SUCCESS(
                                f'      ✓ Created sandbox with {len(new_boards)} boards'
                            ))

                            # Join demo org
                            demo_org = Organization.objects.filter(is_demo=True).first()
                            if demo_org:
                                profile = user.profile
                                if profile.organization != demo_org:
                                    # Don't overwrite real org — just ensure membership
                                    pass

        # ------------------------------------------------------------------
        # Step 7: Update onboarding status
        # ------------------------------------------------------------------
        self.stdout.write('\n7. Finalizing onboarding status...')
        for user in users:
            profile = user.profile
            if profile.onboarding_status in ('pending', 'demo_exploring'):
                ws = Workspace.objects.filter(
                    created_by=user, is_demo=False,
                ).first()
                if ws:
                    profile.onboarding_status = 'completed'
                    profile.active_workspace = ws
                    profile.is_viewing_demo = False
                    profile.save(update_fields=[
                        'onboarding_status', 'active_workspace', 'is_viewing_demo',
                    ])
                    self.stdout.write(
                        f'   [UPDATED] {user.username}: onboarding → completed, '
                        f'active workspace → {ws.name}'
                    )
            else:
                self.stdout.write(
                    f'   [OK] {user.username}: onboarding_status={profile.onboarding_status}'
                )

        # ------------------------------------------------------------------
        # Summary
        # ------------------------------------------------------------------
        self.stdout.write(self.style.SUCCESS('\n' + '=' * 80))
        self.stdout.write(self.style.SUCCESS('  ✓ TEST ENVIRONMENT SETUP COMPLETE'))
        self.stdout.write(self.style.SUCCESS('=' * 80))
        self.stdout.write('\nUser summary:')
        for user in users:
            profile = user.profile
            ws_count = Workspace.objects.filter(created_by=user, is_demo=False).count()
            board_count = Board.objects.filter(
                workspace__created_by=user, is_sandbox_copy=False,
            ).count()
            sandbox_count = Board.objects.filter(
                owner=user, is_sandbox_copy=True,
            ).count()
            memberships = BoardMembership.objects.filter(user=user).exclude(
                board__is_sandbox_copy=True,
            ).select_related('board')
            self.stdout.write(f'\n  {user.username} ({user.email}):')
            self.stdout.write(f'    Org: {profile.organization}')
            self.stdout.write(f'    Workspaces: {ws_count}')
            self.stdout.write(f'    Own boards: {board_count}')
            self.stdout.write(f'    Sandbox boards: {sandbox_count}')
            self.stdout.write(f'    Board memberships:')
            for m in memberships:
                self.stdout.write(
                    f'      - {m.board.name} ({m.role})'
                )
        self.stdout.write('')
