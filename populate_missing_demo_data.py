"""
Populate missing demo data fields for all demo board tasks
- Creates stakeholders for each demo board
- Links stakeholder involvements to tasks
- Adds suggested team members to tasks requiring collaboration
"""
import os
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'kanban_board.settings')
import django
django.setup()

from kanban.models import Task, Board, Column
from kanban.stakeholder_models import ProjectStakeholder, StakeholderTaskInvolvement
from django.contrib.auth.models import User
from django.db.models import Q
from django.utils import timezone
import random

print("=" * 80)
print("POPULATING MISSING DEMO DATA")
print("=" * 80)

# Get demo boards
demo_org_name = 'Demo - Acme Corporation'
solo_boards = Board.objects.filter(
    Q(organization__name=demo_org_name)
).distinct().exclude(name='Website Redesign Project')

# Get demo users
demo_users = {
    'alex': User.objects.filter(username='alex_chen_demo').first(),
    'sam': User.objects.filter(username='sam_rivera_demo').first(),
    'jordan': User.objects.filter(username='jordan_taylor_demo').first(),
    'admin': User.objects.filter(username='demo_admin_solo').first(),
}

# Check if users exist
for name, user in demo_users.items():
    if user:
        print(f"Found demo user: {name} -> {user.username}")
    else:
        print(f"WARNING: Demo user '{name}' not found!")

created_by_user = demo_users['alex'] or demo_users['admin']
if not created_by_user:
    created_by_user = User.objects.filter(is_superuser=True).first()

print(f"\nUsing '{created_by_user.username}' as creator for stakeholders")

# ============================================================================
# STEP 1: Create Stakeholders for each board
# ============================================================================
print("\n" + "=" * 80)
print("STEP 1: Creating Stakeholders for Demo Boards")
print("=" * 80)

