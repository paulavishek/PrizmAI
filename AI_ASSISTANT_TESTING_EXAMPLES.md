# AI Assistant Testing - Example Walkthroughs

**Date**: November 5, 2025  
**Purpose**: Show exactly what to expect when testing different question types

---

## 📌 HOW TO USE THIS DOCUMENT

This document provides **realistic examples** of:
- What questions to ask
- What type of responses you should expect (if working well)
- How to evaluate if the AI performed well

Use these examples to calibrate your expectations during testing.

---

## EXAMPLE 1: Basic Data Retrieval Question

### The Question
**"How many boards do I have?"**

### What the AI Should Do
1. Query the Board model for boards where user is creator or member
2. Count the boards
3. Return a simple number with context

### Example Good Response
```
You currently have 5 boards:
1. Product Development
2. Marketing Campaign Q4
3. Operations Management
4. Research & Innovation
5. Customer Success

Would you like details about any specific board?
```

### Example Poor Response
```
I don't have specific information about your boards right now.
```

### How to Evaluate
✅ **Good if:**
- Returns accurate count
- Lists board names correctly
- Shows these are YOUR boards (not generic)
- Number matches reality

❌ **Poor if:**
- Wrong count
- Generic response
- Doesn't show your board names
- Claims no access

---

## EXAMPLE 2: Intermediate Data Retrieval Question

### The Question
**"Which of my boards has the most tasks?"**

### What the AI Should Do
1. Query all boards for the user
2. Count tasks in each board
3. Identify the board with maximum tasks
4. Return board name with task count

### Example Good Response
```
Your "Product Development" board has the most tasks with 24 total tasks.

Here's the breakdown:
- Product Development: 24 tasks
- Marketing Campaign Q4: 18 tasks
- Operations Management: 15 tasks
- Research & Innovation: 12 tasks
- Customer Success: 8 tasks

The Product Development board has 6 more tasks than the next busiest board.
Would you like to see the breakdown by status (To Do, In Progress, Done)?
```

### Example Poor Response
```
I'm not sure which board has the most tasks.
```

### How to Evaluate
✅ **Good if:**
- Correct board identified
- Accurate task count
- Shows comparison data
- Feels specific to your project

❌ **Poor if:**
- Wrong board identified
- Incorrect counts
- No supporting data
- Uncertainty or hedging

---

## EXAMPLE 3: Complex Data Retrieval Question

### The Question
**"Show me tasks that are blocked (have dependencies) and their assigned team members"**

### What the AI Should Do
1. Query tasks with dependencies or parent_task
2. Get assignee information for each
3. Present in clear format showing task-dependency-assignee relationship

### Example Good Response
```
I found 7 blocked/dependent tasks across your boards:

**HIGH PRIORITY BLOCKERS:**

1. API Authentication Module (Product Development)
   - Depends on: Database Schema Design
   - Status: In Progress (60% complete)
   - Assigned to: Alex Chen
   - Risk: Medium

2. Payment Integration (Product Development)
   - Depends on: API Authentication Module
   - Status: On Hold (0% complete)
   - Assigned to: Jamie Rodriguez
   - Risk: High

**MEDIUM PRIORITY DEPENDENCIES:**

3. Marketing Landing Page (Marketing Campaign Q4)
   - Depends on: Product Feature Finalization
   - Status: In Progress (40% complete)
   - Assigned to: Sam Taylor
   - Risk: Low

[... more tasks ...]

**Summary:** 2 critical blockers need attention, 3 others waiting on dependencies, 
2 have been completed but dependents haven't started yet.
```

### Example Poor Response
```
You have some blocked tasks. Let me check... I see you have dependencies.
```

### How to Evaluate
✅ **Good if:**
- Shows actual task names from your project
- Correct dependency relationships
- Shows who it's assigned to
- Provides actionable summary
- References specific risk levels/status

❌ **Poor if:**
- Generic or vague language
- Wrong task names
- Missing assignee info
- No summary or insight

---

## EXAMPLE 4: Strategic Question - RAG Example 1

### The Question
**"How should I tackle the high-risk tasks in my project? What are best practices?"**

