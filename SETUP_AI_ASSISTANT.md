# AI Project Assistant Setup & Configuration

## Environment Variables Required

Add these to your `.env` file:

```bash
# ============================================
# AI MODEL API KEYS
# ============================================

# Google Gemini API
# Get from: https://aistudio.google.com
GEMINI_API_KEY=your_google_gemini_api_key_here

# OpenAI API (optional)
# Get from: https://platform.openai.com/account/api-keys
OPENAI_API_KEY=your_openai_api_key_here

# ============================================
# GOOGLE CUSTOM SEARCH (RAG - Optional)
# ============================================

# Get from: https://console.cloud.google.com
GOOGLE_SEARCH_API_KEY=your_google_search_api_key_here

# Get from: https://programmablesearchengine.google.com
GOOGLE_SEARCH_ENGINE_ID=your_custom_search_engine_id_here

# Enable/disable web search
ENABLE_WEB_SEARCH=True

# ============================================
# LOGGING
# ============================================
LOG_LEVEL=INFO
```

## Step-by-Step Setup

### 1. Install Dependencies

The required packages are already in `requirements.txt`:
- `google-generativeai` - For Gemini API
- `openai` - For OpenAI API
- `requests` - For Google Search

If not installed:
```bash
pip install google-generativeai openai requests
```

### 2. Create Database Tables

```bash
python manage.py migrate ai_assistant
```

### 3. Get API Keys

#### Google Gemini (Recommended - Free)

