"""
Celery tasks for AI learning loop automation.

Handles:
- PM metrics auto-refresh (from coaching feedback)
- Periodic coaching suggestion generation
- Priority model periodic retraining
- Feedback text analysis for insight extraction
- Organization-level learning profile aggregation
"""
import logging
from celery import shared_task
from django.utils import timezone

logger = logging.getLogger(__name__)


@shared_task(name='kanban.refresh_pm_metrics')
def refresh_pm_metrics_task():
    """
    Refresh PMMetrics for all active boards/PM combinations.
    Runs daily to keep PM performance profiles current for coaching.
    """
    from kanban.models import Board
    from kanban.utils.feedback_learning import FeedbackLearningSystem
    
    learning_system = FeedbackLearningSystem()
    updated_count = 0
    
    try:
        active_boards = Board.objects.filter(is_archived=False)
        
        for board in active_boards:
            # Get the board creator and all members who might be PMs
            pm_users = set()
            if board.created_by:
                pm_users.add(board.created_by)
            # Also include members (they may receive coaching suggestions)
            for member in board.members.all():
                pm_users.add(member)
            
            for pm_user in pm_users:
                try:
                    learning_system.refresh_pm_metrics(board, pm_user, days=30)
                    updated_count += 1
                except Exception as e:
                    logger.error(
                        f"Error refreshing metrics for {pm_user.username} "
                        f"on {board.name}: {e}"
                    )
        
        logger.info(f"PM metrics refresh complete: {updated_count} profiles updated")
        return f"Updated {updated_count} PM metrics profiles"
        
    except Exception as e:
        logger.error(f"PM metrics refresh task failed: {e}")
        raise


@shared_task(name='kanban.generate_coaching_suggestions')
def generate_coaching_suggestions_task():
    """
    Generate coaching suggestions for all active boards.
    Runs daily before the executive briefing so insights are fresh.
    """
    from kanban.models import Board
    from kanban.utils.coaching_rules import CoachingRuleEngine
    from kanban.utils.feedback_learning import FeedbackLearningSystem
    from kanban.coach_models import CoachingSuggestion
    
    learning_system = FeedbackLearningSystem()
    total_created = 0
    total_skipped = 0
    boards_processed = 0
    
    try:
        active_boards = Board.objects.filter(is_archived=False)
        
        for board in active_boards:
            try:
                # Generate suggestions via rule engine
                rule_engine = CoachingRuleEngine(board)
                suggestions_data = rule_engine.analyze_and_generate_suggestions()
                
                if not suggestions_data:
                    continue
                
                boards_processed += 1
                
                for suggestion_data in suggestions_data:
                    # Check learning-based filter
                    should_generate = learning_system.should_generate_suggestion(
                        suggestion_data['suggestion_type'],
                        board,
                        float(suggestion_data.get('confidence_score', 0.75))
                    )
                    
                    if not should_generate:
                        total_skipped += 1
                        continue
                    
                    # Adjust confidence
                    adjusted_confidence = learning_system.get_adjusted_confidence(
                        suggestion_data['suggestion_type'],
                        float(suggestion_data.get('confidence_score', 0.75)),
                        board,
                        severity=suggestion_data.get('severity'),
                        generation_method=suggestion_data.get('generation_method'),
                    )
                    suggestion_data['confidence_score'] = adjusted_confidence
                    
                    # Check for duplicates
                    from django.db.models import Q
                    from datetime import timedelta
                    
                    existing = CoachingSuggestion.objects.filter(
                        board=board,
                        suggestion_type=suggestion_data['suggestion_type'],
                        created_at__gte=timezone.now() - timedelta(days=3),
                    ).filter(
                        Q(status='active') | Q(status='acknowledged')
                    ).exists()
                    
                    if existing:
                        total_skipped += 1
                        continue
                    
                    # Create suggestion
                    try:
                        CoachingSuggestion.objects.create(
                            board=board,
                            suggestion_type=suggestion_data['suggestion_type'],
                            severity=suggestion_data.get('severity', 'medium'),
                            title=suggestion_data.get('title', ''),
                            message=suggestion_data.get('message', ''),
                            reasoning=suggestion_data.get('reasoning', ''),
                            recommended_actions=suggestion_data.get('recommended_actions', []),
                            expected_impact=suggestion_data.get('expected_impact', ''),
                            metrics_snapshot=suggestion_data.get('metrics_snapshot', {}),
                            confidence_score=suggestion_data['confidence_score'],
                            ai_model_used=suggestion_data.get('ai_model_used', 'rule-based'),
                            generation_method=suggestion_data.get('generation_method', 'rule'),
                        )
                        total_created += 1
                    except Exception as create_err:
                        logger.error(f"Error creating suggestion: {create_err}")
                        
            except Exception as board_err:
                logger.error(f"Error processing board {board.name}: {board_err}")
        
        result = (
            f"Coaching generation complete: {total_created} created, "
            f"{total_skipped} skipped across {boards_processed} boards"
        )
        logger.info(result)
        return result
        
    except Exception as e:
        logger.error(f"Coaching suggestion generation task failed: {e}")
        raise


