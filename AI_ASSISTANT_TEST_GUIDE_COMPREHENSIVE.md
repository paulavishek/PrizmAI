# AI Assistant Comprehensive Testing Guide

**Date**: November 5, 2025  
**Purpose**: Test data retrieval capabilities and RAG (Retrieval-Augmented Generation) abilities  
**Status**: Ready for Testing  

---

## 📋 Overview

This guide provides a comprehensive list of test questions to evaluate your AI assistant's:
1. **Data Retrieval Capability**: Can it fetch and accurately report project data?
2. **RAG Ability**: Can it use Retrieval-Augmented Generation to provide informed strategic advice?

The questions are organized by category and complexity level.

---

## PART 1: DATA RETRIEVAL QUESTIONS

These questions test the AI assistant's ability to fetch and report data from your TaskFlow project database (organizations, boards, tasks, teams, etc.).

### Category 1A: Organization Data Retrieval

**Expected**: AI should query Organization model and report accurate organization information

#### Beginner Level
1. **"How many organizations do I have?"**
   - ✅ Expected: Returns total count of organizations accessible to user
   - 📊 Tests: Organization data retrieval, counting functionality
   - 🎯 What it checks: Basic organization model access

2. **"List all my organizations"**
   - ✅ Expected: Returns list of all organizations with names
   - 📊 Tests: Organization enumeration, data display
   - 🎯 What it checks: Can list multiple orgs with proper formatting

3. **"Show organization details"**
   - ✅ Expected: Returns organization names, domains, member counts, board counts
   - 📊 Tests: Multiple field access (name, domain, members count, boards count)
   - 🎯 What it checks: Can access multiple organization attributes

#### Intermediate Level
4. **"Which organizations have the most boards?"**
   - ✅ Expected: Returns organization with highest board count, sorted or ranked
   - 📊 Tests: Aggregation (COUNT boards per org), sorting, ranking
   - 🎯 What it checks: Can perform aggregations and comparisons

5. **"What's the total member count across all my organizations?"**
   - ✅ Expected: Returns sum of members across all user's organizations
   - 📊 Tests: Aggregation across multiple organizations
   - 🎯 What it checks: Can sum/aggregate data across entities

6. **"Show organization created date and creator for each"**
   - ✅ Expected: Returns org name, created_at date, created_by user
   - 📊 Tests: Date fields, ForeignKey relationships (created_by)
   - 🎯 What it checks: Can access datetime and user relationship data

#### Advanced Level
7. **"Analyze organization structure: which org has most active members and which has most boards?"**
   - ✅ Expected: Returns comparative analysis of organizations with metrics
   - 📊 Tests: Complex aggregation, multiple metrics comparison
   - 🎯 What it checks: Can synthesize multiple data points into analysis

---

### Category 1B: Board Data Retrieval

**Expected**: AI should query Board model and provide accurate board-related information

#### Beginner Level
8. **"How many boards do I have?"**
   - ✅ Expected: Returns total board count
   - 📊 Tests: Board counting
   - 🎯 What it checks: Basic Board model access

9. **"List all my boards"**
   - ✅ Expected: Returns board names, organized clearly
   - 📊 Tests: Board enumeration
   - 🎯 What it checks: Can list boards with proper formatting

10. **"What are the names of my boards?"**
    - ✅ Expected: Simple list of board names
    - 📊 Tests: Board name retrieval
    - 🎯 What it checks: Can extract and display board names

#### Intermediate Level
11. **"How many tasks are in each of my boards?"**
    - ✅ Expected: Board name → task count mapping
    - 📊 Tests: Task counting per board, cross-model aggregation
    - 🎯 What it checks: Can query Task model filtered by Board

12. **"Which board has the most tasks?"**
    - ✅ Expected: Board name with highest task count
    - 📊 Tests: Aggregation and ranking across boards
    - 🎯 What it checks: Can identify maximum aggregate value

13. **"Show board members for each board I manage"**
    - ✅ Expected: For each board, list member names
    - 📊 Tests: ManyToMany relationship access (board.members)
    - 🎯 What it checks: Can access and display member lists