1. Visit [Google AI Studio](https://aistudio.google.com)
2. Click "Get API Key"
3. Create new API key
4. Add to `.env`: `GEMINI_API_KEY=your_key`

**Free tier**: Unlimited requests (with rate limiting)

#### OpenAI (Optional - Paid)

1. Go to [OpenAI API](https://platform.openai.com)
2. Sign in with your account
3. Navigate to API keys
4. Create new secret key
5. Add to `.env`: `OPENAI_API_KEY=your_key`

**Pricing**: $0.15 per 1M input tokens, $0.60 per 1M output tokens

#### Google Custom Search (Optional - for RAG)

1. Create Custom Search Engine:
   - Go to [Programmable Search Engine](https://programmablesearchengine.google.com)
   - Click "Create"
   - Configure to search "Entire web"
   - Save and note your "Search Engine ID"

2. Enable Custom Search API:
   - Go to [Google Cloud Console](https://console.cloud.google.com)
   - Create new project or select existing
   - Search for "Custom Search API"
   - Click Enable

3. Create API Key:
   - Go to "Credentials"
   - Create new "API Key"
   - Copy the key

4. Add to `.env`:
```
GOOGLE_SEARCH_API_KEY=your_api_key
GOOGLE_SEARCH_ENGINE_ID=your_search_engine_id
ENABLE_WEB_SEARCH=True
```

**Pricing**: 100 free searches/day, then $5 per 1000

### 4. Test Configuration

```bash
python manage.py shell

# Test Gemini
from ai_assistant.utils.ai_clients import GeminiClient
gemini = GeminiClient()
result = gemini.get_response("Hello, test response")
print(result['content'])

# Test OpenAI (if configured)
from ai_assistant.utils.ai_clients import OpenAIClient
openai = OpenAIClient()
result = openai.get_response("Hello, test response")
print(result['content'])

# Test Google Search (if configured)
from ai_assistant.utils.google_search import GoogleSearchClient
search = GoogleSearchClient()
results = search.search("Python programming")
print(results)
```

### 5. Run Migrations & Create Superuser

```bash
python manage.py migrate
python manage.py createsuperuser
```

### 6. Start Using

1. Go to `http://localhost:8000/assistant/`
2. Login with your user account
3. Start a conversation!

## Configuration in Django Admin

Go to `/admin/` to configure:

1. **AI Assistant Sessions** - View/manage chat sessions
2. **AI Assistant Messages** - View conversation history
3. **AI Assistant Analytics** - Check usage metrics
4. **Project Knowledge Base** - Manage indexed content
5. **User Preferences** - Set per-user defaults

## Settings Reference

All settings in `kanban_board/settings.py`:

```python
# AI Model API Keys
GEMINI_API_KEY = os.getenv('GEMINI_API_KEY', '')
OPENAI_API_KEY = os.getenv('OPENAI_API_KEY', '')

# Google Custom Search (for RAG)
GOOGLE_SEARCH_API_KEY = os.getenv('GOOGLE_SEARCH_API_KEY', '')
GOOGLE_SEARCH_ENGINE_ID = os.getenv('GOOGLE_SEARCH_ENGINE_ID', '')
ENABLE_WEB_SEARCH = os.getenv('ENABLE_WEB_SEARCH', 'True').lower() == 'true'

# AI Assistant Configuration
AI_ASSISTANT_CONFIG = {
    'DEFAULT_MODEL': 'gemini',  # 'gemini' or 'openai'
    'MAX_HISTORY_LENGTH': 50,   # Max messages in context
    'RESPONSE_TIMEOUT': 30,     # Seconds
    'ENABLE_WEB_SEARCH': ENABLE_WEB_SEARCH,
    'KB_REFRESH_INTERVAL': 3600,  # 1 hour
    'CACHE_TTL': 3600,  # 1 hour
}
```

## Testing Endpoints

### Create a new session

```bash
curl -X POST http://localhost:8000/assistant/api/sessions/ \
  -H "Content-Type: application/json" \
  -H "X-CSRFToken: your_csrf_token" \
  -d '{
    "title": "Test Session",
    "description": "Testing the API"
  }'
```

### Send a message

```bash
curl -X POST http://localhost:8000/assistant/api/send-message/ \
  -H "Content-Type: application/json" \
  -H "X-CSRFToken: your_csrf_token" \
  -d '{
    "message": "What tasks do I have this week?",
    "session_id": 1,
    "model": "gemini",
    "board_id": 1
  }'
```

### Get sessions

```bash
curl http://localhost:8000/assistant/api/sessions/ \
  -H "X-CSRFToken: your_csrf_token"
```

## Logs Location

All logs are saved to:
```
PrizmAI/logs/ai_assistant.log
```

View in real-time:
```bash
tail -f logs/ai_assistant.log
```

## Troubleshooting

### Issue: "API key not configured"

**Solution**: 
- Check `.env` file exists
- Verify `GEMINI_API_KEY` is set
- Restart Django: `python manage.py runserver`

### Issue: "ModuleNotFoundError: No module named 'google'"

**Solution**:
```bash
pip install google-generativeai
```

### Issue: "Web search is not working"

**Solution**:
- Check `ENABLE_WEB_SEARCH=True` in `.env`
- Verify `GOOGLE_SEARCH_API_KEY` and `GOOGLE_SEARCH_ENGINE_ID`
- Make sure Custom Search API is enabled in Google Cloud
- Check you haven't exceeded 100 free searches/day

### Issue: "CORS/CSRF errors"

**Solution**:
- Add to `settings.py`: 
  ```python
  CSRF_TRUSTED_ORIGINS = ['http://localhost:8000']
  ```
- Ensure cookies are enabled in browser

### Issue: "Empty responses from AI"

**Solution**:
- Check API key is valid
- Verify rate limits haven't been exceeded
- Try switching models (Gemini ↔ OpenAI)
- Check logs: `tail -f logs/ai_assistant.log`

## Next Steps

1. ✅ Environment variables configured
2. ✅ Database migrations run
3. ✅ API keys added
4. ✅ Service tested
5. 👉 Customize system prompt (optional)
6. 👉 Set up knowledge base (optional)
7. 👉 Configure user permissions
8. 👉 Train team on using Assistant

## Production Deployment

### Before going live:

1. **Security**:
   ```python
   DEBUG = False
   ALLOWED_HOSTS = ['yourdomain.com']
   SECURE_SSL_REDIRECT = True
   ```

2. **Rate Limiting**: Implement per-user limits
   ```python
   RATELIMIT_ENABLE = True
   RATELIMIT_USE_CACHE = 'default'
   ```

3. **Monitoring**: Set up error tracking (Sentry, etc.)

4. **Backups**: Backup database regularly

5. **Cost Control**: Set spending limits on API keys

## Support

For issues or questions:
1. Check logs: `logs/ai_assistant.log`
2. Review guide: `AI_ASSISTANT_INTEGRATION_GUIDE.md`
3. Check Django admin for user sessions/messages
4. Reference: [Nexus 360 Project](https://github.com/paulavishek/Nexus-360)
