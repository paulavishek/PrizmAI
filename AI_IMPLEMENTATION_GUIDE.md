# AI Enhancement Implementation Guide
**Technical Roadmap for 18 AI Features**

---

## Overview

This document provides technical implementation details for integrating 18 AI-powered features into PrizmAI. Features are organized by priority and estimated effort.

**Tech Stack Assumptions:**
- Django 5.2, Python 3.10+
- Google Gemini API (already integrated)
- PostgreSQL (for production)
- Redis (for caching/queues)
- Celery (for async tasks)
- Django REST Framework (API)

---

## TIER 1: High Impact, Medium Effort

### 1. Predictive Task Completion Dates

#### Model Architecture
```
Input Features:
  - Task complexity_score (1-10)
  - Task priority (low, medium, high, urgent)
  - Assigned team member (performance history)
  - Task dependencies (number of blockers)
  - Current progress (%)
  - Days since creation
  - Similar task historical completion time
  - Team member's current workload
  - Time of year / sprint cycle

Output:
  - Predicted completion date
  - Confidence interval (±N days)
  - Probability of on-time completion (%)
  - Key factors affecting prediction
```

#### Database Schema
```sql
-- New model: TaskPrediction
- task_id (FK)
- predicted_completion_date (DateTime)
- confidence_interval_days (Integer)
- confidence_score (0-1)
- probability_on_time (0-100)
- model_version (for tracking)
- last_updated (DateTime)
- factors_json (stores contributing factors)

-- Extend Task model:
- historical_completion_rate (calculated field)
- average_duration_days (calculated field)
- team_member_velocity (calculated on Task model)
```

#### Implementation Steps

**Step 1: Data Collection (Week 1)**
```python
# In kanban/models.py - extend Task model
def get_completion_history(self):
    """Get historical completion data for similar tasks"""
    similar_tasks = Task.objects.filter(
        column__board=self.column.board,
        complexity_score=self.complexity_score,
        priority=self.priority,
    ).exclude(id=self.id)
    
    completed = similar_tasks.filter(
        progress=100,
        updated_at__isnull=False
    )
    
    completion_times = []
    for task in completed:
        duration = (task.updated_at - task.created_at).days
        completion_times.append(duration)
    
    return completion_times

def get_team_member_velocity(self):
    """Calculate velocity for assigned team member"""
    if not self.assigned_to:
        return 1.0
    
    completed_tasks = Task.objects.filter(
        assigned_to=self.assigned_to,
        progress=100
    ).count()
    
    total_tasks = Task.objects.filter(
        assigned_to=self.assigned_to
    ).count()
    
    return completed_tasks / total_tasks if total_tasks > 0 else 1.0
```

