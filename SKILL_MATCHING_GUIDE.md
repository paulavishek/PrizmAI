# Resource Skill Matching with Gap Analysis - Implementation Guide

## 🎯 Overview

The **Resource Skill Matching with Gap Analysis** feature provides AI-powered skill management to help teams proactively identify skill gaps, optimize resource allocation, and plan workforce development.

## 🌟 Key Features

### 1. **AI Skill Extraction**
- Automatically extract required skills from task titles and descriptions
- Maps technical skills, tools, frameworks, and proficiency levels
- Uses Google Gemini AI for intelligent skill detection

### 2. **Team Skill Profiling**
- Aggregates team-wide skill inventory
- Tracks proficiency levels (Beginner → Expert)
- Monitors capacity utilization across the team

### 3. **Gap Analysis**
- Compares required skills vs. available skills
- Quantifies gaps (e.g., "Need 2 more Python experts")
- Prioritizes gaps by severity (Low → Critical)

### 4. **AI-Powered Recommendations**
- Generates actionable plans: Training, Hiring, Redistribution
- Estimates timeframes, costs, and priorities
- Tracks implementation progress

### 5. **Skill Development Tracking**
- Monitor training initiatives and hiring progress
- Measure skill improvement over time
- Track ROI on development investments

---

## 📊 Data Models

### TeamSkillProfile
Aggregated skill inventory for a board/team.

**Key Fields:**
- `skill_inventory`: Dictionary of available skills with proficiency breakdown
- `total_capacity_hours`: Team's total weekly capacity
- `utilized_capacity_hours`: Currently allocated hours
- `utilization_percentage`: Real-time utilization metric

### SkillGap
Identified gaps between required and available skills.

**Key Fields:**
- `skill_name`: The missing/insufficient skill
- `proficiency_level`: Required level (Beginner/Intermediate/Advanced/Expert)
- `gap_count`: Number of additional resources needed
- `severity`: Low/Medium/High/Critical
- `affected_tasks`: Tasks blocked by this gap
- `ai_recommendations`: AI-generated solutions

### SkillDevelopmentPlan
Action plans to address skill gaps.

**Plan Types:**
- `training`: Upskill existing team members
- `hiring`: Recruit new talent
- `contractor`: Engage external resources
- `redistribute`: Adjust workload distribution
- `mentorship`: Pair programming/coaching
- `cross_training`: Multi-skill development

---

## 🔧 API Endpoints

### 1. Analyze Skill Gaps
```http
GET /kanban/api/skill-gaps/analyze/{board_id}/?sprint_days=14
```

**Purpose:** Run AI analysis to identify skill gaps for upcoming work.

**Query Parameters:**
- `sprint_days` (optional): Lookahead period (default: 14 days)

**Response:**
```json
{
  "success": true,
  "gaps": [
    {
      "id": 1,
      "skill_name": "Python",
      "proficiency_level": "Expert",
      "required_count": 2,
      "available_count": 0,
      "gap_count": 2,
      "severity": "critical",
      "status": "identified",
      "affected_tasks": [
        {"id": 101, "title": "Build ML pipeline", "level": "Expert"}
      ],
      "recommendations": [
        {
          "type": "hiring",
          "title": "Hire Python expert",
          "description": "Recruit 2 senior Python developers...",
          "timeframe_days": 60,
          "cost_estimate": "high",
          "priority": 9
        }
      ]
    }
  ],
  "sprint_period_days": 14,
  "total_gaps": 1
}
```

---

### 2. Get Team Skill Profile
```http
GET /kanban/api/team-skill-profile/{board_id}/
```

**Purpose:** Retrieve comprehensive team skill inventory.

**Response:**
```json
{
  "success": true,
  "team_size": 8,
  "total_capacity_hours": 320,
  "utilized_capacity_hours": 256,
  "utilization_percentage": 80.0,
  "skills": [
    {
      "skill_name": "Python",
      "total_members": 5,
      "expert": 2,
      "advanced": 2,
      "intermediate": 1,
      "beginner": 0,
      "members": [
        {"user_id": 1, "username": "john", "level": "Expert"}
      ]
    }
  ],
  "total_unique_skills": 23
}
```

---

### 3. Match Team to Task
```http
POST /kanban/api/task/{task_id}/match-team/
```

**Purpose:** Find best-fit team members for a task based on skill matching.

