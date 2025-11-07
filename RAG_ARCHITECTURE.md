# RAG Architecture & Data Flow

## System Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                      PrizmAI AI Assistant                       │
│                    (Powered by RAG + Gemini)                    │
└─────────────────────────────────────────────────────────────────┘

                           User Query
                               │
                               ▼
                    ┌──────────────────────┐
                    │ Query Classifier     │
                    │ (TypeDetection)      │
                    └──────────────────────┘
                      ▲         │         ▲
                 web?  │         │ project?  │ mixed?
                      │         │         │
        ┌─────────────┴─┐  ┌────┴──────┬───┴──────┐
        │               │  │            │          │
        ▼               ▼  ▼            ▼          ▼
    ┌─────────┐  ┌─────────────┐  ┌──────────┐  ┌─────────┐
    │ Google  │  │PrizmAI DB  │  │Knowledge │  │Combined │
    │ Search  │  │ (Tasks,     │  │Base      │  │Sources  │
    │ (RAG)   │  │ Team,       │  │(KB)      │  │         │
    │         │  │ Boards)     │  │          │  │         │
    └────┬────┘  └──────┬──────┘  └────┬─────┘  └────┬────┘
         │               │              │             │
         │ (1-3s)        │ (0.5-1s)     │ (0.3s)     │
         │ Cached        │ Local DB     │ Indexed    │
         │               │              │             │
         └───────────────┴──────────────┴─────────────┘
                         │
                         ▼
              ┌─────────────────────────┐
              │ Context Synthesizer     │
              │ (Combine all sources)   │
              └────────────┬────────────┘
                           │
                           ▼
              ┌─────────────────────────┐
              │ System Prompt Builder   │
              │ (Add context to prompt) │
              └────────────┬────────────┘
                           │
                           ▼
              ┌─────────────────────────┐
              │  Gemini 2.5-Flash AI    │
              │  (Generate Response)    │
              └────────────┬────────────┘
                  (0.5-2s) │
                           ▼
              ┌─────────────────────────┐
              │ Response Formatter      │
              │ (Add sources & cite)    │
              └────────────┬────────────┘
                           │
                           ▼
                  ┌─────────────────┐
                  │ User Response   │
                  │ with Sources    │
                  └─────────────────┘
                           │
                           ▼
              ┌─────────────────────────┐
              │ Analytics Tracker       │
              │ (Log for insights)      │
              └─────────────────────────┘
```

---

## Data Flow Sequence

### Query: "What are the latest project management trends?"

```
1. INPUT
   └─ User types in chat interface
      └─ Message sent to `/assistant/api/send_message/`

2. DETECTION
   ├─ Check for web triggers: "latest" ✓, "trends" ✓
   ├─ Query type: WEB SEARCH
   └─ Also check project triggers: "project management" ✓
      └─ Type: MIXED (web + project data)

3. RETRIEVAL (Parallel)
   │
   ├─ Path A: WEB SEARCH
   │  ├─ Call: GoogleSearchClient.search("trends in PM")
   │  ├─ Check cache: Not found
   │  ├─ API call to Google (1-3s)
   │  └─ Results: [
   │      { title: "2025 PM Trends...", url: "...", snippet: "..." },
   │      { title: "Future of PM...", url: "...", snippet: "..." },
   │      { title: "AI in Project...", url: "...", snippet: "..." }
   │     ]
   │
   ├─ Path B: PROJECT DATA
   │  ├─ Query PrizmAI DB for "project management"
   │  ├─ Get team members, board info
   │  └─ Current context: Board "API Dev", 8 tasks, 3 members
   │
   └─ Path C: KNOWLEDGE BASE
      ├─ Search KB for "trends" + "project management"
      ├─ Find: "PM Best Practices 2024", "Team Efficiency Tips"
      └─ Snippets from KB

4. CONTEXT ASSEMBLY
   │
   └─ Build augmented prompt:
      """
      System prompt: You are PrizmAI AI Project Assistant...
      
      Context available:
      
      **From Web Search (Latest Information):**
      - 2025 PM Trends from TechCrunch: ...
      - Future of Project Management: ...
      - AI in Project Management: ...
      
      **From Your Project Data:**
      - Current Board: API Development (8 tasks)
      - Team: 3 members
      - Status: In Progress
      
      **From Knowledge Base:**
      - PM Best Practices: ...
      - Team Efficiency Tips: ...
      
      User Question: "What are the latest project management trends?"
      """

