# Demo Messaging: Multi-User Testing Guide

## Overview
Instead of simulating messages, users can now **login as different demo accounts** to experience true real-time messaging delivery.

## Demo User Credentials

All demo users share the same password for easy testing:

| Username | Password | Role |
|----------|----------|------|
| `demo_admin_solo` | `demo123` | Admin |
| `alex_chen_demo` | `demo123` | Project Manager |
| `sam_rivera_demo` | `demo123` | Developer |
| `jordan_taylor_demo` | `demo123` | Analyst |

## How to Test Real-Time Messaging

### Step-by-Step Guide:

1. **Keep your current browser window open** (logged in as `demo_admin_solo`)
2. **Open a new incognito/private window** (Ctrl+Shift+N in Chrome, Ctrl+Shift+P in Firefox)
3. **Login with different credentials:**
   - Username: `sam_rivera_demo`
   - Password: `demo123`
4. **Navigate to the same chat room** in both windows
5. **Send messages from either window** and watch them appear instantly in both!

### What You'll Experience:

- ✅ **Real-time delivery**: Messages appear instantly without refresh
- ✅ **WebSocket connection**: See the "Connected" status indicator
- ✅ **Typing indicators**: See when the other user is typing
- ✅ **@Mentions**: Try mentioning users and see notifications
- ✅ **Read receipts**: See when messages are read
- ✅ **File sharing**: Upload and share files between users

## Where to Find Credentials

The credentials are displayed in two places:

1. **Messaging Hub** (`/messaging/hub/`)
   - Green credential box at the top
   - Shows all 4 demo accounts
   - Instructions for multi-window testing

2. **Chat Room Detail** (any chat room)
   - Green banner below the chat header
   - Quick instructions for testing
   - Lists all available demo accounts

## Changes Made

### 1. Password Setup
- **File**: `kanban/management/commands/create_demo_organization.py`
- **Change**: Demo users now get `user.set_password('demo123')` instead of `user.set_unusable_password()`

### 2. Demo Admin Password
- **File**: `kanban/utils/demo_admin.py`
- **Change**: `demo_admin_solo` also gets password 'demo123' for consistency

### 3. Messaging Hub UI
- **File**: `templates/messaging/messaging_hub.html`
- **Change**: Replaced team member badges with full credentials display
- **Added**: 4-column grid showing all usernames and password
- **Added**: Step-by-step testing instructions

### 4. Chat Room UI
- **File**: `templates/messaging/chat_room_detail.html`
- **Change**: Replaced simulation banner with credentials display
- **Removed**: `simulateDemoMessage()` function (no longer needed)
- **Removed**: "Simulate Demo Message" button

### 5. Password Update Script
- **File**: `update_demo_passwords.py`
- **Purpose**: Update existing demo users to use 'demo123' password
- **Usage**: `python update_demo_passwords.py`

## Why This Approach?

### Previous Approach (Simulation):
- ❌ Complex simulation logic
- ❌ Fake messages don't persist
- ❌ Users couldn't experience true real-time delivery
- ❌ Required explanation banners about what's simulated

### New Approach (Multiple Logins):
- ✅ Simple and authentic
- ✅ Users experience the REAL feature
- ✅ All functionality works (WebSocket, typing, mentions, read receipts)
- ✅ No confusion about what's real vs simulated
- ✅ Better demonstrates the product's capabilities

## Technical Notes

### WebSocket Behavior
When users login as different accounts in separate browser windows:
- Each window maintains its own WebSocket connection
- Messages sent from one window are broadcast through Redis
- Redis delivers to all connected WebSocket clients in that room
- Both users see instant delivery without page refresh

### Security
- Demo passwords are intentionally simple (`demo123`) for easy testing
- All demo accounts are isolated to the demo organization
- Regular production users are unaffected

## Testing Checklist

Test the following with multiple logged-in users:

- [ ] Send message from User A → appears instantly in User B's window
- [ ] Typing indicator shows when either user is typing
- [ ] @mention User B from User A → User B gets notification
- [ ] File upload from User A → User B sees file immediately
- [ ] Read receipt updates when User B reads User A's message
- [ ] Connection status indicator shows "Connected" in both windows
- [ ] Heartbeat keeps connection alive (no disconnects during idle)
- [ ] Reconnection works if connection drops

## Future Enhancements

Potential improvements for demo experience:
- Add "Quick Test" button that opens incognito window automatically
- Pre-populate more diverse conversations
- Add demo team presence indicators
- Create demo scenarios (e.g., "Sprint Planning Chat")
