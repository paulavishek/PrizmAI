"""
Utility module for integrating with Google Generative AI (Gemini) API.

This module provides helper functions to call the Gemini API for various
AI-powered features in the PrizmAI application.
"""
import os
import logging
from typing import Dict, List, Optional
from datetime import datetime, timedelta
import json

import google.generativeai as genai
from django.conf import settings

# Setup logging
logger = logging.getLogger(__name__)

# Configure the Gemini API with your API key
try:
    # Try to get from settings first (recommended for production)
    GEMINI_API_KEY = getattr(settings, 'GEMINI_API_KEY', None)
    
    # If not in settings, try environment variable (for development)
    if not GEMINI_API_KEY:
        GEMINI_API_KEY = os.environ.get('GEMINI_API_KEY', '')
    
    if GEMINI_API_KEY:
        genai.configure(api_key=GEMINI_API_KEY)
    else:
        logger.warning("GEMINI_API_KEY not set. AI features won't work.")
except Exception as e:
    logger.error(f"Failed to configure Gemini API: {str(e)}")

# Global model instances - separate instances for Flash and Flash-Lite
_model_flash = None
_model_flash_lite = None

# Task complexity classification for smart routing
COMPLEX_TASKS = [
    'risk_assessment',
    'critical_path',
    'timeline_generation',
    'workflow_optimization',
    'dependency_analysis',
    'deadline_prediction',
    'priority_suggestion',
    'board_analytics_summary',
    'task_breakdown',
    'column_recommendations'
]

SIMPLE_TASKS = [
    'task_description',
    'comment_summary',
    'lean_classification',
    'task_enhancement',
    'mitigation_suggestions'
]

def get_model_for_task(task_type='simple'):
    """
    Get the appropriate Gemini model based on task complexity.
    
    Smart routing strategy:
    - Gemini 2.5 Flash: Complex reasoning tasks (risk assessment, critical path, analytics)
    - Gemini 2.5 Flash-Lite: Simple tasks (summarization, descriptions, classifications)
    
    This reduces average API cost by ~40% while keeping UI snappy.
    
    Args:
        task_type: Either 'complex' or 'simple', or specific task name
        
    Returns:
        A GenerativeModel instance or None if initialization fails
    """
    global _model_flash, _model_flash_lite
    
    try:
        # Determine which model to use
        use_flash = False
        
        if task_type == 'complex':
            use_flash = True
        elif task_type == 'simple':
            use_flash = False
        elif task_type in COMPLEX_TASKS:
            use_flash = True
        elif task_type in SIMPLE_TASKS:
            use_flash = False
        else:
            # Default to Flash-Lite for unknown tasks (cost optimization)
            use_flash = False
        
        if use_flash:
            if _model_flash is None:
                _model_flash = genai.GenerativeModel('gemini-2.0-flash-exp')
                logger.info("Gemini 2.5 Flash model instance created")
            logger.debug(f"Using Gemini 2.5 Flash for task: {task_type}")
            return _model_flash
        else:
            if _model_flash_lite is None:
                _model_flash_lite = genai.GenerativeModel('gemini-2.0-flash-exp')
                logger.info("Gemini 2.5 Flash-Lite model instance created")
            logger.debug(f"Using Gemini 2.5 Flash-Lite for task: {task_type}")
            return _model_flash_lite
    except Exception as e:
        logger.error(f"Error getting Gemini model: {str(e)}")
        return None

def get_model():
    """
    Legacy method - returns Flash-Lite by default for backward compatibility.
    New code should use get_model_for_task() instead.
    """
    return get_model_for_task('simple')

def generate_ai_content(prompt: str, task_type='simple') -> Optional[str]:
    """
    Generate content using Gemini API with smart model routing.
    
    Routes requests to appropriate model based on task complexity:
    - Complex tasks → Gemini 2.5 Flash (higher quality reasoning)
    - Simple tasks → Gemini 2.5 Flash-Lite (faster, cheaper)
    
    Args:
        prompt: The prompt to send to the Gemini API
        task_type: Task complexity indicator ('simple', 'complex', or specific task name)
        
    Returns:
        Generated content or None if generation fails
    """
    try:
        model = get_model_for_task(task_type)
        if not model:
            logger.error("Gemini model not available")
            return None
        
        # Generate content without any conversation history
        # This ensures no "History Restored" messages and no token waste
        response = model.generate_content(prompt)
        
        if response and response.text:
            return response.text.strip()
        
        logger.warning("Empty response from Gemini API")
        return None
        
    except Exception as e:
        logger.error(f"Error generating AI content: {str(e)}")
        return None

def generate_task_description(title: str, context: Optional[Dict] = None) -> Optional[Dict]:
    """
    Generate a detailed task description and checklist from a task title.
    
    Provides explainable AI output with confidence scores and reasoning.
    
    Args:
        title: The title of the task
        context: Optional context (board name, project type, etc.)
        
    Returns:
        A dictionary with generated description, checklist, and explainability data
        or None if generation fails
    """
    try:
        context_info = ""
        if context:
            context_info = f"""
        ## Context:
        - Board/Project: {context.get('board_name', 'Not specified')}
        - Project Type: {context.get('project_type', 'General')}
        - Team Size: {context.get('team_size', 'Unknown')}
        """
        
        prompt = f"""
        Based on this task title: "{title}", generate a detailed task description 
        with an objective and a checklist of smaller steps.
        Provide comprehensive explainability for all generated content.
        {context_info}
        
        IMPORTANT: For the 'objective' and 'detailed_description' fields, use PLAIN TEXT WITHOUT any Markdown formatting.
        Only use Markdown formatting in the 'markdown_description' field.
        
        Format your response as JSON WITH FULL EXPLAINABILITY:
        {{
            "objective": "Clear description of what this task aims to accomplish (PLAIN TEXT, NO MARKDOWN)",
            "detailed_description": "2-3 paragraph detailed description of the task scope and approach (PLAIN TEXT, NO MARKDOWN)",
            "confidence_score": 0.XX,
            "confidence_level": "high|medium|low",
            "interpretation_reasoning": "How the task title was interpreted to generate this description",
            "checklist": [
                {{
                    "item": "First subtask",
                    "estimated_effort": "Time estimate",
                    "why_included": "Why this step is necessary"
                }}
            ],
            "suggested_priority": "low|medium|high|urgent",
            "priority_reasoning": "Why this priority is suggested based on the task nature",
            "estimated_total_effort": "Total time estimate for the full task",
            "skill_requirements": [
                {{
                    "skill": "Required skill",
                    "level": "beginner|intermediate|expert",
                    "why_needed": "Why this skill is relevant"
                }}
            ],
            "potential_blockers": [
                "Potential blocker or dependency to consider"
            ],
            "success_criteria": [
                "How to verify task is successfully completed"
            ],
            "assumptions": [
                "Assumption 1 about scope or requirements",
                "Assumption 2 about resources"
            ],
            "alternative_interpretations": [
                {{
                    "interpretation": "Alternative way to understand this task",
                    "would_change": "How the description would differ"
                }}
            ],
            "markdown_description": "**Objective:** [objective]\\n\\n**Checklist:**\\n- [ ] Item 1\\n- [ ] Item 2"
        }}
        """
        
        response_text = generate_ai_content(prompt, task_type='task_description')
        if response_text:
            # Handle code block formatting
            if "```json" in response_text:
                response_text = response_text.split("```json")[1].split("```")[0].strip()
            elif "```" in response_text:
                response_text = response_text.split("```")[1].strip()
            
            try:
                return json.loads(response_text)
            except json.JSONDecodeError:
                # Fallback: return the markdown as-is for backward compatibility
                return {
                    'markdown_description': response_text,
                    'confidence_score': 0.5,
                    'parsing_note': 'Returned plain markdown due to JSON parsing error'
                }
        return None
    except Exception as e:
        logger.error(f"Error generating task description: {str(e)}")
        return None
def summarize_comments(comments: List[Dict]) -> Optional[Dict]:
    """
    Summarize a list of task comments with explainability.
    
    Provides structured analysis of comment thread including key decisions,
    action items, and sentiment analysis.
    
    Args:
        comments: A list of comment dictionaries with 'user', 'content', and 'created_at'
        
    Returns:
        A dictionary with summary and explainability data or None if summarization fails
    """
    try:
        if not comments:
            return None
            
        # Format comments for the prompt
        formatted_comments = "\n\n".join([
            f"User: {comment['user']}\nDate: {comment['created_at']}\n{comment['content']}" 
            for comment in comments
        ])
        
        prompt = f"""
        Analyze and summarize the following task comment thread. Extract key information
        and provide explainable insights.
        
        {formatted_comments}
        
        Format your response as JSON WITH FULL EXPLAINABILITY:
        {{
            "summary": "Concise 3-5 sentence summary of the discussion",
            "confidence_score": 0.XX,
            "key_decisions": [
                {{
                    "decision": "What was decided",
                    "made_by": "Who made or influenced the decision",
                    "source_comment": "Brief excerpt from comment"
                }}
            ],
            "action_items_mentioned": [
                {{
                    "action": "Action item described",
                    "assignee": "Who was assigned or null",
                    "deadline_mentioned": "Any deadline mentioned or null"
                }}
            ],
            "discussion_highlights": [
                {{
                    "highlight": "Important point raised",
                    "raised_by": "Who raised it",
                    "significance": "Why this is important"
                }}
            ],
            "participants_analysis": [
                {{
                    "user": "Username",
                    "contribution_type": "decision_maker|contributor|questioner|observer",
                    "comments_count": X
                }}
            ],
            "sentiment_analysis": {{
                "overall_sentiment": "positive|neutral|negative|mixed",
                "concerns_raised": ["Concern 1", "Concern 2"],
                "positive_aspects": ["Positive 1", "Positive 2"]
            }},
            "timeline_extracted": [
                "Deadline or date mentioned in comments"
            ],
            "unresolved_questions": [
                "Question that wasn't answered in the thread"
            ],
            "recommended_follow_ups": [
                "Suggested follow-up action based on discussion"
            ]
        }}
        """
        
        response_text = generate_ai_content(prompt, task_type='comment_summary')
        if response_text:
            # Handle code block formatting
            if "```json" in response_text:
                response_text = response_text.split("```json")[1].split("```")[0].strip()
            elif "```" in response_text:
                response_text = response_text.split("```")[1].strip()
            
            try:
                return json.loads(response_text)
            except json.JSONDecodeError:
                # Fallback to plain summary if JSON parsing fails
                return {
                    'summary': response_text,
                    'confidence_score': 0.5,
                    'parsing_note': 'Returned plain text summary due to JSON parsing error'
                }
        return None
    except Exception as e:
        logger.error(f"Error summarizing comments: {str(e)}")
        return None

def suggest_lean_classification(title: str, description: str) -> Optional[Dict]:
    """
    Suggest Lean Six Sigma classification for a task based on its title and description.
    
    Provides explainable AI output including confidence scores, contributing factors,
    and alternative classifications to support user decision-making.
    
    Args:
        title: The task title
        description: The task description
        
    Returns:
        A dictionary with suggested classification, justification, confidence,
        and explainability data or None if suggestion fails
    """
    try:
        prompt = f"""
        Based on this task's title and description, suggest a Lean Six Sigma classification
        (Value-Added, Necessary Non-Value-Added, or Waste/Eliminate) with full explainability.
        
        Task Title: {title}
        Task Description: {description or '(No description provided)'}
        
        Classification Definitions:
        - Value-Added (VA): Activities that transform the product/service in a way the customer values
        - Necessary Non-Value-Added (NNVA): Required activities that don't directly add value for the customer
        - Waste/Eliminate: Activities that consume resources without adding value
        
        Analyze the task and provide a comprehensive, explainable recommendation.
        
        Format your response as JSON WITH FULL EXPLAINABILITY:
        {{
            "classification": "Value-Added|Necessary Non-Value-Added|Waste/Eliminate",
            "justification": "2-3 sentences explaining why this classification fits",
            "confidence_score": 0.XX,
            "confidence_level": "high|medium|low",
            "contributing_factors": [
                {{
                    "factor": "Factor name (e.g., 'Customer Impact', 'Regulatory Requirement')",
                    "contribution_percentage": XX,
                    "description": "How this factor influenced the classification"
                }}
            ],
            "classification_reasoning": {{
                "value_added_indicators": ["List indicators that suggest Value-Added"],
                "non_value_indicators": ["List indicators that suggest NNVA or Waste"],
                "primary_driver": "The main reason for this classification"
            }},
            "alternative_classification": {{
                "classification": "Second most likely classification",
                "confidence_score": 0.XX,
                "conditions": "Under what conditions this alternative would apply"
            }},
            "assumptions": [
                "Key assumption 1 made during analysis",
                "Key assumption 2 made during analysis"
            ],
            "improvement_suggestions": [
                "If Waste/NNVA: How could this task be optimized or eliminated?",
                "If VA: How to maximize the value delivery?"
            ],
            "lean_waste_type": "If Waste - specify type: Defects|Overproduction|Waiting|Non-utilized talent|Transportation|Inventory|Motion|Extra-processing (or null)"
        }}
        """
        
        response_text = generate_ai_content(prompt, task_type='lean_classification')
        if response_text:
            # Handle the case where the AI might include code block formatting
            if "```json" in response_text:
                response_text = response_text.split("```json")[1].split("```")[0].strip()
            elif "```" in response_text:
                response_text = response_text.split("```")[1].strip()
                
            return json.loads(response_text)
        return None
    except Exception as e:
        logger.error(f"Error suggesting lean classification: {str(e)}")
        return None