### What the AI Should Do
1. Retrieve your high-risk tasks from database
2. Search web for "Risk management best practices", "Handling critical project risks"
3. Synthesize: Your specific risks + industry practices
4. Provide actionable advice tailored to YOUR situation

### Example Good Response (Shows RAG Working)
```
I've analyzed your high-risk tasks and reviewed current risk management best practices.

**YOUR HIGH-RISK SITUATION:**
You have 5 critical-priority tasks:
- API Authentication Module (Risk Score: 85/100)
  Blocker for downstream work, single point of failure
  
- Payment Integration (Risk Score: 78/100)
  Complex integration, security implications
  
- Database Migration (Risk Score: 82/100)
  System-critical, data loss potential
  
- Legacy System Integration (Risk Score: 75/100)
  Unknown dependencies in old codebase
  
- Real-time Notification System (Risk Score: 71/100)
  Performance-critical, requires new infrastructure

**INDUSTRY BEST PRACTICES FOR HIGH-RISK TASKS:**

1. **Risk Mitigation Strategy** (Applied to your context)
   - Break complex tasks into smaller chunks
     → For you: Split "Payment Integration" into auth, processing, reconciliation
   
   - Assign to your most experienced team members
     → You have Alex Chen (experienced) but overloaded with 6 tasks
     → Consider reassigning less critical work from Alex to handle Payment Integration
   
   - Implement extra reviews/checkpoints
     → For database work: Pre-migration backup, staging test, rollback plan

2. **Dependency Management**
   - Identify and unblock dependencies early
     → Your blocker: API Auth module blocking Payment Integration
     → Suggest: Fast-track API Auth with code review, don't wait for all features
   
   - Parallel work where possible
     → Real-time Notifications could run parallel to Payment work

3. **Resource Allocation**
   - Allocate buffer time (20-30% extra)
     → Your timeline: Payment Integration scheduled 2 weeks
     → Recommend: Add 4-6 days buffer given high risk
   
   - Cross-training to reduce single points of failure
     → Payment work should have 2 people who understand it

4. **Monitoring & Early Warning**
   - Daily standups for high-risk work
   - Automated testing on critical path tasks
   - Risk reassessment every 2-3 days (not just at start)

**SPECIFIC RECOMMENDATIONS FOR YOUR PROJECT:**

Immediate (This week):
1. Reassign 2 lower-priority tasks away from Alex to free capacity
2. Have Jamie and Alex pair on Payment Integration architecture review
3. Start database migration testing today (not next week)

Short-term (Next 2 weeks):
1. Daily standups for the 5 critical tasks
2. Implement automated tests before deployment
3. Prepare rollback procedures for database migration
4. Have contingency team ready for real-time system issues

This approach balances speed with risk management - you get done faster while 
reducing failure probability from industry average ~35% to ~15% for this complexity level.
```

### Example Poor Response (RAG Not Working)
```
You should manage your risks carefully. Here are some general best practices:
1. Identify risks early
2. Have a mitigation plan
3. Monitor progress
4. Communicate with your team

I also found some articles about risk management on the web:
- Article 1: https://...
- Article 2: https://...

You can read these for more information.
```

### How to Evaluate
✅ **Good RAG if:**
- Specific tasks mentioned (YOUR data)
- Best practices explained (GENERAL knowledge)
- Integrated together (Your situation + best practice)
- Actionable recommendations
- Considers YOUR constraints (team capacity, timeline, etc.)
- Shows synthesis, not just list

❌ **Poor RAG if:**
- Generic advice not tied to your data
- Just lists web links
- Doesn't mention your specific tasks
- Advice that doesn't fit your context
- Feels like Wikipedia article

---

## EXAMPLE 5: Strategic Question - RAG Example 2

### The Question
**"How can I reduce delays and improve on-time delivery for my projects?"**

### What the AI Should Do
1. Analyze your project history (if available: task completion rates, timeline adherence)
2. Identify current delays/issues
3. Search for "Reducing project delays", "On-time delivery strategies"
4. Synthesize: Your patterns + best practices
5. Provide specific improvements for YOUR workflow

