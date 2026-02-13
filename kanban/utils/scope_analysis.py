"""
Scope Analysis Utilities
AI-powered scope creep detection and analysis
"""

from django.utils import timezone
from django.db.models import Q, Sum
import google.generativeai as genai
from django.conf import settings


def analyze_scope_changes_with_ai(snapshot, baseline_snapshot):
    """
    Use AI to analyze scope changes and provide recommendations
    
    Args:
        snapshot: Current ScopeChangeSnapshot instance
        baseline_snapshot: Baseline ScopeChangeSnapshot instance
    
    Returns:
        dict: AI analysis with recommendations
    """
    if not baseline_snapshot:
        return {
            'summary': 'No baseline available for comparison',
            'recommendations': [],
            'risk_level': 'unknown'
        }
    
    # Calculate changes
    task_change = snapshot.total_tasks - baseline_snapshot.total_tasks
    complexity_change = snapshot.total_complexity_points - baseline_snapshot.total_complexity_points
    
    if baseline_snapshot.total_tasks > 0:
        scope_pct = round((task_change / baseline_snapshot.total_tasks) * 100, 2)
    else:
        scope_pct = 0
    
    if baseline_snapshot.total_complexity_points > 0:
        complexity_pct = round((complexity_change / baseline_snapshot.total_complexity_points) * 100, 2)
    else:
        complexity_pct = 0
    
    # Get task details for AI analysis
    from kanban.models import Task
    board = snapshot.board
    
    # Get recently added tasks (since baseline)
    recent_tasks = Task.objects.filter(
        column__board=board,
        created_at__gte=baseline_snapshot.snapshot_date
    ).values('title', 'priority', 'complexity_score', 'description')[:20]
    
    recent_tasks_summary = "\n".join([
        f"- {task['title']} (Priority: {task['priority']}, Complexity: {task.get('complexity_score', 'N/A')})"
        for task in recent_tasks
    ])
    
    # Build AI prompt
    prompt = f"""You are a project management AI assistant analyzing scope changes.

**Baseline (Project Start):**
- Total Tasks: {baseline_snapshot.total_tasks}
- Total Complexity: {baseline_snapshot.total_complexity_points}
- Date: {baseline_snapshot.snapshot_date.strftime('%Y-%m-%d')}

**Current Status:**
- Total Tasks: {snapshot.total_tasks}
- Total Complexity: {snapshot.total_complexity_points}
- Date: {snapshot.snapshot_date.strftime('%Y-%m-%d')}

**Changes:**
- Tasks Added: {task_change} ({scope_pct:+.1f}%)
- Complexity Added: {complexity_change} ({complexity_pct:+.1f}%)

**Recently Added Tasks:**
{recent_tasks_summary if recent_tasks_summary else 'No recent tasks'}

**Your Task:**
Analyze these scope changes and provide:
1. A brief summary (2-3 sentences) of the scope change impact
2. Risk level assessment (low/medium/high/critical)
3. Estimated timeline impact in days (be realistic)
4. 3-5 specific, actionable recommendations to manage this scope change

Format your response as JSON:
{{
    "summary": "Brief analysis of the scope changes...",
    "risk_level": "medium",
    "estimated_delay_days": 5,
    "recommendations": [
        "Specific recommendation 1",
        "Specific recommendation 2",
        "Specific recommendation 3"
    ],
    "key_concerns": [
        "Concern 1",
        "Concern 2"
    ]
}}
"""
    
    try:
        # Configure Gemini
        genai.configure(api_key=settings.GEMINI_API_KEY)
        model = genai.GenerativeModel('gemini-2.5-flash')
        
        # Generation config for scope analysis
        generation_config = {
            'temperature': 0.4,  # Analytical task
            'top_p': 0.8,
            'top_k': 40,
            'max_output_tokens': 2048,  # Adequate for scope analysis JSON
        }
        
        # Generate analysis
        response = model.generate_content(prompt, generation_config=generation_config)
        
        # Parse response
        import json
        response_text = response.text.strip()
        
        # Remove markdown code blocks if present
        if response_text.startswith('```json'):
            response_text = response_text.replace('```json', '').replace('```', '').strip()
        elif response_text.startswith('```'):
            response_text = response_text.replace('```', '').strip()
        
        analysis = json.loads(response_text)
        
        # Add calculated metrics
        analysis['scope_change_percentage'] = scope_pct
        analysis['complexity_change_percentage'] = complexity_pct
        analysis['tasks_added'] = task_change
        
        return analysis
        
    except Exception as e:
        # Fallback to rule-based analysis
        return generate_rule_based_analysis(scope_pct, complexity_pct, task_change, complexity_change)


