# AI Explainability - User Guide
**How to See AI Decision Logic in PrizmAI**

---

## 🎯 Overview

PrizmAI now shows you **WHY** the AI made specific decisions, not just WHAT it decided. This builds trust and helps you make better decisions.

---

## 📍 Where to Find AI Explanations

### **1. Task Detail Page - Risk Assessment**

#### **Scenario A: Task with Risk Assessment**

**What You See:**
```
🛡️ Risk Assessment
Risk Level: HIGH
Score: 6/9 | Likelihood: 2/3 | Impact: 3/3

[Why? Button] ← Click this!
```

**When You Click "Why?"**:
A detailed modal opens showing:

✅ **AI Confidence Level**: 85% confidence bar (green/yellow/red)

✅ **Visual Breakdown**:
```
┌─────────────┬──────────┬────────────┐
│ Likelihood  │  Impact  │ Risk Score │
│     2       │    3     │    6/9     │
│  (34-66%)   │  (High)  │   (HIGH)   │
└─────────────┴──────────┴────────────┘
```

✅ **How We Calculated This**:
```
Formula: Likelihood (2) × Impact (3) = Risk Score (6)

Summary: This task presents high risk due to complexity 
and external dependencies...
```

✅ **Contributing Factors** (with percentages):
```
1. OAuth Integration Complexity (35%)
   ├─ Multiple API endpoints increase implementation complexity
   └─ Progress bar: ████████░░ 35%

2. External API Dependency (30%)
   ├─ Waiting on Google API approval creates timeline uncertainty
   └─ Progress bar: ███████░░░ 30%

3. Assignee Skill Gap (20%)
   ├─ Intermediate vs Expert level required
   └─ Progress bar: █████░░░░░ 20%

4. Timeline Pressure (15%)
   ├─ 3 days vs typical 5-7 days
   └─ Progress bar: ████░░░░░░ 15%
```

✅ **Likelihood Factors**:
- Complex OAuth integration with multiple API endpoints
- Limited assignee experience with OAuth 2.0
- External dependency on Google API approval

✅ **Impact Analysis**:
- User authentication system
- API integration roadmap
- Q4 release schedule
- Mobile app development

✅ **Model Assumptions** (Expandable):
```
▼ Model Assumptions
  • Assignee can dedicate 6 hours/day to this task
  • Google API approval within 48 hours
  • No major architectural changes needed
  
▼ Data Limitations
  • Limited historical data for OAuth tasks
  • No direct experience data from current assignee
  
▼ Alternative Interpretations
  • Risk could be Medium if using pre-built OAuth library
  • Impact could be lower if authentication is isolated
```

---

#### **Scenario B: Task WITHOUT Risk Assessment**

**What You See:**
```
┌──────────────────────────────────────────────┐
│ 🛡️ AI Risk Assessment                        │
│ Let AI analyze potential risks for this task │
│                                              │
│              [Assess Risk with AI]  ← Click! │
└──────────────────────────────────────────────┘
```

**When You Click**:
1. AI analyzes the task (takes 3-5 seconds)
2. Shows the full explainability modal
3. Page refreshes to show the risk assessment permanently

---

### **2. Task Detail Page - Stakeholder Recommendations**

**What You See:**
```
👥 Stakeholders
                    [AI Insights]  [Manage Stakeholders]
                         ↑
                    Click this!

• John Doe (Product Owner) - Engaged
• Jane Smith (Developer) - Engaged
```

**When You Click "AI Insights"**:
```
┌───────────────────────────────────────────┐
│ 💡 AI Stakeholder Insights                │
├───────────────────────────────────────────┤
│ These stakeholders were identified based  │
│ on:                                        │
│                                           │
│ ✓ Task requirements and scope analysis    │
│ ✓ Historical involvement in similar tasks │
│ ✓ Organizational roles and responsibilities│
│ ✓ Potential impact on their work streams │
│ ✓ Communication patterns in the project   │
│                                           │
│ ℹ️ AI recommendations improve over time   │
│    as more project data becomes available │
└───────────────────────────────────────────┘
```

