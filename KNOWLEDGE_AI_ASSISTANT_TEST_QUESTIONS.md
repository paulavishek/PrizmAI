# Knowledge AI Assistant - Comprehensive Test Questions

This guide contains structured test questions to thoroughly evaluate the Knowledge AI Assistant capabilities across all major feature areas.

---

## 📊 Category 1: Project Data Queries

Test the AI's ability to access and analyze project management data.

### 1.1 Task Statistics & Counts
- **Q1:** "How many tasks do we have in total?"
  - *Expected:* Returns total task count across all boards with breakdown by status
  
- **Q2:** "What's the status of all our projects?"
  - *Expected:* Provides summary of all boards with task counts, active team members
  
- **Q3:** "Show me tasks by priority across all boards"
  - *Expected:* Lists tasks grouped by high/medium/low priority
  
- **Q4:** "How many tasks are in each board?"
  - *Expected:* Shows task distribution per board with names

### 1.2 Board-Specific Queries
- **Q5:** "What tasks are in the [Board Name] board?"
  - *Expected:* Lists all tasks for that specific board
  
- **Q6:** "Give me a summary of [Board Name]"
  - *Expected:* Overview of board status, team, key metrics
  
- **Q7:** "What's overdue in [Board Name]?"
  - *Expected:* Shows overdue tasks with due dates

### 1.3 User & Assignment Queries
- **Q8:** "What tasks are assigned to me?"
  - *Expected:* Lists your personal task assignments
  
- **Q9:** "Who has the most tasks assigned?"
  - *Expected:* Shows team member workload distribution
  
- **Q10:** "Which team members are available?"
  - *Expected:* Shows workload status for all team members

### 1.4 Progress & Completion
- **Q11:** "What's our overall project progress?"
  - *Expected:* Percentage completed, velocity metrics, trending
  
- **Q12:** "Which tasks are completed recently?"
  - *Expected:* Shows recently finished tasks with completion dates
  
- **Q13:** "What tasks are in progress?"
  - *Expected:* Lists all tasks currently being worked on

---

## 🎯 Category 2: Strategic & Planning Queries

Test AI's ability to provide insights and recommendations.

### 2.1 Resource Planning
- **Q14:** "What's our team capacity?"
  - *Expected:* Shows available capacity vs. assigned work
  
- **Q15:** "Who should we assign to [Task Name]?"
  - *Expected:* Suggests best team member based on skills/workload
  
- **Q16:** "Are we over capacity?"
  - *Expected:* Identifies workload issues and bottlenecks

### 2.2 Risk & Mitigation
- **Q17:** "What risks do we have?"
  - *Expected:* Identifies high-risk tasks, delays, blockers
  
- **Q18:** "Which tasks might fail?"
  - *Expected:* Flags tasks with risk indicators
  
- **Q19:** "What's the mitigation strategy for [Task Name]?"
  - *Expected:* Provides risk response strategies

### 2.3 Dependency & Blocking
- **Q20:** "What tasks are blocking our progress?"
  - *Expected:* Shows blockers and dependencies
  
- **Q21:** "Which tasks have dependencies?"
  - *Expected:* Lists dependent tasks and their prerequisites
  
- **Q22:** "What's the critical path?"
  - *Expected:* Shows sequence of critical tasks

### 2.4 Project Recommendations
- **Q23:** "What should we focus on next?"
  - *Expected:* Prioritizes next steps based on project status
  
- **Q24:** "How can we improve team efficiency?"
  - *Expected:* Provides actionable recommendations
  
- **Q25:** "What's the best sprint plan?"
  - *Expected:* Suggests sprint composition and timeline

---

## 📚 Category 3: Wiki & Documentation Queries

Test the AI's ability to search and reference wiki documentation.

### 3.1 Documentation Search
- **Q26:** "Show me the API documentation"
  - *Expected:* Retrieves and references API wiki page with excerpt
  
- **Q27:** "What are our coding standards?"
  - *Expected:* Cites specific wiki page on code standards
  
- **Q28:** "Find documentation about [topic]"
  - *Expected:* Searches wiki and returns matching pages

### 3.2 Knowledge Base Retrieval
- **Q29:** "What best practices do we document?"
  - *Expected:* Lists documented best practices with sources
  
- **Q30:** "Show me the project setup guide"
  - *Expected:* Retrieves setup documentation with step-by-step info
  
- **Q31:** "Do we have documentation on [specific topic]?"
  - *Expected:* Confirms existence and provides excerpt

### 3.3 Quick Info Requests
- **Q32:** "What's our technology stack?"
  - *Expected:* References tech stack documentation
  
- **Q33:** "How do we deploy?"
  - *Expected:* References deployment procedures
  
- **Q34:** "What's our testing strategy?"
  - *Expected:* Cites testing documentation and guidelines

---

## 🎤 Category 4: Meeting & Discussions Queries

Test AI's ability to reference meeting notes and discussions.

### 4.1 Meeting Information
- **Q35:** "What was decided in our last meeting?"
  - *Expected:* Summarizes recent meeting decisions
  