### Example Good Response (Shows RAG Working)
```
Based on analysis of your projects and proven delivery acceleration strategies:

**YOUR CURRENT DELIVERY PERFORMANCE:**

Last 3 months analysis:
- On-time: 14 tasks (58%)
- Late 1-3 days: 8 tasks (33%)
- Late >3 days: 2 tasks (8%)
- Average delay: 1.8 days

High-risk boards:
- Product Development: 68% on-time (better than avg)
- Operations Management: 45% on-time (needs work)
- Marketing Campaign: 52% on-time (needs improvement)

Main delay causes I see in your data:
1. Dependencies blocking (40% of delays)
2. Resource overallocation (35% of delays)  
3. Scope creep (25% of delays)

**PROVEN DELIVERY ACCELERATION METHODS:**

1. **Buffer Planning (Recommended for your situation)**
   - Add 15-25% time buffer based on task complexity
   - Your current approach: Tight schedules contributing to delays
   - Your pattern: Operations tasks slip most often
   - Action: Add explicit "buffer" tasks or mark as "critical path"
   - Expected improvement: 10-15% fewer delays

2. **Dependency Management**
   - 40% of your delays are dependency-related
   - Pattern: API tasks often block others
   - Strategy: 
     * Identify critical path dependencies FIRST
     * Allocate your best people to these
     * Do dependency tasks first, even if not highest priority
   - Expected improvement: 8-12% fewer delays

3. **Resource Leveling**
   - Your team shows uneven loading (Alex: 6 tasks, Sam: 2 tasks)
   - Overloaded team members = delays
   - Strategy: 
     * Keep individual load to 3-4 tasks max
     * Rebalance work before overloads happen
     * Use available capacity from less busy members
   - Expected improvement: 5-10% fewer delays

4. **Scope Lock & Change Control**
   - Some of your delays show scope creep signals
   - Strategy:
     * Freeze scope at project start
     * Changes require timeline adjustment
     * Create separate "enhancement" backlog
   - Expected improvement: 3-8% fewer delays

**YOUR 90-DAY DELIVERY IMPROVEMENT PLAN:**

Month 1 (Weeks 1-4): Foundation
□ Rebalance workload (move 2 tasks from Alex)
□ Identify all critical path dependencies for next 2 boards
□ Add 20% time buffers to Operations board tasks
□ Implement scope lock - no mid-task changes

Expected result: Reduce delays from 42% to 35%

Month 2 (Weeks 5-8): Optimization
□ Daily standups for on-time projects to catch issues early
□ Implement automated task tracking/reminders
□ Run dependency analysis weekly
□ Track delivery metrics daily

Expected result: Further reduce to 25% delays

Month 3 (Weeks 9-12): Institutionalize
□ Document what's working
□ Train team on new processes
□ Create standard templates for new projects
□ Build delivery dashboard for visibility

Expected result: Stabilize at 15-20% delays (industry good performance)

This plan is specific to your patterns and should improve on-time delivery 
from 58% to 80%+ based on similar implementations in comparable teams.
```

### Example Poor Response (RAG Not Working)
```
To improve on-time delivery, you should:
1. Plan better
2. Communicate with your team
3. Track progress
4. Adjust when needed

Here are some strategies:
- Use Agile methodology
- Have daily standups
- Monitor tasks closely

Good luck with your projects!
```

### How to Evaluate
✅ **Good RAG if:**
- Analyzes YOUR delivery patterns
- References specific delays and causes from your projects
- Mentions YOUR team members and workload
- Best practices tailored to YOUR issues
- Specific metrics and timeline
- Clear actions YOU can take

❌ **Poor RAG if:**
- Generic "good practices" anyone could use
- Doesn't reference your projects
- No metrics or specifics
- Doesn't address YOUR root causes
- Could apply to any project

---

## EXAMPLE 6: Question That's Hard to Answer - How to Recognize

### The Question
**"What's the optimal team composition and skills for my organization?"**

### Why It's Hard
- Requires: Industry knowledge + your detailed org data + skills matching
- Depends on: Project types, market conditions, growth plans (may not be in database)
- Highly contextual: What works varies by industry, market, company stage