---

### **3. Board View (Kanban Cards)**

**What You See on Task Cards:**
```
┌────────────────────────────┐
│ Implement OAuth Login      │
│ Multiple API endpoints...  │
│                            │
│ Progress: 45% [░░██████░░] │
│                            │
│ 🛡️ Risk: HIGH (6/9) 💡     │
│       ↑                    │
│   Click badge!             │
└────────────────────────────┘
```

**When You Click the Risk Badge**:
A quick modal appears:
```
┌───────────────────────────────────────────┐
│ 🛡️ Quick Risk View                         │
├───────────────────────────────────────────┤
│ Implement OAuth Login                      │
│                                           │
│ Click below to see the full AI risk        │
│ analysis with detailed explanations:       │
│                                           │
│ ✓ Contributing factors breakdown          │
│ ✓ AI confidence scores                    │
│ ✓ Impact analysis                         │
│ ✓ Model assumptions & limitations         │
│                                           │
│ 💡 Explainable AI: See exactly why this   │
│    risk score was assigned.               │
│                                           │
│         [Cancel]  [View Full Analysis]    │
└───────────────────────────────────────────┘
```

---

### **4. Deadline Predictions** (Task Detail Page)

**What You See:**
```
📅 AI Predicted Completion: November 25, 2025
Confidence: Medium (75%)

[Show Full Reasoning] ← Click this!
```

**When You Click**:
```
┌─────────────────────────────────────────────┐
│ 💡 Why This Deadline?                        │
├─────────────────────────────────────────────┤
│ AI Confidence: 75% [████████████░░░░]       │
│                                             │
│ REASONING                                   │
│ Based on historical data and current team   │
│ velocity, this task requires 5-6 days of    │
│ focused work.                               │
│                                             │
│ VELOCITY ANALYSIS                           │
│ Current: 4.5 h/day │ Expected: 5.0 h/day    │
│ Trend: Declining   │ Remaining: 32 hours    │
│                                             │
│ CALCULATION BREAKDOWN                       │
│ Base Estimate:         3 days               │
│ × Complexity Factor:   1.4                  │
│ × Workload Adjustment: 1.2                  │
│ + Buffer Time:         1 day                │
│ ═══════════════════════════════            │
│ Total: 5.4 days (rounded to 6)              │
│                                             │
│ ALTERNATIVE SCENARIOS                       │
│ Optimistic:  Nov 23  │ Realistic:  Nov 25  │
│ Pessimistic: Nov 28                         │
│                                             │
│ KEY ASSUMPTIONS                             │
│ • Assignee can dedicate 6 hours/day         │
│ • No major blockers will arise              │
│ • Similar tasks took avg 5.2 days           │
│                                             │
│ RISK FACTORS                                │
│ ⚠ External API dependency may cause delays  │
│ ⚠ Assignee has limited OAuth experience     │
│ ⚠ Timeline is tight for this complexity     │
└─────────────────────────────────────────────┘
```

---

## 🎨 Visual Cues

### **Color Coding**:
- **Green**: High confidence (>75%), Low risk
- **Yellow/Orange**: Medium confidence (50-75%), Medium risk
- **Red**: Low confidence (<50%), High/Critical risk

### **Icons**:
- 💡 **Lightbulb**: Click to see AI explanation
- 🛡️ **Shield**: Risk assessment
- 📊 **Chart**: Data-driven analysis
- ⚙️ **Gear**: Model assumptions
- ⚠️ **Warning**: Risk factors or limitations

---

## 🔍 What Information Is Shown

### **For Every AI Decision, You See**:

1. **Confidence Score** (0-100%)
   - How confident the AI is in its prediction
   - Color-coded progress bar

