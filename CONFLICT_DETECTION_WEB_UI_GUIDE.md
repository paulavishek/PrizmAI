# Automated Conflict Detection & Resolution - Web UI Access Guide

## 🎯 Quick Access

The Conflict Detection feature is now fully accessible via the web interface at:
**`http://localhost:8000/kanban/conflicts/`**

A navigation menu item **"Conflicts"** has been added to the main navigation bar with a badge showing the count of active conflicts.

---

## 📋 Available Pages

### 1. **Conflict Dashboard** (`/kanban/conflicts/`)
The main hub for viewing and managing all conflicts.

**Features:**
- **Real-time Statistics**: Active conflicts, severity breakdown, notification count
- **Conflict List**: Filterable by type (Resource, Schedule, Dependency)
- **Quick Actions**: View details, ignore conflicts, trigger detection
- **Notifications Panel**: See your unread conflict alerts
- **Recent Resolutions**: Learn from past successful resolutions

**Actions:**
- Click any conflict card to view details
- Use filter buttons to view specific conflict types
- Click "Scan Now" to trigger immediate detection
- Click "Analytics" to view learning patterns

### 2. **Conflict Detail** (`/kanban/conflicts/<id>/`)
Deep dive into a specific conflict with AI-powered resolution suggestions.

**Features:**
- **Conflict Overview**: Full description, severity, affected tasks/users
- **AI Resolution Suggestions**: Multiple options with confidence scores
- **Implementation Steps**: Detailed action plans for each resolution
- **Similar Past Conflicts**: Learn from historical data
- **Interactive Selection**: Choose and apply resolutions with one click

**Actions:**
- Select a resolution by clicking its card
- Click "Apply Selected Resolution" to resolve the conflict
- Click "Ignore This Conflict" if it's not relevant
- Provide effectiveness feedback after applying (star rating)

### 3. **Analytics Dashboard** (`/kanban/conflicts/analytics/`)
View pattern learning and resolution effectiveness metrics.

**Features:**
- **Key Metrics**: Total resolved, avg resolution time, avg effectiveness
- **Learned Patterns**: See what resolutions work best for each conflict type
- **Success Rates**: Visual representation of pattern performance
- **Confidence Adjustments**: AI learning from your team's decisions
- **Insights Panel**: Top performing resolutions and areas for improvement

**Benefits:**
- Understand what works for your team
- Track AI learning progress
- Identify patterns in conflict resolution
- Optimize future suggestions based on historical data

---

## 🚀 How to Use

### First-Time Setup

1. **Start the Server** (if not running):
   ```bash
   python manage.py runserver
   ```

2. **Navigate to Conflict Dashboard**:
   - Click "Conflicts" in the navigation menu
   - Or go directly to `http://localhost:8000/kanban/conflicts/`

3. **Trigger Initial Detection**:
   - Click the "Scan Now" button on the dashboard
   - Or use the "Scan Specific Board" panel in the sidebar

### Resolving Your First Conflict

1. **View Conflicts**:
   - Dashboard shows all active conflicts sorted by severity
   - Critical conflicts appear at the top with red border

2. **Examine Details**:
   - Click "View & Resolve" on any conflict card
   - Review AI suggestions with confidence scores

3. **Apply Resolution**:
   - Click on a resolution card to select it
   - Review implementation steps (expandable details)
   - Click "Apply Selected Resolution" button

4. **Provide Feedback**:
   - After applying, rate effectiveness (1-5 stars)
   - Optional: Add comments about the resolution
   - This helps AI learn and improve future suggestions

5. **Monitor Results**:
   - Conflict moves to "Resolved" status
   - View in "Recent Resolutions" on dashboard
   - Pattern data updates in Analytics

---

## 🎨 UI Components

### Dashboard Components

**Statistics Cards**:
- **Active Conflicts**: Total number needing attention
- **Critical**: Highest priority conflicts
- **High Priority**: Important conflicts
- **Notifications**: Unread alerts for you

**Conflict Cards**:
- **Color-coded borders**: Severity indication (red=critical, orange=high, yellow=medium, blue=low)
- **Badges**: Type and severity labels
- **Metadata**: Board, tasks affected, users involved
- **Timestamps**: When conflict was detected
- **Action buttons**: View details, Ignore