# Stakeholder templates by board type
stakeholder_templates = {
    'Software Development': [
        {
            'name': 'Michael Chen',
            'role': 'Product Owner',
            'organization': 'Product Team',
            'email': 'michael.chen@acme-demo.com',
            'phone': '+1-555-0101',
            'influence_level': 'high',
            'interest_level': 'high',
            'current_engagement': 'collaborate',
            'desired_engagement': 'empower',
            'notes': 'Primary product owner, responsible for feature prioritization and acceptance criteria.'
        },
        {
            'name': 'Sarah Williams',
            'role': 'Engineering Manager',
            'organization': 'Engineering',
            'email': 'sarah.williams@acme-demo.com',
            'phone': '+1-555-0102',
            'influence_level': 'high',
            'interest_level': 'high',
            'current_engagement': 'collaborate',
            'desired_engagement': 'collaborate',
            'notes': 'Manages development team resources and technical decisions.'
        },
        {
            'name': 'David Kim',
            'role': 'QA Lead',
            'organization': 'Quality Assurance',
            'email': 'david.kim@acme-demo.com',
            'phone': '+1-555-0103',
            'influence_level': 'medium',
            'interest_level': 'high',
            'current_engagement': 'involve',
            'desired_engagement': 'collaborate',
            'notes': 'Responsible for testing strategy and quality gates.'
        },
        {
            'name': 'Emily Rodriguez',
            'role': 'UX Designer',
            'organization': 'Design Team',
            'email': 'emily.rodriguez@acme-demo.com',
            'phone': '+1-555-0104',
            'influence_level': 'medium',
            'interest_level': 'high',
            'current_engagement': 'involve',
            'desired_engagement': 'collaborate',
            'notes': 'Creates user interface designs and conducts usability testing.'
        },
        {
            'name': 'James Thompson',
            'role': 'DevOps Engineer',
            'organization': 'Infrastructure',
            'email': 'james.thompson@acme-demo.com',
            'phone': '+1-555-0105',
            'influence_level': 'medium',
            'interest_level': 'medium',
            'current_engagement': 'consult',
            'desired_engagement': 'involve',
            'notes': 'Handles deployment pipelines and infrastructure concerns.'
        },
        {
            'name': 'Lisa Park',
            'role': 'Security Analyst',
            'organization': 'Security',
            'email': 'lisa.park@acme-demo.com',
            'phone': '+1-555-0106',
            'influence_level': 'high',
            'interest_level': 'medium',
            'current_engagement': 'consult',
            'desired_engagement': 'involve',
            'notes': 'Reviews security implications of new features and code changes.'
        },
    ],
    'Marketing Campaign': [
        {
            'name': 'Jennifer Adams',
            'role': 'Marketing Director',
            'organization': 'Marketing',
            'email': 'jennifer.adams@acme-demo.com',
            'phone': '+1-555-0201',
            'influence_level': 'high',
            'interest_level': 'high',
            'current_engagement': 'empower',
            'desired_engagement': 'empower',
            'notes': 'Oversees all marketing initiatives and budget allocation.'
        },
        {
            'name': 'Robert Chen',
            'role': 'Brand Manager',
            'organization': 'Marketing',
            'email': 'robert.chen@acme-demo.com',
            'phone': '+1-555-0202',
            'influence_level': 'medium',
            'interest_level': 'high',
            'current_engagement': 'collaborate',
            'desired_engagement': 'collaborate',
            'notes': 'Ensures brand consistency across all campaigns.'
        },
        {
            'name': 'Amanda Foster',
            'role': 'Content Strategist',
            'organization': 'Marketing',
            'email': 'amanda.foster@acme-demo.com',
            'phone': '+1-555-0203',
            'influence_level': 'medium',
            'interest_level': 'high',
            'current_engagement': 'involve',
            'desired_engagement': 'collaborate',
            'notes': 'Develops content strategy and editorial calendar.'
        },
        {
            'name': 'Chris Martinez',
            'role': 'Digital Marketing Specialist',
            'organization': 'Marketing',
            'email': 'chris.martinez@acme-demo.com',
            'phone': '+1-555-0204',
            'influence_level': 'low',
            'interest_level': 'high',
            'current_engagement': 'involve',
            'desired_engagement': 'involve',
            'notes': 'Manages paid advertising and social media campaigns.'
        },
        {
            'name': 'Nancy Wilson',
            'role': 'Sales Director',
            'organization': 'Sales',
            'email': 'nancy.wilson@acme-demo.com',
            'phone': '+1-555-0205',
            'influence_level': 'high',
            'interest_level': 'medium',
            'current_engagement': 'consult',
            'desired_engagement': 'collaborate',
            'notes': 'Provides sales team feedback on marketing effectiveness.'
        },
        {
            'name': 'Kevin Brown',
            'role': 'Analytics Manager',
            'organization': 'Marketing',
            'email': 'kevin.brown@acme-demo.com',
            'phone': '+1-555-0206',
            'influence_level': 'medium',
            'interest_level': 'medium',
            'current_engagement': 'consult',
            'desired_engagement': 'involve',
            'notes': 'Tracks campaign performance and provides insights.'
        },
    ],
    'Bug Tracking': [
        {
            'name': 'Patricia Lee',
            'role': 'Support Manager',
            'organization': 'Customer Support',
            'email': 'patricia.lee@acme-demo.com',
            'phone': '+1-555-0301',
            'influence_level': 'medium',
            'interest_level': 'high',
            'current_engagement': 'collaborate',
            'desired_engagement': 'collaborate',
            'notes': 'Reports critical bugs from customer escalations.'
        },
        {
            'name': 'Daniel Wright',
            'role': 'Senior Developer',
            'organization': 'Engineering',
            'email': 'daniel.wright@acme-demo.com',
            'phone': '+1-555-0302',
            'influence_level': 'high',
            'interest_level': 'high',
            'current_engagement': 'empower',
            'desired_engagement': 'empower',
            'notes': 'Lead developer for bug fixes and code reviews.'
        },
        {
            'name': 'Rachel Garcia',
            'role': 'QA Engineer',
            'organization': 'Quality Assurance',
            'email': 'rachel.garcia@acme-demo.com',
            'phone': '+1-555-0303',
            'influence_level': 'medium',
            'interest_level': 'high',
            'current_engagement': 'involve',
            'desired_engagement': 'collaborate',
            'notes': 'Verifies bug fixes and performs regression testing.'
        },
        {
            'name': 'Thomas Anderson',
            'role': 'Customer Success Manager',
            'organization': 'Customer Success',
            'email': 'thomas.anderson@acme-demo.com',
            'phone': '+1-555-0304',
            'influence_level': 'medium',
            'interest_level': 'high',
            'current_engagement': 'consult',
            'desired_engagement': 'involve',
            'notes': 'Represents customer interests and communicates ETA updates.'
        },
        {
            'name': 'Michelle Davis',
            'role': 'Product Manager',
            'organization': 'Product',
            'email': 'michelle.davis@acme-demo.com',
            'phone': '+1-555-0305',
            'influence_level': 'high',
            'interest_level': 'medium',
            'current_engagement': 'consult',
            'desired_engagement': 'involve',
            'notes': 'Prioritizes bugs based on business impact.'
        },
        {
            'name': 'Steven Clark',
            'role': 'Operations Manager',
            'organization': 'Operations',
            'email': 'steven.clark@acme-demo.com',
            'phone': '+1-555-0306',
            'influence_level': 'medium',
            'interest_level': 'low',
            'current_engagement': 'inform',
            'desired_engagement': 'consult',
            'notes': 'Monitors system health and escalates production issues.'
        },
    ],
}

