# 🤖 How to Use AI-Powered Priority Suggestions

## Where Users See the Priority Recommendations

### 📍 Location: Task Creation Page

The **Intelligent Priority Suggestions** widget appears when creating a new task.

**Path:** Board → "Create Task" button → Task Creation Form

---

## 🎯 Step-by-Step User Experience

### 1. **Navigate to Task Creation**
```
1. Log in to PrizmAI
2. Go to any board (e.g., "Software Project", "Bug Tracking", "Marketing Campaign")
3. Click the "Create Task" button
```

### 2. **Fill in Basic Task Information**

As you fill in the task form, the AI analyzes your inputs:

- **Task Title** (Required)
- **Task Description** (Optional but helps AI accuracy)
- **Due Date** (Optional - major factor for priority)
- **Assignee** (Optional)
- **Labels** (Optional)

### 3. **AI Suggestion Appears Automatically**

**When the AI widget triggers:**
- After you fill in the title and description
- When you set or change the due date
- When you modify complexity or risk scores
- Automatically after 1 second of inactivity (debounced)

**What you'll see:**

```
┌─────────────────────────────────────────────────────────┐
│ Priority                                                │
│ ┌─────────────────────────────────────────────────┐    │
│ │ [Dropdown: Low, Medium, High, Urgent]           │    │
│ └─────────────────────────────────────────────────┘    │
│                                                         │
│ 🤖 AI Suggestion: HIGH                                  │
│ Confidence: 85%                                         │
│                                                         │
│ Why this priority?                                      │
│ • Due in 5 days - approaching deadline                  │
│ • Risk score: 7/10 - significant risk factors          │
│ • Complexity: 6/10 - moderately complex                 │
│ • Similar tasks in your team were prioritized as HIGH   │
│                                                         │
│ [Accept Suggestion] [Ignore]                            │
└─────────────────────────────────────────────────────────┘
```

### 4. **Interact with the Suggestion**

You have three options:

#### Option A: **Accept the AI Suggestion** ✅
- Click the "Accept Suggestion" button
- Priority field automatically updates to the suggested value
- Your acceptance is logged to improve future suggestions

#### Option B: **Choose a Different Priority** 🔄
- Select your preferred priority from the dropdown
- The AI learns from this override
- Your decision teaches the AI about your team's patterns

#### Option C: **Ignore** ⏭️
- Simply continue filling the form
- No action is logged until you submit

### 5. **See AI Reasoning (Explainable AI)**

Click **"Why this priority?"** or the info icon to see:

```
📊 AI Analysis:

FACTORS CONSIDERED:
✓ Due Date: 5 days away (High urgency)
✓ Risk Score: 7/10 (Significant risk)
✓ Complexity: 6/10 (Moderate effort required)
✓ Team Capacity: 12 open tasks / 6 members = 2.0 tasks per person
✓ Historical Patterns: 87% of similar tasks were HIGH priority

RECOMMENDATION: HIGH Priority
Confidence: 85%

SIMILAR PAST DECISIONS:
• "Implement OAuth authentication" - HIGH priority, completed in 8 days
• "Fix security vulnerability" - URGENT priority, completed in 2 days
• "API rate limiting" - HIGH priority, completed in 7 days

```

---

## 🎨 Visual Elements

### Loading State
When AI is analyzing:
```
⏳ Analyzing optimal priority...
[Spinner animation]
```

### Suggestion Display
```
🤖 AI Suggestion: [PRIORITY BADGE]
📊 Confidence: XX%
💡 Why this priority? [Expandable explanation]
✅ [Accept Button] ❌ [Ignore Button]
```

### Priority Badges
- 🔴 **URGENT** - Red badge
- 🟠 **HIGH** - Orange badge  
- 🟡 **MEDIUM** - Yellow badge
- 🟢 **LOW** - Green badge

---

## 📊 What the AI Considers

### Primary Factors (Most Important)

1. **Days Until Due Date** (50-55% weight)
   - < 2 days → Usually URGENT
   - 3-7 days → Usually HIGH
   - 8-14 days → Usually MEDIUM  
   - > 14 days → Usually LOW