**Step 2: Feature Engineering (Week 1-2)**
```python
# ai_assistant/utils/prediction_service.py
from datetime import datetime, timedelta
import numpy as np
from django.utils import timezone

class TaskCompletionPredictor:
    
    def get_features(self, task):
        """Extract features for prediction"""
        features = {
            'complexity': task.complexity_score / 10,
            'priority': self._encode_priority(task.priority),
            'dependency_count': task.dependencies.count(),
            'current_progress': task.progress / 100,
            'days_since_creation': (timezone.now() - task.created_at).days,
            'has_due_date': 1 if task.due_date else 0,
            'team_velocity': task.get_team_member_velocity(),
            'team_workload': self._calculate_team_workload(task.assigned_to),
        }
        
        # Add historical average
        historical_times = task.get_completion_history()
        if historical_times:
            features['historical_avg_days'] = np.mean(historical_times)
            features['historical_std_days'] = np.std(historical_times)
        else:
            features['historical_avg_days'] = 5  # default
            features['historical_std_days'] = 2
        
        return features
    
    def _encode_priority(self, priority):
        """Encode priority levels"""
        priority_map = {'low': 1, 'medium': 2, 'high': 3, 'urgent': 4}
        return priority_map.get(priority, 2)
    
    def _calculate_team_workload(self, user):
        """Calculate team member's current workload"""
        if not user:
            return 0
        
        incomplete_tasks = Task.objects.filter(
            assigned_to=user,
            progress__lt=100
        ).count()
        
        return incomplete_tasks
    
    def predict(self, task):
        """Generate prediction for task"""
        features = self.get_features(task)
        
        # Simple regression model (can be replaced with ML model)
        base_days = features['historical_avg_days']
        
        # Adjustments
        if features['progress'] == 0:
            # Not started - assume full time
            adjustment = 1.0
        else:
            # In progress - estimate remaining based on progress
            adjustment = 1 - features['progress']
        
        adjusted_days = base_days * adjustment
        
        # Complexity multiplier
        complexity_mult = 0.8 + (features['complexity'] * 0.4)
        adjusted_days *= complexity_mult
        
        # Workload impact
        if features['team_workload'] > 5:
            adjusted_days *= 1.2
        elif features['team_workload'] > 3:
            adjusted_days *= 1.1
        
        # Calculate confidence
        std = features.get('historical_std_days', 2)
        confidence = 1 - (std / (base_days + std))  # 0-1 scale
        confidence_score = max(0.5, min(0.95, confidence))
        
        predicted_date = timezone.now() + timedelta(days=int(adjusted_days))
        confidence_interval = int(std * 1.96)  # 95% CI
        
        # Probability of on-time completion
        if task.due_date:
            days_until_due = (task.due_date - timezone.now()).days
            days_remaining = adjusted_days
            prob_ontime = 100 if days_remaining <= days_until_due else max(10, 100 - (days_remaining - days_until_due) * 10)
        else:
            prob_ontime = 75
        
        return {
            'predicted_date': predicted_date,
            'confidence_interval_days': confidence_interval,
            'confidence_score': confidence_score,
            'probability_on_time': max(5, min(95, int(prob_ontime))),
            'factors': {
                'complexity': f"{features['complexity']*100:.0f}% - {'High' if features['complexity'] > 0.7 else 'Medium' if features['complexity'] > 0.3 else 'Low'}",
                'workload': f"{features['team_workload']} active tasks",
                'history': f"Avg {features['historical_avg_days']:.0f} days for similar tasks",
                'progress': f"{features['progress']*100:.0f}% complete",
            }
        }
```

**Step 3: API Endpoint (Week 2)**
```python
# api/v1/views.py - add endpoint
@api_view(['GET'])
@permission_classes([IsAuthenticated])
def predict_task_completion(request, task_id):
    """Get completion prediction for a task"""
    task = get_object_or_404(Task, id=task_id)
    
    # Check access
    if not has_board_access(request.user, task.column.board):
        return Response({'error': 'Access denied'}, status=403)
    
    from ai_assistant.utils.prediction_service import TaskCompletionPredictor
    predictor = TaskCompletionPredictor()
    prediction = predictor.predict(task)
    
    return Response(prediction)
```

**Step 4: Frontend Display (Week 2)**
```javascript
// Show prediction in task detail modal
function displayPrediction(taskId) {
    fetch(`/api/v1/tasks/${taskId}/predict-completion/`)
        .then(r => r.json())
        .then(data => {
            const html = `
                <div class="prediction-card">
                    <h6>📅 Predicted Completion</h6>
                    <div class="prediction-date">
                        ${formatDate(data.predicted_date)}
                    </div>
                    <div class="confidence">
                        Confidence: ${(data.confidence_score*100).toFixed(0)}%
                        (±${data.confidence_interval_days} days)
                    </div>
                    <div class="probability">
                        ${data.probability_on_time}% likely on-time
                    </div>
                    <details>
                        <summary>Factors</summary>
                        <ul>
                            ${Object.entries(data.factors).map(([k, v]) => 
                                `<li>${k}: ${v}</li>`
                            ).join('')}
                        </ul>
                    </details>
                </div>
            `;
            document.getElementById('prediction-container').innerHTML = html;
        });
}
```

#### Expected Impact
- **Accuracy**: 70-80% for first sprint (improves with data)
- **Time saved**: 2-3 hours/week estimating tasks
- **Value**: Early detection of schedule risks