14. **"Which boards are associated with which organizations?"**
    - ✅ Expected: Board to Organization mapping
    - 📊 Tests: ForeignKey relationship (board.organization)
    - 🎯 What it checks: Can access organization-board relationships

#### Advanced Level
15. **"Compare boards by: number of tasks, number of team members, and recency of updates"**
    - ✅ Expected: Comparative table showing boards with multiple metrics
    - 📊 Tests: Multiple aggregations, multi-dimensional sorting
    - 🎯 What it checks: Can synthesize complex comparisons

16. **"Identify underutilized boards (few tasks, inactive members)"**
    - ✅ Expected: Boards that are inactive or have low activity
    - 📊 Tests: Complex filtering and analysis
    - 🎯 What it checks: Can identify patterns in data

---

### Category 1C: Task Data Retrieval

**Expected**: AI should retrieve and analyze task-related information accurately

#### Beginner Level
17. **"How many tasks are in my project?"**
    - ✅ Expected: Total task count across all boards
    - 📊 Tests: Task counting
    - 🎯 What it checks: Basic Task model access

18. **"Show tasks assigned to me"**
    - ✅ Expected: List of tasks where assigned_to = current user
    - 📊 Tests: Filtering by assigned_to user
    - 🎯 What it checks: Can filter tasks by assignment

19. **"List all high-priority tasks"**
    - ✅ Expected: Tasks with priority = 'urgent' or highest priority level
    - 📊 Tests: Filtering by priority field
    - 🎯 What it checks: Can filter by priority

20. **"Show incomplete tasks (not in Done column)"**
    - ✅ Expected: Tasks with column != 'Done' or status != 'completed'
    - 📊 Tests: Filtering by column/status
    - 🎯 What it checks: Can filter by task status/column

#### Intermediate Level
21. **"How many tasks are completed vs incomplete?"**
    - ✅ Expected: Breakdown of tasks by completion status with counts
    - 📊 Tests: Aggregation by status
    - 🎯 What it checks: Can group and count by status

22. **"Which tasks are blocked or have dependencies?"**
    - ✅ Expected: Tasks with risk_level='high'/'critical' or with parent_task/dependencies
    - 📊 Tests: Filtering complex task properties
    - 🎯 What it checks: Can identify dependent tasks

23. **"Show task distribution by assignee"**
    - ✅ Expected: Each team member with count of assigned tasks
    - 📊 Tests: Aggregation and grouping
    - 🎯 What it checks: Can group tasks by assigned_to

24. **"What's the average progress of all tasks?"**
    - ✅ Expected: Mean progress percentage
    - 📊 Tests: Numeric aggregation (AVG)
    - 🎯 What it checks: Can calculate statistics

25. **"Which tasks are overdue or due soon?"**
    - ✅ Expected: Tasks with due_date < today or within next 7 days
    - 📊 Tests: Date filtering and comparisons
    - 🎯 What it checks: Can compare dates with today

#### Advanced Level
26. **"Analyze task health: show tasks with multiple risk indicators"**
    - ✅ Expected: Tasks where ai_risk_score > 70 or risk_level='high'/'critical'
    - 📊 Tests: Complex filtering with OR conditions
    - 🎯 What it checks: Can identify at-risk tasks comprehensively

27. **"Create a dependency chain - show which tasks are blocking others"**
    - ✅ Expected: Visualization of task dependencies (parent-child relationships)
    - 📊 Tests: Recursive/hierarchical data access
    - 🎯 What it checks: Can traverse task relationships

28. **"Show task progress trends - what % complete are tasks on average?"**
    - ✅ Expected: Progress percentage, trend analysis
    - 📊 Tests: Statistical analysis over time
    - 🎯 What it checks: Can identify patterns and trends

---

### Category 1D: Team & Resource Data Retrieval

**Expected**: AI should retrieve team composition, skills, and resource information

#### Beginner Level
29. **"Who are the team members on each board?"**
    - ✅ Expected: For each board, list member names
    - 📊 Tests: ManyToMany relationship access
    - 🎯 What it checks: Can retrieve team composition

