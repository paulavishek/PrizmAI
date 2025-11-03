"""
Script to fix missing task dependencies in the Software Project board
"""
import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'kanban_board.settings')
django.setup()

from kanban.models import Task

def fix_dependencies():
    print("=" * 80)
    print("FIXING MISSING TASK DEPENDENCIES")
    print("=" * 80)
    
    # Software Project Board - last 4 tasks need proper dependencies
    # Based on logical project flow:
    # 1. Design Database Schema (Task #29)
    # 2. Implement Backend API (Task #30) - depends on Database Schema
    # 3. Create Frontend UI (Task #31) - depends on Backend API
    # 4. Testing and QA (Task #32) - depends on Frontend UI and Backend API
    # 5. Deployment (Task #33) - depends on Testing and QA
    
    try:
        # Get tasks by ID
        task_29 = Task.objects.get(id=29)  # Design Database Schema
        task_30 = Task.objects.get(id=30)  # Implement Backend API
        task_31 = Task.objects.get(id=31)  # Create Frontend UI
        task_32 = Task.objects.get(id=32)  # Testing and QA
        task_33 = Task.objects.get(id=33)  # Deployment
        
        print("\nCurrent Dependencies:")
        print(f"Task #30 ({task_30.title}): {list(task_30.dependencies.all())}")
        print(f"Task #31 ({task_31.title}): {list(task_31.dependencies.all())}")
        print(f"Task #32 ({task_32.title}): {list(task_32.dependencies.all())}")
        print(f"Task #33 ({task_33.title}): {list(task_33.dependencies.all())}")
        
        # Add dependencies
        print("\n" + "="*80)
        print("Adding logical dependencies...")
        print("="*80)
        
        # Task #30: Implement Backend API depends on Design Database Schema
        if task_29 not in task_30.dependencies.all():
            task_30.dependencies.add(task_29)
            print(f"✓ Added: Task #30 now depends on Task #29 (Design Database Schema)")
        
        # Task #31: Create Frontend UI depends on Implement Backend API
        if task_30 not in task_31.dependencies.all():
            task_31.dependencies.add(task_30)
            print(f"✓ Added: Task #31 now depends on Task #30 (Implement Backend API)")
        
        # Task #32: Testing and QA depends on both Backend API and Frontend UI
        if task_30 not in task_32.dependencies.all():
            task_32.dependencies.add(task_30)
            print(f"✓ Added: Task #32 now depends on Task #30 (Implement Backend API)")
        
        if task_31 not in task_32.dependencies.all():
            task_32.dependencies.add(task_31)
            print(f"✓ Added: Task #32 now depends on Task #31 (Create Frontend UI)")
        
        # Task #33: Deployment depends on Testing and QA
        if task_32 not in task_33.dependencies.all():
            task_33.dependencies.add(task_32)
            print(f"✓ Added: Task #33 now depends on Task #32 (Testing and QA)")
        
        print("\n" + "="*80)
        print("Updated Dependencies:")
        print("="*80)
        print(f"\nTask #30 ({task_30.title}):")
        for dep in task_30.dependencies.all():
            print(f"  → Depends on Task #{dep.id}: {dep.title}")
        
        print(f"\nTask #31 ({task_31.title}):")
        for dep in task_31.dependencies.all():
            print(f"  → Depends on Task #{dep.id}: {dep.title}")
        
        print(f"\nTask #32 ({task_32.title}):")
        for dep in task_32.dependencies.all():
            print(f"  → Depends on Task #{dep.id}: {dep.title}")
        
        print(f"\nTask #33 ({task_33.title}):")
        for dep in task_33.dependencies.all():
            print(f"  → Depends on Task #{dep.id}: {dep.title}")
        
        print("\n" + "="*80)
        print("✅ SUCCESS! Dependencies have been added.")
        print("="*80)
        print("\nThe Gantt chart should now show complete dependency chains.")
        print("Refresh the Gantt chart page to see the changes:")
        print("  http://localhost:8000/boards/1/gantt/")
        
    except Task.DoesNotExist as e:
        print(f"❌ Error: Task not found - {e}")
        return False
    except Exception as e:
        print(f"❌ Error: {e}")
        return False
    
    return True

if __name__ == '__main__':
    if fix_dependencies():
        print("\n✅ All done!")
    else:
        print("\n❌ Failed to fix dependencies")
