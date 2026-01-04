"""
Populate comments and activity logs for demo board tasks
"""
import os
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'kanban_board.settings')
import django
django.setup()

from kanban.models import Task, Board, Column, Comment, TaskActivity
from django.contrib.auth.models import User
from django.db.models import Q
from django.utils import timezone
import random
from datetime import timedelta

print("=" * 80)
print("POPULATING COMMENTS AND ACTIVITY LOGS FOR DEMO TASKS")
print("=" * 80)

# Get demo boards
demo_org_name = 'Demo - Acme Corporation'
solo_boards = Board.objects.filter(
    Q(organization__name=demo_org_name)
).distinct().exclude(name='Website Redesign Project')

# Get demo users
demo_users = []
for username in ['alex_chen_demo', 'sam_rivera_demo', 'jordan_taylor_demo', 'demo_admin_solo']:
    user = User.objects.filter(username=username).first()
    if user:
        demo_users.append(user)
        print(f"Found demo user: {user.username}")

if not demo_users:
    print("ERROR: No demo users found!")
    exit(1)

# ============================================================================
# COMMENT TEMPLATES
# ============================================================================
software_comments = [
    # Progress updates
    "Made good progress today. The core functionality is working as expected.",
    "Ran into some edge cases that need more testing. Will handle in next iteration.",
    "Code review feedback incorporated. Ready for QA testing.",
    "Unit tests are passing. Moving to integration testing next.",
    "Performance looks good - response times under 200ms.",
    "Fixed the bug mentioned in the last standup. Please verify.",
    "Documentation updated to reflect the new API endpoints.",
    "Dependency updates complete. No breaking changes detected.",
    "Pushed initial implementation. Would appreciate feedback on the approach.",
    "Blocked by external API rate limits. Investigating workarounds.",
    
    # Technical discussions
    "Consider using a cache here to improve performance for repeated queries.",
    "Good point about error handling. I'll add more specific exception types.",
    "The database schema looks solid. One suggestion: add an index on the status field.",
    "Let's discuss the authentication flow in today's standup.",
    "I think we should refactor this module before adding more features.",
    
    # Questions
    "Quick question: should we support both JSON and XML responses?",
    "Does anyone have experience with this library? Looking for best practices.",
    "What's our target browser support for this feature?",
    "Should we add logging at the debug level or info level?",
    
    # Status updates
    "On track for Friday delivery. No blockers at the moment.",
    "Might need an extra day due to unexpected complexity in the integration.",
    "This is more complex than initially estimated. Updating timeline.",
    "Feature complete! Just need final review before merging.",
]

marketing_comments = [
    # Campaign updates
    "Campaign assets are ready for review. See attached mockups.",
    "A/B test results are in - version B has 23% higher CTR.",
    "Social media scheduling complete for next 2 weeks.",
    "Email open rates are above industry average at 28%.",
    "Landing page is live. Monitoring conversion rates closely.",
    "Influencer partnership confirmed. Content drops next Monday.",
    
    # Creative feedback
    "Love the new headline copy! Very compelling.",
    "The color scheme needs adjustment for brand consistency.",
    "Video script approved. Moving to production phase.",
    "Banner designs look great. Just need minor sizing adjustments.",
    
    # Analytics & metrics
    "Traffic increased 45% week-over-week. Campaign is working!",
    "Lead quality has improved significantly since the targeting update.",
    "Cost per acquisition is within budget. Optimizing for even better results.",
    "Customer feedback on the new messaging has been positive.",
    
    # Coordination
    "Synced with sales team - they're excited about the new collateral.",
    "Legal has approved the contest terms and conditions.",
    "Waiting on final approval from brand team.",
    "Content calendar is shared with all stakeholders.",
]

bug_comments = [
    # Investigation updates
    "Reproduced the issue. Root cause identified - null pointer exception.",
    "The bug occurs only under high load conditions (>1000 concurrent users).",
    "Found the problematic code path. Working on a fix.",
    "This is related to the recent deployment. Checking the diff now.",
    "Log analysis complete. The error originates in the authentication module.",
    
    # Fix progress
    "Fix deployed to staging. Please verify the issue is resolved.",
    "Patch is ready. Running regression tests before production deploy.",
    "Hotfix merged. Monitoring production for any recurrence.",
    "The issue is more complex than expected. Need to refactor the handler.",
    
    # Communication
    "Customer has been notified about the fix timeline.",
    "Support ticket updated with current status.",
    "This is a priority 1 issue - all hands on deck.",
    "Escalating to senior dev for architecture review.",
    
    # Verification
    "Tested on Chrome, Firefox, and Safari - all working now.",
    "Memory leak is fixed. Usage stable at 200MB after 24 hours.",
    "Performance restored to normal levels after the fix.",
    "Edge case handling improved. Added unit tests to prevent regression.",
]

