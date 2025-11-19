# Skill Matching Architecture Diagram

```
┌─────────────────────────────────────────────────────────────────────────┐
│                     RESOURCE SKILL MATCHING SYSTEM                      │
└─────────────────────────────────────────────────────────────────────────┘

                              ┌──────────────┐
                              │  User Input  │
                              │  Task Desc   │
                              └──────┬───────┘
                                     │
                                     ▼
        ┌────────────────────────────────────────────────────┐
        │         AI SKILL EXTRACTION                         │
        │  ┌──────────────────────────────────────────┐      │
        │  │  Google Gemini 1.5 Flash                 │      │
        │  │  • Parse task title & description        │      │
        │  │  • Extract technical skills              │      │
        │  │  • Identify proficiency levels           │      │
        │  │  • Return structured JSON                │      │
        │  └──────────────────────────────────────────┘      │
        └────────────────────┬───────────────────────────────┘
                             │
                             ▼
        ┌──────────────────────────────────────────────────────┐
        │    SKILL REQUIREMENTS (Task Model)                   │
        │    required_skills: [                                │
        │      {"name": "Python", "level": "Expert"},          │
        │      {"name": "Django", "level": "Intermediate"}     │
        │    ]                                                 │
        └──────────────────┬───────────────────────────────────┘
                           │
        ┌──────────────────┴────────────────────┐
        │                                        │
        ▼                                        ▼
┌─────────────────────┐              ┌──────────────────────┐
│  TEAM SKILL PROFILE │              │   GAP ANALYSIS       │
│  ──────────────────  │              │  ──────────────────  │
│  • Aggregate team   │◄─────────────┤  • Compare required  │
│    skills           │              │    vs available      │
│  • Track capacity   │              │  • Calculate gaps    │
│  • Monitor util%    │              │  • Assess severity   │
└──────────┬──────────┘              └──────────┬───────────┘
           │                                     │
           ▼                                     ▼
┌────────────────────┐              ┌────────────────────────┐
│  SKILL INVENTORY   │              │   SKILL GAP RECORDS    │
│  ────────────────   │              │   ─────────────────    │
│  Python:           │              │   Gap: Python (Expert) │
│    Expert: 2       │              │   Required: 2          │
│    Advanced: 3     │              │   Available: 0         │
│    Intermediate: 1 │              │   Severity: CRITICAL   │
└────────────────────┘              └────────────┬───────────┘
                                                 │
                                                 ▼
                              ┌────────────────────────────────┐
                              │  AI RECOMMENDATION ENGINE      │
                              │  ──────────────────────────     │
                              │  Analyze gap → Generate plans: │
                              │  • Training (30-90 days)       │
                              │  • Hiring (60-90 days)         │
                              │  • Redistribution (7-14 days)  │
                              │  • Mentorship (30-60 days)     │
                              └────────────────┬───────────────┘
                                               │
                                               ▼
                              ┌────────────────────────────────┐
                              │  DEVELOPMENT PLANS             │
                              │  ──────────────────────────     │
                              │  • Track progress (0-100%)     │
                              │  • Monitor costs & timeline    │
                              │  • Measure impact              │
                              │  • Update skill profiles       │
                              └────────────────┬───────────────┘
                                               │
                                               ▼
                              ┌────────────────────────────────┐
                              │  CONTINUOUS IMPROVEMENT        │
                              │  • Skills updated              │
                              │  • Gaps resolved               │
                              │  • Team capacity grows         │
                              └────────────────────────────────┘


═══════════════════════════════════════════════════════════════════════════
                            DATA FLOW EXAMPLE
═══════════════════════════════════════════════════════════════════════════

1. TASK CREATION
   ──────────────
   User creates: "Build machine learning pipeline for customer churn prediction"
   
   ↓ AI Extraction
   
   Extracted Skills:
   • Python (Expert)
   • TensorFlow (Intermediate)
   • Data Analysis (Advanced)
   • SQL (Intermediate)

2. TEAM SKILL PROFILE
   ───────────────────
   Current Team (8 members):
   • Python: 2 Expert, 3 Intermediate
   • TensorFlow: 1 Intermediate, 2 Beginner
   • Data Analysis: 1 Advanced, 2 Intermediate
   • SQL: 3 Advanced, 4 Intermediate

3. GAP ANALYSIS
   ────────────
   ✓ Python: Sufficient (2 experts available)
   ✗ TensorFlow: GAP! Need 1 Intermediate, only have Beginners
   ✓ Data Analysis: Sufficient (1 advanced available)
   ✓ SQL: Sufficient (3 advanced available)

4. AI RECOMMENDATIONS
   ──────────────────
   Gap: TensorFlow (Intermediate) - Need 1 more
   
   Recommendation #1 (Priority: 8/10)
   ├─ Type: Training
   ├─ Action: Upskill 1 beginner to intermediate
   ├─ Timeline: 45 days
   ├─ Cost: $2,000 (online course + practice time)
   └─ Impact: Enables ML pipeline development
   
   Recommendation #2 (Priority: 9/10)
   ├─ Type: Hiring
   ├─ Action: Hire ML engineer with TensorFlow expertise
   ├─ Timeline: 60 days
   ├─ Cost: $100,000/year
   └─ Impact: Immediate capability + knowledge transfer

5. DEVELOPMENT PLAN CREATED
   ─────────────────────────
   Plan: "TensorFlow Training Program"
   ├─ Type: Training
   ├─ Target: John Doe (currently Beginner)
   ├─ Start: Dec 1, 2025
   ├─ Target End: Jan 15, 2026
   ├─ Progress: 0% → 25% → 50% → 75% → 100%
   └─ Success: Task completed successfully!

6. SKILL GAP RESOLVED
   ───────────────────
   Status: RESOLVED
   Team now has: 2 TensorFlow Intermediate members
   Gap closed in: 45 days
   Tasks unblocked: 3


═══════════════════════════════════════════════════════════════════════════
                        MATCH SCORING EXAMPLE
═══════════════════════════════════════════════════════════════════════════

Task Requirements:
├─ Python (Expert) = 4 points
├─ Django (Advanced) = 3 points
└─ PostgreSQL (Intermediate) = 2 points
   Total Required: 9 points

Team Member: Alice Johnson
├─ Python (Expert) = 4 points ✓ (100% match)
├─ Django (Expert) = 4 points ✓ (100% match, exceeds requirement)
├─ PostgreSQL (Beginner) = 1 point ⚠ (70% partial match = 0.7)
└─ Total Matched: 8.7 points

Match Score: (8.7 / 9) × 100 = 97% 🌟

Team Member: Bob Smith
├─ Python (Intermediate) = 2 points ⚠ (70% partial = 1.4)
├─ Django (Advanced) = 3 points ✓ (100% match)
├─ PostgreSQL (Missing) = 0 points ✗
└─ Total Matched: 4.4 points

Match Score: (4.4 / 9) × 100 = 49% ⚠️

Result: Alice is the best match (97% vs 49%)


═══════════════════════════════════════════════════════════════════════════
                       KEY METRICS & THRESHOLDS
═══════════════════════════════════════════════════════════════════════════

TEAM UTILIZATION
├─ Healthy: 0-75% (Green)
├─ Warning: 76-90% (Yellow)
└─ Critical: 91-100%+ (Red)

GAP SEVERITY
├─ Low: Affects 1 task, small impact
├─ Medium: Affects 2-4 tasks
├─ High: Affects 5+ tasks OR gap ≥ 2 people
└─ Critical: Expert/Advanced gap ≥ 2 OR blocks critical path

MATCH QUALITY
├─ Excellent: 90-100%
├─ Good: 75-89%
├─ Fair: 60-74%
└─ Poor: <60%

RECOMMENDATION PRIORITY
├─ 10: Business-critical, immediate action
├─ 8-9: High priority, 1-2 week action
├─ 5-7: Medium priority, 2-4 week action
└─ 1-4: Low priority, monitor

```