**Response:**
```json
{
  "success": true,
  "task_id": 101,
  "task_title": "Build ML pipeline",
  "required_skills": [
    {"name": "Python", "level": "Expert"},
    {"name": "TensorFlow", "level": "Intermediate"}
  ],
  "matches": [
    {
      "user_id": 5,
      "username": "alice",
      "full_name": "Alice Johnson",
      "match_score": 95,
      "matched_skills": [
        {
          "name": "Python",
          "required_level": "Expert",
          "member_level": "Expert",
          "match_quality": "exact"
        },
        {
          "name": "TensorFlow",
          "required_level": "Intermediate",
          "member_level": "Advanced",
          "match_quality": "exceeds"
        }
      ],
      "missing_skills": [],
      "current_workload": 32,
      "available_hours": 8
    }
  ]
}
```

---

### 4. Extract Task Skills
```http
POST /kanban/api/task/{task_id}/extract-skills/
```

**Purpose:** AI-extract required skills from task description.

**Response:**
```json
{
  "success": true,
  "task_id": 101,
  "skills": [
    {"name": "Python", "level": "Intermediate"},
    {"name": "Django", "level": "Advanced"},
    {"name": "PostgreSQL", "level": "Beginner"}
  ],
  "message": "Extracted 3 skills from task description"
}
```

---

### 5. Create Development Plan
```http
POST /kanban/api/development-plans/create/
```

**Request Body:**
```json
{
  "skill_gap_id": 1,
  "plan_type": "training",
  "title": "Python Advanced Training Program",
  "description": "3-month intensive Python training...",
  "target_user_ids": [3, 7],
  "start_date": "2025-12-01",
  "target_completion_date": "2026-02-28",
  "estimated_cost": 5000.00,
  "estimated_hours": 120,
  "ai_suggested": true
}
```

---

### 6. Get Skill Gaps List
```http
GET /kanban/api/skill-gaps/list/{board_id}/
```

**Purpose:** Retrieve active skill gaps.

---

### 7. Get Development Plans
```http
GET /kanban/api/development-plans/{board_id}/?status=in_progress
```

**Purpose:** Retrieve skill development plans with optional status filter.

---

## 💻 Frontend Integration

### Initialize Skill Gap Analyzer

```html
<!-- In your board detail template -->
<div id="skill-gap-dashboard" data-board-id="{{ board.id }}"></div>

<script src="{% static 'js/skill_gap_analysis.js' %}"></script>
```

The JavaScript will automatically initialize when the page loads.

### Programmatic Usage

```javascript
// Initialize
const analyzer = new SkillGapAnalyzer(boardId);
await analyzer.init();

// Run analysis
await analyzer.analyzeGaps(sprintDays=14);

// Extract skills from task
const skills = await analyzer.extractTaskSkills(taskId);

// Match team to task
const matches = await analyzer.matchTeamToTask(taskId);

// Create development plan
await analyzer.createDevelopmentPlan(gapId, {
    plan_type: 'training',
    title: 'Python Training',
    description: 'Upskill team in Python',
    start_date: '2025-12-01',
    target_completion_date: '2026-03-01'
});
```

---

## 🎨 UI Components

### 1. **Team Overview Card**
Displays:
- Team size
- Total unique skills
- Total capacity
- Current utilization percentage

### 2. **Skill Gaps Section**
Shows:
- Critical & high-priority gaps
- Gap count and severity badges
- Affected task counts
- Quick actions to view details

### 3. **Development Plans Section**
Lists:
- Active and proposed plans
- Progress bars
- Plan types (Training, Hiring, etc.)
- Target team members

### 4. **Skill Matrix Table**
Visual heatmap showing:
- Skills vs. proficiency levels
- Color-coded availability (Green = abundant, Red = scarce)
- Total team members per skill

---

## 🔄 Workflow Example

### Scenario: New Sprint Planning

1. **Run Skill Gap Analysis**
   ```javascript
   await analyzer.analyzeGaps(14); // Analyze next 2 weeks
   ```

2. **Review Identified Gaps**
   - System detects: "Need 1 more React Expert"
   - 3 tasks are affected
   - Severity: HIGH

3. **View AI Recommendations**
   - Option 1: Train intermediate React developer (30 days, medium cost)
   - Option 2: Hire React expert (60 days, high cost)
   - Option 3: Redistribute work (7 days, low cost)

4. **Create Development Plan**
   - Select "Training" recommendation
   - Assign to developer with Intermediate React skills
   - Set timeline: 4 weeks
   - Track progress: 0% → 100%

