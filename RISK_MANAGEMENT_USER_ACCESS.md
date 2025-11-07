# Risk Management - User Access & Transparency Update

## Problem
Users could see risk assessment information on task detail pages (Risk Level, Risk Score, Indicators, Mitigation Strategies), but they had no way to:
- Understand where this data came from
- Edit or modify risk assessments
- Add their own risk information

The risk data was only populated through:
- AI API calls (api_views.py)
- Test data management commands (populate_test_data.py)

## Solution Implemented

### 1. Added Risk Fields to TaskForm
**File: `kanban/forms/__init__.py`**

Added the following fields to the task creation and editing forms:
- `risk_likelihood` - Dropdown (1=Low, 2=Medium, 3=High)
- `risk_impact` - Dropdown (1=Low, 2=Medium, 3=High)  
- `risk_level` - Dropdown (Low/Medium/High/Critical)
- `risk_indicators_text` - Textarea for listing indicators (one per line)
- `mitigation_strategies_text` - Textarea for mitigation strategies (one per line)

### 2. Automatic Risk Score Calculation
The form now automatically:
- Calculates `risk_score` = likelihood × impact (range 1-9)
- Auto-suggests `risk_level` based on score:
  - Score ≥ 6: Critical
  - Score ≥ 4: High
  - Score ≥ 2: Medium
  - Score < 2: Low

### 3. Risk Indicators & Mitigation Strategies
**Text Format:**
Users can enter risk indicators and mitigation strategies as plain text:

**Risk Indicators** (one per line):
```
Monitor task progress weekly
Track team member availability
Check for dependencies
```

**Mitigation Strategies** (supports structured format):
```
Allocate resources: Add 2 more developers to team (2 weeks)
Technical review: Conduct early code review to catch issues (1 week)
Monitor progress: Daily standup meetings
```

The form parses the format: `Strategy: Description (Timeline)`

### 4. Updated Task Creation Form
**File: `templates/kanban/create_task.html`**

Added a Risk Assessment section in the "Advanced Features" collapsible panel with:
- Risk Likelihood dropdown
- Risk Impact dropdown
- Risk Level dropdown (auto-calculated or manual)
- Risk Indicators textarea
- Mitigation Strategies textarea
- Help text explaining automatic calculation

### 5. Task Editing
The same risk fields are now available when editing tasks through:
- Task detail page (uses the updated TaskForm)
- Any task edit interface

Since the form uses `{{ form|crispy }}` or individual field rendering, all new fields automatically appear.

## How It Works

### Creating a Task with Risk Assessment:

1. **Create new task** (click "Create Task" button)
2. **Expand "Advanced Features"** section
3. **Fill in Risk Assessment:**
   - Select Risk Likelihood (e.g., High = 3)
   - Select Risk Impact (e.g., High = 3)
   - Risk Score is auto-calculated (3 × 3 = 9)
   - Risk Level is auto-suggested (Critical)
   - Add Risk Indicators (one per line)
   - Add Mitigation Strategies (one per line)

### Editing Existing Risk Assessment:

1. **Go to task detail page**
2. **Scroll to the task form**
3. **Risk fields will show current values:**
   - Existing JSON risk_indicators converted to text (one per line)
   - Existing JSON mitigation_suggestions converted to readable text
4. **Edit any field and save**

## Data Flow

### Before (AI-only):
```
AI API → risk_level, risk_score, risk_indicators, mitigation_suggestions → Database → Display only
```

### After (User-editable):
```
User Form ← → Database ← → AI API
    ↓                    ↓
  Display            Display
```

Users can now:
- ✅ View risk information
- ✅ Edit risk information manually
- ✅ Add new risk assessments
- ✅ Update AI-generated assessments
- ✅ Clear risk assessments

## Benefits

1. **Transparency**: Users understand they can manage risk assessments
2. **Control**: Users can manually assess risks without AI
3. **Flexibility**: Can combine manual entry with AI suggestions
4. **Visibility**: Risk fields are clearly labeled and explained
5. **Automatic Calculation**: Risk score auto-calculated for convenience

## Fields Available

| Field | Type | Description | Editable |
|-------|------|-------------|----------|
| risk_likelihood | Dropdown | Probability (1-3) | ✅ Yes |
| risk_impact | Dropdown | Severity (1-3) | ✅ Yes |
| risk_score | Auto-calculated | Likelihood × Impact (1-9) | ⚡ Auto |
| risk_level | Dropdown | Low/Medium/High/Critical | ✅ Yes |
| risk_indicators | Text List | Indicators to monitor | ✅ Yes |
| mitigation_suggestions | Text List | Mitigation strategies | ✅ Yes |

## Example Usage

### Example 1: Manual Risk Assessment
```
Task: "Implement payment gateway"

Risk Likelihood: High (3)
Risk Impact: High (3)
Risk Level: Critical (auto-suggested)

Risk Indicators:
- Monitor API response times daily
- Track transaction success rates
- Verify PCI compliance requirements

Mitigation Strategies:
- Security review: Conduct penetration testing before launch (1 week)
- Backup plan: Prepare fallback payment provider (ongoing)
- Monitoring: Set up real-time alerts for failures (2 days)
```

### Example 2: Updating AI-Generated Assessment
If AI generated risk data, users can now:
- View it in the form
- Modify any values
- Add additional indicators
- Update mitigation strategies
- Change risk level if they disagree

## Technical Details

### Form Initialization
- Loads JSON `risk_indicators` → Text (newline-separated)
- Loads JSON `mitigation_suggestions` → Text with formatting

### Form Saving
- Converts text → JSON list for `risk_indicators`
- Parses text → JSON structured format for `mitigation_suggestions`
- Calculates `risk_score` automatically
- Suggests `risk_level` if not manually set

### Validation
- All risk fields are optional
- Likelihood and Impact must be 1-3 if provided
- Risk Level must be valid choice if provided

## Files Modified

1. ✅ `kanban/forms/__init__.py` - Added risk fields to TaskForm
2. ✅ `templates/kanban/create_task.html` - Added risk section to UI

## No Breaking Changes

- Existing tasks with AI-generated risk data work as before
- Risk display on task detail page unchanged
- AI risk generation still works if configured
- Backward compatible with existing data

## Next Steps (Optional Enhancements)

Future improvements could include:
- AI button to "Generate Risk Assessment" on demand
- Risk history tracking
- Risk matrix visualization
- Bulk risk assessment for multiple tasks
- Risk dashboard/reports