- **Q36:** "What action items came from the [Meeting Name]?"
  - *Expected:* Lists action items with owners and dates
  
- **Q37:** "Show me meeting minutes from [Date]"
  - *Expected:* Retrieves specific meeting discussion notes

### 4.2 Discussion Topics
- **Q38:** "What did we discuss about [Topic]?"
  - *Expected:* Searches meetings for topic discussion
  
- **Q39:** "Who was assigned what in the last meeting?"
  - *Expected:* Shows meeting action items and assignments
  
- **Q40:** "What's our decision on [Issue]?"
  - *Expected:* References decision documented in meetings

### 4.3 Combined Wiki & Meeting Queries
- **Q41:** "How do our meeting decisions align with our documentation?"
  - *Expected:* Compares recent decisions with documented standards
  
- **Q42:** "Show me documentation about [topic] and what we discussed"
  - *Expected:* Combines wiki + meeting context

---

## 🌐 Category 5: Web Search & External Intelligence

Test RAG (Retrieval-Augmented Generation) with web search capabilities.

### 5.1 Industry Best Practices
- **Q43:** "What are the latest agile best practices?"
  - *Expected:* Web search results with current trends + sources
  
- **Q44:** "Show me current JavaScript best practices"
  - *Expected:* References external sources + frameworks
  
- **Q45:** "What's the recommended approach for [Industry Topic]?"
  - *Expected:* Combines web research with current standards

### 5.2 Technology & Tools
- **Q46:** "What's new in [Framework/Library] v[version]?"
  - *Expected:* Latest features/changes from web search
  
- **Q47:** "How should we implement [Technical Solution]?"
  - *Expected:* Combines best practices with web resources
  
- **Q48:** "What's the state of [Technology] in 2024?"
  - *Expected:* Current market analysis and trends

### 5.3 Problem Solving
- **Q49:** "How do we fix [Common Error]?"
  - *Expected:* Provides solutions with external references
  
- **Q50:** "What's the best tool for [Use Case]?"
  - *Expected:* Compares options with current information

---

## 🧠 Category 6: Complex/Multi-Context Queries

Test AI's ability to handle sophisticated requests.

### 6.1 Multi-Board Analysis
- **Q51:** "Compare task distribution across all boards"
  - *Expected:* Side-by-side analysis of multiple boards
  
- **Q52:** "Which board is most productive?"
  - *Expected:* Metrics comparing completion rates, velocity
  
- **Q53:** "Show me resource allocation across projects"
  - *Expected:* Shows how people are distributed

### 6.2 Trend Analysis
- **Q54:** "What's our velocity trend?"
  - *Expected:* Shows completion rates over time
  
- **Q55:** "Are we improving?"
  - *Expected:* Analyzes historical trends
  
- **Q56:** "When will we finish [Project]?"
  - *Expected:* Estimates based on velocity

### 6.3 Strategic Insights
- **Q57:** "What's our biggest bottleneck?"
  - *Expected:* Identifies key constraint limiting progress
  
- **Q58:** "How healthy is the project?"
  - *Expected:* Overall health assessment with key metrics
  
- **Q59:** "What do we need to change?"
  - *Expected:* Recommends improvements based on analysis

---

## ✅ Category 7: Accuracy & Reliability Tests

Test AI's factual accuracy and error handling.

### 7.1 Data Accuracy
- **Q60:** "List all tasks on [Board] with their status"
  - *Expected:* Accurate task listing matching actual board
  
- **Q61:** "Who is assigned [Specific Task]?"
  - *Expected:* Correct assignment information
  
- **Q62:** "What's the deadline for [Task]?"
  - *Expected:* Accurate due date information

### 7.2 Context Awareness
- **Q63:** "What team am I on?"
  - *Expected:* Correctly identifies user's team/board
  
- **Q64:** "What are my responsibilities?"
  - *Expected:* References your assignments and role
  
- **Q65:** "Show my personal dashboard"
  - *Expected:* User-specific information

### 7.3 Error Handling
- **Q66:** "Tell me about [Non-existent Task]"
  - *Expected:* Politely indicates task doesn't exist
  
- **Q67:** "Show me [Typo'd Board Name]"
  - *Expected:* Suggests correct names or asks for clarification
  
- **Q68:** "What about [Ambiguous Reference]?"
  - *Expected:* Asks for clarification or lists options

---

## 🎯 Category 8: Natural Language & Intent Recognition

Test AI's language understanding capabilities.

### 8.1 Varied Phrasing
- **Q69:** "Give me a summary" → *Test without specifying of what*
  - *Expected:* Intelligently provides overall project summary
  
- **Q70:** "What's going on?" → *Vague query*
  - *Expected:* Provides relevant status update
  
- **Q71:** "Help!" → *Very vague*
  - *Expected:* Asks clarifying questions or suggests common help topics

### 8.2 Conversational Queries
- **Q72:** "How's the team doing?"
  - *Expected:* Shows team health metrics and morale indicators
  
- **Q73:** "Are we on track?"
  - *Expected:* Assesses project timeline vs. progress
  
- **Q74:** "Anything I should know?"
  - *Expected:* Highlights critical issues/updates

