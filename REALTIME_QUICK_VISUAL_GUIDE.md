# Real-Time Communication - Feature Guide

## 🎯 Quick Access Points

### From Main Navigation
```
Top Navigation Bar
└── "Messages" Link
    ├── View Notifications
    ├── See Unread Count
    └── Access All Communication
```

### From Boards
```
Board Page
├── Chat Rooms (per board)
│   ├── Create New Room
│   ├── View Messages
│   └── Real-time Updates
└── Task Comments (per task)
    ├── Add Comments
    ├── @Mention Users
    └── Instant Notifications
```

## 📊 Feature Overview

| Feature | Location | Access Level | Real-Time |
|---------|----------|--------------|-----------|
| **Chat Rooms** | Board → Messages | Board Members | ✅ WebSocket |
| **Task Comments** | Task Detail | Board Members | ✅ WebSocket |
| **Notifications** | Top Nav → Messages | Individual | ✅ Instant |
| **Mentions** | @username in messages | @-symbol | ✅ Instant |

## 🚀 Technology Stack

```
┌─────────────────────────────────────┐
│         Django Application          │
│     (8000 - Daphne Server)         │
├─────────────────────────────────────┤
│    WebSocket Layer (Channels)       │
├─────────────────────────────────────┤
│     Redis (127.0.0.1:6379)         │
│   Message Broker & Channel Layer    │
├─────────────────────────────────────┤
│  Celery Worker + Beat Scheduler    │
│  Task Processing & Background Jobs  │
└─────────────────────────────────────┘
```

## ✨ Real-Time Features

### 💬 Instant Messaging
- **What**: Send messages to team members instantly
- **Where**: Chat Rooms
- **How**: Type message, press Enter or Send
- **Update**: Appears in all members' browsers without refresh

### 📌 Task Discussions
- **What**: Comment on tasks in real-time
- **Where**: Task Detail Page
- **How**: Click Comments → Add Comment
- **Update**: All team members see instantly

### 🔔 Smart Notifications
- **What**: Get notified when mentioned
- **Where**: Notification Center (Messages)
- **How**: Use @username in messages
- **Update**: Instant notification to mentioned user

### 👥 Presence Indicators
- **What**: See who's typing/active
- **Where**: Chat rooms
- **How**: "User is typing..." indicator
- **Update**: Real-time without page refresh

## 🎓 Usage Examples

### Example 1: Quick Chat
```
1. Click "Messages" in top nav
2. Select a board
3. Open a chat room
4. Type: "Hey @john, can you review the design?"
5. @john gets instant notification
6. john responds in real-time
```

### Example 2: Task Collaboration
```
1. Open a task on your board
2. Scroll to Comments section
3. Type: "This needs @sarah's approval"
4. @sarah gets notified immediately
5. Other team members see the update
```

### Example 3: Team Update
```
1. Create a chat room (e.g., "Daily Standup")
2. Add all team members
3. Share: "@team quick update: feature X is complete"
4. Team members see in real-time
5. They can reply instantly
```

## 🔧 Services Status

### Required Services
✅ **Daphne Server** - WebSocket handler (port 8000)
✅ **Redis** - Message broker (port 6379)
✅ **Celery Worker** - Background tasks
✅ **Celery Beat** - Scheduled tasks

### All Start with
```batch
start_PrizmAI.bat
```

## 📈 Data Flow

```
User A Types Message
         ↓
   WebSocket Send
         ↓
   Channels Layer
         ↓
   Redis Channel
         ↓
   Connected Users
         ↓
   Real-Time Update (No Refresh!)
```

## 🛡️ Access Control

- **Chat Rooms**: Available to board members only
- **Task Comments**: Available to board members only
- **Notifications**: Personal to each user
- **Message History**: Accessible to room members
- **@Mentions**: Only tagged users get notifications

## 📱 Browser Compatibility

| Browser | WebSocket | Status |
|---------|-----------|--------|
| Chrome | ✅ | Full Support |
| Firefox | ✅ | Full Support |
| Safari | ✅ | Full Support |
| Edge | ✅ | Full Support |

## 🎯 Key URLs

```
/messaging/                              - Messaging home
/messaging/notifications/                - Notification center
/messaging/board/<board_id>/rooms/       - Board chat rooms
/messaging/room/<room_id>/               - Chat room detail
/messaging/task/<task_id>/comments/      - Task comments
ws://localhost:8000/ws/chat-room/<id>/  - Chat WebSocket
ws://localhost:8000/ws/task-comments/<id>/ - Task WebSocket
```

## 💡 Pro Tips

1. **Use @mentions strategically** - Gets users' attention instantly
2. **Create dedicated rooms** - Organize conversations by topic
3. **Monitor notifications** - Check regularly for mentions
4. **Pin important messages** - Use chat room descriptions for key info
5. **Use task comments** - Keeps discussions linked to work

## 🐛 If Something Isn't Working

### Message not sending?
- Check WebSocket connection (DevTools → Network)
- Refresh page to use HTTP fallback
- Verify you're in the room/task

### Notifications not appearing?
- Check notification settings
- Refresh the page
- Verify Redis is running

### Real-time updates slow?
- Check network connection
- Verify Daphne server is running
- Try in a different browser

### Chat room not showing?
- Refresh the page
- Verify you're a board member
- Check browser console for errors

---

**Everything is ready to use!** Start with `start_PrizmAI.bat` and explore the "Messages" menu.
