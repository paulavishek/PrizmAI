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
            delta = task.due_date - timezone.now()
            days_until_due = delta.total_seconds() / 86400
            is_overdue = days_until_due < 0
        
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
        if task.column:
            board = task.column.board
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
        descriptions = {
            'days_until_due': f"Due in {abs(int(value))} days" if value < 999 else "No due date set",
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
        
        Uses heuristics based on due date, dependencies, and complexity
        """
        score = 0
        factors = []
        
        # Due date urgency (0-4 points)
        if task.due_date:
            delta = task.due_date - timezone.now()
            days_until_due = delta.total_seconds() / 86400
            
            if days_until_due < 0:
                score += 4
                factors.append("Task is overdue")
            elif days_until_due < 1:
                score += 3
                factors.append("Due within 24 hours")
            elif days_until_due < 3:
                score += 2
                factors.append("Due within 3 days")
            elif days_until_due < 7:
                score += 1
                factors.append("Due this week")
        
        # Blocking tasks (0-3 points)
        if task.pk:
            blocking_count = task.dependencies.count()
            if blocking_count >= 3:
                score += 3
                factors.append(f"Blocks {blocking_count} tasks")
            elif blocking_count >= 1:
                score += 2
                factors.append(f"Blocks {blocking_count} tasks")
        
        # Complexity (0-2 points)
        if task.complexity_score >= 8:
            score += 2
            factors.append(f"High complexity ({task.complexity_score}/10)")
        elif task.complexity_score >= 6:
            score += 1
            factors.append(f"Medium-high complexity")
        
        # Risk (0-2 points)
        if task.risk_score:
            if task.risk_score >= 7:
                score += 2
                factors.append("High risk")
            elif task.risk_score >= 4:
                score += 1
                factors.append("Medium risk")
        
        # Collaboration (0-1 point)
        if task.collaboration_required:
            score += 1
            factors.append("Requires collaboration")
        
        # Determine priority based on score
        if score >= 8:
            priority = 'urgent'
            confidence = 0.75
        elif score >= 5:
            priority = 'high'
            confidence = 0.70
        elif score >= 3:
            priority = 'medium'
            confidence = 0.65
        else:
            priority = 'low'
            confidence = 0.60
        
        explanation = f"Based on rule-based analysis, this task should be **{priority}** priority. "
        if factors:
            explanation += f"Key factors: {', '.join(factors[:3])}."
        
        return {
            'suggested_priority': priority,
            'confidence': confidence,
            'reasoning': {
                'top_factors': [{'description': f} for f in factors[:5]],
                'explanation': explanation,
                'confidence_level': self._confidence_label(confidence)
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
