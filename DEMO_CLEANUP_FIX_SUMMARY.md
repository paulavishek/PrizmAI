# Demo Board Cleanup Issue - Fixed

## Issue Reported

User created a board "Website Redesign Project" in solo demo mode. The 48-hour session expired, but when logging in again, the board was still visible even though all demo data should have been cleaned up.

## Root Cause

The issue was a **mismatch between how boards are tagged and how the cleanup searches for them**:

### What Was Happening:
1. When a user creates a board in demo mode, it gets tagged with `created_by_session` = **browser_fingerprint** (a 64-char hash)
2. The browser fingerprint persists across multiple demo sessions for the same user
3. When demo sessions expire, the cleanup task searched for boards using **session_id** only
4. Since the board was tagged with fingerprint (not session_id), it was never found by cleanup
5. Result: User-created boards persisted indefinitely across multiple demo sessions

### Code Evidence:

**Board Creation** ([kanban/views.py:261-263](kanban/views.py#L261-L263)):
```python
browser_fingerprint = request.session.get('browser_fingerprint')
if browser_fingerprint:
    board.created_by_session = browser_fingerprint  # ← Tagged with fingerprint
```

**Old Cleanup Logic** ([kanban/tasks/demo_tasks.py:40-67](kanban/tasks/demo_tasks.py#L40-L67)):
```python
expired_session_ids = list(expired_sessions.values_list('session_id', flat=True))

deleted_boards = Board.objects.filter(
    created_by_session__in=expired_session_ids,  # ← Only searched session_id
    organization=demo_org,
    is_official_demo_board=False
).delete()[0]
```

**The Problem**: 
- Board tagged with: `71bb44cd5a4b7b3e98b177734aeab7cefad031d3128b6a19a27cd5d7d365889f` (fingerprint)
- Cleanup searched for: session IDs like `ycmpetzs4msb1iwg5jghtusbkumcrcfi`
- No match = board never deleted

## The Fix

Updated all cleanup functions to search for content using **BOTH session_id AND browser_fingerprint**:

### Files Modified:

1. **[kanban/tasks/demo_tasks.py](kanban/tasks/demo_tasks.py)** - Celery task for automatic cleanup
2. **[kanban/management/commands/cleanup_demo_sessions.py](kanban/management/commands/cleanup_demo_sessions.py)** - Manual cleanup command
3. **[kanban/demo_views.py](kanban/demo_views.py)** - Reset demo data function

### Changes Made:

```python
# OLD: Only session IDs
expired_session_ids = list(expired_sessions.values_list('session_id', flat=True))

# NEW: Session IDs AND browser fingerprints
expired_session_ids = list(expired_sessions.values_list('session_id', flat=True))
expired_fingerprints = list(expired_sessions.exclude(
    browser_fingerprint__isnull=True
).values_list('browser_fingerprint', flat=True))

# Combine both for comprehensive cleanup
identifiers_to_cleanup = expired_session_ids + expired_fingerprints

# Use combined list in queries
deleted_boards = Board.objects.filter(
    created_by_session__in=identifiers_to_cleanup,  # ← Now finds both
    organization=demo_org,
    is_official_demo_board=False
).delete()[0]
```

## Verification

### Test Results:
- Found 51 DemoSessions with the same browser fingerprint
- Sessions 1-50 were expired (from Jan 1-6)
- Session 51 is currently active (Jan 7)
- The board "Website Redesign Project" was created during one of the expired sessions
- **With the fix, cleanup now correctly identifies this board for deletion**

### Testing Output:
```
Expired sessions: 97
  - Session IDs: 97
  - Fingerprints: 50
  - Total identifiers: 147

BOARDS THAT WILL BE DELETED: 1
✓ Website Redesign Project
```

## How to Apply the Fix

### For Existing Stale Boards:
Run the cleanup command manually:
```bash
python manage.py cleanup_demo_sessions
```

This will:
- Find all expired DemoSessions
- Extract both session_ids AND browser_fingerprints
- Delete boards/tasks/comments created by those sessions
- Clean up the "Website Redesign Project" board

### For Future Sessions:
The automated Celery Beat task already runs hourly and will now correctly clean up boards tagged with browser fingerprints.

## Impact

✅ **Fixed:**
- User-created demo boards are now properly cleaned up after 48-hour expiry
- Works for boards tagged with either session_id or browser_fingerprint
- Prevents accumulation of stale demo data

✅ **Maintained:**
- Official demo boards (`is_official_demo_board=True`) are never deleted
- Browser fingerprint tracking still works correctly
- 48-hour expiry from first demo start is preserved

## Why This Design?

The browser fingerprint approach was intentionally designed to prevent users from resetting the 48-hour timer by logging out and back in. The fingerprint tracks a user across multiple sessions, so:

1. User starts demo → Creates fingerprint → Expires in 48 hours
2. User logs out and back in → Same fingerprint found → Same expiry time
3. User creates board → Board tagged with fingerprint
4. **Now with fix:** Cleanup finds board by fingerprint when ANY session with that fingerprint expires

This ensures users can't bypass the 48-hour limit while also ensuring proper cleanup of their created content.
