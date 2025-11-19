"""
Management command to update existing wiki categories with appropriate AI assistant types
Based on category names, automatically assign meeting or documentation AI types
"""

from django.core.management.base import BaseCommand
from wiki.models import WikiCategory


class Command(BaseCommand):
    help = 'Update existing wiki categories with appropriate AI assistant types based on their names'

    def handle(self, *args, **options):
        # Keywords that indicate meeting-related categories
        meeting_keywords = [
            'meeting', 'meetings', 'standup', 'standups', 'sprint', 
            'retrospective', 'retro', 'planning', 'sync', 'review',
            'discussion', 'agenda', 'minutes'
        ]
        
        categories = WikiCategory.objects.all()
        updated_count = 0
        
        self.stdout.write(self.style.SUCCESS(f'Found {categories.count()} categories to process'))
        
        for category in categories:
            category_name_lower = category.name.lower()
            
            # Check if category name contains meeting keywords
            is_meeting = any(keyword in category_name_lower for keyword in meeting_keywords)
            
            # Determine AI type
            if is_meeting:
                new_type = 'meeting'
                type_name = 'Meeting Analysis'
            else:
                new_type = 'documentation'
                type_name = 'Documentation Assistant'
            
            # Update if different
            if category.ai_assistant_type != new_type:
                old_type = category.get_ai_assistant_type_display() if category.ai_assistant_type else 'Not set'
                category.ai_assistant_type = new_type
                category.save()
                updated_count += 1
                
                self.stdout.write(
                    self.style.SUCCESS(
                        f'✓ Updated "{category.name}": {old_type} → {type_name}'
                    )
                )
            else:
                self.stdout.write(
                    f'  "{category.name}" already set to {type_name}'
                )
        
        self.stdout.write(self.style.SUCCESS(f'\nUpdated {updated_count} categories'))
        self.stdout.write(
            self.style.WARNING(
                '\nReview the categories in the admin panel to ensure AI types are correct.'
            )
        )