# Create stakeholders for each board
board_stakeholders = {}
for board in solo_boards:
    print(f"\nProcessing board: {board.name}")
    templates = stakeholder_templates.get(board.name, stakeholder_templates['Software Development'])
    board_stakeholders[board.id] = []
    
    for data in templates:
        stakeholder, created = ProjectStakeholder.objects.get_or_create(
            board=board,
            email=data['email'],
            defaults={
                'name': data['name'],
                'role': data['role'],
                'organization': data['organization'],
                'phone': data['phone'],
                'influence_level': data['influence_level'],
                'interest_level': data['interest_level'],
                'current_engagement': data['current_engagement'],
                'desired_engagement': data['desired_engagement'],
                'notes': data['notes'],
                'created_by': created_by_user,
            }
        )
        board_stakeholders[board.id].append(stakeholder)
        if created:
            print(f"  ✓ Created: {stakeholder.name} ({stakeholder.role})")
        else:
            print(f"  - Exists: {stakeholder.name} ({stakeholder.role})")

# ============================================================================
# STEP 2: Create Stakeholder Involvements for Tasks
# ============================================================================
print("\n" + "=" * 80)
print("STEP 2: Creating Stakeholder Involvements for Tasks")
print("=" * 80)

# Involvement type mapping based on task characteristics
involvement_type_mapping = {
    'high': ['owner', 'approver', 'contributor'],
    'medium': ['contributor', 'reviewer', 'observer'],
    'low': ['observer', 'beneficiary', 'impacted'],
    'urgent': ['owner', 'approver'],
}

engagement_status_options = ['informed', 'consulted', 'involved', 'collaborated', 'satisfied']

involvement_count = 0
for board in solo_boards:
    print(f"\nProcessing tasks for: {board.name}")
    tasks = Task.objects.filter(column__board=board)
    stakeholders = board_stakeholders.get(board.id, [])
    
    if not stakeholders:
        print(f"  WARNING: No stakeholders for this board!")
        continue
    
    for task in tasks:
        # Skip if task already has stakeholder involvements
        existing_count = StakeholderTaskInvolvement.objects.filter(task=task).count()
        if existing_count > 0:
            continue
        
        # Determine how many stakeholders to involve (2-4)
        num_stakeholders = random.randint(2, min(4, len(stakeholders)))
        selected_stakeholders = random.sample(stakeholders, num_stakeholders)
        
        for stakeholder in selected_stakeholders:
            # Determine involvement type based on priority and stakeholder role
            priority = task.priority or 'medium'
            involvement_types = involvement_type_mapping.get(priority, ['contributor', 'observer'])
            involvement_type = random.choice(involvement_types)
            
            # Higher engagement status for more involved stakeholders
            if involvement_type in ['owner', 'approver']:
                engagement_status = random.choice(['collaborated', 'satisfied'])
            elif involvement_type in ['contributor', 'reviewer']:
                engagement_status = random.choice(['involved', 'consulted'])
            else:
                engagement_status = random.choice(['informed', 'consulted'])
            
            involvement, created = StakeholderTaskInvolvement.objects.get_or_create(
                stakeholder=stakeholder,
                task=task,
                defaults={
                    'involvement_type': involvement_type,
                    'engagement_status': engagement_status,
                    'engagement_count': random.randint(1, 5),
                    'last_engagement': timezone.now() - timezone.timedelta(days=random.randint(0, 14)),
                    'satisfaction_rating': random.choice([3, 4, 4, 5, 5]) if engagement_status in ['involved', 'collaborated', 'satisfied'] else None,
                    'feedback': '',
                    'concerns': '',
                }
            )
            if created:
                involvement_count += 1
    
    print(f"  Created involvements for {tasks.count()} tasks")

print(f"\nTotal stakeholder involvements created: {involvement_count}")

# ============================================================================
# STEP 3: Add Suggested Team Members to Tasks
# ============================================================================
print("\n" + "=" * 80)
print("STEP 3: Adding Suggested Team Members to Tasks")
print("=" * 80)

