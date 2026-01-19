"""
Script to create comprehensive dependencies for all 120 tasks across the 3 demo boards
This creates realistic project dependencies following typical workflows
"""
import os
import django

# Setup Django environment
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'kanban_board.settings')
django.setup()

from kanban.models import Task, Board, Organization
from datetime import timedelta

def create_comprehensive_dependencies():
    """Create dependencies for all tasks in the demo boards"""
    
    # Get demo organization and boards
    demo_org = Organization.objects.filter(is_demo=True).first()
    if not demo_org:
        print("❌ No demo organization found!")
        return
    
    boards = Board.objects.filter(organization=demo_org, is_official_demo_board=True)
    if not boards.exists():
        print("❌ No demo boards found!")
        return
    
    print(f"✅ Found demo organization: {demo_org.name}")
    print(f"✅ Found {boards.count()} demo boards\n")
    
    total_dependencies = 0
    
    for board in boards:
        print(f"\n{'='*70}")
        print(f"📊 Processing Board: {board.name}")
        print(f"{'='*70}")
        
        # Get all tasks ordered by start date
        tasks = Task.objects.filter(
            column__board=board,
            start_date__isnull=False,
            due_date__isnull=False
        ).order_by('start_date')
        
        print(f"Found {tasks.count()} tasks with dates")
        
        if tasks.count() == 0:
            print("⚠️  No tasks with dates found, skipping...")
            continue
        
        # Clear existing dependencies
        print("\n🧹 Clearing existing dependencies...")
        cleared_count = 0
        for task in tasks:
            if task.dependencies.exists():
                cleared_count += task.dependencies.count()
                task.dependencies.clear()
        print(f"   Cleared {cleared_count} existing dependencies")
        
        # Create dependencies based on board type
        if "Software" in board.name:
            deps = create_software_dependencies(tasks)
        elif "Marketing" in board.name:
            deps = create_marketing_dependencies(tasks)
        elif "Bug" in board.name:
            deps = create_bug_dependencies(tasks)
        else:
            deps = create_generic_dependencies(tasks)
        
        total_dependencies += deps
        print(f"\n✅ Created {deps} dependencies for {board.name}")
    
    print(f"\n{'='*70}")
    print(f"🎉 COMPLETED: Created {total_dependencies} total dependencies")
    print(f"{'='*70}\n")


def find_task_by_keyword(tasks, keywords):
    """Find a task by keyword(s) in title (case-insensitive)"""
    if isinstance(keywords, str):
        keywords = [keywords]
    
    for keyword in keywords:
        keyword_lower = keyword.lower()
        for task in tasks:
            if keyword_lower in task.title.lower():
                return task
    return None


def add_dependency_safe(task, predecessor, verbose=True):
    """
    Add a dependency with date validation
    Returns True if added successfully, False otherwise
    """
    if not task or not predecessor:
        return False
    
    if task.id == predecessor.id:
        return False
    
    # Check if already exists
    if predecessor in task.dependencies.all():
        return False
    
    # Validate dates: predecessor must end before or when successor starts
    if predecessor.due_date and task.start_date:
        # Convert to date if datetime
        pred_date = predecessor.due_date.date() if hasattr(predecessor.due_date, 'date') else predecessor.due_date
        task_date = task.start_date.date() if hasattr(task.start_date, 'date') else task.start_date
        
        # More lenient: predecessor should end at or before successor starts (with 3 day grace period)
        if pred_date <= task_date + timedelta(days=3):
            task.dependencies.add(predecessor)
            if verbose:
                print(f"   ✓ {task.title[:40]:40} ← {predecessor.title[:40]}")
            return True
        # Silently skip date conflicts
    
    return False


def create_software_dependencies(tasks):
    """Create realistic dependencies for Software Development board"""
    print("\n🔧 Creating Software Development dependencies...")
    count = 0
    tasks_list = list(tasks)
    
    # Strategy: Create dependencies within the same workflow/phase
    # We'll create multiple dependency chains
    
    print("\n  📌 Creating dependency chains...")
    
    # Chain 1: Every task depends on previous task (sequential workflow)
    for i in range(1, min(22, len(tasks_list))):
        count += add_dependency_safe(tasks_list[i], tasks_list[i-1])
    
    # Chain 2: Later tasks depend on earlier foundational tasks
    if len(tasks_list) >= 20:
        # Tasks 10-25 each depend on task 5 and 3 (foundation)
        for i in range(10, 26):
            if i < len(tasks_list):
                count += add_dependency_safe(tasks_list[i], tasks_list[5])
                count += add_dependency_safe(tasks_list[i], tasks_list[3])
                if i % 2 == 0:
                    count += add_dependency_safe(tasks_list[i], tasks_list[2])
    
    # Chain 3: Advanced tasks depend on multiple earlier tasks
    if len(tasks_list) >= 30:
        for i in range(20, 36):
            if i < len(tasks_list):
                # Each task depends on 2-4 earlier tasks
                count += add_dependency_safe(tasks_list[i], tasks_list[i-10])
                count += add_dependency_safe(tasks_list[i], tasks_list[i-8])
                if i > 15:
                    count += add_dependency_safe(tasks_list[i], tasks_list[i-15])
                if i % 3 == 0:
                    count += add_dependency_safe(tasks_list[i], tasks_list[i-12])
    
    # Chain 4: Final tasks depend on mid-project tasks
    if len(tasks_list) >= 40:
        for i in range(30, 46):
            if i < len(tasks_list):
                count += add_dependency_safe(tasks_list[i], tasks_list[i-5])
                count += add_dependency_safe(tasks_list[i], tasks_list[i-10])
                count += add_dependency_safe(tasks_list[i], tasks_list[i-12])
    
    # Chain 5: Last tasks wrap up multiple threads
    if len(tasks_list) >= 50:
        for i in range(40, 50):
            if i < len(tasks_list):
                count += add_dependency_safe(tasks_list[i], tasks_list[i-8])
                count += add_dependency_safe(tasks_list[i], tasks_list[i-6])
                if i % 2 == 0:
                    count += add_dependency_safe(tasks_list[i], tasks_list[i-11])
    
    return count


