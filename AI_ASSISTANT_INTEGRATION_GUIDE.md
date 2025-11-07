# PrizmAI AI Project Assistant Integration Guide

## Overview

PrizmAI AI Project Assistant is an intelligent conversational chatbot integrated into your PrizmAI project management system. It enables natural language interactions for project insights, task management, resource optimization, and risk analysis.

Built on proven technologies from the Nexus 360 chatbot project, this integration combines:
- **Dual AI Models**: Google Gemini and OpenAI GPT-4
- **RAG (Retrieval Augmented Generation)**: Google Search integration for current information
- **Project Context**: Direct access to PrizmAI data (boards, tasks, teams, etc.)
- **Smart Analytics**: Usage tracking and performance insights

## Features

### Core Capabilities

1. **Conversational Project Insights**
   - Ask about project status, timelines, and progress
   - Get summaries of team workload and capacity
   - Identify risks and blockers automatically

2. **Smart Task Management**
   - Find tasks by description, priority, assignee
   - Get prioritization recommendations
   - Identify task dependencies and conflicts

3. **Resource Optimization**
   - Analyze team member workload
   - Get skill-based assignment recommendations
   - Predict capacity issues before they occur

4. **Risk Management**
   - Automatic risk detection and assessment
   - Mitigation strategy suggestions
   - Early warning alerts

5. **Web-Enhanced Intelligence (RAG)**
   - Real-time information from web searches
   - Latest project management trends and best practices
   - Industry benchmarks and methodologies

6. **Analytics & Reporting**
   - Track AI usage patterns
   - Model performance comparison
   - Conversation insights

## Quick Start

### Prerequisites

```
Python 3.9+
Django 5.2+
Google Gemini API Key
OpenAI API Key (optional)
Google Custom Search API (optional, for RAG)
```

### Installation

1. **Add AI Assistant to INSTALLED_APPS** (already done in settings.py):
```python
INSTALLED_APPS = [
    ...
    'ai_assistant',
]
```

2. **Run Migrations**:
```bash
python manage.py makemigrations ai_assistant
python manage.py migrate ai_assistant
```

3. **Configure Environment Variables**:
Create/update `.env` file:
```
# AI Model Keys
GEMINI_API_KEY=your_google_gemini_api_key_here
OPENAI_API_KEY=your_openai_api_key_here

# Google Custom Search (for RAG)
GOOGLE_SEARCH_API_KEY=your_google_search_api_key_here
GOOGLE_SEARCH_ENGINE_ID=your_custom_search_engine_id_here
ENABLE_WEB_SEARCH=True

# Optional
LOG_LEVEL=INFO
```

4. **Access the Assistant**:
```
http://localhost:8000/assistant/
```

## API Configuration

### Google Gemini API