30. **"How many people are on my team across all boards?"**
    - ✅ Expected: Unique count of all team members
    - 📊 Tests: Unique counting across relationships
    - 🎯 What it checks: Can count unique members

31. **"Who has the most tasks assigned?"**
    - ✅ Expected: Team member with highest task count
    - 📊 Tests: Aggregation and ranking
    - 🎯 What it checks: Can identify workload distribution

#### Intermediate Level
32. **"Show workload distribution - how many tasks per team member?"**
    - ✅ Expected: Each member with their task count
    - 📊 Tests: Aggregation by person
    - 🎯 What it checks: Can analyze workload

33. **"Which team members are overloaded (too many tasks)?"**
    - ✅ Expected: Members with task count above average or > X tasks
    - 📊 Tests: Comparative analysis
    - 🎯 What it checks: Can identify bottlenecks

34. **"Show team members and their skill sets"**
    - ✅ Expected: If skills data exists, show member skills; otherwise note not available
    - 📊 Tests: Accessing user profile skills
    - 🎯 What it checks: Can access extended user attributes

#### Advanced Level
35. **"Analyze team capacity - who has capacity for more work and who's overloaded?"**
    - ✅ Expected: Matrix showing capacity analysis per member
    - 📊 Tests: Complex workload analysis
    - 🎯 What it checks: Can perform capacity planning analysis

36. **"Identify skill gaps - what skills does the team lack for critical tasks?"**
    - ✅ Expected: If skills data available, identify gaps; otherwise note limitation
    - 📊 Tests: Skill-task matching analysis
    - 🎯 What it checks: Can perform gap analysis if data available

---

### Category 1E: Risk & Status Data Retrieval

**Expected**: AI should retrieve and analyze risk information accurately

#### Beginner Level
37. **"What are my critical/high-risk tasks?"**
    - ✅ Expected: List of tasks with risk_level='critical' or 'high'
    - 📊 Tests: Filtering by risk level
    - 🎯 What it checks: Can identify high-risk tasks

38. **"How many tasks are at risk?"**
    - ✅ Expected: Count of tasks with high risk
    - 📊 Tests: Risk counting
    - 🎯 What it checks: Can quantify risk

39. **"What are the risk levels in my tasks?"**
    - ✅ Expected: Breakdown of tasks by risk level
    - 📊 Tests: Risk level distribution
    - 🎯 What it checks: Can categorize by risk

#### Intermediate Level
40. **"Show tasks with risk indicators"**
    - ✅ Expected: Tasks with risk_indicators field populated
    - 📊 Tests: Accessing JSON field data
    - 🎯 What it checks: Can access structured risk data

41. **"Which tasks have mitigation strategies in place?"**
    - ✅ Expected: Tasks with mitigation_suggestions not empty
    - 📊 Tests: Filtering JSON field
    - 🎯 What it checks: Can identify mitigated risks

42. **"What's the AI risk score distribution across tasks?"**
    - ✅ Expected: Statistics on ai_risk_score (min, max, average)
    - 📊 Tests: Statistical analysis of scores
    - 🎯 What it checks: Can analyze numeric distributions

#### Advanced Level
43. **"Perform risk assessment - identify tasks most at risk and why"**
    - ✅ Expected: High-risk tasks with their indicators and contributing factors
    - 📊 Tests: Complex risk analysis
    - 🎯 What it checks: Can synthesize risk information comprehensively

44. **"Create a risk heat map - show risks by board and severity"**
    - ✅ Expected: Matrix showing risk distribution across boards and severity levels
    - 📊 Tests: Multi-dimensional analysis
    - 🎯 What it checks: Can organize data by multiple dimensions

---

## PART 2: STRATEGIC QUESTIONS (RAG CAPABILITY)

These questions test the AI assistant's **Retrieval-Augmented Generation (RAG)** capability—its ability to combine:
- 🌐 **Web Search Results** (external knowledge, best practices, latest trends)
- 🗄️ **Knowledge Base** (your documented insights)
- 📊 **Project Data** (your specific tasks, risks, teams)

To provide strategic advice grounded in both general best practices AND your specific context.

### Category 2A: Risk Management Strategies

