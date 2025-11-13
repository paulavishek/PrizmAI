"""
Management command to migrate existing board members to RBAC system
"""
from django.core.management.base import BaseCommand
from django.db import transaction
from kanban.models import Board
from kanban.permission_models import Role, BoardMembership


class Command(BaseCommand):
    help = 'Migrate existing board members to RBAC system'
    
    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Show what would be migrated without making changes'
        )
        parser.add_argument(
            '--board-id',
            type=int,
            help='Migrate specific board ID only'
        )
    
    def handle(self, *args, **options):
        dry_run = options.get('dry_run', False)
        board_id = options.get('board_id')
        
        if board_id:
            boards = Board.objects.filter(id=board_id)
            if not boards.exists():
                self.stdout.write(self.style.ERROR(f'Board with ID {board_id} not found'))
                return
        else:
            boards = Board.objects.all()
        
        total_boards = 0
        total_memberships = 0
        
        for board in boards:
            self.stdout.write(f'\nProcessing board: {board.name} (ID: {board.id})')
            
            # Get default Editor role for this organization
            default_role = Role.objects.filter(
                organization=board.organization,
                name='Editor'
            ).first()
            
            if not default_role:
                self.stdout.write(self.style.WARNING(
                    f'  ⚠ No default role found for {board.organization.name}. '
                    f'Run initialize_rbac first.'
                ))
                continue
            
            # Get board creator
            creator = board.created_by
            
            # Give creator Admin role
            admin_role = Role.objects.filter(
                organization=board.organization,
                name='Admin'
            ).first()
            
            if admin_role and not BoardMembership.objects.filter(board=board, user=creator).exists():
                if not dry_run:
                    with transaction.atomic():
                        BoardMembership.objects.create(
                            board=board,
                            user=creator,
                            role=admin_role,
                            added_by=creator
                        )
                self.stdout.write(self.style.SUCCESS(
                    f'  ✓ Created Admin membership for creator: {creator.username}'
                ))
                total_memberships += 1
            
            # Migrate existing members
            members = board.members.all()
            migrated_count = 0
            
            for member in members:
                # Skip if already has membership
                if BoardMembership.objects.filter(board=board, user=member).exists():
                    continue
                
                if not dry_run:
                    with transaction.atomic():
                        BoardMembership.objects.create(
                            board=board,
                            user=member,
                            role=default_role,
                            added_by=creator
                        )
                
                migrated_count += 1
                total_memberships += 1
            
            if migrated_count > 0:
                self.stdout.write(self.style.SUCCESS(
                    f'  ✓ Migrated {migrated_count} member(s) to Editor role'
                ))
            else:
                self.stdout.write('  - No members to migrate')
            
            total_boards += 1
        
        if dry_run:
            self.stdout.write(self.style.WARNING(
                f'\nDRY RUN: Would have migrated {total_memberships} membership(s) '
                f'across {total_boards} board(s)'
            ))
        else:
            self.stdout.write(self.style.SUCCESS(
                f'\nSuccessfully migrated {total_memberships} membership(s) '
                f'across {total_boards} board(s)'
            ))
