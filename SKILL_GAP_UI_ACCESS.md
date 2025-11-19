# Skill Gap Analysis - UI Access Points

## 🎯 Where to Find the Feature

### 1. **Board Detail Page** (Main Access)
**Location:** `/boards/{board_id}/`

**Button:** Orange "Skill Gaps" button with brain icon 🧠

**Path:** Board Detail → Top Navigation Bar → "Skill Gaps" button

```
[Back] [Analytics] [Skill Gaps] [Gantt Chart] [Export ▼]
```

---

### 2. **Board Analytics Page** (Alternative Access)
**Location:** `/boards/{board_id}/analytics/`

**Button:** Orange "Skill Gaps" button in navigation

**Path:** Board Detail → Analytics → "Skill Gaps" button

---

### 3. **Direct URL**
**URL:** `/boards/{board_id}/skill-gaps/`

You can bookmark or link directly to the skill gap dashboard for any board.

---

## 📊 What You'll See

### Skill Gap Dashboard Layout

```
┌─────────────────────────────────────────────────────────┐
│  🧠 Skill Gap Analysis - [Board Name]                   │
│  [Back to Board] [Run Analysis]                         │
├─────────────────────────────────────────────────────────┤
│  ┌───────────┐ ┌───────────┐ ┌───────────┐ ┌─────────┐ │
│  │  5 Active │ │ 12 Plans  │ │ 25 Skills │ │  85%    │ │
│  │  Gaps ⚠️  │ │ 📚        │ │ 🔧        │ │ Util.   │ │
│  └───────────┘ └───────────┘ └───────────┘ └─────────┘ │
├─────────────────────────────────────────────────────────┤
│  ┌─────────────────────┐ ┌──────────────────────────┐  │
│  │ ⚠️ SKILL GAPS       │ │ 🎓 DEVELOPMENT PLANS     │  │
│  │                     │ │                          │  │
│  │ • Python (Expert)   │ │ • Python Training        │  │
│  │   Need 2 more       │ │   Progress: 50%         │  │
│  │   [View] [Plan]     │ │   [Details]             │  │
│  │                     │ │                          │  │
│  │ • React (Advanced)  │ │ • Hire React Developer  │  │
│  │   Need 1 more       │ │   Progress: 25%         │  │
│  │   [View] [Plan]     │ │   [Details]             │  │
│  └─────────────────────┘ └──────────────────────────┘  │
├─────────────────────────────────────────────────────────┤
│  📊 TEAM SKILL MATRIX                                   │
│  ┌───────────────────────────────────────────────────┐  │
│  │ Skill      │Expert│Advanced│Inter.│Begin.│Total  │  │
│  │ Python     │  2   │   3    │  1   │  0   │  6    │  │
│  │ React      │  1   │   2    │  3   │  1   │  7    │  │
│  │ Django     │  1   │   1    │  2   │  1   │  5    │  │
│  └───────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────┘
```

---

## 🚀 How to Use

### Step 1: Navigate to Board
1. Go to your board (`/boards/{board_id}/`)
2. Click the **orange "Skill Gaps"** button in the top navigation

### Step 2: Run Analysis
1. Click **"Run Analysis"** button
2. AI will analyze all tasks in the next 2 weeks
3. Gaps will be identified and displayed

### Step 3: Review Gaps
- **Critical gaps** (red border) - Immediate attention needed
- **High gaps** (yellow border) - Address within sprint
- **Medium/Low gaps** - Monitor and plan

### Step 4: View Recommendations
- Click **"View Details"** on any gap
- See AI-generated recommendations
- Choose training, hiring, or redistribution

### Step 5: Create Development Plan
- Click **"Create Plan"** on a gap
- Fill in plan details
- Assign team members
- Track progress

---

## 🎨 Visual Indicators

### Gap Severity Colors
- 🔴 **Red Border** = Critical (need 3+ or expert-level)
- 🟡 **Yellow Border** = High (need 2+ or affects 5+ tasks)
- 🔵 **Blue Border** = Medium (affects 2-4 tasks)
- ⚫ **Gray Border** = Low (affects 1 task)

### Plan Type Icons
- 📚 **Blue Badge** = Training/Upskilling
- ✅ **Green Badge** = Hiring
- 🤝 **Cyan Badge** = Contractor
- 🔄 **Yellow Badge** = Redistribute Work
- 🎓 **Purple Badge** = Mentorship
- 👥 **Gray Badge** = Cross-training

### Progress Bars
- 🟢 **Green** = 75-100% complete
- 🔵 **Blue** = 50-74% complete
- 🟡 **Yellow** = 0-49% complete

---

## 📱 Mobile Access

The dashboard is responsive and works on mobile devices:
- Cards stack vertically
- Tables become scrollable
- Buttons adapt to screen size

---

## 🔗 API Integration

Developers can also access via API:

```javascript
// Analyze gaps
GET /kanban/api/skill-gaps/analyze/{board_id}/?sprint_days=14

// Get team profile
GET /kanban/api/team-skill-profile/{board_id}/

// Match team to task
POST /kanban/api/task/{task_id}/match-team/

// Extract skills from task
POST /kanban/api/task/{task_id}/extract-skills/

// Create development plan
POST /kanban/api/development-plans/create/
```

---

## 🎯 Quick Actions Available

1. **Run Analysis** - Scan for new gaps
2. **View Gap Details** - See affected tasks and recommendations
3. **Create Plan** - Start addressing a gap
4. **View Plan Details** - Track plan progress
5. **Update Progress** - Mark milestones (admin only)

---

## ✅ Checklist for First Use

- [ ] Navigate to board
- [ ] Click "Skill Gaps" button (orange, with brain icon)
- [ ] Click "Run Analysis" to scan for gaps
- [ ] Review identified gaps (if any)
- [ ] View AI recommendations
- [ ] Create development plan for critical gaps
- [ ] Assign team members to plans
- [ ] Track progress regularly

---

## 💡 Pro Tips

1. **Run analysis at sprint planning** - Get ahead of skill bottlenecks
2. **Address critical gaps first** - Don't let them block work
3. **Use AI recommendations** - They're based on industry best practices
4. **Track development** - Update plan progress regularly
5. **Review skill matrix** - Keep team skills updated in profiles

---

## 🆘 Troubleshooting

**Q: Button is not visible?**
- Ensure you're on a board detail or analytics page
- Check that you're a board member or owner

**Q: No gaps showing?**
- Click "Run Analysis" to scan tasks
- Ensure tasks have required_skills populated
- Check that team members have skills in their profiles

**Q: Analysis fails?**
- Check internet connection (AI needs API access)
- Verify GEMINI_API_KEY is configured
- Check browser console for errors

**Q: Can't create plans?**
- Ensure you have board access permissions
- Check that gap exists and is not resolved

---

## 📞 Need Help?

- **Documentation:** See `SKILL_MATCHING_GUIDE.md`
- **Architecture:** See `SKILL_MATCHING_ARCHITECTURE.md`
- **Examples:** See `skill_matching_examples.py`
- **Admin Interface:** `/admin/kanban/`

---

**Last Updated:** November 19, 2025