**Expected**: AI should combine your risk data with best practices to suggest mitigation strategies

#### Beginner Level
45. **"How should I handle high-risk tasks?"**
    - 🎯 Expected RAG flow:
      - Retrieves: Your high-risk tasks from database
      - Searches: "Risk management best practices", "How to handle project risks"
      - Combines: Your specific risks + general best practices
      - Responds: "Based on your risks (X, Y, Z) and industry best practices..."
    - 🧪 Test result pass if: Response mentions your specific tasks AND includes general risk management principles

46. **"What are mitigation strategies for my current risks?"**
    - 🎯 Expected RAG flow:
      - Retrieves: Risk data, mitigation_suggestions from your tasks
      - Searches: "Risk mitigation strategies", "How to mitigate project risks"
      - Combines: Your mitigations + industry practices
      - Responds: "Your current mitigations include... Additionally, industry best practices suggest..."
    - 🧪 Test result pass if: References your specific mitigation data + general strategies

47. **"How can I prevent the risks identified in my tasks?"**
    - 🎯 Expected RAG flow:
      - Retrieves: Risk indicators, contributing factors
      - Searches: "Risk prevention strategies", "Risk avoidance"
      - Combines: Your context + prevention best practices
    - 🧪 Test result pass if: Specific to your risks + general prevention principles

#### Intermediate Level
48. **"What's a strategic approach to tackle risks on the [Board Name] board?"**
    - 🎯 Expected RAG flow:
      - Retrieves: Risks specific to that board
      - Searches: "[Board domain]-specific risk management", "Project delivery risks"
      - Combines: Board-specific risks + relevant strategies
    - 🧪 Test result pass if: Mentions your specific board + provides targeted strategies

49. **"How should I prioritize risk mitigation given my team's capacity?"**
    - 🎯 Expected RAG flow:
      - Retrieves: Risk data + workload/capacity data
      - Searches: "Risk prioritization", "Capacity planning with risk"
      - Combines: Your constraints + prioritization frameworks
    - 🧪 Test result pass if: Acknowledges your workload + suggests prioritization approach

50. **"What are the best practices for managing dependencies and blockers?"**
    - 🎯 Expected RAG flow:
      - Retrieves: Your dependency/blocker data
      - Searches: "Dependency management best practices", "Handling blockers"
      - Combines: Your situation + industry practices
    - 🧪 Test result pass if: References your dependencies + provides frameworks

#### Advanced Level
51. **"Design a comprehensive risk management plan for my project"**
    - 🎯 Expected RAG flow:
      - Retrieves: All project data (tasks, risks, resources, timeline)
      - Searches: "Project risk management framework", "Enterprise risk management"
      - Combines: Holistic project view + comprehensive frameworks
      - Responds: Full risk management strategy tailored to your project
    - 🧪 Test result pass if: 
      - References specific risks from your project
      - Includes identification, assessment, response phases
      - Mentions resource allocation and timeline
      - Includes contingency planning

52. **"How should I adjust my risk management approach based on project stage (planning/execution/closure)?"**
    - 🎯 Expected RAG flow:
      - Retrieves: Project data, timeline, current status
      - Searches: "Risk management by project phase"
      - Combines: Your project stage + phase-appropriate strategies
    - 🧪 Test result pass if: Acknowledges project stage + recommends phase-specific approaches

53. **"Create a risk escalation and communication strategy for my stakeholders"**
    - 🎯 Expected RAG flow:
      - Retrieves: Risk data, stakeholder data (if available)
      - Searches: "Risk communication", "Stakeholder risk reporting"
      - Combines: Your risks + communication best practices
    - 🧪 Test result pass if: Includes risk communication framework + stakeholder considerations

---

### Category 2B: Strategic Project Management Questions

**Expected**: AI should provide strategic guidance combining your project data with PM best practices

#### Beginner Level
54. **"How can I improve project delivery on my boards?"**
    - 🎯 Expected RAG flow:
      - Retrieves: Board data, task progress, team info
      - Searches: "Project delivery best practices", "How to improve project performance"
      - Combines: Your metrics + improvement strategies
    - 🧪 Test result pass if: References your specific boards + provides actionable improvements

