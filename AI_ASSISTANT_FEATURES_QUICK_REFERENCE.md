# AI Assistant Features - Quick Reference

**Last Updated:** January 2025

---

## 🔗 Dependency Chain Analysis

### What It Does
Shows complete task dependency chains with bottleneck identification instead of just immediate parent.

### How to Use
```
Ask: "Show complete dependency chain for 'Task Name'"
Ask: "What's the full dependency chain for 'Create component library'?"
Ask: "Trace dependencies for 'Production deployment'"
```

### What You Get
- **Complete Chain**: All parent tasks from root to target (up to 10 levels)
- **Visual Tree**: Indented arrows showing hierarchy (└─>)
- **Task Details**: Assignee, status, progress %, risk level, due date
- **Bottleneck Score**: Identifies biggest blocker with weighted scoring
- **Recommendations**: Actionable advice to unblock chain

### Example Output
```
COMPLETE DEPENDENCY CHAIN FOR: Create component library

1. → Design System Setup (80% complete, Medium risk)
   └─> John Doe, Due: 2024-02-15

2.   └─> Define Design Tokens (40% complete, High risk, OVERDUE!)
     └─> Jane Smith, Due: 2024-02-10

3.     └─> Create Component Library ← YOU ARE HERE (0%, High risk)
       └─> Bob Johnson, Due: 2024-02-20

⚠️ BOTTLENECK: Define Design Tokens (Score: 8)
   Reasons: not completed, high risk, only 40% complete, overdue
```

### Bottleneck Scoring
- Not completed: +3 points
- High risk: +2 points
- Progress < 50%: +2 points
- Overdue: +3 points
- Blocked status: +4 points
- Unassigned: +1 point

**Higher score = bigger blocker**

---

## 🧹 Clear Chat

### What It Does
Deletes all messages in current chat session while preserving session metadata.

### How to Use
1. Click **"Clear"** button in chat toolbar (red button with eraser icon)
2. Confirm deletion in dialog
3. Messages deleted instantly

### What Happens
- ✅ All messages removed
- ✅ Session title/description preserved
- ✅ Created date preserved
- ✅ Message count reset to 0
- ✅ Token usage reset to 0
- ✅ **Cannot be undone**

### When to Use
- Start fresh conversation in same session
- Remove clutter from long chats
- Reset after testing/experimentation
- Clean up before sharing session

---

## 📥 Export Chat

### What It Does
Downloads chat conversation as file for documentation, sharing, or analysis.

### How to Use
1. Click **"Export"** dropdown button in chat toolbar
2. Select format:
   - **Export as JSON** - Machine-readable, all metadata
   - **Export as Markdown** - Human-readable, formatted document

### File Contents

#### JSON Format
```json
{
  "session": {
    "title": "Project Planning",
    "created_at": "2024-01-15T10:30:00",
    "message_count": 12,
    "total_tokens_used": 4567,
    "board": "Software Project"
  },
  "messages": [
    {
      "role": "user",
      "content": "Show my tasks",
      "created_at": "2024-01-15T10:30:15"
    },
    {
      "role": "assistant",
      "content": "I found 5 tasks...",
      "model": "gemini-2.0-flash-exp",
      "tokens_used": 456,
      "used_web_search": false
    }
  ]
}
```

**Includes**: All metadata, timestamps in ISO format, token usage, web search indicators, feedback data

#### Markdown Format
```markdown
# Project Planning

**Created:** 2024-01-15 10:30:00
**Total Messages:** 12

---

## 👤 User
*2024-01-15 10:30:15*

Show my tasks

---

## 🤖 Assistant
*2024-01-15 10:30:18*

I found 5 tasks in your projects...

---
```

**Includes**: Formatted headers, emoji icons, timestamps, web search indicators

### When to Use

**JSON Export**:
- Data analysis and processing
- Import into other tools
- Programmatic access to conversation history
- Compliance/audit logs

**Markdown Export**:
- Share with stakeholders
- Documentation for projects
- Include in reports
- Archive for future reference
- Easy reading in any text editor

---

## 🔐 Security

### Authorization
- ✅ Must be logged in
- ✅ Can only clear/export your own sessions
- ✅ CSRF protection on clear operation
- ✅ Confirmation required before clearing

### Data Protection
- ✅ No data loss on export (read-only)
- ✅ Clear is permanent but requires confirmation
- ✅ Exported files contain only your data
- ✅ Filenames include session ID and date for organization

