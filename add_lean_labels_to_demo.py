"""
Quick script to add Lean Six Sigma labels to existing demo tasks
"""
import os
import django

# Setup Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'kanban_board.settings')
django.setup()

from kanban.models import Board, Task, TaskLabel, Organization

def main():
    print("Adding Lean Six Sigma labels to demo tasks...")
    
    # Get demo organization
    demo_org = Organization.objects.filter(is_demo=True, name='Demo - Acme Corporation').first()
    if not demo_org:
        print("❌ Demo organization not found")
        return
    
    # Get demo boards
    boards = Board.objects.filter(
        organization=demo_org,
        is_official_demo_board=True
    )
    
    if not boards:
        print("❌ No demo boards found")
        return
    
    print(f"Found {boards.count()} demo boards")
    
    # Create lean labels for each board
    lean_labels_data = [
        {'name': 'Value-Added', 'color': '#28a745', 'category': 'lean'},  # Green
        {'name': 'Necessary NVA', 'color': '#ffc107', 'category': 'lean'},  # Yellow
        {'name': 'Waste/Eliminate', 'color': '#dc3545', 'category': 'lean'}  # Red
    ]
    
    labels_created = 0
    for board in boards:
        for label_data in lean_labels_data:
            label, created = TaskLabel.objects.get_or_create(
                name=label_data['name'],
                board=board,
                category='lean',
                defaults={'color': label_data['color']}
            )
            if created:
                labels_created += 1
    
    print(f"✅ Created/verified {labels_created} Lean labels")
    
    # Assign labels to tasks
    all_tasks = Task.objects.filter(column__board__in=boards)
    print(f"Found {all_tasks.count()} demo tasks")
    
    value_added_count = 0
    necessary_count = 0
    waste_count = 0
    
    for task in all_tasks:
        board = task.column.board
        
        # Get labels for this board
        value_label = TaskLabel.objects.filter(
            name='Value-Added', board=board, category='lean'
        ).first()
        necessary_label = TaskLabel.objects.filter(
            name='Necessary NVA', board=board, category='lean'
        ).first()
        waste_label = TaskLabel.objects.filter(
            name='Waste/Eliminate', board=board, category='lean'
        ).first()
        
        # Value-Added keywords
        value_keywords = ['implement', 'build', 'create', 'develop', 'design', 'api', 'authentication',
                         'feature', 'landing page', 'campaign', 'video', 'content', 'user', 'system']
        
        # Necessary NVA keywords
        necessary_keywords = ['test', 'review', 'document', 'plan', 'meeting', 'research',
                             'analyze', 'investigate', 'fix bug', 'setup', 'configure', 'fix', 'bug']
        
        # Waste keywords
        waste_keywords = ['rework', 'redo', 'duplicate', 'unnecessary', 'redundant',
                         'refactor old', 'update deprecated']
        
        title_lower = task.title.lower()
        desc_lower = (task.description or '').lower()
        
        # Skip if already has a lean label
        if task.labels.filter(category='lean').exists():
            continue
        
        # Categorize based on keywords
        if any(keyword in title_lower or keyword in desc_lower for keyword in waste_keywords):
            if waste_label:
                task.labels.add(waste_label)
                waste_count += 1
        elif any(keyword in title_lower or keyword in desc_lower for keyword in necessary_keywords):
            if necessary_label:
                task.labels.add(necessary_label)
                necessary_count += 1
        elif any(keyword in title_lower or keyword in desc_lower for keyword in value_keywords):
            if value_label:
                task.labels.add(value_label)
                value_added_count += 1
        else:
            # Default: High/Urgent priority = Value-Added, Low = Necessary NVA
            if task.priority in ['high', 'urgent']:
                if value_label:
                    task.labels.add(value_label)
                    value_added_count += 1
            else:
                if necessary_label:
                    task.labels.add(necessary_label)
                    necessary_count += 1
    
    print(f"✅ Assigned labels to tasks:")
    print(f"   • Value-Added: {value_added_count}")
    print(f"   • Necessary NVA: {necessary_count}")
    print(f"   • Waste/Eliminate: {waste_count}")
    print(f"\n✅ Complete! Lean Six Sigma analysis should now display properly.")

if __name__ == '__main__':
    main()