@shared_task(name='kanban.train_priority_models_periodic')
def train_priority_models_task():
    """
    Periodically retrain priority ML models for boards with enough new data.
    Only retrains if a board has accumulated sufficient new PriorityDecision records
    since the last training.
    """
    from kanban.models import Board
    from kanban.priority_models import PriorityDecision, PriorityModel
    
    MIN_NEW_DECISIONS = 20  # Minimum new decisions before retraining
    MIN_TOTAL_DECISIONS = 50  # Minimum total decisions for valid model
    
    retrained_count = 0
    skipped_count = 0
    
    try:
        active_boards = Board.objects.filter(is_archived=False)
        
        for board in active_boards:
            try:
                # Check if there's enough data
                total_decisions = PriorityDecision.objects.filter(board=board).count()
                
                if total_decisions < MIN_TOTAL_DECISIONS:
                    skipped_count += 1
                    continue
                
                # Check if we have enough NEW decisions since last training
                active_model = PriorityModel.get_active_model(board)
                if active_model:
                    new_decisions = PriorityDecision.objects.filter(
                        board=board,
                        decided_at__gt=active_model.trained_at
                    ).count()
                    
                    if new_decisions < MIN_NEW_DECISIONS:
                        skipped_count += 1
                        continue
                
                # Trigger retraining
                _train_board_priority_model(board)
                retrained_count += 1
                
            except Exception as board_err:
                logger.error(f"Error checking/training priority model for {board.name}: {board_err}")
        
        result = f"Priority model training: {retrained_count} retrained, {skipped_count} skipped"
        logger.info(result)
        return result
        
    except Exception as e:
        logger.error(f"Priority model training task failed: {e}")
        raise


