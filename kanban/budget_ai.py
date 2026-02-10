"""
AI-Powered Budget Optimization Service
Uses Gemini to analyze budgets, predict overruns, and generate recommendations
"""
import json
import logging
from decimal import Decimal
from typing import Dict, List, Optional
from django.utils import timezone
from datetime import timedelta

logger = logging.getLogger(__name__)


class BudgetAIOptimizer:
    """
    AI-powered budget analysis and optimization using Gemini
    """
    
    def __init__(self, board):
        """
        Initialize with a board instance
        
        Args:
            board: Board instance to analyze
        """
        self.board = board
    
    def analyze_budget_health(self) -> Dict:
        """
        Comprehensive AI analysis of budget health with recommendations
        
        Returns:
            Dictionary with AI insights and recommendations
        """
        from kanban.budget_utils import BudgetAnalyzer
        
        # Gather data for AI analysis
        metrics = BudgetAnalyzer.calculate_project_metrics(self.board)
        
        if not metrics.get('has_budget'):
            return {'error': 'No budget configured for analysis'}
        
        roi_metrics = BudgetAnalyzer.calculate_roi_metrics(self.board)
        overruns = BudgetAnalyzer.identify_cost_overruns(self.board)
        burn_rate = BudgetAnalyzer.calculate_burn_rate(self.board)
        
        # Build AI analysis prompt
        prompt = self._build_budget_analysis_prompt(metrics, roi_metrics, overruns, burn_rate)
        
        # Get AI insights
        ai_response = self._call_gemini_api(prompt, task_type='complex')
        
        if not ai_response:
            return {'error': 'Failed to get AI analysis'}
        
        # Parse AI response and structure results
        results = self._parse_ai_response(ai_response, metrics)
        
        # Store AI analysis timestamp
        self._update_last_analysis_time()
        
        return results
    
    def generate_recommendations(self, context: Optional[Dict] = None) -> List[Dict]:
        """
        Generate AI-powered budget recommendations
        
        Args:
            context: Additional context for recommendations
            
        Returns:
            List of recommendation dictionaries
        """
        from kanban.budget_utils import BudgetAnalyzer
        from kanban.budget_models import BudgetRecommendation
        
        # Gather comprehensive data
        metrics = BudgetAnalyzer.calculate_project_metrics(self.board)
        overruns = BudgetAnalyzer.identify_cost_overruns(self.board)
        burn_rate = BudgetAnalyzer.calculate_burn_rate(self.board)
        cost_breakdown = BudgetAnalyzer.get_task_cost_breakdown(self.board)
        
        # Build recommendation prompt
        prompt = self._build_recommendation_prompt(metrics, overruns, burn_rate, cost_breakdown, context)
        
        # Get AI recommendations
        ai_response = self._call_gemini_api(prompt, task_type='complex')
        
        if not ai_response:
            return []
        
        # Parse and create recommendation objects
        recommendations = self._parse_recommendations(ai_response)
        
        # Save recommendations to database
        saved_recommendations = []
        for rec in recommendations:
            try:
                recommendation = BudgetRecommendation.objects.create(
                    board=self.board,
                    recommendation_type=rec.get('type', 'efficiency_improvement'),
                    title=rec.get('title', ''),
                    description=rec.get('description', ''),
                    estimated_savings=rec.get('estimated_savings'),
                    confidence_score=rec.get('confidence', 70),
                    priority=rec.get('priority', 'medium'),
                    ai_reasoning=rec.get('reasoning', ''),
                    based_on_patterns=rec.get('patterns', {}),
                )
                saved_recommendations.append({
                    'id': recommendation.id,
                    'type': recommendation.recommendation_type,
                    'title': recommendation.title,
                    'description': recommendation.description,
                    'estimated_savings': float(recommendation.estimated_savings) if recommendation.estimated_savings else None,
                    'confidence': recommendation.confidence_score,
                    'priority': recommendation.priority,
                })
            except Exception as e:
                logger.error(f"Error saving recommendation: {e}")
        
        return saved_recommendations
    
    def predict_cost_overrun(self) -> Dict:
        """
        Predict likelihood and magnitude of cost overruns using AI
        
        Returns:
            Dictionary with prediction results
        """
        from kanban.budget_utils import BudgetAnalyzer
        
        metrics = BudgetAnalyzer.calculate_project_metrics(self.board)
        burn_rate = BudgetAnalyzer.calculate_burn_rate(self.board)
        cost_breakdown = BudgetAnalyzer.get_task_cost_breakdown(self.board)
        
        # Build prediction prompt
        prompt = self._build_prediction_prompt(metrics, burn_rate, cost_breakdown)
        
        # Get AI prediction
        ai_response = self._call_gemini_api(prompt, task_type='complex')
        
        if not ai_response:
            return {'error': 'Failed to get prediction'}
        
        # Parse prediction
        prediction = self._parse_prediction(ai_response)
        
        return prediction
    
    def learn_cost_patterns(self) -> Dict:
        """
        Analyze historical data to identify cost patterns
        
        Returns:
            Dictionary with identified patterns
        """
        from kanban.budget_models import CostPattern, TimeEntry, TaskCost
        from django.db.models import Avg, Count, Sum
        
        # Analyze time entry patterns
        time_patterns = self._analyze_time_patterns()
        
        # Analyze task cost patterns
        cost_patterns = self._analyze_cost_patterns()
        
        # Build learning prompt
        prompt = self._build_pattern_learning_prompt(time_patterns, cost_patterns)
        
        # Get AI pattern analysis
        ai_response = self._call_gemini_api(prompt, task_type='complex')
        
        if not ai_response:
            return {'error': 'Failed to learn patterns'}
        
        # Parse and store patterns
        patterns = self._parse_patterns(ai_response)
        
        # Save patterns to database
        saved_patterns = []
        for pattern in patterns:
            try:
                cost_pattern, created = CostPattern.objects.update_or_create(
                    board=self.board,
                    pattern_name=pattern.get('name', 'Unknown Pattern'),
                    defaults={
                        'pattern_type': pattern.get('type', 'general'),
                        'pattern_data': pattern.get('data', {}),
                        'confidence': Decimal(str(pattern.get('confidence', 50))),
                        'occurrence_count': pattern.get('occurrences', 1),
                        'last_occurred': timezone.now(),
                    }
                )
                saved_patterns.append({
                    'name': cost_pattern.pattern_name,
                    'type': cost_pattern.pattern_type,
                    'confidence': float(cost_pattern.confidence),
                    'created': created,
                })
            except Exception as e:
                logger.error(f"Error saving pattern: {e}")
        
        return {
            'patterns_identified': len(saved_patterns),
            'patterns': saved_patterns,
        }
    
    def optimize_resource_allocation(self) -> Dict:
        """
        AI-powered resource allocation optimization
        
        Returns:
            Dictionary with optimization suggestions
        """
        from kanban.budget_utils import BudgetAnalyzer
        from kanban.models import Task
        
        metrics = BudgetAnalyzer.calculate_project_metrics(self.board)
        cost_breakdown = BudgetAnalyzer.get_task_cost_breakdown(self.board)
        
        # Get task details
        tasks = Task.objects.filter(column__board=self.board).select_related('assignee', 'column')
        task_data = []
        for task in tasks:
            task_info = {
                'id': task.id,
                'title': task.title,
                'priority': task.priority,
                'status': task.column.name,
                'assignee': task.assignee.username if task.assignee else None,
                'complexity': task.complexity_score if hasattr(task, 'complexity_score') else None,
            }
            task_data.append(task_info)
        
        # Build optimization prompt
        prompt = self._build_optimization_prompt(metrics, cost_breakdown, task_data)
        
        # Get AI optimization
        ai_response = self._call_gemini_api(prompt, task_type='complex')
        
        if not ai_response:
            return {'error': 'Failed to get optimization'}
        
        # Parse optimization suggestions
        optimization = self._parse_optimization(ai_response)
        
        return optimization
    
    def _build_budget_analysis_prompt(self, metrics: Dict, roi_metrics: Dict, 
                                     overruns: List, burn_rate: Dict) -> str:
        """Build prompt for budget health analysis"""
        prompt = f"""
You are a financial analyst AI specializing in project budget management. Analyze the following project budget data and provide comprehensive insights.

## Project Budget Overview
- Allocated Budget: {metrics['budget']['currency']} {metrics['budget']['allocated']:,.2f}
- Spent: {metrics['budget']['currency']} {metrics['budget']['spent']:,.2f}
- Remaining: {metrics['budget']['currency']} {metrics['budget']['remaining']:,.2f}
- Utilization: {metrics['budget']['utilization_percent']}%
- Status: {metrics['budget']['status']}

## Time Tracking
- Spent Hours: {metrics['time']['spent_hours']:.2f}
{'- Allocated Hours: ' + str(metrics['time']['allocated_hours']) if metrics['time']['allocated_hours'] else '- No time budget set'}
{'- Time Utilization: ' + str(metrics['time']['utilization_percent']) + '%' if metrics['time']['utilization_percent'] else ''}

## Cost Analysis
- Total Estimated Cost: {metrics['costs']['total_estimated']:,.2f}
- Total Actual Cost: {metrics['costs']['total_actual']:,.2f}
- Variance: {metrics['costs']['variance']:,.2f} ({metrics['costs']['variance_percent']:+.2f}%)

## Task Metrics
- Total Tasks: {metrics['tasks']['total']}
- Completed Tasks: {metrics['tasks']['completed']}
- Completion Rate: {metrics['tasks']['completion_rate']}%
- Cost per Completed Task: {metrics['tasks']['cost_per_completed_task']:,.2f}

## Burn Rate Analysis
- Daily Burn Rate: {burn_rate.get('daily_burn_rate', 0):,.2f}
- Days Remaining: {burn_rate.get('days_remaining', 0)}
- Projected End Date: {burn_rate.get('projected_end_date', 'Unknown')}
- Sustainable: {'Yes' if burn_rate.get('is_sustainable') else 'No'}

## Cost Overruns
{len(overruns)} tasks with cost overruns detected.
{'Top overruns: ' + ', '.join([f"{o['task_title']} (+{o['overrun_percent']:.1f}%)" for o in overruns[:3]]) if overruns else 'No overruns'}

## ROI Metrics
{'- Expected Value: ' + str(roi_metrics.get('expected_value', 'Not set')) if roi_metrics.get('expected_value') else ''}
{'- ROI: ' + str(roi_metrics['roi_percentage']) + '%' if roi_metrics.get('roi_percentage') else '- ROI: Not calculated'}

Please provide:
1. **Overall Health Assessment**: Rate the budget health (Excellent/Good/Concerning/Critical) and explain why
2. **Key Risks**: Identify 3-5 key financial risks
3. **Positive Indicators**: Highlight what's going well
4. **Immediate Actions**: 2-3 actions that should be taken immediately
5. **Trend Analysis**: Based on the data, what trends do you observe?

Format your response as JSON WITH FULL EXPLAINABILITY:
{{
    "confidence_score": 0.XX,
    "health_rating": "Excellent|Good|Concerning|Critical",
    "health_explanation": "Detailed explanation of why this rating was assigned",
    "health_factors": [
        {{
            "factor": "Factor name",
            "status": "positive|neutral|negative",
            "weight": "high|medium|low",
            "evidence": "Data supporting this assessment"
        }}
    ],
    "risks": [
        {{
            "risk": "Risk description",
            "severity": "critical|high|medium|low",
            "likelihood": "high|medium|low",
            "evidence": "What data indicates this risk",
            "potential_impact": "Financial/timeline impact if realized",
            "mitigation": "Suggested action to address"
        }}
    ],
    "positive_indicators": [
        {{
            "indicator": "What's going well",
            "evidence": "Data supporting this observation",
            "significance": "Why this matters"
        }}
    ],
    "immediate_actions": [
        {{
            "action": "Specific action to take",
            "rationale": "Why this action is needed now",
            "expected_outcome": "What improvement to expect",
            "owner_suggestion": "Who should own this action"
        }}
    ],
    "trends": [
        {{
            "trend": "Observed pattern",
            "direction": "improving|stable|declining",
            "evidence": "Data showing this trend",
            "forecast": "What to expect if trend continues"
        }}
    ],
    "analysis_assumptions": [
        "Key assumption made in this analysis"
    ],
    "analysis_limitations": [
        "What data would improve this analysis"
    ]
}}
"""
        return prompt
    
    def _build_recommendation_prompt(self, metrics: Dict, overruns: List, 
                                    burn_rate: Dict, cost_breakdown: List, 
                                    context: Optional[Dict]) -> str:
        """Build prompt for generating recommendations"""
        prompt = f"""
You are a project management AI consultant. Generate actionable budget optimization recommendations based on the following data.

## Current Situation
- Budget Status: {metrics['budget']['status']}
- Budget Utilization: {metrics['budget']['utilization_percent']}%
- Remaining Budget: {metrics['budget']['remaining']:,.2f}
- Daily Burn Rate: {burn_rate.get('daily_burn_rate', 0):,.2f}
- Days Remaining: {burn_rate.get('days_remaining', 0)}

## Problem Areas
- Tasks with overruns: {len(overruns)}
- Total overrun amount: {sum([o['overrun_amount'] for o in overruns]) if overruns else 0:,.2f}
- Completion rate: {metrics['tasks']['completion_rate']}%

## Task Cost Analysis
{len(cost_breakdown)} tasks analyzed. Top cost variances:
{', '.join([f"{t['task_title']}: {t['variance_percent']:+.1f}%" for t in cost_breakdown[:5]])}

{f"## Additional Context: {context}" if context else ""}

Generate 3-7 specific, actionable recommendations. For each recommendation:
1. Choose appropriate type: reallocation, scope_cut, timeline_change, resource_optimization, risk_mitigation, or efficiency_improvement
2. Provide clear title and detailed description
3. Estimate potential cost savings
4. Rate confidence (0-100)
5. Set priority (low/medium/high/urgent)
6. Explain AI reasoning with full transparency

Format as JSON array with objects containing FULL EXPLAINABILITY:
[
    {{
        "type": "recommendation_type",
        "title": "Clear recommendation title",
        "description": "Detailed description of the recommendation",
        "estimated_savings": 1000.00,
        "confidence": 85,
        "confidence_factors": [
            {{
                "factor": "What influences confidence",
                "direction": "increases|decreases",
                "explanation": "How this affects confidence"
            }}
        ],
        "priority": "low|medium|high|urgent",
        "priority_reasoning": "Why this priority level",
        "reasoning": "Detailed explanation of why this is recommended based on data",
        "implementation_steps": ["Step 1", "Step 2", "Step 3"],
        "risks_of_implementation": ["Risk 1"],
        "success_metrics": ["How to measure if this worked"],
        "patterns": {{
            "data_patterns_used": ["What patterns informed this recommendation"],
            "historical_support": "Any historical data supporting this"
        }},
        "alternative_approaches": [
            {{
                "alternative": "Alternative approach",
                "tradeoff": "What you gain/lose"
            }}
        ],
        "assumptions": ["Key assumption for this recommendation"]
    }}
]
"""
        return prompt
    
    def _build_prediction_prompt(self, metrics: Dict, burn_rate: Dict, 
                                cost_breakdown: List) -> str:
        """Build prompt for cost overrun prediction"""
        prompt = f"""
You are a predictive analytics AI. Predict cost overrun likelihood and magnitude.

## Current Data
- Budget: {metrics['budget']['allocated']:,.2f}
- Spent: {metrics['budget']['spent']:,.2f} ({metrics['budget']['utilization_percent']}%)
- Remaining: {metrics['budget']['remaining']:,.2f}
- Daily Burn: {burn_rate.get('daily_burn_rate', 0):,.2f}
- Completion: {metrics['tasks']['completion_rate']}%

## Cost Trends
- Estimated vs Actual Variance: {metrics['costs']['variance_percent']:+.2f}%
- Tasks over budget: {len([t for t in cost_breakdown if t['is_over_budget']])}

Based on current trends, predict:
1. Likelihood of going over budget (0-100%)
2. Predicted overrun amount
3. Expected overrun date
4. Key contributing factors
5. Confidence in prediction

Format as JSON WITH FULL EXPLAINABILITY:
{{
    "confidence_score": 0.XX,
    "overrun_likelihood": 75,
    "likelihood_reasoning": "Why this probability was calculated",
    "predicted_overrun_amount": 5000.00,
    "amount_calculation": "How the overrun amount was estimated",
    "expected_date": "YYYY-MM-DD",
    "date_calculation": "How the date was projected",
    "factors": [
        {{
            "factor": "Contributing factor",
            "contribution_percentage": 25,
            "evidence": "Data supporting this factor",
            "trajectory": "worsening|stable|improving"
        }}
    ],
    "confidence": 80,
    "confidence_factors": [
        {{
            "factor": "What affects prediction confidence",
            "direction": "increases|decreases",
            "explanation": "Why"
        }}
    ],
    "risk_level": "low|medium|high|critical",
    "risk_reasoning": "Why this risk level was assigned",
    "scenario_analysis": {{
        "best_case": {{
            "overrun_amount": 0,
            "probability": 20,
            "conditions": "What must happen for this scenario"
        }},
        "most_likely": {{
            "overrun_amount": 5000,
            "probability": 55,
            "conditions": "Expected conditions"
        }},
        "worst_case": {{
            "overrun_amount": 15000,
            "probability": 25,
            "conditions": "What could make this happen"
        }}
    }},
    "early_warning_indicators": [
        {{
            "indicator": "What to watch for",
            "threshold": "When to be concerned",
            "current_status": "Current value"
        }}
    ],
    "mitigation_opportunities": [
        {{
            "action": "Action to reduce overrun risk",
            "potential_savings": 2000,
            "feasibility": "high|medium|low"
        }}
    ],
    "assumptions": ["Key assumption in this prediction"],
    "limitations": ["What would improve prediction accuracy"]
}}
"""
        return prompt
    
    def _build_pattern_learning_prompt(self, time_patterns: Dict, cost_patterns: Dict) -> str:
        """Build prompt for pattern learning"""
        prompt = f"""
You are a machine learning AI analyzing cost patterns. Identify recurring patterns in project costs.

## Time Entry Patterns
{json.dumps(time_patterns, indent=2)}

## Cost Patterns
{json.dumps(cost_patterns, indent=2)}

Identify 3-5 meaningful patterns such as:
- Tasks that consistently go over budget
- Time periods with high/low productivity
- Task types with predictable costs
- Resource allocation inefficiencies
- Seasonal variations

For each pattern provide: name, type, description, confidence (0-100), occurrences, data (supporting metrics).

Format as JSON array.
"""
        return prompt
    
    def _build_optimization_prompt(self, metrics: Dict, cost_breakdown: List, 
                                  task_data: List) -> str:
        """Build prompt for resource optimization"""
        prompt = f"""
You are an optimization AI. Suggest resource allocation improvements.

## Current State
- Budget Status: {metrics['budget']['status']} ({metrics['budget']['utilization_percent']}%)
- {metrics['tasks']['total']} tasks, {metrics['tasks']['completed']} completed

## Cost Performance
{len([t for t in cost_breakdown if t['is_over_budget']])} tasks over budget
Average variance: {sum([t['variance_percent'] for t in cost_breakdown]) / len(cost_breakdown) if cost_breakdown else 0:.1f}%

## Active Tasks
{len([t for t in task_data if 'done' not in t['status'].lower()])} active tasks

Suggest optimizations for:
1. Task prioritization
2. Resource reallocation
3. Scope adjustments
4. Efficiency improvements

Format as JSON: {{"optimizations": array of {{area, suggestion, impact, effort}}, "prioritization": array of task_ids, "estimated_savings": number}}
"""
        return prompt
    
    def _get_ai_cache(self):
        """Get the AI cache manager."""
        try:
            from kanban_board.ai_cache import ai_cache_manager
            return ai_cache_manager
        except ImportError:
            return None
    
    def _call_gemini_api(self, prompt: str, task_type: str = 'complex', 
                         use_cache: bool = True, cache_operation: str = 'budget_analysis') -> Optional[str]:
        """
        Call Gemini API with the given prompt (with caching support)
        
        Args:
            prompt: The prompt to send
            task_type: 'simple' or 'complex'
            use_cache: Whether to use caching (default True)
            cache_operation: Operation type for TTL selection
            
        Returns:
            AI response text or None
        """
        # Create context ID for caching based on board
        context_id = f"board_{self.board.id}" if self.board else None
        
        # Try cache first
        ai_cache = self._get_ai_cache()
        if use_cache and ai_cache:
            cached = ai_cache.get(prompt, cache_operation, context_id)
            if cached:
                logger.debug(f"Budget AI cache HIT for operation: {cache_operation}")
                return cached
        
        try:
            import google.generativeai as genai
            from django.conf import settings
            
            if not hasattr(settings, 'GEMINI_API_KEY') or not settings.GEMINI_API_KEY:
                logger.error("GEMINI_API_KEY not configured")
                return None
            
            genai.configure(api_key=settings.GEMINI_API_KEY)
            
            # Use Gemini 2.5 Flash for complex financial analysis
            model_name = 'gemini-2.5-flash'
            model = genai.GenerativeModel(model_name)
            logger.debug(f"Using {model_name} for budget AI analysis")
            
            response = model.generate_content(prompt)
            
            if response and response.text:
                result = response.text
                # Cache the result
                if use_cache and ai_cache and result:
                    ai_cache.set(prompt, result, cache_operation, context_id)
                    logger.debug(f"Budget AI response cached for operation: {cache_operation}")
                return result
            return None
        except Exception as e:
            logger.error(f"Error calling Gemini API: {str(e)}")
            return None
    
    def _parse_ai_response(self, response: str, metrics: Dict) -> Dict:
        """Parse AI analysis response"""
        try:
            # Try to extract JSON from response
            response_clean = response.strip()
            if response_clean.startswith('```json'):
                response_clean = response_clean[7:]
            if response_clean.endswith('```'):
                response_clean = response_clean[:-3]
            response_clean = response_clean.strip()
            
            parsed = json.loads(response_clean)
            
            return {
                'analysis_date': timezone.now().isoformat(),
                'health_rating': parsed.get('health_rating', 'Unknown'),
                'health_explanation': parsed.get('health_explanation', ''),
                'risks': parsed.get('risks', []),
                'positive_indicators': parsed.get('positive_indicators', []),
                'immediate_actions': parsed.get('immediate_actions', []),
                'trends': parsed.get('trends', []),
                'metrics_summary': metrics,
            }
        except json.JSONDecodeError:
            logger.error("Failed to parse AI response as JSON")
            return {
                'analysis_date': timezone.now().isoformat(),
                'health_rating': 'Unknown',
                'raw_response': response,
                'error': 'Failed to parse AI response',
            }
    
    def _parse_recommendations(self, response: str) -> List[Dict]:
        """Parse AI recommendations response"""
        try:
            response_clean = response.strip()
            if response_clean.startswith('```json'):
                response_clean = response_clean[7:]
            if response_clean.endswith('```'):
                response_clean = response_clean[:-3]
            response_clean = response_clean.strip()
            
            recommendations = json.loads(response_clean)
            if isinstance(recommendations, dict) and 'recommendations' in recommendations:
                recommendations = recommendations['recommendations']
            
            return recommendations if isinstance(recommendations, list) else []
        except json.JSONDecodeError:
            logger.error("Failed to parse recommendations")
            return []
    
    def _parse_prediction(self, response: str) -> Dict:
        """Parse AI prediction response"""
        try:
            response_clean = response.strip()
            if response_clean.startswith('```json'):
                response_clean = response_clean[7:]
            if response_clean.endswith('```'):
                response_clean = response_clean[:-3]
            response_clean = response_clean.strip()
            
            return json.loads(response_clean)
        except json.JSONDecodeError:
            logger.error("Failed to parse prediction")
            return {'error': 'Failed to parse prediction'}
    
    def _parse_patterns(self, response: str) -> List[Dict]:
        """Parse pattern learning response"""
        try:
            response_clean = response.strip()
            if response_clean.startswith('```json'):
                response_clean = response_clean[7:]
            if response_clean.endswith('```'):
                response_clean = response_clean[:-3]
            response_clean = response_clean.strip()
            
            patterns = json.loads(response_clean)
            return patterns if isinstance(patterns, list) else []
        except json.JSONDecodeError:
            logger.error("Failed to parse patterns")
            return []
    
    def _parse_optimization(self, response: str) -> Dict:
        """Parse optimization response"""
        try:
            response_clean = response.strip()
            if response_clean.startswith('```json'):
                response_clean = response_clean[7:]
            if response_clean.endswith('```'):
                response_clean = response_clean[:-3]
            response_clean = response_clean.strip()
            
            return json.loads(response_clean)
        except json.JSONDecodeError:
            logger.error("Failed to parse optimization")
            return {'error': 'Failed to parse optimization'}
    
    def _analyze_time_patterns(self) -> Dict:
        """Analyze time entry patterns"""
        from kanban.budget_models import TimeEntry
        from django.db.models import Avg, Sum, Count
        from django.db.models.functions import ExtractWeekDay, ExtractHour
        
        entries = TimeEntry.objects.filter(task__column__board=self.board)
        
        if not entries.exists():
            return {'no_data': True}
        
        # Average hours per day of week
        # Daily average
        daily_avg = entries.values('work_date').annotate(
            total=Sum('hours_spent')
        ).aggregate(avg=Avg('total'))
        
        # User productivity
        user_stats = entries.values('user__username').annotate(
            total_hours=Sum('hours_spent'),
            entry_count=Count('id'),
            avg_hours=Avg('hours_spent')
        ).order_by('-total_hours')[:10]
        
        return {
            'daily_average': float(daily_avg['avg'] or 0),
            'total_entries': entries.count(),
            'top_contributors': list(user_stats),
        }
    
    def _analyze_cost_patterns(self) -> Dict:
        """Analyze task cost patterns"""
        from kanban.budget_models import TaskCost
        from django.db.models import Avg, Count, Q
        
        costs = TaskCost.objects.filter(task__column__board=self.board)
        
        if not costs.exists():
            return {'no_data': True}
        
        # Variance statistics
        over_budget_count = sum([1 for tc in costs if tc.is_over_budget()])
        variances = [tc.get_cost_variance_percent() for tc in costs]
        avg_variance = sum(variances) / len(variances) if variances else 0
        
        return {
            'total_tasks_with_costs': costs.count(),
            'over_budget_count': over_budget_count,
            'over_budget_rate': (over_budget_count / costs.count() * 100) if costs.count() > 0 else 0,
            'average_variance_percent': avg_variance,
        }
    
    def _update_last_analysis_time(self):
        """Update the last AI analysis timestamp"""
        try:
            from kanban.budget_models import ProjectBudget
            budget = ProjectBudget.objects.get(board=self.board)
            budget.last_ai_analysis = timezone.now()
            budget.save(update_fields=['last_ai_analysis'])
        except Exception as e:
            logger.error(f"Error updating last analysis time: {e}")
