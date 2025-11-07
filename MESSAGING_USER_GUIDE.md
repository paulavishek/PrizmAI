# Real-Time Messaging - User Guide 📱

## Getting Started with Messaging

### Step 1: Access Messaging Hub
1. Log in to PrizmAI
2. Click **"Messages"** in the top navigation bar
3. You'll see the **Messaging Hub** with all your boards

### Step 2: Navigate to a Board's Chat Rooms
1. From the Messaging Hub, click **"Chat Rooms"** on any board card
2. You'll see all chat rooms for that board
3. Or go to: **Boards → Select a Board → "Messages" button**

---

## 💬 How to Send Messages

### In a Chat Room
1. Click **"Chat Rooms"** for a board
2. Click on any room name to open it
3. **Type your message** in the input box at the bottom
4. Press **Enter** or click the **Send button** (✈️)
5. Message appears **instantly** to all members!

### In Task Comments
1. Open any task on a board
2. Scroll down to the **"Comments"** section
3. Type your comment in the text field
4. Click **"Post Comment"**
5. All team members see it **immediately**

---

## 👥 How to Invite Other Users

### When Creating a Chat Room
1. On the board, click **"Messages"** in navigation
2. Click **"Create New Room"** button
3. Fill in:
   - **Room Name** (e.g., "Frontend Team")
   - **Description** (optional)
4. **Select members** from the checkbox list
   - Shows all board members
   - Check the boxes for who to invite
5. Click **"Create Room"**
6. Selected members can now see and access the room

### When Creating a Board (To Add Members)
1. From Dashboard or Boards page
2. Create or edit a board
3. Add members when creating the board
4. Those members can then be invited to chat rooms

### Quick Note About Permissions
- **Chat Rooms**: Members can only join if explicitly added
- **Task Comments**: All board members can see and comment
- **@Mentions**: Users must exist in the board to be mentioned

---

## 🔔 @Mention System

### How to Mention Someone
**In chat or comments, type:**
```
@username Hey, can you check this?
```

### What Happens
1. Type `@` and start typing a name
2. Suggestions appear automatically
3. Click the username or press Enter
4. **Mentioned user gets instant notification**
5. They can click the notification to see your message

### Example
```
"@john @sarah Can you review the design?"
```
Both John and Sarah get notifications!

---

## 📍 Navigation Guide

### Main Messaging Hub
```
Messages (Top Nav)
  ├── View all your boards
  ├── See recent notifications
  ├── Quick links to chat rooms
  └── Help information
```

### From a Board
```
Board Page
  ├── "Messages" Button → Chat rooms for this board
  ├── Task → Comments section → Add comments
  └── @mention team members anywhere
```

### Notifications
```
Messaging Hub
  └── Unread notifications preview
       ├── @mentions from chat
       ├── @mentions from tasks
       └── Quick links to view full context
```

---

## 📊 Feature Comparison

| Feature | Where | Real-Time | @Mention | Notification |
|---------|-------|-----------|----------|--------------|
| **Chat Rooms** | Board | ✅ Yes | ✅ Yes | ✅ Yes |
| **Task Comments** | Task Page | ✅ Yes | ✅ Yes | ✅ Yes |
| **Notifications** | Messaging | ✅ Live | N/A | ✅ Yes |

---

## 💡 Pro Tips

### Organize Your Communication
- **Create specific chat rooms**: #frontend, #backend, #design, etc.
- **Use task comments for discussions**: Keeps conversations linked to work
- **Use @mentions strategically**: Gets instant attention
- **Check notifications regularly**: See all mentions in one place

### Best Practices
1. **Use room descriptions**: Help members understand the room's purpose
2. **Start with specific names**: "Q4 Planning" instead of "Discussion"
3. **Invite only relevant members**: Keep rooms focused
4. **Use @mentions for urgent items**: Not for casual chat
5. **Follow up on task comments**: Review discussion before closing tasks

### Team Collaboration
1. **Onboard new members**: Add them to relevant chat rooms
2. **Pin important info**: Use room descriptions for key details
3. **Archive old rooms**: Keep the list organized
4. **Create standing meetings**: Regular chat room check-ins

---

## ⚙️ Message Settings

### Real-Time Updates
- Messages appear **instantly** to all members
- **No page refresh needed**
- Works even if you have multiple windows open
- WebSocket connection auto-reconnects if lost

### Message History
- Last **50 messages** load automatically
- Older messages load on scroll
- **Permanently saved** in database
- Searchable in the future

### Notifications
- **Instant alerts** for @mentions
- **One-click navigation** to the message
- **Mark as read** when you view
- Can dismiss without viewing

---

## 🆘 Troubleshooting

### Messages Not Appearing?
- ✅ Check you're a member of the room
- ✅ Refresh the page
- ✅ Clear browser cache
- ✅ Check if Daphne server is running

### Can't See a Chat Room?
- ✅ Verify you're added as a member
- ✅ Refresh the page
- ✅ Check you're on the correct board
- ✅ Ask an admin to add you

### @Mention Not Working?
- ✅ Check the username exists
- ✅ Verify they're a board member
- ✅ Type the exact username
- ✅ User must be in the board to be mentioned

### Not Getting Notifications?
- ✅ Check you're not in "Do Not Disturb" mode
- ✅ Verify browser notifications are enabled
- ✅ Refresh the notifications page
- ✅ Check Celery worker is running

---

## 🎓 Common Workflows

### Scenario 1: Daily Standup
1. Create room: "Daily Standup"
2. Add core team members
3. Share updates in the room
4. @mention if questions arise
5. Access messages anytime for reference

### Scenario 2: Project Discussion
1. Create room: "Project XYZ"
2. Invite project team
3. Share links and ideas
4. Use task comments for specific discussions
5. Reference chat history when needed

### Scenario 3: Quick Decision
1. Open existing team room
2. Type: "@alice @bob quick decision needed on..."
3. They get instant notifications
4. Real-time discussion happens
5. Decision is logged in chat history

---

## 📱 Browser Support

| Browser | Support | WebSocket | Status |
|---------|---------|-----------|--------|
| Chrome | ✅ Full | ✅ Yes | Recommended |
| Firefox | ✅ Full | ✅ Yes | Fully Supported |
| Safari | ✅ Full | ✅ Yes | Fully Supported |
| Edge | ✅ Full | ✅ Yes | Fully Supported |

---

## 🚀 Quick Start (2 minutes)

1. **Click "Messages"** in top nav
2. **Find a board** with chat rooms
3. **Click "Chat Rooms"**
4. **Select a room** from the list
5. **Type a message** in the input box
6. **Press Enter** to send
7. **See it appear instantly!** ✨

---

## 📞 Need Help?

- **Can't find Messages?** Look in top navigation bar
- **No boards?** Create one from the Boards page first
- **Want to chat privately?** Create a room and add specific members
- **Need to mention someone?** Type @ and their name will autocomplete

**Everything is real-time and ready to use!** 🎉