1. Go to [Google AI Studio](https://aistudio.google.com)
2. Create a new API key
3. Add to `.env`: `GEMINI_API_KEY=your_key`

**Features**: Fast, good for project analysis, free tier available

### OpenAI API

1. Visit [OpenAI API Platform](https://platform.openai.com)
2. Create API key in account settings
3. Add to `.env`: `OPENAI_API_KEY=your_key`

**Features**: More capable, better for complex reasoning, usage-based pricing

### Google Custom Search API (for RAG)

1. Create a [Custom Search Engine](https://programmablesearchengine.google.com)
2. Set to search "Entire web"
3. Get Search Engine ID from settings
4. Enable Custom Search API in [Google Cloud Console](https://console.cloud.google.com)
5. Create API key in Credentials
6. Add to `.env`:
```
GOOGLE_SEARCH_API_KEY=your_key
GOOGLE_SEARCH_ENGINE_ID=your_engine_id
ENABLE_WEB_SEARCH=True
```

**Features**: 100 free searches/day, then $5 per 1000 searches

## URL Routes

All AI Assistant routes are under `/assistant/`:

| URL | Purpose |
|-----|---------|
| `/assistant/` | Welcome page |
| `/assistant/chat/` | Main chat interface |
| `/assistant/chat/new/` | Create new session |
| `/assistant/api/send-message/` | Send chat message |
| `/assistant/api/sessions/` | Get user sessions |
| `/assistant/analytics/` | Analytics dashboard |
| `/assistant/recommendations/` | View task recommendations |
| `/assistant/preferences/` | User preferences |
| `/assistant/knowledge-base/` | KB management |

## Usage Examples

### Example 1: Project Status
```
User: "What's the status of our Q4 release project?"

Assistant will:
- Analyze the board "Q4 release"
- Count tasks by status
- Identify blockers
- Assess overall health
```

### Example 2: Resource Planning
```
User: "Who should we assign the API integration task to?"

Assistant will:
- Analyze team skills
- Check current workload
- Consider task complexity
- Recommend best-fit person with reasoning
```

### Example 3: Risk Detection
```
User: "Are there any risks in the payments module?"

Assistant will:
- Scan related tasks
- Identify tight deadlines
- Check task dependencies
- Flag potential blockers
- Suggest mitigation
```

### Example 4: Latest Best Practices
```
User: "What are the latest agile practices for 2025?"

Assistant will:
- Search the web for current trends
- Provide sources
- Contextualize for your project
- Suggest applicable practices
```

## Architecture

### Components

```
ai_assistant/
├── models.py              # Data models
├── views.py               # API views and responses
├── forms.py               # User preference forms
├── admin.py               # Django admin config
├── urls.py                # URL routing
├── utils/
│   ├── ai_clients.py      # Gemini & OpenAI adapters
│   ├── google_search.py   # RAG search implementation
│   └── chatbot_service.py # Main chatbot logic
└── templates/ai_assistant/
    ├── welcome.html       # Landing page
    ├── chat.html          # Chat interface
    ├── analytics.html     # Analytics dashboard
    ├── preferences.html   # Settings
    ├── recommendations.html
    └── knowledge_base.html
```

### Data Flow

```
User Input
    ↓
Views.py (API endpoint)
    ↓
ChatbotService.get_response()
    ├─→ PrizmAI Context (boards, tasks, team)
    ├─→ Knowledge Base (indexed project data)
    ├─→ Web Search (if RAG-enabled)
    └─→ AI Model (Gemini or OpenAI)
    ↓
AIAssistantMessage (saved to DB)
    ↓
Response to User
    ↓
Analytics Updated
```

### Model Switching Logic

```python
# Automatic fallback
If selected_model fails:
    Try fallback model
    Log error
    Return response
```

## Database Models

### AIAssistantSession
Represents a conversation session
- `user` - FK to User
- `board` - FK to Board (optional)
- `title` - Session name
- `is_active` - Active session flag
- `message_count` - Total messages
- `total_tokens_used` - Token tracking

### AIAssistantMessage
Individual messages in a session
- `session` - FK to AIAssistantSession
- `role` - 'user' or 'assistant'
- `content` - Message text
- `model` - Which AI model responded
- `tokens_used` - Token count
- `is_starred` - User-starred messages
- `used_web_search` - RAG flag
- `search_sources` - Web search sources used

### ProjectKnowledgeBase
Indexed project information for AI context
- `board` - FK to Board
- `content_type` - Type of content
- `title` - KB entry title
- `content` - Full content
- `summary` - AI-generated summary
- `source_task` - Related task if any

### AIAssistantAnalytics
Usage analytics per user per day
- `user` - FK to User
- `board` - FK to Board (optional)
- `date` - Analytics date
- `messages_sent` - Message count
- `gemini_requests` - Gemini usage
- `openai_requests` - OpenAI usage
- `web_searches_performed` - Search count
- `total_tokens_used` - Token total

### AITaskRecommendation
AI-generated task recommendations
- `task` - FK to Task
- `recommendation_type` - Type of recommendation
- `title` - Recommendation title
- `description` - Full description
- `confidence_score` - Confidence (0-1)
- `status` - pending/accepted/rejected/implemented

### UserPreference
User settings for AI Assistant
- `user` - OneToOne to User
- `preferred_model` - gemini or openai
- `enable_web_search` - RAG enabled
- `theme` - light/dark/auto
- Various feature toggles

## Customization

### Change Default Model

In `settings.py`:
```python
AI_ASSISTANT_CONFIG = {
    'DEFAULT_MODEL': 'openai',  # Change from 'gemini'
}
```

### Disable Web Search

In `settings.py`:
```python
ENABLE_WEB_SEARCH = False
```

Or per-user in preferences.

### Customize System Prompt

Edit `chatbot_service.py`:
```python
def generate_system_prompt(self):
    return """Your custom system prompt here..."""
```

### Adjust Response Timeout

In `settings.py`:
```python
AI_ASSISTANT_CONFIG = {
    'RESPONSE_TIMEOUT': 60,  # seconds
}
```

## Monitoring & Debugging

### Check Logs
```bash
tail -f logs/ai_assistant.log
```

### View Analytics
Navigate to: `/assistant/analytics/`

### Test API Endpoints

```bash
# Test Gemini
curl -X POST http://localhost:8000/assistant/api/send-message/ \
  -H "Content-Type: application/json" \
  -H "X-CSRFToken: your_token" \
  -d '{"message":"test","session_id":1,"model":"gemini"}'
```

### Check Database

```bash
python manage.py shell
>>> from ai_assistant.models import AIAssistantSession
>>> AIAssistantSession.objects.all()
>>> # Inspect sessions and messages
```

## Performance Tips

1. **Cache Search Results**: Enabled by default (1-hour TTL)
2. **Limit History**: Keep chat history under 50 messages
3. **Use Appropriate Model**: 
   - Gemini for quick insights (faster)
   - OpenAI for complex analysis (more capable)
4. **Monitor Token Usage**: Check analytics dashboard

## Troubleshooting

### "API key not configured"
- Check `.env` file
- Ensure `GEMINI_API_KEY` or `OPENAI_API_KEY` is set
- Restart Django server

### "Web search not working"
- Verify `GOOGLE_SEARCH_API_KEY` and `GOOGLE_SEARCH_ENGINE_ID`
- Check `ENABLE_WEB_SEARCH=True`
- Ensure you haven't exceeded 100 free searches/day

### "Empty responses"
- Check server logs: `tail -f logs/ai_assistant.log`
- Verify API keys are valid
- Try switching models

### "CSRF Token errors"
- Ensure `CSRF_TRUSTED_ORIGINS` includes your domain
- Check browser cookies are enabled

## Advanced Features

### Knowledge Base Indexing

The KB is auto-populated from:
- Project boards and descriptions
- Task descriptions and comments
- Meeting transcripts
- Documentation

To refresh:
```bash
python manage.py refresh_kb
```

### Custom Context Injection

Add custom context to queries:
```python
service = PrizmAIChatbotService(user=request.user, board=board)
# Service automatically includes board context
```

### Multi-Board Analysis

Ask about multiple boards:
```
"Compare resource allocation across all my projects"
```

The assistant analyzes all user's boards and provides cross-project insights.

## Security Considerations

1. **API Keys**: Never commit to version control
2. **User Data**: Only users see their project data
3. **Web Search**: Controlled by `ENABLE_WEB_SEARCH` setting
4. **Token Tracking**: Monitor usage for cost control
5. **Rate Limiting**: Implement per-user limits for production

## Cost Estimation

### Monthly Usage Estimate (100 users)

| Service | Requests | Cost |
|---------|----------|------|
| Gemini | 5,000 | Free |
| OpenAI | 2,000 | ~$5-10 |
| Google Search | 1,000 | $5 |
| **Total** | | **~$10-15** |

Adjust based on your actual usage patterns.

## Future Enhancements

Potential additions:
- [ ] Voice input/output
- [ ] Team collaboration mode
- [ ] Real-time alerts
- [ ] Custom AI fine-tuning
- [ ] Integration with external APIs
- [ ] Scheduled reporting

## Support & Resources

### Documentation
- [Google Gemini Docs](https://ai.google.dev/)
- [OpenAI API Docs](https://platform.openai.com/docs)
- [Google Search API](https://developers.google.com/custom-search)
- [Nexus 360 (Reference Project)](https://github.com/paulavishek/Nexus-360)

### Getting Help
1. Check logs: `logs/ai_assistant.log`
2. Review settings: `kanban_board/settings.py`
3. Test API keys independently
4. Check database models in Django admin

## License

Same as PrizmAI project.

## Changelog

### v1.0 (Initial Release)
- Core chatbot functionality
- Dual model support (Gemini + OpenAI)
- RAG with Google Search
- Session management
- Analytics dashboard
- User preferences
- Task recommendations
