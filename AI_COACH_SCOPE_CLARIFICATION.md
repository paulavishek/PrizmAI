# AI Coach Scope Clarification

## Issue Identified
The "Ask the AI Coach" feature was not explicitly communicating that it only analyzes data from the current board.

## Root Cause Analysis
Looking at the implementation in [ai_coach_service.py](kanban/utils/ai_coach_service.py#L210-L275):

```python
def generate_coaching_advice(self, board, pm_user, question: str) -> Optional[str]:
    # Gather context - ONLY FROM CURRENT BOARD
    active_tasks = Task.objects.filter(
        column__board=board,  # ← Limited to current board
        progress__lt=100
    ).count()
    
    latest_velocity = TeamVelocitySnapshot.objects.filter(
        board=board  # ← Limited to current board
    ).order_by('-period_end').first()
```

The AI Coach:
- ✅ Only queries data from the **specific board** passed to it
- ✅ Retrieves context (active tasks, velocity, team size) from that single board only
- ✅ Does NOT have access to other boards' data
- ✅ Cannot perform cross-board comparisons or analysis

## Why This Is The Correct Design
This is actually a **good design decision** because:
1. **Privacy & Security**: Users should not accidentally expose data from boards they're asking about to other board contexts
2. **Focused Advice**: Board-specific context leads to more actionable, relevant advice
3. **Performance**: Querying a single board is faster than analyzing all boards
4. **Clarity**: Each board is treated as a separate project with its own context

## Changes Made

### 1. Coach Ask Page ([coach_ask.html](templates/kanban/coach_ask.html#L126-L130))
Added a prominent info alert below the title:

```html
<div class="alert alert-info mt-3" style="max-width: 700px; margin: 0 auto;">
    <i class="fas fa-info-circle me-2"></i>
    <strong>Note:</strong> The AI Coach analyzes data from <strong>{{ board.name }}</strong> board only. 
    Questions about other boards or cross-board comparisons are not supported.
</div>
```

### 2. Coach Dashboard ([coach_dashboard.html](templates/kanban/coach_dashboard.html#L436-L440))
Added clarifying text in the "Ask the Coach" section:

```html
<p class="text-muted mb-3">Have a specific question about your project? Ask the AI coach for personalized advice based on this board's context.</p>
<small class="text-muted d-block mb-3">
    <i class="fas fa-info-circle me-1"></i>
    <em>The AI Coach analyzes data from {{ board.name }} only. Cross-board questions are not supported.</em>
</small>
```

## User Impact

**Before:**
- Users could ask cross-board questions like "which board has the most risks?"
- AI would respond based only on current board data, potentially confusing users
- No indication that the scope was limited to one board

**After:**
- Clear notification that AI Coach is board-specific
- Users understand questions should relate to the current board only
- Sets proper expectations about the feature's capabilities

## Example Questions Users Should Ask

### ✅ Good Questions (Board-Specific)
- "How can I improve my team's velocity?"
- "What should I do about scope creep in my project?"
- "How do I handle an overloaded team member?"
- "We're at risk of missing our deadline. What are my options?"
- "How can I better manage project risks?"

### ❌ Questions That Won't Work (Cross-Board)
- "Which board has the most number of risks?"
- "Compare velocity across all my boards"
- "Which project is most at risk?"
- "Show me tasks from other boards"

## Technical Details

**Files Modified:**
1. `templates/kanban/coach_ask.html` - Added info alert on the question page
2. `templates/kanban/coach_dashboard.html` - Added clarifying text on dashboard

**Files Analyzed (No Changes Needed):**
- `kanban/utils/ai_coach_service.py` - Confirmed board-scoped implementation
- `kanban/coach_views.py` - Verified single-board context passing

## Testing Recommendations

1. Navigate to any demo board's AI Coach section
2. Verify the info notice appears on the "Ask the AI Coach" page
3. Verify the clarifying text appears on the Coach Dashboard
4. Test asking both board-specific and cross-board questions to confirm behavior

## Conclusion

✅ **Status**: Issue Resolved

The AI Coach is **correctly** limited to analyzing only the current board. User interface has been updated to clearly communicate this limitation to prevent confusion. This is the intended design and should remain as-is for privacy, performance, and UX reasons.