---

### 2. AI-Powered Meeting Assistant

#### Architecture

```
Flow:
1. User uploads meeting recording or transcript
2. System extracts audio (if recording)
3. Transcribe to text (Gemini or external API)
4. AI analyzes: decisions, action items, risks, attendees
5. Create tasks automatically with context
6. Suggest assignees based on discussion content
```

#### Implementation

**Step 1: File Upload & Storage (Week 1)**
```python
# In kanban/models.py - add model
class MeetingTranscript(models.Model):
    board = models.ForeignKey(Board, on_delete=models.CASCADE)
    title = models.CharField(max_length=200)
    
    # Original file
    file_type = models.CharField(choices=[('audio', 'Audio'), ('transcript', 'Text Transcript')])
    file = models.FileField(upload_to='meetings/')
    
    # Processed
    transcript_text = models.TextField(blank=True, null=True)
    processed_at = models.DateTimeField(null=True)
    
    # AI Analysis
    ai_summary = models.TextField(blank=True, null=True)
    extracted_items = models.JSONField(default=dict)  # {action_items, decisions, risks, etc}
    
    created_at = models.DateTimeField(auto_now_add=True)
    created_by = models.ForeignKey(User, on_delete=models.CASCADE)
    
    def __str__(self):
        return f"{self.title} - {self.created_at.date()}"
```

**Step 2: Transcription Service (Week 1-2)**
```python
# ai_assistant/utils/meeting_service.py
import io
from datetime import datetime
from django.core.files.base import ContentFile

class MeetingAssistant:
    
    def process_meeting_file(self, transcript_obj):
        """Process meeting file and extract transcript"""
        
        if transcript_obj.file_type == 'audio':
            # Use Google Speech-to-Text or similar
            transcript_text = self._transcribe_audio(transcript_obj.file)
        else:
            # Read text file directly
            transcript_text = transcript_obj.file.read().decode('utf-8')
        
        # Save transcript
        transcript_obj.transcript_text = transcript_text
        transcript_obj.processed_at = datetime.now()
        transcript_obj.save()
        
        # Analyze
        self.analyze_transcript(transcript_obj)
        
        return transcript_obj
    
    def _transcribe_audio(self, audio_file):
        """Transcribe audio file using Google API"""
        import google.cloud.speech as speech
        
        client = speech.SpeechClient()
        
        # Read audio content
        with audio_file.open('rb') as f:
            content = f.read()
        
        audio = speech.RecognitionAudio(content=content)
        config = speech.RecognitionConfig(
            encoding=speech.RecognitionConfig.AudioEncoding.MP3,
            sample_rate_hertz=16000,
            language_code="en-US",
        )
        
        response = client.recognize(config=config, audio=audio)
        
        transcript = ""
        for result in response.results:
            transcript += result.alternatives[0].transcript + "\n"
        
        return transcript
    
    def analyze_transcript(self, transcript_obj):
        """Use Gemini to analyze meeting transcript"""
        from ai_assistant.utils.ai_clients import GeminiClient
        
        gemini = GeminiClient()
        
        prompt = f"""
        Analyze the following meeting transcript and extract:
        1. Key decisions made
        2. Action items (with who should do them)
        3. Risks or concerns mentioned
        4. Timeline/deadlines discussed
        5. Attendees and their roles
        6. Project scope discussed
        
        Format your response as JSON:
        {{
            "decisions": ["decision 1", "decision 2"],
            "action_items": [
                {{"task": "description", "owner": "name if mentioned", "due_date": "if mentioned"}},
            ],
            "risks": ["risk 1", "risk 2"],
            "timeline": "description of timeline",
            "attendees": ["person1", "person2"],
            "scope": "project scope discussed"
        }}
        
        Meeting transcript:
        {transcript_obj.transcript_text[:3000]}
        """
        
        response = gemini.get_response(prompt)
        
        import json
        try:
            extracted = json.loads(response)
        except:
            # Fallback: extract what we can
            extracted = self._parse_response_fallback(response)
        
        transcript_obj.extracted_items = extracted
        transcript_obj.ai_summary = response
        transcript_obj.save()
        
        return extracted
    
    def create_tasks_from_transcript(self, transcript_obj, board):
        """Create tasks from extracted action items"""
        from kanban.models import Task, Column
        
        extracted = transcript_obj.extracted_items
        if not extracted:
            return []
        
        # Find appropriate column
        to_do_col = Column.objects.filter(
            board=board,
            name__icontains='to do'
        ).first()
        
        if not to_do_col:
            to_do_col = board.columns.first()
        
        created_tasks = []
        
        for item in extracted.get('action_items', []):
            task = Task.objects.create(
                title=item.get('task', 'Action Item'),
                description=f"From meeting: {transcript_obj.title}\n\nDiscussion: {item.get('discussion', '')}",
                column=to_do_col,
                created_by=transcript_obj.created_by,
                priority='high' if 'urgent' in item.get('task', '').lower() else 'medium',
            )
            
            # Set due date if mentioned
            if item.get('due_date'):
                task.due_date = self._parse_date(item['due_date'])
            
            # Assign if owner is mentioned
            owner_name = item.get('owner', '')
            if owner_name:
                owner = self._find_team_member(owner_name, board)
                if owner:
                    task.assigned_to = owner
            
            task.save()
            created_tasks.append(task)
        
        return created_tasks
    
    def _find_team_member(self, name, board):
        """Find team member by name"""
        for member in board.members.all():
            if name.lower() in member.get_full_name().lower():
                return member
        return None
    
    def _parse_date(self, date_str):
        """Parse date string"""
        # Simple implementation; can be enhanced
        from dateutil import parser
        try:
            return parser.parse(date_str)
        except:
            return None
```

