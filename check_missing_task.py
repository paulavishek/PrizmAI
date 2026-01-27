"""Check which tasks exist in Software Board Phase 3"""
import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'kanban_board.settings')
django.setup()

from kanban.models import Task, Board, Organization

demo_org = Organization.objects.filter(is_demo=True).first()
demo_boards = Board.objects.filter(organization=demo_org, is_official_demo_board=True)
software = demo_boards.filter(name__icontains='software').first()

if software:
    print("Software Board Phase 3 Tasks:")
    phase3_tasks = Task.objects.filter(column__board=software, phase='Phase 3').order_by('created_at')
    for i, task in enumerate(phase3_tasks, 1):
        print(f"{i}. {task.title}")
    
    print(f"\nTotal Phase 3 tasks: {phase3_tasks.count()}")
    
    # Expected Phase 3 tasks
    expected_tasks = [
        'Performance optimization',
        'Security audit fixes',
        'Mobile responsive polish',
        'Load testing',
        'Create user onboarding',
        'Set up monitoring',
        'Documentation review',
        'Accessibility improvements',
        'Deployment automation',
        'Launch preparation',
    ]
    
    print(f"\nExpected Phase 3 tasks: {len(expected_tasks)}")
    print("\nExpected tasks:")
    for i, title in enumerate(expected_tasks, 1):
        print(f"{i}. {title}")
    
    # Find missing tasks
    actual_titles = [task.title for task in phase3_tasks]
    missing = [t for t in expected_tasks if t not in actual_titles]
    
    if missing:
        print(f"\nMissing tasks:")
        for title in missing:
            print(f"  - {title}")
