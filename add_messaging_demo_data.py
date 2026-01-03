"""
Add Messaging Demo Data for PrizmAI Demo Mode
==============================================
Creates chat rooms, messages, file attachments (metadata), and notifications
to showcase the messaging feature without requiring users to log in as multiple accounts.

This script creates realistic team conversations across all demo boards.
"""
import os
import django
import random
from datetime import timedelta

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'kanban_board.settings')
django.setup()

from django.contrib.auth.models import User
from django.utils import timezone
from kanban.models import Board, Task
from accounts.models import Organization
from messaging.models import ChatRoom, ChatMessage, Notification, FileAttachment, TaskThreadComment

print("=" * 80)
print("ADDING MESSAGING DEMO DATA")
print("=" * 80)

# Get demo organization
try:
    demo_org = Organization.objects.get(name='Demo - Acme Corporation')
    print(f"✅ Found organization: {demo_org.name}")
except Organization.DoesNotExist:
    print("❌ Demo - Acme Corporation not found!")
    print("   Please run: python manage.py create_demo_organization")
    exit(1)

# Get demo boards
demo_boards = Board.objects.filter(organization=demo_org)
print(f"✅ Found {demo_boards.count()} demo boards")

# Get demo users
demo_admin = User.objects.filter(username='demo_admin_solo').first()
alex = User.objects.filter(username='alex_chen_demo').first()
sam = User.objects.filter(username='sam_rivera_demo').first()
jordan = User.objects.filter(username='jordan_taylor_demo').first()

demo_users = [u for u in [demo_admin, alex, sam, jordan] if u]
print(f"✅ Found {len(demo_users)} demo users")

if not demo_admin:
    print("❌ demo_admin_solo user not found!")
    exit(1)

# ============================================================================
# CHAT ROOM CONFIGURATIONS BY BOARD
# ============================================================================