2. **Risk Score** (45-53% weight)
   - 8-9 → Critical risk → Higher priority
   - 5-7 → Moderate risk → Medium-High priority
   - 2-4 → Low risk → Lower priority
   - 1 → Minimal risk → LOW priority

### Secondary Factors

3. **Complexity Score** (when available)
   - High complexity + tight deadline = Higher priority
   - Low complexity = Can be scheduled flexibly

4. **Dependencies** (when available)
   - Tasks blocking others → Higher priority
   - Tasks blocked by others → May be lower priority

5. **Team Workload** (when available)
   - Overloaded assignee → May adjust timeline
   - Available capacity → Can take on more

6. **Historical Patterns** (learned from your team)
   - "Tasks like this are usually HIGH priority"
   - "Your team tends to prioritize security issues as URGENT"

---

## 🧠 How the AI Learns

### 1. **Initial Predictions** (Rule-Based)
When a board has < 20 priority decisions, the AI uses smart rules:
- Due date urgency
- Risk scores
- Complexity assessment
- Industry best practices

### 2. **ML-Powered Predictions** (After 20+ Decisions)
Once enough data exists:
- Trained Random Forest model
- Learns your team's unique patterns
- Adapts to your workflow preferences
- Improves accuracy over time

### 3. **Continuous Learning**
Every decision you make teaches the AI:
- **Accepted suggestions** → Reinforces AI confidence
- **Rejected suggestions** → AI learns when to adjust
- **Modified priorities** → AI understands exceptions
- **Team patterns** → AI recognizes team-specific rules

**Example Learning Cycle:**
```
User creates task: "Fix login bug"
├─ AI suggests: MEDIUM (based on complexity)
├─ User selects: URGENT (security concern)
└─ AI learns: "Login bugs are URGENT for this team"

Next time:
├─ Task: "Fix password reset bug"
└─ AI suggests: URGENT (learned from past decisions) ✅
```

---

## 💡 Pro Tips

### Get Better Suggestions

1. **Fill in Due Dates**
   - Most important factor for priority
   - Helps AI understand urgency

2. **Set Risk Scores** (in Advanced Features)
   - Risk Likelihood × Risk Impact = Risk Score
   - AI heavily weighs this factor

3. **Add Task Descriptions**
   - Helps AI understand context
   - Future: Will use NLP for better analysis

4. **Use Complexity Scores**
   - Helps AI estimate effort required
   - Affects timeline pressure calculations

5. **Be Consistent**
   - Use priorities consistently across your team
   - AI learns faster with clear patterns

### When to Override AI

✅ **Override when:**
- You have domain knowledge AI doesn't
- Business priorities change suddenly  
- Stakeholder requests specific priority
- Team has unique circumstances

❌ **Don't override just because:**
- "I always do it this way" (challenge assumptions!)
- Fear of change
- Without considering AI reasoning

---

## 📈 Model Performance

### Current Stats (Demo Data)

- **Total Decisions**: 145 across 3 boards
- **Model Accuracy**: 66.7%
- **AI Acceptance Rate**: 55-57%

### Per-Priority Performance

| Priority | Precision | Recall | Notes |
|----------|-----------|--------|-------|
| Urgent   | 100%      | 83%    | Very reliable |
| High     | 82%       | 67%    | Good accuracy |
| Medium   | 56%       | 50%    | Will improve with data |
| Low      | 56%       | 83%    | Good at identifying low priority |

**Note:** These are initial metrics. Performance improves as more real decisions are logged.

---

## 🔍 Troubleshooting

### "I don't see the AI suggestion widget"

**Check:**
1. Are you on the **Task Creation page**? (Not the board view)
2. Have you filled in the **Title** field?
3. Is JavaScript enabled in your browser?
4. Check browser console for errors (F12)

**Common fixes:**
- Refresh the page (Ctrl+F5 / Cmd+Shift+R)
- Clear browser cache
- Ensure demo data is populated: `python manage.py populate_test_data`
- Verify ML models are trained: `python manage.py train_priority_models --all`

### "AI always suggests the same priority"

**Likely causes:**
- Not enough training data yet (need 20+ decisions per board)
- Using rule-based mode (will improve once trained)
- Tasks are actually similar (check AI reasoning)

