"""
Quick fix script to create performance profiles for existing demo data
Run this if you already have demo data but AI Resource Optimization shows "No performance data yet"
"""
import os
import django

# Setup Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'kanban_board.settings')
django.setup()

from django.contrib.auth.models import User
from accounts.models import Organization
from kanban.models import Board
from kanban.resource_leveling_models import UserPerformanceProfile


def create_demo_performance_profiles():
    """Create and update performance profiles for demo board members"""
    print('🔧 Creating Resource Optimization performance profiles for demo data...\n')
    
    # Get demo organizations
    demo_org_names = ['Dev Team', 'Marketing Team']
    demo_orgs = Organization.objects.filter(name__in=demo_org_names)
    
    if not demo_orgs.exists():
        print('❌ No demo organizations found. Have you run populate_test_data?')
        return
    
    # Get demo boards
    demo_board_names = ['Software Project', 'Bug Tracking', 'Marketing Campaign']
    demo_boards = Board.objects.filter(
        organization__in=demo_orgs,
        name__in=demo_board_names
    )
    
    if not demo_boards.exists():
        print('❌ No demo boards found. Have you run populate_test_data?')
        return
    
    print(f'Found {demo_boards.count()} demo boards:')
    for board in demo_boards:
        print(f'  - {board.name} ({board.organization.name})')
    
    total_profiles = 0
    
    # Process each board
    for board in demo_boards:
        print(f'\n📊 Processing: {board.name}')
        
        members = board.members.all()
        if not members.exists():
            print(f'  ⚠️  No members found')
            continue
        
        print(f'  Found {members.count()} members')
        
        # Create/update profile for each member
        for member in members:
            try:
                profile, created = UserPerformanceProfile.objects.get_or_create(
                    user=member,
                    organization=board.organization,
                    defaults={
                        'weekly_capacity_hours': 40.0,
                        'velocity_score': 1.0,
                        'quality_score': 3.0
                    }
                )
                
                # Update metrics from completed tasks
                profile.update_metrics()
                profile.update_current_workload()
                
                action = '✓ Created' if created else '✓ Updated'
                print(f'    {action} profile for {member.username}:')
                print(f'      - Completed tasks: {profile.total_tasks_completed}')
                print(f'      - Velocity: {profile.velocity_score:.2f} tasks/week')
                print(f'      - Active tasks: {profile.current_active_tasks}')
                print(f'      - Utilization: {profile.utilization_percentage:.1f}%')
                
                total_profiles += 1
                
            except Exception as e:
                print(f'    ❌ Error processing {member.username}: {str(e)}')
    
    print(f'\n✅ Successfully processed {total_profiles} performance profiles!')
    print('\n📌 Next steps:')
    print('  1. Refresh your browser page')
    print('  2. Navigate to any demo board')
    print('  3. The AI Resource Optimization widget should now show team performance data')
    print('\n💡 If you still see "No performance data yet", make sure:')
    print('  - Demo boards have completed tasks (check Done/Closed columns)')
    print('  - Tasks have progress=100 and completed_at timestamp set')


if __name__ == '__main__':
    create_demo_performance_profiles()
