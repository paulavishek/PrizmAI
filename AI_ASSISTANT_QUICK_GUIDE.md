# AI Assistant - Quick Reference Guide

## ✅ What's Been Fixed

1. **Dependency Context Bug** - Fixed error when asking about task dependencies
2. **Strategic Question Handling** - AI now properly answers "how to" questions with RAG
3. **Data Access** - Verified AI can access ALL project data (organization → tasks → subtasks)
4. **RAG Integration** - Enhanced to trigger for strategic/advice/how-to questions

---

## Sample Questions You Can Ask

### 📊 Data Retrieval Questions

**Organization & Boards:**
- "How many organizations am I part of?"
- "How many boards do I have?"
- "How many total tasks across all boards?"
- "Show me task breakdown by board"

**Task Information:**
- "Show me all tasks in [Board Name]"
- "What are the critical tasks?"
- "Show me high-risk tasks"
- "What tasks are assigned to [Name]?"
- "What tasks have dependencies?"

**Risk & Mitigation:**
- "What are the high-risk tasks?"
- "Show me mitigation strategies"
- "What tasks have risk indicators?"
- "Show critical risk items"

### 💡 Strategic Questions (Uses RAG - Web Search + Project Data)

**Risk Management:**
- "How to tackle high-risk issues in my project?"
- "What are best practices for risk mitigation?"
- "How can I reduce project risks?"
- "Advice on handling critical tasks"

**Project Management:**
- "How should I handle task dependencies?"
- "Tips for improving team productivity"
- "How to optimize resource allocation?"
- "What strategies should I use to reduce delays?"
- "How can I better manage my project?"

**Problem Solving:**
- "How to tackle [specific issue]?"
- "What should I do about [problem]?"
- "Best way to handle [situation]?"
- "Guidance on [topic]"

---

## How It Works

### Data Retrieval Questions
1. AI detects you're asking about project data
2. Retrieves relevant data from database
3. Provides specific, data-driven answer

**Example:**
```
You: "How many high-risk tasks do I have?"
AI: "You have 5 high-risk tasks:
     • Task 1 - Risk Level: CRITICAL, Score: 95/100
     • Task 2 - Risk Level: HIGH, Score: 82/100
     ..."
```

### Strategic Questions (RAG)
1. AI detects strategic/how-to question
2. Searches Google for industry best practices
3. Retrieves your specific project data
4. Combines both to give comprehensive answer

**Example:**
```
You: "How to tackle high-risk issues in my project?"
AI: "Based on industry best practices and your project data:
     
     INDUSTRY BEST PRACTICES:
     • Identify root causes using 5 Whys analysis
     • Implement risk mitigation strategies
     • [Web search results...]
     
     YOUR HIGH-RISK TASKS:
     • Task 1 (Critical): Currently has mitigation plan...
     • Task 2 (High): Recommended actions...
     
     SPECIFIC RECOMMENDATIONS:
     • [Tailored advice based on your data]"
```

---

## Tips for Best Results

1. **Be Specific**: "Show me high-risk tasks in Software Project board" is better than "Show tasks"

2. **Ask Strategic Questions Naturally**: 
   - ✅ "How to tackle this issue?"
   - ✅ "What should I do about risks?"
   - ✅ "Tips for improving productivity"

3. **Combine Data + Strategy**:
   - "Show me critical tasks" (gets data)
   - Then: "How should I tackle these?" (gets strategic advice with RAG)

4. **Use Board Context**: Select a board in the AI Assistant to get board-specific insights

---

## What Data AI Can Access

✅ Organizations (name, domain, members)  
✅ Boards (name, description, members, columns)  
✅ Tasks (all fields including risk, dependencies, progress)  
✅ Subtasks and parent tasks  
✅ Task dependencies and relationships  
✅ Risk data (scores, indicators, mitigation plans)  
✅ User profiles and skills  
✅ Comments and activities  
✅ Resource allocation data  
✅ Team capacity and workload  

---

## Troubleshooting

**Q: AI says "I don't have that information"**  
A: Try rephrasing or be more specific. Ensure you're logged in and have data in your project.

**Q: AI gives generic answers for strategic questions**  
A: Make sure web search is enabled (it is by default). Check your internet connection.

**Q: AI doesn't show my board's tasks**  
A: Select the board in the dropdown before asking. Or specify board name in question.

---

## All Improvements Are Live! ✅

You can start using the enhanced AI Assistant immediately. Try the sample questions above to see the improvements in action.
