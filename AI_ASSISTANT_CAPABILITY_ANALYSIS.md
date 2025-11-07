# AI Assistant Capability Analysis Report

## Issue Summary
The AI assistant couldn't answer "how many total tasks are in all the boards?" - a reasonable question about aggregated project data. The Gemini response said it needs more specific information and can't access available context.

---

## Root Cause: Limited Context Window

### What the AI Assistant CAN Answer ✅

1. **Single Board Queries**
   - "What tasks are in Board 1?"
   - "What's the status of [specific board name]?"
   - "Who is on the X project?"

2. **Task-Specific Queries**
   - "Find tasks assigned to [user]"
   - "What are high priority tasks?"
   - "Get all overdue tasks"

3. **General Advice**
   - "What are best practices for project management?"
   - "How should I prioritize my team?"
   - "What's a good agile methodology?"

4. **Web-Based Queries** (with RAG enabled)
   - "Latest project management trends"
   - "What tools should I use for X?"
   - "Industry best practices for risk management"

---

## What the AI Assistant CANNOT Answer ❌

1. **Cross-Board Aggregate Queries** - *YOUR QUESTION*
   - ❌ "How many total tasks are in all boards?"
   - ❌ "Total tasks across all projects?"
   - ❌ "How many tasks are overdue in the entire system?"

2. **System-Wide Analytics**
   - ❌ "What's the total team capacity?"
   - ❌ "How many tasks per team member across all boards?"
   - ❌ "What's the workload distribution?"

3. **Complex Queries Requiring All Data**
   - ❌ "Compare task counts across all boards"
   - ❌ "Show me boards sorted by task count"
   - ❌ "Which board has the most overdue tasks?"

---

## Why This Happens: The Context Architecture

### Current Implementation
```python
# In chatbot_service.py - get_PrizmAI_context()

if self.board:
    # ✅ WORKS: Gets context for ONE board
    context += f"Board: {self.board.name}\n"
    tasks = Task.objects.filter(column__board=self.board)
    
elif self.user:
    # ⚠️ LIMITED: Only gets board names
    boards = Board.objects.filter(
        Q(created_by=self.user) | Q(members=self.user)
    ).distinct()[:5]  # ← Only first 5 boards!
    
    for board in boards:
        context += f"- {board.name}\n"  # ← Only names, NO task counts!
```

### The Problem

1. **When a board_id is selected:**
   - ✅ Full task details provided
   - ✅ All team members shown
   - ✅ Complete context available

2. **When NO board is selected (All Projects view):**
   - ❌ Only board NAMES are provided
   - ❌ NO task counts
   - ❌ NO task details
   - ❌ Limited to first 5 boards
   - ❌ AI cannot aggregate data it doesn't see

### Code Flow Example

```
User asks: "How many total tasks?"
    ↓
send_message() receives board_id = None or undefined
    ↓
PrizmAIChatbotService(user=request.user, board=None)
    ↓
get_PrizmAI_context() runs with self.board = None
    ↓
Falls to: "Get all user's boards and projects" branch
    ↓
Context = ["Board 1", "Board 2", "My Tasks Demo Board", ...]
    ↓
NO TASK COUNTS, NO TASK DETAILS!
    ↓
Gemini receives partial context
    ↓
Response: "I only see board names, not task counts"
```

---

## What Information IS Provided to the AI

### For Single Board (board_id provided):
```
**PrizmAI Project Context:**

Board: Software Project

**Tasks (8):**
- [Todo] User authentication (Priority: High, Assigned: John)
- [In Progress] API integration (Priority: High, Assigned: Jane)
- [Done] Database schema (Priority: Medium, Assigned: Bob)
... (up to 20 tasks)

**Team Members:** John Smith, Jane Doe, Bob Johnson
```

### For All Projects (NO board_id):
```
**PrizmAI Project Context:**

**User's Boards (5):**
- Board 1
- Software Project
- My Tasks Demo Board
- Social Media Relaunch for "Nova" Sportswear
- Bug Tracking
```

---

## Why This Design Limitation Exists

1. **Token Limits** - AI models have input/output token limits
   - All project data would be too large for one request
   - System prompts + large context = expensive/slow

2. **Performance** - Fetching all data is slow
   - Avoids database queries for thousands of tasks
   - Faster response times for single-board queries

3. **Current Architecture** - Designed for focused conversations
   - Chat within a board context works great
   - System-wide queries not originally supported

---

## Current Workarounds (What Users Can Do)

### Workaround 1: Ask by Individual Board ✅
```
"How many tasks in Board 1?"
"How many tasks in Software Project?"
"How many tasks in Bug Tracking?"
```
→ Then sum them manually

### Workaround 2: Ask for Specific Status ✅
```
"How many completed tasks in this board?" (when board is selected)
"Show me overdue tasks" (requires board context)
```

### Workaround 3: Ask with Board Context ✅
```
Select a board first in UI
Then ask: "How many tasks?"
Then select another board and ask again
```

---

## Solutions to Enable This Feature

### Solution 1: Add Query Builder (RECOMMENDED)
**Enables aggregation without full context dump**

```python
def _handle_aggregate_query(self, prompt):
    """Detect and handle aggregate queries"""
    
    aggregate_keywords = ['total', 'all boards', 'across', 'sum', 'count all']
    
    if any(kw in prompt.lower() for kw in aggregate_keywords):
        # Execute query directly
        total_tasks = Task.objects.count()
        tasks_by_status = Task.objects.values('column__name').annotate(
            count=Count('id')
        )
        
        context = f"""
**System-Wide Task Summary:**
- Total Tasks: {total_tasks}
- By Status: {tasks_by_status}
- Boards: {Board.objects.count()}
"""
        return context
    return None
```