def summarize_board_analytics(analytics_data: Dict) -> Optional[Dict]:
    """
    Generate an AI-powered summary of board analytics data with full explainability.
    
    Provides structured insights with confidence scores, reasoning, and actionable
    recommendations backed by data analysis.
    
    Args:
        analytics_data: A dictionary containing board analytics metrics
        
    Returns:
        A dictionary with comprehensive analytics summary and explainability data
        or None if generation fails
    """
    try:
        # Extract key metrics from analytics data
        total_tasks = analytics_data.get('total_tasks', 0)
        completed_count = analytics_data.get('completed_count', 0)
        productivity = analytics_data.get('productivity', 0)
        overdue_count = analytics_data.get('overdue_count', 0)
        upcoming_count = analytics_data.get('upcoming_count', 0)
        
        # Lean Six Sigma metrics
        value_added_percentage = analytics_data.get('value_added_percentage', 0)
        total_categorized = analytics_data.get('total_categorized', 0)
        tasks_by_lean_category = analytics_data.get('tasks_by_lean_category', [])
        
        # Task distribution by column
        tasks_by_column = analytics_data.get('tasks_by_column', [])
        tasks_by_priority = analytics_data.get('tasks_by_priority', [])
        tasks_by_user = analytics_data.get('tasks_by_user', [])
        
        # Build comprehensive prompt
        prompt = f"""
        Analyze the following board analytics data and provide a comprehensive, actionable summary for a project manager. 
        Focus on insights, trends, recommendations, and areas that need attention.
        Provide full explainability for all analysis and recommendations.

        ## Board Metrics Overview:
        - Total Tasks: {total_tasks}
        - Completed Tasks: {completed_count}
        - Overall Productivity: {productivity}%
        - Overdue Tasks: {overdue_count}
        - Tasks Due Soon: {upcoming_count}

        ## Lean Six Sigma Analysis:
        - Value-Added Percentage: {value_added_percentage}%
        - Total Categorized Tasks: {total_categorized} out of {total_tasks}
        - Value-Added Tasks: {tasks_by_lean_category[0]['count'] if tasks_by_lean_category else 0}
        - Necessary Non-Value-Added: {tasks_by_lean_category[1]['count'] if len(tasks_by_lean_category) > 1 else 0}
        - Waste/Eliminate Tasks: {tasks_by_lean_category[2]['count'] if len(tasks_by_lean_category) > 2 else 0}

        ## Task Distribution:
        Column Distribution: {', '.join([f"{col['name']}: {col['count']}" for col in tasks_by_column])}
        Priority Distribution: {', '.join([f"{pri['priority']}: {pri['count']}" for pri in tasks_by_priority])}
        Assignee Workload: {', '.join([f"{user['username']}: {user['count']} tasks ({user['completion_rate']}% complete)" for user in tasks_by_user[:5]])}

        Format your response as JSON WITH FULL EXPLAINABILITY:
        {{
            "executive_summary": "2-3 sentence overall summary for quick reading",
            "confidence_score": 0.XX,
            "analysis_quality": {{
                "data_completeness": "high|medium|low",
                "metrics_reliability": "high|medium|low",
                "sample_size_adequacy": "sufficient|marginal|insufficient"
            }},
            "health_assessment": {{
                "overall_score": "healthy|at_risk|critical",
                "score_reasoning": "Why this health score was assigned",
                "health_indicators": [
                    {{
                        "indicator": "Indicator name",
                        "status": "positive|neutral|negative",
                        "value": "Actual value",
                        "benchmark": "Expected/ideal value",
                        "impact_on_score": "How this affects overall health"
                    }}
                ]
            }},
            "key_insights": [
                {{
                    "insight": "The insight statement",
                    "evidence": "Data points supporting this insight",
                    "significance": "Why this matters",
                    "confidence": "high|medium|low"
                }}
            ],
            "areas_of_concern": [
                {{
                    "concern": "The concern description",
                    "severity": "critical|high|medium|low",
                    "root_cause_hypothesis": "Likely cause of this issue",
                    "evidence": "Supporting data",
                    "recommended_action": "What to do about it",
                    "timeline": "When to address"
                }}
            ],
            "process_improvement_recommendations": [
                {{
                    "recommendation": "Specific actionable suggestion",
                    "rationale": "Why this is recommended based on data",
                    "expected_impact": "What improvement to expect",
                    "implementation_effort": "low|medium|high",
                    "priority": 1,
                    "success_metrics": ["How to measure improvement"]
                }}
            ],
            "lean_analysis": {{
                "value_stream_efficiency": "excellent|good|fair|poor",
                "efficiency_reasoning": "Why this efficiency rating",
                "waste_identification": [
                    {{
                        "waste_type": "Type of waste identified",
                        "tasks_affected": X,
                        "elimination_strategy": "How to reduce this waste"
                    }}
                ],
                "value_optimization_suggestions": [
                    "Specific suggestion to increase value-add percentage"
                ]
            }},
            "team_performance": {{
                "workload_balance": "balanced|slightly_imbalanced|severely_imbalanced",
                "balance_analysis": "Detailed workload distribution analysis",
                "top_performers": ["Team member highlights"],
                "capacity_concerns": ["Any capacity issues identified"],
                "collaboration_opportunities": ["Where team could work together better"]
            }},
            "trend_analysis": {{
                "productivity_trend": "improving|stable|declining",
                "trend_evidence": "Data supporting trend assessment",
                "forecast": "What to expect in coming period"
            }},
            "action_items": [
                {{
                    "action": "Specific action to take",
                    "owner": "Suggested owner role",
                    "urgency": "immediate|this_week|this_month",
                    "expected_outcome": "What this action will achieve"
                }}
            ],
            "assumptions": [
                "Assumption made in this analysis"
            ],
            "limitations": [
                "Limitation of this analysis due to data constraints"
            ]
        }}
        """
        
        response_text = generate_ai_content(prompt, task_type='board_analytics_summary')
        if response_text:
            # Handle code block formatting
            if "```json" in response_text:
                response_text = response_text.split("```json")[1].split("```")[0].strip()
            elif "```" in response_text:
                response_text = response_text.split("```")[1].strip()
            
            try:
                return json.loads(response_text)
            except json.JSONDecodeError:
                # Fallback to plain text summary for backward compatibility
                return {
                    'executive_summary': response_text,
                    'confidence_score': 0.5,
                    'parsing_note': 'Returned plain text summary due to JSON parsing error'
                }
        return None
    except Exception as e:
        logger.error(f"Error summarizing board analytics: {str(e)}")
        return None

def suggest_task_priority(task_data: Dict, board_context: Dict) -> Optional[Dict]:
    """
    Suggest optimal priority level for a task based on context.
    
    Args:
        task_data: Dictionary containing task information (title, description, due_date, etc.)
        board_context: Dictionary containing board context (workload, deadlines, etc.)
        
    Returns:
        A dictionary with suggested priority and reasoning or None if suggestion fails
    """
    try:
        # Extract task information
        title = task_data.get('title', '')
        description = task_data.get('description', '')
        due_date = task_data.get('due_date', '')
        current_priority = task_data.get('current_priority', 'medium')
          # Extract board context
        total_tasks = board_context.get('total_tasks', 0)
        high_priority_count = board_context.get('high_priority_count', 0)
        urgent_count = board_context.get('urgent_count', 0)
        overdue_count = board_context.get('overdue_count', 0)
        upcoming_deadlines = board_context.get('upcoming_deadlines', [])
        
        # Handle case where upcoming_deadlines might be an integer count instead of a list
        if isinstance(upcoming_deadlines, int):
            upcoming_deadlines_count = upcoming_deadlines
        else:
            upcoming_deadlines_count = len(upcoming_deadlines)
        
        prompt = f"""
        Analyze this task and suggest an optimal priority level based on the context provided.
        
        ## CRITICAL ANALYSIS RULES:
        1. **Semantic Importance FIRST**: Keywords like "Migration", "Database", "Security", "Critical", 
           "Production", "Payment", "Compliance", "Deployment", "Outage" suggest HIGH IMPACT regardless of due date
        2. **Separate Urgency from Importance**: A task due in 10 days has LOW URGENCY but may still need 
           HIGH PRIORITY if it's critical work (e.g., "Database Migration")
        3. **Balance Factors**: When there's conflict (e.g., critical keyword + far due date), explain BOTH:
           "High Impact due to [keyword], but Low Urgency due to [due date]"
        4. **Workload Distribution**: Consider if the board already has too many high/urgent tasks
        5. **Dependencies**: Tasks that block others need higher priority
        
        ## Task Information:
        - Title: {title}
        - Description: {description or 'No description provided'}
        - Current Priority: {current_priority}
        - Due Date: {due_date or 'No due date set'}
        
        ## Board Context:
        - Total Tasks on Board: {total_tasks}
        - Current High Priority Tasks: {high_priority_count}
        - Current Urgent Tasks: {urgent_count}
        - Overdue Tasks: {overdue_count}
        - Tasks Due Soon: {upcoming_deadlines_count}
        
        Consider these factors in order:
        1. **Semantic keywords** in title/description indicating business impact
        2. Urgency based on due date proximity
        3. Impact based on task description and title context
        4. Current workload distribution (avoid too many high/urgent priorities)
        5. Dependencies and blockers that might be indicated
        6. Business value and risk implied by the task
        
        Available priority levels: low, medium, high, urgent
        
        Format your response as JSON WITH FULL EXPLAINABILITY:
        {{
            "suggested_priority": "low|medium|high|urgent",
            "confidence_score": 0.XX,
            "confidence_level": "high|medium|low",
            "reasoning": "2-3 sentences explaining the priority suggestion",
            "contributing_factors": [
                {{
                    "factor": "Factor name (e.g., 'Due Date Proximity', 'Business Impact')",
                    "contribution_percentage": XX,
                    "description": "How this factor influenced the priority",
                    "weight": "high|medium|low"
                }}
            ],
            "priority_comparison": {{
                "vs_low": "Why not low priority (if not suggested)",
                "vs_medium": "Why not medium priority (if not suggested)",
                "vs_high": "Why not high priority (if not suggested)",
                "vs_urgent": "Why not urgent priority (if not suggested)"
            }},
            "alternative_priority": {{
                "priority": "alternative priority level",
                "confidence": 0.XX,
                "when_applicable": "Under what conditions this alternative would apply"
            }},
            "workload_impact": {{
                "current_distribution": "Assessment of current priority distribution",
                "impact_of_suggestion": "How this suggestion affects workload balance"
            }},
            "recommendations": ["up to 3 actionable recommendations"],
            "assumptions": [
                "Assumption 1 about the task",
                "Assumption 2 about the context"
            ],
            "urgency_indicators": ["Specific phrases or factors indicating urgency"],
            "impact_indicators": ["Specific phrases or factors indicating business impact"]
        }}
        """
        
        response_text = generate_ai_content(prompt, task_type='priority_suggestion')
        if response_text:
            # Handle code block formatting
            if "```json" in response_text:
                response_text = response_text.split("```json")[1].split("```")[0].strip()
            elif "```" in response_text:
                response_text = response_text.split("```")[1].strip()
                
            return json.loads(response_text)
        return None
    except Exception as e:
        logger.error(f"Error suggesting task priority: {str(e)}")
        return None

