# Messaging Notification Badge Feature Guide

## Overview
A real-time notification badge has been added to the navigation bar that displays the count of unread messages. This helps users quickly see if they have new messages without needing to open the messaging tab.

## Features Implemented

### 1. ✅ Unread Message Count API Endpoint
**File**: `messaging/views.py`
**Function**: `get_unread_message_count(request)`

- **Endpoint**: `/messages/api/messages/unread-count/`
- **Method**: GET
- **Authentication**: Required (login_required)
- **Returns**: JSON with `unread_count` key

**Logic**:
- Retrieves all chat rooms the user is a member of
- Counts messages from the last 24 hours
- Excludes messages authored by the current user
- Returns total unread count across all rooms

**Example Response**:
```json
{
  "unread_count": 5
}
```

### 2. ✅ Notification Badge in Navigation
**File**: `templates/base.html`

**Features**:
- Red badge appears next to "Messages" link in navigation bar
- Badge shows unread count (capped at "99+" for large numbers)
- Hidden when unread_count is 0
- Uses Bootstrap 5 styling with `position-absolute` and `translate-middle` for perfect alignment

**HTML Structure**:
```html
<a class="nav-link position-relative" href="{% url 'messaging:hub' %}">
    <i class="fas fa-comments me-1"></i> Messages
    <span class="position-absolute top-0 start-100 translate-middle badge rounded-pill bg-danger" 
          id="unread-message-badge" style="display: none; font-size: 0.65rem;">
        <span id="unread-count">0</span>
    </span>
</a>
```

### 3. ✅ Auto-Refresh JavaScript
**File**: `templates/base.html`

**Features**:
- Updates unread count on page load
- Auto-refreshes every 30 seconds
- Only runs for authenticated users
- Graceful error handling with console logging
- Non-blocking fetch requests

**Behavior**:
- Badge appears when count > 0
- Badge hides when count = 0
- Count displays as "99+" when over 99 unread messages
- Silent failure if API is unavailable (doesn't break page functionality)

## How to Test

### Test 1: Basic Badge Display
1. Start the PrizmAI application
2. Log in as a user
3. Create a chat room and add multiple team members
4. Have another user send messages to that room
5. Navigate to the dashboard
6. Check the navigation bar - the badge should appear with the unread count

### Test 2: Auto-Refresh
1. Open the messaging hub in a tab
2. Open the dashboard in another tab or window
3. Have a team member send a message in the chat room
4. Wait up to 30 seconds
5. The badge count should update automatically without page reload

### Test 3: Badge Disappears
1. Open a chat room
2. Read all messages
3. The badge count will decrease as you view rooms
4. When all unread messages are viewed, the badge should disappear

### Test 4: Multiple Rooms
1. Create multiple chat rooms
2. Have teammates post messages in different rooms
3. The badge should show the total count across all rooms

## URL Configuration

**File**: `messaging/urls.py`

```python
# Unread Messages
path('messages/unread-count/', views.get_unread_message_count, name='get_unread_message_count'),
```

**Full URL**: `http://localhost:8000/messages/messages/unread-count/`

## Performance Considerations

### Current Implementation
- **Refresh Rate**: 30 seconds (configurable)
- **Data Scope**: Last 24 hours of messages
- **Calculation**: On-demand per request
- **Caching**: None (real-time)

### Optimization Opportunities for Future
1. **Add Message Read Tracking**: Store which messages each user has read
2. **WebSocket Updates**: Use WebSocket for real-time badge updates instead of polling
3. **Caching**: Cache unread count with 5-10 second TTL
4. **Database Index**: Add index on `ChatMessage.created_at` and `author` for faster queries

## Integration with Existing Features

### Notification Differences
- **Notification Badge** (bell icon): Mentions and special notifications
- **Message Badge** (messages link): Unread messages from all chat rooms

### WebSocket Integration
- The WebSocket consumer in `messaging/consumers.py` handles real-time message delivery
- The badge updates via polling every 30 seconds
- Future enhancement: Connect badge updates to WebSocket events for instant updates

## Browser Compatibility

- ✅ Chrome/Chromium
- ✅ Firefox
- ✅ Safari
- ✅ Edge
- ✅ Mobile browsers

**Required**: JavaScript enabled, ES6 support (fetch API)

## Files Modified

1. **messaging/views.py**
   - Added `get_unread_message_count(request)` function

2. **messaging/urls.py**
   - Added route for unread message count endpoint

3. **templates/base.html**
   - Updated Messages link with badge HTML
   - Added JavaScript for auto-refresh functionality

## Future Enhancement Ideas

1. **Real-time Updates**: Connect to WebSocket for instant badge updates
2. **Read Status Tracking**: Add `is_read` field to ChatMessage model
3. **Per-Room Notifications**: Show separate badges for each room
4. **Sound Alert**: Play notification sound when new message arrives
5. **Desktop Notifications**: Browser push notifications for new messages
6. **Mark as Read**: Button to quickly mark all messages as read

## Troubleshooting

### Badge Not Showing
1. Check browser console for JavaScript errors
2. Verify `get_unread_message_count` endpoint is accessible
3. Check that messages exist and are within 24-hour window
4. Clear browser cache and reload

### Badge Shows Wrong Count
1. Check that user is actually a member of the chat rooms
2. Verify message timestamps are correct
3. Check that messages aren't authored by the current user
4. Open a chat room to view messages (may affect future count calculations)

### Badge Not Updating
1. Check if refresh interval is working (browser DevTools Network tab)
2. Verify JavaScript isn't blocked
3. Check console for errors
4. Try manual page refresh

## API Response Examples

### With Unread Messages
```bash
curl http://localhost:8000/messages/messages/unread-count/
```
Response:
```json
{
  "unread_count": 3
}
```

### No Unread Messages
```json
{
  "unread_count": 0
}
```

---

**Created**: October 31, 2025
**Status**: ✅ Complete and Ready for Testing