5. AI GENERATION
   │
   ├─ Send prompt to Gemini 2.5-Flash
   ├─ Gemini processes all context (0.5-2s)
   └─ Generate comprehensive response

6. RESPONSE FORMATTING
   │
   ├─ Format Gemini output
   ├─ Cite sources:
   │  - [Source 1] TechCrunch: https://...
   │  - [Source 2] Your Board: API Development board status
   │  - [Source 3] KB: PM Best Practices
   └─ Add confidence/metadata

7. OUTPUT
   │
   └─ Return to user:
      """
      Based on the latest industry trends and your project context:
      
      **Key 2025 PM Trends:**
      1. AI-assisted planning [From web search]
      2. Remote-first teams [From web + your context]
      3. Continuous delivery [From web + KB]
      
      **For Your Team:**
      Consider adopting... [Tailored to your project]
      
      Sources:
      - TechCrunch: 2025 PM Trends
      - Your Board: API Development Project
      - Knowledge Base: PM Best Practices
      """

8. TRACKING
   └─ Log in analytics:
      ├─ Message ID: msg_12345
      ├─ Used web search: Yes
      ├─ Tokens used: 245
      ├─ Sources cited: 3
      ├─ Processing time: 2.4s
      └─ Cached result: No
```

---

## Caching Strategy

```
Request 1: "What are best practices?"
├─ Not in cache
├─ Query Google Search (1-3s)
├─ Get results
├─ Store in Django Cache (TTL: 1 hour)
└─ Return to user

Request 2: Same question within 1 hour
├─ Check cache: FOUND
├─ Return cached results (< 0.1s)
├─ Save API quota
└─ Return to user

Request 3: Same question after 1 hour
├─ Cache expired
├─ Query Google Search again
├─ Update cache
└─ Return fresh results
```

**Benefits:**
- ✅ 99% faster for repeated queries
- ✅ Save API quota (~100x)
- ✅ Better user experience
- ✅ Team shares cache

---

## Data Source Priority

When multiple sources have info, priority order:

```
1. PROJECT DATA (Highest)
   ├─ Most relevant (your actual project)
   ├─ Always current
   └─ No API quota cost
   
2. KNOWLEDGE BASE (High)
   ├─ Your documented learnings
   ├─ Internal best practices
   └─ Always relevant

3. WEB SEARCH (Medium)
   ├─ Latest external info
   ├─ Industry standards
   ├─ API quota cost
   └─ Might be less relevant

4. AI REASONING (Lowest)
   ├─ Gemini's general knowledge
   ├─ Fallback only
   └─ No guarantees on accuracy
```

**Example - Query: "What's the project status?"**

```
├─ Project data found: "5 tasks done, 8 in progress"
├─ KB: Skip (not more relevant)
├─ Web: Skip (not applicable)
└─ Response uses: Project Data + AI synthesis
```

---

## API Calls & Quota

### Quota Consumption

```
Google Custom Search API
├─ Free tier: 100 queries/day
├─ Your caching: Reduces by ~70%
├─ Effective: ~300 user interactions/day
├─ Team sharing: Multiplies by team size

Example: 5-person team
├─ 100 API queries/day available
├─ With caching: 300 interactions/day
├─ Per person: 60 interactions/day
└─ With sharing: 300 interactions/day
```

### Cost Analysis

```
Scenario 1: Free Tier (1 team, 300 queries/day)
├─ 100 API queries/day
├─ Cost: $0/month
└─ Works for: Small teams with caching

Scenario 2: Paid Tier (growing team)
├─ $5 per 1,000 queries
├─ 10,000 queries/month = $50/month
├─ 100,000 queries/month = $500/month
└─ Scalable to any team size
```

---

## Performance Metrics

### Response Times

```
Operation              Time    Factor
────────────────────────────────────────
1. Project DB Query    0.3-0.5s   Fast (indexed)
2. KB Search           0.2-0.4s   Fast (cached)
3. Web Search (cached) < 0.1s     Very Fast
4. Web Search (new)    1-3s       Medium (API call)
5. Gemini Response     0.5-2s     Medium (AI)
6. Format & Return     0.1s       Fast