def _train_board_priority_model(board):
    """
    Train a priority model for a specific board.
    Extracted as a helper so it can be called from both the Celery task and signal.
    """
    from kanban.priority_models import PriorityDecision, PriorityModel
    import pickle
    
    try:
        from sklearn.ensemble import RandomForestClassifier
        from sklearn.model_selection import train_test_split
        from sklearn.metrics import accuracy_score, precision_recall_fscore_support, confusion_matrix
        import numpy as np
    except ImportError:
        logger.error("scikit-learn not installed — cannot train priority model")
        return None
    
    # Get training data
    decisions = PriorityDecision.objects.filter(
        board=board,
        task_context__isnull=False,
    ).exclude(actual_priority='').order_by('-decided_at')[:500]
    
    if decisions.count() < 50:
        logger.info(f"Not enough data to train for {board.name} ({decisions.count()} decisions)")
        return None
    
    # Extract features and labels
    feature_keys = [
        'title_length', 'has_description', 'description_length',
        'days_until_due', 'is_overdue', 'complexity_score',
        'blocking_count', 'blocked_by_count', 'has_assignee',
        'assignee_workload', 'collaboration_required', 'risk_score',
        'has_subtasks', 'is_subtask', 'label_count', 'comment_count',
    ]
    
    priority_map = {'low': 0, 'medium': 1, 'high': 2, 'urgent': 3}
    
    X, y = [], []
    for d in decisions:
        ctx = d.task_context or {}
        features = []
        for key in feature_keys:
            val = ctx.get(key, 0)
            if isinstance(val, bool):
                val = int(val)
            elif val is None:
                val = 0
            elif isinstance(val, dict):
                val = val.get('tasks_per_member', 0) if 'tasks_per_member' in val else 0
            features.append(float(val))
        
        label = priority_map.get(d.actual_priority)
        if label is not None:
            X.append(features)
            y.append(label)
    
    if len(X) < 50:
        return None
    
    X = np.array(X)
    y = np.array(y)
    
    # Train/test split
    X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42)
    
    # Train
    clf = RandomForestClassifier(n_estimators=100, random_state=42, max_depth=10)
    clf.fit(X_train, y_train)
    
    # Evaluate
    y_pred = clf.predict(X_test)
    acc = accuracy_score(y_test, y_pred)
    precision, recall, f1, _ = precision_recall_fscore_support(y_test, y_pred, average=None, zero_division=0)
    cm = confusion_matrix(y_test, y_pred).tolist()
    
    # Feature importance
    importances = dict(zip(feature_keys, clf.feature_importances_.tolist()))
    
    # Deactivate old models
    PriorityModel.objects.filter(board=board, is_active=True).update(is_active=False)
    
    # Get next version
    last_version = PriorityModel.objects.filter(board=board).order_by('-model_version').first()
    next_version = (last_version.model_version + 1) if last_version else 1
    
    # Save new model
    model_bytes = pickle.dumps(clf)
    
    priority_labels = ['low', 'medium', 'high', 'urgent']
    precision_dict = {priority_labels[i]: float(precision[i]) for i in range(min(len(precision), len(priority_labels)))}
    recall_dict = {priority_labels[i]: float(recall[i]) for i in range(min(len(recall), len(priority_labels)))}
    f1_dict = {priority_labels[i]: float(f1[i]) for i in range(min(len(f1), len(priority_labels)))}
    
    new_model = PriorityModel.objects.create(
        board=board,
        model_version=next_version,
        model_type='random_forest',
        model_file=model_bytes,
        feature_importance=importances,
        training_samples=len(X),
        accuracy_score=acc,
        precision_scores=precision_dict,
        recall_scores=recall_dict,
        f1_scores=f1_dict,
        confusion_matrix=cm,
        is_active=True,
    )
    
    logger.info(
        f"Trained priority model v{next_version} for {board.name}: "
        f"accuracy={acc:.2%}, samples={len(X)}"
    )
    
    return new_model