chat_room_configs = {
    'Software Development': [
        {
            'name': 'General Discussion',
            'description': 'Team updates, announcements, and general discussions',
            'messages': [
                {'author': 'alex', 'content': 'Good morning team! 🌅 Ready for our sprint planning today?', 'minutes_ago': 180},
                {'author': 'sam', 'content': 'Morning @alex_chen_demo! Yes, I finished reviewing the backlog items.', 'minutes_ago': 175},
                {'author': 'demo_admin', 'content': 'Great work everyone! The API integration is looking solid. 👏', 'minutes_ago': 120},
                {'author': 'sam', 'content': '@demo_admin_solo Thank you! I ran into a small issue with the OAuth flow, but resolved it.', 'minutes_ago': 115},
                {'author': 'alex', 'content': 'Quick update: Client meeting moved to 3 PM. @sam_rivera_demo can you prepare the demo?', 'minutes_ago': 60},
                {'author': 'sam', 'content': 'Absolutely! I\'ll have the staging environment ready by 2:30 PM.', 'minutes_ago': 55},
                {'author': 'demo_admin', 'content': 'Perfect. I\'ll update the presentation slides with our latest metrics.', 'minutes_ago': 45},
            ]
        },
        {
            'name': 'Technical Support',
            'description': 'Technical questions, debugging help, and code reviews',
            'messages': [
                {'author': 'sam', 'content': 'Has anyone encountered issues with the database migration on PostgreSQL 15?', 'minutes_ago': 240},
                {'author': 'demo_admin', 'content': '@sam_rivera_demo Yes! Try running `python manage.py migrate --fake-initial` first.', 'minutes_ago': 235},
                {'author': 'sam', 'content': 'That worked! Thanks @demo_admin_solo 🙏', 'minutes_ago': 230},
                {'author': 'alex', 'content': 'Good tip! I\'ll add this to our troubleshooting docs.', 'minutes_ago': 200},
                {'author': 'sam', 'content': 'Also, the WebSocket connection is dropping occasionally. Need to investigate.', 'minutes_ago': 90},
                {'author': 'demo_admin', 'content': 'Check the Nginx timeout settings. We had similar issues last month.', 'minutes_ago': 85},
            ]
        },
        {
            'name': 'Code Reviews',
            'description': 'Pull request discussions and code review feedback',
            'messages': [
                {'author': 'demo_admin', 'content': 'Just submitted PR #142 for the new authentication module. @sam_rivera_demo could you review?', 'minutes_ago': 300},
                {'author': 'sam', 'content': 'On it! Give me about 30 minutes. 🔍', 'minutes_ago': 295},
                {'author': 'sam', 'content': 'Reviewed! LGTM with minor suggestions. Left a few comments on the token refresh logic.', 'minutes_ago': 260},
                {'author': 'demo_admin', 'content': 'Great feedback! I\'ll address those comments and update the PR.', 'minutes_ago': 255},
                {'author': 'alex', 'content': 'Nice work both of you! This will be a great addition to our security features.', 'minutes_ago': 200},
            ]
        },
    ],
    'Marketing Campaign': [
        {
            'name': 'Campaign Planning',
            'description': 'Strategy discussions and campaign planning',
            'messages': [
                {'author': 'jordan', 'content': 'Team, I\'ve drafted the Q1 marketing strategy. Check the shared doc! 📊', 'minutes_ago': 360},
                {'author': 'alex', 'content': '@jordan_taylor_demo Looks comprehensive! Love the social media approach.', 'minutes_ago': 350},
                {'author': 'demo_admin', 'content': 'Great work Jordan! Can we discuss the budget allocation in our next meeting?', 'minutes_ago': 300},
                {'author': 'jordan', 'content': 'Absolutely @demo_admin_solo! I\'ve prepared a detailed breakdown.', 'minutes_ago': 295},
                {'author': 'alex', 'content': 'Should we also consider influencer partnerships? I have some contacts.', 'minutes_ago': 150},
                {'author': 'jordan', 'content': 'That\'s a great idea @alex_chen_demo! Let\'s schedule a brainstorming session.', 'minutes_ago': 145},
            ]
        },
        {
            'name': 'Content Creation',
            'description': 'Blog posts, social media content, and creative assets',
            'messages': [
                {'author': 'jordan', 'content': 'I\'ve uploaded the new brand guidelines to the wiki. Please review! 🎨', 'minutes_ago': 480},
                {'author': 'alex', 'content': 'Fantastic work! The color palette changes look professional.', 'minutes_ago': 470},
                {'author': 'demo_admin', 'content': 'Love the new logo variations. These will work great for the mobile app.', 'minutes_ago': 420},
                {'author': 'jordan', 'content': 'Thanks team! I\'m also working on the product launch video storyboard.', 'minutes_ago': 200},
                {'author': 'alex', 'content': '@jordan_taylor_demo Can\'t wait to see it! When do you think it\'ll be ready?', 'minutes_ago': 195},
                {'author': 'jordan', 'content': 'Aiming for end of this week. I\'ll share a preview soon!', 'minutes_ago': 190},
            ]
        },
        {
            'name': 'Analytics & Reports',
            'description': 'Performance metrics and campaign analytics',
            'messages': [
                {'author': 'demo_admin', 'content': 'November campaign results are in! 📈 CTR increased by 23%!', 'minutes_ago': 600},
                {'author': 'jordan', 'content': 'Wow! That\'s amazing @demo_admin_solo! What was the main driver?', 'minutes_ago': 590},
                {'author': 'demo_admin', 'content': 'The A/B test on email subject lines. Version B performed significantly better.', 'minutes_ago': 580},
                {'author': 'alex', 'content': 'Great insights! Let\'s apply these learnings to the December campaigns.', 'minutes_ago': 500},
            ]
        },
    ],
    'Bug Tracking': [
        {
            'name': 'Critical Issues',
            'description': 'Urgent bugs and production issues',
            'messages': [
                {'author': 'sam', 'content': '🚨 ALERT: Production API throwing 500 errors on user login endpoint!', 'minutes_ago': 45},
                {'author': 'demo_admin', 'content': 'On it! Checking the logs now. @sam_rivera_demo which region?', 'minutes_ago': 42},
                {'author': 'sam', 'content': 'EU-WEST-1. Started about 10 minutes ago according to CloudWatch.', 'minutes_ago': 40},
                {'author': 'jordan', 'content': 'Customer success team is getting tickets. ETA on fix?', 'minutes_ago': 35},
                {'author': 'demo_admin', 'content': 'Found it! Database connection pool exhausted. Deploying fix now.', 'minutes_ago': 30},
                {'author': 'sam', 'content': 'Fix deployed! Monitoring... ✅ Error rate dropping rapidly.', 'minutes_ago': 20},
                {'author': 'jordan', 'content': 'Perfect! I\'ll send an update to affected customers. Thanks team! 🙌', 'minutes_ago': 15},
            ]
        },
        {
            'name': 'Bug Triage',
            'description': 'Bug prioritization and assignment discussions',
            'messages': [
                {'author': 'jordan', 'content': 'Good morning! We have 15 new bugs from the weekend. Let\'s triage.', 'minutes_ago': 180},
                {'author': 'sam', 'content': 'I can take the frontend rendering issues. @jordan_taylor_demo assign me BUG-234 and BUG-236.', 'minutes_ago': 175},
                {'author': 'demo_admin', 'content': 'I\'ll handle the API bugs. The timeout issues look related to my recent changes.', 'minutes_ago': 170},
                {'author': 'jordan', 'content': 'Great! I\'ve updated the task board. Sprint goal: zero critical bugs by Friday. 🎯', 'minutes_ago': 160},
                {'author': 'sam', 'content': 'Challenge accepted! 💪', 'minutes_ago': 155},
            ]
        },
        {
            'name': 'QA Testing',
            'description': 'Testing discussions and QA feedback',
            'messages': [
                {'author': 'jordan', 'content': 'Starting regression testing for v2.5 release. Test plan in the wiki.', 'minutes_ago': 400},
                {'author': 'sam', 'content': '@jordan_taylor_demo Found an edge case in the payment flow. Creating a bug ticket.', 'minutes_ago': 350},
                {'author': 'jordan', 'content': 'Thanks Sam! Please mark it as P1 if it affects checkout.', 'minutes_ago': 345},
                {'author': 'demo_admin', 'content': 'Good catch! I\'ll review the payment service logs.', 'minutes_ago': 300},
                {'author': 'sam', 'content': 'Update: It\'s a currency conversion edge case. Only affects JPY transactions.', 'minutes_ago': 280},
                {'author': 'demo_admin', 'content': 'Ah, the floating point precision issue. I know exactly where to fix this.', 'minutes_ago': 275},
            ]
        },
    ],
}