### Example Partial Response (Some RAG)
```
Based on your organization structure and industry best practices:

**YOUR CURRENT ORGANIZATION:**
- 3 organizations with total 42 members
- Boards: 5 active, 3 archived
- Primary areas: Product, Marketing, Operations
- Board sizes: 4-12 people each

**INDUSTRY BEST PRACTICES FOR TEAM COMPOSITION:**

For product development teams (your largest):
- Recommended ratio: 40% backend, 35% frontend, 15% QA, 10% ops
- Your team: ~30% backend, 40% frontend, 15% QA, 15% ops
- Gap: Slight shortage in backend, slight excess in frontend

For product teams of your size (8 people):
- Ideal: 1 tech lead, 3-4 senior engineers, 3-4 mid-level, 1 QA
- Recommend: Add 1-2 backend engineers, consider rotating 1 frontend to backend

**LIMITATIONS:**
I don't have visibility into:
- Specific skills beyond what's in profiles
- Project pipeline for next year (growth planning)
- Team experience/seniority details (career stage)
- Domain-specific skill needs (varies by industry)
- Market conditions affecting skill availability

**RECOMMENDATION:**
1. Fill immediate backend gap (1-2 engineers) - you have frontend capacity
2. For strategic planning, provide:
   - Your 12-month project roadmap
   - Specific technologies/skills needed
   - Market/industry context
   - Growth targets
```

### How to Evaluate
✅ **Acceptable if:**
- Acknowledges limitations
- Uses available data well
- Shows reasoning
- Asks for missing information
- Provides partial but useful answer

❌ **Poor if:**
- Pretends to have data it doesn't
- Makes up details
- Generic answer ignoring your specifics
- Doesn't note limitations

---

## QUICK RESPONSE EVALUATION CHECKLIST

### For Data Retrieval Questions
- [ ] Answer is specific (names, numbers, details from YOUR project)
- [ ] Answer is accurate (matches reality)
- [ ] Answer is complete (addresses the full question)
- [ ] Answer is clear (well-formatted, easy to understand)
- [ ] Answer has context (explains the significance)

### For Strategic/RAG Questions
- [ ] References YOUR specific data (tasks, people, metrics)
- [ ] Mentions external source or best practice (not just your data)
- [ ] Integrates both together (not just listing them)
- [ ] Is actionable (you can actually do the recommendations)
- [ ] Is tailored (feels specific, not generic)
- [ ] Shows reasoning (you understand the logic)

---

## COMMON RESPONSES AND WHAT THEY MEAN

### Response Type 1: Accurate Data Retrieval
```
You have 5 boards: Product (24 tasks), Marketing (18), Operations (15), Research (12), Support (8).
The most active is Product Development.
```
**Evaluation**: ✅ Data retrieval working well

### Response Type 2: Data + Generic Advice
```
You have 5 boards. Generally, you should have 1 person per 3-4 tasks.
You can read about best practices here: [link]
```
**Evaluation**: ⚠️ Data retrieval working, but RAG not synthesized

### Response Type 3: Specific + Best Practice Synthesis
```
Your Product board has 24 tasks (vs 18 average). This is 33% above average.
Industry standard suggests you should add 1 person per 3-4 tasks.
Your team has 5 people on Product board = optimal for 15-20 tasks.
Recommendation: Either reduce scope 20% or add 1-2 people.
This is specifically relevant because your task density is high.
```
**Evaluation**: ✅ RAG working well - great synthesis

### Response Type 4: Vague/Uncertain
```
I think you might have some boards. I'm not entirely sure about the exact count.
```
**Evaluation**: ❌ Data retrieval not working

### Response Type 5: Hallucination (Making Up Data)
```
Your boards are: Sales, Finance, HR, Legal, Compliance (these don't exist)
```
**Evaluation**: ❌ Major issue - AI made up data

---

## NEXT STEPS

1. **Use Example 1-6** as reference templates
2. **Compare actual responses** to these examples
3. **Rate responses** using the checklist
4. **Document patterns** in what works vs doesn't
5. **Report findings** in your test summary

---

**Ready to test? Compare your AI's responses to these examples!** 🎯