@shared_task(name='kanban.analyze_feedback_text')
def analyze_feedback_text_task():
    """
    Periodically analyze free-text feedback from coaching and Spectra
    to extract themes and create CoachingInsight entries.
    Uses Gemini to summarize patterns in user feedback.
    """
    from kanban.coach_models import CoachingFeedback, CoachingInsight
    from ai_assistant.models import AIAssistantMessage
    from decimal import Decimal
    
    try:
        # Gather unanalyzed coaching feedback text from last 30 days
        from datetime import timedelta
        cutoff = timezone.now() - timedelta(days=30)
        
        coaching_feedback = CoachingFeedback.objects.filter(
            created_at__gte=cutoff,
            feedback_text__isnull=False,
        ).exclude(feedback_text='').values_list(
            'feedback_text', 'was_helpful', 'suggestion__suggestion_type'
        )[:100]
        
        # Gather Spectra feedback
        spectra_feedback = AIAssistantMessage.objects.filter(
            created_at__gte=cutoff,
            role='assistant',
            is_helpful__isnull=False,
            feedback__isnull=False,
        ).exclude(feedback='').values_list(
            'feedback', 'is_helpful'
        )[:100]
        
        total_items = len(coaching_feedback) + len(spectra_feedback)
        if total_items < 5:
            logger.info("Not enough feedback text to analyze")
            return "Insufficient feedback data"
        
        # Group by helpful/unhelpful for coaching feedback
        helpful_coaching = [f[0] for f in coaching_feedback if f[1] is True]
        unhelpful_coaching = [f[0] for f in coaching_feedback if f[1] is False]
        
        # Group coaching feedback by suggestion type
        type_feedback = {}
        for text, was_helpful, stype in coaching_feedback:
            if stype not in type_feedback:
                type_feedback[stype] = {'helpful': [], 'unhelpful': []}
            if was_helpful:
                type_feedback[stype]['helpful'].append(text)
            else:
                type_feedback[stype]['unhelpful'].append(text)
        
        # Create/update insights based on feedback text patterns
        insights_created = 0
        for stype, feedback_data in type_feedback.items():
            if len(feedback_data['helpful']) + len(feedback_data['unhelpful']) < 3:
                continue
            
            total = len(feedback_data['helpful']) + len(feedback_data['unhelpful'])
            helpful_rate = len(feedback_data['helpful']) / total if total > 0 else 0
            
            # Build description from feedback text
            desc_parts = []
            if feedback_data['helpful']:
                desc_parts.append(
                    f"Positive feedback themes ({len(feedback_data['helpful'])} items): "
                    + '; '.join(feedback_data['helpful'][:3])
                )
            if feedback_data['unhelpful']:
                desc_parts.append(
                    f"Negative feedback themes ({len(feedback_data['unhelpful'])} items): "
                    + '; '.join(feedback_data['unhelpful'][:3])
                )
            
            description = ' | '.join(desc_parts)
            if len(description) > 1000:
                description = description[:997] + '...'
            
            CoachingInsight.objects.update_or_create(
                insight_type='pm_behavior',
                title=f"User feedback themes for {stype}",
                defaults={
                    'description': description,
                    'confidence_score': Decimal(str(min(helpful_rate + 0.1, 0.95))),
                    'sample_size': total,
                    'applicable_to_suggestion_types': [stype],
                    'rule_adjustments': {
                        'feedback_analysis': True,
                        'suggestion_type': stype,
                        'helpful_feedback_count': len(feedback_data['helpful']),
                        'unhelpful_feedback_count': len(feedback_data['unhelpful']),
                        'helpful_rate': helpful_rate,
                    },
                    'is_active': True,
                }
            )
            insights_created += 1
        
        result = f"Feedback analysis: {insights_created} insights from {total_items} feedback items"
        logger.info(result)
        return result
        
    except Exception as e:
        logger.error(f"Feedback text analysis failed: {e}")
        raise