# ============================================================================
# FILE ATTACHMENT METADATA (No actual files, just metadata for demo)
# ============================================================================

file_attachment_data = {
    'Software Development': [
        {'room': 'General Discussion', 'filename': 'Sprint_15_Planning.pdf', 'file_type': 'pdf', 'file_size': 245760, 'description': 'Sprint 15 planning document with user stories and acceptance criteria'},
        {'room': 'Technical Support', 'filename': 'Database_Migration_Guide.pdf', 'file_type': 'pdf', 'file_size': 189440, 'description': 'Step-by-step guide for PostgreSQL 15 migration'},
        {'room': 'Code Reviews', 'filename': 'Auth_Module_Architecture.png', 'file_type': 'png', 'file_size': 524288, 'description': 'Architecture diagram for new authentication module'},
    ],
    'Marketing Campaign': [
        {'room': 'Campaign Planning', 'filename': 'Q1_Marketing_Strategy.pdf', 'file_type': 'pdf', 'file_size': 1048576, 'description': 'Comprehensive Q1 2026 marketing strategy document'},
        {'room': 'Content Creation', 'filename': 'Brand_Guidelines_v2.pdf', 'file_type': 'pdf', 'file_size': 2097152, 'description': 'Updated brand guidelines with new logo and color palette'},
        {'room': 'Content Creation', 'filename': 'Product_Launch_Storyboard.pptx', 'file_type': 'pptx', 'file_size': 3145728, 'description': 'Video storyboard for product launch campaign'},
        {'room': 'Analytics & Reports', 'filename': 'November_Campaign_Report.xlsx', 'file_type': 'xlsx', 'file_size': 512000, 'description': 'November 2025 campaign performance metrics'},
    ],
    'Bug Tracking': [
        {'room': 'Critical Issues', 'filename': 'Production_Error_Logs.pdf', 'file_type': 'pdf', 'file_size': 384000, 'description': 'CloudWatch logs from the login endpoint incident'},
        {'room': 'QA Testing', 'filename': 'v2.5_Test_Plan.xlsx', 'file_type': 'xlsx', 'file_size': 256000, 'description': 'Comprehensive regression test plan for v2.5 release'},
        {'room': 'QA Testing', 'filename': 'Bug_Screenshots.png', 'file_type': 'png', 'file_size': 1572864, 'description': 'Screenshots of payment flow edge case bug'},
    ],
}

