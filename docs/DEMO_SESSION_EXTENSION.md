# Demo Session Extension - Technical Documentation

## Overview
The demo session extension feature allows users to extend their demo session when it's about to expire, giving them more time to explore PrizmAI features before committing to an account.

## Recent Changes (January 2026)

### Issues Fixed
1. **Visibility Issue**: The "Extend Session" button was not visible until hover
   - **Root Cause**: Used `btn-outline-warning`/`btn-outline-info` classes which have poor contrast on colored alert backgrounds
   - **Solution**: Changed to `btn-light` with white border for better visibility
   
2. **Extension Limits**: Need to prevent unlimited extensions
   - **Solution**: Implemented configurable limits with clear user messaging

## Configuration

All demo settings are centralized in `kanban/utils/demo_settings.py`:

```python
MAX_DEMO_EXTENSIONS = 3              # Max extensions per session
EXTENSION_DURATION_HOURS = 1         # Hours added per extension
INITIAL_DEMO_DURATION_HOURS = 48     # Initial session length
```

### Why These Limits?

- **3 Extensions Max**: Prevents abuse while being generous
  - Initial: 48 hours
  - After 3 extensions: 48 + 3 = 51 hours total
  - This gives users ~2 days to try the product thoroughly
  
- **1 Hour Per Extension**: Short enough to encourage conversion, long enough to be useful
  - Users appreciate the flexibility
  - Creates multiple conversion touchpoints
  
- **Total Time Window**: Up to 51 hours maximum
  - Long enough for thorough evaluation
  - Short enough to maintain urgency for conversion

## User Experience Flow

### 1. Initial Session (48 hours)
User starts demo → Gets 48 hours to explore

### 2. Warning Triggers
- **4 hours remaining**: Info banner (blue)
- **1 hour remaining**: Warning banner (yellow) + "Extend Session" button visible
- **15 minutes remaining**: Critical banner (red) + Button hidden, push to create account

### 3. Extension Process
```
User clicks "Extend Session"
  ↓
Button shows loading spinner
  ↓
Backend validates:
  - Session exists
  - Not expired
  - Extensions < MAX (3)
  ↓
Success: +1 hour, hide banner, show toast with remaining extensions
Failure: Show error message, redirect to signup if max reached
```

### 4. After Extensions Used
- Button disappears when 3 extensions used
- Message shows "No extensions remaining"
- User must create account to continue

## Technical Implementation

### Backend (`kanban/demo_views.py`)

```python
@require_POST
def extend_demo_session(request):
    # Validates session, checks limits
    # Extends by EXTENSION_DURATION_HOURS
    # Returns JSON with status and extensions_remaining
```

**Key Validations:**
1. Session exists and valid
2. Session not already expired
3. Extensions count < MAX_DEMO_EXTENSIONS
4. Updates `extensions_count` field in database

**Response Format:**
```json
{
  "status": "success",
  "message": "Session extended by 1 hour",
  "new_expiry_time": "2026-01-15T10:30:00Z",
  "extensions_remaining": 2,
  "extension_duration_hours": 1
}
```

### Frontend (`templates/demo/partials/expiry_warning.html`)

**Button Visibility:**
- Shows when: `expiry_warning_level != 'critical'` AND `demo_extensions_remaining > 0`
- Hides when: Critical warning OR no extensions left
- Displays remaining extensions count inline

**AJAX Handling:**
- Disables button during request (prevents double-clicks)
- Shows loading state
- On success: Removes banner, shows toast with info
- On error: Re-enables button, shows error message
- On max reached: Redirects to registration after 3 seconds

### Context Processor (`kanban/context_processors.py`)

Provides to all templates:
```python
demo_extensions_used        # Current count
demo_extensions_max         # Maximum allowed (3)
demo_extensions_remaining   # How many left
demo_extension_duration     # Hours per extension (1)
```

### Database Schema (`analytics/models.py`)

```python
class DemoSession:
    extensions_count = IntegerField(default=0)
    # Tracks how many times user extended session
```

## Configuration Tips

### To Be More Generous:
```python
MAX_DEMO_EXTENSIONS = 5              # Allow 5 extensions
EXTENSION_DURATION_HOURS = 2         # 2 hours each
INITIAL_DEMO_DURATION_HOURS = 72     # Start with 3 days
```
**Result**: Up to 72 + (5×2) = 82 hours (3.4 days)

### To Be More Restrictive:
```python
MAX_DEMO_EXTENSIONS = 2              # Only 2 extensions
EXTENSION_DURATION_HOURS = 0.5       # 30 minutes each
INITIAL_DEMO_DURATION_HOURS = 24     # Start with 1 day
```
**Result**: Up to 24 + (2×0.5) = 25 hours (1 day)

### To Remove Extensions Entirely:
```python
MAX_DEMO_EXTENSIONS = 0              # No extensions allowed
```
**Result**: Hard 48-hour limit

## Analytics & Tracking

Tracked events in `DemoAnalytics`:
```python
event_type='session_extended'
event_data={
    'extensions_count': 1,
    'new_expiry': '2026-01-15T10:30:00Z'
}
```

Use this to monitor:
- How many users extend sessions
- Average extensions per session
- Conversion rate: extenders vs. non-extenders
- Optimal extension limits

## Testing Checklist

- [ ] Button visible on warning/info banners
- [ ] Button hidden on critical banner
- [ ] Button hidden when extensions exhausted
- [ ] Extension adds correct hours
- [ ] Max extensions enforced (3)
- [ ] Proper error messages shown
- [ ] Analytics event tracked
- [ ] Extensions count persists across page loads
- [ ] Expired sessions cannot be extended
- [ ] Toast shows remaining extensions
- [ ] Redirect to signup when max reached

## Security Considerations

1. **No Client-Side Bypass**: All validation on server
2. **Session-Based**: Tied to Django session, not cookies
3. **Database-Backed**: Extension count in `DemoSession` model
4. **CSRF Protected**: Requires valid CSRF token
5. **Rate Limited**: Could add if abuse detected

## Future Enhancements

1. **Variable Extension Duration**: First extension = 1hr, second = 30min, third = 15min (increasing urgency)
2. **Email Notification**: "Your demo expires in 1 hour - extend now?"
3. **Analytics Dashboard**: Show extension usage patterns
4. **A/B Testing**: Test different extension limits for conversion optimization
5. **Premium Extensions**: Offer longer extensions for email signup

## Related Files

- `kanban/utils/demo_settings.py` - Configuration
- `kanban/demo_views.py` - Backend logic
- `kanban/context_processors.py` - Template context
- `templates/demo/partials/expiry_warning.html` - UI
- `analytics/models.py` - Database schema
- `static/css/theme.css` - Styling

## Contact

For questions about demo mode configuration, contact the development team.
