"""
Fix Marketing Campaign dependencies with logical workflow
"""
import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'kanban_board.settings')
django.setup()

from kanban.models import Task

def fix_marketing_dependencies():
    print("="*80)
    print("FIXING MARKETING CAMPAIGN DEPENDENCIES")
    print("="*80)
    
    # Marketing Campaign logical flow:
    # 1. Summer campaign graphics (Task #25) - completed
    # 2. Competitor analysis report (Task #26) - completed  
    # 3. Website redesign for Q4 launch (Task #22) - should depend on graphics & analysis
    # 4. Remove outdated content (Task #27) - part of website redesign
    # 5. New product announcement email (Task #24) - depends on redesign being done
    # 6. Monthly performance report (Task #23) - already has dependency on #25
    # 7. Q3 Email newsletter (Task #21) - already has dependency on #26
    # 8. Holiday social campaign (Task #19) - already has dependency on #26
    # 9. Video content strategy (Task #20) - already has dependencies on #24 and #23
    
    try:
        task_22 = Task.objects.get(id=22)  # Website redesign for Q4 launch
        task_24 = Task.objects.get(id=24)  # New product announcement email
        task_25 = Task.objects.get(id=25)  # Summer campaign graphics
        task_26 = Task.objects.get(id=26)  # Competitor analysis report
        task_27 = Task.objects.get(id=27)  # Remove outdated content
        
        print("\nAdding logical dependencies...")
        print("="*80)
        
        # Task #22: Website redesign depends on graphics and competitor analysis
        if task_25 not in task_22.dependencies.all():
            task_22.dependencies.add(task_25)
            print(f"✓ Task #22 (Website redesign) now depends on Task #25 (Summer campaign graphics)")
        
        if task_26 not in task_22.dependencies.all():
            task_22.dependencies.add(task_26)
            print(f"✓ Task #22 (Website redesign) now depends on Task #26 (Competitor analysis)")
        
        # Task #27: Remove outdated content depends on website redesign starting
        if task_22 not in task_27.dependencies.all():
            task_27.dependencies.add(task_22)
            print(f"✓ Task #27 (Remove outdated content) now depends on Task #22 (Website redesign)")
        
        # Task #24: New product announcement depends on website redesign
        if task_22 not in task_24.dependencies.all():
            task_24.dependencies.add(task_22)
            print(f"✓ Task #24 (New product announcement) now depends on Task #22 (Website redesign)")
        
        print("\n" + "="*80)
        print("UPDATED DEPENDENCY SUMMARY")
        print("="*80)
        
        tasks_to_check = [22, 24, 25, 26, 27, 23, 21, 19, 20]
        for task_id in tasks_to_check:
            task = Task.objects.get(id=task_id)
            deps = task.dependencies.all()
            print(f"\nTask #{task.id}: {task.title}")
            if deps.exists():
                print(f"  Dependencies ({deps.count()}):")
                for dep in deps:
                    print(f"    - Task #{dep.id}: {dep.title}")
            else:
                print(f"  Dependencies: None (independent task)")
        
        print("\n" + "="*80)
        print("✅ SUCCESS! Marketing Campaign dependencies updated.")
        print("="*80)
        print("\nView the updated Gantt chart at:")
        print("  http://localhost:8000/boards/3/gantt/")
        
        return True
        
    except Task.DoesNotExist as e:
        print(f"❌ Error: Task not found - {e}")
        return False
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == '__main__':
    if fix_marketing_dependencies():
        print("\n✅ All done!")
    else:
        print("\n❌ Failed to fix dependencies")