# ============================================================================
# HELPER FUNCTIONS
# ============================================================================

def get_user_by_key(key):
    """Get user by short key name"""
    user_map = {
        'demo_admin': demo_admin,
        'alex': alex,
        'sam': sam,
        'jordan': jordan,
    }
    return user_map.get(key)

def get_board_members(board):
    """Get all members of a board"""
    return list(board.members.all())

# ============================================================================
# CREATE CHAT ROOMS AND MESSAGES
# ============================================================================

print("\n" + "=" * 80)
print("STEP 1: Creating Chat Rooms and Messages")
print("=" * 80)

rooms_created = 0
messages_created = 0
now = timezone.now()

for board in demo_boards:
    board_name = board.name
    if board_name not in chat_room_configs:
        print(f"⚠️  No chat room config for board: {board_name}")
        continue
    
    print(f"\n📋 Board: {board_name}")
    board_members = get_board_members(board)
    
    # Get the creator - use demo_admin if member, otherwise first member
    creator = demo_admin if demo_admin in board_members else board_members[0]
    
    for room_config in chat_room_configs[board_name]:
        room_name = room_config['name']
        
        # Create or get chat room
        room, created = ChatRoom.objects.get_or_create(
            board=board,
            name=room_name,
            defaults={
                'description': room_config['description'],
                'created_by': creator,
            }
        )
        
        if created:
            rooms_created += 1
            # Add all board members to the room
            for member in board_members:
                room.members.add(member)
            print(f"   ✅ Created room: {room_name}")
        else:
            # Ensure all board members are in the room
            for member in board_members:
                if member not in room.members.all():
                    room.members.add(member)
            print(f"   ⏭️  Room already exists: {room_name}")
        
        # Create messages if none exist
        existing_messages = ChatMessage.objects.filter(chat_room=room).count()
        if existing_messages == 0:
            for msg_data in room_config['messages']:
                author = get_user_by_key(msg_data['author'])
                if author and author in board_members:
                    # Calculate message time
                    msg_time = now - timedelta(minutes=msg_data['minutes_ago'])
                    
                    msg = ChatMessage.objects.create(
                        chat_room=room,
                        author=author,
                        content=msg_data['content'],
                    )
                    # Update created_at manually
                    ChatMessage.objects.filter(pk=msg.pk).update(created_at=msg_time)
                    messages_created += 1
                    
                    # Handle @mentions
                    for mentioned_username in msg.get_mentioned_usernames():
                        try:
                            mentioned_user = User.objects.get(username=mentioned_username)
                            msg.mentioned_users.add(mentioned_user)
                        except User.DoesNotExist:
                            pass
            
            print(f"      💬 Added {len(room_config['messages'])} messages")
        else:
            print(f"      ⏭️  Messages already exist ({existing_messages})")

print(f"\n✅ Created {rooms_created} chat rooms and {messages_created} messages")

# ============================================================================
# CREATE FILE ATTACHMENTS (Metadata only - no actual files)
# ============================================================================

print("\n" + "=" * 80)
print("STEP 2: Creating File Attachment Metadata")
print("=" * 80)

attachments_created = 0

for board in demo_boards:
    board_name = board.name
    if board_name not in file_attachment_data:
        continue
    
    print(f"\n📋 Board: {board_name}")
    board_members = get_board_members(board)
    
    for file_data in file_attachment_data[board_name]:
        room_name = file_data['room']
        
        try:
            room = ChatRoom.objects.get(board=board, name=room_name)
        except ChatRoom.DoesNotExist:
            print(f"   ⚠️  Room not found: {room_name}")
            continue
        
        # Check if attachment already exists
        existing = FileAttachment.objects.filter(
            chat_room=room,
            filename=file_data['filename']
        ).exists()
        
        if not existing:
            # Pick a random uploader from board members
            uploader = random.choice(board_members)
            
            # Create file attachment metadata (without actual file)
            attachment = FileAttachment.objects.create(
                chat_room=room,
                uploaded_by=uploader,
                filename=file_data['filename'],
                file_size=file_data['file_size'],
                file_type=file_data['file_type'],
                description=file_data.get('description', ''),
                file='demo_placeholder.txt',  # Placeholder - won't be accessible
            )
            attachments_created += 1
            print(f"   📎 Added: {file_data['filename']} (by {uploader.username})")
        else:
            print(f"   ⏭️  Already exists: {file_data['filename']}")