### 8.3 Follow-up Conversations
- **Q75 (after Q1):** "And in [specific board]?"
  - *Expected:* Uses context to understand you mean that board
  
- **Q76 (after Q35):** "Who was assigned to that?"
  - *Expected:* References previous meeting context
  
- **Q77 (after previous queries):** "Can you elaborate?"
  - *Expected:* Provides more detail on previous response

---

## 🔧 Category 9: Response Quality Tests

Test the quality and usefulness of responses.

### 9.1 Clarity & Formatting
- **Q78:** "List team members by workload"
  - *Expected:* Clearly formatted list with specific numbers
  
- **Q79:** "Explain our project risks"
  - *Expected:* Well-structured explanation with sections
  
- **Q80:** "Give me actionable recommendations"
  - *Expected:* Numbered list with specific actions

### 9.2 Actionability
- **Q81:** "What should we do?"
  - *Expected:* Specific, actionable next steps (not vague advice)
  
- **Q82:** "How do we improve velocity?"
  - *Expected:* Concrete improvements tied to your data
  
- **Q83:** "What's the plan?"
  - *Expected:* Specific sequenced actions

### 9.3 Source Attribution
- **Q84:** "Where did you find that information?"
  - *Expected:* Can cite wiki page, meeting, or web source
  
- **Q85:** (After web search query) "What are your sources?"
  - *Expected:* Lists URLs and attribution
  
- **Q86:** (After wiki query) "Which wiki page was that?"
  - *Expected:* Cites specific page title and location

---

## 📋 Category 10: Edge Cases & Robustness

Test AI's handling of unusual situations.

### 10.1 Empty/Incomplete Data
- **Q87:** "What if we had no tasks?"
  - *Expected:* Handles gracefully with next steps suggestion
  
- **Q88:** (When no meetings exist) "Show me meeting action items"
  - *Expected:* Clearly states no meetings exist, suggests what to do
  
- **Q89:** (When no wiki pages) "Show me documentation"
  - *Expected:* Indicates no docs but offers to help create

### 10.2 Conflicting Information
- **Q90:** "Who actually has the most tasks?"
  - *Expected:* Provides definitive answer with breakdown
  
- **Q91:** "Are these dates consistent?"
  - *Expected:* Checks for date conflicts and inconsistencies
  
- **Q92:** "What's the real status?"
  - *Expected:* Reconciles any conflicting status info

### 10.3 Scope Testing
- **Q93:** "Can you help with marketing?"
  - *Expected:* Clarifies scope (project-focused) or assists if relevant
  
- **Q94:** "Tell me jokes about deadlines"
  - *Expected:* Declines or gracefully redirects to work help
  
- **Q95:** "What's unrelated information?"
  - *Expected:* Politely redirects to project-related assistance

---

## 🚀 Quick Testing Checklist

Use this checklist to rapidly test key features:

- [ ] **Data Access**: Can it retrieve accurate project data?
- [ ] **Wiki Integration**: Does it search and cite wiki pages?
- [ ] **Meeting Context**: Does it reference meeting notes?
- [ ] **Web Search**: Does it use web search for external queries?
- [ ] **Recommendations**: Does it provide actionable suggestions?
- [ ] **Multi-Board**: Can it handle queries about multiple boards?
- [ ] **Error Handling**: Does it fail gracefully on errors?
- [ ] **Context Awareness**: Does it know who you are?
- [ ] **Formatting**: Are responses clear and well-structured?
- [ ] **Source Attribution**: Does it cite information sources?
- [ ] **Follow-ups**: Does it understand conversation context?
- [ ] **Natural Language**: Does it handle varied phrasing?

---

## 📊 Scoring Rubric

For each question, score the response:

| Score | Criteria |
|-------|----------|
| 5 | Perfect answer with details, formatting, and sources |
| 4 | Correct answer with good formatting, minor detail missing |
| 3 | Correct answer but lacks detail, formatting, or context |
| 2 | Partially correct or requires clarification |
| 1 | Incorrect or unhelpful response |
| 0 | Error or refusal without justification |

**Overall Score = Total Points / (95 questions × 5)**

---

## 💡 Testing Tips

1. **Start Simple**: Begin with Category 1 questions to verify basic data access
2. **Progress to Complex**: Move to multi-context queries once basics work
3. **Test Edge Cases**: Try Q87-95 to find failure modes
4. **Check Sources**: Always verify it cites information sources
5. **Test Follow-ups**: Use multi-turn conversations to test context retention
6. **Vary Phrasing**: Ask the same question different ways
7. **Create Test Data**: Ensure you have sample tasks, wiki pages, and meetings
8. **Document Issues**: Note any incorrect responses for debugging
9. **Test Performance**: Note response times, especially for complex queries
10. **Evaluate UX**: Consider ease of use and clarity

---

## 📝 Notes

- **95 questions total** covering all major capabilities
- Questions are categorized by feature area for organized testing
- Each question includes expected behavior as a guide
- Use as starting point - adapt questions to your specific project
- Document all findings for improvement roadmap

---

**Happy Testing! 🧪**
