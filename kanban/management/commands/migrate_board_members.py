"""
Management command to migrate existing board members to RBAC system
[DEPRECATED] The legacy Role-based RBAC migration is no longer needed.
Use the data migration in kanban/migrations instead.
"""
from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = '[DEPRECATED] Legacy board member migration — no longer needed'

    def handle(self, *args, **options):
        self.stdout.write(self.style.WARNING(
            'This command is deprecated. Board member migration is now handled '
            'by Django data migrations. No action taken.'
        ))
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