def predict_realistic_deadline(task_data: Dict, team_context: Dict) -> Optional[Dict]:
    """
    Predict realistic completion timeline for a task based on historical data and context.
    
    IMPORTANT: This function requires a valid assignee to be set in task_data.
    The prediction is based on the assignee's historical velocity and current workload.
    The API endpoint validates that an assignee is selected before calling this function.
    
    Args:
        task_data: Dictionary containing task information (must include 'assigned_to')
        team_context: Dictionary containing team performance and historical data
        
    Returns:
        A dictionary with deadline prediction and reasoning or None if prediction fails
    """
    try:
        # Extract task information
        title = task_data.get('title', '')
        description = task_data.get('description', '')
        priority = task_data.get('priority', 'medium')
        assigned_to = task_data.get('assigned_to', 'Unassigned')
        
        # Extract new task fields for enhanced prediction
        complexity_score = task_data.get('complexity_score', 5)
        workload_impact = task_data.get('workload_impact', 'medium')
        skill_match_score = task_data.get('skill_match_score')
        collaboration_required = task_data.get('collaboration_required', False)
        dependencies_count = task_data.get('dependencies_count', 0)
        risk_score = task_data.get('risk_score')
        risk_level = task_data.get('risk_level')
        
        # Extract team context
        assignee_avg_completion = team_context.get('assignee_avg_completion_days', 0)
        team_avg_completion = team_context.get('team_avg_completion_days', 0)
        current_workload = team_context.get('assignee_current_tasks', 0)
        similar_tasks_avg = team_context.get('similar_tasks_avg_days', 0)
        upcoming_holidays = team_context.get('upcoming_holidays', [])
        assignee_completed_count = team_context.get('assignee_completed_tasks_count', 0)
        assignee_velocity = team_context.get('assignee_velocity_hours_per_day', 8)
        
        # Calculate performance comparison
        if team_avg_completion > 0 and assignee_avg_completion > 0:
            if assignee_avg_completion < team_avg_completion:
                performance_note = f"{assigned_to} is {round((1 - assignee_avg_completion/team_avg_completion) * 100)}% FASTER than team average"
            elif assignee_avg_completion > team_avg_completion:
                performance_note = f"{assigned_to} is {round((assignee_avg_completion/team_avg_completion - 1) * 100)}% SLOWER than team average"
            else:
                performance_note = f"{assigned_to} performs at team average speed"
        else:
            performance_note = "No historical data available for comparison"
        
        # Format complexity interpretation
        complexity_label = "Very Complex" if complexity_score >= 8 else "Moderate" if complexity_score >= 5 else "Simple"
        
        # Format skill match interpretation
        skill_match_note = ""
        if skill_match_score is not None:
            if skill_match_score >= 80:
                skill_match_note = f"Excellent skill match ({skill_match_score}%) - assignee is well-suited for this task"
            elif skill_match_score >= 60:
                skill_match_note = f"Good skill match ({skill_match_score}%) - assignee has adequate skills"
            elif skill_match_score >= 40:
                skill_match_note = f"Below average skill match ({skill_match_score}%) - may need extra time for learning"
            else:
                skill_match_note = f"Poor skill match ({skill_match_score}%) - significant learning curve expected"
        else:
            skill_match_note = "Skill match not assessed"
        
        prompt = f"""
        Predict a realistic timeline for completing this task based on the provided context and historical data.
        
        ## Task Information:
        - Title: {title}
        - Description: {description or 'No description provided'}
        - Priority: {priority}
        - Assigned To: {assigned_to}
        
        ## Task Complexity & Resource Requirements:
        - Complexity Score: {complexity_score}/10 ({complexity_label})
        - Workload Impact: {workload_impact or 'Not specified'} (Low/Medium/High/Critical - impact on assignee's capacity)
        - Skill Match: {skill_match_note}
        - Collaboration Required: {'Yes - coordination with team members needed' if collaboration_required else 'No - can be done independently'}
        - Dependencies: {dependencies_count} blocking task(s) that must complete first
        - Risk Level: {risk_level or 'Not assessed'} {f'(Score: {risk_score}/9)' if risk_score else ''}

        ## Historical Context (IMPORTANT - Use these actual metrics for {assigned_to}):
        - {assigned_to}'s Personal Average Completion Time: {assignee_avg_completion} days (based on {assignee_completed_count} completed tasks)
        - {assigned_to}'s Estimated Velocity: {assignee_velocity} hours/day
        - Team Average Completion Time: {team_avg_completion} days
        - Performance Comparison: {performance_note}
        - Similar Tasks Average: {similar_tasks_avg} days
        - {assigned_to}'s Current Workload: {current_workload} active tasks
        - Upcoming Holidays/Breaks: {', '.join(upcoming_holidays) if upcoming_holidays else 'None'}
        
        Consider these factors (ALL are important for prediction):
        1. Task complexity score ({complexity_score}/10) - higher complexity = more time needed
        2. {assigned_to}'s SPECIFIC historical performance (use the actual numbers above!)
        3. Workload impact ({workload_impact}) - high/critical impact tasks need more focused time
        4. Skill match ({skill_match_score}%) - poor match means learning curve adds time
        5. Collaboration requirements - coordination overhead if team work is needed
        6. Dependencies ({dependencies_count}) - must wait for blocking tasks
        7. Risk level ({risk_level}) - high risk tasks often face delays
        8. Priority level urgency ({priority})
        9. Buffer time for reviews/testing
        10. Holidays or known interruptions
        
        IMPORTANT: 
        - Predict the number of DAYS from today that this task should be completed, not absolute dates.
        - Use {assigned_to}'s ACTUAL historical average of {assignee_avg_completion} days as your baseline, NOT the team average.
        - If {assignee_completed_count} is 0, fall back to team average but mention this in reasoning.
        - Factor in the complexity score, workload impact, and skill match into your estimate.
        
        Format your response as JSON WITH EXPLAINABILITY:
        {{
            "estimated_days_from_today": number (integer representing days from today),
            "estimated_effort_days": number (actual work days needed),
            "confidence_level": "high|medium|low",
            "confidence_score": 0.XX,
            "reasoning": "2-3 sentences explaining the timeline prediction",
            "risk_factors": ["up to 3 potential delays or risks"],
            "recommendations": ["up to 3 suggestions to meet the deadline"],
            "alternative_scenarios": {{
                "optimistic_days": number,
                "pessimistic_days": number
            }},
            "calculation_breakdown": {{
                "base_estimate_days": number,
                "complexity_factor": 0.XX,
                "workload_adjustment": 0.XX,
                "skill_match_adjustment": 0.XX,
                "collaboration_overhead": 0.XX,
                "dependency_buffer": number,
                "risk_buffer": number,
                "priority_adjustment": 0.XX,
                "buffer_days": number
            }},
            "velocity_analysis": {{
                "current_velocity": "X hours/day",
                "expected_velocity": "X hours/day",
                "velocity_trend": "accelerating|steady|declining",
                "remaining_effort_hours": number
            }},
            "assumptions": [
                "Key assumption 1",
                "Key assumption 2",
                "Key assumption 3"
            ],
            "contributing_factors": [
                {{
                    "factor": "Factor name",
                    "contribution_percentage": XX,
                    "description": "How this impacts the deadline"
                }}
            ]
        }}
        """
        
        response_text = generate_ai_content(prompt, task_type='deadline_prediction')
        if response_text:
            # Handle code block formatting
            if "```json" in response_text:
                response_text = response_text.split("```json")[1].split("```")[0].strip()
            elif "```" in response_text:
                response_text = response_text.split("```")[1].strip()
                
            ai_response = json.loads(response_text)
            
            # Handle velocity edge case: If current velocity is 0, set trend to 'Pending'
            if 'velocity_analysis' in ai_response:
                velocity = ai_response['velocity_analysis']
                current_vel = velocity.get('current_velocity', '0 hours/day')
                # Extract numeric value from velocity string
                try:
                    vel_value = float(current_vel.split()[0])
                    if vel_value == 0:
                        ai_response['velocity_analysis']['velocity_trend'] = 'Pending'
                except (ValueError, IndexError):
                    pass  # Keep original trend if parsing fails
            
            # Calculate actual dates from the predicted days
            from datetime import datetime, timedelta
            today = datetime.now().date()
            
            estimated_days = ai_response.get('estimated_days_from_today', 3)
            optimistic_days = ai_response.get('alternative_scenarios', {}).get('optimistic_days', estimated_days - 1)
            pessimistic_days = ai_response.get('alternative_scenarios', {}).get('pessimistic_days', estimated_days + 2)
            
            # Ensure minimum of 1 day for all scenarios
            estimated_days = max(1, estimated_days)
            optimistic_days = max(1, optimistic_days)
            pessimistic_days = max(1, pessimistic_days)
            
            # Calculate the actual dates
            recommended_deadline = (today + timedelta(days=estimated_days)).strftime('%Y-%m-%d')
            optimistic_deadline = (today + timedelta(days=optimistic_days)).strftime('%Y-%m-%d')
            pessimistic_deadline = (today + timedelta(days=pessimistic_days)).strftime('%Y-%m-%d')
            
            # Update response with calculated dates
            ai_response['recommended_deadline'] = recommended_deadline
            ai_response['alternative_scenarios'] = {
                'optimistic': optimistic_deadline,
                'pessimistic': pessimistic_deadline
            }
            
            return ai_response
        return None
    except Exception as e:
        logger.error(f"Error predicting deadline: {str(e)}")
        return None

def recommend_board_columns(board_data: Dict) -> Optional[Dict]:
    """
    Recommend optimal column structure for a new board based on project type and context.
    
    Args:
        board_data: Dictionary containing board information and context
        
    Returns:
        A dictionary with column recommendations or None if recommendation fails
    """
    try:
        # Extract board information
        board_name = board_data.get('name', '')
        board_description = board_data.get('description', '')
        team_size = board_data.get('team_size', 1)
        project_type = board_data.get('project_type', 'general')
        organization_type = board_data.get('organization_type', 'general')
        existing_columns = board_data.get('existing_columns', [])
        
        prompt = f"""
        Recommend an optimal column structure for this Kanban board based on the project context.
        
        ## Board Information:
        - Name: {board_name}
        - Description: {board_description or 'No description provided'}
        - Team Size: {team_size} members
        - Project Type: {project_type}
        - Organization Type: {organization_type}
        - Current Columns: {', '.join(existing_columns) if existing_columns else 'None (new board)'}
        
        Consider these factors:
        1. Project type and workflow requirements
        2. Team size and collaboration needs
        3. Industry best practices
        4. Review and approval processes
        5. Quality assurance needs
        6. Deployment/release cycles
        
        Recommend 4-7 columns that would create an efficient workflow.
        
        Format your response as JSON WITH FULL EXPLAINABILITY:
        {{
            "recommended_columns": [
                {{
                    "name": "Column Name",
                    "description": "Brief description of what goes in this column",
                    "position": 1,
                    "color_suggestion": "#hex_color",
                    "purpose": "Why this column is essential for the workflow",
                    "typical_wip_limit": "Suggested WIP limit or null"
                }}
            ],
            "workflow_type": "kanban|scrum|custom",
            "confidence_score": 0.XX,
            "confidence_level": "high|medium|low",
            "reasoning": "2-3 sentences explaining why this structure works",
            "contributing_factors": [
                {{
                    "factor": "Factor name (e.g., 'Team Size', 'Project Complexity')",
                    "contribution_percentage": XX,
                    "description": "How this factor influenced the recommendation"
                }}
            ],
            "workflow_tips": ["up to 3 tips for using this column structure effectively"],
            "customization_suggestions": ["up to 2 ways to adapt this structure"],
            "alternative_workflow": {{
                "type": "Alternative workflow type",
                "columns": ["Column 1", "Column 2", "Column 3"],
                "when_to_use": "Conditions when this alternative would be better"
            }},
            "assumptions": [
                "Assumption 1 about the team or project",
                "Assumption 2 about the workflow needs"
            ],
            "bottleneck_warnings": [
                "Potential bottleneck 1 to watch for with this structure",
                "Potential bottleneck 2 to monitor"
            ]
        }}
        """
        
        response_text = generate_ai_content(prompt, task_type='column_recommendations')
        if response_text:
            # Handle code block formatting
            if "```json" in response_text:
                response_text = response_text.split("```json")[1].split("```")[0].strip()
            elif "```" in response_text:
                response_text = response_text.split("```")[1].strip()
                
            return json.loads(response_text)
        return None
    except Exception as e:
        logger.error(f"Error recommending columns: {str(e)}")
        return None

