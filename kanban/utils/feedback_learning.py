"""
Feedback Learning System

Learns from user feedback to improve coaching suggestions
Implements reinforcement learning patterns
"""

import logging
from datetime import timedelta
from typing import Dict, List, Optional
from django.utils import timezone
from django.db.models import Avg, Count, Q
from decimal import Decimal

logger = logging.getLogger(__name__)


class FeedbackLearningSystem:
    """
    Learns from user feedback to improve coaching quality
    Implements basic reinforcement learning for suggestion optimization
    """
    
    def __init__(self):
        """Initialize feedback learning system"""
        self.confidence_adjustment_rate = 0.1  # How much to adjust confidence based on feedback
    
    def record_feedback(self, suggestion, user, was_helpful: bool, 
                       relevance_score: int, action_taken: str,
                       feedback_text: str = '', outcome_description: str = '',
                       improved_situation: Optional[bool] = None) -> 'CoachingFeedback':
        """
        Record user feedback on a suggestion
        
        Args:
            suggestion: CoachingSuggestion object
            user: User providing feedback
            was_helpful: Was the suggestion helpful?
            relevance_score: Relevance rating (1-5)
            action_taken: Action taken by user
            feedback_text: Optional detailed feedback
            outcome_description: What happened after action
            improved_situation: Did situation improve?
            
        Returns:
            Created CoachingFeedback object
        """
        from kanban.coach_models import CoachingFeedback
        
        # Create feedback entry
        feedback = CoachingFeedback.objects.create(
            suggestion=suggestion,
            user=user,
            was_helpful=was_helpful,
            relevance_score=relevance_score,
            action_taken=action_taken,
            feedback_text=feedback_text,
            outcome_description=outcome_description,
            improved_situation=improved_situation
        )
        
        # Update suggestion with feedback
        suggestion.was_helpful = was_helpful
        suggestion.action_taken = action_taken
        
        if action_taken in ['accepted', 'partially', 'modified']:
            suggestion.status = 'resolved'
            suggestion.resolved_at = timezone.now()
        elif action_taken in ['ignored', 'not_applicable']:
            suggestion.status = 'dismissed'
            suggestion.resolved_at = timezone.now()
        
        suggestion.save()
        
        # Trigger learning from this feedback
        self._learn_from_feedback(feedback)
        
        logger.info(f"Recorded feedback for suggestion {suggestion.id}: helpful={was_helpful}, action={action_taken}")
        
        return feedback
    
    def _learn_from_feedback(self, feedback: 'CoachingFeedback'):
        """
        Learn from feedback to improve future suggestions
        
        Args:
            feedback: CoachingFeedback object
        """
        try:
            # Update suggestion type effectiveness
            self._update_suggestion_type_effectiveness(feedback)
            
            # Learn context patterns
            self._learn_context_patterns(feedback)
            
            # Generate insights if enough data
            self._generate_insights(feedback)
            
        except Exception as e:
            logger.error(f"Error learning from feedback: {e}")
    
    def _update_suggestion_type_effectiveness(self, feedback: 'CoachingFeedback'):
        """Update effectiveness metrics for this suggestion type"""
        from kanban.coach_models import CoachingSuggestion
        
        suggestion = feedback.suggestion
        suggestion_type = suggestion.suggestion_type
        
        # Get all feedback for this suggestion type
        similar_suggestions = CoachingSuggestion.objects.filter(
            suggestion_type=suggestion_type,
            board=suggestion.board
        )
        
        # Calculate effectiveness metrics
        total = similar_suggestions.count()
        helpful = similar_suggestions.filter(was_helpful=True).count()
        acted_on = similar_suggestions.filter(
            action_taken__in=['accepted', 'partially', 'modified']
        ).count()
        
        effectiveness_rate = (helpful / total * 100) if total > 0 else 0
        action_rate = (acted_on / total * 100) if total > 0 else 0
        
        logger.info(
            f"Suggestion type '{suggestion_type}' effectiveness: "
            f"{effectiveness_rate:.1f}% helpful, {action_rate:.1f}% action rate "
            f"(n={total})"
        )
        
        # Adjust confidence for future suggestions of this type
        # If effectiveness is low, reduce confidence
        if effectiveness_rate < 40 and total >= 5:
            logger.warning(
                f"Suggestion type '{suggestion_type}' has low effectiveness. "
                f"Consider adjusting rules or thresholds."
            )
    
    def _learn_context_patterns(self, feedback: 'CoachingFeedback'):
        """Learn which contexts make suggestions more or less effective"""
        suggestion = feedback.suggestion
        
        # Extract context features
        context_features = {
            'board_size': suggestion.board.members.count(),
            'severity': suggestion.severity,
            'confidence': float(suggestion.confidence_score),
            'generation_method': suggestion.generation_method,
        }
        
        # Add metrics snapshot features
        if suggestion.metrics_snapshot:
            for key, value in suggestion.metrics_snapshot.items():
                if isinstance(value, (int, float)):
                    context_features[f'metric_{key}'] = value
        
        # Store pattern (simplified - in production, use ML model)
        logger.debug(f"Context pattern: {context_features} -> helpful={feedback.was_helpful}")
    
    def _generate_insights(self, feedback: 'CoachingFeedback'):
        """Generate insights when sufficient data is available"""
        from kanban.coach_models import CoachingSuggestion, CoachingInsight
        
        suggestion_type = feedback.suggestion.suggestion_type
        
        # Count feedback for this type
        feedback_count = CoachingSuggestion.objects.filter(
            suggestion_type=suggestion_type,
            was_helpful__isnull=False
        ).count()
        
        # Generate insights once we have enough data
        if feedback_count >= 10 and feedback_count % 10 == 0:
            self._create_insight_for_type(suggestion_type, feedback_count)
    
    def _create_insight_for_type(self, suggestion_type: str, sample_size: int):
        """Create a coaching insight based on feedback patterns"""
        from kanban.coach_models import CoachingSuggestion, CoachingInsight
        
        # Get all suggestions of this type with feedback
        suggestions = CoachingSuggestion.objects.filter(
            suggestion_type=suggestion_type,
            was_helpful__isnull=False
        )
        
        # Calculate statistics
        helpful_rate = suggestions.filter(was_helpful=True).count() / sample_size
        action_rate = suggestions.filter(
            action_taken__in=['accepted', 'partially', 'modified']
        ).count() / sample_size
        
        avg_confidence = suggestions.aggregate(
            Avg('confidence_score')
        )['confidence_score__avg'] or 0
        
        # Determine if this is a valuable insight
        if helpful_rate > 0.7 and action_rate > 0.5:
            insight_desc = (
                f"Suggestions of type '{suggestion_type}' are highly effective "
                f"({helpful_rate*100:.0f}% helpful, {action_rate*100:.0f}% action rate). "
                f"Continue generating these suggestions."
            )
            confidence = Decimal(str(min(helpful_rate, 0.95)))
            
        elif helpful_rate < 0.4 or action_rate < 0.3:
            insight_desc = (
                f"Suggestions of type '{suggestion_type}' have low effectiveness "
                f"({helpful_rate*100:.0f}% helpful, {action_rate*100:.0f}% action rate). "
                f"Consider adjusting thresholds or improving message quality."
            )
            confidence = Decimal(str(min(1 - helpful_rate, 0.85)))
        else:
            # Moderate effectiveness - no insight needed
            return
        
        # Create or update insight
        insight, created = CoachingInsight.objects.get_or_create(
            insight_type='effectiveness',
            title=f"Effectiveness pattern for {suggestion_type}",
            defaults={
                'description': insight_desc,
                'confidence_score': confidence,
                'sample_size': sample_size,
                'applicable_to_suggestion_types': [suggestion_type],
                'rule_adjustments': {
                    'suggestion_type': suggestion_type,
                    'helpful_rate': helpful_rate,
                    'action_rate': action_rate,
                    'recommended_confidence': float(avg_confidence) * helpful_rate
                }
            }
        )
        
        if not created:
            # Update existing insight
            insight.description = insight_desc
            insight.confidence_score = confidence
            insight.sample_size = sample_size
            insight.save()
        
        logger.info(f"Generated insight for {suggestion_type}: {insight_desc}")
    
    def get_adjusted_confidence(self, suggestion_type: str, base_confidence: float,
                                board) -> float:
        """
        Get adjusted confidence score based on learning
        
        Args:
            suggestion_type: Type of suggestion
            base_confidence: Base confidence from rules
            board: Board context
            
        Returns:
            Adjusted confidence score (0-1)
        """
        from kanban.coach_models import CoachingSuggestion, CoachingInsight
        
        # Get all active insights and filter in Python (SQLite doesn't support JSONField contains)
        all_insights = CoachingInsight.objects.filter(is_active=True).order_by('-confidence_score', '-sample_size')
        insights = [
            insight for insight in all_insights 
            if suggestion_type in insight.applicable_to_suggestion_types
        ]
        
        if not insights:
            return base_confidence
        
        # Use top insight to adjust confidence
        top_insight = insights[0]
        rule_adjustments = top_insight.rule_adjustments
        
        if 'recommended_confidence' in rule_adjustments:
            adjusted = float(rule_adjustments['recommended_confidence'])
            
            # Blend with base confidence (weighted average)
            weight = min(top_insight.sample_size / 20, 0.7)  # Max 70% weight on learned data
            final_confidence = (adjusted * weight) + (base_confidence * (1 - weight))
            
            logger.debug(
                f"Adjusted confidence for {suggestion_type}: "
                f"{base_confidence:.2f} -> {final_confidence:.2f} "
                f"(based on {top_insight.sample_size} samples)"
            )
            
            return max(0.1, min(1.0, final_confidence))  # Clamp to [0.1, 1.0]
        
        return base_confidence
    
    def should_generate_suggestion(self, suggestion_type: str, board,
                                  base_confidence: float = 0.75) -> bool:
        """
        Decide if a suggestion should be generated based on learning
        
        Args:
            suggestion_type: Type of suggestion
            board: Board context
            base_confidence: Base confidence from rules
            
        Returns:
            True if suggestion should be generated
        """
        from kanban.coach_models import CoachingInsight
        
        # Get all active insights and filter in Python (SQLite doesn't support JSONField contains)
        all_insights = CoachingInsight.objects.filter(is_active=True)
        insights = [
            insight for insight in all_insights 
            if suggestion_type in insight.applicable_to_suggestion_types
        ]
        
        for insight in insights:
            adjustments = insight.rule_adjustments
            
            # If we've learned this type is ineffective, suppress it
            if 'helpful_rate' in adjustments:
                helpful_rate = adjustments['helpful_rate']
                action_rate = adjustments.get('action_rate', 0)
                
                # Suppress if consistently unhelpful (>20 samples)
                if insight.sample_size >= 20 and helpful_rate < 0.3 and action_rate < 0.2:
                    logger.info(
                        f"Suppressing {suggestion_type} due to low effectiveness "
                        f"({helpful_rate*100:.0f}% helpful, {insight.sample_size} samples)"
                    )
                    return False
        
        return True
    
    def calculate_pm_coaching_effectiveness(self, board, pm_user,
                                          days: int = 30) -> Dict:
        """
        Calculate coaching effectiveness for a PM
        
        Args:
            board: Board to analyze
            pm_user: PM user
            days: Time period in days
            
        Returns:
            Effectiveness metrics
        """
        from kanban.coach_models import CoachingSuggestion, CoachingFeedback
        
        start_date = timezone.now() - timedelta(days=days)
        
        # Get suggestions for this board
        suggestions = CoachingSuggestion.objects.filter(
            board=board,
            created_at__gte=start_date
        )
        
        total_suggestions = suggestions.count()
        
        if total_suggestions == 0:
            return {
                'total_suggestions': 0,
                'feedback_count': 0,
                'helpful_count': 0,
                'acted_on': 0,
                'dismissed_count': 0,
                'effectiveness_score': 0,
                'overall_score': 0,
                'action_rate': 0,
                'helpful_rate': 0,
                'dismissal_rate': 0,
                'avg_relevance': 0,
                'avg_confidence': 0,
                'message': 'No suggestions generated yet'
            }
        
        # Calculate metrics
        with_feedback = suggestions.filter(was_helpful__isnull=False)
        feedback_count = with_feedback.count()
        
        helpful_count = suggestions.filter(was_helpful=True).count()
        acted_on = suggestions.filter(
            action_taken__in=['accepted', 'partially', 'modified']
        ).count()
        
        # Get average relevance from detailed feedback
        feedbacks = CoachingFeedback.objects.filter(
            suggestion__in=suggestions
        )
        
        avg_relevance = feedbacks.aggregate(
            Avg('relevance_score')
        )['relevance_score__avg'] or 0
        
        # Calculate dismissal metrics
        dismissed_count = suggestions.filter(status='dismissed').count()
        dismissal_rate = (dismissed_count / total_suggestions * 100) if total_suggestions > 0 else 0
        
        # Calculate average confidence score
        avg_confidence = suggestions.aggregate(
            Avg('confidence_score')
        )['confidence_score__avg'] or 0
        
        # Calculate rates
        action_rate = (acted_on / total_suggestions * 100) if total_suggestions > 0 else 0
        helpful_rate = (helpful_count / feedback_count * 100) if feedback_count > 0 else 0
        
        # Overall effectiveness score (weighted combination)
        effectiveness_score = (
            (helpful_rate * 0.4) +
            (action_rate * 0.4) +
            (avg_relevance / 5 * 100 * 0.2)
        )
        
        return {
            'total_suggestions': total_suggestions,
            'feedback_count': feedback_count,
            'helpful_count': helpful_count,
            'acted_on': acted_on,
            'dismissed_count': dismissed_count,
            'action_rate': round(action_rate, 1),
            'helpful_rate': round(helpful_rate, 1),
            'dismissal_rate': round(dismissal_rate, 1),
            'avg_relevance': round(avg_relevance, 2),
            'avg_confidence': round(float(avg_confidence), 2),
            'effectiveness_score': round(effectiveness_score, 1),
            'overall_score': round(effectiveness_score, 1),  # Alias for template compatibility
            'message': self._generate_effectiveness_message(effectiveness_score)
        }
    
    def _generate_effectiveness_message(self, score: float) -> str:
        """Generate human-readable message about effectiveness"""
        if score >= 80:
            return "Excellent! Coaching is highly effective."
        elif score >= 60:
            return "Good! Coaching is providing value."
        elif score >= 40:
            return "Moderate effectiveness. Room for improvement."
        elif score >= 20:
            return "Low effectiveness. Suggestions may need adjustment."
        else:
            return "Very low effectiveness. Review coaching strategy."
    
    def get_improvement_recommendations(self, board, pm_user) -> List[str]:
        """
        Get recommendations for improving PM effectiveness
        
        Args:
            board: Board to analyze
            pm_user: PM user
            
        Returns:
            List of recommendation strings
        """
        from kanban.coach_models import CoachingSuggestion
        
        recommendations = []
        
        # Analyze recent suggestions
        recent = CoachingSuggestion.objects.filter(
            board=board,
            created_at__gte=timezone.now() - timedelta(days=30)
        )
        
        # Check action rate
        total = recent.count()
        if total > 0:
            acted_on = recent.filter(
                action_taken__in=['accepted', 'partially', 'modified']
            ).count()
            action_rate = (acted_on / total * 100)
            
            if action_rate < 30:
                if total == acted_on == 0:
                    recommendations.append(
                        "You haven't engaged with any suggestions yet. Try acting on 1-2 per week "
                        "to build coaching momentum."
                    )
                else:
                    recommendations.append(
                        "Most suggestions haven't been acted on yet. Try accepting or modifying "
                        "1-2 per week to build coaching engagement."
                    )
        
        # Check for recurring suggestion types
        type_counts = recent.values('suggestion_type').annotate(
            count=Count('id')
        ).order_by('-count')
        
        if type_counts:
            top_type = type_counts[0]
            if top_type['count'] >= 3:
                recommendations.append(
                    f"You're seeing repeated '{top_type['suggestion_type']}' suggestions. "
                    f"Addressing root causes will prevent recurrence."
                )
        
        # Check response time
        acknowledged = recent.filter(acknowledged_at__isnull=False)
        if acknowledged.exists():
            avg_response_hours = sum([
                (s.acknowledged_at - s.created_at).total_seconds() / 3600
                for s in acknowledged
            ]) / acknowledged.count()
            
            if avg_response_hours > 72:  # More than 3 days
                recommendations.append(
                    "Try responding to suggestions within 48 hours to stay proactive."
                )
        
        if not recommendations:
            recommendations.append(
                "Keep up the good work! Stay engaged with coaching suggestions."
            )
        
        return recommendations
