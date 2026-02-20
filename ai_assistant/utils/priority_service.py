"""
Priority Suggestion Service
AI-powered task priority classification with explainability
"""
import logging
import pickle
from datetime import datetime
from django.utils import timezone
from django.db.models import Count, Q

try:
    import numpy as np
    NUMPY_AVAILABLE = True
except ImportError:
    NUMPY_AVAILABLE = False
    np = None

logger = logging.getLogger(__name__)


class PrioritySuggestionService:
    """
    Service for suggesting task priorities using machine learning
    Provides explainable predictions based on historical team decisions
    """
    
    PRIORITY_WEIGHTS = {
        'low': 1,
        'medium': 2,
        'high': 3,
        'urgent': 4
    }
    
    FEATURE_NAMES = [
        'days_until_due',
        'is_overdue',
        'complexity_score',
        'blocking_count',
        'blocked_by_count',
        'assignee_workload',
        'team_tasks_per_member',
        'has_description',
        'description_length',
        'collaboration_required',
        'risk_score',
        'has_subtasks',
        'is_subtask',
        'label_count'
    ]
    
    def __init__(self):
        self.model = None
        self.feature_importance = {}
    
    def suggest_priority(self, task, user=None):
        """
        Suggest priority for a task with reasoning
        
        Args:
            task: Task object (can be unsaved)
            user: User requesting suggestion (optional)
        
        Returns:
            dict: {
                'suggested_priority': 'high',
                'confidence': 0.85,
                'reasoning': {
                    'top_factors': [...],
                    'explanation': '...'
                },
                'alternatives': [...]
            }
        """
        from kanban.priority_models import PriorityModel
        
        # Get board (handle unsaved tasks)
        board = None
        if task.pk and task.column:
            board = task.column.board
        elif hasattr(task, '_board'):
            board = task._board
        
        if not board:
            logger.warning("No board found for task, using rule-based fallback")
            return self._rule_based_suggestion(task)
        
        # Try to get trained model
        model_obj = PriorityModel.get_active_model(board)
        
        if not model_obj:
            logger.info(f"No trained model for board {board.id}, using rule-based approach")
            return self._rule_based_suggestion(task)
        
        # Load model
        try:
            self.model = pickle.loads(model_obj.model_file)
            self.feature_importance = model_obj.feature_importance
        except Exception as e:
            logger.error(f"Error loading model: {e}")
            return self._rule_based_suggestion(task)
        
        # Extract features
        features = self._extract_features(task)
        
        # Make prediction
        try:
            prediction_proba = self.model.predict_proba([features])[0]
            predicted_class = self.model.predict([features])[0]
            
            # Get class labels
            classes = self.model.classes_
            
            # Map prediction to priority
            suggested_priority = classes[predicted_class]
            confidence = prediction_proba[predicted_class]
            
            # Get alternative priorities
            alternatives = []
            for i, cls in enumerate(classes):
                if cls != suggested_priority:
                    alternatives.append({
                        'priority': cls,
                        'confidence': float(prediction_proba[i])
                    })
            
            # Sort alternatives by confidence
            alternatives.sort(key=lambda x: x['confidence'], reverse=True)
            
            # Generate reasoning
            reasoning = self._generate_reasoning(features, suggested_priority, confidence, task)
            
            # Log suggestion
            self._log_suggestion(task, model_obj, suggested_priority, confidence, reasoning, features, user)
            
            return {
                'suggested_priority': suggested_priority,
                'confidence': float(confidence),
                'reasoning': reasoning,
                'alternatives': alternatives[:2],  # Top 2 alternatives
                'model_version': model_obj.model_version,
                'is_ml_based': True
            }
        
        except Exception as e:
            logger.error(f"Error making prediction: {e}")
            return self._rule_based_suggestion(task)
    
    def _extract_features(self, task):
        """
        Extract features from task for ML model
        
        Returns:
            list: Feature values in correct order
        """
        from kanban.models import Task
        
        # Calculate days until due
        days_until_due = 999  # Default for no due date
        is_overdue = False
        if task.due_date:
            # Make sure due_date is timezone-aware
            due_date = task.due_date
            if timezone.is_naive(due_date):
                due_date = timezone.make_aware(due_date)
            
            delta = due_date - timezone.now()
            days_until_due = delta.total_seconds() / 86400
            is_overdue = days_until_due < 0
            
            # If there is a future start date, urgency is determined by the work
            # window (start → due) rather than (today → due).  A task starting
            # in 7 days with a 2-day window is more urgent than plain "due in 9
            # days" suggests.
            start_date = getattr(task, 'start_date', None)
            if start_date and not is_overdue:
                sd = start_date
                # Normalise to datetime
                if not hasattr(sd, 'hour'):
                    from datetime import datetime
                    sd = datetime.combine(sd, datetime.min.time())
                if timezone.is_naive(sd):
                    sd = timezone.make_aware(sd)
                if sd > timezone.now():
                    work_window = (due_date - sd).total_seconds() / 86400
                    if work_window > 0:
                        days_until_due = work_window
        
        # Count dependencies
        blocking_count = 0
        blocked_by_count = 0
        if task.pk:
            blocking_count = task.dependencies.count()
            blocked_by_count = task.dependent_tasks.count()
        
        # Get assignee workload
        assignee_workload = 0
        if task.assigned_to:
            assignee_workload = Task.objects.filter(
                assigned_to=task.assigned_to,
                progress__lt=100
            ).exclude(
                column__name__icontains='done'
            ).count()
        
        # Get team capacity
        team_tasks_per_member = 0
        board = None
        
        # Safely get board
        if task.pk:
            try:
                if task.column:
                    board = task.column.board
            except:
                pass
        
        if not board and hasattr(task, '_board'):
            board = task._board
        
        if board:
            team_size = board.members.count()
            if team_size > 0:
                total_open_tasks = Task.objects.filter(
                    column__board=board,
                    progress__lt=100
                ).exclude(
                    column__name__icontains='done'
                ).count()
                team_tasks_per_member = total_open_tasks / team_size
        
        # Risk score
        risk_score = task.risk_score or 0
        
        # Subtasks
        has_subtasks = False
        is_subtask = task.parent_task is not None
        if task.pk:
            has_subtasks = task.subtasks.exists()
        
        # Labels
        label_count = 0
        if task.pk:
            label_count = task.labels.count()
        
        # Build feature vector
        features = [
            days_until_due,
            1 if is_overdue else 0,
            task.complexity_score,
            blocking_count,
            blocked_by_count,
            assignee_workload,
            team_tasks_per_member,
            1 if task.description else 0,
            len(task.description or ''),
            1 if task.collaboration_required else 0,
            risk_score,
            1 if has_subtasks else 0,
            1 if is_subtask else 0,
            label_count
        ]
        
        return features
    
    def _generate_reasoning(self, features, priority, confidence, task):
        """
        Generate human-readable reasoning for the suggestion
        
        Returns:
            dict: Reasoning with top factors and explanation
        """
        # Map features to names
        feature_dict = dict(zip(self.FEATURE_NAMES, features))
        
        # Get top influential features based on feature importance
        top_factors = []
        
        if self.feature_importance:
            # Sort features by importance
            sorted_features = sorted(
                self.feature_importance.items(),
                key=lambda x: x[1],
                reverse=True
            )[:5]
            
            for feature_name, importance in sorted_features:
                if feature_name in feature_dict:
                    value = feature_dict[feature_name]
                    factor_desc = self._describe_feature(feature_name, value, task)
                    if factor_desc:
                        top_factors.append({
                            'factor': feature_name,
                            'value': value,
                            'importance': float(importance),
                            'description': factor_desc
                        })
        
        # Generate natural language explanation
        explanation = self._build_explanation(priority, confidence, top_factors, task)
        
        return {
            'top_factors': top_factors,
            'explanation': explanation,
            'confidence_level': self._confidence_label(confidence)
        }
    
    def _describe_feature(self, feature_name, value, task):
        """Convert feature to human-readable description"""
        # Build a context-aware due date label.  When days_until_due was
        # already adjusted to the work window (future start date), show it as
        # such so the user isn't confused by "Due in 2 days" on a task whose
        # calendar due date is 9 days out.
        due_label = "No due date set"
        if feature_name == 'days_until_due' and value < 999:
            start_date_attr = getattr(task, 'start_date', None)
            if start_date_attr and task.due_date:
                from django.utils import timezone as _tz
                sd = start_date_attr
                if not hasattr(sd, 'hour'):
                    from datetime import datetime
                    sd = datetime.combine(sd, datetime.min.time())
                if _tz.is_naive(sd):
                    sd = _tz.make_aware(sd)
                if sd > _tz.now():
                    due_date = task.due_date
                    if _tz.is_naive(due_date):
                        due_date = _tz.make_aware(due_date)
                    days_from_today = (due_date - _tz.now()).total_seconds() / 86400
                    due_label = f"{abs(int(value))}-day work window (due in {int(days_from_today)} days)"
                else:
                    due_label = f"Due in {abs(int(value))} days"
            else:
                due_label = f"Due in {abs(int(value))} days"
        descriptions = {
            'days_until_due': due_label,
            'is_overdue': "Task is overdue!" if value else None,
            'complexity_score': f"Complexity: {int(value)}/10",
            'blocking_count': f"Blocks {int(value)} other tasks" if value > 0 else None,
            'blocked_by_count': f"Blocked by {int(value)} tasks" if value > 0 else None,
            'assignee_workload': f"Assignee has {int(value)} open tasks" if value > 0 else None,
            'team_tasks_per_member': f"Team average: {value:.1f} tasks/member" if value > 0 else None,
            'has_description': "Has detailed description" if value else None,
            'description_length': f"Description: {int(value)} characters" if value > 50 else None,
            'collaboration_required': "Requires team collaboration" if value else None,
            'risk_score': f"Risk score: {int(value)}" if value > 0 else None,
            'has_subtasks': f"Has {task.subtasks.count() if task.pk else 0} subtasks" if value else None,
            'is_subtask': "Is a subtask" if value else None,
            'label_count': f"{int(value)} labels" if value > 0 else None,
        }
        
        return descriptions.get(feature_name)
    
    def _build_explanation(self, priority, confidence, top_factors, task):
        """Build natural language explanation"""
        priority_reasons = {
            'urgent': "immediate attention required",
            'high': "important and time-sensitive",
            'medium': "standard priority",
            'low': "can be scheduled flexibly"
        }
        
        reason = priority_reasons.get(priority, "recommended")
        
        explanation = f"This task should be **{priority}** priority ({reason}). "
        
        # Add top reason
        if top_factors:
            main_factor = top_factors[0]
            explanation += f"Key factor: {main_factor['description']}. "
        
        # Add secondary reasons
        if len(top_factors) > 1:
            other_reasons = [f['description'] for f in top_factors[1:3] if f['description']]
            if other_reasons:
                explanation += f"Also considering: {', '.join(other_reasons)}."
        
        return explanation
    
    def _confidence_label(self, confidence):
        """Convert confidence score to label"""
        if confidence >= 0.8:
            return "High confidence"
        elif confidence >= 0.6:
            return "Moderate confidence"
        else:
            return "Low confidence"
    
    def _rule_based_suggestion(self, task):
        """
        Fallback rule-based priority suggestion when no ML model available
        
        Uses heuristics based on due date, dependencies, complexity, semantic keywords,
        and advanced fields (risk assessment, workload impact, complexity analysis, etc.)
        """
        score = 0
        max_score = 25  # Updated to reflect extended scoring: due-date tiers, duration, complexity tiers
        factors = []
        no_due_date = True  # Track whether a due date was provided
        
        # Semantic keyword analysis (0-4 points) - Check FIRST before due date
        high_impact_keywords = {
            'critical': 4, 'urgent': 4, 'emergency': 4, 'security': 4, 'breach': 4,
            'migration': 3, 'database': 3, 'deployment': 3, 'production': 3, 'outage': 3,
            'payment': 3, 'compliance': 3, 'audit': 3, 'legal': 3, 'data loss': 4,
            'bug': 2, 'performance': 2, 'optimization': 2, 'refactor': 1, 'integration': 2,
            'api': 2, 'authentication': 3, 'authorization': 3, 'backup': 3
        }
        
        text_to_analyze = f"{task.title} {task.description or ''}".lower()
        
        # Also analyze risk indicators, mitigation strategies, and complexity risks if available
        if hasattr(task, '_advanced_context'):
            text_to_analyze += f" {task._advanced_context.get('risk_indicators_text', '')}".lower()
            text_to_analyze += f" {task._advanced_context.get('mitigation_strategies_text', '')}".lower()
            text_to_analyze += f" {task._advanced_context.get('complexity_risks_text', '')}".lower()
        
        keyword_score = 0
        keyword_matches = []
        
        for keyword, weight in high_impact_keywords.items():
            if keyword in text_to_analyze:
                keyword_score = max(keyword_score, weight)  # Take highest match
                keyword_matches.append(keyword.title())
        
        if keyword_score > 0:
            score += keyword_score
            if keyword_matches:
                factors.append(f"High-impact keywords detected: {', '.join(keyword_matches[:3])}")
        
        # Due date urgency (0-5 points, with -1 penalty for far-future dates)
        days_until_due = None
        if task.due_date:
            no_due_date = False
            due_date = task.due_date
            if timezone.is_naive(due_date):
                due_date = timezone.make_aware(due_date)
            delta = due_date - timezone.now()
            days_from_today = delta.total_seconds() / 86400
            days_until_due = days_from_today

            # When there is a **future** start date, urgency is driven by the
            # available work window (start → due), not (today → due).  A task
            # that starts in 7 days and is due 2 days later is far more urgent
            # than "due in 9 days" implies.
            work_window_days = None
            start_date_attr = getattr(task, 'start_date', None)
            if start_date_attr and days_from_today > 0:
                sd = start_date_attr
                if not hasattr(sd, 'hour'):
                    from datetime import datetime
                    sd = datetime.combine(sd, datetime.min.time())
                if timezone.is_naive(sd):
                    sd = timezone.make_aware(sd)
                if sd > timezone.now():
                    ww = (due_date - sd).total_seconds() / 86400
                    if ww > 0:
                        work_window_days = ww
                        days_until_due = ww  # use work window for urgency scoring

            def _due_label(d_today, ww):
                """Human-readable due-date factor text."""
                if ww is not None:
                    return f"{int(ww)}-day work window (due in {int(d_today)} days)"
                return f"Due in {int(d_today)} days"

            if days_until_due < 0:
                score += 5
                factors.append("Task is overdue")
            elif days_until_due < 1:
                score += 4
                factors.append("Due within 24 hours" if work_window_days is None else _due_label(days_from_today, work_window_days))
            elif days_until_due < 3:
                score += 3
                factors.append("Due within 3 days" if work_window_days is None else _due_label(days_from_today, work_window_days))
            elif days_until_due < 7:
                score += 2
                factors.append("Due within 7 days" if work_window_days is None else _due_label(days_from_today, work_window_days))
            elif days_until_due < 14:
                score += 1
                factors.append(_due_label(days_from_today, work_window_days))
            elif days_until_due < 60:
                # Neutral — upcoming but not imminent
                factors.append(_due_label(days_from_today, work_window_days))
            else:
                # Long-term deadline reduces urgency
                score -= 1
                label = _due_label(days_from_today, work_window_days)
                factors.append(f"{label} (long-term deadline)")
        else:
            # No due date: urgency cannot be determined
            factors.append("No due date set — urgency cannot be assessed")

        # === TASK DURATION FACTOR (-0 to -2 points) ===
        # A very long project span signals low short-term urgency regardless of complexity
        start_date = getattr(task, 'start_date', None)
        if start_date and task.due_date:
            sd = start_date
            ed = task.due_date
            if timezone.is_naive(sd):
                sd = timezone.make_aware(sd)
            if timezone.is_naive(ed):
                ed = timezone.make_aware(ed)
            duration_days = (ed - sd).total_seconds() / 86400
            if duration_days > 180:
                score -= 2
                factors.append(f"Long-term project span ({int(duration_days)} days — low short-term urgency)")
            elif duration_days > 90:
                score -= 1
                factors.append(f"Extended project timeline ({int(duration_days)} days)")
        
        # Blocking tasks (0-3 points) - Check both saved tasks and advanced context
        blocking_count = 0
        if task.pk:
            blocking_count = task.dependencies.count()
        elif hasattr(task, '_advanced_context'):
            blocking_count = task._advanced_context.get('dependencies_count', 0)
        
        if blocking_count >= 3:
            score += 3
            factors.append(f"Blocks {blocking_count} tasks")
        elif blocking_count >= 1:
            score += 2
            factors.append(f"Blocks {blocking_count} tasks")
        
        # Complexity (0-3 points) - Use AI-analyzed complexity if available
        complexity = task.complexity_score
        ai_complexity = None
        
        # Check for AI complexity analysis results
        if hasattr(task, '_advanced_context'):
            ai_complexity = task._advanced_context.get('ai_complexity_score')
            is_breakdown_recommended = task._advanced_context.get('is_breakdown_recommended', False)
            subtasks_count = task._advanced_context.get('suggested_subtasks_count', 0)
            complexity_risk_count = task._advanced_context.get('complexity_risk_count', 0)
        else:
            is_breakdown_recommended = False
            subtasks_count = 0
            complexity_risk_count = 0
        
        # Use AI complexity if available (more accurate), otherwise use manual slider
        effective_complexity = ai_complexity if ai_complexity is not None else complexity
        if isinstance(effective_complexity, str):
            try:
                effective_complexity = int(effective_complexity)
            except (ValueError, TypeError):
                effective_complexity = 5
        
        # Score based on complexity (more granular tiers)
        complexity_source = "AI-analyzed" if ai_complexity else "Manual"
        if effective_complexity >= 9:
            score += 3
            factors.append(f"Very high complexity ({effective_complexity}/10, {complexity_source})")
        elif effective_complexity >= 7:
            score += 2
            factors.append(f"High complexity ({effective_complexity}/10, {complexity_source})")
        elif effective_complexity >= 5:
            score += 1
            factors.append(f"Medium complexity ({effective_complexity}/10)")
        
        # Additional points for breakdown recommendation (indicates very complex task)
        if is_breakdown_recommended:
            score += 1
            factors.append(f"AI recommends breaking into {subtasks_count} subtasks")
        
        # Additional consideration for complexity-related risks
        if complexity_risk_count >= 2:
            score += 1
            factors.append(f"Multiple complexity risks identified ({complexity_risk_count})")
        
        # === ADVANCED RISK ASSESSMENT (0-4 points) ===
        # Check risk_likelihood and risk_impact first (more granular)
        risk_likelihood = getattr(task, 'risk_likelihood', None)
        risk_impact = getattr(task, 'risk_impact', None)
        risk_level = getattr(task, 'risk_level', None)
        
        if risk_likelihood and risk_impact:
            # Calculate combined risk (likelihood × impact gives 1-9)
            combined_risk = risk_likelihood * risk_impact
            if combined_risk >= 6:  # High (6-9)
                score += 3
                factors.append(f"High risk assessment (likelihood × impact = {combined_risk})")
            elif combined_risk >= 4:  # Medium (4-5)
                score += 2
                factors.append(f"Medium risk assessment (score: {combined_risk})")
            elif combined_risk >= 2:  # Low-Medium (2-3)
                score += 1
                factors.append(f"Low-medium risk (score: {combined_risk})")
        elif risk_level:
            # Fallback to risk_level if likelihood/impact not set
            risk_level_scores = {'critical': 4, 'high': 3, 'medium': 2, 'low': 1}
            risk_level_score = risk_level_scores.get(risk_level.lower(), 0)
            if risk_level_score >= 3:
                score += risk_level_score
                factors.append(f"Risk level: {risk_level.title()}")
            elif risk_level_score >= 1:
                score += risk_level_score
                factors.append(f"Risk level: {risk_level.title()}")
        else:
            # Original risk_score fallback (0-2 points)
            risk = task.risk_score
            if risk:
                if isinstance(risk, str):
                    try:
                        risk = int(risk)
                    except (ValueError, TypeError):
                        risk = 0
                
                if risk >= 7:
                    score += 2
                    factors.append("High risk score")
                elif risk >= 4:
                    score += 1
                    factors.append("Medium risk score")
        
        # === WORKLOAD IMPACT (0-2 points) ===
        workload_impact = getattr(task, 'workload_impact', None)
        if workload_impact:
            workload_scores = {'critical': 2, 'high': 2, 'medium': 1, 'low': 0}
            workload_score = workload_scores.get(workload_impact.lower(), 0)
            if workload_score > 0:
                score += workload_score
                factors.append(f"Workload impact: {workload_impact.title()}")
        
        # Collaboration (0-1 point)
        if task.collaboration_required:
            score += 1
            factors.append("Requires collaboration")
        
        # === SUBTASK/HIERARCHY CONTEXT (0-1 point) ===
        is_subtask = False
        if hasattr(task, '_advanced_context'):
            is_subtask = task._advanced_context.get('has_parent_task', False)
        elif task.parent_task:
            is_subtask = True
        
        if is_subtask:
            # Subtasks might inherit urgency but are generally more focused
            factors.append("Part of larger task (subtask)")
        
        # Determine priority based on recalibrated thresholds (max_score = 25)
        # Proportional bands: low <5 (0-20%), medium 5-8 (20-36%), high 9-14 (36-56%), urgent >=15 (60%+)
        if score >= 15:
            priority = 'urgent'
            confidence = 0.82
        elif score >= 9:
            priority = 'high'
            confidence = 0.77
        elif score >= 5:
            priority = 'medium'
            confidence = 0.72
        else:
            priority = 'low'
            confidence = 0.67

        # Cap at 'high' and reduce confidence when no due date is provided
        # (cannot reliably determine urgency without a deadline)
        if no_due_date:
            confidence = max(0.45, confidence - 0.10)
            if priority == 'urgent':
                priority = 'high'
        
        # Build detailed explanation
        explanation = f"Based on rule-based analysis (score: {score}/{max_score}), this task should be **{priority}** priority. "

        # Add no-due-date warning prominently
        if no_due_date:
            explanation += "⚠️ No due date set — urgency is estimated from task attributes only. Set a due date for a more accurate priority recommendation. "

        # Add specific reasoning
        if keyword_matches:
            explanation += f"Contains critical keywords suggesting high impact. "
        if days_until_due is not None:
            if days_until_due > 60:
                explanation += f"Due date is {int(days_until_due)} days away (long-term). "
            elif days_until_due > 7:
                explanation += f"Due date is {int(days_until_due)} days away. "
            elif days_until_due < 3:
                explanation += f"Due date is approaching ({int(days_until_due)} days). "
        
        # Highlight advanced factors in explanation
        if risk_likelihood and risk_impact:
            explanation += f"Risk assessment (L:{risk_likelihood}×I:{risk_impact}) factored in. "
        if workload_impact and workload_impact.lower() in ['high', 'critical']:
            explanation += f"High workload impact increases priority. "
        
        # Highlight complexity analysis in explanation
        if is_breakdown_recommended:
            explanation += f"AI complexity analysis suggests this is a complex task requiring breakdown. "
        elif ai_complexity and ai_complexity >= 7:
            explanation += f"AI detected high complexity ({ai_complexity}/10). "
        
        if not factors:
            factors.append("No strong indicators detected")
        
        # Calculate contribution percentages
        top_factors_with_pct = []
        for i, f in enumerate(factors[:5]):
            # Estimate contribution based on order and total factors
            pct = max(10, 40 - (i * 8)) if factors else 0
            top_factors_with_pct.append({
                'description': f,
                'contribution_percentage': pct,
                'factor': f.split(':')[0] if ':' in f else f
            })
        
        # Floor displayed score at 0 (negative penalties are for logic only)
        displayed_score = max(0, score)

        return {
            'suggested_priority': priority,
            'confidence': confidence,
            'no_due_date': no_due_date,  # Frontend uses this to show warning
            'reasoning': {
                'top_factors': top_factors_with_pct,
                'explanation': explanation,
                'confidence_level': self._confidence_label(confidence),
                'analysis_score': f"{displayed_score}/{max_score} points"
            },
            'alternatives': [],
            'is_ml_based': False,
            'fallback_method': 'rule_based'
        }
    
    def _log_suggestion(self, task, model_obj, priority, confidence, reasoning, features, user):
        """Log the suggestion for analytics"""
        from kanban.priority_models import PrioritySuggestionLog
        
        try:
            # Only log if task is saved
            if not task.pk:
                return
            
            feature_dict = dict(zip(self.FEATURE_NAMES, features))
            
            PrioritySuggestionLog.objects.create(
                task=task,
                model=model_obj,
                suggested_priority=priority,
                confidence_score=confidence,
                reasoning=reasoning,
                feature_values=feature_dict,
                shown_to_user=user
            )
        except Exception as e:
            logger.error(f"Error logging suggestion: {e}")


