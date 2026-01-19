"""
Script to verify and summarize the created task dependencies
"""
import os
import django

# Setup Django environment
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'kanban_board.settings')
django.setup()

from kanban.models import Task, Board, Organization

def verify_dependencies():
    """Verify and display summary of all task dependencies"""
    
    # Get demo organization and boards
    demo_org = Organization.objects.filter(is_demo=True).first()
    if not demo_org:
        print("❌ No demo organization found!")
        return
    
    boards = Board.objects.filter(organization=demo_org, is_official_demo_board=True)
    if not boards.exists():
        print("❌ No demo boards found!")
        return
    
    print("\n" + "="*70)
    print("DEPENDENCY VERIFICATION SUMMARY")
    print("="*70 + "\n")
    
    total_deps = 0
    total_tasks = 0
    
    for board in boards:
        tasks = Task.objects.filter(column__board=board)
        total_tasks += tasks.count()
        
        # Count dependencies
        deps = sum([t.dependencies.count() for t in tasks])
        tasks_with_deps = sum([1 for t in tasks if t.dependencies.count() > 0])
        total_deps += deps
        
        print(f"📊 {board.name}")
        print(f"   Total tasks: {tasks.count()}")
        print(f"   Tasks with dependencies: {tasks_with_deps}")
        print(f"   Total dependencies: {deps}")
        print(f"   Avg dependencies per task: {deps/tasks.count():.2f}")
        print()
        
        # Show sample dependencies
        print(f"   Sample dependencies:")
        sample_tasks = list(tasks.filter(dependencies__isnull=False).distinct()[:5])
        for task in sample_tasks:
            deps_list = list(task.dependencies.all()[:2])
            deps_str = ", ".join([f'"{d.title[:30]}"' for d in deps_list])
            print(f"   • {task.title[:40]:40} depends on: {deps_str}")
        print()
    
    print("="*70)
    print(f"✅ TOTAL TASKS: {total_tasks}")
    print(f"✅ TOTAL DEPENDENCIES: {total_deps}")
    print(f"✅ Average dependencies per task: {total_deps/total_tasks:.2f}")
    print("="*70 + "\n")

if __name__ == '__main__':
    verify_dependencies()