# ============================================================================
# ACTIVITY LOG TEMPLATES
# ============================================================================
activity_templates = [
    {'type': 'created', 'desc': 'Created this task'},
    {'type': 'updated', 'desc': 'Updated task description'},
    {'type': 'updated', 'desc': 'Changed priority from medium to high'},
    {'type': 'updated', 'desc': 'Changed priority from low to medium'},
    {'type': 'updated', 'desc': 'Updated due date'},
    {'type': 'updated', 'desc': 'Updated start date'},
    {'type': 'assigned', 'desc': 'Assigned task to {assignee}'},
    {'type': 'moved', 'desc': 'Moved from To Do to In Progress'},
    {'type': 'moved', 'desc': 'Moved from In Progress to Done'},
    {'type': 'label_added', 'desc': 'Added label: Value-Added'},
    {'type': 'label_added', 'desc': 'Added label: Business Value-Added'},
    {'type': 'updated', 'desc': 'Updated progress to 50%'},
    {'type': 'updated', 'desc': 'Updated progress to 75%'},
    {'type': 'updated', 'desc': 'Updated complexity score'},
    {'type': 'commented', 'desc': 'Added a comment'},
]

# ============================================================================
# STEP 1: Add Comments to Tasks
# ============================================================================
print("\n" + "=" * 80)
print("STEP 1: Adding Comments to Demo Tasks")
print("=" * 80)

comment_count = 0
for board in solo_boards:
    print(f"\nProcessing board: {board.name}")
    tasks = Task.objects.filter(column__board=board)
    
    # Select appropriate comment pool
    if 'Software' in board.name:
        comment_pool = software_comments
    elif 'Marketing' in board.name:
        comment_pool = marketing_comments
    else:
        comment_pool = bug_comments
    
    for task in tasks:
        # Skip if task already has comments
        if Comment.objects.filter(task=task).exists():
            continue
        
        # Determine number of comments (1-4 for most tasks, more for complex/in-progress)
        if task.progress > 0 and task.progress < 100:
            num_comments = random.randint(2, 4)
        elif task.complexity_score >= 7:
            num_comments = random.randint(2, 5)
        else:
            num_comments = random.randint(1, 3)
        
        # Create comments
        base_time = timezone.now() - timedelta(days=random.randint(5, 20))
        for i in range(num_comments):
            comment_text = random.choice(comment_pool)
            comment_user = random.choice(demo_users)
            comment_time = base_time + timedelta(hours=random.randint(1, 48) * (i + 1))
            
            Comment.objects.create(
                task=task,
                user=comment_user,
                content=comment_text,
                created_at=comment_time
            )
            comment_count += 1
    
    print(f"  Added comments to {tasks.count()} tasks")

print(f"\nTotal comments created: {comment_count}")

# ============================================================================
# STEP 2: Add Activity Logs to Tasks
# ============================================================================
print("\n" + "=" * 80)
print("STEP 2: Adding Activity Logs to Demo Tasks")
print("=" * 80)

activity_count = 0
for board in solo_boards:
    print(f"\nProcessing board: {board.name}")
    tasks = Task.objects.filter(column__board=board)
    
    for task in tasks:
        # Skip if task already has significant activity
        existing_activities = TaskActivity.objects.filter(task=task).count()
        if existing_activities >= 3:
            continue
        
        # Determine number of activities based on task state
        if task.progress == 100:
            num_activities = random.randint(4, 7)
        elif task.progress > 50:
            num_activities = random.randint(3, 5)
        elif task.progress > 0:
            num_activities = random.randint(2, 4)
        else:
            num_activities = random.randint(1, 3)
        
        # Always start with "created"
        activities_to_add = [activity_templates[0]]  # 'created'
        
        # Add random activities
        remaining = random.sample(activity_templates[1:], min(num_activities - 1, len(activity_templates) - 1))
        activities_to_add.extend(remaining)
        
        # Create activities
        base_time = task.created_at if task.created_at else timezone.now() - timedelta(days=random.randint(10, 30))
        
        for i, activity in enumerate(activities_to_add):
            activity_user = random.choice(demo_users)
            activity_time = base_time + timedelta(hours=random.randint(1, 24) * (i + 1))
            
            description = activity['desc']
            if '{assignee}' in description and task.assigned_to:
                description = description.format(assignee=task.assigned_to.username)
            elif '{assignee}' in description:
                description = description.format(assignee=activity_user.username)
            
            # Check if this exact activity already exists
            if not TaskActivity.objects.filter(
                task=task,
                activity_type=activity['type'],
                description=description
            ).exists():
                TaskActivity.objects.create(
                    task=task,
                    user=activity_user,
                    activity_type=activity['type'],
                    description=description,
                    created_at=activity_time
                )
                activity_count += 1
    
    print(f"  Added activities to {tasks.count()} tasks")

print(f"\nTotal activities created: {activity_count}")

# ============================================================================
# VERIFICATION
# ============================================================================
print("\n" + "=" * 80)
print("VERIFICATION")
print("=" * 80)

for board in solo_boards:
    print(f"\nBoard: {board.name}")
    tasks = Task.objects.filter(column__board=board)
    
    tasks_with_comments = 0
    tasks_with_activities = 0
    total_comments = 0
    total_activities = 0
    
    for task in tasks:
        comment_count_task = Comment.objects.filter(task=task).count()
        activity_count_task = TaskActivity.objects.filter(task=task).count()
        
        if comment_count_task > 0:
            tasks_with_comments += 1
        if activity_count_task > 0:
            tasks_with_activities += 1
        
        total_comments += comment_count_task
        total_activities += activity_count_task
    
    print(f"  Tasks with comments: {tasks_with_comments}/{tasks.count()} ({total_comments} total)")
    print(f"  Tasks with activities: {tasks_with_activities}/{tasks.count()} ({total_activities} total)")

print("\n" + "=" * 80)
print("COMMENTS AND ACTIVITIES POPULATION COMPLETE!")
print("=" * 80)
