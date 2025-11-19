# Intelligent Priority Suggestions - Implementation Guide

## Overview

The Intelligent Priority Suggestions feature uses AI and machine learning to help teams make better priority decisions. It learns from historical priority assignments and provides explainable recommendations for new tasks.

## Features

### 1. **AI-Powered Priority Suggestions**
- Analyzes multiple factors: due dates, dependencies, complexity, team capacity
- Provides confidence scores for transparency
- Shows reasoning behind each suggestion
- Offers alternative priorities

### 2. **Learning from Team Decisions**
- Tracks all priority assignments and corrections
- Learns from accepted and rejected suggestions
- Adapts to your team's priority culture over time

### 3. **Explainable AI**
- Shows top factors influencing the suggestion
- Natural language explanations
- Feature importance visualization
- Confidence levels (High/Moderate/Low)

### 4. **Dual-Mode Operation**
- **Rule-Based Mode**: Works immediately with heuristic rules
- **ML Mode**: Activates after collecting 20+ priority decisions
- Seamless transition between modes

## Architecture

### Models (`kanban/priority_models.py`)

#### `PriorityDecision`
Tracks every priority decision for learning:
- Initial assignments
- Manual corrections
- AI suggestions accepted/rejected
- Full task context snapshot

#### `PriorityModel`
Stores trained ML models per board:
- Random Forest classifier
- Feature importance scores
- Performance metrics
- Version tracking

#### `PrioritySuggestionLog`
Analytics on suggestion usage:
- What was suggested
- User responses
- Accuracy tracking

### AI Service (`ai_assistant/utils/priority_service.py`)

#### `PrioritySuggestionService`
Main service for getting suggestions:
- Feature extraction from tasks
- ML prediction with confidence
- Rule-based fallback
- Explainability generation

#### `PriorityModelTrainer`
Trains classification models:
- Uses historical decisions
- Random Forest classifier
- Cross-validation
- Performance reporting

### API Endpoints

```
POST /api/suggest-priority/
- Get priority suggestion for new/existing task
- Returns: priority, confidence, reasoning, alternatives

POST /api/log-priority-decision/
- Log priority decision for learning
- Tracks accepts/rejects for model improvement

POST /api/board/<id>/train-priority-model/
- Train/retrain model for board
- Requires 20+ historical decisions

GET /api/board/<id>/priority-model-info/
- Get model status and metrics
- Check if model is available
```

## Usage

### For Users

#### 1. **Get Priority Suggestions**
When creating or editing a task:
1. Fill in task details (title, due date, complexity)
2. Click "AI Suggest Priority" button
3. Review suggestion with reasoning
4. Accept, reject, or choose alternative

#### 2. **Provide Feedback**
Your decisions help the AI learn:
- **Accept**: Confirms the AI's understanding
- **Reject**: Teaches what's wrong
- **Modify**: Provides nuanced feedback

### For Administrators

#### 1. **Initial Setup**
```bash
# Install ML dependencies
pip install scikit-learn numpy

# Run migrations
python manage.py migrate

# The system works immediately in rule-based mode
```

#### 2. **Training Models**
After collecting 20+ priority decisions:

```bash
# Train model for specific board
python manage.py train_priority_models --board-id 1

# Train all boards with sufficient data
python manage.py train_priority_models --all

# Force training with fewer samples (not recommended)
python manage.py train_priority_models --board-id 1 --force
```

#### 3. **Monitor Performance**
Access via Django Admin:
- View model accuracy and metrics
- Track suggestion acceptance rates
- Analyze feature importance

## How It Works

### Phase 1: Rule-Based (Immediate)
Uses heuristic scoring:
- **Due date urgency**: Overdue = +4 points
- **Blocking tasks**: 3+ blocks = +3 points
- **Complexity**: High = +2 points
- **Risk score**: High risk = +2 points
- **Collaboration**: Required = +1 point

Score thresholds:
- 8+ points → Urgent
- 5-7 points → High
- 3-4 points → Medium
- 0-2 points → Low

### Phase 2: Machine Learning (After 20+ decisions)

