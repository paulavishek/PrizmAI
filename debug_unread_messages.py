"""
Debug script to check unread message counts
"""
import os
import sys
import django

# Setup Django
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'kanban_board.settings')
django.setup()

from django.contrib.auth.models import User
from messaging.models import ChatRoom, ChatMessage

# Get the first user (or you can specify username)
print("Enter username to check (or press Enter for first user):")
username = input().strip()

if username:
    user = User.objects.get(username=username)
else:
    user = User.objects.first()

print(f"\n=== Checking unread messages for user: {user.username} ===\n")

# Get all chat rooms the user is a member of
user_chat_rooms = ChatRoom.objects.filter(members=user)
print(f"User is member of {user_chat_rooms.count()} chat rooms:\n")

total_unread = 0
for room in user_chat_rooms:
    # Count messages that user hasn't read and didn't author
    unread_in_room = room.messages.exclude(read_by=user).exclude(author=user).count()
    total_unread += unread_in_room
    
    # Also count total messages in room
    total_in_room = room.messages.count()
    user_authored = room.messages.filter(author=user).count()
    
    print(f"Chat Room: {room.name} (Board: {room.board.name})")
    print(f"  - Total messages: {total_in_room}")
    print(f"  - Authored by user: {user_authored}")
    print(f"  - Unread by user: {unread_in_room}")
    
    # Check for any messages that might be counted multiple times
    all_messages = room.messages.all()
    print(f"  - Message IDs in this room: {list(all_messages.values_list('id', flat=True))[:10]}")
    print()

print(f"\n=== TOTAL UNREAD COUNT: {total_unread} ===")

# Additional debug: Check if there are any duplicate message IDs
all_user_room_messages = ChatMessage.objects.filter(chat_room__in=user_chat_rooms)
message_ids = list(all_user_room_messages.values_list('id', flat=True))
if len(message_ids) != len(set(message_ids)):
    print(f"\nWARNING: Found duplicate message IDs!")
    from collections import Counter
    duplicates = [id for id, count in Counter(message_ids).items() if count > 1]
    print(f"Duplicate IDs: {duplicates}")
else:
    print(f"\nNo duplicate message IDs found.")

# Check the exact query used in the view
print("\n=== Simulating the view's logic ===")
unread_count = 0
for room in user_chat_rooms:
    room_unread = room.messages.exclude(read_by=user).exclude(author=user).count()
    unread_count += room_unread
print(f"Total unread (view logic): {unread_count}")