55. **"What are the best practices for team collaboration in project management?"**
    - 🎯 Expected RAG flow:
      - Retrieves: Your team structure and dynamics
      - Searches: "Team collaboration best practices", "Agile collaboration"
      - Combines: Your team setup + collaboration frameworks
    - 🧪 Test result pass if: Acknowledges your team structure + provides general best practices

56. **"How should I prioritize tasks to maximize efficiency?"**
    - 🎯 Expected RAG flow:
      - Retrieves: Task list, priorities, dependencies, resources
      - Searches: "Task prioritization frameworks", "Eisenhower matrix"
      - Combines: Your tasks + prioritization methods
    - 🧪 Test result pass if: References your tasks + explains prioritization framework

#### Intermediate Level
57. **"How can I optimize team resource allocation?"**
    - 🎯 Expected RAG flow:
      - Retrieves: Team members, workload, skills, tasks
      - Searches: "Resource optimization", "Workload balancing"
      - Combines: Your resource constraints + optimization strategies
    - 🧪 Test result pass if: Uses your workload data + provides allocation strategies

58. **"What's an effective approach to managing project dependencies?"**
    - 🎯 Expected RAG flow:
      - Retrieves: Your dependency data (task relationships)
      - Searches: "Dependency management", "Critical path analysis"
      - Combines: Your dependencies + management frameworks
    - 🧪 Test result pass if: References your task chains + explains frameworks

59. **"How should I structure my project boards for maximum clarity and efficiency?"**
    - 🎯 Expected RAG flow:
      - Retrieves: Current board structure, workflows, team size
      - Searches: "Board structure best practices", "Kanban optimization"
      - Combines: Your setup + design principles
    - 🧪 Test result pass if: Analyzes your structure + recommends improvements

#### Advanced Level
60. **"Develop a strategic roadmap for improving our project management practices"**
    - 🎯 Expected RAG flow:
      - Retrieves: Comprehensive project data, analytics, trends
      - Searches: "Project management transformation", "Agile maturity models"
      - Combines: Your current state + improvement roadmap
    - 🧪 Test result pass if: 
      - Baseline assessment of current practices
      - Specific improvement initiatives
      - Timeline and milestones
      - Resource requirements

61. **"How should we balance agility with control in our project approach?"**
    - 🎯 Expected RAG flow:
      - Retrieves: Your project structure, team size, complexity
      - Searches: "Agile vs Waterfall", "Hybrid project management"
      - Combines: Your context + framework recommendations
    - 🧪 Test result pass if: Acknowledges your project characteristics + recommends balance

---

### Category 2C: Organizational & Strategic Alignment

**Expected**: AI should provide strategic advice about organizational structure and alignment

#### Beginner Level
62. **"How should I structure my organizations and boards?"**
    - 🎯 Expected RAG flow:
      - Retrieves: Current org/board structure
      - Searches: "Organizational structure best practices", "Portfolio management"
      - Combines: Your structure + design principles
    - 🧪 Test result pass if: Analyzes your current structure + recommends organization

63. **"What are best practices for multi-team project coordination?"**
    - 🎯 Expected RAG flow:
      - Retrieves: Your organizations, boards, team structures
      - Searches: "Cross-team coordination", "Multi-team collaboration"
      - Combines: Your teams + coordination frameworks
    - 🧪 Test result pass if: References your teams + provides coordination strategies

#### Intermediate Level
64. **"How can we better align our project structure with organizational goals?"**
    - 🎯 Expected RAG flow:
      - Retrieves: Organization data, board data, task data
      - Searches: "OKR alignment", "Strategic alignment frameworks"
      - Combines: Your structure + alignment methods
    - 🧪 Test result pass if: Provides alignment recommendations specific to your structure

65. **"What's the best way to scale project management as we grow?"**
    - 🎯 Expected RAG flow:
      - Retrieves: Current org size, board complexity, team structure
      - Searches: "Scaling project management", "Portfolio management at scale"
      - Combines: Your current scale + scaling strategies
    - 🧪 Test result pass if: Acknowledges your size + provides growth-oriented recommendations

