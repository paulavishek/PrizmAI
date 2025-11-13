"""
Management command to initialize RBAC system
Creates default roles for all organizations
"""
from django.core.management.base import BaseCommand
from accounts.models import Organization
from kanban.permission_models import Role


class Command(BaseCommand):
    help = 'Initialize RBAC system with default roles for all organizations'
    
    def add_arguments(self, parser):
        parser.add_argument(
            '--org-id',
            type=int,
            help='Initialize roles for specific organization ID only'
        )
    
    def handle(self, *args, **options):
        org_id = options.get('org_id')
        
        if org_id:
            try:
                organizations = [Organization.objects.get(id=org_id)]
            except Organization.DoesNotExist:
                self.stdout.write(self.style.ERROR(f'Organization with ID {org_id} not found'))
                return
        else:
            organizations = Organization.objects.all()
        
        total_orgs = 0
        total_roles = 0
        
        for org in organizations:
            self.stdout.write(f'\nProcessing organization: {org.name}')
            
            # Create default roles
            roles = Role.create_default_roles(org)
            
            self.stdout.write(self.style.SUCCESS(f'  ✓ Created {len(roles)} roles:'))
            for role in roles:
                self.stdout.write(f'    - {role.name}: {len(role.permissions)} permissions')
            
            total_orgs += 1
            total_roles += len(roles)
        
        self.stdout.write(self.style.SUCCESS(
            f'\nSuccessfully initialized RBAC for {total_orgs} organization(s), '
            f'created {total_roles} role(s)'
        ))