**Step 3: API Endpoint (Week 2)**
```python
# kanban/views.py
@login_required
def upload_meeting(request, board_id):
    """Upload and process meeting"""
    if request.method == 'POST':
        board = get_object_or_404(Board, id=board_id)
        
        # Check access
        if not (board.created_by == request.user or request.user in board.members.all()):
            return JsonResponse({'error': 'Access denied'}, status=403)
        
        from kanban.models import MeetingTranscript
        from ai_assistant.utils.meeting_service import MeetingAssistant
        
        # Create transcript record
        transcript = MeetingTranscript.objects.create(
            board=board,
            title=request.POST.get('title', 'Untitled Meeting'),
            file_type=request.POST.get('file_type', 'transcript'),
            file=request.FILES.get('file'),
            created_by=request.user
        )
        
        # Process async
        from celery import shared_task
        process_meeting_async.delay(transcript.id, board_id)
        
        return JsonResponse({
            'id': transcript.id,
            'status': 'processing',
            'title': transcript.title
        })
    
    # GET - show upload form
    return render(request, 'kanban/upload_meeting.html', {'board': board})

@shared_task
def process_meeting_async(transcript_id, board_id):
    """Process meeting file asynchronously"""
    from kanban.models import MeetingTranscript, Board
    from ai_assistant.utils.meeting_service import MeetingAssistant
    
    transcript = MeetingTranscript.objects.get(id=transcript_id)
    board = Board.objects.get(id=board_id)
    
    assistant = MeetingAssistant()
    
    try:
        # Process file
        assistant.process_meeting_file(transcript)
        
        # Create tasks
        created = assistant.create_tasks_from_transcript(transcript, board)
        
        # Send notification
        messages.success(
            request,
            f"Meeting processed! Created {len(created)} tasks"
        )
    except Exception as e:
        print(f"Meeting processing error: {e}")
        transcript.ai_summary = f"Error: {str(e)}"
        transcript.save()
```

#### Expected Impact
- **Time saved**: 15-20 min per meeting
- **Accuracy**: 85%+ for action item extraction
- **Value**: Eliminates "who was supposed to do that?" arguments

---

### 3. Intelligent Priority Suggestions

