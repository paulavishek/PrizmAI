# RAG Examples - Chatbot Query Patterns

Your AI chatbot automatically uses RAG (Retrieval Augmented Generation) to combine multiple data sources. Here are real examples:

---

## Example 1: Web Search Query (Latest Trends)

**User Input:**
```
"What are the latest best practices in agile project management for 2025?"
```

**System Processing:**
```
✓ Detected: WEB SEARCH QUERY (contains "latest", "2025", "best practices")
✓ Retrieved: Google Search results for agile best practices
✓ Retrieved: Project knowledge base entries about agile
✓ Context injected into Gemini
✓ Generated response with sources
```

**Response:**
```
Agile project management in 2025 emphasizes:

1. **AI-Assisted Planning** - Teams use AI for sprint forecasting
   [Source 1] From recent article on TechCrunch

2. **Remote-First Ceremonies** - Adapted for distributed teams
   [Source 2] From Scrum Alliance 2025 guidelines

3. **Continuous Value Delivery** - Shorter cycles, faster feedback
   [Source 3] From Atlassian whitepaper

[Full sources with URLs are displayed]
```

---

## Example 2: Project Data Query

**User Input:**
```
"Which team members have the most tasks assigned?"
```

**System Processing:**
```
✓ Detected: PROJECT QUERY (contains "team members", "tasks")
✓ Retrieved: Task data from your board
✓ Retrieved: Assigned tasks by team member
✗ Skipped: Web search (not needed for project data)
✓ Generated response with current project status
```

**Response:**
```
Based on your current board data:

1. **Alice Johnson** - 8 tasks assigned
   - 3 In Progress
   - 5 Not Started
   - Workload: MODERATE

2. **Bob Smith** - 12 tasks assigned
   - 5 In Progress
   - 7 Not Started
   - Workload: HIGH (Consider redistribution)

3. **Carol Williams** - 5 tasks assigned
   - 2 Completed
   - 2 In Progress
   - 1 Not Started
   - Workload: LOW (Can take more work)

Recommendation: Move 2 tasks from Bob to Carol for better load balancing.
```

---

## Example 3: Mixed Query (Project + Knowledge Base)

**User Input:**
```
"What risks should we watch out for in our current project based on industry practices?"
```

**System Processing:**
```
✓ Detected: PROJECT + WEB QUERY
✓ Retrieved: Your board's current project data
✓ Retrieved: Risk-related entries from knowledge base
✓ Retrieved: Industry risk management guidelines (web)
✓ Synthesized all sources
```

**Response:**
```
Based on your project data + industry practices:

**Immediate Risks (Your Project):**
- Task dependencies between Frontend and Backend not documented
  Industry tip: Use dependency graphs
  
- 3 team members on vacation next week with 5 pending tasks
  Industry standard: Maintain 20% buffer capacity

**Industry Best Practices for Risk Management:**
- Implement risk registers (from PMI standards)
- Weekly risk review meetings
- Automated dependency tracking

[Sources included from web search + KB]
```

---

## Example 4: Tool/Framework Query (Web + RAG)

**User Input:**
```
"What's the best project management tool stack for 2025 for distributed teams?"
```

**System Processing:**
```
✓ Detected: WEB SEARCH QUERY + GENERAL KNOWLEDGE
✓ Retrieved: Latest tool comparisons from web
✓ Retrieved: Your team's historical tool usage notes
✓ Retrieved: Industry benchmarks
✓ Generated comparison response
```

**Response:**
```
Top Project Management Tool Stacks for 2025 (Distributed Teams):

**Popular Combination 1: Asana + Slack + GitHub**
- Pros: Great integration, AI features, real-time collaboration
- Cons: Higher pricing tier
- Industry adoption: 45% of distributed teams

**Popular Combination 2: Monday.com + Microsoft Teams**
- Pros: Familiar UI, MS ecosystem integration
- Cons: Mobile app less powerful than desktop
- Industry adoption: 35% of enterprises

**For Your Context (based on KB):**
PrizmAI is strong for kanban boards. Consider:
- PrizmAI (you have this!) + Slack integration
- Add: Google Docs for documentation
- Add: GitHub for code integration

[Sources with links, analyst reports, user reviews]
```

---

## Example 5: Technical Deep Dive (Knowledge Base Primary)

**User Input:**
```
"How does our CI/CD pipeline handle deployment failures?"
```

