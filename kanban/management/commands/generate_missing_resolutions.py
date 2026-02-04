"""
Management command to generate resolution suggestions for conflicts that don't have any.
Usage: python manage.py generate_missing_resolutions [--conflict-id=X] [--with-ai]
"""
from django.core.management.base import BaseCommand
from django.db.models import Count
from kanban.conflict_models import ConflictDetection, ConflictResolution
from kanban.utils.conflict_detection import ConflictResolutionSuggester
from kanban.utils.ai_conflict_resolution import AIConflictResolutionEngine


class Command(BaseCommand):
    help = 'Generate resolution suggestions for conflicts that are missing them'

    def add_arguments(self, parser):
        parser.add_argument(
            '--conflict-id',
            type=int,
            help='Generate resolutions for a specific conflict ID',
        )
        parser.add_argument(
            '--with-ai',
            action='store_true',
            help='Generate AI-powered resolution suggestions (requires API key)',
        )
        parser.add_argument(
            '--force',
            action='store_true',
            help='Regenerate resolutions even if they already exist',
        )

    def handle(self, *args, **options):
        conflict_id = options.get('conflict_id')
        with_ai = options.get('with_ai', False)
        force = options.get('force', False)
        
        self.stdout.write(self.style.NOTICE('Finding conflicts without resolutions...'))
        
        # Find conflicts without resolutions
        if conflict_id:
            conflicts = ConflictDetection.objects.filter(id=conflict_id, status='active')
            if not conflicts.exists():
                self.stdout.write(self.style.ERROR(f'Active conflict with ID {conflict_id} not found'))
                return
        else:
            # Find all active conflicts and annotate with resolution count
            conflicts = ConflictDetection.objects.filter(
                status='active'
            ).annotate(
                resolution_count=Count('resolutions')
            )
            
            if not force:
                # Only get conflicts without resolutions
                conflicts = conflicts.filter(resolution_count=0)
        
        total_conflicts = conflicts.count()
        
        if total_conflicts == 0:
            self.stdout.write(self.style.SUCCESS('All active conflicts already have resolution suggestions!'))
            return
        
        self.stdout.write(self.style.NOTICE(f'Found {total_conflicts} conflict(s) without resolutions'))
        self.stdout.write('')
        
        # Generate resolutions for each conflict
        total_resolutions = 0
        total_ai_resolutions = 0
        
        for conflict in conflicts:
            self.stdout.write(f'Processing: {conflict.title}')
            self.stdout.write(f'  Type: {conflict.get_conflict_type_display()}, Severity: {conflict.get_severity_display()}')
            
            # Delete existing resolutions if force mode
            if force:
                existing_count = conflict.resolutions.count()
                if existing_count > 0:
                    conflict.resolutions.all().delete()
                    self.stdout.write(f'  Deleted {existing_count} existing resolutions (force mode)')
            
            # Generate basic rule-based suggestions
            try:
                suggester = ConflictResolutionSuggester(conflict)
                basic_suggestions = suggester.generate_suggestions()
                
                self.stdout.write(self.style.SUCCESS(
                    f'  ✓ Generated {len(basic_suggestions)} basic resolution(s)'
                ))
                total_resolutions += len(basic_suggestions)
                
                # Display the suggestions
                for i, resolution in enumerate(basic_suggestions, 1):
                    self.stdout.write(f'    {i}. {resolution.title} (confidence: {resolution.ai_confidence}%)')
                
            except Exception as e:
                self.stdout.write(self.style.ERROR(
                    f'  ✗ Failed to generate basic resolutions: {str(e)}'
                ))
                continue
            
            # Generate AI suggestions if requested
            if with_ai:
                try:
                    ai_engine = AIConflictResolutionEngine()
                    ai_suggestions = ai_engine.generate_advanced_resolutions(conflict)
                    
                    self.stdout.write(self.style.SUCCESS(
                        f'  ✓ Generated {len(ai_suggestions)} AI-powered resolution(s)'
                    ))
                    total_ai_resolutions += len(ai_suggestions)
                    
                    # Display AI suggestions
                    for i, resolution in enumerate(ai_suggestions, 1):
                        self.stdout.write(f'    AI-{i}. {resolution.title} (confidence: {resolution.ai_confidence}%)')
                    
                except Exception as e:
                    self.stdout.write(self.style.WARNING(
                        f'  ! AI generation failed: {str(e)}'
                    ))
            
            self.stdout.write('')  # Blank line between conflicts
        
        # Summary
        self.stdout.write(self.style.SUCCESS('─' * 60))
        self.stdout.write(self.style.SUCCESS(f'Summary:'))
        self.stdout.write(self.style.SUCCESS(f'  Conflicts processed: {total_conflicts}'))
        self.stdout.write(self.style.SUCCESS(f'  Basic resolutions generated: {total_resolutions}'))
        if with_ai:
            self.stdout.write(self.style.SUCCESS(f'  AI resolutions generated: {total_ai_resolutions}'))
        self.stdout.write(self.style.SUCCESS('─' * 60))
        self.stdout.write(self.style.SUCCESS('\n✓ Resolution generation completed!'))