#### Simple Implementation (Week 1)
```python
# kanban/utils/priority_service.py
from django.utils import timezone
from datetime import timedelta

class PrioritySuggester:
    
    def suggest_priority(self, task):
        """Suggest priority based on multiple factors"""
        
        score = 0
        factors = []
        
        # Factor 1: Time urgency (due date)
        if task.due_date:
            days_until_due = (task.due_date - timezone.now()).days
            if days_until_due <= 1:
                score += 40
                factors.append("Due very soon (critical)")
            elif days_until_due <= 3:
                score += 30
                factors.append("Due within 3 days")
            elif days_until_due <= 7:
                score += 15
                factors.append("Due within a week")
        
        # Factor 2: Dependencies
        dependent_count = task.dependent_tasks.count()
        if dependent_count >= 3:
            score += 25
            factors.append(f"{dependent_count} tasks depend on this")
        elif dependent_count >= 1:
            score += 10
            factors.append("Other tasks depend on this")
        
        # Factor 3: Team member workload
        if task.assigned_to:
            active_tasks = Task.objects.filter(
                assigned_to=task.assigned_to,
                progress__lt=100
            ).count()
            if active_tasks <= 2:
                score += 5
                factors.append("Assigned person is available")
            elif active_tasks >= 5:
                score -= 10
                factors.append("Assigned person is overloaded")
        
        # Factor 4: Complexity
        if task.complexity_score >= 8:
            score += 10
            factors.append("High complexity task")
        
        # Factor 5: Current progress
        if task.progress == 0:
            score += 5
            factors.append("Not yet started")
        elif task.progress >= 80:
            score -= 15
            factors.append("Nearly complete")
        
        # Factor 6: Risk level
        if task.risk_level == 'critical':
            score += 35
            factors.append("High risk identified")
        elif task.risk_level == 'high':
            score += 15
            factors.append("Moderate-high risk")
        
        # Determine priority
        if score >= 60:
            priority = 'urgent'
        elif score >= 40:
            priority = 'high'
        elif score >= 20:
            priority = 'medium'
        else:
            priority = 'low'
        
        return {
            'suggested_priority': priority,
            'confidence': min(100, (abs(score) / 100) * 100),
            'score': score,
            'factors': factors,
            'recommendation': self._get_recommendation(priority, score, factors)
        }
    
    def _get_recommendation(self, priority, score, factors):
        """Generate natural language recommendation"""
        if priority == 'urgent':
            return "This task needs immediate attention due to multiple urgency factors."
        elif priority == 'high':
            return "Recommend prioritizing this task soon to prevent delays."
        elif priority == 'medium':
            return "Good task to work on when higher priorities are handled."
        else:
            return "This is a lower priority task; schedule when team has capacity."
```

#### API & UI (Week 1)
```python
# api/v1/views.py
@api_view(['POST'])
@permission_classes([IsAuthenticated])
def suggest_task_priority(request, task_id):
    """Get priority suggestion for a task"""
    from kanban.models import Task
    from kanban.utils.priority_service import PrioritySuggester
    
    task = get_object_or_404(Task, id=task_id)
    
    suggester = PrioritySuggester()
    suggestion = suggester.suggest_priority(task)
    
    return Response(suggestion)
```

---

## TIER 2: High Value, Quick Wins (2-3 weeks each)

### 4. Sentiment Analysis on Comments