**Sidebar Panels**:
- **Notifications**: Your unread conflict alerts (click to view)
- **Recent Resolutions**: Successfully resolved conflicts
- **Board Scanner**: Scan specific boards on-demand

### Detail Page Components

**Resolution Cards**:
- **Hover effect**: Border highlights on hover
- **Selection**: Green background when selected
- **Confidence bar**: Visual representation (green=high, yellow=medium, red=low)
- **AI Reasoning**: Why this solution works
- **Implementation Steps**: Expandable action plan
- **Historical data**: Times accepted and average rating

**Quick Actions Panel**:
- **Ignore**: Mark conflict as not relevant
- **Back to Dashboard**: Return to main view

### Analytics Components

**Metric Cards**:
- **Hover animation**: Slight lift effect
- **Color-coded icons**: Visual category identification
- **Responsive numbers**: Large, readable statistics

**Pattern Cards**:
- **Success rate bars**: Green (high), yellow (medium), red (low)
- **Confidence indicators**: Boost/penalty badges
- **Star ratings**: Average effectiveness from users
- **Last used timestamps**: Pattern freshness

---

## 🔔 Notifications

### How Notifications Work

1. **Automatic Creation**: When a conflict affects you (your tasks/boards)
2. **Unread Badge**: Shows count in navigation menu
3. **Notification Panel**: Sidebar on dashboard shows recent alerts
4. **Click to View**: Automatically marks as read and opens conflict

### Notification Types

- **Resource Conflicts**: You're overbooked on multiple tasks
- **Schedule Conflicts**: Your tasks have deadline issues
- **Dependency Conflicts**: Tasks you're assigned to are blocked

---

## 📊 Pattern Learning

### How AI Learns

1. **Initial Suggestions**: AI generates resolutions with base confidence
2. **Your Choice**: You select and apply a resolution
3. **Feedback**: You rate effectiveness (1-5 stars)
4. **Pattern Creation**: System records (conflict type → resolution type → outcome)
5. **Confidence Adjustment**:
   - High ratings (4-5 stars) = confidence boost (+10-20%)
   - Low ratings (1-2 stars) = confidence penalty (-10-20%)

### Pattern Scope

- **Board-Specific**: Patterns for individual boards (more specific)
- **Global**: Patterns across all boards (general guidance)
- **Minimum Threshold**: 5 resolutions before pattern becomes active

### Viewing Pattern Impact

- Go to Analytics page
- See "Confidence boost" or "Confidence penalty" badges
- Green = AI prefers this pattern
- Red = AI avoids this pattern
- Gray = Neutral (collecting data)

---

## 🎯 Best Practices

### For Team Leads

1. **Review Daily**: Check dashboard once per day
2. **Address Critical First**: Red-bordered conflicts are highest priority
3. **Provide Feedback**: Always rate resolutions to improve AI
4. **Monitor Analytics**: Weekly review of pattern learning
5. **Train Team**: Show members how to resolve their conflicts

### For Team Members

1. **Check Notifications**: Review alerts about your tasks
2. **Resolve Promptly**: Don't let conflicts accumulate
3. **Use AI Suggestions**: Trust high-confidence recommendations
4. **Give Honest Ratings**: Help improve system accuracy
5. **Report Issues**: Use "Ignore" with reason if conflict is incorrect

### For Administrators

1. **Enable Celery Beat**: Ensure hourly detection runs automatically
2. **Monitor Patterns**: Review analytics for team trends
3. **Adjust Detection**: Tune thresholds if too many false positives
4. **Export Data**: Use Django Admin for advanced analysis
5. **Review Ignored**: Periodically check ignored conflicts for system tuning

---

## 🔧 Advanced Features

### Manual Detection Triggers

**Dashboard "Scan Now"**:
- Scans all accessible boards
- Generates new conflicts if found
- Updates existing conflicts if status changed
- ~5-10 seconds for typical workspace

**Board-Specific Scanning**:
- Sidebar dropdown "Scan Specific Board"
- Select board from list
- Click "Scan Board"
- Faster than full scan

**CLI Command** (for automation):
```bash
# Scan all boards
python manage.py detect_conflicts --all-boards

# Scan specific board
python manage.py detect_conflicts --board-id 1

# With AI suggestions
python manage.py detect_conflicts --all-boards --with-ai
```