## System Components

### 1. **AI Layer**
- Google Gemini 1.5 Flash for NLP
- Skill extraction from unstructured text
- Recommendation generation
- Confidence scoring

### 2. **Data Layer**
- TeamSkillProfile: Aggregate team capabilities
- SkillGap: Identified deficiencies
- SkillDevelopmentPlan: Action tracking
- Task.required_skills: Demand signal
- UserProfile.skills: Supply signal

### 3. **Business Logic**
- `calculate_skill_gaps()`: Gap analysis algorithm
- `match_team_member_to_task()`: Matching algorithm
- `generate_skill_gap_recommendations()`: AI advisor
- `build_team_skill_profile()`: Aggregation engine

### 4. **API Layer**
7 RESTful endpoints for frontend integration

### 5. **UI Layer**
- Interactive skill gap dashboard
- Skill matrix heatmap
- Development plan tracker
- Team member matcher

## Integration Points

```
Task Creation → Auto Skill Extraction → Update Requirements
     ↓
User Profile → Manual Skills Entry → Update Team Profile
     ↓
Sprint Planning → Run Gap Analysis → Generate Recommendations
     ↓
Create Dev Plan → Track Progress → Update Skills → Close Gap
     ↓
Task Assignment → Match Algorithm → Suggest Best Fit → Assign
```