5. **Monitor Progress**
   - Development plan status updates
   - Skill gap severity decreases as training progresses
   - Team capacity improves

---

## 🧮 Skill Matching Algorithm

### Match Score Calculation

The system uses a weighted scoring algorithm:

```python
Level Weights:
- Beginner: 1 point
- Intermediate: 2 points
- Advanced: 3 points
- Expert: 4 points

Match Quality:
- Exact match: 100% credit
- Exceeds requirement: 100% credit
- Partial match (lower level): 70% credit
- Missing skill: 0% credit

Final Score = (Total Matched Weight / Total Required Weight) × 100
```

### Example

**Task Requirements:**
- Python (Expert) = 4 points
- Django (Intermediate) = 2 points
- **Total Required: 6 points**

**Team Member Skills:**
- Python (Expert) = 4 points ✓
- Django (Beginner) = 1 point (70% credit = 0.7 points)
- **Total Matched: 4.7 points**

**Match Score = (4.7 / 6) × 100 = 78%**

---

## 📈 Analytics & Insights

### Gap Severity Classification

| Severity   | Criteria |
|------------|----------|
| **Critical** | Gap ≥ 3 OR (Gap ≥ 2 AND Expert/Advanced level) |
| **High**     | Gap ≥ 2 OR Affects ≥ 5 tasks |
| **Medium**   | Affects ≥ 2 tasks |
| **Low**      | Affects 1 task |

### Utilization Thresholds

- **🟢 Healthy:** < 75%
- **🟡 Warning:** 75-90%
- **🔴 Critical:** > 90%

---

## 🛠️ Admin Interface

Access via Django Admin at `/admin/kanban/`

### TeamSkillProfile
- View team capacity metrics
- Inspect skill inventory JSON
- Track analysis timestamps

### SkillGap
- Filter by severity, status, board
- View affected tasks
- Read AI recommendations
- Mark as resolved

### SkillDevelopmentPlan
- Track plan progress
- Update status (Proposed → In Progress → Completed)
- Monitor success metrics
- View AI-suggested plans

---

## 🚀 Getting Started

### 1. Run Migrations
```bash
python manage.py migrate
```

### 2. Configure User Skills
Users should add their skills via their profile:
```python
user.profile.skills = [
    {"name": "Python", "level": "Expert"},
    {"name": "Django", "level": "Advanced"},
    {"name": "React", "level": "Intermediate"}
]
user.profile.save()
```

### 3. Auto-Extract Skills from Tasks
For existing tasks:
```python
from kanban.utils.skill_analysis import auto_populate_task_skills
from kanban.models import Task

for task in Task.objects.filter(required_skills=[]):
    auto_populate_task_skills(task)
```

### 4. Run Initial Analysis
```bash
# Via API or Django shell
from kanban.utils.skill_analysis import calculate_skill_gaps
from kanban.models import Board

board = Board.objects.get(id=1)
gaps = calculate_skill_gaps(board, sprint_period_days=14)
```

---

## 🎯 Best Practices

### 1. **Keep Skills Updated**
- Encourage team members to update skills quarterly
- Add new skills as technologies evolve
- Track skill level progression

### 2. **Regular Gap Analysis**
- Run analysis at sprint planning
- Review gaps weekly for large teams
- Address critical gaps immediately

### 3. **Proactive Planning**
- Create development plans for medium+ severity gaps
- Budget for training and hiring based on forecasts
- Track skill development ROI

### 4. **Task Skill Definition**
- Let AI extract skills first, then refine manually
- Be specific (e.g., "React Hooks" not just "JavaScript")
- Include soft skills when relevant (e.g., "Client Communication")

---

## 🐛 Troubleshooting

### No Skills Extracted
- **Issue:** AI returns empty array
- **Solution:** Ensure task description is detailed enough. Add technical terms.

### Low Match Scores
- **Issue:** All team members show <50% match
- **Solution:** Check if required skills are too specific. Consider cross-training.

### API Errors
- **Issue:** 403 Forbidden
- **Solution:** Verify user is board member or creator.

---

## 📚 Additional Resources

- **API Documentation:** `/kanban/api-docs/`
- **Django Admin:** `/admin/kanban/`
- **User Guide:** See `AI_EXPLAINABILITY_USER_GUIDE.md`

---

## 🤝 Support

For issues or feature requests, contact your development team or file an issue in the project repository.

---

**Version:** 1.0.0  
**Last Updated:** November 19, 2025  
**Author:** PrizmAI Development Team