def generate_rule_based_analysis(scope_pct, complexity_pct, task_change, complexity_change):
    """
    Fallback rule-based analysis when AI is unavailable
    """
    # Determine risk level
    if abs(scope_pct) >= 40 or abs(complexity_pct) >= 50:
        risk_level = 'critical'
        estimated_delay = max(10, int(abs(scope_pct) / 3))
    elif abs(scope_pct) >= 25 or abs(complexity_pct) >= 30:
        risk_level = 'high'
        estimated_delay = max(5, int(abs(scope_pct) / 4))
    elif abs(scope_pct) >= 15 or abs(complexity_pct) >= 20:
        risk_level = 'medium'
        estimated_delay = max(3, int(abs(scope_pct) / 5))
    else:
        risk_level = 'low'
        estimated_delay = 1
    
    # Generate summary
    if scope_pct > 0:
        summary = f"Scope has increased by {scope_pct:.1f}% ({task_change} tasks added). "
    else:
        summary = f"Scope has decreased by {abs(scope_pct):.1f}% ({abs(task_change)} tasks removed). "
    
    if complexity_pct > 0:
        summary += f"Overall complexity increased by {complexity_pct:.1f}%. "
    
    summary += f"This represents a {risk_level} risk to the project timeline."
    
    # Generate recommendations
    recommendations = []
    
    if scope_pct > 30:
        recommendations.extend([
            "Review project priorities and consider removing low-value tasks",
            "Negotiate timeline extension with stakeholders",
            "Add resources to the team to handle increased workload",
            "Break large tasks into smaller, manageable pieces"
        ])
    elif scope_pct > 15:
        recommendations.extend([
            "Review recent task additions and validate their necessity",
            "Consider deferring non-critical tasks to future iterations",
            "Optimize team workload distribution",
            "Communicate timeline risks to stakeholders"
        ])
    elif scope_pct > 5:
        recommendations.extend([
            "Monitor scope changes closely over the next week",
            "Document reasons for scope additions",
            "Review task priorities to ensure focus on critical work"
        ])
    else:
        recommendations.extend([
            "Continue current practices - scope is well controlled",
            "Maintain regular scope reviews"
        ])
    
    key_concerns = []
    if scope_pct > 25:
        key_concerns.append(f"Large scope increase may delay project by ~{estimated_delay} days")
    if complexity_pct > 30:
        key_concerns.append("Increased complexity may impact task completion velocity")
    if task_change > 20:
        key_concerns.append(f"{task_change} new tasks added - ensure team capacity can handle load")
    
    return {
        'summary': summary,
        'risk_level': risk_level,
        'estimated_delay_days': estimated_delay,
        'recommendations': recommendations[:5],  # Limit to 5
        'key_concerns': key_concerns,
        'scope_change_percentage': scope_pct,
        'complexity_change_percentage': complexity_pct,
        'tasks_added': task_change,
        'analysis_type': 'rule_based'  # Indicate this is fallback
    }