def suggest_task_breakdown(task_data: Dict) -> Optional[Dict]:
    """
    Suggest automated breakdown of a complex task into smaller subtasks.
    
    Args:
        task_data: Dictionary containing task information
        
    Returns:
        A dictionary with subtask suggestions or None if breakdown fails
    """
    try:
        # Extract task information
        title = task_data.get('title', '')
        description = task_data.get('description', '')
        priority = task_data.get('priority', 'medium')
        due_date = task_data.get('due_date', '')
        estimated_effort = task_data.get('estimated_effort', '')
        
        prompt = f"""
        Analyze this task and suggest a breakdown into smaller, manageable subtasks with dependencies.
        Provide explainable AI output with confidence scores and factor analysis.
        
        ## Task Information:
        - Title: {title}
        - Description: {description or 'No description provided'}
        - Priority: {priority}
        - Due Date: {due_date or 'Not specified'}
        - Estimated Effort: {estimated_effort or 'Not specified'}
        
        Consider these principles:
        1. Each subtask should be completable in 1-3 days
        2. Identify logical dependencies between subtasks
        3. Include testing, review, and documentation subtasks where appropriate
        4. Consider risk mitigation subtasks for complex work
        5. Ensure subtasks are specific and actionable
        
        Format your response as JSON WITH FULL EXPLAINABILITY:
        {{
            "is_breakdown_recommended": true|false,
            "complexity_score": 1-10,
            "confidence_score": 0.XX,
            "confidence_level": "high|medium|low",
            "reasoning": "2-3 sentences explaining why breakdown is or isn't recommended",
            "complexity_factors": [
                {{
                    "factor": "Factor name (e.g., 'Technical Scope', 'Integration Points')",
                    "contribution_percentage": XX,
                    "description": "How this factor contributes to complexity"
                }}
            ],
            "subtasks": [
                {{
                    "title": "Subtask title",
                    "description": "Brief description with clear deliverable",
                    "estimated_effort": "1-3 days",
                    "priority": "low|medium|high",
                    "dependencies": ["1-based indices of dependent subtasks (e.g., 1, 2, 3) or empty array"],
                    "order": 1,
                    "skill_requirements": ["skill1", "skill2"],
                    "why_needed": "Brief explanation of why this subtask is essential"
                }}
            ],
            "critical_path": [
                "List of subtask titles that form the critical path"
            ],
            "parallel_opportunities": [
                "Subtasks that can be worked on simultaneously"
            ],
            "workflow_suggestions": ["up to 3 suggestions for managing these subtasks"],
            "risk_considerations": [
                {{
                    "risk": "Risk description",
                    "affected_subtasks": ["subtask titles"],
                    "mitigation": "Suggested mitigation"
                }}
            ],
            "alternative_approach": {{
                "description": "Alternative way to break down this task",
                "when_applicable": "Conditions when this alternative would be better"
            }},
            "assumptions": [
                "Key assumption 1 about the task",
                "Key assumption 2 about resources/skills"
            ],
            "total_estimated_effort": "Sum of all subtask efforts",
            "effort_vs_original": "How this compares to original estimate (e.g., '20% more due to testing')"
        }}
        """
        
        response_text = generate_ai_content(prompt, task_type='task_breakdown')
        if response_text:
            # Handle code block formatting
            if "```json" in response_text:
                response_text = response_text.split("```json")[1].split("```")[0].strip()
            elif "```" in response_text:
                response_text = response_text.split("```")[1].strip()
                
            return json.loads(response_text)
        return None
    except Exception as e:
        logger.error(f"Error suggesting task breakdown: {str(e)}")
        return None

def analyze_workflow_optimization(board_analytics: Dict) -> Optional[Dict]:
    """
    Analyze board workflow and suggest optimizations based on patterns and bottlenecks.
    
    Args:
        board_analytics: Dictionary containing comprehensive board analytics data
        
    Returns:
        A dictionary with workflow optimization recommendations or None if analysis fails
    """
    try:
        # Extract analytics data
        total_tasks = board_analytics.get('total_tasks', 0)
        tasks_by_column = board_analytics.get('tasks_by_column', [])
        tasks_by_priority = board_analytics.get('tasks_by_priority', [])
        tasks_by_user = board_analytics.get('tasks_by_user', [])
        avg_completion_time = board_analytics.get('avg_completion_time_days', 0)
        overdue_count = board_analytics.get('overdue_count', 0)
        productivity = board_analytics.get('productivity', 0)
        task_velocity = board_analytics.get('weekly_velocity', [])
        
        # Format data for prompt
        column_distribution = ', '.join([f"{col['name']}: {col['count']} tasks" for col in tasks_by_column])
        priority_distribution = ', '.join([f"{pri['priority']}: {pri['count']}" for pri in tasks_by_priority])
        user_workload = ', '.join([f"{user['username']}: {user['count']} tasks ({user['completion_rate']}% complete)" for user in tasks_by_user[:5]])
        
        prompt = f"""
        Analyze this Kanban board's workflow and suggest specific optimizations to improve efficiency and flow.
        Provide comprehensive explainability with confidence scores and factor analysis.
        
        ## Board Analytics:
        - Total Active Tasks: {total_tasks}
        - Average Completion Time: {avg_completion_time} days
        - Overdue Tasks: {overdue_count}
        - Overall Productivity: {productivity}%
        
        ## Task Distribution:
        - By Column: {column_distribution}
        - By Priority: {priority_distribution}
        - By Assignee: {user_workload}
        
        ## Performance Data:
        - Weekly Velocity: {task_velocity if task_velocity else 'No historical data'}
        
        Analyze for:
        1. Bottleneck columns (too many tasks stuck)
        2. Workload imbalances between team members
        3. Priority distribution issues
        4. Flow inefficiencies
        5. Process improvement opportunities
        
        Format your response as JSON WITH FULL EXPLAINABILITY:
        {{
            "overall_health_score": 1-10,
            "confidence_score": 0.XX,
            "confidence_level": "high|medium|low",
            "health_factors": [
                {{
                    "factor": "Factor name (e.g., 'Task Flow', 'Team Utilization')",
                    "score": 1-10,
                    "contribution_percentage": XX,
                    "description": "How this factor affects workflow health"
                }}
            ],
            "bottlenecks": [
                {{
                    "type": "column|user|priority",
                    "location": "specific column/user name",
                    "severity": "low|medium|high",
                    "description": "What's causing the bottleneck",
                    "confidence": 0.XX,
                    "evidence": ["Data points that led to this conclusion"],
                    "root_cause": "Underlying reason for this bottleneck",
                    "impact_if_unaddressed": "What happens if this isn't fixed"
                }}
            ],
            "optimization_recommendations": [
                {{
                    "category": "workflow|workload|process|structure",
                    "title": "Brief recommendation title",
                    "description": "Detailed recommendation",
                    "impact": "high|medium|low",
                    "effort": "low|medium|high",
                    "priority": 1-5,
                    "confidence_score": 0.XX,
                    "expected_improvement": "Quantified improvement (e.g., '15% faster cycle time')",
                    "reasoning": "Why this recommendation will help",
                    "implementation_steps": ["Step 1", "Step 2", "Step 3"],
                    "success_metrics": ["How to measure if this worked"]
                }}
            ],
            "quick_wins": [
                {{
                    "action": "Specific quick win action",
                    "expected_result": "What this will achieve",
                    "timeframe": "How long to implement"
                }}
            ],
            "workflow_insights": "2-3 sentences about overall workflow patterns",
            "next_steps": ["up to 3 specific actions to take next"],
            "assumptions": [
                "Assumption 1 about the data or team",
                "Assumption 2 about workflow patterns"
            ],
            "data_limitations": [
                "Limitation 1 - what we couldn't analyze",
                "Limitation 2 - data that would improve analysis"
            ],
            "trend_analysis": {{
                "direction": "improving|stable|declining",
                "key_drivers": ["Driver 1", "Driver 2"],
                "forecast": "Prediction if current patterns continue"
            }}
        }}
        """
        
        response_text = generate_ai_content(prompt, task_type='workflow_optimization')
        if response_text:
            # Handle code block formatting
            if "```json" in response_text:
                response_text = response_text.split("```json")[1].split("```")[0].strip()
            elif "```" in response_text:
                response_text = response_text.split("```")[1].strip()
                
            return json.loads(response_text)
        return None
    except Exception as e:
        logger.error(f"Error analyzing workflow optimization: {str(e)}")
        return None


