# 🎯 PrizmAI Features - Complete Guide

This document contains detailed information about all advanced features in PrizmAI.

**See [README.md](README.md) for a quick overview and getting started guide.**

---

## 📚 Table of Contents

- [Explainable AI](#-explainable-ai)
- [AI Coach](#-ai-coach-for-project-managers)
- [Burndown Charts](#-burndown-chart--sprint-analytics)
- [Scope Creep Detection](#-scope-creep-detection--tracking)
- [Conflict Detection](#-automated-conflict-detection--resolution)
- [Budget & ROI Tracking](#-budget--roi-tracking-with-ai-optimization)
- [AI-Powered Retrospectives](#-ai-powered-retrospectives)
- [Skill Gap Analysis](#-ai-mediated-skill-gap-analysis)
- [Smart Recommendations](#-smart-recommendations)
- [AI Assistants for Wiki](#-intelligent-ai-assistants-for-wiki-pages)
- [Resource Leveling](#-ai-powered-resource-leveling--optimization)

---

## 🔍 **Explainable AI**

### What is Explainable AI?

PrizmAI doesn't just make recommendations - it **explains them**. Every AI decision includes:
- Why the AI reached that conclusion
- How confident it is
- What factors influenced the decision
- What assumptions it made
- Known limitations
- Alternative perspectives

**This is revolutionary because:**
- Traditional AI tools just say "Here's my recommendation" (trust us!)
- PrizmAI says "Here's my recommendation, here's why, and here's what I'm uncertain about"

### How Explainability Works in Practice

Whenever you see an AI recommendation, look for the **"Why?"** button. Click it to get:

#### **1. Risk Assessment Explanation**

```
Task: "Integrate Payment Gateway"
Risk Score: 7/10

Why?
├─ AI Confidence: 82% (Pretty sure about this)
├─ Contributing Factors:
│  ├─ 35% - Task Complexity (multiple integration points)
│  ├─ 30% - External Dependencies (payment processor approval)
│  ├─ 20% - Skill Gap (needs expert, only have intermediate)
│  └─ 15% - Timeline Pressure (3 days vs typical 5 days)
├─ Calculation: Likelihood (2) × Impact (3) = Risk (6)
├─ Model Assumptions:
│  └─ Bob can dedicate 6 hours/day to this task
├─ Data Limitations:
│  └─ Limited historical payment integration data
└─ Alternative View:
   └─ Risk could be lower if using Stripe SDK instead
```

**What This Means for You:**
- You understand exactly why it's risky
- You can challenge the assumption if Bob has more time
- You can mitigate the risk by choosing Stripe
- You know the AI is 82% confident (not a guess)

#### **2. Deadline Prediction Explanation**

```
Task: "Implement User Dashboard"
Predicted Completion: Nov 25, 2025
Confidence: 78%

Click "Why?" to see:
├─ AI Confidence: 78% (fairly reliable)
├─ Similar Historical Tasks:
│  ├─ "Build Admin Panel" - 4.2 days (similar complexity)
│  ├─ "Implement Settings Page" - 3.8 days
│  ├─ "Create Dashboard Layout" - 5.1 days
│  └─ ... (4 more similar tasks)
├─ Calculation:
│  ├─ Base Estimate: 3 days
│  ├─ × Complexity Factor: 1.4 (medium complexity)
│  ├─ × Current Workload: 1.2 (team busy this week)
│  └─ + Buffer: 1 day (for unknowns)
│  = Final: 5.4 → 6 days
├─ Assumptions:
│  ├─ Bob dedicated 6-8 hours/day
│  ├─ No major API delays
│  └─ Code review takes 1 day
├─ Alternative Scenarios:
│  ├─ Optimistic: Nov 23 (if no blockers)
│  ├─ Realistic: Nov 25 (most likely)
│  └─ Pessimistic: Nov 28 (if API delays happen)
└─ Risk Factors:
   ├─ External API dependency
   └─ Team has 3 other urgent tasks
```

**What This Means for You:**
- You can promise clients a realistic date (Nov 25)
- You know the worst case (Nov 28) to budget for delays
- You understand why (complexity, team capacity)
- You can change the outcome (remove other urgent tasks, hire help, use pre-built APIs)

#### **3. Assignee Recommendation Explanation**

```
Recommended: Jane Smith

Click "Why?" to see:
├─ Skill Match Score: 92%
├─ Skill Breakdown:
│  ├─ Python: Need Expert → Jane has Expert (100% match)
│  ├─ React: Need Advanced → Jane has Advanced (100% match)
│  ├─ AWS: Need Intermediate → Jane has Advanced (95% match)
│  └─ API Design: Need Intermediate → Jane has Intermediate (100% match)
├─ Historical Performance:
│  ├─ Similar Tasks: 7 completed
│  ├─ Average Time: 4.2 days
│  ├─ Quality Score: 9.2/10
│  └─ Current Workload: 2 tasks (manageable)
├─ Availability:
│  └─ 8 hours/day this week
└─ Why Not Bob?
   └─ Bob has only beginner React skills (95% match vs Jane's 100%)
```

**What This Means for You:**
- You know Jane is the best person, backed by data
- You understand why (skills and availability)
- You can see alternatives if Jane is unavailable
- You can prioritize training (if you need to develop Bob's skills)

### Why Explainability Matters for Your Team

**For Managers:**
- Make decisions with confidence, not guesses
- Explain to executives why you're assigning work this way
- Challenge AI when you see flawed assumptions
- Track if AI recommendations actually work

**For Team Members:**
- Understand why they're assigned work
- See what skills to develop next
- Know if deadlines are realistic
- Learn from AI patterns

**For Executives:**
- Compliance requirements - every AI decision is auditable
- Risk management - see model confidence and limitations
- ROI tracking - understand which AI recommendations work best
- Trust in AI - employees believe in transparent AI

### All Explainability Features at a Glance

| Feature | When Used | What You Learn |
|---------|-----------|---------------|
| Risk Assessment | When evaluating task difficulty | Why it's risky, confidence level, mitigation |
| Deadline Prediction | When planning timeline | How long it'll really take, confidence, scenarios |
| Assignee Recommendation | When assigning work | Who's best match, why, skill gaps |
| Priority Suggestion | When prioritizing tasks | Which tasks matter most, why |
| Workload Forecast | When capacity planning | Who's overloaded, recommendations, conflicts |
| Dependency Analysis | When planning complex projects | Which tasks block others, why, critical path |

---

## 🎓 **AI Coach for Project Managers**

**Get proactive coaching and intelligent guidance to improve your project management decisions in real-time.**

The AI Coach is like having an experienced mentor looking over your shoulder, watching your project metrics and offering timely, actionable advice. It automatically detects problems before they become critical and learns from your feedback to improve suggestions over time.

### What It Does

The AI Coach continuously monitors your project and:

- 🚨 **Catches problems early** - Detects velocity drops, resource overloads, and risks before they escalate
- ⚠️ **Prevents disasters** - Alerts you when multiple high-risk tasks converge
- 💡 **Spots opportunities** - Identifies skilled team members ready for challenging work
- 📈 **Learns and improves** - Gets smarter from your feedback and actions
- 🎯 **Provides actionable guidance** - Suggests concrete steps to improve your project

### Core Features

**1. Intelligent Pattern Detection**

The rule engine analyzes your project in real-time and detects:

```
Detected Issues:
├─ 🔴 Velocity Drop: Team completing 30% fewer tasks this week
├─ 🟠 Resource Overload: Jane has 10 active tasks (2x normal)
├─ 🔴 Risk Convergence: 3 high-risk tasks due same week
├─ 🟡 Scope Creep: 15% increase in total tasks and complexity
├─ 🟠 Deadline Risk: 40% probability of missing deadline
├─ 🟡 Team Burnout: 4 team members working overtime for 2+ weeks
├─ 🟡 Quality Issues: 5 tasks reopened this week (double normal)
├─ 🔴 Communication Gap: 2 blockers waiting on external response
├─ 🟠 Skill Opportunity: Bob ready to lead complex database work
└─ 🔵 Best Practice: Consider parallel testing for faster feedback
```

**2. AI-Enhanced Reasoning**

Each suggestion includes AI-generated explanations:

```
Suggestion: "Your Velocity is Dropping"
────────────────────────────────────

Why This Matters:
  Your team completed 30% fewer tasks this week (12 vs 18 tasks).
  This pattern typically precedes project delays.

What Might Be Happening:
  ├─ Blocking issues delaying task completion
  ├─ Increased complexity of recent tasks
  ├─ Team members pulled to other work
  └─ Skill gap in emerging technology

Recommended Actions:
  1. Run quick team standup to identify blockers
  2. Review 3 oldest "In Progress" tasks for issues
  3. Pair junior developers with senior mentors
  4. Consider simplifying next task scope

Expected Impact:
  If you address blockers, velocity should recover within 2-3 days.

AI Confidence: 82% (based on 12 similar patterns in past projects)
```

**3. Continuous Learning**

The system learns from your feedback and improves:

```
Learning Cycle:
  1. System generates suggestion
  2. You take action (or dismiss suggestion)
  3. System learns what worked
  4. Next similar situation → better suggestion

Example Learning:
  Week 1: Coach suggests "Pair programming will improve quality"
          You dismiss it, code reviews work better for your team
  Week 2: Coach suggests "Pair programming"
          But with lower confidence (remembers you prefer code reviews)
  Week 3: Coach suggests "Code review needed" instead
          Confidence: 95% (learned your preference)
```

### Types of Suggestions You'll Receive

**Critical Alerts (🔴)** - Require immediate action:
- Risk convergence (3+ high-risk tasks due same period)
- Deadline at risk (40%+ probability of missing)
- Severe team burnout (multiple people 40+ hours/week)

**High Priority (🟠)** - Address within 1-2 days:
- Velocity drops significantly (30%+ decrease)
- Resource overload (person has 2x normal tasks)
- Critical blockers (work waiting on external response)

**Medium Priority (🟡)** - Address this week:
- Scope creep (15%+ increase in work)
- Quality issues emerging (higher reopened task rate)
- Skill gaps identified (task requires unavailable skill)

**Low Priority (🟦)** - Consider when planning:
- Skill development opportunities (team member ready to stretch)
- Best practice recommendations
- Process improvements

### Benefits

✅ **Proactive Management** - Catch issues before they become problems  
✅ **Data-Driven Decisions** - Recommendations based on actual metrics  
✅ **Team Development** - Identifies learning opportunities for team growth  
✅ **Continuous Improvement** - System learns from feedback  
✅ **Risk Mitigation** - Early warning for project threats  
✅ **Time Saving** - No need to constantly analyze project metrics  
✅ **Transparent Reasoning** - Understand why each suggestion is made  
✅ **Scalable Mentoring** - Works as your team and projects grow  

---

## 📊 **Burndown Chart & Sprint Analytics**

**Visualize your sprint progress in real-time with intelligent burndown charts and forecasting.**

Every board now includes a comprehensive burndown dashboard that shows:

- 📉 **Burndown Chart** - Visual representation of tasks remaining over time
- 🎯 **Completion Forecast** - Predicted project completion date with confidence interval
- 📈 **Current Progress** - Real-time metrics on tasks completed, velocity, and trends
- ⚠️ **Risk Assessment** - Automatic detection of delays and blockers
- 💡 **Actionable Suggestions** - AI-powered recommendations to improve completion probability
- 📊 **Velocity History** - Track team velocity trends week-over-week

### Key Metrics on the Dashboard:

```
Completion Forecast:
├─ Predicted Completion Date ±2 days (90% confidence)
├─ Completion Range (lower to upper bound)
├─ Days Until Completion
└─ Risk Level (with miss probability)

Current Progress:
├─ Tasks Completed / Total Tasks (% complete)
├─ Tasks Remaining
├─ Current Velocity (tasks/week)
└─ Velocity Trend (Increasing, Stable, or Decreasing)
```

### Example Forecast:

```
Project Status: Mobile App Release

Predicted Completion: Nov 22, 2025 ±2 days (90% confidence)
Optimistic Case: Nov 20 (if everything goes smoothly)
Realistic Case: Nov 22 (most likely)
Pessimistic Case: Nov 25 (if blockers emerge)

Current Progress:
├─ 96.4% complete (85/88 tasks done)
├─ 3 tasks remaining
├─ Velocity: 12 tasks/week (stable)
└─ Risk Level: MEDIUM (25% miss probability)

Alerts:
🟡 One high-complexity task may slip (API integration)
💡 Suggestion: Assign senior developer to prevent delay
```

---

## 🚨 **Scope Creep Detection & Tracking**

**Automatically detect when your project is growing beyond its original boundaries — before it becomes a problem.**

### What is Scope Creep Detection?

Every board now has a **dedicated scope tracking dashboard** that monitors how your project grows over time:

```
Project Scope Tracking Dashboard

Original Scope: 85 tasks
Current Scope: 127 tasks
Scope Growth: +42 tasks (+49.4%)

⚠️ ALERT: Significant Scope Increase Detected!
```

### How It Works

**1. Baseline Establishment**

When you create a board or enable scope tracking, PrizmAI captures a **baseline snapshot** of your current scope:

```
Baseline Snapshot (Day 1):
├─ Total Tasks: 85
├─ Total Complexity: 340 points
├─ Total Estimated Hours: 480 hours
├─ Critical Tasks: 8
└─ Status: Documented and locked
```

**2. Continuous Monitoring**

PrizmAI automatically tracks changes:

```
Daily Monitoring:
├─ New tasks added
├─ Tasks marked complete
├─ Task complexity changes
├─ Priority level changes
├─ Dependencies added
└─ Timeline changes
```

**3. Alert Generation**

When scope changes exceed configured thresholds, alerts are created:

```
Scope Creep Alert
├─ Type: Task Addition Spike
├─ Severity: HIGH
├─ Detected: Nov 20, 2025 at 2:30 PM
├─ Change: +8 new tasks added today
├─ Impact: +20 hours of work
└─ Recommendation: Review and prioritize new tasks
```

### Key Metrics Tracked

**Scope Growth Analysis:**

```
Overall Scope Growth:
├─ Original Tasks: 85
├─ Current Tasks: 127
├─ Difference: +42 tasks (+49.4%)
├─ Growth Rate: 2.1 tasks per day (average)
└─ Trend: Rapidly Increasing 🔴

Complexity Growth:
├─ Original Complexity: 340 points
├─ Current Complexity: 512 points
├─ Difference: +172 points (+50.6%)
└─ Average Task Complexity: 4.0 → 4.0 (stable)

Effort Growth:
├─ Original Estimate: 480 hours
├─ Current Estimate: 720 hours (est.)
├─ Difference: +240 hours (+50%)
└─ Impact on Timeline: +3 weeks delay (estimated)
```

### Impact Metrics:

```
Original Commitment vs Current State:

                  Original    Current    Impact
├─ Timeline:      4 weeks     6 weeks    +50% delay
├─ Team Size:     3 people    3 people   100% overload
├─ Budget:        $50k        $75k       +50% cost
├─ Quality Risk:  Medium      High       Reduced QA time
├─ Delivery Date: Jan 20      Feb 24     +35 days slip
└─ Completion Probability: 85%   35%     -60% confidence
```

### Features

✅ **Automatic Baseline Capture** - Snapshots scope when tracking starts  
✅ **Continuous Monitoring** - Tracks all scope changes in real-time  
✅ **Intelligent Alerts** - Notifies on significant scope changes  
✅ **Visual Trends** - See scope growth over time with charts  
✅ **Impact Analysis** - Understand impact on timeline and resources  
✅ **Detailed Reporting** - Generate comprehensive scope reports  
✅ **Recommendations** - AI suggests scope management actions  
✅ **Historical Comparison** - Compare to similar past projects  
✅ **Change Audit Trail** - Track who added/removed what and when  

---

## 🚨 **Automated Conflict Detection & Resolution**

**Automatically detect and resolve resource, schedule, and dependency conflicts before they derail your projects.**

### What It Detects

**Resource Conflicts**
- Same person assigned to multiple tasks at the same time
- Team members overbooked beyond capacity
- Critical skills bottlenecks (one person is the only expert)
- Conflicting assignment requests
- Workload imbalances across team

**Schedule Conflicts**
- Task deadlines that overlap with dependencies
- Impossible timelines (due date before task can realistically start)
- Critical path delays due to resource unavailability
- Sprint commitments exceeding team capacity
- Meeting overload preventing task work

**Dependency Conflicts**
- Circular dependencies (Task A depends on B, B depends on A)
- Broken dependency chains (Task depends on cancelled task)
- Missing dependencies (task assumes prior work that isn't tracked)
- Critical path bottlenecks (one task blocks multiple others)
- External dependency risks

### How It Works

**Automatic Detection:**
1. PrizmAI continuously scans your board for conflicts
2. AI analyzes: assignments, due dates, dependencies, team capacity
3. Conflicts are scored by severity (Critical, High, Medium, Low)
4. Dashboard shows all active conflicts with impact analysis
5. Real-time alerts notify team members of new conflicts

**AI-Powered Suggestions:**

For each detected conflict, AI generates multiple resolution options with reasoning and confidence scores.

### Example: Resource Conflict

```
Conflict: Jane assigned to 3 simultaneous tasks
Severity: 🔴 CRITICAL
Impact: Will miss all deadlines, team blocked

🤖 AI Suggestions:
1. Reassign "Mobile UI" to Tom
   ├─ Confidence: 88%
   ├─ Reasoning: Tom completed similar work 15% faster
   ├─ Impact: Jane has capacity, Tom handles 40% of work
   └─ Risk: Tom not familiar with design system

2. Extend "API Integration" deadline by 3 days
   ├─ Confidence: 92%
   ├─ Reasoning: Current deadline gives only 2 days/task
   ├─ Impact: Realistic timeline, all work completes on schedule
   └─ Risk: Client communication needed

3. Split "Authentication" into 2 subtasks
   ├─ Confidence: 78%
   ├─ Reasoning: Can parallelize OAuth & JWT implementation
   ├─ Impact: Jane + Bob work together, faster completion
   └─ Risk: Requires coordination overhead
```

### Features

✅ **Automatic Detection** - Continuously scans for conflicts  
✅ **AI Suggestions** - Multiple resolution options with reasoning  
✅ **Confidence Scoring** - Understand reliability of each suggestion  
✅ **Smart Learning** - System learns which resolutions work for your team  
✅ **Real-time Alerts** - Proactive notifications of emerging conflicts  
✅ **Prevention Mode** - Warns before conflicts happen  
✅ **Outcome Tracking** - Learns from results of applied resolutions  

---

## 💰 **Budget & ROI Tracking with AI Optimization**

**Control your project finances and maximize return on investment with intelligent budget management.**

### What You Get

**Budget Management Dashboard:**
- Set and track project budgets with real-time utilization monitoring
- Multi-currency support (USD, EUR, GBP, INR, JPY)
- Automatic status alerts (OK/Warning/Critical/Over Budget)
- Visual budget health indicators with percentage utilization
- Configure warning (80%) and critical (95%) thresholds

**Cost Tracking:**
- Track task-level estimated and actual costs
- Log time spent on tasks with automatic labor cost calculation
- Separate tracking for resource and material costs
- Cost variance analysis (compare estimated vs. actual)
- Calculate average cost per completed task

**ROI Analysis:**
- Create point-in-time ROI snapshots
- Track expected vs. realized project value
- Automatic ROI calculation: (Value - Cost) / Cost × 100
- Compare ROI performance across historical snapshots
- Cost per task ROI metrics and efficiency analysis

**Burn Rate & Overrun Prediction:**
- Calculate daily spending rate and trend analysis
- Predict budget exhaustion date with accuracy
- Sustainability warnings when burn rate is unsustainable
- Days remaining calculations with real-time updates
- Cost overrun prediction before it happens

### AI-Powered Intelligence

**Budget Health Analysis:**
Comprehensive AI assessment of your project budget with:
- Health rating: Excellent / Good / Concerning / Critical
- Risk identification and severity analysis
- Positive indicators highlighting what's working
- Immediate action recommendations
- Trend analysis based on historical data

**Smart Recommendations:**
The AI generates 3-7 targeted recommendations for each analysis, including:
1. Budget Reallocation - Optimize budget distribution across work areas
2. Scope Reduction - Identify scope cuts to stay within budget
3. Timeline Adjustment - Timeline changes to optimize costs
4. Resource Optimization - Better resource allocation strategies
5. Risk Mitigation - Address financial risks proactively
6. Efficiency Improvement - Process improvements to reduce costs

Each recommendation includes:
- Confidence score (0-100%)
- Estimated cost savings
- Priority level (Low / Medium / High / Urgent)
- AI reasoning and supporting data patterns
- Implementation difficulty assessment

### Real-World Example

```
Project: Mobile App Release - Budget: $150,000

Current Status:
├─ Spent: $98,500 (65.7%)
├─ Remaining Budget: $51,500
├─ Burn Rate: $4,200/day
├─ Projected Completion: Dec 22 (12 days away)
├─ Projected Cost: $148,900
└─ Status: ⚠️ WARNING (approaching budget limit)

AI Analysis:
├─ Health: Concerning (85% threshold exceeded)
├─ Risk: 72% probability of minor overrun
└─ Days until budget exhaustion: 12.3 days

🤖 AI Recommendations:
1. [HIGH PRIORITY] Reduce scope on mobile-only features
   • Estimated Savings: $15,000
   • Impact: 3-day timeline acceleration
   • Confidence: 88%
```

---

## 🎓 **AI-Powered Retrospectives**

**Capture organizational learning and drive continuous improvement across every sprint and project.**

Every board has a built-in retrospective system that automatically analyzes:

- 🤖 What went well this sprint/project
- 🤖 What needs improvement
- 🤖 Key achievements and challenges
- 🤖 Lessons learned with impact scoring
- 🤖 Actionable improvement recommendations
- 🤖 Team sentiment and morale indicators

### Features

✅ **AI-Generated Insights** - Automatic analysis of what worked  
✅ **Lessons Tracking** - Capture and track learning  
✅ **Action Items** - Convert lessons into concrete actions  
✅ **Implementation Monitoring** - See if improvements stick  
✅ **Trend Analysis** - Track improvement over time  
✅ **Recurring Issues** - Identify patterns needing attention  
✅ **Team Sentiment** - Measure morale and satisfaction  
✅ **Explainable Analysis** - Understand AI recommendations  
✅ **Multiple Retrospective Types** - Sprint, Project, Milestone, Quarterly  
✅ **Progress Dashboard** - See organization-wide improvements  

---

## 🧠 **AI-Mediated Skill Gap Analysis**

**Automatically identify skill shortages before they block your team's progress.**

### How It Works

**1. Automatic Skill Extraction**

When you create tasks, PrizmAI automatically extracts required skills from task descriptions.

**2. Team Skill Profiling**

PrizmAI builds a profile of your team's current skills across all experience levels.

**3. Gap Identification & Quantification**

The system compares required skills against available skills and identifies gaps:

```
Skill Gap Report - Mobile App Development Project

Critical Gap: React Native
├─ Required: 2 people at Advanced level
├─ Available: 0 people
├─ Gap: Need 2 more
├─ Severity: CRITICAL - Cannot proceed
├─ Affected Tasks: 8 (App UI, Navigation, Testing)
└─ Impact: 40+ hours of blocked work
```

### AI-Generated Recommendations

For each skill gap, PrizmAI recommends concrete actions:

1. **HIRE** (Fastest Resolution)
   - Timeline and cost estimates
   - Risk assessment
   - Market rate analysis

2. **TRAINING** (Develop Internal Talent)
   - Training programs and timeline
   - Productivity impact calculations
   - Success metrics

3. **CONTRACTOR + TRAINING** (Balanced Approach)
   - Expert mentoring model
   - Knowledge transfer strategy
   - Budget and timeline

4. **REDISTRIBUTE** (Use Existing Skills)
   - Team reconfiguration options
   - Quality and timeline implications

### Features

✅ **Automatic Detection** - No manual data entry required  
✅ **Continuous Monitoring** - Gaps update as team skills change  
✅ **AI Recommendations** - Concrete solutions (hire, train, redistribute)  
✅ **Development Plans** - Track progress on closing gaps  
✅ **Affected Tasks View** - See impact of each gap  
✅ **Team Skill Matrix** - Visual view of all team capabilities  
✅ **Historical Trends** - Track skill development over time  
✅ **Notifications** - Get alerted when gaps emerge or resolve  
✅ **Explainable Analysis** - Understand why gaps exist and how to fix them  
✅ **Cost/Timeline Estimates** - Make budget and planning decisions  

---

## 📊 **Smart Recommendations**

PrizmAI provides intelligent recommendations throughout the system:

### Smart Column Suggestions
When creating a new board, AI recommends the perfect columns for your project type based on industry best practices.

### Auto-Generate Task Details
Instead of writing vague task titles, AI auto-generates detailed checklists, acceptance criteria, and specifications.

### Meeting Transcripts → Tasks
Upload meeting notes or transcripts. AI automatically:
- Identifies action items
- Creates tasks from them
- Suggests priorities
- Assigns to team members

### Smart Comment Summaries
Long comment threads? Click "Summarize" and get a concise summary of the key points and decisions.

---

## 🤖 **Intelligent AI Assistants for Wiki Pages**

**Two Specialized AI Assistants - Configured by Category**

PrizmAI features **category-based AI assistants** that adapt to your documentation type.

### 📊 Meeting Analysis AI
*For meeting notes, retrospectives, and discussion documentation*

**What It Does:**
- Extracts action items and deliverables from meeting notes
- Identifies decisions made and their owners
- Creates actionable tasks automatically from discussions
- Tracks follow-ups and commitments
- Summarizes key points and next steps
- Assigns priorities to action items

### 📖 Documentation Assistant AI
*For general documentation, guides, and reference materials*

**What It Does:**
- Summarizes technical documentation
- Extracts actionable suggestions for improvement
- Identifies knowledge gaps and missing information
- Suggests related documentation to create
- Assesses documentation quality and completeness
- Provides recommendations for clarity

### How Category-Based AI Works

**1. Configure Categories:**
When creating or editing a wiki category, select the AI assistant type:
- **Meeting Analysis** - For collaborative discussions and decisions
- **Documentation Assistant** - For reference materials and guides
- **None** - Disable AI features for this category

**2. Automatic Detection:**
When viewing a wiki page, the correct AI assistant appears based on the page's category. No manual switching needed.

**3. Clear Visual Guidance:**
- **Category badges** show AI type in category lists
- **Info banners** on wiki pages explain which AI is available
- **Sidebar cards** provide quick reference for AI capabilities
- **Icon indicators** differentiate meeting vs documentation analysis

### Why Category-Based Configuration?

✅ **Predictable** - You know exactly which AI will be available  
✅ **Consistent** - All pages in a category use the same AI type  
✅ **User-Controlled** - You decide which AI fits your content  
✅ **No Surprises** - Clear visual indicators throughout the interface  
✅ **Organized** - Natural fit with your existing content structure  

---

## 🎯 **AI-Powered Resource Leveling & Optimization**

**Let AI automatically recommend the best task assignments to balance team workload and maximize productivity.**

### How AI Resource Optimization Works

PrizmAI analyzes five key factors to recommend the best person for each task:

```
Assignment Score Calculation:

Skill Match (30%)
├─ How well does the person's skills match the task requirements?
├─ Based on: Task keywords vs. person's work history
└─ Example: Task mentions "React" → Jane has completed 15 React tasks

Availability (25%)
├─ How much free capacity does this person have?
├─ Based on: Current workload, active tasks, estimated hours
└─ Example: Alice has 2 tasks (40% capacity) → very available

Velocity (20%)
├─ How fast does this person complete similar tasks?
├─ Based on: Historical completion times
└─ Example: Jane completes feature work in 3 days avg → fast

Reliability (15%)
├─ How consistently does this person hit deadlines?
├─ Based on: On-time task completion rate
└─ Example: Bob completes 95% of tasks on time → very reliable

Quality (10%)
├─ How high-quality is their work?
├─ Based on: Task reopens, revisions needed, code quality
└─ Example: Sarah rarely needs revisions → high quality

Overall Confidence = (Skill×0.30) + (Availability×0.25) + 
                     (Velocity×0.20) + (Reliability×0.15) + (Quality×0.10)
```

### Real-World Example

```
Task: "Create onboarding tutorial"

AI Recommendations (Ranked):

1. ⭐ Jane Smith - Overall Score: 72.7%
   ├─ Skill Match: 50%
   ├─ Availability: 87.5%
   ├─ Velocity: 100%
   ├─ Reliability: 65.8%
   └─ Quality: 60%

2. ⭐⭐ Bob Martinez - Overall Score: 73.7%
   ├─ Skill Match: 50%
   ├─ Availability: 87.5%
   ├─ Velocity: 100%
   ├─ Reliability: 72.4%
   └─ Quality: 60%

3. Carol Anderson - Overall Score: 68.2%
   ├─ Skill Match: 75%
   ├─ Availability: 20%
   ├─ Velocity: 85%
   ├─ Reliability: 71%
   └─ Quality: 65%
```

### Smart Features

**1. Workload Balancing**
- AI tracks active tasks per person and estimated hours
- Recommends assignments that prevent overload
- Shows capacity warnings ("Alice is at 85% capacity")
- Suggests reassignment when someone becomes overloaded

**2. Skill Gap Awareness**
- Identifies when task requirements don't match available skills
- Suggests pairing experienced/novice for skill transfer
- Flags critical skills that no one has
- Recommends training opportunities

**3. Team Capacity Forecasting**
- Shows predicted team utilization for the next 1-2 weeks
- Identifies bottlenecks before they happen
- Suggests task priorities to prevent overload
- Warns when deadline is at risk due to capacity

**4. Cross-Training Opportunities**
- Identifies tasks that develop team skills
- Suggests assignments that stretch people's abilities
- Balances growth opportunities across the team
- Prevents knowledge silos

### Benefits

✅ **Faster Decisions** - Stop debating who should do this task  
✅ **Better Balance** - Team workload stays even, no heroes  
✅ **Higher Quality** - Tasks go to people with right skills  
✅ **Faster Delivery** - People work at full capacity, not overloaded  
✅ **Better Development** - Growth opportunities distributed fairly  
✅ **Fewer Conflicts** - Transparent, data-driven assignments  
✅ **Reduced Burnout** - No one consistently overloaded  

---

**← Back to [README.md](README.md)**