# Get all demo users for suggestions
all_demo_users = [u for u in demo_users.values() if u is not None]

# Team member suggestion templates
team_suggestions_templates = [
    {
        'username': 'alex_chen_demo',
        'reason': 'Strong experience with similar tasks and excellent communication skills',
        'match_score': 92
    },
    {
        'username': 'sam_rivera_demo',
        'reason': 'Technical expertise aligns well with task requirements',
        'match_score': 88
    },
    {
        'username': 'jordan_taylor_demo',
        'reason': 'Proven track record with related deliverables',
        'match_score': 85
    },
    {
        'username': 'demo_admin_solo',
        'reason': 'Project oversight capabilities and domain knowledge',
        'match_score': 78
    },
]

suggestion_count = 0
for board in solo_boards:
    print(f"\nProcessing tasks for: {board.name}")
    tasks = Task.objects.filter(column__board=board)
    
    for task in tasks:
        # Skip if already has suggested team members
        if task.suggested_team_members:
            continue
        
        # Add suggested team members for collaborative tasks or complex tasks
        if task.collaboration_required or task.complexity_score >= 6:
            # Select 2-3 team member suggestions (excluding current assignee)
            current_assignee_username = task.assigned_to.username if task.assigned_to else None
            available_suggestions = [
                s for s in team_suggestions_templates 
                if s['username'] != current_assignee_username
            ]
            
            num_suggestions = random.randint(2, min(3, len(available_suggestions)))
            selected_suggestions = random.sample(available_suggestions, num_suggestions)
            
            # Adjust match scores based on task characteristics
            suggestions = []
            for suggestion in selected_suggestions:
                adjusted_score = suggestion['match_score'] + random.randint(-5, 5)
                adjusted_score = max(60, min(98, adjusted_score))  # Keep between 60-98
                
                suggestions.append({
                    'username': suggestion['username'],
                    'reason': suggestion['reason'],
                    'match_score': adjusted_score
                })
            
            # Sort by match score descending
            suggestions.sort(key=lambda x: x['match_score'], reverse=True)
            
            task.suggested_team_members = suggestions
            task.collaboration_required = True  # Mark as requiring collaboration
            task.save(update_fields=['suggested_team_members', 'collaboration_required'])
            suggestion_count += 1
        else:
            # For simpler tasks, add 1-2 suggestions
            current_assignee_username = task.assigned_to.username if task.assigned_to else None
            available_suggestions = [
                s for s in team_suggestions_templates 
                if s['username'] != current_assignee_username
            ]
            
            if available_suggestions:
                num_suggestions = random.randint(1, 2)
                selected_suggestions = random.sample(available_suggestions, min(num_suggestions, len(available_suggestions)))
                
                suggestions = []
                for suggestion in selected_suggestions:
                    adjusted_score = suggestion['match_score'] - 10 + random.randint(-5, 5)
                    adjusted_score = max(50, min(90, adjusted_score))
                    
                    suggestions.append({
                        'username': suggestion['username'],
                        'reason': suggestion['reason'],
                        'match_score': adjusted_score
                    })
                
                suggestions.sort(key=lambda x: x['match_score'], reverse=True)
                
                task.suggested_team_members = suggestions
                task.save(update_fields=['suggested_team_members'])
                suggestion_count += 1
    
    print(f"  Updated suggested team members for {tasks.count()} tasks")

print(f"\nTotal tasks with suggested team members: {suggestion_count}")

# ============================================================================
# VERIFICATION
# ============================================================================
print("\n" + "=" * 80)
print("VERIFICATION")
print("=" * 80)

for board in solo_boards:
    print(f"\nBoard: {board.name}")
    stakeholder_count = ProjectStakeholder.objects.filter(board=board).count()
    tasks = Task.objects.filter(column__board=board)
    tasks_with_stakeholders = 0
    tasks_with_suggestions = 0
    
    for task in tasks:
        if StakeholderTaskInvolvement.objects.filter(task=task).exists():
            tasks_with_stakeholders += 1
        if task.suggested_team_members:
            tasks_with_suggestions += 1
    
    print(f"  Stakeholders: {stakeholder_count}")
    print(f"  Tasks with stakeholder involvement: {tasks_with_stakeholders}/{tasks.count()}")
    print(f"  Tasks with suggested team members: {tasks_with_suggestions}/{tasks.count()}")

print("\n" + "=" * 80)
print("DEMO DATA POPULATION COMPLETE!")
print("=" * 80)