#### Advanced Level
66. **"Design a portfolio management strategy across our organizations"**
    - 🎯 Expected RAG flow:
      - Retrieves: All organizations, boards, strategic data
      - Searches: "Portfolio management frameworks", "Strategic portfolio management"
      - Combines: Your complete structure + comprehensive framework
    - 🧪 Test result pass if: 
      - Covers all your organizations
      - Includes prioritization across portfolio
      - Includes resource allocation strategy
      - Mentions risk management at portfolio level

---

### Category 2D: Process Improvement & Optimization

**Expected**: AI should suggest improvements based on your project data combined with best practices

#### Beginner Level
67. **"What are common mistakes in project management and how do I avoid them?"**
    - 🎯 Expected RAG flow:
      - Retrieves: Your project setup (to identify potential issues)
      - Searches: "Common project management mistakes"
      - Combines: General mistakes + your specific situation
    - 🧪 Test result pass if: Provides general mistakes + specific checks for your setup

68. **"How can I make project planning more effective?"**
    - 🎯 Expected RAG flow:
      - Retrieves: Your planning approach (boards, tasks, timeline)
      - Searches: "Effective project planning", "Planning best practices"
      - Combines: Your approach + improvements
    - 🧪 Test result pass if: Analyzes your planning + suggests enhancements

#### Intermediate Level
69. **"What metrics should I track to measure project success?"**
    - 🎯 Expected RAG flow:
      - Retrieves: Your project data, board complexity, team size
      - Searches: "Project success metrics", "KPIs for projects"
      - Combines: Your context + relevant metrics
    - 🧪 Test result pass if: Recommends metrics appropriate for your project type/size

70. **"How can we reduce project delays and improve on-time delivery?"**
    - 🎯 Expected RAG flow:
      - Retrieves: Task data, timeline data, past delays (if available)
      - Searches: "Reducing project delays", "On-time delivery strategies"
      - Combines: Your delivery patterns + improvement strategies
    - 🧪 Test result pass if: References your data + provides specific improvements

71. **"What's an effective communication strategy for project stakeholders?"**
    - 🎯 Expected RAG flow:
      - Retrieves: Stakeholder data (if available), project complexity
      - Searches: "Stakeholder communication", "Project communication best practices"
      - Combines: Your stakeholders + communication framework
    - 🧪 Test result pass if: Considers your stakeholder landscape + provides strategies

#### Advanced Level
72. **"Create a process improvement plan for our project management function"**
    - 🎯 Expected RAG flow:
      - Retrieves: Complete project management data and current processes
      - Searches: "Process improvement frameworks", "Lean/Six Sigma"
      - Combines: Current state analysis + improvement roadmap
    - 🧪 Test result pass if:
      - Assessment of current state
      - Identified improvement opportunities
      - Prioritized improvement initiatives
      - Implementation approach

---

### Category 2E: Decision-Making & Strategic Advice

**Expected**: AI should help with complex strategic decisions using your data and external knowledge

#### Beginner Level
73. **"Should we add more team members to speed up work?"**
    - 🎯 Expected RAG flow:
      - Retrieves: Workload, team capacity, task distribution
      - Searches: "Team sizing", "Mythical man-month", "Team scaling"
      - Combines: Your workload + hiring considerations
    - 🧪 Test result pass if: Analyzes your workload + provides hiring guidance

74. **"How do we decide which projects to prioritize?"**
    - 🎯 Expected RAG flow:
      - Retrieves: Your project list and characteristics
      - Searches: "Project prioritization frameworks", "Portfolio prioritization"
      - Combines: Your projects + decision framework
    - 🧪 Test result pass if: References your projects + explains prioritization framework

#### Intermediate Level
75. **"Should we change our project management approach (agile vs waterfall vs hybrid)?"**
    - 🎯 Expected RAG flow:
      - Retrieves: Current approach, project characteristics, team skills
      - Searches: "Choosing between agile/waterfall", "Hybrid approaches"
      - Combines: Your situation + method comparison
    - 🧪 Test result pass if: 
      - Assesses your current approach
      - Analyzes pros/cons for your context
      - Provides recommendation with rationale