def create_marketing_dependencies(tasks):
    """Create realistic dependencies for Marketing Campaign board"""
    print("\n📢 Creating Marketing Campaign dependencies...")
    count = 0
    tasks_list = list(tasks)
    
    print("\n  📌 Creating marketing workflow dependencies...")
    
    # Chain 1: Sequential content creation (first 15 tasks)
    for i in range(1, min(15, len(tasks_list))):
        count += add_dependency_safe(tasks_list[i], tasks_list[i-1])
    
    # Chain 2: Campaign execution depends on planning
    if len(tasks_list) >= 20:
        for i in range(12, 22):
            if i < len(tasks_list):
                # Execution tasks depend on planning tasks
                count += add_dependency_safe(tasks_list[i], tasks_list[i-8])
                count += add_dependency_safe(tasks_list[i], tasks_list[i-6])
    
    # Chain 3: Analysis depends on execution
    if len(tasks_list) >= 30:
        for i in range(20, 32):
            if i < len(tasks_list):
                count += add_dependency_safe(tasks_list[i], tasks_list[i-5])
                count += add_dependency_safe(tasks_list[i], tasks_list[i-10])
                count += add_dependency_safe(tasks_list[i], tasks_list[i-8])
    
    # Chain 4: Optimization depends on analysis
    if len(tasks_list) >= 40:
        for i in range(30, 40):
            if i < len(tasks_list):
                count += add_dependency_safe(tasks_list[i], tasks_list[i-6])
                count += add_dependency_safe(tasks_list[i], tasks_list[i-9])
    
    return count


def create_bug_dependencies(tasks):
    """Create realistic dependencies for Bug Tracking board"""
    print("\n🐛 Creating Bug Tracking dependencies...")
    count = 0
    tasks_list = list(tasks)
    
    print("\n  📌 Creating bug resolution dependencies...")
    
    # Chain 1: Sequential bug fixes (every other bug)
    for i in range(2, len(tasks_list), 2):
        if i < len(tasks_list):
            count += add_dependency_safe(tasks_list[i], tasks_list[i-2])
            if i > 4:
                count += add_dependency_safe(tasks_list[i], tasks_list[i-4])
    
    # Chain 2: Critical bugs get dependencies
    for i in range(5, min(18, len(tasks_list))):
        count += add_dependency_safe(tasks_list[i], tasks_list[i-5])
        if i > 8:
            count += add_dependency_safe(tasks_list[i], tasks_list[i-8])
    
    # Chain 3: Later bugs depend on earlier investigations
    if len(tasks_list) >= 20:
        for i in range(15, 24):
            if i < len(tasks_list):
                count += add_dependency_safe(tasks_list[i], tasks_list[i-10])
                count += add_dependency_safe(tasks_list[i], tasks_list[i-7])
    
    # Chain 4: Final bug fixes wrap up
    if len(tasks_list) >= 30:
        for i in range(20, 30):
            if i < len(tasks_list):
                count += add_dependency_safe(tasks_list[i], tasks_list[i-7])
                count += add_dependency_safe(tasks_list[i], tasks_list[i-5])
    
    return count


def create_generic_dependencies(tasks):
    """Create generic dependencies for any board type"""
    print("\n🔗 Creating generic dependencies...")
    count = 0
    tasks_list = list(tasks)
    
    # Create dependencies based on start dates - every 3rd and 5th task
    for i in range(len(tasks_list) - 1):
        if i % 3 == 0 and i > 0:  # Every 3rd task depends on previous
            count += add_dependency_safe(tasks_list[i], tasks_list[i-1])
        if i % 5 == 0 and i > 5:  # Every 5th task depends on 5 tasks back
            count += add_dependency_safe(tasks_list[i], tasks_list[i-5])
    
    return count


if __name__ == '__main__':
    print("\n" + "="*70)
    print("🚀 Creating Comprehensive Task Dependencies")
    print("="*70 + "\n")
    
    create_comprehensive_dependencies()
    
    print("\n✨ Done! Check the Gantt chart to see the dependencies.\n")