---

## 📍 Where to Find Features

### In Chat Interface

**Location**: Top toolbar in chat view

**Buttons (left to right)**:
1. **Board Selector** - Filter by project board
2. **Export** (dropdown) - Download as JSON or Markdown
3. **Clear** (red) - Delete all messages
4. **Refresh** - Reload data

### API Endpoints

**For Developers**:
- Clear: `POST /assistant/api/sessions/{session_id}/clear/`
- Export JSON: `GET /assistant/api/sessions/{session_id}/export/?format=json`
- Export Markdown: `GET /assistant/api/sessions/{session_id}/export/?format=markdown`

---

## 💡 Tips & Best Practices

### Dependency Chain
- **Be Specific**: Mention task name in quotes for best results
- **Use Full Names**: "Show chain for 'Create component library'" works better than "show chain"
- **Follow Up**: After seeing bottleneck, ask "How can I unblock [task name]?"
- **Compare Projects**: Ask for chains across different boards to compare complexity

### Clear Chat
- **Export First**: Always export before clearing if you want to keep records
- **Use for Fresh Start**: Good for switching topics within same session
- **Alternative to Delete**: Keeps session in list but removes messages
- **Great for Testing**: Clear after experimental queries

### Export
- **JSON for Analysis**: Use JSON if you plan to process data programmatically
- **Markdown for Sharing**: Use Markdown for human readers
- **Regular Exports**: Export important planning sessions monthly
- **File Naming**: Files auto-named with session ID and date (e.g., `chat_session_42_20240115.json`)

---

## 🐛 Troubleshooting

### "No session selected" Error
**Cause**: No active chat session  
**Fix**: Create or select a session from sidebar first

### Clear Button Not Working
**Cause**: Need to confirm dialog  
**Fix**: Click "OK" in confirmation popup (or "Cancel" to abort)

### Export Downloads Empty File
**Cause**: Session has no messages  
**Fix**: Send at least one message before exporting

### Can't See Other User's Sessions
**Cause**: By design - security feature  
**Fix**: Users can only access their own sessions (working as intended)

### Dependency Chain Shows Only One Task
**Cause**: Task has no parent_task relationship  
**Fix**: Standalone tasks have no dependencies (working as intended)

---

## 🆕 What's New

### January 2025 Release

**Added**:
1. **Full Dependency Chain Traversal** - Up to 10 levels deep
2. **Bottleneck Scoring System** - 6-criteria weighted analysis
3. **Clear Chat Feature** - Remove messages, keep session
4. **Export as JSON** - Machine-readable format with all metadata
5. **Export as Markdown** - Human-readable formatted document

**Improved**:
- Dependency queries now show complete chains instead of just immediate parent
- Visual tree representation with indentation and arrows
- Overdue task detection in dependency chains
- Blocked status highlighting

---

## 📚 Related Documentation

- **Full Feature Guide**: `AI_ASSISTANT_NEW_FEATURES.md`
- **Testing Instructions**: See "Testing Instructions" section in full guide
- **API Documentation**: See "API Endpoints" in full guide
- **Security Details**: See "Security & Validation" in full guide

---

## 🎯 Quick Examples

### Example 1: Find Bottleneck
```
You: "Show complete dependency chain for 'Production deployment'"

AI: [Shows 5-task chain, identifies 'Database migration' as bottleneck 
     with score 9 due to: overdue, blocked, high risk, no assignee]

You: "How can I unblock Database migration?"

AI: [Provides specific recommendations: assign to DBA team, break into 
     smaller tasks, prioritize schema changes]
```

### Example 2: Clean and Export
```
1. Chat about project planning (20 messages)
2. Click "Export" → "Export as Markdown"
3. Save file for documentation
4. Click "Clear" → Confirm
5. Start fresh conversation in same session
```

### Example 3: Compare Dependencies
```
You: "Show dependency chain for 'Launch marketing campaign'"
[Shows chain, identifies bottleneck]

You: "Show dependency chain for 'Mobile app release'"
[Shows chain, identifies different bottleneck]

You: "Which project has more dependency risk?"
[AI compares bottleneck scores and provides analysis]
```

---

**Need Help?** Ask the AI Assistant: "How do I use the dependency chain feature?" or "How do I export my chat?"

