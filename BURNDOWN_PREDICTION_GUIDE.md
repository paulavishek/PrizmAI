# Burndown/Burnup Prediction with Confidence Intervals

## Overview

PrizmAI now includes **statistical burndown/burnup prediction** with confidence intervals - a powerful forecasting feature that helps teams understand when projects will complete with a quantified confidence level.

## What This Feature Does

### 🎯 Core Capabilities

1. **Projects Completion Date with Confidence Intervals**
   - Shows: "We'll finish **May 15** (±3 days, 90% confidence)"
   - Provides upper and lower bounds based on historical variance
   - Updates predictions as team velocity changes

2. **Risk Assessment & Probability**
   - Warns: "Current velocity shows **15% miss probability**"
   - Calculates delay probability compared to target dates
   - Categorizes risk levels: Low, Medium, High, Critical

3. **Actionable Suggestions**
   - AI-generated recommendations to improve completion probability
   - Prioritized by impact and effort
   - Context-aware based on current situation

4. **Visual Confidence Bands**
   - Burndown chart with confidence interval bands
   - Historical vs. predicted progress visualization
   - Ideal burndown line for comparison

## Why This is Valuable

✅ **Accurate Timeline Communication**
- Move beyond simple linear projections
- Communicate realistic ranges to stakeholders
- Build confidence with data-driven estimates

✅ **Early Warning System**
- Detect delays before they become critical
- Alert when velocity drops or variance increases
- Proactive risk management

✅ **Better Than Simple Projections**
- Accounts for team velocity variance/noise
- Statistical confidence intervals (90%, 95%, 99%)
- Learns from historical performance

## Implementation Details

### Architecture

```
┌─────────────────────────────────────────┐
│  Burndown Prediction System             │
├─────────────────────────────────────────┤
│                                          │
│  1. Velocity Tracking                   │
│     - TeamVelocitySnapshot model        │
│     - Weekly/Sprint velocity capture    │
│     - Team composition tracking         │
│                                          │
│  2. Statistical Engine                  │
│     - Mean velocity calculation         │
│     - Standard deviation (variance)     │
│     - Confidence interval computation   │
│     - Z-score based projections         │
│                                          │
│  3. Risk Assessment                     │
│     - Delay probability calculation     │
│     - Risk level classification         │
│     - Target date comparison            │
│                                          │
│  4. AI Suggestion Engine                │
│     - Context-aware recommendations     │
│     - Impact/effort scoring             │
│     - Priority ranking                  │
│                                          │
│  5. Visualization                       │
│     - Interactive burndown charts       │
│     - Confidence band display           │
│     - Real-time alert system            │
│                                          │
└─────────────────────────────────────────┘
```

### Models

#### 1. **TeamVelocitySnapshot**
Tracks team velocity over time for statistical analysis.

**Fields:**
- `period_start`, `period_end` - Time period for measurement
- `tasks_completed` - Number of tasks completed
- `story_points_completed` - Complexity points completed
- `active_team_members` - Team size during period
- `quality_score` - Quality metric (100 - reopened%)

#### 2. **BurndownPrediction**
Stores prediction results with confidence intervals.

**Key Fields:**
- `predicted_completion_date` - Most likely completion (50th percentile)
- `completion_date_lower_bound` - Early completion (10th percentile)
- `completion_date_upper_bound` - Late completion (90th percentile)
- `days_margin_of_error` - ±days margin
- `delay_probability` - % probability of missing target
- `risk_level` - low, medium, high, critical
- `velocity_std_dev` - Standard deviation (measures variance)
- `actionable_suggestions` - AI-generated recommendations

#### 3. **BurndownAlert**
Alerts for issues requiring attention.

**Alert Types:**
- `velocity_drop` - Velocity decreased significantly
- `scope_creep` - Scope increased unexpectedly
- `target_risk` - Target date at risk
- `variance_high` - High velocity variance
- `stagnation` - Progress stalled

#### 4. **SprintMilestone**
Track sprint/project milestones for progress visualization.

### Statistical Techniques

#### Confidence Interval Calculation

The system uses **standard error** and **Z-scores** to calculate confidence intervals:

```python
# Standard error for completion time
SE = std_dev / sqrt(n_periods)

# Confidence interval bounds
margin = Z_score * SE * sqrt(n_periods)
upper_bound = predicted_date + margin
lower_bound = predicted_date - margin
```

