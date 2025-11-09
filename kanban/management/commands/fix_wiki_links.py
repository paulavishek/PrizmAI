from django.core.management.base import BaseCommand
from wiki.models import WikiPage


class Command(BaseCommand):
    help = 'Fix broken wiki links in demo data'

    def handle(self, *args, **options):
        self.stdout.write(self.style.NOTICE('Fixing broken wiki links...'))
        
        # Find and update the Developer Onboarding Checklist page
        try:
            page = WikiPage.objects.get(title='Developer Onboarding Checklist')
            
            # Replace the old content with the new content (removing broken links)
            new_content = '''# Developer Onboarding Checklist

## Week 1: Setup & Introduction
- [ ] Get access to GitHub repository
- [ ] Set up local development environment
- [ ] Install required tools (Python, PostgreSQL, Redis)
- [ ] Run the application locally
- [ ] Meet the team members
- [ ] Review codebase structure

## Week 2: First Tasks
- [ ] Fix your first bug
- [ ] Submit your first pull request
- [ ] Attend sprint planning
- [ ] Read all technical documentation
- [ ] Set up your IDE with project settings

## Week 3: Integration
- [ ] Take on a feature task
- [ ] Participate in code reviews
- [ ] Join team standups
- [ ] Learn about deployment process

## Key Information
- Complete source code is available in the GitHub repository
- Technical documentation is maintained in the team wiki
- Database schemas are documented in our internal documentation
- Our code follows PEP 8 style guidelines
'''
            
            page.content = new_content
            page.save()
            
            self.stdout.write(
                self.style.SUCCESS(
                    f'✓ Successfully updated "Developer Onboarding Checklist" page'
                )
            )
            
        except WikiPage.DoesNotExist:
            self.stdout.write(
                self.style.WARNING(
                    'Developer Onboarding Checklist page not found'
                )
            )
        
        self.stdout.write(self.style.SUCCESS('Wiki links fixed!'))
