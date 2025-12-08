# AI Coach for Project Managers - Implementation Guide

## Overview

The **AI Coach for Project Managers** is a proactive coaching system that helps PMs make better decisions by:
- Automatically detecting project issues and opportunities
- Providing contextual, AI-powered recommendations
- Learning from feedback to improve suggestions over time
- Training less-experienced PMs through intelligent guidance

## Architecture

### Core Components

```
┌─────────────────────────────────────────────────────────────┐
│                    AI COACH SYSTEM                          │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  ┌──────────────────┐      ┌──────────────────┐          │
│  │  Rule Engine     │      │  AI Enhancement  │          │
│  │  (coaching_rules)│─────>│  (ai_coach)      │          │
│  │                  │      │                  │          │
│  │ • Velocity drops │      │ • Contextual     │          │
│  │ • Resource load  │      │   advice         │          │
│  │ • Risk patterns  │      │ • Deep analysis  │          │
│  │ • Skill opps     │      │ • Explanations   │          │
│  └──────────────────┘      └──────────────────┘          │
│           │                         │                      │
│           └────────────┬────────────┘                      │
│                        ▼                                   │
│           ┌─────────────────────────┐                     │
│           │   CoachingSuggestion     │                     │
│           │   (Data Model)           │                     │
│           └────────────┬─────────────┘                     │
│                        │                                   │
│           ┌────────────▼─────────────┐                     │
│           │   Feedback Learning      │                     │
│           │   (feedback_learning)    │                     │
│           │                          │                     │
│           │ • Track user actions     │                     │
│           │ • Adjust confidence      │                     │
│           │ • Generate insights      │                     │
│           │ • Improve suggestions    │                     │
│           └──────────────────────────┘                     │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

### Data Models

#### 1. **CoachingSuggestion**
Stores AI-generated coaching suggestions.

**Key Fields:**
- `suggestion_type`: Type of suggestion (velocity_drop, resource_overload, etc.)
- `severity`: Priority level (critical, high, medium, low, info)
- `status`: Current state (active, acknowledged, resolved, dismissed)
- `title`, `message`: User-facing content
- `reasoning`: AI explanation of why
- `recommended_actions`: List of action steps
- `confidence_score`: AI confidence (0-1)
- `metrics_snapshot`: Context data when generated
- `was_helpful`: User feedback

#### 2. **CoachingFeedback**
User feedback on suggestions for learning.

**Key Fields:**
- `was_helpful`: Boolean feedback
- `relevance_score`: 1-5 rating
- `action_taken`: What user did (accepted, partially, ignored, etc.)
- `outcome_description`: What happened
- `improved_situation`: Did it help?

#### 3. **PMMetrics**
Performance metrics for project managers.

**Key Fields:**
- `suggestions_received`, `suggestions_acted_on`
- `avg_response_time_hours`
- `velocity_trend`, `deadline_hit_rate`
- `coaching_effectiveness_score`
- `improvement_areas`, `struggle_areas`

#### 4. **CoachingInsight**
Learned patterns from feedback data.

**Key Fields:**
- `insight_type`: Pattern type
- `confidence_score`: Confidence in insight
- `sample_size`: Data points supporting this
- `rule_adjustments`: How to adjust rules
- `is_active`: Whether to apply this learning

## Installation

### Step 1: Add Models to Django

The coach models are in `kanban/coach_models.py`. We need to import them into the kanban app:

```python
# In kanban/models.py, add at the end:
from kanban.coach_models import (
    CoachingSuggestion,
    CoachingFeedback,
    PMMetrics,
    CoachingInsight
)
```

### Step 2: Create Database Migration

```bash
python manage.py makemigrations kanban
python manage.py migrate
```

### Step 3: Register Admin Interfaces

Add to `kanban/admin.py`:

```python
# Import admin configurations
from kanban.coach_admin import (
    CoachingSuggestionAdmin,
    CoachingFeedbackAdmin,
    PMMetricsAdmin,
    CoachingInsightAdmin
)

# Admin classes are already registered with decorators
```

### Step 4: Add URL Patterns

In `kanban/urls.py`, include coach URLs:

```python
from django.urls import path, include

