# Refresh Button Fix - AI Assistant Chat

## Problem
The refresh button in the AI Assistant chat interface was non-functional. When clicked, nothing happened.

## Root Cause
The refresh button in the chat header had no event listener or onclick handler attached to it. It was just a visual placeholder without any JavaScript functionality.

### Before (Line 311 in templates/ai_assistant/chat.html):
```html
<button class="btn btn-sm btn-outline-secondary" title="Refresh data">
    <i class="fas fa-sync"></i>
</button>
```

## Solution
1. **Added button ID**: Added `id="refresh-btn"` to make the button selectable and identifiable
2. **Added tooltip**: Updated the title to be more descriptive: "Refresh knowledge base and clear cache"
3. **Added text label**: Added "Refresh" text to make it clear what the button does
4. **Implemented event listener**: Added JavaScript event listener that:
   - Shows loading state with spinner animation
   - Calls the backend `refresh_knowledge_base` endpoint
   - Displays success feedback with a checkmark
   - Reloads chat messages to reflect any updates
   - Handles errors gracefully

### After:
```html
<button class="btn btn-sm btn-outline-secondary" id="refresh-btn" title="Refresh knowledge base and clear cache">
    <i class="fas fa-sync"></i> Refresh
</button>
```

## JavaScript Implementation
```javascript
document.getElementById('refresh-btn')?.addEventListener('click', function() {
    const btn = this;
    const originalHTML = btn.innerHTML;
    
    // Show loading state
    btn.disabled = true;
    btn.innerHTML = '<i class="fas fa-spinner fa-spin me-2"></i> Refreshing...';
    
    fetch(`{% url "ai_assistant:refresh_kb" %}?board_id=${document.getElementById('board-selector').value || ''}`, {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
            'X-CSRFToken': document.querySelector('[name=csrfmiddlewaretoken]').value,
        }
    })
    .then(r => r.json())
    .then(data => {
        if (data.status === 'success') {
            // Show success feedback
            btn.innerHTML = '<i class="fas fa-check me-2"></i> Refreshed!';
            setTimeout(() => {
                btn.innerHTML = originalHTML;
                btn.disabled = false;
            }, 2000);
            
            // Reload messages to show updated content
            loadMessages();
        } else {
            alert('Error refreshing knowledge base: ' + (data.error || 'Unknown error'));
            btn.innerHTML = originalHTML;
            btn.disabled = false;
        }
    })
    .catch(err => {
        alert('Error refreshing knowledge base: ' + err.message);
        btn.innerHTML = originalHTML;
        btn.disabled = false;
    });
});
```

## What the Refresh Button Does
When clicked, the refresh button:
1. **Refreshes the knowledge base** - Re-indexes project data to provide fresh context for AI responses
2. **Clears response cache** - Ensures the next AI request uses fresh data instead of cached responses
3. **Respects project context** - Only refreshes data for the currently selected project/board
4. **Provides visual feedback** - Shows loading spinner and success confirmation

## Backend Endpoint
The button calls the existing backend endpoint:
- **URL**: `/assistant/api/knowledge-base/refresh/`
- **Method**: POST
- **Parameters**: 
  - `board_id` (optional) - Specific board/project to refresh, or all if omitted
- **Response**: JSON with status and message

## Files Modified
- `templates/ai_assistant/chat.html` - Added button ID, text label, and JavaScript event listener

## Testing
To test the fix:
1. Open the AI Assistant chat interface
2. Click the "Refresh" button next to the "Clear" button
3. Observe:
   - Button shows "Refreshing..." with spinner
   - After completion, shows "Refreshed!" with checkmark
   - Button returns to normal state after 2 seconds
   - Chat messages are reloaded with fresh data
