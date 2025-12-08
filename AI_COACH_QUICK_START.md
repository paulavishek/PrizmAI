# AI Coach for Project Managers - Quick Start Guide

## What It Does

The AI Coach proactively watches your project and helps you:
- 🚨 **Catch problems early** - "Your velocity is dropping"
- ⚠️ **Prevent risks** - "3 high-risk tasks converging"  
- 💡 **Spot opportunities** - "Jane can take on challenging work"
- 📈 **Learn and improve** - Gets better from your feedback

Think of it as an experienced PM looking over your shoulder, ready to help.

## 5-Minute Setup

### 1. Install (One Time)

```bash
# Add models to database
python manage.py makemigrations kanban
python manage.py migrate

# Generate your first suggestions
python manage.py generate_coach_suggestions
```

### 2. Access Dashboard

Go to any board → Look for **"AI Coach"** button or navigate to:
```
/board/{your-board-id}/coach/
```

### 3. Done! 

You'll see suggestions grouped by priority. Red = urgent, Orange = important, etc.

## Daily Workflow

### Morning Routine (2 minutes)
1. Open Coach Dashboard
2. Check critical/high suggestions
3. Acknowledge what you'll act on today
4. Dismiss what's not relevant

### Weekly Practice (5 minutes)
1. Review resolved suggestions from past week
2. Provide feedback on 2-3 suggestions (was it helpful?)
3. Check coaching analytics to see your progress

## Understanding Suggestions

Each suggestion shows:

```
[SEVERITY BADGE] Title
──────────────────────
Message: What's happening and why it matters

Why: The reasoning behind this alert

Actions:
• Step 1
• Step 2  
• Step 3

Impact: What improves if you act on this
```

## Common Suggestions You'll See

### 🔴 Critical

**Risk Convergence**
- 3+ high-risk tasks due same week
- Action: Create mitigation plan, stagger if possible

**Deadline at Risk**
- >50% chance of missing deadline
- Action: Cut scope or add resources NOW

### 🟠 High

**Velocity Drop**
- Team completing 30%+ fewer tasks
- Action: Team check-in to find blockers

**Resource Overload**
- Someone has >10 active tasks
- Action: Redistribute work, extend deadlines

### 🔵 Medium

**Scope Creep**
- 15%+ increase in tasks/complexity
- Action: Review what's truly needed

**Quality Issues**
- Many tasks being reopened
- Action: Review definition of done

### 🟢 Low

**Skill Opportunity**
- Team member ready for growth
- Action: Assign stretch assignment

## Providing Feedback

When you act on a suggestion, tell the system what happened:

```
1. Click "Provide Feedback"

2. Answer:
   ☐ Was this helpful? Yes/No
   ⭐ Relevance: 1-5 stars
   
3. What did you do?
   ○ Accepted and applied
   ○ Partially applied
   ○ Modified it
   ○ Ignored
   ○ Not applicable

4. Optional: Describe outcome
   "Did team check-in, velocity improved!"
```

**Why feedback matters**: The AI learns from your responses and gets better at helping YOU specifically.

## Ask the Coach

Got a PM question? Ask the AI:

```
Navigate to: /board/{id}/coach/ask/

Examples:
• "How do I handle this scope creep?"
• "My team velocity is declining, what should I do?"
• "How can I improve our deadline hit rate?"
```

Get personalized advice based on your project context.

## View Your Progress

Check coaching analytics:

```
Navigate to: /board/{id}/coach/analytics/

See:
• How many suggestions you acted on
• Which types help you most
• Your improvement areas
• Coaching effectiveness score
```

## Pro Tips

### For Best Results

✅ **Check daily** - Problems caught early are easier to fix
✅ **Provide feedback** - Helps AI learn what works for you
✅ **Act on high-severity** - These are the "fire alarms"
✅ **Use Ask Coach** - When in doubt, ask!
✅ **Review analytics monthly** - Track your growth

### Common Patterns

📊 **If you see repeated suggestions**
→ Address root cause, not just symptoms

⏱️ **If suggestions feel irrelevant**
→ Provide feedback! System will adapt

🎯 **If overwhelmed by suggestions**
→ Focus on critical/high only at first

## Automated Generation

Suggestions auto-generate when you run:

```bash
python manage.py generate_coach_suggestions
```

**Recommended schedule**:
- Every 6 hours during work day
- Or daily at 9am

Set up with cron/scheduler:
```bash
# crontab example (every 6 hours)
0 */6 * * * cd /path/to/prizmAI && python manage.py generate_coach_suggestions
```

## Troubleshooting

### "No suggestions showing"

1. Check that board has tasks and recent activity
2. Run generation command manually
3. Check Django admin → Coaching Suggestions

### "AI responses not working"

1. Verify `GEMINI_API_KEY` in settings
2. Check logs for API errors
3. Suggestions still work with rules even without AI

### "Too many suggestions"

1. Focus on critical/high severity first
2. Dismiss irrelevant ones (system learns)
3. Consider adjusting thresholds in `coaching_rules.py`

## Example Scenario

### Monday Morning

**Dashboard shows**:
- 🔴 3 high-risk tasks converging this week
- 🟠 Team velocity dropped 35%
- 🟢 Sarah has capacity for more work

**You act**:
1. Create risk mitigation plan for convergence
2. Schedule team check-in for velocity issue
3. Assign Sarah a challenging task

**End of week**:
- Risk mitigation worked - all tasks completed
- Team check-in identified blocker, velocity recovering
- Sarah appreciated the growth opportunity

**You provide feedback**:
- Risk suggestion: ⭐⭐⭐⭐⭐ "Critical - prevented crisis"
- Velocity suggestion: ⭐⭐⭐⭐ "Helpful - found root cause"
- Skill suggestion: ⭐⭐⭐⭐ "Good - team member happy"

**System learns**:
- Risk convergence suggestions work well for you
- Velocity suggestions help you catch issues early
- Skill opportunities align with your management style

**Next week**:
- Similar suggestions appear earlier
- Confidence scores adjusted based on your feedback
- New patterns detected and flagged

## Integration with Other Features

The AI Coach works with:

- **Burndown Predictions** - Deadline risk suggestions
- **Velocity Tracking** - Velocity drop alerts
- **Risk Assessment** - Risk convergence detection
- **Scope Tracking** - Scope creep warnings
- **Skill Matching** - Skill development opportunities

It's the "intelligent layer" that connects all your project data.

## For New PMs

If you're new to project management:

1. **Week 1**: Just read suggestions, don't stress about acting on everything
2. **Week 2**: Start acknowledging and dismissing suggestions
3. **Week 3**: Act on 1-2 high-severity suggestions
4. **Week 4**: Provide feedback, use Ask Coach for questions
5. **Month 2+**: You're now a coaching power user! 🚀

The coach is specifically designed to help less-experienced PMs avoid common mistakes and build skills.

## Getting Help

- **Documentation**: `AI_COACH_IMPLEMENTATION.md` (detailed guide)
- **Django Admin**: View/manage all suggestions
- **Ask Coach**: Ask the AI directly
- **Analytics**: Track what's working for you

## Success Story Template

After using AI Coach for 30 days, you should see:

- ✅ Fewer surprises and "fire drills"
- ✅ Better team velocity stability
- ✅ More deadlines hit on time
- ✅ Improved team satisfaction
- ✅ Your own PM skills growing

Track your metrics in coaching analytics to see the impact!

---

**Remember**: The AI Coach is a tool to help you, not judge you. Every suggestion is an opportunity to improve. The more you use it and provide feedback, the better it gets at helping YOU specifically.

Happy coaching! 🎯
