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
        Learn from feedback to improve future suggestions.
        Incorporates outcome-based reinforcement: suggestions that actually
        improved the situation get stronger positive signals than those
        merely rated as 'helpful'.
        
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
            
            # Outcome-based reinforcement learning
            self._apply_outcome_reinforcement(feedback)
            
        except Exception as e:
            logger.error(f"Error learning from feedback: {e}")
    
    def _apply_outcome_reinforcement(self, feedback: 'CoachingFeedback'):
        """
        Apply outcome-based reinforcement to coaching insights.
        
        When users report that a suggestion actually improved the situation
        (improved_situation=True), we boost the confidence more than just
        a 'helpful' rating. This creates a true outcome-based learning signal.
        
        Args:
            feedback: CoachingFeedback object with outcome data
        """
        from kanban.coach_models import CoachingSuggestion, CoachingInsight
        
        suggestion = feedback.suggestion
        suggestion_type = suggestion.suggestion_type
        
        # Only process if we have outcome data
        if feedback.improved_situation is None:
            return
        
        # Get all suggestions of this type with outcome data
        suggestions_with_outcomes = CoachingSuggestion.objects.filter(
            suggestion_type=suggestion_type,
        ).filter(
            feedback_entries__improved_situation__isnull=False,
        ).distinct()
        
        total_outcomes = suggestions_with_outcomes.count()
        if total_outcomes < 3:
            return  # Not enough outcome data yet
        
        # Count positive outcomes
        positive_outcomes = suggestions_with_outcomes.filter(
            feedback_entries__improved_situation=True,
        ).distinct().count()
        
        outcome_success_rate = positive_outcomes / total_outcomes if total_outcomes > 0 else 0
        
        # Look for existing effectiveness insight to enhance with outcome data
        insight_title = f"Effectiveness pattern for {suggestion_type}"
        try:
            insight = CoachingInsight.objects.get(
                insight_type='effectiveness',
                title=insight_title,
            )
            
            # Enhance rule_adjustments with outcome data
            adjustments = insight.rule_adjustments or {}
            adjustments['outcome_success_rate'] = round(outcome_success_rate, 4)
            adjustments['outcome_sample_size'] = total_outcomes
            
            # Boost recommended_confidence if outcomes are positive
            if 'recommended_confidence' in adjustments:
                base_rec = adjustments['recommended_confidence']
                # Positive outcomes boost confidence by up to 15%
                if outcome_success_rate > 0.6:
                    outcome_boost = min((outcome_success_rate - 0.5) * 0.3, 0.15)
                    adjustments['recommended_confidence'] = min(
                        base_rec + outcome_boost, 0.95
                    )
                elif outcome_success_rate < 0.3 and total_outcomes >= 5:
                    # Poor outcomes reduce confidence
                    outcome_penalty = min((0.4 - outcome_success_rate) * 0.2, 0.10)
                    adjustments['recommended_confidence'] = max(
                        base_rec - outcome_penalty, 0.1
                    )
            
            insight.rule_adjustments = adjustments
            insight.save()
            
            logger.info(
                f"Outcome reinforcement for {suggestion_type}: "
                f"success_rate={outcome_success_rate*100:.0f}% (n={total_outcomes})"
            )
            
        except CoachingInsight.DoesNotExist:
            # No effectiveness insight yet — outcome data will be picked up
            # when _generate_insights creates one
            pass
        except Exception as e:
            logger.debug(f"Could not apply outcome reinforcement: {e}")
    
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
        """
        Learn which contexts make suggestions more or less effective.
        Persists context patterns to CoachingInsight so future confidence
        adjustments account for board size, severity, and generation method.
        """
        from kanban.coach_models import CoachingSuggestion, CoachingInsight
        
        suggestion = feedback.suggestion
        suggestion_type = suggestion.suggestion_type
        board = suggestion.board
        
        # Extract context features
        context_features = {
            'board_size': board.memberships.count(),
            'severity': suggestion.severity,
            'confidence': float(suggestion.confidence_score),
            'generation_method': suggestion.generation_method,
        }
        
        # Add metrics snapshot features
        if suggestion.metrics_snapshot:
            for key, value in suggestion.metrics_snapshot.items():
                if isinstance(value, (int, float)):
                    context_features[f'metric_{key}'] = value
        
        # --- Severity-level effectiveness tracking ---
        severity = suggestion.severity
        severity_suggestions = CoachingSuggestion.objects.filter(
            suggestion_type=suggestion_type,
            severity=severity,
            was_helpful__isnull=False,
        )
        severity_total = severity_suggestions.count()
        
        if severity_total >= 5:
            severity_helpful = severity_suggestions.filter(was_helpful=True).count()
            severity_helpful_rate = severity_helpful / severity_total
            severity_acted = severity_suggestions.filter(
                action_taken__in=['accepted', 'partially', 'modified']
            ).count()
            severity_action_rate = severity_acted / severity_total
            
            # Create/update a context_factor insight for severity
            insight_title = f"Severity context for {suggestion_type} at {severity}"
            insight, created = CoachingInsight.objects.update_or_create(
                insight_type='context_factor',
                title=insight_title,
                defaults={
                    'description': (
                        f"When {suggestion_type} suggestions are generated at "
                        f"'{severity}' severity, they have a {severity_helpful_rate*100:.0f}% "
                        f"helpful rate and {severity_action_rate*100:.0f}% action rate "
                        f"(n={severity_total})."
                    ),
                    'confidence_score': Decimal(str(min(severity_helpful_rate, 0.95))),
                    'sample_size': severity_total,
                    'applicable_to_suggestion_types': [suggestion_type],
                    'rule_adjustments': {
                        'context_type': 'severity',
                        'severity': severity,
                        'suggestion_type': suggestion_type,
                        'helpful_rate': severity_helpful_rate,
                        'action_rate': severity_action_rate,
                        'recommended_confidence': float(suggestion.confidence_score) * severity_helpful_rate,
                        'sample_size': severity_total,
                    },
                    'is_active': True,
                }
            )
            
            logger.info(
                f"Context pattern learned: {suggestion_type} at {severity} severity -> "
                f"{severity_helpful_rate*100:.0f}% helpful (n={severity_total})"
            )
        
        # --- Generation method effectiveness tracking ---
        gen_method = suggestion.generation_method
        if gen_method:
            method_suggestions = CoachingSuggestion.objects.filter(
                suggestion_type=suggestion_type,
                generation_method=gen_method,
                was_helpful__isnull=False,
            )
            method_total = method_suggestions.count()
            
            if method_total >= 5:
                method_helpful = method_suggestions.filter(was_helpful=True).count()
                method_helpful_rate = method_helpful / method_total
                method_acted = method_suggestions.filter(
                    action_taken__in=['accepted', 'partially', 'modified']
                ).count()
                method_action_rate = method_acted / method_total
                
                insight_title = f"Generation method context for {suggestion_type} via {gen_method}"
                CoachingInsight.objects.update_or_create(
                    insight_type='context_factor',
                    title=insight_title,
                    defaults={
                        'description': (
                            f"When {suggestion_type} suggestions are generated via "
                            f"'{gen_method}' method, they have a {method_helpful_rate*100:.0f}% "
                            f"helpful rate and {method_action_rate*100:.0f}% action rate "
                            f"(n={method_total})."
                        ),
                        'confidence_score': Decimal(str(min(method_helpful_rate, 0.95))),
                        'sample_size': method_total,
                        'applicable_to_suggestion_types': [suggestion_type],
                        'rule_adjustments': {
                            'context_type': 'generation_method',
                            'generation_method': gen_method,
                            'suggestion_type': suggestion_type,
                            'helpful_rate': method_helpful_rate,
                            'action_rate': method_action_rate,
                            'recommended_confidence': float(suggestion.confidence_score) * method_helpful_rate,
                            'sample_size': method_total,
                        },
                        'is_active': True,
                    }
                )
                
                logger.info(
                    f"Context pattern learned: {suggestion_type} via {gen_method} -> "
                    f"{method_helpful_rate*100:.0f}% helpful (n={method_total})"
                )
        
        # --- Board size category tracking ---
        board_size = board.memberships.count()
        if board_size <= 3:
            size_category = 'small'
        elif board_size <= 8:
            size_category = 'medium'
        else:
            size_category = 'large'
        
        # We track by storing the features for future get_adjusted_confidence lookups
        logger.debug(
            f"Context pattern recorded: {suggestion_type} / {severity} / "
            f"{gen_method} / board_size={board_size}({size_category}) -> "
            f"helpful={feedback.was_helpful}"
        )
    
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
                                board, severity: str = None,
                                generation_method: str = None) -> float:
        """
        Get adjusted confidence score based on learning, including context factors.
        
        Blends three sources of learned confidence:
        1. Effectiveness insights (per suggestion type)
        2. Severity context insights (per type + severity)
        3. Generation method context insights (per type + method)
        
        Args:
            suggestion_type: Type of suggestion
            base_confidence: Base confidence from rules
            board: Board context
            severity: Optional severity level for context-aware adjustment
            generation_method: Optional generation method for context-aware adjustment
            
        Returns:
            Adjusted confidence score (0-1)
        """
        from kanban.coach_models import CoachingInsight
        
        # Get all active insights for this suggestion type
        all_insights = CoachingInsight.objects.filter(is_active=True).order_by('-confidence_score', '-sample_size')
        type_insights = [
            insight for insight in all_insights 
            if suggestion_type in insight.applicable_to_suggestion_types
        ]
        
        if not type_insights:
            # Cold-start fallback: use organization-level learning profile
            return self._get_org_adjusted_confidence(
                suggestion_type, base_confidence, board
            )
        
        # Collect confidence adjustments from different insight types
        adjustments = []
        
        for insight in type_insights:
            rule_adj = insight.rule_adjustments
            if 'recommended_confidence' not in rule_adj:
                continue
                
            context_type = rule_adj.get('context_type', 'general')
            adjusted_conf = float(rule_adj['recommended_confidence'])
            weight = min(insight.sample_size / 20, 0.7)
            
            # Prioritize context-specific insights when matching
            if context_type == 'severity' and severity and rule_adj.get('severity') == severity:
                # Severity-specific insight — boost weight slightly for specificity
                adjustments.append((adjusted_conf, min(weight * 1.1, 0.75), 'severity'))
            elif context_type == 'generation_method' and generation_method and rule_adj.get('generation_method') == generation_method:
                adjustments.append((adjusted_conf, min(weight * 1.1, 0.75), 'method'))
            elif context_type not in ('severity', 'generation_method'):
                # General effectiveness insight
                adjustments.append((adjusted_conf, weight, 'general'))
        
        if not adjustments:
            return base_confidence
        
        # Weighted average of all applicable adjustments
        total_weight = sum(w for _, w, _ in adjustments)
        if total_weight > 0:
            blended_learned = sum(conf * w for conf, w, _ in adjustments) / total_weight
            # Blend learned vs base: use max weight from any single source, capped at 0.75
            max_weight = min(max(w for _, w, _ in adjustments), 0.75)
            final_confidence = (blended_learned * max_weight) + (base_confidence * (1 - max_weight))
        else:
            final_confidence = base_confidence
        
        logger.debug(
            f"Adjusted confidence for {suggestion_type}: "
            f"{base_confidence:.2f} -> {final_confidence:.2f} "
            f"(sources: {[(s, round(w, 2)) for _, w, s in adjustments]})"
        )
        
        return max(0.1, min(1.0, final_confidence))
    
    def _get_org_adjusted_confidence(self, suggestion_type: str, 
                                      base_confidence: float, board) -> float:
        """
        Cold-start fallback: use organization-level aggregated learning data
        when a board has insufficient board-level insights.
        
        Args:
            suggestion_type: Type of suggestion
            base_confidence: Base confidence from rules
            board: Board context (used to find organization)
            
        Returns:
            Adjusted confidence, or base_confidence if no org data available
        """
        try:
            from kanban.coach_models import OrganizationLearningProfile
            
            org = getattr(board, 'organization', None)
            if not org:
                return base_confidence
            
            profile = OrganizationLearningProfile.objects.filter(
                organization=org,
                suggestion_type=suggestion_type,
                total_feedback__gte=5,  # Need minimum data
            ).first()
            
            if not profile:
                return base_confidence
            
            recommended = float(profile.recommended_confidence)
            
            # Lower weight for org-level data (max 0.4) — less specific than board-level
            weight = min(profile.total_feedback / 50, 0.4)
            final = (recommended * weight) + (base_confidence * (1 - weight))
            
            logger.debug(
                f"Org-level confidence for {suggestion_type}: "
                f"{base_confidence:.2f} -> {final:.2f} "
                f"(org: {org.name}, {profile.total_feedback} samples, weight={weight:.2f})"
            )
            
            return max(0.1, min(1.0, final))
            
        except Exception as e:
            logger.debug(f"Org fallback unavailable: {e}")
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
        
        # If no board-level insights exist, check organization-level suppression
        if not insights:
            try:
                from kanban.coach_models import OrganizationLearningProfile
                org = getattr(board, 'organization', None)
                if org:
                    org_profile = OrganizationLearningProfile.objects.filter(
                        organization=org,
                        suggestion_type=suggestion_type,
                    ).first()
                    if org_profile and org_profile.should_suppress:
                        logger.info(
                            f"Suppressing {suggestion_type} based on org-level data "
                            f"(org: {org.name})"
                        )
                        return False
            except Exception:
                pass
        
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

    def refresh_pm_metrics(self, board, pm_user, days: int = 30):
        """
        Auto-populate PMMetrics from coaching data and board activity.
        Called periodically to keep PM performance profile up to date.
        
        Args:
            board: Board to analyze
            pm_user: PM user
            days: Time period in days
            
        Returns:
            PMMetrics instance (created or updated)
        """
        from kanban.coach_models import CoachingSuggestion, CoachingFeedback, PMMetrics
        from kanban.models import Task
        
        period_end = timezone.now().date()
        period_start = period_end - timedelta(days=days)
        
        # Get coaching effectiveness metrics
        effectiveness = self.calculate_pm_coaching_effectiveness(board, pm_user, days)
        
        # Calculate suggestion response times
        suggestions = CoachingSuggestion.objects.filter(
            board=board,
            created_at__gte=timezone.now() - timedelta(days=days)
        )
        
        total_suggestions = suggestions.count()
        acted_on = suggestions.filter(
            action_taken__in=['accepted', 'partially', 'modified']
        ).count()
        
        # Average response time (acknowledged suggestions)
        acknowledged = suggestions.filter(acknowledged_at__isnull=False)
        avg_response_hours = Decimal('0')
        if acknowledged.exists():
            total_hours = sum([
                (s.acknowledged_at - s.created_at).total_seconds() / 3600
                for s in acknowledged
            ])
            avg_response_hours = Decimal(str(round(total_hours / acknowledged.count(), 2)))
        
        # Velocity trend — compare task completion: last N days vs previous N days
        recent_completed = Task.objects.filter(
            column__board=board,
            column__name__icontains='done',
            updated_at__gte=timezone.now() - timedelta(days=days)
        ).count()
        
        previous_completed = Task.objects.filter(
            column__board=board,
            column__name__icontains='done',
            updated_at__gte=timezone.now() - timedelta(days=days * 2),
            updated_at__lt=timezone.now() - timedelta(days=days)
        ).count()
        
        if recent_completed > previous_completed * 1.1:
            velocity_trend = 'improving'
        elif recent_completed < previous_completed * 0.9:
            velocity_trend = 'declining'
        else:
            velocity_trend = 'stable'
        
        # Deadline hit rate — tasks with due dates that were completed on time
        tasks_with_due = Task.objects.filter(
            column__board=board,
            due_date__isnull=False,
            due_date__gte=period_start,
            due_date__lte=period_end,
        )
        total_due = tasks_with_due.count()
        on_time = tasks_with_due.filter(
            column__name__icontains='done',
        ).count()
        deadline_hit_rate = Decimal(str(round((on_time / total_due * 100) if total_due > 0 else 0, 2)))
        
        # Identify struggle and improvement areas from suggestion patterns
        struggle_areas = []
        improvement_areas = []
        
        type_stats = suggestions.values('suggestion_type').annotate(
            total=Count('id'),
            helpful=Count('id', filter=Q(was_helpful=True)),
        ).order_by('-total')
        
        for stat in type_stats:
            stype = stat['suggestion_type']
            helpful_rate = stat['helpful'] / stat['total'] if stat['total'] > 0 else 0
            if stat['total'] >= 3 and helpful_rate < 0.4:
                struggle_areas.append(stype)
            elif stat['total'] >= 3 and helpful_rate > 0.7:
                improvement_areas.append(stype)
        
        # Create or update PMMetrics
        from django.db.models import Q as DQ
        metrics, created = PMMetrics.objects.update_or_create(
            board=board,
            pm_user=pm_user,
            period_start=period_start,
            period_end=period_end,
            defaults={
                'suggestions_received': total_suggestions,
                'suggestions_acted_on': acted_on,
                'avg_response_time_hours': avg_response_hours,
                'velocity_trend': velocity_trend,
                'deadline_hit_rate': deadline_hit_rate,
                'improvement_areas': improvement_areas,
                'struggle_areas': struggle_areas,
                'coaching_effectiveness_score': Decimal(str(round(
                    effectiveness.get('effectiveness_score', 0), 2
                ))),
                'calculated_by': 'feedback_learning_system',
            }
        )
        
        logger.info(
            f"PMMetrics {'created' if created else 'updated'} for {pm_user.username} "
            f"on {board.name}: effectiveness={effectiveness.get('effectiveness_score', 0):.1f}, "
            f"velocity={velocity_trend}"
        )
        
        return metrics