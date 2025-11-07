# RAG Integration - Quick Setup Summary

## Current Status

✅ **RAG is already fully integrated in your code!**

Your chatbot has three retrieval sources:
1. **Project Data** - Tasks, team, boards from PrizmAI
2. **Knowledge Base** - Documented insights
3. **Web Search** - Latest information via Google Custom Search (needs API key)

---

## What You Need to Do

### Get 2 Keys from Google

**Key 1: Google Search API Key**
- Go: https://console.cloud.google.com/apis/credentials
- Create API Key
- Copy it

**Key 2: Custom Search Engine ID**
- Go: https://programmablesearchengine.google.com/
- Create new search engine
- Copy the "Search Engine ID" (cx value)

### Update Your `.env` File

Add these lines (already added as placeholders):

```env
GOOGLE_SEARCH_API_KEY=your_key_here
GOOGLE_SEARCH_ENGINE_ID=your_cx_here
ENABLE_WEB_SEARCH=True
```

### Test It

Start server:
```bash
python manage.py runserver
```

Go to: http://localhost:8000/assistant/chat/

Try a web search query like:
```
"What are the latest project management trends?"
```

If it works, you'll see sources cited in the response!

---

## How It Works

**Query → AI Detects Type → Retrieves Context → Generates Response**

```
"latest frameworks" 
  → Detected as WEB query
    → Google Search retrieves results
      → Injected into Gemini prompt
        → Response with sources
```

vs.

```
"What tasks are assigned to me?"
  → Detected as PROJECT query
    → Project data retrieved
      → Injected into Gemini prompt
        → Response with task info
```

---

## Files Already Set Up

| File | Purpose | Status |
|------|---------|--------|
| `ai_assistant/utils/google_search.py` | Google Search client | ✅ Ready |
| `ai_assistant/utils/chatbot_service.py` | RAG orchestration | ✅ Ready |
| `kanban_board/settings.py` | Configuration | ✅ Ready |
| `.env` | API credentials | 🔧 Needs keys |

---

## Pricing

**Google Custom Search API:**
- Free: 100 queries/day
- Paid: $5 per 1,000 queries (after free tier)

Your system has **1-hour caching** to minimize quota usage.

---

## For Full Details

See: `RAG_SETUP_GUIDE.md` (comprehensive guide with troubleshooting)

---

## Quick Troubleshooting

| Issue | Solution |
|-------|----------|
| Web search not working | Check API keys in `.env` |
| "API quota exceeded" | Upgrade plan or use caching |
| Need specific domains only | Edit search engine at programmablesearchengine.google.com |
| Want to disable web search | Set `ENABLE_WEB_SEARCH=False` in `.env` |

---

✅ **That's it! You're ready to go.**

Get your API keys and update `.env` - everything else is already working!