#### Training Process:
1. Collect historical priority decisions
2. Extract 14 features per decision:
   - Temporal: days until due, is overdue
   - Complexity: complexity score
   - Dependencies: blocking/blocked counts
   - Resources: assignee workload, team capacity
   - Context: description length, labels, risk
   - Relationships: subtasks, collaboration

3. Train Random Forest classifier:
   - 100 trees, max depth 10
   - Balanced class weights
   - 80/20 train/test split

4. Evaluate performance:
   - Overall accuracy
   - Per-class precision/recall/F1
   - Feature importance ranking

#### Prediction Process:
1. Extract features from task
2. Get probability distribution across priorities
3. Select highest probability class
4. Calculate confidence score
5. Generate reasoning from feature importance
6. Provide alternatives

### Explainability

The system explains suggestions through:

1. **Feature Importance**: Which factors matter most
2. **Top Factors**: Specific values that influenced decision
3. **Natural Language**: "This task should be **high** priority because..."
4. **Alternatives**: Other viable priorities with confidence scores

## Best Practices

### For Teams

1. **Be Consistent**: Use priorities consistently in the first 20 decisions
2. **Provide Context**: Fill in due dates, complexity, and dependencies
3. **Give Feedback**: Accept/reject suggestions to improve accuracy
4. **Review Periodically**: Retrain models as team practices evolve

### For Developers

1. **Monitor Model Performance**: Track accuracy over time
2. **Retrain Regularly**: Quarterly or after 100+ new decisions
3. **Handle Edge Cases**: System gracefully falls back to rules
4. **Respect Privacy**: Task context is board-scoped

## Configuration

### Feature Weights (Customizable)
Edit `ai_assistant/utils/priority_service.py`:

```python
PRIORITY_WEIGHTS = {
    'low': 1,
    'medium': 2,
    'high': 3,
    'urgent': 4
}
```

### Model Parameters
Edit `PriorityModelTrainer.train_model()`:

```python
RandomForestClassifier(
    n_estimators=100,      # Number of trees
    max_depth=10,          # Tree depth
    min_samples_split=5,   # Min samples to split
    class_weight='balanced' # Handle imbalanced data
)
```

### Minimum Training Samples
Default: 20 decisions per board
- Configurable via `--min-samples` flag
- Can force with `--force` flag (not recommended)

## Performance Metrics

### Expected Accuracy
- **20-50 decisions**: 60-70% accuracy
- **50-100 decisions**: 70-80% accuracy
- **100+ decisions**: 80-90% accuracy

### Feature Importance (Typical)
1. Days until due: ~25%
2. Complexity score: ~18%
3. Is overdue: ~15%
4. Blocking count: ~12%
5. Team capacity: ~10%
6. Others: ~20%

## Troubleshooting

### "Failed to get priority suggestion"
- Check API endpoint is accessible
- Verify user has board access
- Check browser console for errors

### "Insufficient training data"
- Need at least 20 priority decisions
- Use rule-based mode until then
- Check decision count in admin panel

### Low model accuracy
- Need more training samples
- Ensure consistent priority usage
- Check for data quality issues
- Consider retraining with updated data

### Model not activating
- Verify migration ran successfully
- Check model exists in admin panel
- Ensure `is_active` flag is True
- Try retraining model

## Testing

Run tests:
```bash
python manage.py test kanban.tests.test_priority_suggestion
```

Test coverage includes:
- Rule-based suggestions
- Feature extraction
- Decision logging
- API endpoints
- Model training simulation

## Future Enhancements

Potential improvements:
1. **Deep Learning**: Neural networks for complex patterns
2. **Time Series**: Learn from temporal patterns
3. **Collaborative Filtering**: Learn from similar projects
4. **Active Learning**: Focus on uncertain predictions
5. **Multi-Board Learning**: Share knowledge across boards
6. **Real-Time Updates**: Retrain on new decisions automatically

## Support

For issues or questions:
1. Check logs: `logs/django.log`
2. Review admin panel: Priority Models section
3. Inspect browser console for client errors
4. Test API endpoints directly with curl/Postman

## License

Part of PrizmAI project. See main LICENSE file.