def create_scope_alert_if_needed(snapshot):
    """
    Create a ScopeCreepAlert if thresholds are exceeded
    
    Args:
        snapshot: ScopeChangeSnapshot instance
    
    Returns:
        ScopeCreepAlert instance or None
    """
    if not snapshot.baseline_snapshot:
        return None
    
    if not snapshot.scope_change_percentage:
        snapshot.calculate_changes_from_baseline()
        snapshot.save()
    
    scope_pct = abs(snapshot.scope_change_percentage or 0)
    complexity_pct = abs(snapshot.complexity_change_percentage or 0)
    
    # Determine if alert is needed and severity
    severity = None
    if scope_pct >= 30 or complexity_pct >= 40:
        severity = 'critical'
    elif scope_pct >= 15 or complexity_pct >= 25:
        severity = 'warning'
    elif scope_pct >= 5 or complexity_pct >= 10:
        severity = 'info'
    
    if not severity:
        return None
    
    # Check if there's already an active alert for this board
    from kanban.models import ScopeCreepAlert
    existing_alert = ScopeCreepAlert.objects.filter(
        board=snapshot.board,
        status__in=['active', 'acknowledged']
    ).order_by('-detected_at').first()
    
    # Only create new alert if scope has increased since last alert
    if existing_alert and existing_alert.scope_increase_percentage >= snapshot.scope_change_percentage:
        return None
    
    # Get or generate AI analysis
    if not snapshot.ai_analysis:
        ai_analysis = analyze_scope_changes_with_ai(snapshot, snapshot.baseline_snapshot)
        snapshot.ai_analysis = ai_analysis
        snapshot.predicted_delay_days = ai_analysis.get('estimated_delay_days')
        snapshot.save()
    else:
        ai_analysis = snapshot.ai_analysis
    
    # Create alert
    alert = ScopeCreepAlert.objects.create(
        board=snapshot.board,
        snapshot=snapshot,
        severity=severity,
        scope_increase_percentage=snapshot.scope_change_percentage,
        complexity_increase_percentage=snapshot.complexity_change_percentage or 0,
        tasks_added=snapshot.total_tasks - snapshot.baseline_snapshot.total_tasks,
        predicted_delay_days=ai_analysis.get('estimated_delay_days'),
        timeline_at_risk=(severity in ['warning', 'critical']),
        recommendations=ai_analysis.get('recommendations', []),
        ai_summary=ai_analysis.get('summary', '')
    )
    
    return alert


def get_scope_trend_data(board, days=30):
    """
    Get scope trend data for visualization
    
    Args:
        board: Board instance
        days: Number of days to look back
    
    Returns:
        list: Trend data points
    """
    from datetime import timedelta
    from kanban.models import ScopeChangeSnapshot
    
    cutoff_date = timezone.now() - timedelta(days=days)
    snapshots = ScopeChangeSnapshot.objects.filter(
        board=board,
        snapshot_date__gte=cutoff_date
    ).order_by('snapshot_date')
    
    trend_data = []
    for snapshot in snapshots:
        trend_data.append({
            'date': snapshot.snapshot_date.strftime('%Y-%m-%d'),
            'total_tasks': snapshot.total_tasks,
            'complexity': snapshot.total_complexity_points,
            'scope_change_pct': snapshot.scope_change_percentage,
            'is_baseline': snapshot.is_baseline
        })
    
    return trend_data


def calculate_scope_velocity(board, weeks=4):
    """
    Calculate the rate of scope change over time
    
    Args:
        board: Board instance
        weeks: Number of weeks to analyze
    
    Returns:
        dict: Velocity metrics
    """
    from datetime import timedelta
    from kanban.models import ScopeChangeSnapshot
    
    cutoff_date = timezone.now() - timedelta(weeks=weeks)
    snapshots = ScopeChangeSnapshot.objects.filter(
        board=board,
        snapshot_date__gte=cutoff_date
    ).order_by('snapshot_date')
    
    if snapshots.count() < 2:
        return {
            'avg_tasks_added_per_week': 0,
            'avg_complexity_added_per_week': 0,
            'trend': 'insufficient_data'
        }
    
    first = snapshots.first()
    last = snapshots.last()
    
    time_diff = (last.snapshot_date - first.snapshot_date).days
    weeks_elapsed = max(time_diff / 7, 1)
    
    tasks_diff = last.total_tasks - first.total_tasks
    complexity_diff = last.total_complexity_points - first.total_complexity_points
    
    avg_tasks_per_week = tasks_diff / weeks_elapsed
    avg_complexity_per_week = complexity_diff / weeks_elapsed
    
    # Determine trend
    if avg_tasks_per_week > 5:
        trend = 'rapidly_increasing'
    elif avg_tasks_per_week > 2:
        trend = 'increasing'
    elif avg_tasks_per_week > -2:
        trend = 'stable'
    else:
        trend = 'decreasing'
    
    return {
        'avg_tasks_added_per_week': round(avg_tasks_per_week, 2),
        'avg_complexity_added_per_week': round(avg_complexity_per_week, 2),
        'trend': trend,
        'weeks_analyzed': round(weeks_elapsed, 1),
        'total_change': {
            'tasks': tasks_diff,
            'complexity': complexity_diff
        }
    }