### Filtering Conflicts

**By Type**:
- Click filter buttons in dashboard header
- Resource, Schedule, Dependency, or All
- Instantly hides/shows conflicts

**By Severity** (via sort):
- Conflicts auto-sorted by severity (critical first)
- Then by detection time (newest first)

### Ignoring Conflicts

**When to Ignore**:
- False positive (not actually a conflict)
- Already resolved manually
- Acceptable situation (intentional overlap)

**How to Ignore**:
1. Click "Ignore" button on conflict card or detail page
2. Optional: Provide reason (helps improve detection)
3. Conflict status changes to "ignored"
4. No longer appears in active list
5. Available in Django Admin for review

---

## 🎓 Tips & Tricks

### Maximize AI Learning

1. **Be Consistent**: Apply similar resolutions for similar conflicts
2. **Rate Honestly**: Accurate ratings = better future suggestions
3. **Add Context**: Use feedback text for complex situations
4. **Review Patterns**: Analytics shows what AI has learned

### Handle High Conflict Volumes

1. **Use Filters**: Focus on one type at a time
2. **Address Critical First**: Red borders = highest priority
3. **Batch Similar**: Resolve similar conflicts together
4. **Delegate**: Share conflict URLs with team members
5. **Adjust Schedules**: Use insights to prevent future conflicts

### Troubleshooting

**No Conflicts Showing**:
- Click "Scan Now" to trigger detection
- Check that you have boards with tasks
- Verify Celery is running for auto-detection

**Too Many False Positives**:
- Use "Ignore" with reasons
- Admin can adjust detection thresholds
- Patterns will learn over time

**Suggestions Not Helpful**:
- Rate them honestly (low stars)
- Provide feedback text explaining why
- AI will adjust confidence for future suggestions

**Notifications Not Appearing**:
- Refresh page to update badge count
- Check that conflicts affect your assigned tasks
- Verify you're a member of the boards

---

## 📱 Mobile Responsiveness

All pages are fully responsive:
- **Phone**: Stacked layout, scrollable cards
- **Tablet**: Two-column layout where appropriate
- **Desktop**: Full three-column dashboard

Bootstrap 5 ensures consistent experience across devices.

---

## 🔐 Permissions

**Who Can Access**:
- All authenticated users
- See conflicts from their boards only
- Organization-scoped access

**What Actions Are Allowed**:
- View conflicts on accessible boards
- Apply resolutions to conflicts
- Provide feedback and ratings
- Ignore conflicts (with reason)
- Trigger manual scans

**Admin Additional Access**:
- Django Admin at `/admin/kanban/conflictdetection/`
- View all conflicts across organization
- Manually edit/delete conflicts
- Export pattern data
- Adjust detection settings

---

## 🎉 Success Indicators

You'll know the system is working when:
- ✅ Dashboard shows active conflicts with statistics
- ✅ Navigation badge displays conflict count
- ✅ AI suggestions have varied confidence scores
- ✅ Applied resolutions appear in "Recent Resolutions"
- ✅ Analytics shows learned patterns (after 5+ resolutions)
- ✅ Confidence boosts/penalties appear in patterns
- ✅ Notifications alert you about your task conflicts

---

## 📞 Getting Help

**In the UI**:
- Help panel on detail page explains conflict types
- Analytics has "How It Works" explanation
- Tooltips on hover (where available)

**Documentation**:
- `CONFLICT_DETECTION_GUIDE.md` - Technical details
- This file - Web UI access guide
- Django Admin docs - Advanced management

**Support**:
- Check server logs: `logs/celery.log` and `logs/django.log`
- Review detection output: `python manage.py detect_conflicts`
- Django Admin: `/admin/kanban/conflictdetection/`

---

## 🚀 Next Steps

Now that the UI is ready:

1. **Start Using**: Navigate to `/kanban/conflicts/`
2. **Run First Scan**: Click "Scan Now" button
3. **Review Results**: Examine detected conflicts
4. **Apply Resolutions**: Select and apply AI suggestions
5. **Provide Feedback**: Rate effectiveness to train AI
6. **Monitor Learning**: Check Analytics after ~10 resolutions

The system will continuously improve as your team uses it!

---

**Happy Conflict Resolving! 🎯**
