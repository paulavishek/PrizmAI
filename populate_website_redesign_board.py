#!/usr/bin/env python
"""
Populate Website Redesign Board
================================
Standalone script to populate the "Website Redesign" board with test data.
Creates 30 tasks across 3 phases for Gantt chart testing.

Usage:
    python populate_website_redesign_board.py

⚠️ DELETE THIS FILE AFTER TESTING
"""
import os
import django
import sys
from datetime import timedelta
import random

# Setup Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'kanban_board.settings')
django.setup()

from django.utils import timezone
from django.contrib.auth import get_user_model
from kanban.models import Board, Column, Task, Organization

User = get_user_model()

# Website Redesign task data
WEBSITE_REDESIGN_TASKS = {
    'Phase 1': [
        {'title': 'Conduct user research and interviews', 'desc': 'Interview 20+ current users to understand pain points and needs', 'priority': 'high', 'complexity': 7},
        {'title': 'Analyze competitor websites', 'desc': 'Research top 10 competitor sites for design patterns and UX', 'priority': 'medium', 'complexity': 5},
        {'title': 'Create user personas', 'desc': 'Develop 4-5 detailed user personas based on research', 'priority': 'high', 'complexity': 6},
        {'title': 'Define information architecture', 'desc': 'Map out site structure, navigation, and content hierarchy', 'priority': 'high', 'complexity': 7},
        {'title': 'Develop brand guidelines', 'desc': 'Update brand colors, typography, and visual identity', 'priority': 'medium', 'complexity': 6},
        {'title': 'Create wireframes', 'desc': 'Low-fidelity wireframes for all key pages', 'priority': 'high', 'complexity': 8},
        {'title': 'Setup design system', 'desc': 'Create component library in Figma with reusable elements', 'priority': 'medium', 'complexity': 7},
        {'title': 'Plan content strategy', 'desc': 'Define content types, tone, and migration plan', 'priority': 'medium', 'complexity': 5},
        {'title': 'Stakeholder presentation', 'desc': 'Present research findings and design direction', 'priority': 'medium', 'complexity': 4},
        {'title': 'Finalize project scope', 'desc': 'Lock down requirements, timeline, and deliverables', 'priority': 'high', 'complexity': 5},
    ],
    'Phase 2': [
        {'title': 'Design homepage mockup', 'desc': 'High-fidelity design with all sections and hero', 'priority': 'urgent', 'complexity': 8},
        {'title': 'Design product pages', 'desc': 'Product detail and listing page designs', 'priority': 'high', 'complexity': 7},
        {'title': 'Design about/team pages', 'desc': 'Company story, team profiles, and values', 'priority': 'medium', 'complexity': 5},
        {'title': 'Design contact forms', 'desc': 'Contact, quote request, and support forms', 'priority': 'medium', 'complexity': 4},
        {'title': 'Create responsive designs', 'desc': 'Mobile and tablet layouts for all pages', 'priority': 'high', 'complexity': 7},
        {'title': 'Design blog layout', 'desc': 'Blog listing, detail, and category pages', 'priority': 'low', 'complexity': 5},
        {'title': 'Prototype interactions', 'desc': 'Interactive prototype with animations and transitions', 'priority': 'medium', 'complexity': 6},
        {'title': 'Accessibility review', 'desc': 'Ensure WCAG 2.1 AA compliance in designs', 'priority': 'high', 'complexity': 6},
        {'title': 'User testing round 1', 'desc': 'Test prototypes with 10 users and gather feedback', 'priority': 'high', 'complexity': 7},
        {'title': 'Revise designs based on feedback', 'desc': 'Iterate on designs using user testing insights', 'priority': 'medium', 'complexity': 5},
    ],
    'Phase 3': [
        {'title': 'Frontend development setup', 'desc': 'Configure build tools, React, and Tailwind CSS', 'priority': 'high', 'complexity': 6},
        {'title': 'Implement homepage', 'desc': 'Build responsive homepage with all components', 'priority': 'urgent', 'complexity': 8},
        {'title': 'Build navigation system', 'desc': 'Header, footer, and mobile menu implementation', 'priority': 'high', 'complexity': 6},
        {'title': 'Develop product pages', 'desc': 'Product listing and detail pages with filtering', 'priority': 'high', 'complexity': 7},
        {'title': 'Implement forms', 'desc': 'Contact and quote forms with validation', 'priority': 'medium', 'complexity': 5},
        {'title': 'Build blog system', 'desc': 'Blog pages with CMS integration', 'priority': 'low', 'complexity': 6},
        {'title': 'Optimize images and assets', 'desc': 'Image compression, lazy loading, and CDN setup', 'priority': 'medium', 'complexity': 5},
        {'title': 'SEO optimization', 'desc': 'Meta tags, structured data, and sitemap', 'priority': 'high', 'complexity': 6},
        {'title': 'Cross-browser testing', 'desc': 'Test on Chrome, Firefox, Safari, and Edge', 'priority': 'high', 'complexity': 5},
        {'title': 'Launch website', 'desc': 'Deploy to production and DNS cutover', 'priority': 'urgent', 'complexity': 7},
    ]
}