**Fix:**
- Run: `python manage.py train_priority_models --all`
- Check: `python check_priority_status.py`
- Create more varied tasks to train the AI

### "AI suggestions don't make sense"

**Check the reasoning:**
- Click "Why this priority?" to see factors
- Verify your task inputs (due date, risk score, etc.)
- Remember: AI learns from YOUR team's past decisions

**Report issues:**
- AI reasoning helps debug unexpected suggestions
- Each board learns independently  
- Different teams may have different patterns

---

## 🚀 Testing the Feature

### Quick Test

1. **Login** with demo credentials:
   ```
   Username: admin
   Password: admin123
   ```

2. **Navigate** to Software Project board

3. **Click "Create Task"**

4. **Fill in:**
   - Title: "Fix critical payment bug"
   - Description: "Payment gateway failing for all users"
   - Due Date: Tomorrow
   - Risk Likelihood: High (3)
   - Risk Impact: High (3)

5. **Watch** the AI widget appear

6. **Expected:** AI should suggest **URGENT** priority (due date + high risk)

7. **Try accepting** the suggestion

8. **Create another task** with:
   - Title: "Update color scheme"
   - Due Date: 30 days from now
   - Risk: Low

9. **Expected:** AI should suggest **LOW** priority

---

## 📚 Related Documentation

- **Feature Guide**: `PRIORITY_SUGGESTION_GUIDE.md` - Complete technical documentation
- **API Docs**: `API_DOCUMENTATION.md` - REST API endpoints
- **Demo Data**: `DEMO_DATA_ENHANCEMENT_COMPLETE.md` - Training data details
- **Implementation**: `ai_assistant/utils/priority_service.py` - ML service code

---

## 🎓 Understanding the Widget Code

### JavaScript File Location
```
static/js/priority_suggestion.js
```

### Key Components

1. **PrioritySuggestionWidget** - Main class
2. **Auto-triggers** - Detects field changes  
3. **API Integration** - Calls `/api/priority-suggestions/`
4. **UI Rendering** - Shows suggestion card
5. **Interaction Handlers** - Accept/reject buttons
6. **Feedback Loop** - Logs decisions

### API Endpoints Used

```javascript
// Get suggestion
POST /api/priority-suggestions/suggest/
{
  "task_context": {...}
}

// Log decision
POST /api/priority-suggestions/log/
{
  "task_id": 123,
  "suggested_priority": "high",
  "chosen_priority": "urgent",
  "accepted": false
}
```

---

## ✅ Checklist: Is Priority Suggestions Working?

- [ ] Server is running: `python manage.py runserver`
- [ ] Demo data populated: `python manage.py populate_test_data`
- [ ] ML models trained: `python manage.py train_priority_models --all`
- [ ] Can access task creation page
- [ ] JavaScript file loads (check Network tab in browser dev tools)
- [ ] API endpoints respond (check Console for errors)
- [ ] Widget appears when filling task form
- [ ] Can accept/reject suggestions
- [ ] Decisions are logged to database

**Verify with:**
```bash
python check_priority_status.py
```

Should show:
- ✅ 145 priority decisions
- ✅ 3 trained ML models
- ✅ 66.7% accuracy per board

---

## 🎉 Success Indicators

### You know it's working when:

1. ✅ **Widget appears** within 1 second of filling title
2. ✅ **Suggestion makes sense** based on your inputs
3. ✅ **Reasoning is clear** when you expand details
4. ✅ **Accept button works** and updates priority field
5. ✅ **Different tasks** get different priority suggestions
6. ✅ **AI learns** from your choices over time

### Long-term Success:

- 📈 Suggestion accuracy improves (aim for 80%+)
- 🎯 Acceptance rate increases (your team trusts AI)
- ⚡ Faster task creation (less time deciding priorities)
- 🤝 More consistent priorities across team
- 📊 Better project planning and resource allocation

---

**🚀 Ready to Try?**

1. Start the server: `python manage.py runserver`
2. Visit: http://localhost:8000/
3. Login as admin
4. Go to any board
5. Click "Create Task"
6. Watch the AI magic happen! ✨

