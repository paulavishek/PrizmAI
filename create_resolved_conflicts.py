"""
Script to create resolved conflicts for demo analytics
"""
import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'kanban_board.settings')
django.setup()

from kanban.conflict_models import ConflictDetection, ConflictResolution, ResolutionPattern
from django.utils import timezone
from datetime import timedelta
import random

print('='*70)
print('CREATING RESOLVED CONFLICTS FOR ANALYTICS')
print('='*70)

# Get some active conflicts to resolve
active_conflicts = list(ConflictDetection.objects.filter(status='active').order_by('?')[:20])

if not active_conflicts:
    print('No active conflicts found!')
else:
    resolved_count = 0
    
    # Resolution strategies for different conflict types
    resolution_strategies = {
        'resource': [
            {
                'type': 'reassign',
                'title': 'Reassign tasks to available team member',
                'description': 'Reallocate overbooked tasks to team members with capacity',
                'ai_confidence': 85,
                'effectiveness': 4
            },
            {
                'type': 'reschedule',
                'title': 'Extend timeline to reduce workload pressure',
                'description': 'Add buffer time to prevent team burnout',
                'ai_confidence': 78,
                'effectiveness': 4
            },
            {
                'type': 'split_task',
                'title': 'Split task into smaller subtasks',
                'description': 'Break down complex task for parallel work',
                'ai_confidence': 82,
                'effectiveness': 5
            }
        ],
        'schedule': [
            {
                'type': 'adjust_dates',
                'title': 'Adjust due date based on dependencies',
                'description': 'Reschedule task to align with dependency completion',
                'ai_confidence': 88,
                'effectiveness': 4
            },
            {
                'type': 'reschedule',
                'title': 'Fast-track critical path tasks',
                'description': 'Prioritize tasks blocking other work',
                'ai_confidence': 80,
                'effectiveness': 4
            },
            {
                'type': 'adjust_dates',
                'title': 'Add buffer time for overdue tasks',
                'description': 'Realistic timeline adjustment with stakeholder approval',
                'ai_confidence': 75,
                'effectiveness': 3
            }
        ],
        'dependency': [
            {
                'type': 'remove_dependency',
                'title': 'Remove unnecessary dependency',
                'description': 'Break circular dependency by restructuring workflow',
                'ai_confidence': 90,
                'effectiveness': 5
            },
            {
                'type': 'modify_dependency',
                'title': 'Parallelize independent work streams',
                'description': 'Identify and execute non-dependent tasks concurrently',
                'ai_confidence': 84,
                'effectiveness': 4
            }
        ]
    }
    
    for conflict in active_conflicts[:20]:
        # Create 2-3 resolution suggestions for each conflict
        strategies = resolution_strategies.get(conflict.conflict_type, resolution_strategies['resource'])
        
        num_resolutions = random.randint(2, 3)
        for i, strategy_data in enumerate(strategies[:num_resolutions]):
            resolution = ConflictResolution.objects.create(
                conflict=conflict,
                resolution_type=strategy_data['type'],
                title=strategy_data['title'],
                description=strategy_data['description'],
                ai_confidence=strategy_data['ai_confidence'],
                ai_reasoning=f"Based on {conflict.conflict_type} conflict pattern analysis",
                action_steps=[
                    'Review current task allocation',
                    'Identify available resources or timeline adjustments',
                    'Implement changes and monitor results'
                ],
                estimated_impact=f"Expected to reduce conflict severity by {random.randint(60, 90)}%"
            )
        
        # Mark the first resolution as chosen and resolve the conflict
        chosen_resolution = conflict.resolutions.first()
        conflict.chosen_resolution = chosen_resolution
        conflict.status = 'resolved'
        conflict.resolved_at = timezone.now() - timedelta(days=random.randint(1, 14), hours=random.randint(0, 23))
        
        # Add effectiveness rating
        effectiveness = strategies[0]['effectiveness']
        conflict.resolution_effectiveness = effectiveness
        
        conflict.save()
        resolved_count += 1
    
    print(f'✓ Created and resolved {resolved_count} conflicts with resolutions')
    
    # Create some resolution patterns
    print()
    print('Creating resolution patterns...')
    
    pattern_data = [
        {
            'conflict_type': 'resource',
            'resolution_type': 'reassign',
            'success_rate': 0.85,
            'times_used': 8,
            'times_successful': 7,
            'avg_effectiveness_rating': 4.2,
            'context': {'overallocated_users': True, 'available_capacity': True}
        },
        {
            'conflict_type': 'schedule',
            'resolution_type': 'adjust_dates',
            'success_rate': 0.78,
            'times_used': 6,
            'times_successful': 5,
            'avg_effectiveness_rating': 3.8,
            'context': {'overdue_task': True, 'dependencies_met': True}
        },
        {
            'conflict_type': 'dependency',
            'resolution_type': 'remove_dependency',
            'success_rate': 0.92,
            'times_used': 4,
            'times_successful': 4,
            'avg_effectiveness_rating': 4.8,
            'context': {'circular_dependency': True}
        },
        {
            'conflict_type': 'resource',
            'resolution_type': 'split_task',
            'success_rate': 0.82,
            'times_used': 5,
            'times_successful': 4,
            'avg_effectiveness_rating': 4.4,
            'context': {'high_complexity': True, 'parallelizable': True}
        }
    ]
    
    patterns_created = 0
    for pdata in pattern_data:
        pattern, created = ResolutionPattern.objects.get_or_create(
            conflict_type=pdata['conflict_type'],
            resolution_type=pdata['resolution_type'],
            board=None,  # Global pattern
            defaults={
                'success_rate': pdata['success_rate'],
                'times_used': pdata['times_used'],
                'times_successful': pdata['times_successful'],
                'avg_effectiveness_rating': pdata['avg_effectiveness_rating'],
                'pattern_context': pdata['context'],
                'confidence_boost': (pdata['success_rate'] - 0.5) * 20  # Boost based on success
            }
        )
        if created:
            patterns_created += 1
    
    print(f'✓ Created {patterns_created} resolution patterns')
    
    # Summary
    print()
    print('='*70)
    print('✅ DEMO ANALYTICS DATA CREATED SUCCESSFULLY')
    print('='*70)
    print(f'Resolved Conflicts: {resolved_count}')
    print(f'Resolution Patterns: {patterns_created}')
    print()
    print('The analytics page should now show:')
    print('  ✓ Total resolved conflicts')
    print('  ✓ Average resolution time')
    print('  ✓ Average effectiveness rating')
    print('  ✓ Resolution patterns with success rates')
    print()
    print('Refresh the Conflict Analytics page to see the data!')