**System Processing:**
```
✓ Detected: PROJECT/KB QUERY
✓ Retrieved: CI/CD documentation from knowledge base
✗ Skipped: Web search (internal process, not needed)
✓ Found: Detailed procedures from your KB
```

**Response:**
```
Based on your documented procedures:

**Deployment Failure Handling:**

1. **Automated Rollback** (< 2 minutes)
   - Pipeline detects health check failure
   - Automatically reverts to last known good
   - Team alerted via Slack

2. **Manual Investigation** (5-15 minutes)
   - DevOps team reviews logs
   - Root cause analysis
   - Documentation in incident tracker

3. **Communication Protocol**
   - Stakeholders notified immediately
   - Hourly updates during resolution
   - Incident review meeting within 24 hours

[Linked to actual KB docs]
```

---

## Query Types Summary

### 🌐 Web Search Triggers
These queries use Google Search + RAG:
- "What are the latest..."
- "Tell me about [new topic]"
- "Best practices for..."
- "Compare [tool] vs [tool]"
- "Industry standards for..."
- Anything mentioning current year or "2025"

### 📊 Project Data Triggers
These queries use PrizmAI data + KB:
- "What tasks..."
- "Which team members..."
- "What's the status..."
- "Are we on schedule..."
- "Show me [board name]"
- "Who is assigned..."

### 🔍 Mixed Triggers
These combine all sources:
- "What risks should we worry about?"
- "How do we compare to industry?"
- "What's our team's capacity?"
- "Recommend next steps..."

---

## Response Sources Displayed

When your chatbot uses RAG, it includes sources:

```
**From Project Data:**
- Found 5 tasks assigned to Alice in Q1

**From Knowledge Base:**
- Referenced your documented risk framework

**From Web Search:**
- [Source 1] Industry article from TechCrunch
  URL: https://techcrunch.com/...
  
- [Source 2] Best practices from PMI
  URL: https://pmi.org/...
```

---

## Tips for Better RAG Results

### ✅ DO:
- Ask specific questions
- Include timeframe if relevant ("this quarter", "2025")
- Ask about industry standards when applicable
- Let system auto-detect query type

### ❌ DON'T:
- Oversimplify: "help me" (be specific)
- Assume old data: Ask for "recent" or "current"
- Combine too many topics in one query
- Ask the same question repeatedly (use caching)

---

## Pricing Reminder

**Google Custom Search API:**
- Free: 100 queries/day
- Beyond 100: $5 per 1,000 queries

Your system caches results for 1 hour, so:
- Repeated questions don't count
- Team-wide queries share cache
- Database of queries built over time

---

## Performance

Expected response times:

| Query Type | Time | Notes |
|-----------|------|-------|
| Project data | 0.5-1s | Fast, local database |
| KB search | 0.3-0.8s | Database indexed |
| Web search | 1-3s | Network + cache depends |
| Mixed | 2-4s | All sources combined |

Gemini response generation: +0.5-2s depending on complexity

---

## Advanced: Custom Context

Want to add more context to a query?

```
"Given that Alice is overloaded with 12 tasks, 
what can we do based on industry best practices 
for workload distribution?"
```

This query:
✓ Provides specific context (Alice, 12 tasks)
✓ Triggers project data retrieval
✓ Triggers web search (industry best practices)
✓ Combines for comprehensive response

---

## Troubleshooting Common Scenarios

### "I asked about my project but got generic info"
**Solution:** Be more specific
- ❌ "Tell me about our project"
- ✅ "Show me all tasks in the 'API Development' board"

### "Web search didn't trigger"
**Solution:** Use web search trigger keywords
- ✅ Add "latest", "2025", "trend", "best practices"
- ✅ Check ENABLE_WEB_SEARCH=True in .env

### "Response is too general"
**Solution:** Add context
- ❌ "What about our risks?"
- ✅ "Considering our team is 50% remote and has 5 pending tasks, what risks should we watch?"

---

## Next Steps

1. ✅ Set up Google Search API (see RAG_SETUP_GUIDE.md)
2. 🔄 Test with these query examples
3. 📊 Monitor usage in analytics dashboard
4. 💡 Build knowledge base with your learnings
5. 🚀 Share with team and gather feedback

---

**Ready to use RAG?** Start chatting at `/assistant/chat/`!