urlpatterns = [
    # ... existing patterns ...
    
    # AI Coach URLs
    path('', include('kanban.coach_urls')),
]
```

### Step 5: Create Management Command

Create `kanban/management/commands/generate_coach_suggestions.py`:

```python
from django.core.management.base import BaseCommand
from kanban.models import Board
from kanban.utils.coaching_rules import CoachingRuleEngine
from kanban.utils.ai_coach_service import AICoachService
from kanban.utils.feedback_learning import FeedbackLearningSystem
from kanban.coach_models import CoachingSuggestion
import logging

logger = logging.getLogger(__name__)

class Command(BaseCommand):
    help = 'Generate coaching suggestions for all active boards'

    def add_arguments(self, parser):
        parser.add_argument(
            '--board-id',
            type=int,
            help='Generate suggestions for specific board only',
        )

    def handle(self, *args, **options):
        board_id = options.get('board_id')
        
        if board_id:
            boards = Board.objects.filter(id=board_id)
        else:
            boards = Board.objects.all()
        
        ai_coach = AICoachService()
        learning_system = FeedbackLearningSystem()
        
        total_generated = 0
        
        for board in boards:
            self.stdout.write(f"Analyzing board: {board.name}")
            
            # Run rule engine
            rule_engine = CoachingRuleEngine(board)
            suggestions_data = rule_engine.analyze_and_generate_suggestions()
            
            # Context for AI
            context = {
                'board_name': board.name,
                'team_size': board.members.count(),
            }
            
            board_generated = 0
            
            for suggestion_data in suggestions_data:
                # Check if should generate based on learning
                if not learning_system.should_generate_suggestion(
                    suggestion_data['suggestion_type'],
                    board,
                    float(suggestion_data['confidence_score'])
                ):
                    continue
                
                # Adjust confidence
                adjusted_confidence = learning_system.get_adjusted_confidence(
                    suggestion_data['suggestion_type'],
                    float(suggestion_data['confidence_score']),
                    board
                )
                suggestion_data['confidence_score'] = adjusted_confidence
                
                # Enhance with AI
                suggestion_data = ai_coach.enhance_suggestion_with_ai(
                    suggestion_data, context
                )
                
                # Create suggestion
                CoachingSuggestion.objects.create(**suggestion_data)
                board_generated += 1
            
            total_generated += board_generated
            self.stdout.write(
                self.style.SUCCESS(
                    f"  Generated {board_generated} suggestions"
                )
            )
        
        self.stdout.write(
            self.style.SUCCESS(
                f"\nTotal: {total_generated} suggestions generated"
            )
        )
