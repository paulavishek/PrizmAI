# AI Explainability UI Guide

## Overview

This document describes the UI components and features available for displaying AI explainability information throughout PrizmAI. Every AI-powered feature now includes comprehensive explanations to help users understand **why** the AI made specific recommendations.

## Core JavaScript Module

### Location: `static/js/ai_explainability.js`

This is the central module for rendering AI explainability UI components. Import it via `base.html` (already included).

### Available Functions

#### 1. `AIExplainability.renderConfidenceMeter(confidence, reasoning)`
Renders a visual confidence meter with optional reasoning tooltip.

```javascript
const html = AIExplainability.renderConfidenceMeter(0.85, "Based on 50+ similar tasks");
```

#### 2. `AIExplainability.renderFactorBreakdown(factors)`
Renders contributing factors with percentage bars.

```javascript
const factors = [
    { factor: "Task Complexity", contribution_percentage: 35, description: "High complexity increases risk" },
    { factor: "Timeline Pressure", contribution_percentage: 25, description: "Tight deadline detected" }
];
const html = AIExplainability.renderFactorBreakdown(factors);
```

#### 3. `AIExplainability.renderExplainabilityPanel(data)`
Renders a comprehensive explainability panel with all details.

```javascript
const data = {
    confidence_score: 0.85,
    contributing_factors: [...],
    assumptions: ["Stable team velocity", "No major blockers"],
    limitations: ["Limited historical data"]
};
const html = AIExplainability.renderExplainabilityPanel(data);
```

#### 4. `AIExplainability.renderExplainabilityBadge(confidence, clickable)`
Renders a compact confidence badge that can expand on click.

#### 5. `AIExplainability.renderReasoningSection(reasoning)`
Renders a detailed reasoning section with methodology and factors.

#### 6. `AIExplainability.renderActionItems(actions)`
Renders recommended actions with rationale and urgency levels.

#### 7. `AIExplainability.renderAlternatives(alternatives)`
Renders alternative approaches with trade-offs.

#### 8. `AIExplainability.renderScenarioAnalysis(scenarios)`
Renders optimistic/realistic/pessimistic scenario cards.

#### 9. `AIExplainability.renderHealthAssessment(health)`
Renders project/task health status with contributing factors.

#### 10. `AIExplainability.renderWhyThisSection(data, collapsible)`
Renders a "Why This?" collapsible section.

#### 11. `AIExplainability.renderAIInsightCard(data, title)`
Renders a comprehensive AI insight card with all components.

#### 12. `AIExplainability.showExplainabilityModal(data, title)`
Shows a modal popup with detailed explainability information.

#### 13. `AIExplainability.renderTooltipContent(data)`
Renders inline tooltip content for quick hover info.

---

## CSS Styles

### Location: `static/css/ai_explainability.css`

Comprehensive styles for all explainability components including:

- `.confidence-meter` - Confidence bar styling
- `.factor-breakdown`, `.factor-item` - Factor display
- `.why-this-section` - Collapsible explanation sections
- `.reasoning-card` - Reasoning display cards
- `.action-items-section`, `.action-item` - Action items
- `.alternatives-section`, `.alternative-card` - Alternatives display
- `.scenario-analysis`, `.scenario-card` - Scenario cards
- `.health-assessment` - Health status display
- `.ai-insight-card` - Comprehensive insight cards
- `.explainability-modal` - Modal styling
- `.explainability-tooltip` - Tooltip content
- `.explainability-badge` - Compact confidence badges

---

## Template Integration

### 1. AI Coach Suggestions (`templates/kanban/partials/suggestion_card.html`)

Each coaching suggestion now includes:
- **Confidence Badge** with visual meter
- **"Why This?"** button to expand explainability
- **Contributing Factors** breakdown
- **Assumptions Made** list
- **Alternative Approaches** when available

Usage: Automatically rendered when using `{% include 'kanban/partials/suggestion_card.html' %}`

### 2. Priority Suggestion Widget (`static/js/priority_suggestion.js`)

Enhanced with:
- **Top Factors** display with contribution percentages
- **"Why This?"** expandable section
- **Urgency/Impact Indicators** breakdown
- **Workload Impact** analysis
- **Assumptions Made** in detail view

### 3. Budget Recommendations (`templates/kanban/budget_dashboard.html`)

Each budget recommendation shows:
- **"Why?"** button for each recommendation
- **Confidence Breakdown** with progress bar
- **AI Reasoning** explanation
- **Considerations** list

### 4. Conflict Resolutions (`templates/kanban/conflicts/detail.html`)