```python
# ai_assistant/utils/sentiment_service.py
from django.utils import timezone
from datetime import timedelta

class CommentSentimentAnalyzer:
    
    def analyze_comment(self, comment):
        """Analyze sentiment of a single comment"""
        from ai_assistant.utils.ai_clients import GeminiClient
        
        gemini = GeminiClient()
        
        prompt = f"""
        Analyze the sentiment and emotional tone of this project management comment.
        
        Rate on scale:
        - Very Positive (5)
        - Positive (4)
        - Neutral (3)
        - Negative (2)
        - Very Negative (1)
        
        Also identify if the comment indicates:
        - Blockers/frustration
        - Progress/celebration
        - Risk/concern
        - Question/uncertainty
        
        Respond as JSON:
        {{
            "sentiment": 3,
            "sentiment_label": "neutral",
            "confidence": 0.85,
            "keywords": ["blocked", "urgent"],
            "concerns": ["technical blocker"],
            "tone": "professional but urgent"
        }}
        
        Comment: "{comment.content}"
        """
        
        import json
        response = gemini.get_response(prompt)
        
        try:
            analysis = json.loads(response)
        except:
            analysis = {'sentiment': 3, 'sentiment_label': 'neutral', 'confidence': 0.5}
        
        # Store analysis
        comment.sentiment_score = analysis.get('sentiment', 3)
        comment.sentiment_label = analysis.get('sentiment_label', 'neutral')
        comment.sentiment_confidence = analysis.get('confidence', 0.5)
        comment.save()
        
        return analysis
    
    def get_task_sentiment_trend(self, task):
        """Get sentiment trend over task comments"""
        from kanban.models import Comment
        
        comments = Comment.objects.filter(task=task).order_by('created_at')
        
        sentiments = []
        for comment in comments:
            if not hasattr(comment, 'sentiment_score'):
                self.analyze_comment(comment)
            sentiments.append({
                'date': comment.created_at,
                'score': comment.sentiment_score,
                'author': comment.created_by.username
            })
        
        if not sentiments:
            return None
        
        # Calculate trend
        recent = sentiments[-5:] if len(sentiments) >= 5 else sentiments
        recent_avg = sum(s['score'] for s in recent) / len(recent)
        overall_avg = sum(s['score'] for s in sentiments) / len(sentiments)
        
        trend = 'improving' if recent_avg > overall_avg else 'declining' if recent_avg < overall_avg else 'stable'
        
        return {
            'overall_sentiment': overall_avg,
            'recent_sentiment': recent_avg,
            'trend': trend,
            'comments_analyzed': len(sentiments),
            'sentiments': sentiments
        }
    
    def detect_concerns(self, task):
        """Detect if team has concerns/blockers"""
        from kanban.models import Comment
        import re
        
        comments = Comment.objects.filter(task=task)
        
        concern_keywords = [
            'blocked', 'stuck', 'can\'t', 'unable', 'issue', 'problem', 'error',
            'failed', 'crash', 'urgent', 'help', 'need assistance', 'unclear',
            'not working', 'complicated', 'confused', 'impossible'
        ]
        
        concerns = []
        
        for comment in comments:
            text = comment.content.lower()
            for keyword in concern_keywords:
                if keyword in text:
                    concerns.append({
                        'keyword': keyword,
                        'author': comment.created_by.username,
                        'date': comment.created_at,
                        'comment': comment.content[:100] + '...'
                    })
        
        return {
            'has_concerns': len(concerns) > 0,
            'concerns_count': len(concerns),
            'concerns': concerns,
            'risk_level': 'high' if len(concerns) >= 3 else 'medium' if len(concerns) >= 1 else 'low'
        }
```

**Dashboard Widget (Week 2):**
```html
<!-- templates/kanban/board_sentiment_dashboard.html -->
{% extends 'base.html' %}

{% block content %}
<div class="sentiment-dashboard">
    <h2>Team Sentiment & Concerns</h2>
    
    {% for task in critical_concern_tasks %}
    <div class="sentiment-card alert alert-warning">
        <div class="task-title">{{ task.title }}</div>
        <div class="sentiment-indicators">
            {% if task.sentiment_trend.trend == 'declining' %}
                🔴 Sentiment Declining ({{ task.sentiment_trend.recent_sentiment|floatformat:1 }}/5)
            {% elif task.sentiment_trend.trend == 'improving' %}
                🟢 Sentiment Improving ({{ task.sentiment_trend.recent_sentiment|floatformat:1 }}/5)
            {% else %}
                🟡 Stable Sentiment
            {% endif %}
        </div>
        
        {% if task.concerns %}
        <div class="concerns">
            <strong>Concerns detected:</strong>
            <ul>
            {% for concern in task.concerns %}
                <li>{{ concern.keyword }}: "{{ concern.comment }}"</li>
            {% endfor %}
            </ul>
        </div>
        {% endif %}
        
        <button class="btn btn-sm btn-primary" onclick="managerCheckIn({{ task.id }})">
            Check In with Team
        </button>
    </div>
    {% endfor %}
</div>
{% endblock %}
```