```

### Step 6: Set Up Scheduled Task

Add to your task scheduler (cron, celery, etc.):

```bash
# Run every 6 hours
python manage.py generate_coach_suggestions
```

## Usage

### For Project Managers

#### 1. **View Coaching Dashboard**

Navigate to: `/board/{board_id}/coach/`

The dashboard shows:
- Active suggestions grouped by severity
- Coaching effectiveness metrics
- Recent resolved suggestions
- Improvement recommendations

#### 2. **Interact with Suggestions**

Each suggestion shows:
- **Title & Message**: What the issue/opportunity is
- **Reasoning**: Why this matters
- **Recommended Actions**: Specific steps to take
- **Expected Impact**: What will improve

Actions available:
- **Acknowledge**: Mark as seen
- **Provide Feedback**: Rate helpfulness and describe outcome
- **Dismiss**: Not relevant right now

#### 3. **Ask the AI Coach**

Navigate to: `/board/{board_id}/coach/ask/`

Ask questions like:
- "How can I improve team velocity?"
- "What should I do about scope creep?"
- "How do I handle this high-risk convergence?"

Get personalized, context-aware advice.

#### 4. **Review Analytics**

Navigate to: `/board/{board_id}/coach/analytics/`

See:
- Suggestion effectiveness over time
- Which suggestions you act on most
- Areas where you're improving
- Patterns in your PM behavior

### For Administrators

#### 1. **View in Django Admin**

Admin interfaces available for:
- **Coaching Suggestions**: View, filter, manage suggestions
- **Coaching Feedback**: Analyze user feedback
- **PM Metrics**: Track PM performance
- **Coaching Insights**: See learned patterns

#### 2. **Customize Rules**

Edit `kanban/utils/coaching_rules.py` to:
- Adjust thresholds (e.g., what % velocity drop triggers suggestion)
- Add new rule types
- Modify suggestion messages

#### 3. **Monitor Learning**

Check `CoachingInsight` model to see what the system has learned:
- Which suggestions are most effective
- Which contexts make suggestions more helpful
- Recommended confidence adjustments

## Suggestion Types

### 1. **velocity_drop**
**Triggers when**: Team velocity drops by >15%

**Typical actions**:
- Schedule 1-on-1 check-ins
- Review workload distribution
- Identify blockers

### 2. **resource_overload**
**Triggers when**: Team member has >10 active tasks

**Typical actions**:
- Prioritize and redistribute work
- Extend deadlines where possible
- Check for blockers

### 3. **risk_convergence**
**Triggers when**: 3+ high-risk tasks due same week

**Typical actions**:
- Create risk mitigation plan
- Stagger deadlines if possible
- Assign backup resources

### 4. **skill_opportunity**
**Triggers when**: Team member has capacity + developing skills

**Typical actions**:
- Assign stretch assignments
- Pair with senior mentor
- Provide challenging work

### 5. **scope_creep**
**Triggers when**: Scope increases by >15%

**Typical actions**:
- Review added tasks for necessity
- Move lower-priority items to next sprint
- Communicate timeline impact

### 6. **deadline_risk**
**Triggers when**: Burndown prediction shows >30% miss probability

**Typical actions**:
- Review and cut scope
- Add resources
- Communicate timeline risk

### 7. **team_burnout**
**Triggers when**: Velocity declining + quality dropping

**Typical actions**:
- Team check-in on workload
- Lighten sprint commitments
- Ensure breaks and time off

### 8. **quality_issue**
**Triggers when**: Quality score <85/100

**Typical actions**:
- Review definition of done
- Add peer reviews
- Check if team is rushing

### 9. **dependency_blocker**
**Triggers when**: 3+ tasks stalled for >5 days

**Typical actions**:
- Review in standup
- Resolve blocking dependencies
- Move to 'Blocked' status

### 10. **communication_gap**
**Triggers when**: 5+ tasks with no updates in 7 days

**Typical actions**:
- Require status updates
- Check if assignees need help
- Implement daily standups

## AI Enhancement

The system uses two levels of intelligence:

### Level 1: Rule-Based Detection
Fast, reliable pattern detection based on metrics.

**Pros**:
- Predictable and explainable
- Low latency
- No API costs

**Cons**:
- Limited to predefined patterns
- Generic advice

### Level 2: AI Enhancement (Gemini)
Contextual analysis and personalized advice.

**When AI is used**:
- Enhancing rule-based suggestions with context
- Answering PM questions (Ask Coach)
- Analyzing PM performance
- Generating learning content

**What AI adds**:
- Context-specific reasoning
- Nuanced recommendations
- Personalized explanations
- Deeper analysis

## Feedback Learning

The system learns from every interaction:

### 1. **Immediate Learning**
When user provides feedback:
- Updates suggestion effectiveness metrics
- Adjusts confidence scores for similar suggestions
- Records context patterns

### 2. **Batch Learning**
Every 10 feedback entries of same type:
- Generates `CoachingInsight`
- Identifies effectiveness patterns
- Adjusts rule thresholds

### 3. **Continuous Improvement**
Over time:
- Suppresses ineffective suggestion types
- Boosts confidence in helpful patterns
- Personalizes to PM behavior

### Feedback Loop

```
Rule Detects Pattern
        ↓
Generate Suggestion (base confidence)
        ↓
AI Enhancement (if available)
        ↓
Adjust Confidence (based on learning)
        ↓
Show to PM
        ↓
PM Takes Action + Provides Feedback
        ↓
Record Feedback
        ↓
Update Effectiveness Metrics
        ↓
Generate Insights (if enough data)
        ↓