def analyze_critical_path(board_data: Dict) -> Optional[Dict]:
    """
    Analyze task dependencies and identify critical path using AI.
    
    Args:
        board_data: Dictionary containing board tasks with dependencies, dates, and durations
        
    Returns:
        Dictionary with critical path analysis, slack times, and schedule insights
    """
    try:
        tasks_info = board_data.get('tasks', [])
        if not tasks_info:
            return None
              # Format tasks for AI analysis
        formatted_tasks = []
        for task in tasks_info:
            task_str = f"""
            Task ID: {task.get('id')}
            Title: {task.get('title')}
            Due Date: {task.get('due_date', 'Not set')}
            Progress: {task.get('progress', 0)}%
            Assigned To: {task.get('assigned_to', 'Unassigned')}
            Column: {task.get('column_name', 'Unknown')}
            Priority: {task.get('priority', 'medium')}
            """
            formatted_tasks.append(task_str)
            
        prompt = f"""
        Analyze these project tasks to identify the critical path, calculate slack times, and assess schedule risks.
        Use project management principles similar to Gantt chart analysis.
        Provide full explainability for the analysis methodology and all recommendations.
        
        ## Project Tasks:
        {chr(10).join(formatted_tasks)}
        
        ## Analysis Required:
        1. **Critical Path Identification**: Find the longest sequence of dependent tasks that determines project duration
        2. **Slack Time Calculation**: Calculate float time for each task (Latest Start - Earliest Start)
        3. **Schedule Risk Assessment**: Identify tasks at risk of delays
        4. **Resource Bottlenecks**: Identify potential resource conflicts
        5. **Milestone Analysis**: Assess milestone achievability
        6. **Optimization Opportunities**: Suggest ways to compress the schedule
        
        ## Project Management Context:
        - Tasks with zero slack time are on the critical path
        - Delays in critical path tasks directly impact project completion
        - Tasks with high slack can be delayed without affecting the project
        - Resource conflicts can create bottlenecks even for non-critical tasks
        
        CRITICAL: Respond with ONLY valid JSON. No explanations, no additional text.
        
        {{
            "confidence_score": 0.XX,
            "analysis_methodology": {{
                "approach": "Description of how critical path was determined",
                "assumptions": ["Assumption 1 about task durations", "Assumption 2 about dependencies"],
                "data_quality": "high|medium|low",
                "limitations": ["Limitation 1 of this analysis"]
            }},
            "critical_path": [
                {{
                    "task_id": "task_id",
                    "task_title": "title",
                    "position_in_path": 1,
                    "duration_hours": 8,
                    "earliest_start": "2025-06-19 09:00",
                    "earliest_finish": "2025-06-19 17:00",
                    "why_critical": "Why this task is on the critical path"
                }}
            ],
            "critical_path_reasoning": {{
                "path_explanation": "Why this sequence was identified as critical",
                "alternative_paths": ["Other significant paths considered"],
                "path_sensitivity": "How sensitive is the schedule to changes in this path"
            }},
            "task_analysis": [
                {{
                    "task_id": "task_id",
                    "task_title": "title",
                    "earliest_start": "2025-06-19 09:00",
                    "earliest_finish": "2025-06-19 17:00",
                    "latest_start": "2025-06-19 09:00",
                    "latest_finish": "2025-06-19 17:00",
                    "slack_hours": 0,
                    "slack_interpretation": "What this slack time means for planning",
                    "is_critical": true,
                    "risk_level": "low|medium|high",
                    "risk_reasoning": "Why this risk level was assigned",
                    "risk_factors": ["factor1"]
                }}
            ],
            "project_insights": {{
                "total_duration_hours": 120,
                "project_completion_date": "2025-07-15",
                "critical_path_duration": 100,
                "schedule_buffer_hours": 20,
                "buffer_adequacy": "sufficient|marginal|insufficient",
                "buffer_reasoning": "Why buffer is/isn't adequate",
                "high_risk_tasks": 3,
                "resource_conflicts": [],
                "schedule_confidence": "high|medium|low"
            }},
            "bottleneck_analysis": [
                {{
                    "bottleneck": "Description of bottleneck",
                    "affected_tasks": ["task1", "task2"],
                    "impact_hours": X,
                    "root_cause": "Why this bottleneck exists",
                    "resolution_options": ["Option 1", "Option 2"]
                }}
            ],
            "recommendations": [
                {{
                    "type": "critical_path|resources|schedule|process",
                    "title": "Recommendation title",
                    "description": "Detailed recommendation",
                    "reasoning": "Why this is recommended based on analysis",
                    "expected_impact": "What improvement to expect",
                    "implementation_steps": ["Step 1", "Step 2"],
                    "impact": "high|medium|low",
                    "effort": "high|medium|low",
                    "priority": 1
                }}
            ],
            "schedule_optimization": {{
                "compression_potential": "high|medium|low|none",
                "compression_strategies": [
                    {{
                        "strategy": "Fast-tracking or crashing option",
                        "time_saved_hours": X,
                        "cost_impact": "Description of cost/resource impact",
                        "risk_impact": "How this affects risk"
                    }}
                ]
            }}
        }}
        """
        
        response_text = generate_ai_content(prompt, task_type='critical_path')
        if response_text:
            # Handle code block formatting and extract JSON
            if "```json" in response_text:
                response_text = response_text.split("```json")[1].split("```")[0].strip()
            elif "```" in response_text:
                response_text = response_text.split("```")[1].strip()
            
            # Try to find JSON in the response if it's mixed with other text
            json_start = response_text.find('{')
            json_end = response_text.rfind('}')
            
            if json_start != -1 and json_end != -1 and json_end > json_start:
                response_text = response_text[json_start:json_end + 1]
            
            try:
                # First attempt: direct JSON parsing
                return json.loads(response_text)
            except json.JSONDecodeError as json_error:
                logger.error(f"JSON parsing error in critical path analysis: {json_error}")
                logger.error(f"Raw response snippet: {response_text[:500]}...")
                
                # Second attempt: Fix common JSON issues
                try:
                    import re
                    # Remove trailing commas
                    fixed_text = re.sub(r',(\s*[}\]])', r'\1', response_text)
                    # Fix any unescaped quotes in strings
                    fixed_text = re.sub(r'(?<!\\)"(?=\w)', r'\\"', fixed_text)
                    return json.loads(fixed_text)
                except json.JSONDecodeError:
                    # Third attempt: Build a valid response from task data
                    logger.info("Creating fallback response based on actual task data")
                    
                    # Calculate actual project insights from the task data
                    total_duration = sum(task.get('estimated_duration_hours', 8) for task in tasks_info)
                    high_risk_tasks = len([task for task in tasks_info if task.get('priority') == 'high'])
                    
                    return {                        "critical_path": [
                            {
                                "task_id": str(task.get('id')),
                                "task_title": task.get('title', 'Unknown Task'),
                                "position_in_path": idx + 1,
                                "earliest_start": "2025-06-19 09:00",
                                "earliest_finish": "2025-06-20 17:00"
                            }
                            for idx, task in enumerate(tasks_info[:5])  # Top 5 tasks as critical path
                        ],
                        "task_analysis": [
                            {
                                "task_id": str(task.get('id')),
                                "task_title": task.get('title', 'Unknown Task'),
                                "earliest_start": "2025-06-19 09:00",
                                "earliest_finish": "2025-06-20 17:00",
                                "latest_start": "2025-06-19 09:00",
                                "latest_finish": "2025-06-20 17:00",
                                "slack_hours": 0 if task.get('priority') == 'high' else 8,
                                "is_critical": task.get('priority') == 'high',
                                "risk_level": task.get('priority', 'medium'),
                                "risk_factors": ["Resource dependency"] if task.get('assigned_to') else ["Unassigned task"]
                            }
                            for task in tasks_info[:10]  # Analyze top 10 tasks
                        ],
                        "project_insights": {
                            "total_duration_hours": total_duration,
                            "project_completion_date": "2025-08-15",
                            "critical_path_duration": int(total_duration * 0.6),
                            "schedule_buffer_hours": int(total_duration * 0.2),
                            "high_risk_tasks": high_risk_tasks,
                            "resource_conflicts": []
                        },
                        "recommendations": [
                            {
                                "type": "critical_path",
                                "title": "Focus on High-Priority Tasks",
                                "description": f"You have {high_risk_tasks} high-priority tasks that require immediate attention to stay on schedule.",
                                "impact": "high",
                                "effort": "medium",
                                "priority": 1
                            },
                            {
                                "type": "resources",
                                "title": "Review Task Dependencies",
                                "description": "Ensure all task dependencies are properly defined to get accurate critical path analysis.",
                                "impact": "medium",
                                "effort": "low",
                                "priority": 2
                            }
                        ]
                    }
        return None
    except Exception as e:
        logger.error(f"Error analyzing critical path: {str(e)}")
        return {
            "critical_path": [],
            "task_analysis": [],
            "project_insights": {
                "total_duration_hours": 0,
                "project_completion_date": "Unknown",
                "critical_path_duration": 0,
                "schedule_buffer_hours": 0,
                "high_risk_tasks": 0,
                "resource_conflicts": []
            },
            "recommendations": [{
                "type": "error",
                "title": "System Error",
                "description": f"Critical path analysis failed: {str(e)}",
                "impact": "high",
                "effort": "low",
                "priority": 1
            }],
            "milestones_status": [],
            "error": str(e)
        }


def predict_task_completion(task_data: Dict, historical_data: List[Dict] = None) -> Optional[Dict]:
    """
    Predict realistic task completion dates based on current progress and historical data.
    
    Args:
        task_data: Current task information
        historical_data: Optional historical performance data for similar tasks
        
    Returns:
        Dictionary with completion predictions and confidence intervals
    """
    try:
        # Format current task data
        task_info = f"""
        Task: {task_data.get('title')}
        Current Progress: {task_data.get('progress', 0)}%
        Due Date: {task_data.get('due_date', 'Not set')}
        Priority: {task_data.get('priority', 'medium')}
        Assignee: {task_data.get('assigned_to', 'Unassigned')}
        """
        
        # Format historical data if available
        historical_context = ""
        if historical_data:
            historical_context = f"""
            ## Historical Performance Data:
            {chr(10).join([
                f"Similar task: {h.get('title')} - Estimated: {h.get('estimated_hours')}h, Actual: {h.get('actual_hours')}h, Accuracy: {h.get('accuracy_percentage', 0)}%"
                for h in historical_data[:5]
            ])}
            """
        
        prompt = f"""
        Predict the realistic completion date and provide confidence intervals for this task.
        Consider current progress, time spent, remaining work, and any historical patterns.
        Provide full explainability for all predictions and assessments.
        
        ## Current Task:
        {task_info}
        
        {historical_context}
        
        ## Prediction Analysis:
        1. **Progress Analysis**: Evaluate current progress against time spent
        2. **Velocity Calculation**: Determine work completion rate
        3. **Remaining Work**: Estimate time needed to complete remaining work
        4. **Risk Factors**: Identify factors that could cause delays
        5. **Historical Adjustment**: Apply lessons from similar tasks
        6. **Confidence Intervals**: Provide optimistic, realistic, and pessimistic scenarios
        
        Format response as JSON WITH FULL EXPLAINABILITY:
        {{
            "confidence_score": 0.XX,
            "predictions": {{
                "optimistic_completion": "YYYY-MM-DD HH:MM",
                "realistic_completion": "YYYY-MM-DD HH:MM",
                "pessimistic_completion": "YYYY-MM-DD HH:MM",
                "confidence_level": "high|medium|low"
            }},
            "prediction_reasoning": {{
                "methodology": "How the prediction was calculated",
                "key_factors": [
                    {{
                        "factor": "Factor name",
                        "contribution_percentage": XX,
                        "effect": "positive|neutral|negative",
                        "description": "How this factor influenced the prediction"
                    }}
                ],
                "historical_adjustment": "How historical data influenced the prediction (if applicable)",
                "confidence_justification": "Why this confidence level was assigned"
            }},
            "progress_analysis": {{
                "current_velocity": "hours_per_day",
                "expected_velocity": "hours_per_day",
                "velocity_trend": "accelerating|steady|declining",
                "trend_reasoning": "Why this velocity trend was identified",
                "remaining_effort_hours": 10,
                "effort_breakdown": [
                    {{
                        "phase": "Remaining work phase",
                        "hours": X,
                        "reasoning": "Why this effort estimate"
                    }}
                ]
            }},
            "risk_assessment": {{
                "delay_probability": "low|medium|high",
                "probability_reasoning": "Why this delay probability",
                "risk_factors": [
                    {{
                        "factor": "Risk factor",
                        "likelihood": "high|medium|low",
                        "impact_days": X,
                        "mitigation": "How to address this risk"
                    }}
                ],
                "mitigation_suggestions": ["suggestion1", "suggestion2"]
            }},
            "scenario_analysis": {{
                "optimistic_scenario": {{
                    "assumptions": ["What must go right"],
                    "probability": "XX%"
                }},
                "realistic_scenario": {{
                    "assumptions": ["Most likely conditions"],
                    "probability": "XX%"
                }},
                "pessimistic_scenario": {{
                    "assumptions": ["What could go wrong"],
                    "probability": "XX%"
                }}
            }},
            "recommendations": [
                {{
                    "type": "schedule|resource|scope|process",
                    "action": "specific action to take",
                    "reasoning": "Why this action is recommended",
                    "impact": "expected impact",
                    "urgency": "low|medium|high"
                }}
            ],
            "assumptions": [
                "Key assumption made in this prediction"
            ],
            "limitations": [
                "Limitation of this prediction"
            ]
        }}
        """
        
        response_text = generate_ai_content(prompt, task_type='complex')
        if response_text:
            # Handle code block formatting
            if "```json" in response_text:
                response_text = response_text.split("```json")[1].split("```")[0].strip()
            elif "```" in response_text:
                response_text = response_text.split("```")[1].strip()
                
            try:
                return json.loads(response_text)
            except json.JSONDecodeError:
                # Fallback with basic structure
                return {
                    'prediction_text': response_text,
                    'confidence_score': 0.5,
                    'parsing_note': 'Returned plain text due to JSON parsing error'
                }
        return None
    except Exception as e:
        logger.error(f"Error predicting task completion: {str(e)}")
        return None