Each resolution suggestion includes:
- **AI Confidence** score with visual bar
- **"Why this works"** explanation
- **Details** expandable section with:
  - Contributing Factors
  - Assumptions
  - Success Indicators

### 5. LSS Classification (`static/js/ai_features.js`)

Classification suggestions now display:
- **Confidence Score** with progress bar
- **Key Factors** that influenced the classification
- **Methodology** explanation

---

## Backend AI Response Structure

All AI functions now return structured data including:

```python
{
    "result": "...",  # The main AI output
    "confidence_score": 0.85,  # 0-1 confidence level
    "contributing_factors": [
        {
            "factor": "Factor Name",
            "contribution_percentage": 25,
            "description": "Why this factor matters"
        }
    ],
    "assumptions": [
        "Assumption 1",
        "Assumption 2"
    ],
    "limitations": [
        "Limitation 1"
    ],
    "reasoning": {
        "methodology": "How the AI analyzed this",
        "confidence_level": "High/Medium/Low",
        "top_factors": [...]
    },
    "alternatives": [
        {
            "approach": "Alternative approach",
            "tradeoffs": "What you'd give up",
            "confidence": 0.7
        }
    ]
}
```

---

## Best Practices for Developers

### Adding Explainability to New AI Features

1. **Backend**: Include explainability in your AI prompt:
```python
response_format = '''
{
    "result": "...",
    "confidence_score": 0.0-1.0,
    "contributing_factors": [...],
    "assumptions": [...],
    "limitations": [...],
    "reasoning": {...}
}
'''
```

2. **Frontend**: Use the AIExplainability module:
```javascript
if (typeof AIExplainability !== 'undefined') {
    const html = AIExplainability.renderAIInsightCard(data, 'My AI Feature');
    document.getElementById('container').innerHTML = html;
}
```

3. **Template**: Include the "Why This?" pattern:
```html
<button onclick="toggleExplain()" class="btn btn-sm btn-outline-info">
    <i class="bi bi-lightbulb"></i> Why?
</button>
<div id="explainability-section" style="display: none;">
    <!-- Use AIExplainability.renderWhyThisSection() -->
</div>
```

### Confidence Level Colors
- **High (≥75%)**: Green (`bg-success`)
- **Medium (50-74%)**: Yellow (`bg-warning`)  
- **Low (<50%)**: Red (`bg-danger`)

### Icons Used
- 🧠 `bi-brain` - AI reasoning
- 📊 `bi-pie-chart` - Contributing factors
- ⚡ `bi-speedometer2` - Confidence/speed
- ⚠️ `bi-exclamation-triangle` - Assumptions/warnings
- 💡 `bi-lightbulb` - Insights/tips
- ✅ `bi-check-circle` - Success indicators
- 🔄 `bi-arrows-angle-expand` - Alternatives

---

## Files Modified in This Enhancement

### JavaScript
- `static/js/ai_explainability.js` - Core rendering module (major enhancement)
- `static/js/priority_suggestion.js` - Priority widget explainability
- `static/js/ai_features.js` - LSS classification and utility functions

### CSS
- `static/css/ai_explainability.css` - Comprehensive styling (major enhancement)

### Templates
- `templates/kanban/partials/suggestion_card.html` - Coach suggestions
- `templates/kanban/budget_dashboard.html` - Budget recommendations
- `templates/kanban/conflicts/detail.html` - Conflict resolutions

### Backend AI Functions (Enhanced with Explainability)
- `kanban/utils/ai_utils.py` - 20+ functions
- `kanban/utils/ai_coach_service.py` - Coaching prompts
- `kanban/budget_ai.py` - Budget analysis
- `kanban/utils/ai_conflict_resolution.py` - Conflict resolution
- `wiki/ai_utils.py` - Wiki AI features
- `kanban/utils/dependency_suggestions.py` - Dependency analysis

---

## Testing Checklist

- [ ] Coach Dashboard: Click "Why?" on each suggestion
- [ ] Task Creation: Use "Generate with AI" and check explainability
- [ ] Priority Suggestion: Expand details to see full reasoning
- [ ] Budget Dashboard: View AI recommendation explanations
- [ ] Conflict Resolution: Check resolution reasoning details
- [ ] LSS Classification: Verify confidence and factors display

---

## Future Enhancements

1. **Feedback Loop**: Allow users to rate explanation helpfulness
2. **Comparison View**: Show before/after for AI suggestions
3. **History Tracking**: Show how AI confidence changed over time
4. **Customization**: Let users choose explanation detail level