def populate_board():
    """Main function to populate the Website Redesign board"""
    print("=" * 70)
    print("POPULATING WEBSITE REDESIGN BOARD")
    print("=" * 70)
    
    # Get the Website Redesign board
    try:
        # Try with is_official_demo_board first, then without
        try:
            board = Board.objects.get(name='Website Redesign', is_official_demo_board=True)
        except Board.DoesNotExist:
            # Try without the flag
            board = Board.objects.get(name='Website Redesign')
            # Mark it as an official demo board
            board.is_official_demo_board = True
            board.save()
            print(f"ℹ️  Marked board as official demo board")
        print(f"✅ Found board: {board.name}")
    except Board.DoesNotExist:
        print("❌ Website Redesign board not found!")
        print("   Please create the board first through the UI")
        sys.exit(1)
    
    # Get demo organization and users
    try:
        demo_org = Organization.objects.get(name='Demo - Acme Corporation')
        alex = User.objects.get(username='alex_chen_demo')
        sam = User.objects.get(username='sam_rivera_demo')
        jordan = User.objects.get(username='jordan_taylor_demo')
        print(f"✅ Found demo organization and users")
    except (Organization.DoesNotExist, User.DoesNotExist) as e:
        print(f"❌ Error finding demo data: {e}")
        sys.exit(1)
    
    # Get board columns
    columns = {col.name: col for col in Column.objects.filter(board=board).order_by('position')}
    if not columns:
        print("❌ No columns found for board!")
        sys.exit(1)
    
    print(f"✅ Found {len(columns)} columns: {', '.join(columns.keys())}")
    
    # Map column names to common ones
    backlog_col = columns.get('Backlog') or columns.get('To Do') or list(columns.values())[0]
    in_progress_col = columns.get('In Progress') or list(columns.values())[min(1, len(columns)-1)]
    review_col = columns.get('Code Review') or columns.get('Testing/QA') or in_progress_col
    done_col = columns.get('Done') or columns.get('Ready for Deployment') or list(columns.values())[-1]
    
    # Demo users for assignment (only the 3 visible demo personas)
    users = [alex, sam, jordan]
    now = timezone.now().date()
    
    # Delete existing tasks if any
    existing_tasks = Task.objects.filter(column__board=board)
    if existing_tasks.exists():
        count = existing_tasks.count()
        existing_tasks.delete()
        print(f"🗑️  Deleted {count} existing tasks")
    
    print("\n📝 Creating tasks...")
    
    all_tasks = []
    task_count = 0
    
    # Phase 1: Research & Planning (days -60 to -31)
    # Tasks mostly completed (in Done column)
    print("\n  Phase 1: Research & Planning (Completed)")
    prev_due_date = now + timedelta(days=-60)
    
    for i, task_data in enumerate(WEBSITE_REDESIGN_TASKS['Phase 1']):
        # Sequential task dates with no overlap
        start = prev_due_date + timedelta(days=random.randint(1, 2))
        due = start + timedelta(days=random.randint(2, 4))
        
        # Phase 1 tasks are 100% complete (in Done column)
        task = Task.objects.create(
            column=done_col,
            title=task_data['title'],
            description=task_data['desc'],
            priority=task_data['priority'],
            complexity_score=task_data['complexity'],
            assigned_to=random.choice(users),
            created_by=alex,
            progress=100,
            start_date=start,
            due_date=due,
            phase='Phase 1',
            is_seed_demo_data=True,
        )
        all_tasks.append(task)
        task_count += 1
        prev_due_date = due
        print(f"    ✓ {task.title}")
    
    # Phase 2: Design (days -30 to -1)
    # Mix of In Progress and Review
    print("\n  Phase 2: Design (In Progress)")
    prev_due_date = now + timedelta(days=-30)
    
    for i, task_data in enumerate(WEBSITE_REDESIGN_TASKS['Phase 2']):
        start = prev_due_date + timedelta(days=random.randint(1, 2))
        due = start + timedelta(days=random.randint(2, 4))
        
        # Mix of progress states
        if i < 4:
            # First 4 tasks are done
            column = done_col
            progress = 100
        elif i < 7:
            # Next 3 in review
            column = review_col
            progress = random.randint(70, 90)
        else:
            # Last 3 in progress
            column = in_progress_col
            progress = random.randint(30, 60)
        
        task = Task.objects.create(
            column=column,
            title=task_data['title'],
            description=task_data['desc'],
            priority=task_data['priority'],
            complexity_score=task_data['complexity'],
            assigned_to=random.choice(users),
            created_by=alex,
            progress=progress,
            start_date=start,
            due_date=due,
            phase='Phase 2',
            is_seed_demo_data=True,
        )
        all_tasks.append(task)
        task_count += 1
        prev_due_date = due
        print(f"    ✓ {task.title} ({progress}%)")
    
    # Phase 3: Development & Launch (days 0 to +45)
    # All in Backlog (not started yet)
    print("\n  Phase 3: Development & Launch (Upcoming)")
    prev_due_date = now
    
    for i, task_data in enumerate(WEBSITE_REDESIGN_TASKS['Phase 3']):
        start = prev_due_date + timedelta(days=random.randint(1, 3))
        due = start + timedelta(days=random.randint(3, 5))
        
        task = Task.objects.create(
            column=backlog_col,
            title=task_data['title'],
            description=task_data['desc'],
            priority=task_data['priority'],
            complexity_score=task_data['complexity'],
            assigned_to=random.choice(users),
            created_by=alex,
            progress=0,
            start_date=start,
            due_date=due,
            phase='Phase 3',
            is_seed_demo_data=True,
        )
        all_tasks.append(task)
        task_count += 1
        prev_due_date = due
        print(f"    ✓ {task.title}")
    
    # Create some dependencies between tasks for Gantt chart
    print("\n🔗 Creating task dependencies...")
    # Phase 1 dependencies
    all_tasks[5].dependencies.add(all_tasks[3])  # Wireframes depend on IA
    all_tasks[6].dependencies.add(all_tasks[4])  # Design system depends on brand guidelines
    
    # Phase 2 dependencies
    all_tasks[10].dependencies.add(all_tasks[6])  # Homepage design depends on design system
    all_tasks[11].dependencies.add(all_tasks[6])  # Product pages depend on design system
    all_tasks[16].dependencies.add(all_tasks[10])  # Prototype depends on homepage
    all_tasks[18].dependencies.add(all_tasks[16])  # User testing depends on prototype
    
    # Phase 3 dependencies
    all_tasks[21].dependencies.add(all_tasks[10])  # Homepage implementation depends on homepage design
    all_tasks[22].dependencies.add(all_tasks[21])  # Navigation depends on homepage
    all_tasks[23].dependencies.add(all_tasks[11])  # Product pages depend on product design
    all_tasks[29].dependencies.add(all_tasks[21], all_tasks[23])  # Launch depends on key pages
    
    print(f"    ✓ Created dependencies")
    
    # Summary
    print("\n" + "=" * 70)
    print("✅ BOARD POPULATION COMPLETE")
    print("=" * 70)
    print(f"\n📊 Summary:")
    print(f"   • Board: {board.name}")
    print(f"   • Tasks created: {task_count}")
    print(f"   • Phase 1 (Completed): 10 tasks")
    print(f"   • Phase 2 (In Progress): 10 tasks")
    print(f"   • Phase 3 (Upcoming): 10 tasks")
    print(f"   • Dependencies: Multiple")
    print(f"\n🎯 You can now test the Gantt chart with this board!")
    print(f"\n⚠️  REMEMBER: Delete this script after testing")
    print(f"   Command: del populate_website_redesign_board.py")
    print()


if __name__ == '__main__':
    try:
        populate_board()
    except KeyboardInterrupt:
        print("\n\n❌ Interrupted by user")
        sys.exit(1)
    except Exception as e:
        print(f"\n\n❌ Error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
