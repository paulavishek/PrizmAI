# Unified Knowledge AI - Quick Reference

## 🎯 What Is It?

One AI assistant that searches BOTH Wiki and Meetings data simultaneously!

**Status**: ✅ Ready to Use

---

## ⚡ Quick Start

### Access the AI Assistant

```
Main Menu → "AI Assistant" → Type your question
```

### Example Queries

**Find Documentation:**
```
"Show me the API documentation"
"What's our Python style guide?"
"Find the onboarding guide"
```

**Find Meeting Notes:**
```
"What was discussed in yesterday's standup?"
"Show action items from Q4 planning"
"What was decided about the campaign?"
```

**Combined Searches:**
```
"What are our coding best practices?"
→ Returns: Wiki pages + Related meeting decisions
```

---

## 🔍 How It Works

### Automatic Detection

AI automatically knows what you're looking for:

| Query Type | Keywords Detected | Sources Searched |
|------------|------------------|------------------|
| **Wiki** | docs, guide, reference, standards | WikiPage model |
| **Meeting** | meeting, standup, discussed, action item | MeetingNotes model |
| **Both** | Contains keywords from both | Both models |

### Search Process

```
Your Question
    ↓
AI Detects: Wiki? Meeting? Both?
    ↓
Searches Relevant Data
    ↓
Ranks by Relevance
    ↓
Returns Top Results with Context
```

---

## 📊 What You Get

### Wiki Results Include:

- 📄 Page title and category
- 👤 Author and last updated
- 🏷️ Tags
- 📝 Content excerpt (500 chars)

### Meeting Results Include:

- 🎤 Meeting title and type
- 📅 Date and duration
- 👥 Attendees
- ✅ Action items (top 3)
- 🎯 Decisions (top 3)
- 📝 Meeting summary
- 📝 Notes excerpt (300 chars)

---

## 🎨 UI/UX

### Where to Use

1. **AI Assistant Page** - Main interface
2. **While Browsing Wiki** - Ask about current page
3. **In Meeting Hub** - Search meeting history

### Natural Language

Just ask naturally:

✅ "Show me..."
✅ "What did we discuss..."
✅ "Find the..."
✅ "List action items..."

---

## 🔒 Permissions

**You Only See:**
- Wiki pages in your organization
- Meetings you attended or created
- Published pages only

---

## 💡 Pro Tips

### Get Better Results

1. **Be Specific**: "Q4 campaign meeting" vs "meeting"
2. **Use Keywords**: Include key terms from titles
3. **Ask Follow-ups**: AI maintains context

### Common Patterns

**Documentation:**
```
"Show me [topic] documentation"
"Find [team] guidelines"
"What's our [process] guide?"
```

**Meetings:**
```
"What was discussed in [meeting name]?"
"Show action items from [date/meeting]"
"List decisions from [meeting type]"
```

---

## 📦 Demo Data Available

### Wiki Pages: 8

- API Reference Guide
- Database Schema Documentation
- Python Code Style Guide
- Developer Onboarding Checklist
- Q4 2025 Campaign Strategy
- Brand Style Guide
- Sprint Planning Notes
- Team Sync Notes

### Meeting Notes: 8

- Sprint Planning Meetings (2)
- Daily Standups (2)
- Technical Design Reviews (2)
- Campaign Planning Meetings (2)

**Try asking about any of these!**

---

## 🚀 Try These Examples

### Example 1: Developer Onboarding

**Ask:** "Show me the developer onboarding guide"

**Expected:** Returns complete onboarding checklist with setup instructions

### Example 2: Meeting Action Items

**Ask:** "What action items came from the Q4 campaign meeting?"

**Expected:** Lists specific action items with assignees

### Example 3: Code Standards

**Ask:** "What are our Python coding best practices?"

**Expected:** Returns both wiki guide + meeting decisions about code standards

---

## 🔧 Technical Details

### Code Changes

**File**: `ai_assistant/utils/chatbot_service.py`

**Added**:
- `_is_wiki_query()` - Detects wiki queries
- `_is_meeting_query()` - Detects meeting queries  
- `_get_wiki_context()` - Searches wiki pages
- `_get_meeting_context()` - Searches meetings

**Total**: ~250 lines added

### Database Models Used

- `wiki.models.WikiPage` - Documentation
- `wiki.models.MeetingNotes` - Meetings

### No Breaking Changes

- All existing AI features still work
- Wiki and meeting features unchanged
- Only added new capabilities

---

## ❓ FAQ

**Q: Will this search my private wiki pages?**
A: Only published pages in your organization

**Q: Can I see meetings I didn't attend?**
A: No, only meetings you created or attended

**Q: How does relevance scoring work?**
A: Title matches (3 pts) > Tags (2 pts) > Content (1 pt)

**Q: What if no matches found?**
A: AI shows list of available pages/meetings

**Q: Does this replace the Meeting Hub AI?**
A: No, it complements it. Meeting Hub still has transcript analysis

---

## 📚 Related Docs

- `UNIFIED_KNOWLEDGE_AI_IMPLEMENTATION.md` - Full implementation details
- `AI_ASSISTANT_INTEGRATION_GUIDE.md` - Main AI assistant guide
- `MEETING_HUB_IMPLEMENTATION_SUMMARY.md` - Meeting Hub features
- `WIKI_README.md` - Wiki documentation

---

## ✅ Status

**Implementation**: ✅ Complete  
**Testing**: ✅ Verified with demo data  
**Documentation**: ✅ Complete  
**Ready for Use**: ✅ YES

---

**Quick Help**: Just ask the AI "How do I search wiki and meetings?" 😊