print(f"\n✅ Created {attachments_created} file attachment records")

# ============================================================================
# CREATE NOTIFICATIONS FOR DEMO USER
# ============================================================================

print("\n" + "=" * 80)
print("STEP 3: Creating Notifications for Demo User")
print("=" * 80)

notifications_created = 0

# Create notifications for mentions
for board in demo_boards:
    rooms = ChatRoom.objects.filter(board=board)
    for room in rooms:
        messages = ChatMessage.objects.filter(chat_room=room, mentioned_users=demo_admin)
        for msg in messages:
            # Check if notification already exists
            existing = Notification.objects.filter(
                recipient=demo_admin,
                chat_message=msg,
                notification_type='MENTION'
            ).exists()
            
            if not existing and msg.author != demo_admin:
                Notification.objects.create(
                    recipient=demo_admin,
                    sender=msg.author,
                    notification_type='MENTION',
                    text=f'{msg.author.username} mentioned you in {room.name}: "{msg.content[:50]}..."',
                    chat_message=msg,
                    is_read=False,
                )
                notifications_created += 1
                print(f"   🔔 Created notification from @{msg.author.username}")

print(f"\n✅ Created {notifications_created} notifications")

# ============================================================================
# CREATE TASK THREAD COMMENTS (for demonstrating task-level messaging)
# ============================================================================

print("\n" + "=" * 80)
print("STEP 4: Creating Task Thread Comments")
print("=" * 80)

task_comments_created = 0

# Get some tasks from demo boards
demo_tasks = Task.objects.filter(column__board__in=demo_boards)[:10]

task_comment_templates = [
    {'author': 'alex', 'content': 'Great progress on this! Let me know if you need any help.'},
    {'author': 'sam', 'content': 'I\'ve started working on this. Should have an update by EOD.'},
    {'author': 'jordan', 'content': '@demo_admin_solo Can you review the latest changes?'},
    {'author': 'demo_admin', 'content': 'Looks good! Moving this to review. @sam_rivera_demo please verify.'},
    {'author': 'sam', 'content': 'Verified and tested. Ready for production! 🚀'},
]

for task in demo_tasks:
    # Check if task already has comments
    existing_comments = TaskThreadComment.objects.filter(task=task).count()
    if existing_comments == 0:
        # Add 1-3 random comments
        num_comments = random.randint(1, 3)
        board_members = get_board_members(task.column.board)
        
        for i in range(num_comments):
            template = random.choice(task_comment_templates)
            author = get_user_by_key(template['author'])
            
            if author and author in board_members:
                comment = TaskThreadComment.objects.create(
                    task=task,
                    author=author,
                    content=template['content'],
                )
                task_comments_created += 1
                
                # Handle mentions
                for mentioned_username in comment.get_mentioned_usernames():
                    try:
                        mentioned_user = User.objects.get(username=mentioned_username)
                        comment.mentioned_users.add(mentioned_user)
                    except User.DoesNotExist:
                        pass

print(f"\n✅ Created {task_comments_created} task thread comments")

# ============================================================================
# SUMMARY
# ============================================================================

print("\n" + "=" * 80)
print("MESSAGING DEMO DATA SUMMARY")
print("=" * 80)

# Recalculate totals
total_rooms = ChatRoom.objects.filter(board__in=demo_boards).count()
total_messages = ChatMessage.objects.filter(chat_room__board__in=demo_boards).count()
total_attachments = FileAttachment.objects.filter(chat_room__board__in=demo_boards).count()
total_notifications = Notification.objects.filter(recipient=demo_admin).count()
total_task_comments = TaskThreadComment.objects.filter(task__column__board__in=demo_boards).count()

print(f"""
📊 Total Demo Messaging Data:
   • Chat Rooms: {total_rooms}
   • Chat Messages: {total_messages}
   • File Attachments: {total_attachments}
   • Notifications (for demo user): {total_notifications}
   • Task Thread Comments: {total_task_comments}

🎉 Demo messaging feature is now populated!
   Users can explore chat rooms, read messages, and see team collaboration in action.
""")

print("=" * 80)
print("DONE!")
print("=" * 80)