2. **Contributing Factors**
   - What influenced the decision
   - Percentage contribution of each factor
   - Description of why it matters

3. **Calculation Method**
   - The actual formula used
   - Step-by-step breakdown
   - Visual metrics

4. **Model Assumptions**
   - What the AI assumes to be true
   - Known limitations in the data
   - Alternative interpretations

5. **Reasoning**
   - Plain English explanation
   - Key factors list
   - Impact analysis

---

## 💼 Business Value

### **For Users**:
- **Trust**: Understand AI decisions
- **Actionable**: Know what to change
- **Learning**: Understand patterns
- **Transparency**: See assumptions

### **For Managers**:
- **Validation**: Challenge AI when needed
- **Communication**: Explain decisions to stakeholders
- **Risk Management**: Understand model limitations

### **For Enterprise**:
- **Compliance**: GDPR, SOC 2, ISO 27001 audit trails
- **Quality Assurance**: Validate AI before acting
- **Transparency**: Market as "explainable AI"

---

## 🚀 Quick Start

### **To See Risk Explanation**:
1. Open any task
2. Look for risk assessment section
3. Click **"Why?"** button
4. Modal opens with full explanation

### **To Get AI Risk Assessment**:
1. Open task without risk assessment
2. Click **"Assess Risk with AI"**
3. Wait 3-5 seconds
4. View full explanation modal
5. Page refreshes with permanent assessment

### **To See Stakeholder Insights**:
1. Open task with stakeholders
2. Click **"AI Insights"** button
3. View reasoning modal

### **To View Risk on Board**:
1. Look at task cards on Kanban board
2. Click on risk badge (🛡️ Risk: HIGH 💡)
3. Quick modal appears
4. Click "View Full Analysis" for details

---

## 📝 Example User Journey

**Sarah (Project Manager) wants to understand a high-risk task:**

1. **Opens Task**: "Implement OAuth Login"
   - Sees: Risk Level: HIGH (6/9)

2. **Clicks "Why?" Button**
   - Modal opens with AI explanation

3. **Sees Contributing Factors**:
   - OAuth Complexity: 35%
   - External Dependency: 30%
   - Skill Gap: 20%
   - Timeline Pressure: 15%

4. **Reviews Assumptions**:
   - "Assignee can dedicate 6 hours/day" ← Sarah realizes this is wrong!
   - John can only work 4 hours/day this week

5. **Takes Action**:
   - Reassigns to Jane (more available)
   - Or extends deadline
   - Or requests pre-built OAuth library

6. **Result**: Risk reduced from HIGH to MEDIUM

---

## 🎓 Tips for Best Results

### **Do**:
✅ Click "Why?" buttons to understand AI reasoning
✅ Review contributing factors to identify high-impact changes
✅ Check model assumptions - they might be wrong!
✅ Use explainability to communicate with stakeholders
✅ Challenge AI when it doesn't make sense

### **Don't**:
❌ Blindly trust AI without reviewing explanation
❌ Ignore data limitations warnings
❌ Skip reading assumptions
❌ Forget that AI learns from your data

---

## 🔗 Related Features

- **Risk Management**: Full risk assessment with AI
- **Deadline Predictions**: AI-powered timeline estimates
- **Stakeholder Recommendations**: Smart stakeholder identification
- **Task Assignment**: AI-powered assignee suggestions
- **Priority Recommendations**: Intelligent task prioritization

---

## 🆘 Troubleshooting

**Q: "Why?" button doesn't work**
- Check that JavaScript is enabled
- Refresh the page
- Check browser console for errors

**Q: AI confidence is low (<50%)**
- Limited historical data
- Complex/unusual task
- Review assumptions carefully

**Q: Contributing factors don't make sense**
- Check model assumptions
- Provide feedback to improve AI
- Manual override is always available

---

**Status**: ✅ Live in Production
**Last Updated**: November 18, 2025
**Feature Version**: 1.0
