# AI-Powered Retrospective Generator - Quick Start Guide

## What is it?

An AI-powered feature that automatically generates comprehensive sprint/project retrospectives by analyzing your project data using Google Gemini AI.

## Key Benefits

✅ **Automated Analysis** - AI analyzes your project metrics and generates insights in 10-30 seconds  
✅ **Organizational Learning** - Captures lessons learned and tracks improvements over time  
✅ **Actionable Recommendations** - Generates prioritized action items with owners and due dates  
✅ **Trend Tracking** - Shows improvement rates, recurring issues, and performance trends  
✅ **Reduced Meeting Time** - Pre-generates insights so teams can focus on discussion  

## Quick Start

### 1. Generate Your First Retrospective

1. Navigate to your board
2. Click **"Retrospectives"** in the navigation
3. Click **"Generate New Retrospective"**
4. Select date range (e.g., last 2 weeks)
5. Choose type (Sprint, Project, Milestone, or Quarterly)
6. Click **"Generate"** and wait 10-30 seconds
7. Review AI-generated insights

### 2. What You'll Get

**AI generates:**
- ✅ What went well (successes and achievements)
- ⚠️ What needs improvement (challenges and blockers)
- 📚 Lessons learned (categorized and prioritized)
- 🎯 Key achievements and milestones
- 🚧 Challenges faced with impact assessment
- 💡 Improvement recommendations (actionable items)
- 😊 Team sentiment and morale indicators
- 📊 Performance trend analysis

### 3. Review & Finalize

1. Review the AI-generated content
2. Add team notes from your retrospective meeting
3. Click **"Finalize"** to lock the retrospective
4. Assign action items to team members
5. Track implementation of lessons learned

### 4. Track Progress

**Dashboard shows:**
- Total retrospectives conducted
- Implementation rate of lessons learned
- Action item completion rate
- Recurring issues across sprints
- Velocity and quality trends
- Urgent pending actions

## Access Points

### From Board View
```
Board Detail → "Retrospectives" button
```

### URLs
- List: `/board/{board_id}/retrospectives/`
- Dashboard: `/board/{board_id}/retrospectives/dashboard/`
- Create: `/board/{board_id}/retrospectives/create/`
- Lessons: `/board/{board_id}/lessons/`

## Features at a Glance

### 📝 Retrospective Management
- Generate AI-powered retrospectives
- View detailed analysis with metrics
- Export retrospectives (JSON format)
- Add team notes and finalize
- Link to meeting transcripts

### 📚 Lessons Learned
- Categorized lessons (10 categories)
- Priority levels (critical, high, medium, low)
- Status tracking (identified → implemented → validated)
- Recurring issue detection
- AI confidence scores
- Action owner assignment

### 📊 Improvement Metrics
- Track key metrics over time
- Automatic trend calculation
- Comparison with previous periods
- Visual progress indicators
- Target vs actual tracking

### ✅ Action Items
- AI-generated recommendations
- Priority and type classification
- Assignment and due dates
- Progress tracking (0-100%)
- Blocking status management
- Link to related tasks

### 📈 Trend Analysis
- Implementation and completion rates
- Recurring issues identification
- Velocity and quality trends
- Top improvement categories
- Historical comparisons

## Example Workflow

**Week 1-2: Sprint Work**
- Team works on tasks as usual
- All activity is tracked automatically

**End of Week 2: Retrospective**
1. Generate retrospective (10-30 sec)
2. Hold team retrospective meeting
3. Review AI insights together
4. Add team notes and discussion points
5. Finalize retrospective

**Week 3+: Implementation**
- Track action items completion
- Mark lessons as implemented
- Monitor improvement metrics
- See trends over time

## Best Practices

### 🎯 Regular Cadence
Generate retrospectives consistently:
- Sprints: Every 1-2 weeks
- Projects: At major milestones
- Quarterly: Every 3 months

### 👥 Team Involvement
- Review AI insights together
- Add team notes and feedback
- Assign action item owners
- Follow up on implementation

### 📊 Track Progress
- Update lesson statuses regularly
- Complete action items on time
- Review dashboard monthly
- Address recurring issues

### 🔄 Continuous Improvement
- Compare trends over time
- Celebrate improvements
- Focus on high-priority lessons
- Iterate based on data

## Technical Details

**AI Model:** Google Gemini 2.0 Flash  
**Analysis Time:** 10-30 seconds  
**Data Analyzed:**
- Task completion rates
- Team velocity
- Quality metrics
- Risk indicators
- Scope changes
- Historical trends

**Generated Insights:**
- Natural language analysis
- Categorized recommendations
- Priority classifications
- Sentiment analysis
- Trend predictions

## Admin Access

Administrators can:
- View all retrospectives in Django admin
- Mark retrospectives as reviewed/finalized
- Manage lessons and actions
- Run trend analyses
- Export data

Access: `/admin/kanban/projectretrospective/`

## Need Help?

### Troubleshooting
- **No insights generated?** Check date range includes task data
- **AI errors?** Verify GEMINI_API_KEY in settings
- **Permissions error?** Ensure you're a board member

### Documentation
- Full guide: `AI_RETROSPECTIVE_IMPLEMENTATION.md`
- Admin panel: Django admin interface
- API docs: View source code docstrings

## Feature Components

**Models (5):**
- ProjectRetrospective
- LessonLearned
- ImprovementMetric
- RetrospectiveActionItem
- RetrospectiveTrend

**Views (9):**
- List, Create, Detail, Dashboard
- Finalize, Export
- Lessons list
- Status update APIs

**Templates (4):**
- List, Create, Detail, Dashboard views

**Admin (5):**
- Full admin interfaces for all models
- Custom actions and filters

## Integration

Works seamlessly with:
- ✅ Task management
- ✅ Burndown predictions
- ✅ Velocity tracking
- ✅ Scope monitoring
- ✅ Risk management
- ✅ Team analytics

## Success Metrics

Track your improvement:
- **Implementation Rate** - % of lessons implemented
- **Completion Rate** - % of actions completed
- **Velocity Trend** - Team speed over time
- **Quality Trend** - Defect rate reduction
- **Recurring Issues** - Problems being resolved

---

**Ready to start?** Navigate to your board and click "Retrospectives"! 🚀