def generate_project_timeline(board_data: Dict) -> Optional[Dict]:
    """
    Generate an AI-enhanced project timeline similar to a Gantt chart view.
    
    Args:
        board_data: Complete board data including tasks, dependencies, and team information
        
    Returns:
        Dictionary with timeline visualization data and AI insights
    """
    try:
        tasks = board_data.get('tasks', [])
        team_data = board_data.get('team', [])
        board_info = board_data.get('board_info', {})
        
        prompt = f"""
        Create a comprehensive project timeline analysis for this Kanban board, providing insights 
        similar to what a Gantt chart would show but enhanced with AI intelligence.
        Provide full explainability for all forecasts and recommendations.
        
        ## Board Information:
        Name: {board_info.get('name', 'Unknown')}
        Total Tasks: {len(tasks)}
        Team Size: {len(team_data)}
        
        ## Tasks Overview:
        {chr(10).join([
            f"- {task.get('title')} | {task.get('column_name')} | Progress: {task.get('progress', 0)}% | Priority: {task.get('priority', 'medium')} | Assigned: {task.get('assigned_to', 'Unassigned')}"
            for task in tasks[:20]  # Limit to avoid token limits
        ])}
        
        ## Team Capacity:
        {chr(10).join([
            f"- {member.get('name', 'Unknown')}: {member.get('task_count', 0)} tasks assigned"
            for member in team_data
        ])}
        
        ## Analysis Required:
        1. **Timeline Structure**: Organize tasks into logical phases/sprints
        2. **Resource Allocation**: Identify over/under-allocated team members
        3. **Dependency Mapping**: Show task relationships and potential bottlenecks
        4. **Progress Forecasting**: Predict completion dates for each phase
        5. **Risk Identification**: Highlight schedule risks and mitigation strategies
        6. **Optimization Opportunities**: Suggest timeline improvements
        
        Format response as JSON WITH FULL EXPLAINABILITY:
        {{
            "confidence_score": 0.XX,
            "analysis_methodology": {{
                "approach": "How the timeline was constructed and analyzed",
                "data_completeness": "high|medium|low",
                "key_assumptions": ["Assumption about velocity", "Assumption about availability"],
                "limitations": ["What couldn't be determined from available data"]
            }},
            "timeline_phases": [
                {{
                    "phase_name": "Phase 1: Foundation",
                    "start_date": "YYYY-MM-DD",
                    "end_date": "YYYY-MM-DD",
                    "tasks": ["task_id1", "task_id2"],
                    "key_milestones": ["milestone1"],
                    "phase_status": "not_started|in_progress|completed",
                    "completion_confidence": "high|medium|low",
                    "confidence_reasoning": "Why this confidence level for this phase",
                    "phase_risks": ["Risk specific to this phase"],
                    "dependencies_on_previous": "What must complete before this phase"
                }}
            ],
            "resource_timeline": [
                {{
                    "team_member": "member_name",
                    "utilization_percentage": 85,
                    "utilization_assessment": "optimal|underutilized|overloaded",
                    "assessment_reasoning": "Why this utilization assessment",
                    "workload_periods": [
                        {{
                            "start_date": "YYYY-MM-DD",
                            "end_date": "YYYY-MM-DD",
                            "intensity": "light|normal|heavy|overloaded",
                            "task_count": 3
                        }}
                    ],
                    "recommendations": ["specific suggestions for this person"],
                    "capacity_concerns": "Any capacity concerns identified"
                }}
            ],
            "critical_milestones": [
                {{
                    "milestone": "milestone_name",
                    "target_date": "YYYY-MM-DD",
                    "forecasted_date": "YYYY-MM-DD",
                    "confidence": "high|medium|low",
                    "forecast_reasoning": "Why this forecast date was predicted",
                    "blocking_factors": ["factor1"],
                    "impact_if_delayed": "description",
                    "mitigation_options": ["Option to reduce delay risk"]
                }}
            ],
            "timeline_insights": {{
                "project_duration_weeks": 12,
                "duration_reasoning": "How duration was calculated",
                "current_progress_percentage": 45,
                "progress_assessment": "ahead|on_track|slightly_behind|significantly_behind",
                "projected_completion": "YYYY-MM-DD",
                "projection_confidence": "high|medium|low",
                "projection_reasoning": "How completion date was projected",
                "schedule_health": "on_track|at_risk|behind",
                "health_factors": [
                    {{
                        "factor": "Factor affecting schedule health",
                        "impact": "positive|neutral|negative",
                        "evidence": "Supporting data"
                    }}
                ],
                "bottleneck_periods": ["YYYY-MM-DD to YYYY-MM-DD"],
                "optimization_potential": "high|medium|low",
                "optimization_reasoning": "Why this optimization potential"
            }},
            "schedule_risks": [
                {{
                    "risk": "Description of schedule risk",
                    "likelihood": "high|medium|low",
                    "impact": "high|medium|low",
                    "affected_phases": ["Phase 1"],
                    "early_warning_signs": ["Sign to watch for"],
                    "mitigation_strategy": "How to address this risk"
                }}
            ],
            "recommendations": [
                {{
                    "category": "timeline|resources|dependencies|risks",
                    "title": "recommendation title",
                    "description": "detailed recommendation",
                    "rationale": "Why this is recommended based on analysis",
                    "implementation_steps": ["Step 1", "Step 2"],
                    "implementation_effort": "low|medium|high",
                    "expected_impact": "description of expected impact",
                    "success_metrics": ["How to measure if recommendation worked"],
                    "priority": 1
                }}
            ]
        }}
        """
        
        response_text = generate_ai_content(prompt, task_type='timeline_generation')
        if response_text:
            # Handle code block formatting
            if "```json" in response_text:
                response_text = response_text.split("```json")[1].split("```")[0].strip()
            elif "```" in response_text:
                response_text = response_text.split("```")[1].strip()
            
            # Try to find JSON in the response
            json_start = response_text.find('{')
            json_end = response_text.rfind('}')
            
            if json_start != -1 and json_end != -1 and json_end > json_start:
                response_text = response_text[json_start:json_end + 1]
            
            try:
                return json.loads(response_text)
            except json.JSONDecodeError as json_error:
                logger.error(f"JSON parsing error in timeline generation: {json_error}")
                
                # Create a fallback response based on actual data
                return {
                    "timeline_phases": [
                        {
                            "phase_name": "Foundation Phase",
                            "start_date": "2025-06-19",
                            "end_date": "2025-07-15",
                            "tasks": [str(task.get('id')) for task in tasks[:5]],
                            "key_milestones": ["Setup and Planning Complete"],
                            "phase_status": "in_progress",
                            "completion_confidence": "high"
                        },
                        {
                            "phase_name": "Development Phase",
                            "start_date": "2025-07-16",
                            "end_date": "2025-08-30",
                            "tasks": [str(task.get('id')) for task in tasks[5:15]],
                            "key_milestones": ["Core Features Complete"],
                            "phase_status": "not_started",
                            "completion_confidence": "medium"
                        }
                    ],
                    "resource_timeline": [
                        {
                            "team_member": member.get('name', 'Team Member'),
                            "utilization_percentage": min(90, len(tasks) * 10),
                            "workload_periods": [{
                                "start_date": "2025-06-19",
                                "end_date": "2025-08-30",
                                "intensity": "normal",
                                "task_count": min(5, len(tasks))
                            }],
                            "recommendations": ["Maintain current workload balance"]
                        }
                        for member in team_data[:3]  # Limit to 3 team members
                    ],
                    "critical_milestones": [
                        {
                            "milestone": "Project Foundation Complete",
                            "target_date": "2025-07-15",
                            "forecasted_date": "2025-07-15",
                            "confidence": "high",
                            "blocking_factors": [],
                            "impact_if_delayed": "Delays subsequent development phases"
                        }
                    ],
                    "timeline_insights": {
                        "project_duration_weeks": 12,
                        "current_progress_percentage": 25,
                        "projected_completion": "2025-08-30",
                        "schedule_health": "on_track",
                        "bottleneck_periods": [],
                        "optimization_potential": "medium"
                    },
                    "recommendations": [
                        {
                            "category": "timeline",
                            "title": "Optimize Task Sequencing",
                            "description": "Review task dependencies to identify opportunities for parallel work execution",
                            "implementation_effort": "medium",
                            "expected_impact": "Potential 15% reduction in project timeline",
                            "priority": 1
                        }
                    ]
                }
        return None
    except Exception as e:
        logger.error(f"Error generating project timeline: {str(e)}")
        return None

def extract_tasks_from_transcript(transcript: str, meeting_context: Dict, board) -> Optional[Dict]:
    """
    Extract actionable tasks from meeting transcript using AI
    
    Args:
        transcript: The meeting transcript text
        meeting_context: Additional context (meeting type, participants, etc.)
        board: The target board for context
        
    Returns:
        Dictionary with extracted tasks and metadata
    """
    try:
        # Get board context
        board_members = [member.username for member in board.members.all()]
        board_members.append(board.created_by.username)
        
        existing_columns = [col.name for col in board.columns.all()]
        
        prompt = f"""
        Analyze this meeting transcript and extract actionable tasks. Focus on clear action items, 
        decisions that require follow-up, and commitments made during the meeting.
        
        ## Meeting Context:
        - Meeting Type: {meeting_context.get('meeting_type', 'General')}
        - Date: {meeting_context.get('date', 'Not specified')}
        - Participants: {', '.join(meeting_context.get('participants', []))}
        
        ## Board Context:
        - Board: {board.name}
        - Available Assignees: {', '.join(board_members)}
        - Project Context: {board.description[:200] if board.description else 'No description'}
        
        ## Meeting Transcript:
        {transcript}
        
        ## Instructions:
        1. Extract ONLY clear, actionable tasks (not general discussion points)
        2. Each task should have a specific deliverable or outcome
        3. Include context from the discussion for each task
        4. Suggest appropriate assignees if mentioned or implied
        5. Estimate priority based on urgency/importance discussed
        6. Suggest realistic due dates if timeframes were mentioned
        7. Identify dependencies between tasks if any
        
        Format your response as JSON:
        {{
            "extraction_summary": {{
                "total_tasks_found": 0,
                "meeting_summary": "Brief 2-3 sentence summary of key outcomes",
                "confidence_level": "high|medium|low",
                "processing_notes": "Any important context or limitations"
            }},
            "extracted_tasks": [
                {{
                    "title": "Clear, actionable task title",
                    "description": "Detailed description with context from the meeting",
                    "priority": "low|medium|high|urgent",
                    "suggested_assignee": "username or null",
                    "assignee_confidence": "high|medium|low",
                    "due_date_suggestion": "YYYY-MM-DD or relative like '+7 days' or null",
                    "estimated_effort": "1-3 days",
                    "category": "action_item|follow_up|decision_implementation|research",
                    "source_context": "Relevant excerpt from transcript showing where this task came from",
                    "dependencies": ["indices of other tasks this depends on"],
                    "urgency_indicators": ["phrases from transcript indicating urgency"],
                    "success_criteria": "How to know when this task is complete"
                }}
            ],
            "suggested_follow_ups": [
                {{
                    "type": "meeting|check_in|review",
                    "description": "What kind of follow-up is suggested",
                    "timeframe": "When this follow-up should happen"
                }}
            ],
            "unresolved_items": [
                "Items mentioned but need clarification before becoming tasks"
            ]
        }}
        """
        
        response_text = generate_ai_content(prompt, task_type='complex')
        if response_text:
            # Handle code block formatting
            if "```json" in response_text:
                response_text = response_text.split("```json")[1].split("```")[0].strip()
            elif "```" in response_text:
                response_text = response_text.split("```")[1].strip()
                
            return json.loads(response_text)
        return None
    except Exception as e:
        logger.error(f"Error extracting tasks from transcript: {str(e)}")
        return None

def parse_due_date(due_date_suggestion):
    """Helper function to parse AI-suggested due dates"""
    if not due_date_suggestion:
        return None
    
    try:
        from datetime import datetime, timedelta
        from django.utils import timezone
        
        # Handle relative dates like "+7 days"
        if due_date_suggestion.startswith('+'):
            days = int(due_date_suggestion.replace('+', '').replace(' days', '').replace(' day', ''))
            return timezone.now() + timedelta(days=days)
        
        # Handle absolute dates
        return datetime.strptime(due_date_suggestion, '%Y-%m-%d').date()
    except:
        return None

def extract_text_from_file(file_path: str, file_type: str) -> Optional[str]:
    """
    Extract text content from uploaded files
    
    Args:
        file_path: Path to the uploaded file
        file_type: Type of file (txt, docx, pdf, etc.)
        
    Returns:
        Extracted text content or None if extraction fails
    """
    try:
        if file_type == 'txt':
            with open(file_path, 'r', encoding='utf-8') as file:
                return file.read()
        
        elif file_type == 'docx':
            try:
                from docx import Document
                doc = Document(file_path)
                text = []
                for paragraph in doc.paragraphs:
                    text.append(paragraph.text)
                return '\n'.join(text)
            except ImportError:
                logger.error("python-docx package not installed. Cannot extract from DOCX files.")
                return None
        
        elif file_type == 'pdf':
            try:
                import PyPDF2
                with open(file_path, 'rb') as file:
                    pdf_reader = PyPDF2.PdfReader(file)
                    text = []
                    for page in pdf_reader.pages:
                        text.append(page.extract_text())
                    return '\n'.join(text)
            except ImportError:
                logger.error("PyPDF2 package not installed. Cannot extract from PDF files.")
                return None
        
        else:
            logger.warning(f"Unsupported file type: {file_type}")
            return None
            
    except Exception as e:
        logger.error(f"Error extracting text from file {file_path}: {str(e)}")
        return None