**Effort:** Low (2-3 hours)  
**Impact:** High - Enables system-wide queries

---

### Solution 2: Implement RAG for Project Analytics
**Uses search-like approach for large datasets**

```python
def get_analytics_context(self, prompt):
    """Build analytics context from aggregated data"""
    
    # Pre-computed aggregates
    analytics = AIAssistantAnalytics.objects.filter(
        user=self.user,
        date=timezone.now().date()
    ).first()
    
    # Provide high-level stats without dumping all data
    return f"""
**Analytics Summary:**
- Messages sent: {analytics.messages_sent}
- Total tokens: {analytics.total_tokens_used}
- Active sessions: {AIAssistantSession.objects.filter(user=self.user, is_active=True).count()}
"""
```

**Effort:** Medium (4-6 hours)  
**Impact:** Medium - Enables analytics queries

---

### Solution 3: Multi-Pass Query Processing
**Asks follow-up questions to get specific subset**

```python
def get_response(self, prompt, history=None, use_cache=True):
    """
    Multi-pass processing for complex queries
    """
    
    # If query is ambiguous/aggregate:
    if self._is_aggregate_query(prompt):
        # Step 1: AI suggests clarification
        response = {
            'response': "I can help! Which boards would you like me to check? Or should I count across all boards?",
            'needs_clarification': True,
            'boards': [b.name for b in self.get_user_boards()]
        }
        return response
    
    # Step 2: Once clarified, get specific data
    ...
```

**Effort:** Medium (6-8 hours)  
**Impact:** Low-Medium - Better UX but more steps

---

## Recommended Quick Fix

### Enable Aggregate Query Support

**File:** `c:\Users\Avishek Paul\PrizmAI\ai_assistant\utils\chatbot_service.py`

Add this method:

```python
def _get_aggregate_context(self, prompt):
    """
    Get system-wide aggregate data for queries like:
    - "How many tasks in all boards?"
    - "Total tasks?"
    - "Task count across all projects?"
    """
    try:
        # Check if this is an aggregate query
        aggregate_keywords = [
            'total', 'all boards', 'across all', 'all projects',
            'sum', 'count all', 'how many tasks'
        ]
        
        if not any(kw in prompt.lower() for kw in aggregate_keywords):
            return None
        
        # Get aggregate data
        user_boards = Board.objects.filter(
            Q(created_by=self.user) | Q(members=self.user)
        ).distinct()
        
        total_tasks = Task.objects.filter(
            column__board__in=user_boards
        ).count()
        
        tasks_by_status = Task.objects.filter(
            column__board__in=user_boards
        ).values('column__name').annotate(
            count=Count('id')
        ).order_by('column__name')
        
        # Build context
        context = f"""**System-Wide Task Analytics (All Projects):**

- **Total Tasks:** {total_tasks}
- **Total Boards:** {user_boards.count()}

**Tasks by Status:**
"""
        for status in tasks_by_status:
            context += f"  - {status['column__name']}: {status['count']}\n"
        
        context += f"\n**Boards:** {', '.join([b.name for b in user_boards])}\n"
        
        return context
    
    except Exception as e:
        logger.error(f"Error getting aggregate context: {e}")
        return None
```

Then modify `get_response()`:

```python
def get_response(self, prompt, history=None, use_cache=True):
    try:
        # Check for aggregate queries FIRST
        aggregate_context = self._get_aggregate_context(prompt)
        if aggregate_context:
            context_parts.append(aggregate_context)
            is_project_query = True
        
        # ... rest of existing code ...
```

**Time to implement:** 30 minutes  
**Impact:** Solves your reported issue immediately

---

## Testing the Fix

```python
# Test case
prompt = "How many total tasks are in all the boards?"

# Before fix:
# Response: "I can only see board names..."

# After fix:
# Response: "Based on my analysis, you have X total tasks:
#            - Todo: Y
#            - In Progress: Z
#            - Done: W
#            across 5 boards"
```

---

## Current vs. Proposed Architecture

### Current (Limited)
```
Query → Detect type → Provide single-board context → AI responds
```

### Proposed (Full)
```
Query → Detect type → Check aggregate keywords
         ├─ Aggregate? → Provide system-wide stats
         ├─ Single board? → Provide board context
         ├─ General? → Provide general knowledge
         └─ Web query? → Provide web search + context
         → AI responds
```

---

## Summary

| Capability | Current | How to Enable |
|-----------|---------|---------------|
| Single board queries | ✅ Works | Already implemented |
| All boards aggregate | ❌ Doesn't work | Implement `_get_aggregate_context()` |
| Task recommendations | ✅ Works | Already implemented |
| System analytics | ⚠️ Partial | Add analytics context builder |
| Web searches | ✅ Works | Already implemented (if enabled) |
| Cross-board comparisons | ❌ Doesn't work | Implement multi-board context |

---

## Next Steps

1. **Immediate (5 min):** Review `_get_aggregate_context()` code above
2. **Short-term (30 min):** Implement the fix in `chatbot_service.py`
3. **Medium-term (2 hours):** Add test cases for aggregate queries
4. **Long-term (4-6 hours):** Implement full analytics context builder

The AI assistant is well-designed for focused conversations, but needs this one enhancement to handle system-wide queries like yours.