76. **"How do we balance speed vs quality in our projects?"**
    - 🎯 Expected RAG flow:
      - Retrieves: Project timeline, quality metrics, team capacity
      - Searches: "Speed vs quality tradeoff", "Technical debt"
      - Combines: Your constraints + strategic considerations
    - 🧪 Test result pass if: Acknowledges your constraints + provides strategic guidance

77. **"What technology/tools should we adopt to improve project management?"**
    - 🎯 Expected RAG flow:
      - Retrieves: Current tools, project complexity, team skills
      - Searches: "Project management tools", "Tool comparison"
      - Combines: Your needs + tool recommendations
    - 🧪 Test result pass if: References your context + justifies tool recommendations

#### Advanced Level
78. **"Help us make a strategic decision about outsourcing vs building in-house"**
    - 🎯 Expected RAG flow:
      - Retrieves: Team capacity, skills, project backlog, timeline
      - Searches: "Outsourcing decisions", "Build vs buy", "Insourcing vs outsourcing"
      - Combines: Your resource situation + strategic framework
    - 🧪 Test result pass if:
      - Financial analysis
      - Risk considerations
      - Timeline impact
      - Quality implications

---

### Category 2F: Trend Analysis & Future Planning

**Expected**: AI should combine your historical project data with external trends for future planning

#### Beginner Level
79. **"What emerging trends should we be aware of in project management?"**
    - 🎯 Expected RAG flow:
      - Searches: "Project management trends 2024/2025", "Future of PM"
      - Combines: Latest trends + your project context
    - 🧪 Test result pass if: Mentions current/emerging trends relevant to your work

80. **"How are AI and automation changing project management?"**
    - 🎯 Expected RAG flow:
      - Searches: "AI in project management", "Automation benefits"
      - Combines: Latest info + your potential applications
    - 🧪 Test result pass if: Discusses AI/automation trends + your use cases

#### Intermediate Level
81. **"Based on our project history, what's our productivity trend?"**
    - 🎯 Expected RAG flow:
      - Retrieves: Historical task data, completion rates (if available)
      - Searches: "Productivity measurement", "Velocity tracking"
      - Combines: Your trends + benchmark comparisons
    - 🧪 Test result pass if: References your data + explains trend significance

82. **"What should we prepare for to improve over the next 6 months?"**
    - 🎯 Expected RAG flow:
      - Retrieves: Current capabilities, bottlenecks, team growth
      - Searches: "Project management roadmap", "Capability maturity"
      - Combines: Your situation + growth strategy
    - 🧪 Test result pass if: Provides specific 6-month improvements for your context

#### Advanced Level
83. **"Forecast team capacity and project demand for the next quarter"**
    - 🎯 Expected RAG flow:
      - Retrieves: Historical workload, team skills, current projects
      - Searches: "Capacity forecasting", "Demand planning"
      - Combines: Your data + forecasting methods
    - 🧪 Test result pass if:
      - Projects your team capacity
      - Estimates demand
      - Identifies potential gaps
      - Suggests mitigation strategies

---

## HOW TO TEST

### Step 1: Setup
1. Ensure AI assistant is running
2. Have demo data loaded in your TaskFlow instance
3. Open the chat interface

### Step 2: Test Sequence

#### Phase 1: Data Retrieval (Questions 1-44)
- Start with **Category 1A** (Organization questions)
- Progress through categories in order
- For each question:
  - ✅ Note if response is accurate
  - ⚠️ Note any hallucinations or inaccuracies
  - 📝 Record response time
  - 🎯 Note which data sources were used

#### Phase 2: RAG Capability (Questions 45-83)
- Test strategic questions in order by category
- For each question:
  - 🌐 Does it mention web search results? (Look for "According to...", "Industry research shows...")
  - 📊 Does it reference your specific project data? (Task names, team members, risk data?)
  - 🧪 Is the advice grounded in both sources? (Specific + general?)
  - ⚡ Does it feel relevant and tailored vs generic?

### Step 3: Document Findings

Create a test report showing:
- ✅ Questions answered correctly
- ⚠️ Questions answered partially or incorrectly
- ❌ Questions the AI couldn't answer
- 🧪 Quality of RAG synthesis (how well it combined data + web search)
- 🎯 Areas for improvement

