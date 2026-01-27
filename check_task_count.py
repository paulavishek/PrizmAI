"""Check task count per demo board"""
import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'kanban_board.settings')
django.setup()

from kanban.models import Task, Board, Organization

demo_org = Organization.objects.filter(is_demo=True).first()
if not demo_org:
    print("No demo organization found!")
    exit(1)

demo_boards = Board.objects.filter(organization=demo_org, is_official_demo_board=True)
software = demo_boards.filter(name__icontains='software').first()
marketing = demo_boards.filter(name__icontains='marketing').first()
bug = demo_boards.filter(name__icontains='bug').first()

software_count = Task.objects.filter(column__board=software).count() if software else 0
marketing_count = Task.objects.filter(column__board=marketing).count() if marketing else 0
bug_count = Task.objects.filter(column__board=bug).count() if bug else 0
total_count = Task.objects.filter(column__board__in=demo_boards).count()

print(f"Software Development Board: {software_count} tasks")
print(f"Marketing Campaign Board: {marketing_count} tasks")
print(f"Bug Tracking Board: {bug_count} tasks")
print(f"Total: {total_count} tasks")
print(f"\nExpected: 90 tasks (30 per board)")
print(f"Missing: {90 - total_count} task(s)")

# Check which phases have how many tasks
if software:
    print(f"\nSoftware Board by Phase:")
    for phase in ['Phase 1', 'Phase 2', 'Phase 3']:
        count = Task.objects.filter(column__board=software, phase=phase).count()
        print(f"  {phase}: {count} tasks")

if marketing:
    print(f"\nMarketing Board by Phase:")
    for phase in ['Phase 1', 'Phase 2', 'Phase 3']:
        count = Task.objects.filter(column__board=marketing, phase=phase).count()
        print(f"  {phase}: {count} tasks")

if bug:
    print(f"\nBug Board by Phase:")
    for phase in ['Phase 1', 'Phase 2', 'Phase 3']:
        count = Task.objects.filter(column__board=bug, phase=phase).count()
        print(f"  {phase}: {count} tasks")