---

### 5. Critical Path Highlighting

```python
# kanban/utils/critical_path_service.py
from collections import defaultdict, deque

class CriticalPathAnalyzer:
    
    def find_critical_path(self, board):
        """Find critical path for entire board"""
        from kanban.models import Task
        
        tasks = Task.objects.filter(column__board=board)
        
        # Build dependency graph
        graph = defaultdict(list)
        in_degree = defaultdict(int)
        task_map = {}
        
        for task in tasks:
            task_map[task.id] = task
            for dep in task.dependencies.all():
                graph[dep.id].append(task.id)
                in_degree[task.id] += 1
        
        # Topological sort
        queue = deque([t.id for t in tasks if in_degree[t.id] == 0])
        topo_order = []
        
        while queue:
            task_id = queue.popleft()
            topo_order.append(task_id)
            
            for dependent_id in graph[task_id]:
                in_degree[dependent_id] -= 1
                if in_degree[dependent_id] == 0:
                    queue.append(dependent_id)
        
        # Calculate earliest start/finish
        earliest_start = {}
        earliest_finish = {}
        
        for task_id in topo_order:
            task = task_map[task_id]
            duration = max(1, task.duration_days())  # at least 1 day
            
            # Get max finish time of dependencies
            max_dep_finish = 0
            for dep in task.dependencies.all():
                max_dep_finish = max(max_dep_finish, earliest_finish.get(dep.id, 0))
            
            earliest_start[task_id] = max_dep_finish
            earliest_finish[task_id] = earliest_start[task_id] + duration
        
        # Calculate latest start/finish (backward pass)
        total_duration = max(earliest_finish.values()) if earliest_finish else 0
        
        latest_finish = {}
        latest_start = {}
        
        # Initialize end tasks
        for task_id in task_map:
            if not graph[task_id]:  # No dependents
                latest_finish[task_id] = total_duration
        
        # Process in reverse topological order
        for task_id in reversed(topo_order):
            task = task_map[task_id]
            duration = max(1, task.duration_days())
            
            if task_id not in latest_finish:
                # Has dependents
                min_dep_start = float('inf')
                for dependent_id in graph[task_id]:
                    min_dep_start = min(min_dep_start, latest_start.get(dependent_id, float('inf')))
                
                latest_finish[task_id] = min_dep_start if min_dep_start != float('inf') else total_duration
            
            latest_start[task_id] = latest_finish[task_id] - duration
        
        # Identify critical path (slack = 0)
        critical_tasks = []
        
        for task_id in task_map:
            slack = latest_start.get(task_id, 0) - earliest_start.get(task_id, 0)
            
            if slack == 0:
                critical_tasks.append({
                    'task_id': task_id,
                    'task': task_map[task_id],
                    'slack': slack,
                    'earliest_start': earliest_start.get(task_id, 0),
                    'earliest_finish': earliest_finish.get(task_id, 0),
                })
        
        return {
            'critical_path': critical_tasks,
            'total_duration': total_duration,
            'critical_count': len(critical_tasks),
            'total_tasks': len(task_map),
            'is_feasible': len(critical_tasks) > 0,
        }
    
    def identify_bottlenecks(self, board):
        """Find tasks that are blocking multiple others"""
        from kanban.models import Task
        
        tasks = Task.objects.filter(column__board=board)
        
        bottlenecks = []
        
        for task in tasks:
            dependent_count = task.dependent_tasks.count()
            
            if dependent_count >= 3:
                bottlenecks.append({
                    'task': task,
                    'dependent_count': dependent_count,
                    'dependents': list(task.dependent_tasks.values_list('title', flat=True)),
                    'impact_level': 'critical' if dependent_count >= 5 else 'high' if dependent_count >= 3 else 'medium',
                })
        
        return sorted(bottlenecks, key=lambda x: x['dependent_count'], reverse=True)
```