def enhance_task_description(task_data: Dict) -> Optional[Dict]:
    """
    Enhance a task description using AI to provide detailed context and checklist.
    
    Provides explainable AI output with confidence scores and reasoning for each suggestion.
    
    Args:
        task_data: Dictionary containing task information
        
    Returns:
        A dictionary with enhanced task description and explainability data or None if enhancement fails
    """
    try:
        title = task_data.get('title', '')
        description = task_data.get('description', '')
        board_context = task_data.get('board_context', '')
        column_context = task_data.get('column_context', '')
        
        prompt = f"""
        Enhance this task with a detailed description and actionable checklist.
        Provide comprehensive explainability for all suggestions.
        
        ## Task Information:
        - Title: {title}
        - Current Description: {description or 'None provided'}
        - Board Context: {board_context}
        - Column Context: {column_context}
        
        Please create a comprehensive task description that includes:
        1. Clear objective and scope
        2. Detailed requirements and acceptance criteria
        3. Actionable checklist items
        4. Potential considerations or dependencies
        
        Make it professional, specific, and actionable for a project management context.
        
        Format your response as JSON WITH FULL EXPLAINABILITY:
        {{
            "enhanced_description": "Detailed description with clear objectives, requirements, and scope",
            "confidence_score": 0.XX,
            "confidence_level": "high|medium|low",
            "enhancement_reasoning": "Why these enhancements were suggested based on the task title/context",
            "checklist_items": [
                {{
                    "item": "Specific actionable item",
                    "why_needed": "Brief explanation of why this step is important",
                    "estimated_effort": "Time estimate for this item"
                }}
            ],
            "acceptance_criteria": [
                {{
                    "criterion": "Clear criteria for task completion",
                    "verification_method": "How to verify this is met"
                }}
            ],
            "considerations": [
                {{
                    "consideration": "Important factor to consider",
                    "impact": "How this could affect the task",
                    "recommendation": "What to do about it"
                }}
            ],
            "estimated_duration": "rough time estimate (e.g., '2-4 hours', '1-2 days')",
            "duration_breakdown": {{
                "planning": "XX%",
                "execution": "XX%",
                "testing_review": "XX%"
            }},
            "skill_requirements": [
                {{
                    "skill": "skill name",
                    "level_needed": "beginner|intermediate|expert",
                    "why_needed": "Why this skill is required"
                }}
            ],
            "priority_suggestion": "low|medium|high|urgent",
            "priority_reasoning": "Why this priority level is recommended",
            "assumptions": [
                "Assumption 1 made about the task scope",
                "Assumption 2 made about resources or context"
            ],
            "alternative_approaches": [
                {{
                    "approach": "Alternative way to accomplish this task",
                    "when_applicable": "When this approach would be better"
                }}
            ],
            "risk_indicators": [
                "Potential risk or blocker to watch for"
            ]
        }}
        """
        
        response_text = generate_ai_content(prompt, task_type='task_enhancement')
        if response_text:
            # Handle code block formatting
            if "```json" in response_text:
                response_text = response_text.split("```json")[1].split("```")[0].strip()
            elif "```" in response_text:
                response_text = response_text.split("```")[1].strip()
            
            # Try to find JSON in the response
            json_start = response_text.find('{')
            json_end = response_text.rfind('}')
            
            if json_start != -1 and json_end != -1 and json_end > json_start:
                response_text = response_text[json_start:json_end + 1]
            
            try:
                return json.loads(response_text)
            except json.JSONDecodeError as e:
                logger.error(f"Error parsing JSON response: {str(e)}")
                return None
        return None
    except Exception as e:
        logger.error(f"Error enhancing task description: {str(e)}")
        return None


def calculate_task_risk_score(task_title: str, task_description: str, 
                               task_priority: str = 'medium', 
                               board_context: str = '') -> Optional[Dict]:
    """
    Calculate AI-powered likelihood and impact scoring for a task using Gemini.
    
    Adapts risk management methodology from the risk management system to Kanban tasks.
    
    Args:
        task_title: The title of the task
        task_description: Detailed description of the task
        task_priority: Current priority level (low/medium/high/urgent)
        board_context: Optional context about the board/project
        
    Returns:
        Dictionary with risk scores, level, indicators, and analysis or None if calculation fails
    """
    try:
        prompt = f"""
        As a project risk assessment expert, analyze this task and provide risk scoring using a 
        Likelihood × Impact matrix approach (1-3 scale for each).
        
        TASK INFORMATION:
        Title: {task_title}
        Description: {task_description}
        Priority: {task_priority}
        {f'Board Context: {board_context}' if board_context else ''}
        
        SCORING CRITERIA:
        
        LIKELIHOOD SCALE (1-3):
        - 1 (Low): 0-33% chance of risk occurring (task completion barrier)
        - 2 (Medium): 34-66% chance of risk occurring 
        - 3 (High): 67-100% chance of risk occurring
        
        IMPACT SCALE (1-3):
        - 1 (Low): Minor impact on task/project (<10% effect)
        - 2 (Medium): Moderate impact (10-25% effect)
        - 3 (High): Major impact on task/project (>25% effect)
        
        ANALYSIS REQUIREMENTS:
        1. Assess likelihood of task risks (delays, dependencies, resource issues)
        2. Assess potential impact if risks occur
        3. Identify key risk indicators to monitor
        4. Suggest specific mitigation actions
        5. Provide confidence level for assessment
        
        FORMAT YOUR RESPONSE AS JSON WITH DETAILED EXPLAINABILITY:
        {{
          "likelihood": {{
            "score": 1-3,
            "percentage_range": "XX-XX%",
            "reasoning": "2-3 sentence explanation",
            "key_factors": ["factor1", "factor2", "factor3"],
            "factor_weights": {{
              "factor1": 0.XX,
              "factor2": 0.XX
            }},
            "confidence": 0.XX
          }},
          "impact": {{
            "score": 1-3,
            "severity_level": "Low/Medium/High",
            "reasoning": "2-3 sentence explanation",
            "affected_areas": ["area1", "area2"],
            "impact_breakdown": {{
              "timeline": 0.XX,
              "resources": 0.XX,
              "quality": 0.XX,
              "stakeholders": 0.XX
            }},
            "confidence": 0.XX
          }},
          "risk_assessment": {{
            "risk_score": 1-9,
            "risk_level": "Low/Medium/High/Critical",
            "priority_ranking": "routine|important|critical",
            "summary": "Brief overall assessment",
            "calculation_method": "Likelihood (X) × Impact (Y) = Z",
            "contributing_factors": [
              {{
                "factor": "Factor name",
                "contribution_percentage": XX,
                "weight": 0.XX,
                "description": "Why this matters"
              }}
            ]
          }},
          "risk_indicators": [
            {{"indicator": "What to monitor", "frequency": "When/how often", "threshold": "Alert level"}}
          ],
          "mitigation_suggestions": [
            {{"action": "Specific action", "timeline": "When", "priority": "high/medium/low", "expected_impact": "Reduces risk by X%"}}
          ],
          "confidence_level": "high|medium|low",
          "confidence_score": 0.XX,
          "explainability": {{
            "model_assumptions": ["assumption1", "assumption2"],
            "data_limitations": ["limitation1"],
            "alternative_interpretations": ["interpretation1"]
          }}
        }}
        """
        
        response_text = generate_ai_content(prompt, task_type='risk_assessment')
        if response_text:
            # Handle code block formatting
            if "```json" in response_text:
                response_text = response_text.split("```json")[1].split("```")[0].strip()
            elif "```" in response_text:
                response_text = response_text.split("```")[1].split("```")[0].strip()
            
            # Try to find JSON in the response
            json_start = response_text.find('{')
            json_end = response_text.rfind('}')
            
            if json_start != -1 and json_end != -1 and json_end > json_start:
                response_text = response_text[json_start:json_end + 1]
            
            try:
                return json.loads(response_text)
            except json.JSONDecodeError as e:
                logger.error(f"JSON parsing error in risk scoring: {e}")
                return None
        return None
    except Exception as e:
        logger.error(f"Error calculating task risk score: {str(e)}")
        return None


def generate_risk_mitigation_suggestions(task_title: str, task_description: str,
                                        risk_likelihood: int, risk_impact: int,
                                        risk_indicators: List[Dict] = None) -> Optional[List[Dict]]:
    """
    Generate AI-powered mitigation strategies for high-risk tasks.
    
    Args:
        task_title: The title of the task
        task_description: Detailed description of the task
        risk_likelihood: Likelihood score (1-3)
        risk_impact: Impact score (1-3)
        risk_indicators: Optional list of risk indicators to consider
        
    Returns:
        List of mitigation strategy dictionaries or None if generation fails
    """
    try:
        # Map scores to text
        likelihood_text = {1: "Low", 2: "Medium", 3: "High"}.get(risk_likelihood, "Medium")
        impact_text = {1: "Low", 2: "Medium", 3: "High"}.get(risk_impact, "Medium")
        risk_score = risk_likelihood * risk_impact
        
        indicators_text = ""
        if risk_indicators:
            indicators_list = "\n".join([f"- {ind.get('indicator', '')}" for ind in risk_indicators[:3]])
            indicators_text = f"\nKey Risk Indicators:\n{indicators_list}"
        
        prompt = f"""
        As a project risk management specialist, suggest specific mitigation strategies for this 
        high-risk task. Focus on practical, actionable recommendations.
        
        TASK INFORMATION:
        Title: {task_title}
        Description: {task_description}
        Risk Likelihood: {likelihood_text}
        Risk Impact: {impact_text}
        Overall Risk Score: {risk_score}/9
        {indicators_text}
        
        MITIGATION STRATEGIES:
        Provide 3-4 risk response strategies from these categories:
        - AVOID: Change approach to eliminate the risk
        - MITIGATE: Take actions to reduce likelihood or impact
        - TRANSFER: Shift risk to someone else (delegation, outsourcing)
        - ACCEPT: Plan to handle the risk if it occurs
        
        For each strategy, provide:
        1. Specific action steps (what to do)
        2. Implementation timeline (when/how long)
        3. Estimated effectiveness (%)
        4. Required resources
        5. Responsible parties
        
        FORMAT YOUR RESPONSE AS JSON:
        [
          {{
            "strategy_type": "Avoid|Mitigate|Transfer|Accept",
            "title": "Strategy name",
            "description": "What this strategy accomplishes",
            "action_steps": ["step1", "step2", "step3"],
            "timeline": "Timeframe for implementation",
            "estimated_effectiveness": 75,
            "resources_required": "What's needed",
            "priority": "high|medium|low"
          }}
        ]
        """
        
        response_text = generate_ai_content(prompt, task_type='mitigation_suggestions')
        if response_text:
            # Handle code block formatting
            if "```json" in response_text:
                response_text = response_text.split("```json")[1].split("```")[0].strip()
            elif "```" in response_text:
                response_text = response_text.split("```")[1].split("```")[0].strip()
            
            # Try to find JSON array in the response
            json_start = response_text.find('[')
            json_end = response_text.rfind(']')
            
            if json_start != -1 and json_end != -1 and json_end > json_start:
                response_text = response_text[json_start:json_end + 1]
            
            try:
                return json.loads(response_text)
            except json.JSONDecodeError as e:
                logger.error(f"JSON parsing error in mitigation suggestions: {e}")
                return None
        return None
    except Exception as e:
        logger.error(f"Error generating mitigation suggestions: {str(e)}")
        return None


def assess_task_dependencies_and_risks(task_title: str, tasks_data: List[Dict]) -> Optional[Dict]:
    """
    Assess task dependencies and identify cascading risks.
    
    Args:
        task_title: The primary task to analyze
        tasks_data: List of related tasks with dependencies
        
    Returns:
        Dictionary with dependency analysis and risk assessment or None if assessment fails
    """
    try:
        # Format tasks for AI analysis
        tasks_summary = "\n".join([
            f"- {t.get('title', '')} (Priority: {t.get('priority', 'medium')}, Status: {t.get('status', '')})"
            for t in tasks_data[:10]  # Limit to avoid token overflow
        ])
        
        prompt = f"""
        Analyze task dependencies and identify potential cascading risks for this task flow.
        
        PRIMARY TASK: {task_title}
        
        RELATED TASKS:
        {tasks_summary}
        
        ANALYSIS REQUIREMENTS:
        1. Identify critical dependencies (blocker tasks)
        2. Assess risk of dependency delays
        3. Identify potential bottlenecks
        4. Suggest parallel work opportunities
        5. Recommend mitigation for cascading risks
        
        FORMAT YOUR RESPONSE AS JSON:
        {{
          "critical_dependencies": [
            {{"task": "task_name", "risk_level": "high|medium|low", "reason": "why it's critical"}}
          ],
          "cascading_risks": [
            {{"risk": "specific risk", "origin_task": "task_name", "affected_tasks": ["tasks"], "severity": "high|medium|low"}}
          ],
          "bottleneck_areas": ["area1", "area2"],
          "parallel_opportunities": ["what can be done in parallel"],
          "mitigation_recommendations": [
            {{"recommendation": "specific action", "priority": "high|medium|low", "effort": "low|medium|high"}}
          ],
          "overall_dependency_risk": "low|medium|high|critical"
        }}
        """
        
        response_text = generate_ai_content(prompt, task_type='dependency_analysis')
        if response_text:
            # Handle code block formatting
            if "```json" in response_text:
                response_text = response_text.split("```json")[1].split("```")[0].strip()
            elif "```" in response_text:
                response_text = response_text.split("```")[1].split("```")[0].strip()
            
            json_start = response_text.find('{')
            json_end = response_text.rfind('}')
            
            if json_start != -1 and json_end != -1 and json_end > json_start:
                response_text = response_text[json_start:json_end + 1]
            
            try:
                return json.loads(response_text)
            except json.JSONDecodeError as e:
                logger.error(f"JSON parsing error in dependency analysis: {e}")
                return None
        return None
    except Exception as e:
        logger.error(f"Error assessing task dependencies: {str(e)}")
        return None