**Z-scores used:**
- 90% confidence: ±1.645
- 95% confidence: ±1.960
- 99% confidence: ±2.576

#### Velocity Variance Analysis

**Coefficient of Variation (CV):**
```python
CV = (std_dev / mean_velocity) * 100
```

- CV < 20%: Low variance, high confidence
- CV 20-40%: Medium variance, moderate confidence
- CV > 40%: High variance, lower confidence

#### Risk Assessment

**Delay Probability Calculation:**
Uses normal distribution approximation based on distance from target:

```python
z = (target_date - predicted_date) / margin_of_error

# Probability mapping
if z > 2: prob_meet = 97%
if z > 1: prob_meet = 84%
if z > 0: prob_meet = 65%
# ... etc
```

### AI Techniques

#### 1. **Velocity Trend Detection**
Simple regression to detect if velocity is:
- **Increasing**: Recent avg > Historical avg (>10%)
- **Stable**: Change within ±10%
- **Decreasing**: Recent avg < Historical avg (<-10%)

#### 2. **Confidence Scoring**
Multi-factor confidence calculation:
```python
confidence = (
    sample_score * 0.3 +      # More data = higher confidence
    variance_score * 0.4 +     # Lower variance = higher confidence
    consistency_score * 0.3    # Recent consistency = higher confidence
)
```

#### 3. **Actionable Suggestion Engine**
Context-aware recommendations based on:
- **Risk Level**: Higher risk → more aggressive suggestions
- **Velocity Variance**: High variance → process improvement focus
- **Velocity Trend**: Declining → investigate root causes
- **Delay Probability**: High probability → scope/capacity actions

**Suggestion Types:**
- `reduce_scope` - Defer low-priority work
- `stabilize_velocity` - Reduce WIP, remove blockers
- `address_slowdown` - Investigate velocity decline
- `increase_capacity` - Add team members or resources
- `process_improvement` - Improve estimation, testing, reviews
- `increase_monitoring` - Daily progress tracking

## Usage Guide

### Accessing Burndown Predictions

1. **From Board View:**
   - Click **"Burndown"** button in the navigation bar
   
2. **Or via URL:**
   - Navigate to: `/board/<board_id>/burndown/`

### Generating Predictions

1. Click **"Generate New Prediction"** button
2. System automatically:
   - Calculates recent velocity from task completions
   - Analyzes velocity variance and trends
   - Projects completion date with confidence bands
   - Assesses risk and generates alerts
   - Creates actionable suggestions

### Understanding the Dashboard

#### Completion Forecast Section
- **Predicted Completion**: Most likely date (50th percentile)
- **Completion Range**: Confidence interval bounds
- **Days Until Completion**: Working days remaining
- **Risk Level**: Current risk classification

#### Progress Metrics
- **Tasks Completed/Remaining**: Current scope status
- **Current Velocity**: Recent completion rate
- **Velocity Trend**: Direction (increasing/stable/decreasing)

#### Burndown Chart
- **Green Line**: Actual progress (historical)
- **Blue Dashed Line**: Predicted progress (future)
- **Blue Shaded Area**: Confidence bands (90%)
- **Gray Dashed Line**: Ideal burndown path

#### Active Alerts
- **Critical**: Requires immediate action
- **Warning**: Monitor closely
- **Info**: For awareness

#### Actionable Suggestions
- Numbered by priority (1 = highest)
- Impact level: Critical, High, Medium, Low
- Effort estimate: High, Medium, Low

### API Endpoints

#### Generate Prediction
```
POST /board/<board_id>/burndown/generate/
```

**Response:**
```json
{
  "success": true,
  "prediction": {
    "predicted_date": "2025-05-15",
    "lower_bound": "2025-05-12",
    "upper_bound": "2025-05-18",
    "days_until": 21,
    "margin_of_error": 3,
    "confidence": 90,
    "delay_probability": 15.0,
    "risk_level": "medium"
  }
}
```

#### Get Chart Data
```
GET /board/<board_id>/burndown/chart-data/
```

Returns burndown curve with confidence bands for visualization.

#### Get Velocity Data
```
GET /board/<board_id>/burndown/velocity-data/
```

Returns historical velocity snapshots for trend analysis.

#### Get Suggestions
```
GET /board/<board_id>/burndown/suggestions/
```

Returns AI-generated actionable suggestions.

## Best Practices

### 1. Regular Prediction Updates
- Generate predictions **weekly** or at sprint boundaries
- Track accuracy over time
- Adjust team processes based on insights