Total (cached query):  1.2-3.5s   ✅ Good
Total (new web query): 2.5-6s     ✅ Acceptable
```

### Scalability

```
Concurrent Users      Response Time   Viable?
─────────────────────────────────────────
1-10 users           1-3s             ✅ Yes
10-100 users         2-4s             ✅ Yes
100-1000 users       3-5s             ⚠️ May need optimization
1000+ users          5-10s+           ❌ Need caching layer

Solution for scale: Use Redis cache + CDN
```

---

## Security Architecture

```
┌─────────────────────────────────────────┐
│        User (Authenticated)             │
│        Django Session                   │
└────────────┬────────────────────────────┘
             │
             ▼
    ┌────────────────────┐
    │ Permission Check   │
    │ (Is user allowed?) │
    └────────┬───────────┘
             │
             ▼
    ┌────────────────────┐
    │ Filter Data        │
    │ (User's boards)    │
    └────────┬───────────┘
             │
             ▼
    ┌────────────────────┐
    │ Safe API Calls     │
    │ (No key exposure)  │
    └────────┬───────────┘
             │
             ▼
    ┌────────────────────┐
    │ Response Filter    │
    │ (Only user's data) │
    └────────────────────┘
```

**Security Features:**
- ✅ Authentication required
- ✅ Board-level filtering
- ✅ API keys server-side only
- ✅ HTTPS only (production)
- ✅ Rate limiting per user
- ✅ Audit logging

---

## Database Schema (Related to RAG)

```
User
├─ AIAssistantSession (1:N)
│  └─ AIAssistantMessage (1:N)
│     └─ used_web_search: Boolean
│
├─ AIAssistantAnalytics (1:N)
│  └─ web_searches_performed: Integer
│
├─ ProjectKnowledgeBase (1:N)
│  ├─ title
│  ├─ content
│  └─ is_active
│
└─ UserPreference (1:1)
   └─ enable_web_search: Boolean
```

---

## Configuration Hierarchy

```
Environment (.env file - HIGHEST PRIORITY)
├─ GOOGLE_SEARCH_API_KEY
├─ GOOGLE_SEARCH_ENGINE_ID
└─ ENABLE_WEB_SEARCH

       ↓ (override by)

Settings (kanban_board/settings.py)
├─ Load from environment
├─ Default fallback values
└─ Cache configuration

       ↓ (used by)

Runtime (utils/google_search.py, chatbot_service.py)
├─ GoogleSearchClient()
├─ PrizmAIChatbotService()
└─ GeminiClient()
```

---

## Error Handling Flow

```
Request comes in
    │
    ▼
Try to process
    │
    ├─ Success ──────────────► Return response
    │
    └─ Error occurred
        ├─ API key missing
        │  └─ Log warning
        │  └─ Use project data only
        │  └─ Return response without web search
        │
        ├─ Google API rate limited
        │  └─ Log warning
        │  └─ Return cached result if available
        │  └─ Else use project data
        │
        ├─ Gemini error
        │  └─ Log error
        │  └─ Return graceful error message
        │
        └─ Other error
           └─ Log error
           └─ Return "Try again later"
```

---

## Monitoring Points

```
Production Monitoring Checklist:
│
├─ API Quota Usage
│  └─ Track daily queries against 100-query limit
│
├─ Cache Hit Rate
│  └─ Monitor % of cached vs fresh results
│
├─ Response Times
│  └─ Track p50, p95, p99 latencies
│
├─ Error Rates
│  └─ Google API failures, Gemini errors
│
├─ User Queries
│  └─ Track what users ask about
│
└─ Data Quality
   └─ Are responses accurate?
   └─ Are sources correct?
   └─ Is context relevant?
```

---

## Summary

Your RAG system:
- ✅ Retrieves from 3 sources (Project, KB, Web)
- ✅ Intelligently detects query type
- ✅ Caches results (1 hour)
- ✅ Formats responses with sources
- ✅ Tracks analytics
- ✅ Handles errors gracefully
- ✅ Stays within API quotas
- ✅ Maintains security

**Total processing time: 1-6 seconds**
**User experience: Lightning fast with context**