---

## TIER 3-4: Advanced Features (Implementation Details in Production Roadmap)

### Features 6-18 Quick Summary

| # | Feature | Effort | ROI | Implementation Notes |
|---|---------|--------|-----|----------------------|
| 6 | Resource Skill Matching | Medium | High | Use NLP to extract skills from descriptions, build team profiles |
| 7 | Sentiment Analysis | Low | Medium | Use Gemini API for analysis, store scores, dashboard alerts |
| 8 | Critical Path | Medium | High | Graph algorithms, topological sort, critical path method |
| 9 | Template Library | Medium | Medium | Cluster similar projects, generate templates with Gemini |
| 10 | Workload Prediction | Medium | High | Time series forecasting, Monte Carlo simulation |
| 11 | Auto Task Breakdown | Low-Medium | High | Expand existing feature, better decomposition logic |
| 12 | Burndown Prediction | Low-Medium | Medium | Linear/polynomial regression with confidence intervals |
| 13 | Scope Creep Detection | Low | Medium | Track metrics over time, anomaly detection |
| 14 | Retrospective Generator | Low | Low | Summarization after project completion |
| 15 | Slack Bot | Medium | High | Slack API, conversational Gemini, webhook integration |
| 16 | Budget/ROI Tracking | Medium | Medium | Time tracking integration, financial calculations |
| 17 | Conflict Detection | Medium | High | Constraint satisfaction, resource scheduling |
| 18 | PM Coach | Medium-High | Medium | Rule engine + Gemini, contextual advice |

---

## Database Schema Changes Summary

```sql
-- Add to Task model
- sentiment_score (Integer, 1-5)
- sentiment_label (String)
- sentiment_confidence (Float)
- predicted_completion_date (DateTime)
- prediction_confidence (Float)
- skill_gap_analysis (JSONField)

-- New models
- TaskPrediction
- MeetingTranscript
- TaskSentimentHistory
- ResourceSkillMatch
- ProjectTemplate
- BudgetAllocation

-- Extend Comment model
- sentiment_score (Integer)
- sentiment_label (String)
- sentiment_confidence (Float)
```

---

## API Endpoints to Add

```
POST   /api/v1/tasks/{id}/predict-completion/
GET    /api/v1/boards/{id}/critical-path/
POST   /api/v1/meetings/upload/
GET    /api/v1/tasks/{id}/sentiment-trend/
POST   /api/v1/tasks/{id}/suggest-priority/
POST   /api/v1/tasks/{id}/suggest-team-member/
GET    /api/v1/boards/{id}/bottlenecks/
POST   /api/v1/projects/{id}/generate-template/
```

---

## Frontend Components to Add

1. **Prediction Card** - Show in task detail
2. **Sentiment Dashboard** - Board-level concerns view
3. **Critical Path Visualization** - Interactive diagram
4. **Meeting Upload** - Form + processing status
5. **Priority Suggestion Widget** - In task creation
6. **Skill Match Modal** - Show in task assignment

---

## Deployment Considerations

- **ML Model Storage**: Consider saving trained models for persistence
- **Async Processing**: Use Celery for transcription, heavy analysis
- **Caching**: Cache prediction models, sentiment scores
- **Rate Limiting**: Gemini API calls ~$0.075/1M input tokens; cache heavily
- **Data Privacy**: Meeting transcripts contain sensitive info; secure storage

---

## Success Metrics

Track improvements with:
- **Adoption Rate**: % of tasks using new AI features
- **User Satisfaction**: Feature usage and feedback scores
- **Business Impact**:
  - Projects completed on-time (should improve 15-30%)
  - Team velocity (should increase 10-20%)
  - Manager time saved (should save 3-5 hours/week)
  - Risk incidents prevented (track vs. baseline)

---

**Total Implementation Timeline: 4-6 months**
- Months 1-2: Tier 1 & 2 features (high impact)
- Months 3-4: Tier 3 features (differentiation)
- Months 5-6: Polish, mobile app, integrations

**Recommended Team:** 2-3 Python/ML developers + 1 frontend dev