class PriorityModelTrainer:
    """
    Train and evaluate priority classification models
    """
    
    def __init__(self, board):
        self.board = board
        self.model = None
        self.feature_importance = {}
    
    def train_model(self, min_samples=20):
        """
        Train a priority classification model for the board
        
        Args:
            min_samples: Minimum training samples required
        
        Returns:
            dict: Training results including metrics
        """
        from kanban.priority_models import PriorityDecision, PriorityModel
        
        try:
            from sklearn.ensemble import RandomForestClassifier
            from sklearn.model_selection import train_test_split
            from sklearn.metrics import accuracy_score, precision_recall_fscore_support, confusion_matrix
        except ImportError as e:
            logger.error(f"scikit-learn not available: {e}")
            return {
                'success': False,
                'error': 'Machine learning libraries not installed. Run: pip install scikit-learn numpy'
            }
        
        if not NUMPY_AVAILABLE:
            return {
                'success': False,
                'error': 'NumPy not installed. Run: pip install numpy'
            }
        
        # Get training data
        decisions = PriorityDecision.objects.filter(
            board=self.board,
            was_correct__isnull=False  # Only use decisions with feedback
        ).order_by('-decided_at')[:500]  # Last 500 decisions
        
        if decisions.count() < min_samples:
            return {
                'success': False,
                'error': f'Insufficient training data. Need at least {min_samples} samples, have {decisions.count()}'
            }
        
        # Prepare training data
        X = []
        y = []
        
        for decision in decisions:
            features = self._extract_features_from_context(decision.task_context)
            X.append(features)
            y.append(decision.actual_priority)
        
        # Convert to numpy arrays
        if not NUMPY_AVAILABLE:
            return {
                'success': False,
                'error': 'NumPy not available for array operations'
            }
        
        X = np.array(X)
        y = np.array(y)
        
        # Split data
        X_train, X_test, y_train, y_test = train_test_split(
            X, y, test_size=0.2, random_state=42, stratify=y
        )
        
        # Train model
        self.model = RandomForestClassifier(
            n_estimators=100,
            max_depth=10,
            min_samples_split=5,
            random_state=42,
            class_weight='balanced'  # Handle imbalanced classes
        )
        
        self.model.fit(X_train, y_train)
        
        # Evaluate
        y_pred = self.model.predict(X_test)
        accuracy = accuracy_score(y_test, y_pred)
        
        # Calculate per-class metrics
        precision, recall, f1, support = precision_recall_fscore_support(
            y_test, y_pred, average=None, labels=self.model.classes_
        )
        
        conf_matrix = confusion_matrix(y_test, y_pred, labels=self.model.classes_)
        
        # Feature importance
        feature_names = PrioritySuggestionService.FEATURE_NAMES
        self.feature_importance = dict(zip(
            feature_names,
            self.model.feature_importances_
        ))
        
        # Save model
        model_file = pickle.dumps(self.model)
        
        # Get next version number
        last_version = PriorityModel.objects.filter(board=self.board).aggregate(
            max_ver=Count('model_version')
        )['max_ver'] or 0
        new_version = last_version + 1
        
        # Deactivate old models
        PriorityModel.objects.filter(board=self.board, is_active=True).update(is_active=False)
        
        # Create new model
        model_obj = PriorityModel.objects.create(
            board=self.board,
            model_version=new_version,
            model_type='random_forest',
            model_file=model_file,
            feature_importance=self.feature_importance,
            training_samples=len(X_train),
            accuracy_score=accuracy,
            precision_scores=dict(zip(self.model.classes_, precision.tolist())),
            recall_scores=dict(zip(self.model.classes_, recall.tolist())),
            f1_scores=dict(zip(self.model.classes_, f1.tolist())),
            confusion_matrix=conf_matrix.tolist(),
            is_active=True
        )
        
        logger.info(f"Trained priority model v{new_version} for board {self.board.id} - Accuracy: {accuracy:.2%}")
        
        return {
            'success': True,
            'model_version': new_version,
            'accuracy': accuracy,
            'training_samples': len(X_train),
            'test_samples': len(X_test),
            'feature_importance': self.feature_importance,
            'classes': self.model.classes_.tolist(),
            'precision': dict(zip(self.model.classes_, precision.tolist())),
            'recall': dict(zip(self.model.classes_, recall.tolist())),
            'f1_scores': dict(zip(self.model.classes_, f1.tolist())),
        }
    
    def _extract_features_from_context(self, context):
        """Extract feature vector from saved task context"""
        feature_names = PrioritySuggestionService.FEATURE_NAMES
        
        # Map context to feature vector
        days_until_due = context.get('days_until_due', 999)
        if days_until_due is None:
            days_until_due = 999
        
        features = [
            days_until_due,
            1 if context.get('is_overdue', False) else 0,
            context.get('complexity_score', 5),
            context.get('blocking_count', 0),
            context.get('blocked_by_count', 0),
            context.get('assignee_workload', 0),
            context.get('team_capacity', {}).get('tasks_per_member', 0),
            1 if context.get('has_description', False) else 0,
            context.get('description_length', 0),
            1 if context.get('collaboration_required', False) else 0,
            context.get('risk_score') or 0,
            1 if context.get('has_subtasks', False) else 0,
            1 if context.get('is_subtask', False) else 0,
            context.get('label_count', 0)
        ]
        
        return features