### 2. Respond to Alerts
- **Acknowledge** alerts when seen
- **Resolve** after taking corrective action
- Don't ignore critical alerts

### 3. Act on Suggestions
- Prioritize high-impact, low-effort suggestions first
- Document decisions and outcomes
- Share insights with team

### 4. Build Velocity History
- Minimum **3 weeks** of data for basic predictions
- Best with **8+ weeks** for reliable confidence intervals
- Consistent team composition improves accuracy

### 5. Maintain Quality Data
- Mark tasks complete when truly done
- Use consistent complexity scoring
- Track task reopenings for quality metrics

## Interpreting Results

### Confidence Levels

**90% Confidence (Default):**
- "We're 90% confident completion will fall within this range"
- 10% chance of finishing earlier
- 10% chance of finishing later

**Narrow Ranges (±1-2 days):**
- Consistent team velocity
- Low variance in performance
- High prediction reliability

**Wide Ranges (±7+ days):**
- Variable team velocity
- High uncertainty
- May need process stabilization

### Risk Levels

**Low Risk (<15% delay probability):**
- ✅ On track, monitoring sufficient
- Continue current pace

**Medium Risk (15-30% delay probability):**
- ⚠️ Watch closely, consider actions
- Review priorities and blockers

**High Risk (30-50% delay probability):**
- ⚠️ Action recommended
- Implement suggestions
- Daily monitoring

**Critical Risk (>50% delay probability):**
- 🚨 Immediate intervention required
- Scope reduction or capacity increase
- Stakeholder communication essential

### Velocity Trends

**Increasing Velocity:**
- Team improving efficiency
- Learning curve effect
- Process improvements working

**Stable Velocity:**
- Predictable performance
- Mature team processes
- Reliable forecasting

**Decreasing Velocity:**
- 🚨 Investigate immediately
- Possible causes:
  - Technical debt accumulation
  - Team morale issues
  - Scope creep or unclear requirements
  - External blockers

## Technical Requirements

### Dependencies
- Django 4.x+
- Chart.js 4.x (for visualization)
- Python 3.8+ (for statistics module)

### Database
- New tables created via migrations
- Indexes on frequently queried fields
- JSON fields for flexible data storage

### Performance
- Velocity snapshots calculated once per period
- Predictions cached for 24 hours
- Chart data served via API endpoints

## Troubleshooting

### "Insufficient Data" Message
**Cause:** Less than 3 velocity snapshots available  
**Solution:** 
- Complete more tasks over multiple weeks
- System auto-generates snapshots from task completions
- Manual creation possible via admin

### Wide Confidence Intervals
**Cause:** High velocity variance  
**Solution:**
- Focus on stabilizing workflow
- Reduce work-in-progress
- Remove blockers promptly
- Improve estimation accuracy

### Inaccurate Predictions
**Cause:** Team composition changes, scope changes  
**Solution:**
- Regenerate prediction after major changes
- Use milestone markers for scope boundaries
- Consider separate predictions per phase

## Future Enhancements

Potential improvements for future versions:

1. **Multiple Confidence Levels**
   - User-selectable (90%, 95%, 99%)
   - Compare different scenarios

2. **What-If Analysis**
   - "What if we add 2 team members?"
   - "What if we descope 5 tasks?"

3. **Monte Carlo Simulation**
   - More sophisticated probability modeling
   - Account for task dependencies

4. **Machine Learning Integration**
   - Learn from prediction accuracy
   - Personalized confidence scoring
   - Factor detection (holidays, team events)

5. **Integration with Resource Forecasting**
   - Combined capacity and burndown predictions
   - Skill-weighted velocity calculations

## References

### Statistical Methods
- **Confidence Intervals**: Standard error and Z-scores
- **Coefficient of Variation**: Measure of relative variability
- **Linear Regression**: Trend detection

### Agile Metrics
- **Velocity**: Work completed per time period
- **Burndown Charts**: Visual progress tracking
- **Sprint Predictions**: Completion forecasting

---

## Support & Feedback

For questions or suggestions about burndown predictions:
- Review this documentation
- Check the Django admin for raw data
- Examine the `BurndownPredictor` class for algorithm details
- Test with sample data to understand behavior

**Version:** 1.0.0  
**Last Updated:** November 2025  
**Module:** `kanban.burndown_models`, `kanban.utils.burndown_predictor`
