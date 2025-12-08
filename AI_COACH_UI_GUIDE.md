# AI Coach - Where to Find It in the UI

## 🎯 Quick Access Locations

### 1. **Main Access: Board Navigation Bar**

When viewing any board, you'll see the **AI Coach** button in the top navigation:

```
Board Detail Page
├── Back
├── Analytics  
├── Burndown
├── ✨ AI Coach  ← HERE!
├── Skill Gaps
├── Gantt Chart
└── Budget
```

**To access:**
1. Go to any board (e.g., `/board/123/`)
2. Look at the top button bar
3. Click the purple **"AI Coach"** button with graduation cap icon 🎓

### 2. **Direct URL Access**

You can also navigate directly via URL:

```
/board/{board_id}/coach/
```

Example: `/board/1/coach/`

## 📊 What You'll See

### Coach Dashboard

When you click "AI Coach", you'll see:

```
┌─────────────────────────────────────────────┐
│ 🎓 AI Coach                    [Back] [Refresh]│
│ Proactive guidance to improve your project  │
├─────────────────────────────────────────────┤
│                                             │
│  ┌─────┐  ┌─────┐  ┌─────┐  ┌─────┐       │
│  │ 85% │  │  3  │  │ 67% │  │ 80% │       │
│  └─────┘  └─────┘  └─────┘  └─────┘       │
│  Effectiveness Active Action Helpful       │
│                                             │
├─────────────────────────────────────────────┤
│ 🔴 Critical Attention Needed                │
│                                             │
│  ┌────────────────────────────────────┐    │
│  │ [CRITICAL] 3 high-risk tasks       │    │
│  │ converging this week               │    │
│  │                                    │    │
│  │ Message: You have 3 high-risk...  │    │
│  │ Why: Multiple high-risk items...  │    │
│  │                                    │    │
│  │ Actions:                           │    │
│  │ → Create risk mitigation plan      │    │
│  │ → Consider staggering deadlines    │    │
│  │                                    │    │
│  │ [Acknowledge] [Feedback] [Dismiss]│    │
│  └────────────────────────────────────┘    │
│                                             │
├─────────────────────────────────────────────┤
│ 🟠 High Priority                            │
│  [Multiple suggestion cards...]             │
│                                             │
├─────────────────────────────────────────────┤
│ 💬 Ask the AI Coach                         │
│  Have a question? Get personalized advice   │
│  [Ask a Question] [View Analytics]          │
└─────────────────────────────────────────────┘
```

## 🚀 Getting Started

### First Time Setup

1. **Navigate to your board**
   - Click on any project board

2. **Click "AI Coach"**
   - Purple button in top navigation

3. **Generate suggestions**
   - Click "Refresh Suggestions" button
   - Wait ~10 seconds while AI analyzes your project

4. **View your first suggestions**
   - See what the AI Coach has detected
   - Organized by priority (Critical → Info)

### Daily Usage

**Morning Routine (2 min):**
1. Open board
2. Click "AI Coach"
3. Review critical/high suggestions
4. Acknowledge what you'll act on
5. Get back to work!

**Weekly Practice (5 min):**
1. Provide feedback on resolved suggestions
2. Check analytics to see your progress
3. Ask coach a question if needed

## 🎨 Visual Features

### Color Coding

- **🔴 Red border** = Critical (act now!)
- **🟠 Orange border** = High priority (act today)
- **🔵 Blue border** = Medium priority (this week)
- **🟢 Green border** = Low priority (when possible)
- **⚫ Gray border** = Info (FYI)

### Badges

- **Severity badge** (colored) = How urgent
- **Type badge** (gray) = What kind of suggestion
- **Confidence %** = How sure AI is
- **Days active** = How long it's been there

### Action Buttons

- **Acknowledge** = "I've seen this"
- **Provide Feedback** = "Tell AI how it went"
- **Dismiss** = "Not relevant to me"

## 🔗 Related Features

### From Coach Dashboard, you can:

1. **View Analytics**
   - `/board/{id}/coach/analytics/`
   - See effectiveness over time
   - Track your improvement

2. **Ask Questions**
   - `/board/{id}/coach/ask/`
   - Get AI advice on specific topics
   - Personalized to your project

3. **See Suggestion Details**
   - Click "Provide Feedback" button
   - View full context and history
   - Submit detailed feedback

## 📱 Navigation Flow

```
Board Detail
    ↓ Click "AI Coach"
Coach Dashboard
    ↓ Click suggestion
Suggestion Detail
    ↓ Provide feedback
Feedback Form
    ↓ Submit
Back to Dashboard (updated)
```

## 🎯 Quick Tips

**To find suggestions quickly:**
- Critical/High at top (scroll first!)
- Medium in middle
- Low/Info at bottom

**To understand a suggestion:**
- Read "Why this matters" section
- Check recommended actions
- Look at expected impact

**To interact:**
- Acknowledge = Mark as seen
- Feedback = Tell how it went
- Dismiss = Not relevant

**To get help:**
- Click "Ask a Question"
- Use "View Analytics" for trends
- Check documentation files

## 🔧 Troubleshooting

### "I don't see any suggestions"

1. Click "Refresh Suggestions" button
2. Wait for analysis to complete
3. If still empty = board looks good! 🎉

### "Button is missing"

1. Check you're on board detail page (not board list)
2. Make sure you ran migrations
3. Check URL patterns are included
4. Verify you have access to the board

### "Error when clicking button"

1. Check Django server is running
2. Look at browser console for errors
3. Verify CSRF token is present
4. Check URL routing in `coach_urls.py`

## 📞 Need Help?

- **Documentation**: `AI_COACH_IMPLEMENTATION.md`
- **Quick Start**: `AI_COACH_QUICK_START.md`
- **Django Admin**: `/admin/` → Coaching Suggestions
- **Logs**: Check Django console output

---

## ✅ Checklist: Is It Working?

- [ ] I can see "AI Coach" button on board page
- [ ] Button has purple color and graduation cap icon
- [ ] Clicking opens coach dashboard
- [ ] Dashboard shows header and stats
- [ ] "Refresh Suggestions" button works
- [ ] Suggestions appear after generation
- [ ] Action buttons (Acknowledge, etc.) work
- [ ] Can navigate to Ask Coach page
- [ ] Can view analytics page

If all checked = You're ready to use AI Coach! 🎉