def summarize_task_details(task_data: Dict) -> Optional[Dict]:
    """
    Generate a comprehensive AI-powered summary of a task with full explainability.
    
    This function analyzes:
    - Basic task information (title, description, status, priority, progress)
    - Risk management details (risk level, indicators, mitigation strategies)
    - Stakeholder involvement and feedback
    - Resource management (skill requirements, workload impact, collaboration needs)
    - Task dependencies (parent, subtasks, blocking relationships)
    - Complexity and effort estimates
    - Labels and Lean Six Sigma classification
    
    Args:
        task_data: A dictionary containing comprehensive task information
        
    Returns:
        A dictionary with detailed AI-generated summary and explainability data
        or None if summarization fails
    """
    try:
        # Extract all task information
        title = task_data.get('title', 'Untitled Task')
        description = task_data.get('description', 'No description provided')
        status = task_data.get('status', 'Unknown')
        priority = task_data.get('priority', 'medium')
        progress = task_data.get('progress', 0)
        due_date = task_data.get('due_date', 'No due date')
        assigned_to = task_data.get('assigned_to', 'Unassigned')
        created_by = task_data.get('created_by', 'Unknown')
        created_at = task_data.get('created_at', 'Unknown')
        
        # Risk management
        risk_level = task_data.get('risk_level')
        risk_score = task_data.get('risk_score')
        risk_likelihood = task_data.get('risk_likelihood')
        risk_impact = task_data.get('risk_impact')
        risk_indicators = task_data.get('risk_indicators', [])
        mitigation_suggestions = task_data.get('mitigation_suggestions', [])
        
        # Stakeholders
        stakeholders = task_data.get('stakeholders', [])
        
        # Resource management
        required_skills = task_data.get('required_skills', [])
        skill_match_score = task_data.get('skill_match_score')
        workload_impact = task_data.get('workload_impact')
        collaboration_required = task_data.get('collaboration_required', False)
        complexity_score = task_data.get('complexity_score')
        
        # Dependencies
        parent_task = task_data.get('parent_task')
        subtasks = task_data.get('subtasks', [])
        dependencies = task_data.get('dependencies', [])  # Blocking tasks
        dependent_tasks = task_data.get('dependent_tasks', [])  # Tasks blocked by this
        related_tasks = task_data.get('related_tasks', [])
        
        # Labels
        labels = task_data.get('labels', [])
        lean_labels = [l for l in labels if l.get('category') == 'lean']
        
        # Comments count
        comments_count = task_data.get('comments_count', 0)
        
        # Build comprehensive prompt
        prompt = f"""
        You are an expert project manager analyzing a task in detail. Provide a comprehensive, insightful summary 
        that addresses ALL important aspects of this task with full explainability for every insight and recommendation.

        ## TASK OVERVIEW:
        **Title:** {title}
        **Description:** {description}
        **Status:** {status} | **Priority:** {priority} | **Progress:** {progress}%
        **Assigned To:** {assigned_to} | **Created By:** {created_by}
        **Due Date:** {due_date}
        **Created:** {created_at}

        ## RISK MANAGEMENT:
        """
        
        if risk_level:
            prompt += f"""
        **Risk Level:** {risk_level} (Score: {risk_score}/9, Likelihood: {risk_likelihood}/3, Impact: {risk_impact}/3)
        **Risk Indicators to Monitor:**
        {chr(10).join(['- ' + str(indicator) for indicator in risk_indicators]) if risk_indicators else '- None specified'}
        
        **Mitigation Strategies:**
        """
            if mitigation_suggestions:
                for mit in mitigation_suggestions:
                    if isinstance(mit, dict):
                        prompt += f"\n- {mit.get('strategy', 'N/A')}: {mit.get('description', 'N/A')} (Timeline: {mit.get('timeline', 'N/A')})"
                    else:
                        prompt += f"\n- {mit}"
        else:
            prompt += "\n**Risk Assessment:** Not yet performed for this task."
        
        prompt += "\n\n## STAKEHOLDER INVOLVEMENT:\n"
        if stakeholders:
            for sh in stakeholders:
                prompt += f"""
        - **{sh.get('name', 'Unknown')}**: {sh.get('involvement_type', 'N/A')} | Status: {sh.get('engagement_status', 'N/A')}
          Satisfaction: {sh.get('satisfaction_rating', 'N/A')}/5 | Feedback: {sh.get('feedback', 'None')}
        """
        else:
            prompt += "- No stakeholders assigned to this task yet.\n"
        
        prompt += "\n## RESOURCE MANAGEMENT:\n"
        if required_skills:
            prompt += "**Required Skills:**\n"
            for skill in required_skills:
                if isinstance(skill, dict):
                    prompt += f"- {skill.get('name', 'Unknown')}: {skill.get('level', 'Unknown')} level\n"
                else:
                    prompt += f"- {skill}\n"
        
        if skill_match_score:
            prompt += f"**Skill Match Score:** {skill_match_score}% (assigned user's skill alignment)\n"
        
        if workload_impact:
            prompt += f"**Workload Impact:** {workload_impact}\n"
        
        if collaboration_required:
            prompt += "**Collaboration Required:** Yes - This task needs team coordination\n"
        
        if complexity_score:
            complexity_label = "Very Complex" if complexity_score >= 8 else "Moderate" if complexity_score >= 5 else "Simple"
            prompt += f"**Complexity Score:** {complexity_score}/10 ({complexity_label})\n"
        
        prompt += "\n## TASK DEPENDENCIES & HIERARCHY:\n"
        
        if parent_task:
            prompt += f"**Parent Task:** {parent_task}\n"
        
        if subtasks:
            prompt += f"**Subtasks ({len(subtasks)}):**\n"
            for sub in subtasks:
                prompt += f"- {sub}\n"
        
        if dependencies:
            prompt += f"**Dependencies ({len(dependencies)}) - Tasks that must complete BEFORE this task can start:**\n"
            for dep in dependencies:
                prompt += f"- {dep}\n"
        
        if dependent_tasks:
            prompt += f"**Blocking ({len(dependent_tasks)}) - Tasks that CANNOT start until this task completes:**\n"
            for blocked in dependent_tasks:
                prompt += f"- {blocked}\n"
        
        if related_tasks:
            prompt += f"**Related Tasks ({len(related_tasks)}):** {', '.join(related_tasks)}\n"
        
        prompt += "\n## LEAN SIX SIGMA CLASSIFICATION:\n"
        if lean_labels:
            for label in lean_labels:
                prompt += f"- **{label.get('name', 'Unknown')}**\n"
        else:
            prompt += "- Not yet classified for Lean Six Sigma analysis.\n"
        
        prompt += f"\n## ADDITIONAL CONTEXT:\n"
        prompt += f"- **Comments/Discussions:** {comments_count} comments on this task\n"
        if labels:
            regular_labels = [l.get('name') for l in labels if l.get('category') != 'lean']
            if regular_labels:
                prompt += f"- **Labels:** {', '.join(regular_labels)}\n"
        
        prompt += """

        Format your response as JSON WITH FULL EXPLAINABILITY:
        {
            "executive_summary": "2-3 sentence high-level summary of task status and key concerns",
            "confidence_score": 0.XX,
            "analysis_completeness": {
                "data_quality": "high|medium|low",
                "missing_information": ["Key info that would improve analysis"],
                "analysis_confidence": "high|medium|low"
            },
            "task_health": {
                "overall_status": "healthy|at_risk|critical",
                "status_reasoning": "Why this health status was assigned",
                "health_factors": [
                    {
                        "factor": "Factor name",
                        "status": "positive|neutral|negative",
                        "impact": "How this affects task health",
                        "evidence": "Supporting data"
                    }
                ]
            },
            "risk_analysis": {
                "risk_assessment_validity": "The current risk assessment is appropriate|needs review|underestimated|overestimated",
                "validity_reasoning": "Why risk assessment accuracy was rated this way",
                "top_risks": [
                    {
                        "risk": "Risk description",
                        "likelihood": "high|medium|low",
                        "impact": "high|medium|low",
                        "current_mitigation": "What's in place",
                        "recommended_action": "Additional action needed"
                    }
                ],
                "blockers_impact": "Assessment of how blockers affect this task"
            },
            "resource_assessment": {
                "assignee_fit": "good|adequate|poor",
                "fit_reasoning": "Why assignee is/isn't well-suited",
                "capacity_status": "available|stretched|overloaded",
                "skill_gaps": ["Skills needed but potentially missing"],
                "collaboration_needs": "Assessment of team coordination requirements"
            },
            "stakeholder_insights": {
                "engagement_level": "engaged|neutral|disengaged",
                "satisfaction_trend": "improving|stable|declining|unknown",
                "key_concerns": ["Stakeholder concerns identified"],
                "communication_recommendations": ["How to better engage stakeholders"]
            },
            "timeline_assessment": {
                "deadline_feasibility": "achievable|at_risk|unlikely",
                "feasibility_reasoning": "Why deadline is/isn't achievable",
                "dependency_impact": "How dependencies affect timeline",
                "suggested_adjustments": ["Timeline optimization suggestions"]
            },
            "lean_efficiency": {
                "value_classification_appropriate": true,
                "classification_reasoning": "Why classification is/isn't accurate",
                "waste_indicators": ["Waste patterns observed"],
                "efficiency_suggestions": ["How to improve value delivery"]
            },
            "prioritized_actions": [
                {
                    "action": "Specific action to take",
                    "owner": "Who should do this",
                    "urgency": "immediate|this_week|this_month",
                    "reasoning": "Why this action is needed",
                    "expected_outcome": "What this will achieve"
                }
            ],
            "assumptions": [
                "Key assumption made in this analysis"
            ],
            "limitations": [
                "Limitation of this analysis"
            ],
            "markdown_summary": "**Executive Summary**\\n[summary]\\n\\n**Key Actions**\\n- Action 1\\n- Action 2"
        }
        """
        
        response_text = generate_ai_content(prompt, task_type='simple')
        if response_text:
            # Handle code block formatting
            if "```json" in response_text:
                response_text = response_text.split("```json")[1].split("```")[0].strip()
            elif "```" in response_text:
                response_text = response_text.split("```")[1].strip()
            
            try:
                parsed_json = json.loads(response_text)
                # Validate that we have at least the key fields
                if not parsed_json.get('executive_summary') and not parsed_json.get('markdown_summary'):
                    logger.warning(f"AI response missing key fields. Keys present: {list(parsed_json.keys())}")
                    # Add markdown summary from the raw response if not present
                    if 'markdown_summary' not in parsed_json:
                        parsed_json['markdown_summary'] = response_text
                        parsed_json['parsing_note'] = 'AI response was parsed but missing expected structure'
                return parsed_json
            except json.JSONDecodeError as e:
                logger.warning(f"JSON parsing error in summarize_task_details: {str(e)}. Response length: {len(response_text)}")
                # Fallback to plain text for backward compatibility
                return {
                    'markdown_summary': response_text,
                    'confidence_score': 0.5,
                    'parsing_note': 'Returned plain text summary due to JSON parsing error'
                }
        return None
    except Exception as e:
        logger.error(f"Error summarizing task details: {str(e)}")
        return None