---

## EXPECTED CAPABILITIES BY CATEGORY

### Data Retrieval (Part 1)

| Category | ✅ Should work | ⚠️ Might be complex | ❌ Unlikely |
|----------|---------|-----------|----------|
| **Organizations** | Listing, counting basic org data | Comparative analysis across orgs | Deep organization hierarchy analysis |
| **Boards** | Listing, task counts per board | Complex board metrics | Board timeline analysis |
| **Tasks** | Filtering by status/priority, basic counts | Dependency visualization, trend analysis | Predictive task completion |
| **Teams** | Member listing, task distribution | Capacity analysis, skill matching | Predictive team needs |
| **Risk** | Identifying high-risk tasks | Risk scoring validation | Predictive risk models |

### RAG Capability (Part 2)

| Category | ✅ Core Capability | How to Verify |
|----------|-----------|---------|
| **Risk Strategies** | Combine risk data + best practices | Response mentions your risks + general principles |
| **PM Strategies** | Combine project data + best practices | Response mentions your projects + relevant frameworks |
| **Org Alignment** | Combine structure + strategic principles | Response considers your structure + alignment advice |
| **Process Improvement** | Combine current state + improvement frameworks | Response analyzes your setup + suggests improvements |
| **Strategic Decisions** | Combine your data + decision frameworks | Response weighs options with your context |
| **Trend Analysis** | Combine your data + external trends | Response includes trends + your application |

---

## QUALITY METRICS

### For Data Retrieval Questions
- **Accuracy**: Does the answer match your actual project data? (0-100%)
- **Completeness**: Does it answer all aspects of the question? (0-100%)
- **Clarity**: Is the answer clear and well-formatted? (0-100%)

### For RAG Questions
- **Relevance**: Is the advice relevant to your specific project? (0-100%)
- **Grounding**: Is it grounded in both general knowledge AND your data? (0-100%)
- **Actionability**: Can you act on the advice provided? (0-100%)
- **Synthesis**: Does it thoughtfully combine sources vs just listing both? (0-100%)

---

## TROUBLESHOOTING

### If data retrieval is poor:
1. Check that demo data is loaded (`python manage.py loaddata demo_data.json`)
2. Verify user is a member of boards
3. Check that user's organization is set up correctly

### If RAG is not working:
1. Verify `ENABLE_WEB_SEARCH=True` in `.env`
2. Check that Google Search API keys are configured
3. Look for "web search" indicators in responses
4. Check logs: `tail -f logs/chatbot.log`

### If responses are slow:
1. Check AI API key is valid
2. Monitor token usage in analytics
3. Consider enabling caching

---

## NEXT STEPS AFTER TESTING

1. **Document findings**: Create a test report
2. **Identify gaps**: Note which queries don't work well
3. **Prioritize fixes**: Rank issues by user impact
4. **Implement improvements**: Update context builders, add new query types
5. **Retesting**: Verify fixes with questions in same category

---

## QUICK REFERENCE CHECKLIST

### Data Retrieval Quick Check ✅
- [ ] Question 1-5: Organization data (basic)
- [ ] Question 6-15: Organization data (advanced) & Board data
- [ ] Question 16-27: Task data and analysis
- [ ] Question 28-36: Team and capacity data
- [ ] Question 37-44: Risk data and analysis

### RAG Quick Check ✅
- [ ] Question 45-53: Risk management strategies
- [ ] Question 54-61: Strategic PM advice
- [ ] Question 62-66: Organizational strategy
- [ ] Question 67-72: Process improvement
- [ ] Question 73-78: Strategic decisions
- [ ] Question 79-83: Trends and forecasting

---

## SUMMARY

You now have **83 comprehensive test questions** organized by:
- **Complexity**: Beginner → Intermediate → Advanced
- **Domain**: Organizations, Boards, Tasks, Teams, Risk, Strategy
- **Capability**: Data Retrieval (44 Qs) vs RAG/Strategic Advice (39 Qs)

**Good luck with testing! 🚀**