Adjust Future Suggestions ← (loop back)
```

## API Endpoints

### GET `/api/board/{board_id}/coach/suggestions/`
Get coaching suggestions.

**Query params**:
- `status`: Filter by status (active, resolved, etc.)
- `severity`: Filter by severity
- `type`: Filter by suggestion type
- `limit`: Max results (default: 20)

**Response**:
```json
{
  "success": true,
  "suggestions": [
    {
      "id": 1,
      "type": "velocity_drop",
      "severity": "high",
      "title": "Team velocity dropped by 35%",
      "message": "...",
      "recommended_actions": ["...", "..."],
      "confidence_score": 0.85,
      "days_active": 2
    }
  ],
  "count": 1
}
```

### POST `/board/{board_id}/coach/generate/`
Generate new suggestions for a board.

**Response**:
```json
{
  "success": true,
  "created": 5,
  "skipped": 2,
  "message": "Generated 5 new coaching suggestions"
}
```

### POST `/coach/suggestion/{suggestion_id}/acknowledge/`
Acknowledge a suggestion.

### POST `/coach/suggestion/{suggestion_id}/dismiss/`
Dismiss a suggestion.

### POST `/coach/suggestion/{suggestion_id}/feedback/`
Submit detailed feedback.

**Request body**:
```json
{
  "was_helpful": true,
  "relevance_score": 5,
  "action_taken": "accepted",
  "feedback_text": "This was very helpful!",
  "outcome_description": "Velocity improved after team check-in",
  "improved_situation": true
}
```

### POST `/board/{board_id}/coach/ask/`
Ask the AI coach a question.

**Request body**:
```json
{
  "question": "How can I improve team velocity?"
}
```

**Response**:
```json
{
  "success": true,
  "advice": "Based on your current project metrics...",
  "question": "How can I improve team velocity?"
}
```

## Best Practices

### For Development

1. **Test rule thresholds** with real project data
2. **Monitor feedback patterns** to tune suggestions
3. **Use AI enhancement** for complex situations
4. **Keep suggestions actionable** - concrete steps only
5. **Expire old suggestions** to avoid clutter

### For PMs

1. **Check dashboard weekly** to stay proactive
2. **Provide feedback** on every 3rd suggestion (helps learning)
3. **Act on high-severity** suggestions within 48 hours
4. **Use "Ask Coach"** when unsure about situations
5. **Review analytics monthly** to track improvement

### For Training New PMs

1. **Start with dashboard tour** - show suggestion types
2. **Demonstrate feedback loop** - how it learns
3. **Practice with "Ask Coach"** - build confidence
4. **Review analytics together** - discuss patterns
5. **Share success stories** - how suggestions helped

## Troubleshooting

### No suggestions appearing

**Check**:
- Is the board active with tasks?
- Run `python manage.py generate_coach_suggestions --board-id={id}`
- Check Django admin for generated suggestions
- Verify thresholds aren't too strict in rules

### AI enhancement not working

**Check**:
- `GEMINI_API_KEY` configured in settings?
- Check logs for API errors
- Suggestions will still work with rule-based only

### Feedback not improving suggestions

**Check**:
- Need 10+ feedback entries for learning to kick in
- Check `CoachingInsight` model for generated insights
- Verify insights are marked `is_active=True`

### Performance issues

**Optimize**:
- Run suggestion generation as background task
- Add database indexes (already included in models)
- Cache dashboard queries
- Limit historical data queries to 30-90 days

## Future Enhancements

### Phase 2 Ideas

1. **PM Skill Assessment** - Identify PM strengths/weaknesses
2. **Comparative Analytics** - Benchmark against other PMs
3. **Predictive Coaching** - Anticipate issues before they happen
4. **Team Health Score** - Holistic team wellness metric
5. **Integration with Retrospectives** - Link insights to retro findings
6. **Mobile Notifications** - Push critical suggestions
7. **Coaching Chatbot** - Conversational interface
8. **Custom Rule Builder** - Let PMs create their own rules

## Success Metrics

Track these KPIs to measure coaching effectiveness:

1. **Suggestion Acceptance Rate**: % of suggestions acted on (target: >40%)
2. **Situation Improvement Rate**: % where situation improved after action (target: >60%)
3. **PM Response Time**: Time to acknowledge suggestions (target: <48 hours)
4. **Recurring Issue Reduction**: Decrease in repeat suggestions (target: -20% quarter-over-quarter)
5. **Velocity Stabilization**: Reduced velocity variance (target: <30% CV)
6. **Deadline Hit Rate**: % of deadlines met (target: >80%)
7. **Team Satisfaction**: Self-reported or survey-based (target: >4/5)

## Conclusion

The AI Coach for Project Managers transforms PrizmAI from a passive tool into an active partner that helps PMs:
- ✅ Make better decisions proactively
- ✅ Learn from experience (both theirs and others')
- ✅ Avoid common pitfalls
- ✅ Build PM skills over time
- ✅ Maintain project health

It combines the reliability of rule-based systems with the intelligence of AI and the continuous improvement of reinforcement learning.

**Next Steps**:
1. Run migrations to create database tables
2. Generate initial suggestions for active boards
3. Train PMs on using the dashboard
4. Monitor feedback and tune rules
5. Celebrate improved project outcomes!
