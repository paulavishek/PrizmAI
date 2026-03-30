"""
Management command to initialize RBAC system
[DEPRECATED] The legacy Role-based RBAC system has been replaced with
the new BoardMembership model (owner/member/viewer roles).
"""
from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = '[DEPRECATED] Legacy RBAC initialization — no longer needed'

    def handle(self, *args, **options):
        self.stdout.write(self.style.WARNING(
            'This command is deprecated. The legacy Role-based RBAC system '
            'has been replaced with the new BoardMembership model '
            '(owner/member/viewer roles). No action taken.'
        ))
            
            self.stdout.write(self.style.SUCCESS(f'  ✓ Created {len(roles)} roles:'))
            for role in roles:
                self.stdout.write(f'    - {role.name}: {len(role.permissions)} permissions')
            
            total_orgs += 1
            total_roles += len(roles)
        
        self.stdout.write(self.style.SUCCESS(
            f'\nSuccessfully initialized RBAC for {total_orgs} organization(s), '
            f'created {total_roles} role(s)'
        ))