@shared_task(name='kanban.aggregate_org_learning')
def aggregate_org_learning_task():
    """
    Aggregate coaching insights across all boards in each organization
    to build OrganizationLearningProfile entries.
    
    Enables:
    - Cross-board collective intelligence
    - Cold-start bootstrapping for new boards
    - Organization-wide effectiveness metrics
    """
    from accounts.models import Organization
    from kanban.models import Board
    from kanban.coach_models import CoachingSuggestion, OrganizationLearningProfile
    from django.db.models import Count, Q, Avg
    from decimal import Decimal
    
    orgs_processed = 0
    profiles_updated = 0
    
    try:
        organizations = Organization.objects.all()
        
        for org in organizations:
            try:
                # Get all boards in this organization
                org_boards = Board.objects.filter(
                    organization=org,
                    is_archived=False,
                )
                
                if not org_boards.exists():
                    continue
                
                board_ids = list(org_boards.values_list('id', flat=True))
                
                # Get all suggestions across org boards with feedback
                org_suggestions = CoachingSuggestion.objects.filter(
                    board_id__in=board_ids,
                    was_helpful__isnull=False,
                )
                
                if org_suggestions.count() < 5:
                    continue
                
                orgs_processed += 1
                
                # Aggregate by suggestion_type
                type_stats = org_suggestions.values('suggestion_type').annotate(
                    total=Count('id'),
                    helpful=Count('id', filter=Q(was_helpful=True)),
                    acted=Count('id', filter=Q(
                        action_taken__in=['accepted', 'partially', 'modified']
                    )),
                    avg_conf=Avg('confidence_score'),
                    boards=Count('board', distinct=True),
                )
                
                for stat in type_stats:
                    stype = stat['suggestion_type']
                    total = stat['total']
                    helpful_rate = stat['helpful'] / total if total > 0 else 0
                    action_rate = stat['acted'] / total if total > 0 else 0
                    avg_conf = float(stat['avg_conf'] or 0.75)
                    
                    # Suppress if consistently unhelpful across org
                    should_suppress = (
                        total >= 20 and helpful_rate < 0.25 and action_rate < 0.15
                    )
                    
                    # Recommended confidence for new boards (cold start)
                    recommended_conf = avg_conf * helpful_rate if helpful_rate > 0 else 0.5
                    
                    # Per-severity effectiveness
                    severity_stats = org_suggestions.filter(
                        suggestion_type=stype
                    ).values('severity').annotate(
                        sev_total=Count('id'),
                        sev_helpful=Count('id', filter=Q(was_helpful=True)),
                    )
                    
                    severity_effectiveness = {}
                    for ss in severity_stats:
                        if ss['sev_total'] >= 3:
                            severity_effectiveness[ss['severity']] = round(
                                ss['sev_helpful'] / ss['sev_total'], 4
                            )
                    
                    OrganizationLearningProfile.objects.update_or_create(
                        organization=org,
                        suggestion_type=stype,
                        defaults={
                            'total_suggestions': total,
                            'total_feedback': total,
                            'helpful_rate': Decimal(str(round(helpful_rate, 4))),
                            'action_rate': Decimal(str(round(action_rate, 4))),
                            'avg_confidence': Decimal(str(round(avg_conf, 4))),
                            'boards_with_data': stat['boards'],
                            'recommended_confidence': Decimal(str(round(recommended_conf, 4))),
                            'should_suppress': should_suppress,
                            'severity_effectiveness': severity_effectiveness,
                        }
                    )
                    profiles_updated += 1
                    
            except Exception as org_err:
                logger.error(f"Error aggregating for org {org.name}: {org_err}")
        
        result = (
            f"Org learning aggregation: {profiles_updated} profiles updated "
            f"across {orgs_processed} organizations"
        )
        logger.info(result)
        return result
        
    except Exception as e:
        logger.error(f"Organization learning aggregation failed: {e}")
        raise


@shared_task(name='kanban.run_ab_experiments')
def run_ab_experiments_task():
    """
    Run A/B experiment analysis comparing AI generation methods.
    Calculates effectiveness metrics for rule-based vs AI vs hybrid suggestions
    at board and organization level. Runs weekly.
    """
    from kanban.models import Board
    from kanban.coach_models import AIExperimentResult
    from accounts.models import Organization
    
    experiments_calculated = 0
    errors = 0
    
    try:
        # Board-level experiments
        active_boards = Board.objects.filter(archived=False)
        for board in active_boards:
            try:
                results = AIExperimentResult.calculate_experiment_results(
                    board=board, days=30
                )
                experiments_calculated += len(results)
            except Exception as board_err:
                logger.error(
                    f"A/B experiment error for board {board.name}: {board_err}"
                )
                errors += 1
        
        # Organization-level experiments
        orgs = Organization.objects.all()
        for org in orgs:
            try:
                results = AIExperimentResult.calculate_experiment_results(
                    organization=org, days=30
                )
                experiments_calculated += len(results)
            except Exception as org_err:
                logger.error(
                    f"A/B experiment error for org {org.name}: {org_err}"
                )
                errors += 1
        
        result = (
            f"A/B experiments: {experiments_calculated} results calculated "
            f"({errors} errors)"
        )
        logger.info(result)
        return result
        
    except Exception as e:
        logger.error(f"A/B experiment task failed: {e}")
        raise
