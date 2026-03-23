"""
Utility module for integrating with Google Generative AI (Gemini) API.

This module provides helper functions to call the Gemini API for various
AI-powered features in the PrizmAI application.
"""
import os
import re
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
    'column_recommendations',
    'workspace_generation',
    'assignee_suggestion',
    'proxy_metrics',            # Goal-Aware Analytics: deeper reasoning for outcome indicators
]

SIMPLE_TASKS = [
    'task_description',
    'comment_summary',
    'lean_classification',
    'task_enhancement',
    'mitigation_suggestions',
    'board_classification',      # Goal-Aware Analytics: short JSON classification
    'analytics_narrative',       # Goal-Aware Analytics: 2-sentence board narrative
    'portfolio_narrative',       # Goal-Aware Analytics: portfolio-level narrative
]

# Temperature settings for different AI task types
# Lower = more deterministic/consistent, Higher = more creative/varied
TASK_TEMPERATURE_MAP = {
    # Deterministic tasks (0.2-0.3) - Need consistent, predictable outputs
    'column_recommendations': 0.3,      # Same project should get similar column structure
    'board_setup': 0.2,                  # Phase count, team size should be consistent
    'task_breakdown': 0.3,               # Subtask structure should be predictable
    'resource_optimization': 0.3,        # Workload calculations need consistency
    'workspace_generation': 0.4,          # Goal-to-workspace: structured yet thoughtful
    
    # Analytical tasks (0.4) - Data-driven with professional narrative
    'risk_assessment': 0.4,              # Risk identification should be thorough & consistent
    'board_analytics_summary': 0.4,      # Analytics reports need reliability
    'priority_suggestion': 0.4,          # Priority should be consistent for similar tasks
    'deadline_prediction': 0.4,          # Deadline estimates need consistency
    'skill_gap_analysis': 0.4,           # Skill assessments should be reliable
    'budget_analysis': 0.4,              # Financial analysis needs accuracy
    'team_performance': 0.4,             # Performance reports should be consistent
    'dependency_analysis': 0.4,          # Dependency analysis should be reliable
    'critical_path': 0.4,                # Critical path needs accuracy
    'workflow_optimization': 0.4,        # Workflow suggestions should be consistent
    'assignee_suggestion': 0.3,          # Assignee matching should be highly consistent & factual
    
    # Dashboard/Insights (0.5) - Analytical with slight variation for freshness
    'dashboard_insights': 0.5,           # Insights can have slight variation
    'timeline_generation': 0.5,          # Timeline needs accuracy with some flexibility
    
    # Creative content (0.6) - Natural language, readability matters
    'task_description': 0.6,             # Descriptions should be varied but professional
    'retrospective': 0.6,                # Retrospectives benefit from thoughtful variation
    'comment_summary': 0.6,              # Summaries should read naturally
    
    # Conversational (0.7) - Engaging, human-like responses
    'chat': 0.7,                         # Chat should feel natural
    'lean_classification': 0.5,          # Classification with explanation
    'task_enhancement': 0.6,             # Enhancement suggestions
    'mitigation_suggestions': 0.5,       # Mitigation advice
    
    # Goal-Aware Analytics
    'board_classification': 0.2,         # Deterministic project-type classification
    'analytics_narrative': 0.4,          # Data-driven 2-sentence narrative
    'portfolio_narrative': 0.4,          # Portfolio-level data storytelling
    'proxy_metrics': 0.5,               # Balanced reasoning for outcome indicators
    
    # Defaults
    'simple': 0.6,                       # Default for simple tasks
    'complex': 0.4,                      # Default for complex tasks
}

# Token limits for different AI task types
# Lower limits = faster responses, Higher limits = more detailed outputs
# Optimized for latency while maintaining quality - increased to prevent JSON truncation
TASK_TOKEN_LIMITS = {
    # Short responses (2048-2560 tokens) - generous limits to ensure complete responses with explainability
    'lean_classification': 2560,          # Classification + detailed explanation + confidence + alternatives
    'comment_summary': 3072,              # Summary with sentiment analysis, action items, and participant analysis
    'mitigation_suggestions': 3072,       # Mitigation strategies with action steps + per-strategy reasoning
    
    # Medium responses (2560-3072 tokens)
    'task_description': 2560,            # Description + checklist + confidence + reasoning + assumptions
    'priority_suggestion': 3072,         # Priority with full comparison and recommendations
    'dashboard_insights': 2560,          # Quick insights with reasoning
    'velocity_forecast': 2560,           # Forecast data with explanations
    'simple': 2560,                      # Default for simple tasks - generous for explainability
    
    # Standard responses (3072-4096 tokens)
    'task_enhancement': 4096,            # Enhanced description + checklist + acceptance criteria + reasoning
    'board_analytics_summary': 4096,     # Comprehensive analytics with health factors + explainability
    'risk_assessment': 4096,             # Risk analysis with mitigation and explainability
    'retrospective': 4096,               # Retrospective summary with patterns and recommendations
    'skill_gap_analysis': 4096,          # Skill analysis with recommendations
    'assignee_suggestion': 4096,         # Assignee analysis with multi-factor scoring + explainability
    'budget_analysis': 4096,             # Budget insights with trends and recommendations
    'dependency_analysis': 4096,         # Dependency and cascading risk analysis
    'deadline_prediction': 2560,         # Timeline prediction with confidence and reasoning
    
    # Extended responses (4096-8192 tokens) - complex nested JSON structures
    'workflow_optimization': 6144,       # Workflow analysis with bottlenecks and recommendations
    'task_breakdown': 3072,              # Subtask list with per-subtask reasoning
    'critical_path': 8192,               # Critical path with task analysis and scheduling
    'complex': 8192,                     # General complex analysis tasks - comprehensive JSON
    'timeline_generation': 6144,         # Timeline details with milestones + explainability
    
    # Large responses (8192+ tokens) - extensive board-wide analysis
    'column_recommendations': 8192,      # Complex structure with full explainability (4-7 columns)
    'board_setup': 6144,                 # Full board configuration with explainability
    'task_summary': 8192,                # Comprehensive task summary with all aspects analyzed
    'workspace_generation': 8192,        # Full workspace hierarchy: goal → missions → strategies → boards → tasks
    'status_report': 4096,               # Status report with RAG reasoning + explainability metadata
    'board_summary': 4096,               # Board summary with confidence + data completeness
    'prizmbrief': 6144,                  # PrizmBrief slides (8-10 slides) + data sources slide
    
    # Goal-Aware Analytics
    'board_classification': 512,          # Short JSON: {project_type, confidence, reason}
    'analytics_narrative': 256,           # 2 sentences plain text
    'portfolio_narrative': 512,           # Portfolio-level narrative (slightly longer)
    'proxy_metrics': 1024,               # JSON array of 3 proxy metric objects
    
    # Default
    'default': 4096,                     # Default for unspecified tasks - generous to prevent truncation
}

def get_token_limit_for_task(task_type: str) -> int:
    """
    Get the appropriate max_output_tokens for a given task type.
    
    Args:
        task_type: The type of AI task being performed
        
    Returns:
        int: Maximum output tokens for this task
    """
    return TASK_TOKEN_LIMITS.get(task_type, TASK_TOKEN_LIMITS['default'])

def get_temperature_for_task(task_type: str) -> float:
    """
    Get the appropriate temperature setting for a given task type.
    
    Args:
        task_type: The type of AI task being performed
        
    Returns:
        float: Temperature value between 0.0 and 1.0
    """
    return TASK_TEMPERATURE_MAP.get(task_type, 0.5)  # Default to 0.5 if unknown

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
                _model_flash = genai.GenerativeModel('gemini-2.5-flash')
                logger.info("Gemini 2.5 Flash model instance created")
            logger.debug(f"Using Gemini 2.5 Flash for task: {task_type}")
            return _model_flash
        else:
            if _model_flash_lite is None:
                _model_flash_lite = genai.GenerativeModel('gemini-2.5-flash')
                logger.info("Gemini 2.5 Flash model instance created")
            logger.debug(f"Using Gemini 2.5 Flash for task: {task_type}")
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

def generate_ai_content(prompt: str, task_type='simple', use_cache: bool = True, 
                        context_id: Optional[str] = None) -> Optional[str]:
    """
    Generate content using Gemini API with smart model routing, optimized temperature, and caching.
    
    Routes requests to appropriate model based on task complexity:
    - Complex tasks → Gemini 2.5 Flash (higher quality reasoning)
    - Simple tasks → Gemini 2.5 Flash-Lite (faster, cheaper)
    
    Temperature is automatically set based on task type:
    - Deterministic tasks (0.2-0.3): column_recommendations, board_setup, task_breakdown
    - Analytical tasks (0.4): risk_assessment, analytics, priority_suggestion
    - Creative tasks (0.6): task_description, retrospective
    - Conversational (0.7): chat responses
    
    Caching is enabled by default to reduce API costs.
    
    Args:
        prompt: The prompt to send to the Gemini API
        task_type: Task complexity indicator ('simple', 'complex', or specific task name)
        use_cache: Whether to use caching (default True, set False for unique responses)
        context_id: Optional identifier for cache context (e.g., board_id)
        
    Returns:
        Generated content or None if generation fails
    """
    # Import caching system
    try:
        from kanban_board.ai_cache import ai_cache_manager, get_ttl_for_operation
    except ImportError:
        use_cache = False
        logger.warning("AI cache module not available, running without cache")
    
    # Check cache first if enabled
    if use_cache:
        cached = ai_cache_manager.get(prompt, task_type, context_id)
        if cached is not None:
            logger.debug(f"AI content cache HIT for task_type: {task_type}")
            return cached
    
    try:
        model = get_model_for_task(task_type)
        if not model:
            logger.error("Gemini model not available")
            return None
        
        # Get optimized temperature for this task type
        temperature = get_temperature_for_task(task_type)
        
        # Get optimized token limit for this task type (reduces latency)
        max_tokens = get_token_limit_for_task(task_type)
        
        # Create generation config with task-specific temperature and token limits
        generation_config = {
            'temperature': temperature,
            'top_p': 0.8,
            'top_k': 40,
            'max_output_tokens': max_tokens,
        }
        
        logger.debug(f"Generating AI content - Task: {task_type}, Temperature: {temperature}, MaxTokens: {max_tokens}")
        
        # Generate content with optimized settings (60s hard timeout prevents hangs)
        response = model.generate_content(
            prompt,
            generation_config=generation_config,
            request_options={"timeout": 60},
        )
        
        if response and response.text:
            result = response.text.strip()
            
            # Cache the result if caching is enabled
            if use_cache and result:
                ai_cache_manager.set(prompt, result, task_type, context_id)
                logger.debug(f"AI content cached for task_type: {task_type}")
            
            return result
        
        logger.warning("Empty response from Gemini API")
        return None
        
    except Exception as e:
        logger.error(f"Error generating AI content: {str(e)}")
        return None

def generate_task_description(title: str, context: Optional[Dict] = None) -> Optional[Dict]:
    """
    Generate a structured task description with deliverables and obstacles from a task title.
    
    Args:
        title: The title of the task
        context: Optional context (board name, project type, etc.)
        
    Returns:
        A dictionary with generated description sections or None if generation fails
    """
    try:
        context_info = ""
        if context:
            context_parts = []
            if context.get('board_name'):
                context_parts.append(f"Project: {context['board_name']}")
            if context.get('current_description'):
                context_parts.append(f"Current description (improve upon this): {context['current_description'][:500]}")
            if context.get('priority'):
                context_parts.append(f"Priority: {context['priority']}")
            if context.get('assigned_to'):
                context_parts.append(f"Assigned to: {context['assigned_to']}")
            if context.get('lss_classification'):
                context_parts.append(f"LSS Classification: {context['lss_classification']}")
            if context.get('complexity_score'):
                context_parts.append(f"Complexity Score: {context['complexity_score']}/10")
            if context.get('recent_comments'):
                context_parts.append(f"Recent discussion: {'; '.join(context['recent_comments'][:3])[:300]}")
            context_info = "\n".join(context_parts)
        
        prompt = f"""Generate a task description for: "{title}"
{context_info}

RULES:
- DO NOT include time estimates, effort predictions, or deadlines
- DO NOT suggest priority levels
- Keep each section brief and actionable
- Include explainability fields so the user understands how this description was generated

Return JSON only:
{{
    "objective": "1-2 sentence goal",
    "key_deliverables": ["Deliverable 1", "Deliverable 2", "Deliverable 3"],
    "action_steps": ["Step 1", "Step 2", "Step 3", "Step 4"],
    "potential_obstacles": ["Risk/obstacle 1", "Risk/obstacle 2"],
    "success_criteria": "How to know this task is complete",
    "confidence_score": 0.0 to 1.0 representing how confident you are in this description given the available context,
    "reasoning": "One sentence explaining the basis for this description, e.g. what the title implied",
    "assumptions": ["Assumption 1 you made since only a title was provided", "Assumption 2"]
}}"""
        
        response_text = generate_ai_content(prompt, task_type='task_description')
        if response_text:
            # Handle code block formatting
            if "```json" in response_text:
                response_text = response_text.split("```json")[1].split("```")[0].strip()
            elif "```" in response_text:
                response_text = response_text.split("```")[1].strip()
            
            try:
                result = json.loads(response_text)
                
                # Build markdown description from structured data
                md_parts = []
                if result.get('objective'):
                    md_parts.append(f"**Objective:** {result['objective']}")
                
                if result.get('key_deliverables'):
                    md_parts.append("\n**Key Deliverables:**")
                    for item in result['key_deliverables'][:5]:
                        md_parts.append(f"- {item}")
                
                if result.get('action_steps'):
                    md_parts.append("\n**Action Steps:**")
                    for item in result['action_steps'][:6]:
                        md_parts.append(f"- [ ] {item}")
                
                if result.get('potential_obstacles'):
                    md_parts.append("\n**Potential Obstacles:**")
                    for item in result['potential_obstacles'][:3]:
                        md_parts.append(f"- {item}")
                
                if result.get('success_criteria'):
                    md_parts.append(f"\n**Success Criteria:** {result['success_criteria']}")
                
                # Add explainability note to the markdown
                if result.get('assumptions'):
                    md_parts.append("\n**AI Assumptions:**")
                    for assumption in result['assumptions'][:4]:
                        md_parts.append(f"- _{assumption}_")
                
                result['markdown_description'] = "\n".join(md_parts)
                # Ensure explainability fields are present in the returned dict
                result.setdefault('confidence_score', 0.5)
                result.setdefault('reasoning', 'Generated based on the task title.')
                result.setdefault('assumptions', [])
                return result
                
            except json.JSONDecodeError:
                # Fallback: return the text as markdown
                return {
                    'markdown_description': response_text,
                    'parsing_note': 'Returned plain text due to JSON parsing error'
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

def suggest_lean_classification(title: str, description: str, estimated_cost: float = None, estimated_hours: float = None, hourly_rate: float = None, task_context: dict = None) -> Optional[Dict]:
    """
    Suggest Lean Six Sigma classification for a task based on its title, description, and context data.
    
    Provides explainable AI output including confidence scores, contributing factors,
    and alternative classifications to support user decision-making.
    
    Args:
        title: The task title
        description: The task description
        estimated_cost: Estimated cost for this task (optional)
        estimated_hours: Estimated hours to complete (optional)
        hourly_rate: Hourly rate for labor cost calculation (optional)
        task_context: Optional dict with priority, complexity_score, dependencies_count,
                      collaboration_required, risk_level, risk_score, etc.
        
    Returns:
        A dictionary with suggested classification, justification, confidence,
        and explainability data or None if suggestion fails
    """
    try:
        # Build budget context string
        budget_context = ""
        if estimated_cost is not None or estimated_hours is not None or hourly_rate is not None:
            budget_parts = []
            if estimated_cost is not None and estimated_cost > 0:
                budget_parts.append(f"Estimated Cost: ${estimated_cost:,.2f}")
            if estimated_hours is not None and estimated_hours > 0:
                budget_parts.append(f"Estimated Hours: {estimated_hours:.1f} hours")
            if hourly_rate is not None and hourly_rate > 0:
                budget_parts.append(f"Hourly Rate: ${hourly_rate:.2f}/hr")
                if estimated_hours is not None and estimated_hours > 0:
                    labor_cost = estimated_hours * hourly_rate
                    budget_parts.append(f"Estimated Labor Cost: ${labor_cost:,.2f}")
            if budget_parts:
                budget_context = "\n\nBudget/Effort context:\n- " + "\n- ".join(budget_parts)
        
        # Build enhanced context from task_context if provided
        enhanced_context = ""
        if task_context:
            context_parts = []
            if task_context.get('priority'):
                context_parts.append(f"Priority: {task_context['priority']}")
            if task_context.get('complexity_score') is not None:
                score = task_context['complexity_score']
                label = "Very Complex" if score >= 8 else "Moderate" if score >= 5 else "Simple"
                context_parts.append(f"Complexity: {score}/10 ({label})")
            if task_context.get('dependencies_count') is not None and int(task_context.get('dependencies_count', 0)) > 0:
                context_parts.append(f"Dependencies: {task_context['dependencies_count']} blocking task(s)")
            if task_context.get('collaboration_required'):
                context_parts.append("Collaboration Required: Yes")
            if task_context.get('risk_level'):
                context_parts.append(f"Risk Level: {task_context['risk_level']}")
            if task_context.get('risk_score') is not None:
                context_parts.append(f"Risk Score: {task_context['risk_score']}/9")
            if task_context.get('due_date'):
                context_parts.append(f"Due Date: {task_context['due_date']}")
            if context_parts:
                enhanced_context = "\n\nTask Context:\n- " + "\n- ".join(context_parts)
        
        prompt = f"""Analyze this task for Lean Six Sigma classification. Task: "{title}". Description: "{description or 'None'}".{budget_context}{enhanced_context}

Classifications: Value-Added (directly transforms the product/service and delivers customer value), Necessary Non-Value-Added (required process step that supports quality or compliance but does not directly deliver customer value), Waste/Eliminate (genuinely redundant, duplicated, or avoidable work that should be removed).

CRITICAL CLASSIFICATION RULE: Tasks that involve testing, security, quality assurance, compliance, documentation, code review, audit, validation, verification, certification, legal/regulatory requirements, or any form of mandatory oversight MUST be classified as "Necessary Non-Value-Added". These are essential process steps. Only classify a task as "Waste/Eliminate" when it is provably redundant, duplicated effort, or a process step that can be eliminated without any loss of quality, value, or compliance.

Return ONLY valid JSON with NO line breaks inside strings:
{{"classification":"Value-Added|Necessary Non-Value-Added|Waste/Eliminate","justification":"Brief reason in one sentence","confidence_score":0.XX,"confidence_level":"high|medium|low","contributing_factors":[{{"factor":"Factor1","contribution_percentage":XX,"description":"Brief desc"}}],"classification_reasoning":{{"value_added_indicators":["indicator1"],"non_value_indicators":["indicator1"],"primary_driver":"Main reason"}},"alternative_classification":{{"classification":"Alternative","confidence_score":0.XX,"conditions":"When applies"}},"assumptions":["assumption1"],"improvement_suggestions":["suggestion1"],"lean_waste_type":null,"data_quality":"high|medium|low"}}"""
        
        response_text = generate_ai_content(prompt, task_type='lean_classification')
        if response_text:
            # Log the raw response for debugging - write to file for inspection
            logger.warning(f"Raw LSS response length: {len(response_text)}")
            try:
                with open('lss_debug_response.txt', 'w', encoding='utf-8') as f:
                    f.write(response_text)
                logger.info("Wrote raw LSS response to lss_debug_response.txt")
            except Exception as write_err:
                logger.error(f"Could not write debug file: {write_err}")
            
            # Handle the case where the AI might include code block formatting
            if "```json" in response_text:
                response_text = response_text.split("```json")[1].split("```")[0].strip()
            elif "```" in response_text:
                response_text = response_text.split("```")[1].strip()
            
            # Clean up potential JSON issues before parsing
            response_text = response_text.strip()
            
            # Try parsing with json.loads first
            try:
                return json.loads(response_text)
            except json.JSONDecodeError as json_err:
                logger.warning(f"Initial JSON parse failed: {str(json_err)}, attempting cleanup")
                # Log problematic area
                error_pos = json_err.pos if hasattr(json_err, 'pos') else 395
                start = max(0, error_pos - 50)
                end = min(len(response_text), error_pos + 50)
                logger.warning(f"JSON around error position {error_pos}: ...{repr(response_text[start:end])}...")
                
                # Strategy 0: Handle truncated JSON (common with AI responses)
                # Try to extract fields from partial/truncated JSON
                def extract_from_truncated_json(text):
                    """Extract key fields from truncated JSON response"""
                    result = {}
                    
                    # Extract classification
                    class_match = re.search(r'"classification"\s*:\s*"([^"]+)"', text)
                    if class_match:
                        result['classification'] = class_match.group(1)
                    
                    # Extract justification
                    just_match = re.search(r'"justification"\s*:\s*"([^"]+)"', text)
                    if just_match:
                        result['justification'] = just_match.group(1)
                    
                    # Extract confidence_score
                    conf_match = re.search(r'"confidence_score"\s*:\s*([\d.]+)', text)
                    if conf_match:
                        result['confidence_score'] = float(conf_match.group(1))
                    
                    # Extract confidence_level
                    level_match = re.search(r'"confidence_level"\s*:\s*"([^"]+)"', text)
                    if level_match:
                        result['confidence_level'] = level_match.group(1)
                    
                    return result if 'classification' in result else None
                
                # Try extraction from truncated response first
                extracted = extract_from_truncated_json(response_text)
                if extracted and 'classification' in extracted:
                    logger.info(f"Extracted fields from truncated JSON: {list(extracted.keys())}")
                    # Build a complete response with extracted data
                    return {
                        "classification": extracted.get('classification', 'Value-Added'),
                        "justification": extracted.get('justification', 'Classification based on task analysis.'),
                        "confidence_score": extracted.get('confidence_score', 0.7),
                        "confidence_level": extracted.get('confidence_level', 'medium'),
                        "contributing_factors": [],
                        "classification_reasoning": {
                            "value_added_indicators": [],
                            "non_value_indicators": [],
                            "primary_driver": extracted.get('justification', 'Task analysis')[:100] if extracted.get('justification') else 'Task analysis'
                        },
                        "alternative_classification": None,
                        "assumptions": [],
                        "improvement_suggestions": [],
                        "lean_waste_type": None
                    }
                
                # Aggressive cleanup strategy: Fix multi-line strings
                # The issue is that AI generates strings with literal newlines
                def fix_multiline_strings(text):
                    """Replace literal newlines inside JSON strings with escaped \\n"""
                    result = []
                    in_string = False
                    escape_next = False
                    i = 0
                    
                    while i < len(text):
                        char = text[i]
                        
                        if escape_next:
                            result.append(char)
                            escape_next = False
                            i += 1
                            continue
                        
                        if char == '\\':
                            result.append(char)
                            escape_next = True
                            i += 1
                            continue
                        
                        if char == '"':
                            in_string = not in_string
                            result.append(char)
                            i += 1
                            continue
                        
                        if in_string and char in '\n\r':
                            # Replace literal newline with escaped version
                            if char == '\n':
                                result.append('\\n')
                            else:
                                result.append('\\r')
                            i += 1
                            continue
                        
                        result.append(char)
                        i += 1
                    
                    return ''.join(result)
                
                # Try multiple cleanup strategies
                cleaned_text = response_text
                
                # Strategy 1: Fix multi-line strings (most likely cause of "Unterminated string")
                try:
                    cleaned_text = fix_multiline_strings(response_text)
                    return json.loads(cleaned_text)
                except json.JSONDecodeError as e:
                    logger.debug(f"Strategy 1 (fix multiline) failed: {e}")
                
                # Strategy 2: Replace single quotes with double quotes (common AI mistake)
                try:
                    cleaned_text = fix_multiline_strings(response_text)
                    # Replace single-quoted strings: 'value' -> "value"
                    cleaned_text = re.sub(r"'([^']+)'(\s*:)", r'"\1"\2', cleaned_text)
                    cleaned_text = re.sub(r":\s*'([^']*)'", r': "\1"', cleaned_text)
                    return json.loads(cleaned_text)
                except json.JSONDecodeError as e:
                    logger.debug(f"Strategy 2 (single quotes) failed: {e}")
                
                # Strategy 3: Remove trailing commas
                try:
                    cleaned_text = fix_multiline_strings(response_text)
                    cleaned_text = re.sub(r',\s*}', '}', cleaned_text)
                    cleaned_text = re.sub(r',\s*]', ']', cleaned_text)
                    return json.loads(cleaned_text)
                except json.JSONDecodeError as e:
                    logger.debug(f"Strategy 3 (trailing commas) failed: {e}")
                
                # Strategy 4: Try ast.literal_eval for Python dict syntax
                try:
                    import ast
                    parsed = ast.literal_eval(response_text)
                    return parsed
                except (ValueError, SyntaxError) as e:
                    logger.debug(f"Strategy 4 (ast.literal_eval) failed: {e}")
                
                logger.error(f"All JSON cleanup strategies failed for LSS classification")
                # Last resort: try to extract just the classification
                try:
                    # Extract just the classification field if possible (try both quote styles)
                    classification_match = re.search(r'["\']classification["\']\s*:\s*["\']([^"\']+)["\']', response_text)
                    if classification_match:
                        classification = classification_match.group(1)
                        # Return minimal valid response
                        return {
                            "classification": classification,
                            "justification": "AI-generated response had formatting issues, using classification only.",
                            "confidence_score": 0.5,
                            "confidence_level": "low",
                            "contributing_factors": [],
                            "classification_reasoning": {
                                "value_added_indicators": [],
                                "non_value_indicators": [],
                                "primary_driver": "Unable to parse full reasoning"
                            },
                            "alternative_classification": None,
                            "assumptions": [],
                            "improvement_suggestions": [],
                            "lean_waste_type": None
                        }
                except Exception:
                    pass
                
                # If all else fails, return None
                return None
        return None
    except Exception as e:
        logger.error(f"Error suggesting lean classification: {str(e)}")
        return None


def _transform_analytics_response(parsed: Dict) -> Dict:
    """
    Transform simplified AI response to full format for backward compatibility.
    Maps new streamlined fields to legacy structure expected by frontend.
    """
    # If already in old format, return as-is
    if 'health_assessment' in parsed:
        return parsed
    
    # Transform simplified response to expected format
    result = {
        'executive_summary': parsed.get('executive_summary', ''),
        'confidence_score': 0.75,  # Default confidence
    }
    
    # Map health_score -> health_assessment
    if 'health_score' in parsed or 'health_reasoning' in parsed:
        result['health_assessment'] = {
            'overall_score': parsed.get('health_score', 'at_risk'),
            'score_reasoning': parsed.get('health_reasoning', ''),
            'health_indicators': []
        }
    
    # Map key_insights (format is compatible)
    if 'key_insights' in parsed:
        result['key_insights'] = parsed['key_insights']
    
    # Map concerns -> areas_of_concern
    if 'concerns' in parsed:
        result['areas_of_concern'] = [
            {
                'concern': c.get('concern', ''),
                'severity': c.get('severity', 'medium'),
                'recommended_action': c.get('action', ''),
            }
            for c in parsed.get('concerns', [])
        ]
    
    # Map recommendations -> process_improvement_recommendations
    if 'recommendations' in parsed:
        result['process_improvement_recommendations'] = [
            {
                'recommendation': r.get('recommendation', ''),
                'expected_impact': r.get('impact', ''),
                'priority': r.get('priority', 1),
                'implementation_effort': 'medium',
            }
            for r in parsed.get('recommendations', [])
        ]
    
    # Map lean_efficiency -> lean_analysis
    if 'lean_efficiency' in parsed:
        result['lean_analysis'] = {
            'value_stream_efficiency': parsed.get('lean_efficiency', 'fair'),
            'efficiency_reasoning': '',
            'waste_identification': [],
        }
    
    # Map team metrics
    if 'workload_balance' in parsed:
        result['team_performance'] = {
            'workload_balance': parsed.get('workload_balance', 'balanced'),
        }
    
    # Map trend
    if 'productivity_trend' in parsed:
        result['trend_analysis'] = {
            'productivity_trend': parsed.get('productivity_trend', 'stable'),
        }
    
    return result


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
        
        # Build optimized prompt - streamlined for faster response while maintaining quality
        prompt = f"""Analyze this board data and provide actionable insights for a project manager.

## Metrics:
- Tasks: {total_tasks} total, {completed_count} complete ({productivity}% productivity)
- Overdue: {overdue_count}, Due soon: {upcoming_count}
- Lean: {value_added_percentage}% value-added (target: 60%+), {total_categorized} categorized
- Columns: {', '.join([f"{col['name']}:{col['count']}" for col in tasks_by_column])}
- Priority: {', '.join([f"{pri['priority']}:{pri['count']}" for pri in tasks_by_priority])}
- Team: {', '.join([f"{user['username']}:{user['count']}tasks({user['completion_rate']}%)" for user in tasks_by_user[:5]])}

Return JSON only:
{{
  "executive_summary": "2-3 sentences summarizing health and key findings",
  "health_score": "healthy|at_risk|critical",
  "health_reasoning": "Brief explanation",
  "key_insights": [
    {{"insight": "Finding", "evidence": "Data point", "confidence": "high|medium|low"}}
  ],
  "concerns": [
    {{"concern": "Issue", "severity": "critical|high|medium|low", "action": "Recommendation"}}
  ],
  "recommendations": [
    {{"recommendation": "Action", "impact": "Expected result", "priority": 1}}
  ],
  "lean_efficiency": "excellent|good|fair|poor",
  "workload_balance": "balanced|imbalanced",
  "productivity_trend": "improving|stable|declining"
}}"""
        
        response_text = generate_ai_content(prompt, task_type='board_analytics_summary')
        if response_text:
            logger.debug(f"Raw AI response (first 500 chars): {response_text[:500]}")
            
            # Handle code block formatting - more robust extraction
            original_response = response_text
            
            if "```json" in response_text:
                try:
                    response_text = response_text.split("```json")[1].split("```")[0].strip()
                except IndexError:
                    logger.warning("Failed to extract JSON from ```json block")
            elif "```" in response_text:
                # Handle case where code block might contain language identifier
                parts = response_text.split("```")
                if len(parts) >= 2:
                    # Get the content between first ``` and second ```
                    code_content = parts[1]
                    # Remove language identifier if present (e.g., 'json\n')
                    if code_content.lstrip().startswith('json'):
                        code_content = code_content.lstrip()[4:].lstrip()
                    response_text = code_content.strip()
            
            # Clean up any leading/trailing whitespace
            response_text = response_text.strip()
            
            # Try to find JSON object if response has extra text before it
            if not response_text.startswith('{'):
                json_start = response_text.find('{')
                if json_start != -1:
                    response_text = response_text[json_start:]
            
            # Find the matching closing brace for complete JSON extraction
            if response_text.startswith('{'):
                brace_count = 0
                json_end = -1
                in_string = False
                escape_next = False
                
                for i, char in enumerate(response_text):
                    if escape_next:
                        escape_next = False
                        continue
                    if char == '\\':
                        escape_next = True
                        continue
                    if char == '"' and not escape_next:
                        in_string = not in_string
                        continue
                    if not in_string:
                        if char == '{':
                            brace_count += 1
                        elif char == '}':
                            brace_count -= 1
                            if brace_count == 0:
                                json_end = i + 1
                                break
                
                if json_end > 0:
                    response_text = response_text[:json_end]
            
            logger.debug(f"Processed JSON (first 300 chars): {response_text[:300]}")
            
            try:
                parsed = json.loads(response_text)
                # Validate that we got expected structure
                if isinstance(parsed, dict):
                    logger.info(f"Successfully parsed board analytics JSON with {len(parsed)} keys")
                    # Transform simplified format to full format for backward compatibility
                    parsed = _transform_analytics_response(parsed)
                    return parsed
                else:
                    logger.warning(f"AI returned non-dict JSON: {type(parsed)}")
                    return {
                        'executive_summary': str(parsed),
                        'confidence_score': 0.5,
                        'parsing_note': 'AI returned unexpected JSON type'
                    }
            except json.JSONDecodeError as e:
                logger.warning(f"JSON parse error in board analytics: {e}")
                logger.debug(f"Failed JSON content: {response_text[:500]}")
                
                # Try a more aggressive JSON extraction using regex
                import re
                
                # Try to find and parse any valid JSON object
                json_pattern = r'\{[^{}]*(?:\{[^{}]*\}[^{}]*)*\}'
                matches = re.findall(json_pattern, response_text, re.DOTALL)
                
                for match in matches:
                    try:
                        parsed = json.loads(match)
                        if isinstance(parsed, dict) and 'executive_summary' in parsed:
                            logger.info("Recovered JSON using regex extraction")
                            return parsed
                    except json.JSONDecodeError:
                        continue
                
                # Last resort: extract key fields manually
                result = {'confidence_score': 0.5, 'parsing_note': 'Partial extraction from malformed JSON'}
                
                # Extract executive_summary
                exec_match = re.search(r'"executive_summary"\s*:\s*"((?:[^"\\]|\\.)*)"', response_text)
                if exec_match:
                    result['executive_summary'] = exec_match.group(1).replace('\\"', '"').replace('\\n', '\n')
                
                # Extract confidence_score
                conf_match = re.search(r'"confidence_score"\s*:\s*([\d.]+)', response_text)
                if conf_match:
                    try:
                        result['confidence_score'] = float(conf_match.group(1))
                    except ValueError:
                        pass
                
                # Extract health_assessment overall_score
                health_match = re.search(r'"overall_score"\s*:\s*"([^"]+)"', response_text)
                if health_match:
                    result['health_assessment'] = {'overall_score': health_match.group(1)}
                
                if 'executive_summary' in result:
                    logger.info("Partially recovered data from malformed JSON")
                    return result
                
                # Complete fallback
                return {
                    'executive_summary': original_response[:500] if len(original_response) > 500 else original_response,
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
        task_data: Dictionary containing task information (title, description, due_date, budget fields, etc.)
        board_context: Dictionary containing board context (workload, deadlines, budget summary, etc.)

    Returns:
        A dictionary with suggested priority and reasoning or None if suggestion fails
    """
    try:
        # Extract task information
        title = task_data.get('title', '')
        description = task_data.get('description', '')
        due_date = task_data.get('due_date', '')
        current_priority = task_data.get('current_priority', 'medium')

        # Extract enhanced context fields
        complexity_score = task_data.get('complexity_score')
        risk_score = task_data.get('risk_score')
        risk_level = task_data.get('risk_level', '')
        risk_likelihood = task_data.get('risk_likelihood', '')
        risk_impact = task_data.get('risk_impact', '')
        dependencies_count = task_data.get('dependencies_count', 0)
        collaboration_required = task_data.get('collaboration_required', False)
        workload_impact = task_data.get('workload_impact', '')
        skill_match_score = task_data.get('skill_match_score')
        start_date = task_data.get('start_date', '')
        
        # Extract budget/cost information
        estimated_cost = task_data.get('estimated_cost')
        estimated_hours = task_data.get('estimated_hours')
        hourly_rate = task_data.get('hourly_rate')
        
        # Build budget context string
        budget_info = ""
        if estimated_cost is not None or estimated_hours is not None or hourly_rate is not None:
            budget_parts = []
            if estimated_cost is not None and float(estimated_cost) > 0:
                budget_parts.append(f"Estimated Cost: ${float(estimated_cost):,.2f}")
            if estimated_hours is not None and float(estimated_hours) > 0:
                budget_parts.append(f"Estimated Hours: {float(estimated_hours):.1f} hours")
            if hourly_rate is not None and float(hourly_rate) > 0:
                budget_parts.append(f"Hourly Rate: ${float(hourly_rate):.2f}/hr")
                if estimated_hours is not None and float(estimated_hours) > 0:
                    labor_cost = float(estimated_hours) * float(hourly_rate)
                    budget_parts.append(f"Estimated Labor Cost: ${labor_cost:,.2f}")
            if budget_parts:
                budget_info = "\n        - " + "\n        - ".join(budget_parts)
        
        # Build enhanced task context string
        enhanced_task_info = ""
        context_parts = []
        if complexity_score is not None:
            label = "Very Complex" if int(complexity_score) >= 8 else "Moderate" if int(complexity_score) >= 5 else "Simple"
            context_parts.append(f"Complexity Score: {complexity_score}/10 ({label})")
        if risk_level:
            context_parts.append(f"Risk Level: {risk_level}")
        if risk_score is not None:
            context_parts.append(f"Risk Score: {risk_score}/9")
        elif risk_likelihood and risk_impact:
            context_parts.append(f"Risk: Likelihood={risk_likelihood}, Impact={risk_impact}")
        if dependencies_count and int(dependencies_count) > 0:
            context_parts.append(f"Dependencies: {dependencies_count} blocking task(s) — delays on these block this task")
        if collaboration_required:
            context_parts.append("Collaboration Required: Yes (multi-person coordination)")
        if workload_impact:
            context_parts.append(f"Workload Impact: {workload_impact}")
        if skill_match_score is not None:
            label = "Excellent" if int(skill_match_score) >= 80 else "Good" if int(skill_match_score) >= 60 else "Below Average" if int(skill_match_score) >= 40 else "Poor"
            context_parts.append(f"Skill Match: {skill_match_score}% ({label})")
        if start_date:
            context_parts.append(f"Start Date: {start_date}")
        if context_parts:
            enhanced_task_info = "\n        - " + "\n        - ".join(context_parts)
        
        # Extract board context
        total_tasks = board_context.get('total_tasks', 0)
        high_priority_count = board_context.get('high_priority_count', 0)
        urgent_count = board_context.get('urgent_count', 0)
        overdue_count = board_context.get('overdue_count', 0)
        upcoming_deadlines = board_context.get('upcoming_deadlines', [])
        
        # Extract board budget context if available
        avg_task_cost = board_context.get('avg_task_cost')
        total_board_budget = board_context.get('total_board_budget')
        
        board_budget_info = ""
        if avg_task_cost is not None:
            board_budget_info += f"\n        - Average Task Cost on Board: ${float(avg_task_cost):,.2f}"
        if total_board_budget is not None:
            board_budget_info += f"\n        - Total Board Budget: ${float(total_board_budget):,.2f}"
        
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
        6. **Budget & Cost Impact**: Higher-cost tasks may warrant higher priority for ROI optimization
        
        ## Task Information:
        - Title: {title}
        - Description: {description or 'No description provided'}
        - Current Priority: {current_priority}
        - Due Date: {due_date or 'No due date set'}{budget_info if budget_info else ''}{enhanced_task_info if enhanced_task_info else ''}
        
        ## Board Context:
        - Total Tasks on Board: {total_tasks}
        - Current High Priority Tasks: {high_priority_count}
        - Current Urgent Tasks: {urgent_count}
        - Overdue Tasks: {overdue_count}
        - Tasks Due Soon: {upcoming_deadlines_count}{board_budget_info if board_budget_info else ''}
        
        Consider these factors in order:
        1. **Semantic keywords** in title/description indicating business impact
        2. Urgency based on due date proximity
        3. Impact based on task description and title context
        4. Current workload distribution (avoid too many high/urgent priorities)
        5. Dependencies and blockers that might be indicated
        6. Business value and risk implied by the task
        7. **Budget/Cost considerations**: High-cost tasks may need higher priority for better ROI
        8. **Task complexity**: Higher complexity tasks may need earlier attention to avoid delays
        9. **Risk assessment**: Tasks with high risk scores may warrant elevated priority
        10. **Collaboration & skill gaps**: Poor skill match or multi-person coordination adds urgency
        
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

            # Standard token fixes
            response_text = response_text.replace('True', 'true').replace('False', 'false')
            response_text = response_text.replace('None', 'null')
            response_text = re.sub(r',\s*([}\]])', r'\1', response_text)

            try:
                return json.loads(response_text)
            except json.JSONDecodeError as json_err:
                logger.warning(f"Priority suggestion JSON parse error: {json_err}. Attempting repair...")

                # Strategy 1: _repair_json (fixes commas, braces, truncated strings)
                try:
                    repaired = _repair_json(response_text)
                    if repaired:
                        return json.loads(repaired)
                except (json.JSONDecodeError, Exception) as e:
                    logger.debug(f"Priority repair strategy 1 (_repair_json) failed: {e}")

                # Strategy 2: regex extraction of key fields
                try:
                    priority_match = re.search(
                        r'["\']suggested_priority["\']\s*:\s*["\']([^"\']+)["\']', response_text
                    )
                    confidence_match = re.search(
                        r'["\']confidence_score["\']\s*:\s*([\d.]+)', response_text
                    )
                    reasoning_match = re.search(
                        r'["\']reasoning["\']\s*:\s*["\']([^"\']{5,})', response_text
                    )
                    if priority_match:
                        extracted_priority = priority_match.group(1).lower()
                        if extracted_priority in ('low', 'medium', 'high', 'urgent'):
                            logger.info(f"Priority suggestion recovered via regex: {extracted_priority}")
                            return {
                                "suggested_priority": extracted_priority,
                                "confidence_score": float(confidence_match.group(1)) if confidence_match else 0.5,
                                "confidence_level": "low",
                                "reasoning": reasoning_match.group(1) if reasoning_match else "AI response was truncated; priority extracted from partial data.",
                                "contributing_factors": [],
                                "priority_comparison": {},
                                "alternative_priority": None,
                                "workload_impact": {},
                                "recommendations": ["Re-run analysis for full explainability"],
                                "assumptions": ["Partial response — some analysis context was lost"],
                                "urgency_indicators": [],
                                "impact_indicators": [],
                                "truncation_note": "Response was truncated and recovered via regex extraction."
                            }
                except Exception as e:
                    logger.debug(f"Priority repair strategy 2 (regex) failed: {e}")

                # Strategy 3: rule-based fallback using task context
                logger.warning("All priority JSON repair strategies failed — using rule-based fallback")
                return _create_fallback_priority_suggestion(
                    title, description, due_date, current_priority, board_context
                )
        return None
    except Exception as e:
        logger.error(f"Error suggesting task priority: {str(e)}")
        return None


def _create_fallback_priority_suggestion(
    title: str, description: str, due_date: str,
    current_priority: str, board_context: Dict
) -> Dict:
    """
    Rule-based fallback when AI JSON parsing fails for priority suggestion.
    Uses keyword analysis and board context to produce a reasonable suggestion.
    """
    text = f"{title} {description}".lower()

    # Keyword-based importance signal
    high_keywords = [
        'security', 'critical', 'production', 'outage', 'payment',
        'compliance', 'migration', 'database', 'deployment', 'hotfix',
        'vulnerability', 'breach', 'downtime', 'data loss',
    ]
    medium_keywords = [
        'refactor', 'performance', 'integration', 'api', 'testing',
        'monitoring', 'optimization', 'upgrade',
    ]

    importance = 'medium'
    matched_keywords = []
    for kw in high_keywords:
        if kw in text:
            importance = 'high'
            matched_keywords.append(kw)
    if importance == 'medium':
        for kw in medium_keywords:
            if kw in text:
                matched_keywords.append(kw)

    # Due-date urgency
    urgency = 'medium'
    if due_date:
        try:
            from django.utils import timezone as tz
            from django.utils.dateparse import parse_datetime, parse_date
            due = parse_datetime(due_date) or parse_date(due_date)
            if due:
                if hasattr(due, 'date'):
                    due = due.date()
                days_left = (due - tz.now().date()).days
                if days_left <= 2:
                    urgency = 'urgent'
                elif days_left <= 5:
                    urgency = 'high'
                elif days_left > 14:
                    urgency = 'low'
        except Exception:
            pass

    # Combine signals
    priority_rank = {'low': 0, 'medium': 1, 'high': 2, 'urgent': 3}
    score = max(priority_rank.get(importance, 1), priority_rank.get(urgency, 1))

    # Board overload check: if too many high/urgent already, nudge down
    high_count = board_context.get('high_priority_count', 0) + board_context.get('urgent_count', 0)
    total = board_context.get('total_tasks', 1) or 1
    if high_count / total > 0.4 and score >= 2:
        score = max(score - 1, 1)

    rank_to_priority = {0: 'low', 1: 'medium', 2: 'high', 3: 'urgent'}
    suggested = rank_to_priority.get(score, 'medium')

    factors = []
    if matched_keywords:
        factors.append({
            "factor": "Keyword Analysis",
            "contribution_percentage": 50,
            "description": f"Keywords detected: {', '.join(matched_keywords[:3])}",
            "weight": "high" if importance == 'high' else "medium",
        })
    if urgency != 'medium':
        factors.append({
            "factor": "Due Date Proximity",
            "contribution_percentage": 40,
            "description": f"Urgency assessed as {urgency} based on deadline",
            "weight": urgency,
        })

    return {
        "suggested_priority": suggested,
        "confidence_score": 0.4,
        "confidence_level": "low",
        "reasoning": (
            "AI response could not be parsed. This suggestion is based on "
            "keyword analysis and deadline proximity (rule-based fallback)."
        ),
        "contributing_factors": factors,
        "priority_comparison": {},
        "alternative_priority": None,
        "workload_impact": {
            "current_distribution": f"{high_count} high/urgent out of {total} tasks",
            "impact_of_suggestion": "Rule-based estimate — re-run for detailed analysis",
        },
        "recommendations": ["Re-run AI analysis for full explainability"],
        "assumptions": ["Rule-based fallback — limited analysis context"],
        "urgency_indicators": [urgency] if urgency != 'medium' else [],
        "impact_indicators": matched_keywords[:3],
        "fallback_note": "Generated by rule-based fallback due to AI response parsing failure.",
    }


def predict_realistic_deadline(task_data: Dict, team_context: Dict) -> Optional[Dict]:
    """
    Predict realistic completion timeline for a task based on historical data and context.
    
    IMPORTANT: This function requires a valid assignee to be set in task_data.
    The prediction is based on the assignee's historical velocity and current workload.
    The API endpoint validates that an assignee is selected before calling this function.
    
    Args:
        task_data: Dictionary containing task information (must include 'assigned_to', may include 'estimated_hours', 'start_date')
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
        start_date_str = task_data.get('start_date')  # Get start date for proper deadline calculation
        
        # Extract new task fields for enhanced prediction
        complexity_score = task_data.get('complexity_score', 5)
        workload_impact = task_data.get('workload_impact', 'medium')
        skill_match_score = task_data.get('skill_match_score')
        collaboration_required = task_data.get('collaboration_required', False)
        dependencies_count = task_data.get('dependencies_count', 0)
        risk_score = task_data.get('risk_score')
        risk_level = task_data.get('risk_level')
        
        # Extract budget/effort estimation fields
        estimated_hours = task_data.get('estimated_hours')
        estimated_cost = task_data.get('estimated_cost')
        hourly_rate = task_data.get('hourly_rate')
        
        # Extract team context
        assignee_avg_completion = team_context.get('assignee_avg_completion_days', 0)
        team_avg_completion = team_context.get('team_avg_completion_days', 0)
        team_completed_count = team_context.get('team_completed_tasks_count', 0)
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
        
        # Format estimated hours info (critical for timeline calculation)
        estimated_hours_note = ""
        if estimated_hours is not None and float(estimated_hours) > 0:
            hours_val = float(estimated_hours)
            # Calculate expected days based on estimated hours and assignee velocity
            if assignee_velocity > 0:
                estimated_days_from_hours = hours_val / assignee_velocity
                estimated_hours_note = f"Estimated Effort: {hours_val:.1f} hours (approximately {estimated_days_from_hours:.1f} days at {assignee_velocity} hours/day)"
            else:
                estimated_hours_note = f"Estimated Effort: {hours_val:.1f} hours"
        else:
            estimated_hours_note = "Estimated Effort: Not specified"
        
        # Determine data availability for honest AI reasoning
        has_assignee_history = assignee_completed_count > 0
        has_team_history = team_completed_count > 0
        
        if has_assignee_history:
            history_note = f"Based on {assigned_to}'s history of {assignee_completed_count} completed tasks (avg {assignee_avg_completion} days each)"
        elif has_team_history:
            history_note = f"No history for {assigned_to} yet. Using team average from {team_completed_count} completed tasks ({team_avg_completion} days avg)"
        else:
            history_note = f"NO HISTORICAL DATA available - this is a new board with no completed tasks. Estimate based on task complexity ({complexity_score}/10) and estimated effort only"
        
        # Determine start date for prompt
        if start_date_str:
            start_date_note = f"Start Date: {start_date_str} (predict days needed to complete FROM this date)"
        else:
            start_date_note = "Start Date: Today (no start date specified)"
        
        prompt = f"""
        Predict realistic timeline for this task.
        
        Task: {title}
        Priority: {priority} | Assigned: {assigned_to}
        Complexity: {complexity_score}/10 ({complexity_label}) | Current workload: {current_workload} active tasks
        {estimated_hours_note}
        {start_date_note}
        Skill Match: {skill_match_note}
        Collaboration Required: {'Yes' if collaboration_required else 'No'}
        Dependencies: {dependencies_count} blocking task(s)
        Risk: {risk_level or 'Not assessed'} (score: {risk_score if risk_score is not None else 'N/A'})
        Performance: {performance_note}
        
        DATA AVAILABILITY: {history_note}
        
        IMPORTANT RULES:
        - Predict number of WORKING DAYS needed to complete this task (not calendar date)
        - Be HONEST about data availability in your reasoning
        - If no historical data exists, say "estimated based on task complexity" NOT "based on historical averages"
        - Keep response concise. Return JSON only:
        
        {{
            "estimated_days_to_complete": number,
            "confidence_score": float_0_to_1,
            "confidence_level": "high|medium|low",
            "reasoning": "2-3 honest sentences explaining basis for timeline (mention data availability, key drivers)",
            "risk_factors": ["2-3 brief risks that could delay completion"],
            "optimistic_days": number,
            "pessimistic_days": number,
            "contributing_factors": [
                {{"name": "factor name", "contribution_percentage": integer_1_to_100, "description": "1 sentence on how this factor affected the estimate"}}
            ],
            "assumptions": ["1-3 key assumptions made in this prediction"],
            "data_quality": "high|medium|low"
        }}
        
        Contributing factors should include the top 3-5 drivers (e.g. complexity, assignee velocity, workload, skill match, dependencies).
        data_quality should be 'high' if assignee has >5 completed tasks, 'medium' if 1-5, 'low' if none.
        """
        
        response_text = generate_ai_content(prompt, task_type='deadline_prediction')
        if response_text:
            # Handle code block formatting
            if "```json" in response_text:
                response_text = response_text.split("```json")[1].split("```")[0].strip()
            elif "```" in response_text:
                response_text = response_text.split("```")[1].strip()
            
            # Try to parse JSON, with fallback for malformed responses
            ai_response = None
            try:
                ai_response = json.loads(response_text)
            except json.JSONDecodeError as json_err:
                logger.warning(f"JSON parsing failed for deadline prediction: {json_err}. Attempting regex extraction.")
                # Try to extract key values using regex as fallback
                import re
                ai_response = {}
                
                # Extract estimated_days_to_complete
                days_match = re.search(r'"estimated_days_to_complete"\s*:\s*(\d+)', response_text)
                if days_match:
                    ai_response['estimated_days_to_complete'] = int(days_match.group(1))
                else:
                    # Fallback based on complexity
                    ai_response['estimated_days_to_complete'] = max(2, complexity_score)
                
                # Extract confidence_level
                conf_match = re.search(r'"confidence_level"\s*:\s*"(high|medium|low)"', response_text)
                ai_response['confidence_level'] = conf_match.group(1) if conf_match else 'low'
                
                # Extract optimistic_days
                opt_match = re.search(r'"optimistic_days"\s*:\s*(\d+)', response_text)
                ai_response['optimistic_days'] = int(opt_match.group(1)) if opt_match else max(1, ai_response['estimated_days_to_complete'] - 1)
                
                # Extract pessimistic_days
                pess_match = re.search(r'"pessimistic_days"\s*:\s*(\d+)', response_text)
                ai_response['pessimistic_days'] = int(pess_match.group(1)) if pess_match else ai_response['estimated_days_to_complete'] + 2
                
                # Default reasoning
                ai_response['reasoning'] = f"Estimated based on task complexity ({complexity_score}/10)"
                ai_response['risk_factors'] = ["Timeline based on complexity estimate"]
                ai_response['confidence_score'] = 0.3
                ai_response['contributing_factors'] = [{"name": "Task Complexity", "contribution_percentage": 80, "description": f"Primary driver at {complexity_score}/10"}]
                ai_response['assumptions'] = ["No historical data available; estimate based on complexity alone"]
                ai_response['data_quality'] = "low"
                
                logger.info(f"Deadline prediction extracted via regex fallback: {ai_response['estimated_days_to_complete']} days")
            
            if not ai_response:
                return None
                
            # Calculate actual dates from the predicted days
            from django.utils import timezone
            from datetime import timedelta, datetime
            today = timezone.now().date()
            
            # Use start_date as base if provided, otherwise use today
            if start_date_str:
                try:
                    # Parse various date formats
                    for fmt in ['%Y-%m-%d', '%d-%m-%Y', '%m/%d/%Y', '%d/%m/%Y']:
                        try:
                            base_date = datetime.strptime(start_date_str, fmt).date()
                            break
                        except ValueError:
                            continue
                    else:
                        base_date = today  # Fallback to today if parsing fails
                except Exception:
                    base_date = today
            else:
                base_date = today
            
            # Get estimated days (try both old and new field names for compatibility)
            estimated_days = ai_response.get('estimated_days_to_complete') or ai_response.get('estimated_days_from_today', 3)
            optimistic_days = ai_response.get('optimistic_days', estimated_days - 1)
            pessimistic_days = ai_response.get('pessimistic_days', estimated_days + 2)
            
            # Ensure minimum of 1 day for all scenarios
            estimated_days = max(1, estimated_days)
            optimistic_days = max(1, optimistic_days)
            pessimistic_days = max(1, pessimistic_days)
            
            # Calculate the actual dates FROM the base_date (start_date or today)
            recommended_deadline = (base_date + timedelta(days=estimated_days)).strftime('%Y-%m-%d')
            optimistic_deadline = (base_date + timedelta(days=optimistic_days)).strftime('%Y-%m-%d')
            pessimistic_deadline = (base_date + timedelta(days=pessimistic_days)).strftime('%Y-%m-%d')
            
            # Update response with calculated dates
            ai_response['recommended_deadline'] = recommended_deadline
            ai_response['start_date_used'] = base_date.strftime('%Y-%m-%d')
            ai_response['alternative_scenarios'] = {
                'optimistic': optimistic_deadline,
                'pessimistic': pessimistic_deadline
            }
            
            return ai_response
        return None
    except Exception as e:
        logger.error(f"Error predicting deadline: {str(e)}")
        return None


def suggest_optimal_assignee(task_data: Dict, candidates_with_scores: List[Dict], board_context: Dict) -> Optional[Dict]:
    """
    Use AI to analyze scored candidates and suggest the optimal assignee with full explainability.
    
    Combines algorithmic multi-factor scoring from ResourceLevelingService with AI reasoning
    to provide natural language explanations of why a particular person is the best fit.
    
    Args:
        task_data: Dict with title, description, required_skills, complexity_score, workload_impact
        candidates_with_scores: List of candidate dicts from ResourceLevelingService._analyze_candidate
        board_context: Dict with board_name, total_tasks, team_size, etc.
        
    Returns:
        Dict with recommended_user_id, confidence, reasoning, factors, alternatives, warnings
    """
    try:
        if not candidates_with_scores:
            return None
        
        # Build candidate profiles text
        candidates_text = ""
        for i, c in enumerate(candidates_with_scores, 1):
            candidates_text += f"""
Candidate {i}: {c.get('display_name', c.get('username', 'Unknown'))} (ID: {c.get('user_id')})
  - Overall Score: {c.get('overall_score', 0):.1f}/100
  - Skill Match: {c.get('skill_match', 0):.1f}/100
  - Availability: {c.get('availability', 0):.1f}/100 (Utilization: {c.get('utilization', 0):.1f}%, Active Tasks: {c.get('current_workload', 0)})
  - Velocity: {c.get('velocity', 0):.1f}/100
  - Reliability (On-time %): {c.get('reliability', 0):.1f}/100
  - Quality Score: {c.get('quality', 0):.1f}/100
  - Estimated Completion: {c.get('estimated_hours', 0):.1f} hours (by {c.get('estimated_completion', 'N/A')})
"""
        
        # Build required skills text
        required_skills = task_data.get('required_skills', [])
        if isinstance(required_skills, list) and required_skills:
            skills_text = ", ".join([
                f"{s.get('name', 'Unknown')} ({s.get('level', 'Any')})"
                for s in required_skills if isinstance(s, dict)
            ]) or "Not specified"
        else:
            skills_text = "Not specified"
        
        current_assignee = task_data.get('current_assignee', 'None')
        
        prompt = f"""You are an AI assistant for a project management tool. Analyze the following task and team member data to recommend the best assignee.

## Task Details
- **Title**: {task_data.get('title', 'Untitled')}
- **Description**: {task_data.get('description', 'No description provided')}
- **Required Skills**: {skills_text}
- **Complexity Score**: {task_data.get('complexity_score', 5)}/10
- **Workload Impact**: {task_data.get('workload_impact', 'medium')}
- **Current Assignee**: {current_assignee}

## Board Context
- **Board**: {board_context.get('board_name', 'Unknown')}
- **Team Size**: {board_context.get('team_size', 0)} members
- **Total Active Tasks**: {board_context.get('total_tasks', 0)}

## Candidate Analysis (Pre-scored by algorithmic engine)
Each candidate has been scored on 5 factors (0-100 scale) using historical performance data:
- **Skill Match**: How well their skills match the task requirements (keyword analysis of past completed tasks)
- **Availability**: 100 minus their current utilization percentage (higher = more available)
- **Velocity**: How fast they complete tasks compared to team average
- **Reliability**: Their on-time task completion rate
- **Quality**: Their quality score based on past work

{candidates_text}

## Your Task
Analyze all candidates holistically. Consider:
1. The algorithmic scores as strong signals, but also think about practical factors
2. Whether the task requires collaboration or specialized skills
3. Workload balance — avoid overloading team members even if they score highest
4. If a current assignee exists, whether reassignment is justified (>15 point improvement)
5. Risk factors: burnout risk for high-utilization members, skill gaps, timeline pressure
6. Task priority and due date urgency — high-priority or near-deadline tasks need reliable, available members
7. Estimated hours — larger tasks need members with more availability headroom
8. Dependencies count — tasks with many blockers need members experienced with coordinated delivery
9. Risk level/score — high-risk tasks should go to the most reliable and skilled members

Respond with ONLY valid JSON in this exact format:
{{
    "recommended_user_id": <integer - the user ID of the best candidate>,
    "recommended_username": "<string - their username>",
    "recommended_display_name": "<string - their display name>",
    "confidence": <float 0.0-1.0 - how confident you are in this recommendation>,
    "reasoning": "<string - 2-4 sentences explaining why this person is the best fit. Be specific about their strengths relative to the task. If reassigning, explain why the change is warranted.>",
    "factors": [
        {{
            "name": "<factor name e.g. 'Skill Match', 'Availability', 'Velocity', 'Reliability', 'Quality', 'Workload Balance'>",
            "contribution": <integer 1-100 - how much this factor influenced your decision>,
            "description": "<string - 1 sentence explaining this factor's role in the decision>"
        }}
    ],
    "alternatives": [
        {{
            "user_id": <integer>,
            "username": "<string>",
            "display_name": "<string>",
            "score": <float - their overall score>,
            "brief_reason": "<string - 1 sentence on why they're a viable alternative>"
        }}
    ],
    "warnings": ["<string - any concerns about the recommendation, e.g. 'High utilization risk', 'Limited skill match data'. Empty array if none.>"],
    "reassignment_justified": <boolean - true if changing from current assignee is recommended, false or null if no current assignee>,
    "explainability": {{
        "confidence_score": <float 0.0-1.0 - same as confidence above>,
        "reasoning": "<string - brief summary of the decision logic>",
        "data_quality": "<string - 'high', 'medium', or 'low' based on how much historical data was available>",
        "assumptions": ["<string - any assumptions the AI made, e.g. 'Assumed skill keywords from task titles reflect actual expertise'>"]
    }}
}}

IMPORTANT: Include 3-5 factors in the factors array. Include up to 3 alternatives (fewer if less than 4 candidates). Provide at least 1 assumption in explainability."""

        ai_response_text = generate_ai_content(prompt, task_type='assignee_suggestion')
        
        if not ai_response_text:
            logger.warning("AI returned empty response for assignee suggestion, using algorithmic fallback")
            return _build_algorithmic_fallback(candidates_with_scores, task_data)
        
        # Parse the AI response - strip markdown code fences if present
        cleaned = ai_response_text.strip()
        if cleaned.startswith('```'):
            cleaned = re.sub(r'^```(?:json)?\s*', '', cleaned)
            cleaned = re.sub(r'\s*```$', '', cleaned)
        
        try:
            ai_response = json.loads(cleaned)
        except json.JSONDecodeError:
            logger.warning(f"Failed to parse AI assignee suggestion JSON, attempting regex extraction")
            ai_response = _extract_assignee_suggestion_fields(cleaned, candidates_with_scores)
        
        if not ai_response:
            return _build_algorithmic_fallback(candidates_with_scores, task_data)
        
        # Validate recommended_user_id is one of the candidates
        valid_ids = {c['user_id'] for c in candidates_with_scores}
        rec_id = ai_response.get('recommended_user_id')
        if rec_id not in valid_ids and candidates_with_scores:
            # Fall back to algorithmic top pick but keep AI reasoning
            top = candidates_with_scores[0]
            ai_response['recommended_user_id'] = top['user_id']
            ai_response['recommended_username'] = top.get('username', '')
            ai_response['recommended_display_name'] = top.get('display_name', '')
            ai_response.setdefault('warnings', []).append(
                'AI recommended an invalid user; fell back to highest-scored candidate.'
            )
        
        # Ensure explainability block exists
        if 'explainability' not in ai_response:
            ai_response['explainability'] = {
                'confidence_score': ai_response.get('confidence', 0.7),
                'reasoning': ai_response.get('reasoning', 'Based on multi-factor analysis.'),
                'data_quality': 'medium',
                'assumptions': ['Used algorithmic scoring as primary signal.']
            }
        
        return ai_response
        
    except Exception as e:
        logger.error(f"Error in suggest_optimal_assignee: {str(e)}")
        if candidates_with_scores:
            return _build_algorithmic_fallback(candidates_with_scores, task_data)
        return None


def _build_algorithmic_fallback(candidates: List[Dict], task_data: Dict) -> Dict:
    """Build a structured response from algorithmic scores when AI is unavailable."""
    if not candidates:
        return None
    
    top = candidates[0]
    alternatives = []
    for c in candidates[1:4]:
        alternatives.append({
            'user_id': c['user_id'],
            'username': c.get('username', ''),
            'display_name': c.get('display_name', ''),
            'score': c.get('overall_score', 0),
            'brief_reason': f"Score: {c.get('overall_score', 0):.1f}/100 — Skill: {c.get('skill_match', 0):.0f}, Avail: {c.get('availability', 0):.0f}"
        })
    
    return {
        'recommended_user_id': top['user_id'],
        'recommended_username': top.get('username', ''),
        'recommended_display_name': top.get('display_name', ''),
        'confidence': min(top.get('overall_score', 50) / 100, 0.95),
        'reasoning': (
            f"{top.get('display_name', top.get('username', 'This candidate'))} is recommended based on "
            f"algorithmic multi-factor scoring: Skill Match {top.get('skill_match', 0):.0f}/100, "
            f"Availability {top.get('availability', 0):.0f}/100, Velocity {top.get('velocity', 0):.0f}/100, "
            f"Reliability {top.get('reliability', 0):.0f}/100, Quality {top.get('quality', 0):.0f}/100."
        ),
        'factors': [
            {'name': 'Skill Match', 'contribution': 30, 'description': f"Score: {top.get('skill_match', 0):.0f}/100 based on keyword analysis of past tasks."},
            {'name': 'Availability', 'contribution': 25, 'description': f"Score: {top.get('availability', 0):.0f}/100 — currently at {top.get('utilization', 0):.0f}% utilization."},
            {'name': 'Velocity', 'contribution': 20, 'description': f"Score: {top.get('velocity', 0):.0f}/100 relative to team average."},
            {'name': 'Reliability', 'contribution': 15, 'description': f"Score: {top.get('reliability', 0):.0f}/100 on-time completion rate."},
            {'name': 'Quality', 'contribution': 10, 'description': f"Score: {top.get('quality', 0):.0f}/100 based on work quality metrics."},
        ],
        'alternatives': alternatives,
        'warnings': ['AI analysis unavailable — showing algorithmic scoring only.'],
        'reassignment_justified': None,
        'explainability': {
            'confidence_score': min(top.get('overall_score', 50) / 100, 0.95),
            'reasoning': 'Recommendation based on algorithmic multi-factor scoring (AI reasoning unavailable).',
            'data_quality': 'medium',
            'assumptions': ['Used historical performance data and current workload metrics.']
        }
    }


def _extract_assignee_suggestion_fields(text: str, candidates: List[Dict]) -> Optional[Dict]:
    """Attempt to extract assignee suggestion fields from malformed AI response via regex."""
    try:
        result = {}
        
        # Extract recommended_user_id
        id_match = re.search(r'"recommended_user_id"\s*:\s*(\d+)', text)
        if id_match:
            result['recommended_user_id'] = int(id_match.group(1))
        elif candidates:
            result['recommended_user_id'] = candidates[0]['user_id']
        
        # Extract username and display name
        username_match = re.search(r'"recommended_username"\s*:\s*"([^"]+)"', text)
        if username_match:
            result['recommended_username'] = username_match.group(1)
        
        display_match = re.search(r'"recommended_display_name"\s*:\s*"([^"]+)"', text)
        if display_match:
            result['recommended_display_name'] = display_match.group(1)
        
        # Extract confidence
        conf_match = re.search(r'"confidence"\s*:\s*([\d.]+)', text)
        result['confidence'] = float(conf_match.group(1)) if conf_match else 0.7
        
        # Extract reasoning
        reason_match = re.search(r'"reasoning"\s*:\s*"((?:[^"\\]|\\.)*)"', text)
        result['reasoning'] = reason_match.group(1) if reason_match else 'Based on multi-factor analysis.'
        
        # Default fields
        result.setdefault('factors', [])
        result.setdefault('alternatives', [])
        result.setdefault('warnings', ['AI response partially parsed.'])
        result.setdefault('reassignment_justified', None)
        result.setdefault('explainability', {
            'confidence_score': result.get('confidence', 0.7),
            'reasoning': result.get('reasoning', ''),
            'data_quality': 'low',
            'assumptions': ['Response was partially parsed from AI output.']
        })
        
        return result if 'recommended_user_id' in result else None
        
    except Exception as e:
        logger.error(f"Error extracting assignee suggestion fields: {str(e)}")
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
        
        Recommend 4-7 columns that create an efficient workflow. Keep descriptions concise.
        
        REQUIRED: Your first column MUST be named "To Do" (this is where the task creation button is located).
        Also ensure your recommendations include:
        2. One or more active work stages (e.g., "In Progress", "Development", "Design", "Review")
        3. A completion stage (e.g., "Done", "Complete", "Deployed")
        
        The "To Do" column is mandatory - do not use alternatives like "Backlog" or "Planned" for the first column.
        
        Format as JSON:
        {{
            "recommended_columns": [
                {{
                    "name": "Column Name",
                    "description": "One sentence description",
                    "position": 1,
                    "color_suggestion": "#hex_color",
                    "purpose": "One sentence why essential",
                    "typical_wip_limit": "Number or null"
                }}
            ],
            "workflow_type": "kanban|scrum|custom",
            "confidence_score": 0.XX,
            "confidence_level": "high|medium|low",
            "reasoning": "1-2 sentences why this structure works",
            "contributing_factors": [
                {{
                    "factor": "Factor name",
                    "contribution_percentage": XX,
                    "description": "One sentence impact"
                }}
            ],
            "workflow_tips": ["Tip 1 (keep brief)", "Tip 2", "Tip 3"],
            "customization_suggestions": ["Option 1", "Option 2"],
            "alternative_workflow": {{
                "type": "Type",
                "columns": ["Col1", "Col2", "Col3"],
                "when_to_use": "One sentence when better"
            }},
            "assumptions": ["Brief assumption 1", "Brief assumption 2"],
            "bottleneck_warnings": ["Brief warning 1", "Brief warning 2"]
        }}
        """
        
        response_text = generate_ai_content(prompt, task_type='column_recommendations')
        if response_text:
            # Handle code block formatting and clean up response
            if "```json" in response_text:
                response_text = response_text.split("```json")[1].split("```")[0].strip()
            elif "```" in response_text:
                response_text = response_text.split("```")[1].strip()
            
            # Remove any leading/trailing whitespace and potential BOM
            response_text = response_text.strip()
            
            # Try to find JSON object if response contains extra text
            if not response_text.startswith('{'):
                # Look for the first { and last }
                start_idx = response_text.find('{')
                end_idx = response_text.rfind('}')
                if start_idx != -1 and end_idx != -1:
                    response_text = response_text[start_idx:end_idx+1]
            
            try:
                return json.loads(response_text)
            except json.JSONDecodeError as e:
                logger.error(f"JSON parsing error in column recommendations: {str(e)}")
                logger.error(f"Response text: {response_text[:500]}")
                return None
        return None
    except Exception as e:
        logger.error(f"Error recommending columns: {str(e)}")
        return None


def generate_board_setup_recommendations(board_data: Dict) -> Optional[Dict]:
    """
    Generate AI-powered recommendations for board description, phase configuration, 
    and team size based on the board name and project type.
    
    Provides explainable AI output with reasoning for each recommendation.
    
    Args:
        board_data: Dictionary containing:
            - name: Board/project name
            - project_type: Optional project type hint
            
    Returns:
        A dictionary with recommendations and explainability data or None if generation fails
    """
    try:
        board_name = board_data.get('name', '')
        project_type = board_data.get('project_type', '')
        
        if not board_name:
            return None
        
        prompt = f"""
        Analyze this project/board name and generate smart setup recommendations.
        
        ## Project Information:
        - Name: {board_name}
        - Project Type Hint: {project_type or 'Not specified'}
        
        Based on the project name, intelligently infer:
        1. A concise project description (2-3 sentences MAX - keep it brief and actionable)
        2. Recommended number of phases (0-10)
        3. Recommended team size category
        
        IMPORTANT: Keep the description SHORT and focused. No lengthy explanations.
        
        Format your response as JSON WITH FULL EXPLAINABILITY:
        {{
            "description": "Brief 2-3 sentence project description focused on key objectives",
            "description_reasoning": "1 sentence explaining how you interpreted the project name",
            "recommended_phases": 3,
            "phases_reasoning": "1-2 sentences explaining why this phase count is recommended",
            "phase_names": ["Phase 1 name", "Phase 2 name", "Phase 3 name"],
            "recommended_team_size": "small|medium|large|solo|enterprise",
            "team_size_reasoning": "1 sentence explaining why this team size fits the project scope",
            "confidence_score": 0.XX,
            "confidence_level": "high|medium|low",
            "inferred_project_type": "The project type inferred from the name",
            "key_assumptions": [
                "Brief assumption 1 about the project scope",
                "Brief assumption 2 about the project nature"
            ],
            "alternative_configuration": {{
                "phases": 2,
                "team_size": "medium",
                "when_applicable": "Brief description of when this alternative might be better"
            }}
        }}
        """
        
        response_text = generate_ai_content(prompt, task_type='board_setup')
        if response_text:
            # Handle code block formatting and clean up response
            if "```json" in response_text:
                response_text = response_text.split("```json")[1].split("```")[0].strip()
            elif "```" in response_text:
                response_text = response_text.split("```")[1].strip()
            
            # Remove any leading/trailing whitespace and potential BOM
            response_text = response_text.strip()
            
            # Try to find JSON object if response contains extra text
            if not response_text.startswith('{'):
                # Look for the first { and last }
                start_idx = response_text.find('{')
                end_idx = response_text.rfind('}')
                if start_idx != -1 and end_idx != -1:
                    response_text = response_text[start_idx:end_idx+1]
            
            try:
                return json.loads(response_text)
            except json.JSONDecodeError as e:
                logger.error(f"JSON parsing error in board setup: {str(e)}")
                logger.error(f"Response text: {response_text[:500]}")
                return None
        return None
    except Exception as e:
        logger.error(f"Error generating board setup recommendations: {str(e)}")
        return None


def suggest_task_breakdown(task_data: Dict) -> Optional[Dict]:
    """
    Suggest automated breakdown of a complex task into smaller subtasks.
    Includes all optional context fields (risk, workload, dependencies, etc.)
    for accurate complexity scoring and transparent factor reporting.

    Args:
        task_data: Dictionary containing task information
        
    Returns:
        A dictionary with subtask suggestions, factors_considered, and
        factors_missing for explainability, or None if breakdown fails
    """
    try:
        # Extract core task information
        title = task_data.get('title', '')
        description = task_data.get('description', '')
        priority = task_data.get('priority', 'medium')
        due_date = task_data.get('due_date', '')
        estimated_effort = task_data.get('estimated_effort', '')

        # Extract optional context fields
        risk_likelihood = task_data.get('risk_likelihood')
        risk_impact = task_data.get('risk_impact')
        risk_level = task_data.get('risk_level')
        risk_score = task_data.get('risk_score')
        workload_impact = task_data.get('workload_impact')
        skill_match_score = task_data.get('skill_match_score')
        collaboration_required = task_data.get('collaboration_required')
        dependencies_count = task_data.get('dependencies_count')
        estimated_hours = task_data.get('estimated_hours')
        estimated_cost = task_data.get('estimated_cost')
        hourly_rate = task_data.get('hourly_rate')

        # ----------------------------------------------------------------
        # Build structured factor list for the prompt so the AI can reason
        # transparently and so we can reflect it back to the user.
        # Each factor records: name, value, direction (raises/lowers/neutral),
        # whether it was provided.
        # ----------------------------------------------------------------
        factors_provided = []
        factors_missing = []

        # --- Risk --------------------------------------------------------
        if risk_score is not None:
            level = risk_level or ('high' if risk_score >= 6 else 'medium' if risk_score >= 3 else 'low')
            direction = 'raises' if risk_score >= 6 else 'lowers' if risk_score <= 2 else 'neutral'
            factors_provided.append({
                'name': 'Risk Score',
                'value': f"{risk_score}/9 ({level})",
                'direction': direction,
                'note': f"Risk score {risk_score}/9 → complexity {'penalty' if direction == 'raises' else 'benefit' if direction == 'lowers' else 'neutral'}"
            })
        elif risk_level:
            direction = 'raises' if risk_level.lower() == 'high' else 'lowers' if risk_level.lower() == 'low' else 'neutral'
            factors_provided.append({
                'name': 'Risk Level',
                'value': risk_level,
                'direction': direction,
                'note': f"Risk level is {risk_level}"
            })
        elif risk_likelihood and risk_impact:
            combo = f"{risk_likelihood}/{risk_impact}"
            direction = 'raises' if (risk_likelihood.lower() == 'high' or risk_impact.lower() == 'high') else \
                        'lowers' if (risk_likelihood.lower() == 'low' and risk_impact.lower() == 'low') else 'neutral'
            factors_provided.append({
                'name': 'Risk',
                'value': f"Likelihood={risk_likelihood}, Impact={risk_impact}",
                'direction': direction,
                'note': f"Combined risk signals are {combo}"
            })
        else:
            factors_missing.append({'name': 'Risk Assessment', 'note': 'No risk fields filled – treated as neutral'})

        # --- Workload ----------------------------------------------------
        if workload_impact:
            direction = 'raises' if workload_impact.lower() in ('high', 'critical') else \
                        'lowers' if workload_impact.lower() == 'low' else 'neutral'
            factors_provided.append({
                'name': 'Workload Impact',
                'value': workload_impact,
                'direction': direction,
                'note': f"Assignee workload is {workload_impact}"
            })
        else:
            factors_missing.append({'name': 'Workload Impact', 'note': 'Not specified – treated as neutral'})

        # --- Skill Match -------------------------------------------------
        if skill_match_score is not None:
            direction = 'lowers' if skill_match_score >= 70 else 'raises' if skill_match_score < 50 else 'neutral'
            factors_provided.append({
                'name': 'Skill Match',
                'value': f"{skill_match_score}%",
                'direction': direction,
                'note': f"{'Good' if skill_match_score >= 70 else 'Moderate' if skill_match_score >= 50 else 'Poor'} skill alignment"
            })
        else:
            factors_missing.append({'name': 'Skill Match Score', 'note': 'Not assessed – treated as neutral'})

        # --- Collaboration -----------------------------------------------
        if collaboration_required is not None:
            direction = 'raises' if collaboration_required else 'lowers'
            factors_provided.append({
                'name': 'Collaboration Required',
                'value': 'Yes' if collaboration_required else 'No',
                'direction': direction,
                'note': 'Coordination overhead adds complexity' if collaboration_required else 'Solo task reduces coordination complexity'
            })
        else:
            factors_missing.append({'name': 'Collaboration Required', 'note': 'Not specified – treated as neutral'})

        # --- Dependencies ------------------------------------------------
        if dependencies_count is not None:
            direction = 'raises' if dependencies_count > 2 else 'neutral' if dependencies_count > 0 else 'lowers'
            factors_provided.append({
                'name': 'Dependencies',
                'value': str(dependencies_count),
                'direction': direction,
                'note': f"{dependencies_count} task dependenc{'ies' if dependencies_count != 1 else 'y'}"
            })
        else:
            factors_missing.append({'name': 'Dependencies Count', 'note': 'Not specified – treated as neutral'})

        # --- Estimated Effort --------------------------------------------
        if estimated_hours is not None and float(estimated_hours) > 0:
            hours_val = float(estimated_hours)
            direction = 'raises' if hours_val > 16 else 'lowers' if hours_val <= 8 else 'neutral'
            factors_provided.append({
                'name': 'Estimated Hours',
                'value': f"{hours_val:.1f} hrs",
                'direction': direction,
                'note': f"{'Short' if hours_val <= 8 else 'Medium' if hours_val <= 16 else 'Long'} effort estimate"
            })
        else:
            factors_missing.append({'name': 'Estimated Hours', 'note': 'Not specified – AI estimates from description'})

        # ----------------------------------------------------------------
        # Build readable factor summary for the prompt
        # ----------------------------------------------------------------
        def fmt_direction(d):
            return '⬆ raises complexity' if d == 'raises' else '⬇ lowers complexity' if d == 'lowers' else '↔ neutral'

        provided_block = '\n'.join(
            f"  - {f['name']}: {f['value']} → {fmt_direction(f['direction'])} ({f['note']})"
            for f in factors_provided
        ) or '  (none provided)'

        missing_block = '\n'.join(
            f"  - {f['name']}: {f['note']}"
            for f in factors_missing
        ) or '  (all fields provided)'

        prompt = f"""
        Analyze this task and suggest a breakdown into smaller subtasks.

        ## Task
        Title: {title}
        Description: {description or 'No description provided'}
        Priority: {priority}
        Due: {due_date or 'Not set'}

        ## Context Factors Provided (YOU MUST USE THESE TO ADJUST THE COMPLEXITY SCORE)
{provided_block}

        ## Context Factors Missing (treat each as NEUTRAL – do NOT penalise for missing data)
{missing_block}

        ## COMPLEXITY SCORING RULES
        1. Start from the content complexity of the title + description (distinct deliverables, unknowns, technical challenges).
        2. For EVERY factor listed as "⬇ lowers complexity", REDUCE the score by 1-2 points.
        3. For EVERY factor listed as "⬆ raises complexity", INCREASE the score by 1-2 points.
        4. For missing/neutral factors, make NO adjustment – do not assume difficulty.
        5. Final score must be between 1 and 10.
        6. In your "reasoning" field, explicitly name each factor and how it moved the score.

        ## Output Format
        Return JSON only – no extra text:
        {{
            "is_breakdown_recommended": true|false,
            "complexity_score": 1-10,
            "confidence_score": float_0_to_1,
            "confidence_level": "high|medium|low",
            "reasoning": "Explain score step-by-step: content base score X, then list each factor adjustment",
            "subtasks": [
                {{
                    "title": "Short subtask title",
                    "description": "One sentence describing what to do",
                    "estimated_effort": "0.5-1 day",
                    "priority": "low|medium|high",
                    "order": 1
                }}
            ],
            "total_estimated_effort": "Total time estimate",
            "factors_considered": [
                {{"name": "Factor Name", "value": "Factor Value", "direction": "raises|lowers|neutral", "note": "one-line explanation"}}
            ],
            "factors_missing": [
                {{"name": "Factor Name", "note": "why it was not available"}}
            ],
            "assumptions": ["1-3 key assumptions made in this breakdown analysis"],
            "data_quality": "high|medium|low"
        }}
        """
        
        def _enrich_result(result):
            """Guarantee factors_considered / factors_missing are always present so
            the frontend can always render the explainability panel."""
            if not result.get('factors_considered'):
                result['factors_considered'] = factors_provided
            if not result.get('factors_missing'):
                result['factors_missing'] = factors_missing
            return result

        def _fix_unescaped_json_strings(text):
            """Escape raw control characters (newlines, tabs, etc.) that appear
            inside JSON string values — a common issue with AI-generated JSON."""
            result = []
            in_string = False
            escape_next = False
            for ch in text:
                if escape_next:
                    result.append(ch)
                    escape_next = False
                elif ch == '\\' and in_string:
                    result.append(ch)
                    escape_next = True
                elif ch == '"':
                    in_string = not in_string
                    result.append(ch)
                elif in_string and ch == '\n':
                    result.append('\\n')
                elif in_string and ch == '\r':
                    result.append('\\r')
                elif in_string and ch == '\t':
                    result.append('\\t')
                else:
                    result.append(ch)
            return ''.join(result)

        def _repair_truncated_json(text):
            """Best-effort repair for truncated JSON: close any open string,
            then close any unclosed arrays/objects in reverse order."""
            text = text.rstrip()
            in_string = False
            escape_next = False
            stack = []  # track '[' and '{'
            for ch in text:
                if escape_next:
                    escape_next = False
                    continue
                if ch == '\\' and in_string:
                    escape_next = True
                    continue
                if ch == '"':
                    in_string = not in_string
                elif not in_string:
                    if ch in ('{', '['):
                        stack.append(ch)
                    elif ch == '}':
                        if stack and stack[-1] == '{':
                            stack.pop()
                    elif ch == ']':
                        if stack and stack[-1] == '[':
                            stack.pop()

            suffix = ''
            if in_string:
                suffix += '"'       # close the open string
            # close unclosed arrays/objects
            for opener in reversed(stack):
                suffix += ']' if opener == '[' else '}'
            repaired = text + suffix
            return repaired

        response_text = generate_ai_content(prompt, task_type='task_breakdown')
        if response_text:
            # Handle code block formatting
            if "```json" in response_text:
                response_text = response_text.split("```json")[1].split("```")[0].strip()
            elif "```" in response_text:
                response_text = response_text.split("```")[1].strip()

            # Step 1: escape raw newlines/tabs inside JSON string values
            response_text = _fix_unescaped_json_strings(response_text)

            # Step 2: standard token fixes
            response_text = response_text.replace('True', 'true').replace('False', 'false')
            response_text = response_text.replace('None', 'null')
            response_text = re.sub(r',\s*([}\]])', r'\1', response_text)  # Remove trailing commas

            try:
                return _enrich_result(json.loads(response_text))
            except json.JSONDecodeError as json_err:
                logger.error(f"Task breakdown JSON parse error: {json_err}. Response text (first 500 chars): {response_text[:500]}")

                # Step 3: try repairing truncated JSON
                try:
                    repaired = _repair_truncated_json(response_text)
                    parsed = json.loads(repaired)
                    logger.info("Successfully repaired truncated/incomplete JSON for task breakdown")
                    return _enrich_result(parsed)
                except json.JSONDecodeError as repair_err:
                    logger.error(f"Repair attempt failed: {repair_err}")

                # Step 4: strip remaining control characters and retry
                cleaned = re.sub(r'[\x00-\x08\x0b\x0c\x0e-\x1f\x7f-\x9f]', '', response_text)
                try:
                    return _enrich_result(json.loads(cleaned))
                except json.JSONDecodeError as second_err:
                    logger.error(f"Second JSON parse attempt failed: {second_err}")
                    try:
                        repaired2 = _repair_truncated_json(cleaned)
                        parsed2 = json.loads(repaired2)
                        logger.info("Repaired JSON after control-char strip for task breakdown")
                        return _enrich_result(parsed2)
                    except Exception as repair2_err:
                        logger.error(f"Failed to repair JSON after strip: {repair2_err}")
                        # Return a minimal valid response indicating failure
                        return _enrich_result({
                            "is_breakdown_recommended": False,
                            "complexity_score": 5,
                            "confidence_score": 0.0,
                            "confidence_level": "low",
                            "reasoning": "Unable to analyze task due to response parsing error. Please try again or simplify the task description.",
                            "complexity_factors": [],
                            "subtasks": [],
                            "critical_path": [],
                            "parallel_opportunities": [],
                            "workflow_suggestions": ["Try breaking down the task manually", "Simplify the task description"],
                            "risk_considerations": [],
                            "assumptions": ["Analysis incomplete due to technical error"],
                            "total_estimated_effort": "Unknown",
                            "effort_vs_original": "Unable to estimate"
                        })
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
                               board_context: str = '',
                               task_context: dict = None) -> Optional[Dict]:
    """
    Calculate AI-powered likelihood and impact scoring for a task using Gemini.
    
    Adapts risk management methodology from the risk management system to Kanban tasks.
    
    Args:
        task_title: The title of the task
        task_description: Detailed description of the task
        task_priority: Current priority level (low/medium/high/urgent)
        board_context: Optional context about the board/project
        task_context: Optional dict with complexity_score, due_date, estimated_hours, 
                      dependencies_count, collaboration_required, skill_match_score, etc.
        
    Returns:
        Dictionary with risk scores, level, indicators, and analysis or None if calculation fails
    """
    try:
        # Build enhanced context from task_context if provided
        enhanced_context = ""
        if task_context:
            context_parts = []
            if task_context.get('complexity_score') is not None:
                score = task_context['complexity_score']
                label = "Very Complex" if score >= 8 else "Moderate" if score >= 5 else "Simple"
                context_parts.append(f"Complexity Score: {score}/10 ({label})")
            if task_context.get('due_date'):
                context_parts.append(f"Due Date: {task_context['due_date']}")
            if task_context.get('start_date'):
                context_parts.append(f"Start Date: {task_context['start_date']}")
            if task_context.get('assigned_to'):
                context_parts.append(f"Assigned To: {task_context['assigned_to']}")
            if task_context.get('estimated_hours') is not None:
                context_parts.append(f"Estimated Hours: {task_context['estimated_hours']}")
            if task_context.get('estimated_cost') is not None:
                context_parts.append(f"Estimated Cost: ${float(task_context['estimated_cost']):,.2f}")
            if task_context.get('collaboration_required'):
                context_parts.append("Collaboration Required: Yes (multi-person coordination needed)")
            if task_context.get('dependencies_count') and int(task_context['dependencies_count']) > 0:
                context_parts.append(f"Dependencies: {task_context['dependencies_count']} blocking task(s)")
            if task_context.get('skill_match_score') is not None:
                score = task_context['skill_match_score']
                label = "Excellent" if score >= 80 else "Good" if score >= 60 else "Below Average" if score >= 40 else "Poor"
                context_parts.append(f"Skill Match: {score}% ({label})")
            if task_context.get('workload_impact'):
                context_parts.append(f"Workload Impact: {task_context['workload_impact']}")
            if context_parts:
                enhanced_context = "\n\n        TASK CONTEXT (use these to refine risk assessment):\n        " + "\n        ".join(f"- {p}" for p in context_parts)
        
        prompt = f"""
        As a project risk assessment expert, analyze this task and provide risk scoring using a 
        Likelihood × Impact matrix approach (1-3 scale for each).
        
        TASK INFORMATION:
        Title: {task_title}
        Description: {task_description}
        Priority: {task_priority}
        {f'Board Context: {board_context}' if board_context else ''}{enhanced_context}
        
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
        1. Assess likelihood of task risks (delays, dependencies, resource issues, skill gaps)
        2. Assess potential impact if risks occur (timeline, resources, quality, stakeholders)
        3. Factor in task complexity, dependencies, collaboration needs, and skill match if provided
        4. Consider due date proximity and estimated effort for timeline risk
        5. Identify key risk indicators to monitor
        6. Suggest specific mitigation actions
        7. Provide confidence level for assessment
        
        IMPORTANT FORMATTING RULES:
        - Keep all string values on a single line (no line breaks within strings)
        - Keep "reasoning" fields concise (max 2-3 sentences, under 300 characters)
        - Ensure all JSON is properly closed with matching braces
        - Use proper JSON syntax with commas after each property except the last
        
        FORMAT YOUR RESPONSE AS VALID JSON WITH DETAILED EXPLAINABILITY:
        {{
          "likelihood": {{
            "score": 1-3,
            "percentage_range": "XX-XX%",
            "reasoning": "Concise 1-2 sentence explanation on single line",
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
            "reasoning": "Concise 1-2 sentence explanation on single line",
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
            "summary": "Brief overall assessment on single line",
            "calculation_method": "Likelihood (X) × Impact (Y) = Z",
            "contributing_factors": [
              {{
                "factor": "Factor name",
                "contribution_percentage": XX,
                "weight": 0.XX,
                "description": "Brief description on single line"
              }}
            ]
          }},
          "risk_indicators": [
            {{"indicator": "What to monitor", "frequency": "When/how often", "threshold": "Alert level"}}
          ],
          "mitigation_suggestions": [
            {{"action": "Specific action", "timeline": "When", "priority": "high/medium/low", "expected_impact": "Brief impact description"}}
          ],
          "confidence_level": "high|medium|low",
          "confidence_score": 0.XX,
          "explainability": {{
            "model_assumptions": ["assumption1", "assumption2"],
            "data_limitations": ["limitation1"],
            "alternative_interpretations": ["interpretation1"]
          }}
        }}
        
        CRITICAL: Return ONLY valid JSON. Keep all text on single lines. No line breaks within string values.
        """
        
        response_text = generate_ai_content(prompt, task_type='risk_assessment')
        if response_text:
            # Log the raw response for debugging
            logger.debug(f"Raw AI response for risk scoring (length: {len(response_text)}): {response_text[:500]}...")
            
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
            
            # Try to parse JSON
            try:
                parsed_data = json.loads(response_text)
                logger.info(f"Successfully parsed risk assessment for task: {task_title[:50]}")
                return parsed_data
            except json.JSONDecodeError as e:
                logger.error(f"JSON parsing error in risk scoring: {e}")
                logger.error(f"Problematic JSON text (first 1000 chars): {response_text[:1000]}")
                
                # Try advanced JSON repair
                fixed_text = _repair_json(response_text)
                if fixed_text:
                    try:
                        parsed_data = json.loads(fixed_text)
                        logger.info(f"Successfully parsed risk assessment after repairing JSON for task: {task_title[:50]}")
                        return parsed_data
                    except json.JSONDecodeError as e2:
                        logger.error(f"Failed to parse repaired JSON: {e2}")
                
                # Return fallback assessment
                logger.warning(f"Falling back to rule-based assessment for task: {task_title[:50]}")
                return _create_fallback_risk_assessment(task_title, task_description, task_priority)
        else:
            logger.warning(f"No response from AI for risk scoring of task: {task_title[:50]}")
            return _create_fallback_risk_assessment(task_title, task_description, task_priority)
        
        return _create_fallback_risk_assessment(task_title, task_description, task_priority)
    except Exception as e:
        logger.error(f"Error calculating task risk score: {str(e)}", exc_info=True)
        return _create_fallback_risk_assessment(task_title, task_description, task_priority)


def _repair_json(json_text: str) -> Optional[str]:
    """
    Attempt to repair common JSON formatting issues.
    
    Args:
        json_text: Potentially malformed JSON string
        
    Returns:
        Repaired JSON string or None if repair failed
    """
    try:
        import re
        
        # Remove trailing commas before closing braces/brackets
        fixed_text = re.sub(r',\s*([}\]])', r'\1', json_text)
        
        # Fix missing commas between object properties (common in AI responses)
        # This regex looks for patterns like: "value"\n    "key": where comma is missing
        fixed_text = re.sub(r'"\s*\n\s*"', '",\n    "', fixed_text)
        
        # Fix missing commas in arrays
        fixed_text = re.sub(r'"\s*\n\s*\{', '",\n    {', fixed_text)
        fixed_text = re.sub(r'\}\s*\n\s*\{', '},\n    {', fixed_text)
        fixed_text = re.sub(r'\]\s*\n\s*\{', '],\n    {', fixed_text)
        
        # Handle truncated strings - if a string is not closed before end of object
        # Look for unclosed quotes before closing braces
        lines = fixed_text.split('\n')
        repaired_lines = []
        in_string = False
        string_char = None
        
        for line in lines:
            quote_count_double = line.count('"') - line.count('\\"')
            quote_count_single = line.count("'") - line.count("\\'")
            
            # Simple heuristic: if line has odd number of quotes, string may be unclosed
            if quote_count_double % 2 != 0 or quote_count_single % 2 != 0:
                # Check if this looks like a truncated string (doesn't end with quote but ends with letter/word)
                stripped = line.rstrip()
                if stripped and not stripped.endswith(('"', "'", ',', '{', '}', '[', ']', ':')):
                    # This might be a truncated line - add closing quote and comma
                    line = stripped + '...",'
            
            repaired_lines.append(line)
        
        fixed_text = '\n'.join(repaired_lines)
        
        # Try to balance braces if they're unbalanced
        open_braces = fixed_text.count('{')
        close_braces = fixed_text.count('}')
        open_brackets = fixed_text.count('[')
        close_brackets = fixed_text.count(']')
        
        if open_braces > close_braces:
            # Add missing closing braces at the end
            fixed_text += '\n' + ('  ' * (open_braces - close_braces - 1)) + '}\n' * (open_braces - close_braces)
        
        if open_brackets > close_brackets:
            # Add missing closing brackets at the end
            fixed_text += ']' * (open_brackets - close_brackets)
        
        logger.debug(f"JSON repair attempted. Original length: {len(json_text)}, Repaired length: {len(fixed_text)}")
        return fixed_text
        
    except Exception as e:
        logger.error(f"Error during JSON repair: {e}")
        return None


def _create_fallback_risk_assessment(task_title: str, task_description: str, task_priority: str) -> Dict:
    """
    Create a basic fallback risk assessment when AI parsing fails.
    
    Args:
        task_title: The title of the task
        task_description: Detailed description of the task
        task_priority: Priority level
        
    Returns:
        Dictionary with basic risk assessment
    """
    # Simple rule-based assessment
    priority_risk_map = {
        'urgent': {'likelihood': 3, 'impact': 3},
        'high': {'likelihood': 2, 'impact': 2},
        'medium': {'likelihood': 2, 'impact': 2},
        'low': {'likelihood': 1, 'impact': 1}
    }
    
    risk_scores = priority_risk_map.get(task_priority.lower(), {'likelihood': 2, 'impact': 2})
    risk_score = risk_scores['likelihood'] * risk_scores['impact']
    
    if risk_score >= 6:
        risk_level = 'Critical'
    elif risk_score >= 4:
        risk_level = 'High'
    elif risk_score >= 2:
        risk_level = 'Medium'
    else:
        risk_level = 'Low'
    
    return {
        'likelihood': {
            'score': risk_scores['likelihood'],
            'percentage_range': '34-66%',
            'reasoning': f'Assessment based on task priority ({task_priority}). AI analysis temporarily unavailable.',
            'key_factors': ['Task priority', 'Complexity assessment'],
            'factor_weights': {'priority': 0.7, 'complexity': 0.3},
            'confidence': 0.5
        },
        'impact': {
            'score': risk_scores['impact'],
            'severity_level': risk_level,
            'reasoning': f'Impact estimated from task priority and context. AI analysis temporarily unavailable.',
            'affected_areas': ['Timeline', 'Resources'],
            'impact_breakdown': {'timeline': 0.4, 'resources': 0.3, 'quality': 0.2, 'stakeholders': 0.1},
            'confidence': 0.5
        },
        'risk_assessment': {
            'risk_score': risk_score,
            'risk_level': risk_level,
            'priority_ranking': 'important' if risk_score >= 4 else 'routine',
            'summary': f'Basic risk assessment for {task_priority} priority task. AI analysis temporarily unavailable.',
            'calculation_method': f'Likelihood ({risk_scores["likelihood"]}) × Impact ({risk_scores["impact"]}) = {risk_score}',
            'contributing_factors': [
                {
                    'factor': 'Task Priority',
                    'contribution_percentage': 70,
                    'weight': 0.7,
                    'description': f'Priority level is {task_priority}'
                }
            ]
        },
        'risk_indicators': [
            {'indicator': 'Task progress', 'frequency': 'Daily', 'threshold': 'Less than expected progress'},
            {'indicator': 'Blocker status', 'frequency': 'As needed', 'threshold': 'Any blockers identified'}
        ],
        'mitigation_suggestions': [
            {'action': 'Monitor task progress closely', 'timeline': 'Daily', 'priority': 'medium', 'expected_impact': 'Helps identify issues early'},
            {'action': 'Ensure clear requirements', 'timeline': 'Before starting', 'priority': 'high', 'expected_impact': 'Reduces uncertainty'}
        ],
        'confidence_level': 'medium',
        'confidence_score': 0.5,
        'explainability': {
            'model_assumptions': ['Assessment based on priority level', 'Standard risk factors considered'],
            'data_limitations': ['AI analysis temporarily unavailable', 'Using rule-based fallback'],
            'alternative_interpretations': ['Actual risk may vary based on task specifics']
        }
    }


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
        3. Estimated effectiveness (%) — explain what this number is based on
        4. Required resources
        5. Responsible parties
        6. confidence (0.0-1.0): How confident you are in this strategy's viability
        7. reasoning: A 1-2 sentence explanation of WHY you chose this approach for this specific task
        8. data_basis: What data or project context this recommendation draws upon
        
        FORMAT YOUR RESPONSE AS JSON (object, NOT bare array):
        {{
          "strategies": [
            {{
              "strategy_type": "Avoid|Mitigate|Transfer|Accept",
              "title": "Strategy name",
              "description": "What this strategy accomplishes",
              "action_steps": ["step1", "step2", "step3"],
              "timeline": "Timeframe for implementation",
              "estimated_effectiveness": 75,
              "resources_required": "What's needed",
              "priority": "high|medium|low",
              "confidence": 0.85,
              "reasoning": "Why this strategy fits this specific task",
              "data_basis": "What information or indicators drove this recommendation"
            }}
          ],
          "explainability": {{
            "overall_confidence": 0.80,
            "analysis_reasoning": "Brief explanation of the overall mitigation approach",
            "assumptions": ["assumption1", "assumption2"],
            "limitations": "Any caveats about the recommendations"
          }}
        }}
        """
        
        response_text = generate_ai_content(prompt, task_type='mitigation_suggestions')
        if response_text:
            # Handle code block formatting
            if "```json" in response_text:
                response_text = response_text.split("```json")[1].split("```")[0].strip()
            elif "```" in response_text:
                response_text = response_text.split("```")[1].split("```")[0].strip()
            
            # Try to parse as new dict format first
            try:
                parsed = json.loads(response_text)
                if isinstance(parsed, dict) and 'strategies' in parsed:
                    # New format with explainability wrapper
                    strategies = parsed.get('strategies', [])
                    explainability = parsed.get('explainability', {})
                    # Ensure per-strategy defaults
                    for s in strategies:
                        s.setdefault('confidence', 0.7)
                        s.setdefault('reasoning', '')
                        s.setdefault('data_basis', '')
                    return {
                        'strategies': strategies,
                        'explainability': explainability,
                    }
                elif isinstance(parsed, list):
                    # Legacy bare-array fallback
                    return {
                        'strategies': parsed,
                        'explainability': {
                            'overall_confidence': 0.65,
                            'analysis_reasoning': 'Mitigation strategies generated (legacy format).',
                            'assumptions': [],
                            'limitations': 'Explainability data not available for this response.',
                        },
                    }
            except json.JSONDecodeError:
                pass
            
            # Fallback: try to find JSON array in the response
            json_start = response_text.find('[')
            json_end = response_text.rfind(']')
            
            if json_start != -1 and json_end != -1 and json_end > json_start:
                try:
                    strategies = json.loads(response_text[json_start:json_end + 1])
                    return {
                        'strategies': strategies,
                        'explainability': {
                            'overall_confidence': 0.60,
                            'analysis_reasoning': 'Strategies extracted from AI response (array fallback).',
                            'assumptions': [],
                            'limitations': 'Response did not include structured explainability.',
                        },
                    }
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
        
        # Calculate expected confidence score based on available data
        expected_confidence = 0.50  # Baseline for any task with title
        if description and description != 'No description provided':
            expected_confidence += 0.08
        if due_date and due_date != 'No due date set':
            expected_confidence += 0.08
        if assigned_to and assigned_to != 'Unassigned':
            expected_confidence += 0.08
        if risk_level:
            expected_confidence += 0.10
        if priority and priority.lower() != 'medium':
            expected_confidence += 0.05
        if dependencies or dependent_tasks:
            expected_confidence += 0.06
        if stakeholders:
            expected_confidence += 0.05
        if required_skills or skill_match_score or workload_impact:
            expected_confidence += 0.05
        if complexity_score:
            expected_confidence += 0.03
        if labels:
            expected_confidence += 0.02
        expected_confidence = min(expected_confidence, 0.95)  # Cap at 95%
        
        # Build comprehensive prompt
        prompt = f"""
        You are an expert project manager analyzing a task. Provide a COMPACT, actionable summary 
        highlighting ONLY the most critical insights and recommendations. Be concise - use brief bullet points.

        CRITICAL REQUIREMENTS:
        - Each section should have 2-4 bullet points maximum with key highlights only
        - Executive summary: 2 sentences maximum
        - Status reasoning: 2-3 sentences maximum  
        - Each health factor, risk, action item: 1-2 lines maximum
        - Avoid lengthy explanations - focus on actionable insights
        - Skip sections with no significant insights (return null for those)

        CONFIDENCE SCORE: Based on the available data, set confidence_score to approximately {expected_confidence:.2f}
        (This reflects data completeness - the analysis quality is good regardless of what data is available)

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

        Format your response as COMPACT JSON (key highlights only, not exhaustive):
        {
            "executive_summary": "1-2 sentence critical status and top concern (max 50 words)",
            "confidence_score": 0.XX,
            "analysis_completeness": {
                "data_quality": "high|medium|low",
                "missing_information": ["1-3 key missing items only"]
            },
            "task_health": {
                "overall_status": "healthy|at_risk|critical",
                "status_reasoning": "2-3 sentences max explaining the status",
                "health_factors": [
                    {
                        "factor": "Factor name (max 5 words)",
                        "status": "positive|neutral|negative",
                        "impact": "One line impact (max 15 words)",
                        "evidence": "Brief supporting data"
                    }
                ]
            },
            "risk_analysis": {
                "risk_assessment_validity": "appropriate|needs review|underestimated|overestimated",
                "validity_reasoning": "One sentence (max 25 words)",
                "top_risks": [
                    {
                        "risk": "Risk in max 10 words",
                        "likelihood": "high|medium|low",
                        "impact": "high|medium|low",
                        "recommended_action": "One actionable step (max 20 words)"
                    }
                ],
                "blockers_impact": "One sentence on blocker impact (max 25 words)"
            },
            "resource_assessment": {
                "assignee_fit": "good|adequate|poor",
                "fit_reasoning": "One sentence (max 20 words)",
                "capacity_status": "available|stretched|overloaded",
                "skill_gaps": ["Max 3-5 key skill gaps only"],
                "collaboration_needs": "One sentence (max 20 words)"
            },
            "stakeholder_insights": {
                "engagement_level": "engaged|neutral|disengaged",
                "satisfaction_trend": "improving|stable|declining|unknown",
                "key_concerns": ["Max 2-3 top concerns only"],
                "communication_recommendations": ["Max 2-3 actionable tips"]
            },
            "timeline_assessment": {
                "deadline_feasibility": "achievable|at_risk|unlikely",
                "feasibility_reasoning": "One sentence (max 25 words)",
                "dependency_impact": "One sentence (max 20 words)",
                "suggested_adjustments": ["Max 2-4 key timeline suggestions"]
            },
            "lean_efficiency": {
                "value_classification_appropriate": true,
                "classification_reasoning": "One sentence (max 25 words)",
                "waste_indicators": ["Max 2-4 waste indicators"],
                "efficiency_suggestions": ["Max 2-4 improvement tips"]
            },
            "prioritized_actions": [
                {
                    "action": "One specific action (max 15 words)",
                    "owner": "Who should do this",
                    "urgency": "immediate|this_week|this_month",
                    "reasoning": "Brief justification (max 15 words)"
                }
            ],
            "assumptions": ["Max 2-3 key assumptions"],
            "limitations": ["Max 2-3 key limitations"]
        }

        IMPORTANT: Complete the ENTIRE JSON structure. Do not truncate. If a section has no insights, use null or empty array.
        """
        
        response_text = generate_ai_content(prompt, task_type='task_summary')
        if response_text:
            # Handle code block formatting
            if "```json" in response_text:
                response_text = response_text.split("```json")[1].split("```")[0].strip()
            elif "```" in response_text:
                response_text = response_text.split("```")[1].strip()
            
            # Check for truncated response (incomplete JSON)
            json_text = response_text.strip()
            open_braces = json_text.count('{') - json_text.count('}')
            open_brackets = json_text.count('[') - json_text.count(']')
            is_truncated = open_braces > 0 or open_brackets > 0 or not json_text.endswith('}')
            
            if is_truncated:
                logger.warning(f"Detected truncated AI response. Attempting to repair JSON. Open braces: {open_braces}, Open brackets: {open_brackets}")
                # Try to repair truncated JSON by closing open structures
                while open_brackets > 0:
                    json_text += ']'
                    open_brackets -= 1
                while open_braces > 0:
                    json_text += '}'
                    open_braces -= 1
                response_text = json_text
            
            try:
                parsed_json = json.loads(response_text)
                # Validate that we have at least the key fields
                if not parsed_json.get('executive_summary') and not parsed_json.get('markdown_summary'):
                    logger.warning(f"AI response missing key fields. Keys present: {list(parsed_json.keys())}")
                    # Add markdown summary from the raw response if not present
                    if 'markdown_summary' not in parsed_json:
                        parsed_json['markdown_summary'] = response_text
                        parsed_json['parsing_note'] = 'AI response was parsed but missing expected structure'
                
                # Override AI's confidence score with our calculated one based on data completeness
                # This ensures consistent, data-driven confidence regardless of AI variations
                parsed_json['confidence_score'] = expected_confidence
                
                # Add truncation note if applicable
                if is_truncated:
                    parsed_json['truncation_note'] = 'Response was truncated but has been recovered. Some sections may be incomplete.'
                
                return parsed_json
            except json.JSONDecodeError as e:
                logger.warning(f"JSON parsing error in summarize_task_details: {str(e)}. Response length: {len(response_text)}")
                # Fallback to plain text for backward compatibility
                return {
                    'markdown_summary': response_text,
                    'confidence_score': expected_confidence,
                    'parsing_note': 'Returned plain text summary due to JSON parsing error'
                }
        return None
    except Exception as e:
        logger.error(f"Error summarizing task details: {str(e)}")
        return None


def generate_status_report(report_data: Dict) -> Optional[Dict]:
    """
    Generate a concise, stakeholder-ready status report for a board
    with explainability metadata.

    Args:
        report_data: Dictionary containing board metrics (tasks, completion,
                     velocity, overdue, budget, blockers, etc.)

    Returns:
        A dictionary with 'report' (formatted text), 'rag_status', 'rag_reasoning',
        'confidence_score', 'data_completeness', and 'key_data_drivers', or None on failure.
    """
    try:
        board_name = report_data.get('board_name', 'Project')
        total_tasks = report_data.get('total_tasks', 0)
        completed = report_data.get('completed_count', 0)
        in_progress = report_data.get('in_progress_count', 0)
        overdue = report_data.get('overdue_count', 0)
        completion_pct = report_data.get('completion_pct', 0)
        velocity = report_data.get('velocity', 'N/A')
        high_risk_count = report_data.get('high_risk_count', 0)
        budget_status = report_data.get('budget_status', 'N/A')
        tasks_by_column = report_data.get('tasks_by_column', [])
        report_date = report_data.get('report_date', datetime.now().strftime('%B %d, %Y'))

        column_summary = ', '.join(
            [f"{col['name']}: {col['count']}" for col in tasks_by_column]
        ) or 'N/A'

        # Calculate data completeness for explainability
        available_metrics = 0
        total_metrics = 7  # total, completed, overdue, velocity, risk, budget, columns
        if total_tasks > 0: available_metrics += 1
        if completed > 0 or total_tasks > 0: available_metrics += 1
        if overdue is not None: available_metrics += 1
        if velocity != 'N/A': available_metrics += 1
        if high_risk_count is not None: available_metrics += 1
        if budget_status != 'Not tracked' and budget_status != 'N/A': available_metrics += 1
        if tasks_by_column: available_metrics += 1
        data_completeness = round(available_metrics / total_metrics, 2)

        prompt = f"""You are an experienced project manager writing a weekly status report with Explainable AI.
Write a concise, professional stakeholder update for the project "{board_name}" using the metrics below.

## Project Metrics ({report_date})
- Total tasks: {total_tasks} | Completed: {completed} ({completion_pct}%) | In Progress: {in_progress}
- Overdue tasks: {overdue}
- Velocity: {velocity} tasks/week
- High-risk tasks: {high_risk_count}
- Budget status: {budget_status}
- Column breakdown: {column_summary}

## Instructions
Return your response as a JSON object with these keys:

{{
    "report": "The full status report as a markdown string with 4 sections: **Overall Status** (RAG 🟢/🟡/🔴 + headline), **Progress This Week** (2-3 bullets), **Key Risks & Blockers** (2-3 bullets), **Next Steps** (2-3 action items)",
    "rag_status": "green" or "amber" or "red",
    "rag_reasoning": "1-2 sentences explaining WHY you chose this RAG status based on the specific metrics above",
    "confidence_score": 0.0 to 1.0 (how confident you are in this assessment given available data),
    "key_data_drivers": ["The top 2-3 metrics that most influenced your assessment"]
}}

Keep the report concise, factual, and actionable. Write for a non-technical stakeholder audience.
Do not invent data not listed above.
Return ONLY the JSON object — no markdown fences, no extra prose."""

        result_text = generate_ai_content(prompt, task_type='status_report', use_cache=False)
        if result_text:
            # Parse JSON response
            clean = result_text.strip()
            if clean.startswith('```'):
                clean = clean.split('```json')[-1].split('```')[0].strip() if '```json' in clean else clean.split('```')[1].split('```')[0].strip()
            
            try:
                result = json.loads(clean)
                # Ensure all explainability fields are present
                result.setdefault('rag_status', 'amber')
                result.setdefault('rag_reasoning', 'Assessment based on available project metrics.')
                result.setdefault('confidence_score', round(data_completeness * 0.9, 2))
                result.setdefault('key_data_drivers', [])
                result['data_completeness'] = data_completeness
                return result
            except json.JSONDecodeError:
                logger.warning("Status report JSON parse failed, falling back to plain text")
                return {
                    'report': result_text,
                    'rag_status': 'amber',
                    'rag_reasoning': 'Could not parse structured response; showing raw report text.',
                    'confidence_score': round(data_completeness * 0.7, 2),
                    'data_completeness': data_completeness,
                    'key_data_drivers': [],
                }
        return None
    except Exception as e:
        logger.error(f"Error generating status report: {str(e)}")
        return None


# ---------------------------------------------------------------------------
# BUBBLE-UP AI SUMMARY CHAIN
# Task → Board → Strategy → Mission
# Each level generates a persistent plain-text executive summary stored in the
# model's ai_summary + ai_summary_generated_at fields.
# ---------------------------------------------------------------------------

def generate_and_save_task_summary(task) -> Optional[str]:
    """
    Generate a plain-text executive summary for a task, persist it to the DB,
    and return the summary string (or None on failure).
    Reuses the existing summarize_task_details() function and extracts
    the executive_summary section.
    """
    try:
        from django.utils import timezone as tz
        from kanban.stakeholder_models import StakeholderTaskInvolvement

        task_data = {
            'title': task.title,
            'description': task.description or 'No description provided',
            'status': task.column.name,
            'priority': task.get_priority_display(),
            'progress': task.progress if task.progress is not None else 0,
            'due_date': task.due_date.strftime('%B %d, %Y') if task.due_date else 'No due date set',
            'assigned_to': task.assigned_to.username if task.assigned_to else 'Unassigned',
            'created_by': task.created_by.username,
            'created_at': task.created_at.strftime('%B %d, %Y'),
            'risk_level': task.risk_level,
            'risk_score': task.risk_score,
            'risk_likelihood': task.risk_likelihood,
            'risk_impact': task.risk_impact,
            'risk_indicators': task.risk_indicators if task.risk_indicators else [],
            'mitigation_suggestions': task.mitigation_suggestions if task.mitigation_suggestions else [],
            'stakeholders': [
                {
                    'name': inv.stakeholder.name,
                    'involvement_type': inv.get_involvement_type_display(),
                    'engagement_status': inv.get_engagement_status_display(),
                    'satisfaction_rating': inv.satisfaction_rating,
                    'feedback': inv.feedback,
                }
                for inv in StakeholderTaskInvolvement.objects.filter(task=task).select_related('stakeholder')
            ],
            'required_skills': task.required_skills if task.required_skills else [],
            'skill_match_score': task.skill_match_score,
            'workload_impact': task.get_workload_impact_display() if task.workload_impact else None,
            'collaboration_required': task.collaboration_required,
            'complexity_score': task.complexity_score,
            'parent_task': task.parent_task.title if task.parent_task else None,
            'subtasks': [s.title for s in task.subtasks.all()],
            'dependencies': [
                f"{dep.title} ({dep.progress}% complete)"
                for dep in task.dependencies.all()
            ],
            'dependent_tasks': [f"{t.title} (waiting)" for t in task.dependent_tasks.all()],
            'related_tasks': [r.title for r in task.related_tasks.all()],
            'labels': [{'name': l.name, 'category': l.category} for l in task.labels.all()],
            'comments_count': task.comments.count(),
        }

        result = summarize_task_details(task_data)
        if not result:
            return None

        # Extract the executive summary text — fall back to markdown_summary if missing
        summary_text = None
        es = result.get('executive_summary')
        if isinstance(es, dict):
            summary_text = es.get('one_line_summary') or es.get('summary') or str(es)
        elif isinstance(es, str):
            summary_text = es
        if not summary_text:
            summary_text = result.get('markdown_summary') or str(result)

        # Build rich metadata from the full AI response
        metadata = {
            'confidence_score': result.get('confidence_score'),
            'analysis_completeness': result.get('analysis_completeness'),
            'task_health': result.get('task_health'),
            'risk_analysis': result.get('risk_analysis'),
            'resource_assessment': result.get('resource_assessment'),
            'stakeholder_insights': result.get('stakeholder_insights'),
            'timeline_assessment': result.get('timeline_assessment'),
            'lean_efficiency': result.get('lean_efficiency'),
            'prioritized_actions': result.get('prioritized_actions'),
            'assumptions': result.get('assumptions', []),
            'limitations': result.get('limitations', []),
        }
        # Remove None values so we only store meaningful data
        metadata = {k: v for k, v in metadata.items() if v is not None}

        if result.get('truncation_note'):
            metadata['truncation_note'] = result['truncation_note']
        if result.get('parsing_note'):
            metadata['parsing_note'] = result['parsing_note']

        # Persist
        task.ai_summary = summary_text
        task.ai_summary_generated_at = tz.now()
        task.ai_summary_metadata = metadata
        task.save(update_fields=['ai_summary', 'ai_summary_generated_at', 'ai_summary_metadata'])
        return summary_text

    except Exception as e:
        logger.error(f"Error in generate_and_save_task_summary (task {task.pk}): {e}")
        return None


def generate_and_save_board_summary(board) -> Optional[str]:
    """
    Collect ai_summary values from all tasks on the board (generating any that are
    missing), send them to the LLM for a board-level synthesis, persist to the Board
    model, and return the summary string.
    """
    try:
        from django.utils import timezone as tz
        from kanban.models import Task

        tasks = Task.objects.filter(column__board=board, item_type='task').select_related(
            'column', 'assigned_to', 'created_by', 'parent_task'
        ).prefetch_related('labels')

        task_snippets = []
        for task in tasks:
            snippet = task.ai_summary
            if not snippet:
                # Use raw task data as fallback instead of generating a full AI summary
                # per task (avoids 30+ sequential API calls that cause 15-20 min hangs).
                desc = (task.description or '').strip()[:200]
                status = task.column.name if task.column else 'Unknown'
                progress = task.progress or 0
                snippet = f"{status}, {progress}% complete" + (
                    f" — {desc}" if desc else ""
                )
            if snippet:
                task_snippets.append(f"- [{task.title}] {snippet}")

        if not task_snippets:
            summary_text = f"No tasks available yet on board '{board.name}'."
            metadata = {'confidence_score': 0.0, 'data_completeness': 0.0, 'tasks_analyzed': 0, 'tasks_with_ai_summary': 0}
        else:
            snippets_block = "\n".join(task_snippets[:40])  # cap to keep prompt manageable
            total = tasks.count()
            completed = tasks.filter(progress=100).count()
            tasks_with_summary = sum(1 for t in tasks if t.ai_summary)
            data_completeness = round(tasks_with_summary / total, 2) if total else 0.0

            prompt = f"""You are a senior project manager with Explainable AI capabilities.
Synthesise the following individual task summaries for the project board "{board.name}" into a structured JSON response.

Board stats: {total} total tasks, {completed} completed ({round(completed/total*100) if total else 0}% done).
{tasks_with_summary} of {total} tasks have AI-generated summaries (rest use fallback data).

Task summaries:
{snippets_block}

Return a JSON object with these keys:
{{
    "summary": "A concise board-level summary paragraph (3-5 sentences). Focus on: overall progress, key risks, critical next steps, and team health. Be factual and actionable. Do NOT invent data.",
    "confidence_score": 0.0 to 1.0 (how confident you are given the data quality),
    "key_risk_drivers": ["Top 2-3 risk factors or themes identified across tasks"],
    "data_freshness_note": "Brief note on data quality, e.g. how many tasks had full AI summaries vs fallback"
}}

Return ONLY the JSON object — no markdown fences, no extra prose."""

            raw = generate_ai_content(prompt, task_type='board_summary', use_cache=False)
            summary_text = None
            metadata = {
                'confidence_score': round(0.5 + data_completeness * 0.4, 2),
                'data_completeness': data_completeness,
                'tasks_analyzed': total,
                'tasks_with_ai_summary': tasks_with_summary,
                'key_risk_drivers': [],
                'data_freshness_note': f"{tasks_with_summary}/{total} tasks had AI summaries.",
            }

            if raw:
                clean = raw.strip()
                if clean.startswith('```'):
                    clean = clean.split('```json')[-1].split('```')[0].strip() if '```json' in clean else clean.split('```')[1].split('```')[0].strip()
                try:
                    parsed = json.loads(clean)
                    summary_text = parsed.get('summary', clean)
                    metadata['confidence_score'] = min(1.0, max(0.0, float(parsed.get('confidence_score', metadata['confidence_score']))))
                    metadata['key_risk_drivers'] = parsed.get('key_risk_drivers', [])
                    if parsed.get('data_freshness_note'):
                        metadata['data_freshness_note'] = parsed['data_freshness_note']
                except (json.JSONDecodeError, ValueError):
                    summary_text = raw  # fallback to raw text

        if not summary_text:
            return None

        board.ai_summary = summary_text
        board.ai_summary_generated_at = tz.now()
        board.ai_summary_metadata = metadata
        board.save(update_fields=['ai_summary', 'ai_summary_generated_at', 'ai_summary_metadata'])
        return summary_text

    except Exception as e:
        logger.error(f"Error in generate_and_save_board_summary (board {board.pk}): {e}")
        return None


def generate_and_save_strategy_summary(strategy) -> Optional[str]:
    """
    Collect ai_summary values from all boards under the strategy (generating any that
    are missing), synthesise a strategy-level summary, persist it, and return the text.
    """
    try:
        from django.utils import timezone as tz

        boards = strategy.boards.all()
        board_snippets = []
        for board in boards:
            snippet = board.ai_summary
            if not snippet:
                # Use board stats as fallback instead of triggering a full board
                # summary (which would cascade into generating all task summaries).
                try:
                    from kanban.models import Task as _Task
                    total = _Task.objects.filter(column__board=board, item_type='task').count()
                    completed = _Task.objects.filter(
                        column__board=board, item_type='task', progress=100
                    ).count()
                    snippet = (
                        f"{total} tasks, {completed} completed "
                        f"({round(completed / total * 100) if total else 0}% done)"
                    )
                except Exception:
                    snippet = board.name
            if snippet:
                board_snippets.append(f"- [{board.name}] {snippet}")

        if not board_snippets:
            summary_text = f"No boards linked to strategy '{strategy.name}' yet."
        else:
            snippets_block = "\n".join(board_snippets)
            prompt = f"""You are a senior strategy analyst. Synthesise the following board-level summaries
for the strategy "{strategy.name}" (under mission: "{strategy.mission.name}") into one concise
strategy-level summary (3-5 sentences).
Focus on: strategic progress, cross-board risks and dependencies, and highest-priority actions.
Be factual and actionable. Do NOT invent data not listed below.

Board summaries:
{snippets_block}

Write ONLY the summary paragraph — no headings, no bullet points, no JSON."""

            summary_text = generate_ai_content(prompt, task_type='board_analytics_summary', use_cache=False)

        if not summary_text:
            return None

        strategy.ai_summary = summary_text
        strategy.ai_summary_generated_at = tz.now()
        strategy.save(update_fields=['ai_summary', 'ai_summary_generated_at'])
        return summary_text

    except Exception as e:
        logger.error(f"Error in generate_and_save_strategy_summary (strategy {strategy.pk}): {e}")
        return None


def generate_and_save_mission_summary(mission) -> Optional[str]:
    """
    Collect ai_summary values from all strategies under the mission (generating any
    that are missing), synthesise a mission-level summary, persist it, and return the text.
    """
    try:
        from django.utils import timezone as tz

        strategies = mission.strategies.all()
        strategy_snippets = []
        for strategy in strategies:
            snippet = strategy.ai_summary
            if not snippet:
                # Use description/status as fallback instead of triggering recursive
                # board + task summary generation for every missing strategy.
                snippet = (
                    (strategy.description or '').strip()[:200]
                    or f"Strategy '{strategy.name}' — status: {strategy.status}"
                )
            if snippet:
                strategy_snippets.append(f"- [{strategy.name}] {snippet}")

        if not strategy_snippets:
            summary_text = f"No strategies defined for mission '{mission.name}' yet."
        else:
            snippets_block = "\n".join(strategy_snippets)
            prompt = f"""You are a C-level executive advisor. Synthesise the following strategy-level summaries
for the mission "{mission.name}" into one concise mission-level executive summary (3-5 sentences).
Focus on: mission progress, strategic alignment, key risks, and critical next steps.
Be factual, high-level, and actionable. Do NOT invent data not listed below.

Strategy summaries:
{snippets_block}

Write ONLY the summary paragraph — no headings, no bullet points, no JSON."""

            summary_text = generate_ai_content(prompt, task_type='board_analytics_summary', use_cache=False)

        if not summary_text:
            return None

        mission.ai_summary = summary_text
        mission.ai_summary_generated_at = tz.now()
        mission.save(update_fields=['ai_summary', 'ai_summary_generated_at'])
        return summary_text

    except Exception as e:
        logger.error(f"Error in generate_and_save_mission_summary (mission {mission.pk}): {e}")
        return None


# ---------------------------------------------------------------------------
# PRIZMBRIEF — AI Presentation Content Generator
# Generates structured slide-by-slide presentation content from live board data,
# tailored to the chosen audience (client / executive / team / technical)
# and detail mode (Executive Summary / Full Briefing).
# ---------------------------------------------------------------------------

def generate_prizmbrief(brief_data: Dict) -> Optional[str]:
    """
    Generate audience-aware, slide-by-slide presentation content for a board.

    Args:
        brief_data: Dict with board metrics + audience / purpose / mode choices.

    Returns:
        Formatted plain-text string with slides delimited by
        --- SLIDE N: Title --- markers, or None on failure.
    """
    try:
        board_name      = brief_data.get('board_name', 'Project')
        report_date     = brief_data.get('report_date', datetime.now().strftime('%B %d, %Y'))
        user_name       = brief_data.get('user_name', 'Project Manager')
        audience        = brief_data.get('audience', 'client')
        audience_label  = brief_data.get('audience_label', audience)
        purpose_label   = brief_data.get('purpose_label', 'Project Status Update')
        mode            = brief_data.get('mode', 'executive_summary')

        total_tasks     = brief_data.get('total_tasks', 0)
        completed       = brief_data.get('completed', 0)
        in_progress     = brief_data.get('in_progress', 0)
        not_started     = brief_data.get('not_started', 0)
        completion_pct  = brief_data.get('completion_pct', 0)
        overdue         = brief_data.get('overdue', 0)
        blocked_count   = brief_data.get('blocked_count', 0)
        blocked_list    = brief_data.get('blocked_list', [])
        velocity_now    = brief_data.get('velocity_now', 0)
        velocity_change = brief_data.get('velocity_change', 0)
        high_risk_count = brief_data.get('high_risk_count', 0)
        tasks_by_column = brief_data.get('tasks_by_column', [])
        workload        = brief_data.get('workload', [])
        budget          = brief_data.get('budget', {})
        milestones      = brief_data.get('milestones', [])
        new_tasks_count = brief_data.get('new_tasks_count', 0)
        total_open      = brief_data.get('total_open', 0)

        # ── Derive overall RAG status ─────────────────────────────────────────
        if completion_pct >= 70 and overdue == 0 and blocked_count == 0:
            rag = "🟢 ON TRACK"
        elif overdue > 3 or blocked_count > 3 or high_risk_count > 2:
            rag = "🔴 AT RISK"
        else:
            rag = "🟡 ON TRACK WITH MINOR RISKS"

        # ── Budget summary line ───────────────────────────────────────────────
        if budget:
            currency   = budget.get('currency', 'USD')
            allocated  = budget.get('allocated', 0)
            spent      = budget.get('spent', 0)
            remaining  = budget.get('remaining', 0)
            pct_spent  = budget.get('pct_spent', 0)
            bud_status = budget.get('status', '')
            budget_str = (
                f"Allocated: {currency} {allocated:,.2f} | "
                f"Spent: {currency} {spent:,.2f} ({pct_spent}%) | "
                f"Remaining: {currency} {remaining:,.2f} | "
                f"Status: {bud_status}"
            )
        else:
            budget_str = "Budget data not available"

        # ── Column & team summaries ───────────────────────────────────────────
        column_summary = ", ".join(
            f"{c['name']}: {c['count']}" for c in tasks_by_column
        ) or "N/A"

        workload_summary = "\n".join(
            f"  - {w['name']}: {w['open_tasks']} open tasks ({w['capacity']}% of board load)"
            for w in workload
        ) or "  No individual assignments found"

        blocked_summary = "\n".join(
            f"  - '{b['title']}' — Owner: {b['assigned_to__username'] or 'Unassigned'}"
            for b in blocked_list
        ) or "  None identified"

        milestone_summary = "\n".join(
            f"  - {m['due_date']}: {m['title']}" for m in milestones
        ) or "  No upcoming milestones found"

        velocity_trend = (
            f"{velocity_now} tasks/week ({'+' if velocity_change >= 0 else ''}{velocity_change}% vs prior week)"
        )

        # ── Audience-specific instruction block ───────────────────────────────
        if audience in ('client', 'executive'):
            audience_instructions = """
AUDIENCE FOCUS — Client / Executive:
- Emphasise: Overall health (RAG), schedule variance, budget status, top 3 risks, next milestone, decisions needed.
- Omit: Individual task names, developer workload details, sprint velocity, technical jargon.
- Tone: Non-technical, leadership-friendly, concise paragraphs with supporting bullet points."""

        elif audience == 'team':
            audience_instructions = """
AUDIENCE FOCUS — Internal Team:
- Emphasise: Task status breakdown, blocked tasks with specific reasons, individual workload, sprint velocity trend, scope creep notice, clear action items with named owners.
- Include budget headline only (no breakdown).
- Tone: Collaborative, direct, action-oriented."""

        else:  # technical
            audience_instructions = """
AUDIENCE FOCUS — Technical Team / Developers:
- Emphasise: Detailed task breakdown by status, blocked tasks with reasons, dependency conflicts, sprint velocity, burndown trend, specific technical action items.
- Include workload data and who is overloaded.
- Omit: Deep budget financials (show headline only).
- Tone: Precise, technical, no marketing fluff."""

        # ── Slide count instruction ───────────────────────────────────────────
        if mode == 'executive_summary':
            slide_count_instruction = """
SLIDE COUNT: Generate exactly 5–6 slides covering:
  Slide 1: Project Snapshot (name, date, presenter, overall RAG status)
  Slide 2: Progress Overview (completion %, tasks done/total, timeline variance)
  Slide 3: Budget Health (if budget data available, else replace with Key Achievements)
  Slide 4: Key Risks & Issues
  Slide 5: Next Milestones / Roadmap
  Slide 6: Decisions & Actions Needed"""
        else:  # full_briefing
            slide_count_instruction = """
SLIDE COUNT: Generate exactly 8–10 slides covering:
  Slide 1: Project Snapshot (name, date, presenter, overall RAG status)
  Slide 2: Progress Overview (completion %, tasks done/total, timeline variance)
  Slide 3: Budget Health (if budget data available, else replace with Key Achievements)
  Slide 4: Key Risks & Issues
  Slide 5: Next Milestones / Roadmap
  Slide 6: Decisions & Actions Needed
  Slide 7: Team & Workload Analysis
  Slide 8: Task Detail Breakdown (by status, top blocked tasks)
  Slide 9: AI Insights & Anomalies (velocity trend, scope creep, forecast)
  Slide 10: Recommended Priority Actions (next 7 days, with named owners)"""

        # ── Full prompt ───────────────────────────────────────────────────────
        prompt = f"""You are an expert project manager and business storyteller.
Generate a slide-by-slide presentation content brief for the project "{board_name}".
Each slide must be wrapped in a delimiter on its own line:  --- SLIDE N: Title ---
where N is the slide number and Title is the descriptive slide heading.

The user will copy this output into Gamma AI or PowerPoint to build the actual deck.
Write the content in a way that a presentation tool can directly use it — clear headings,
tight bullet points, one key insight per bullet, and a "Suggested visual:" note in italics
for each slide indicating the best chart or graphic type.

## Live Board Data ({report_date})
- Board: {board_name}
- Prepared by: {user_name}
- Purpose: {purpose_label}
- Audience: {audience_label}
- Overall Status: {rag}
- Total tasks: {total_tasks} | Completed: {completed} ({completion_pct}%) | In Progress: {in_progress} | Not Started: {not_started}
- Overdue tasks: {overdue}
- Blocked tasks: {blocked_count}
  Top blocked:
{blocked_summary}
- Sprint velocity: {velocity_trend}
- High-risk tasks: {high_risk_count}
- Scope change since baseline: {new_tasks_count} tasks added beyond baseline (positive = scope creep signal)
- Budget: {budget_str}
- Column breakdown: {column_summary}
- Next milestones:
{milestone_summary}
- Team workload (open tasks per person):
{workload_summary}

{audience_instructions}

{slide_count_instruction}

## Output Rules
1. Start each slide immediately with its delimiter: --- SLIDE N: Title ---
2. Under each slide write: bullet points for the main content, then one line: *Suggested visual: [chart/image type]*
3. Do NOT add any text before the first slide delimiter.
4. Do NOT add any preamble, preamble headings, or closing remarks outside the slide blocks.
5. Be factual — only use numbers from the data above. Do not invent data.
6. If a data point is "Not available", acknowledge it briefly rather than fabricating a number.
7. IMPORTANT: Always include a FINAL slide titled "Data Sources & Confidence" that covers:
   - A bullet list of which data metrics were available and used (tasks, velocity, budget, milestones, etc.)
   - Which data was missing or limited (e.g., "No budget data", "No milestones set")
   - An overall confidence note: how reliable is this brief given the available data (High / Medium / Low)
   - A brief note on data freshness (when metrics were captured)
   This transparency slide helps stakeholders understand the basis of this AI-generated content.
"""

        result = generate_ai_content(
            prompt,
            task_type='prizmbrief',
            use_cache=False,
        )
        return result

    except Exception as e:
        logger.error(f"Error generating PrizmBrief: {e}")
        return None


# ---------------------------------------------------------------------------
# WORKSPACE GENERATION — AI-powered onboarding
# Takes an organization goal and produces a full hierarchy:
#   Goal → Missions → Strategies → Boards (with columns) → Tasks
# ---------------------------------------------------------------------------

def generate_workspace_from_goal(goal_text: str) -> Optional[Dict]:
    """
    Generate a complete workspace hierarchy from an organization goal.

    Calls Gemini with a structured prompt and returns a JSON dict:
    {
      "goal": { "name", "description", "target_metric", "target_date" },
      "missions": [
        { "name", "description", "strategies": [
          { "name", "description", "boards": [
            { "name", "description", "columns": [...], "tasks": [...] }
          ]}
        ]}
      ]
    }

    Returns None on failure (caller should invoke the template fallback).
    """
    today = datetime.now().strftime('%Y-%m-%d')

    prompt = f"""
You are an expert project management consultant.  A user just signed up for
PrizmAI — an AI-powered project management tool.  They provided their
**organization goal** and you need to design a complete workspace hierarchy
that will get them operational immediately.

## The user's organization goal
\"\"\"{goal_text}\"\"\"

## PrizmAI hierarchy (you must produce every level)

1. **Organization Goal** — the apex strategic objective.
2. **Missions** (2-3 per goal) — major focus areas that serve the goal.
3. **Strategies** (1-2 per mission) — concrete approaches to fulfil each mission.
4. **Boards** (1 per strategy) — Kanban boards where the work happens.
   Each board has 4-7 **columns** (the first column MUST be "To Do").
5. **Tasks** (3-5 per board) — actionable starter items placed in the
   first column ("To Do").  Each task needs a priority and item_type.

## Rules
- Missions, strategies and boards must feel **surprisingly specific and
  useful** — avoid generic corporate buzzwords.
- Task titles should be concrete actions a team member could start today.
- Priorities: Critical, High, Medium, Low.
- Item types: task, bug, feature, story.
- Do not assign any tasks to any specific user. Leave all task assignees
  unassigned — the user will assign them to their team members after setup.
- target_date must be a date string in YYYY-MM-DD format, at least 3 months
  from today ({today}).
- Keep descriptions concise — 1-3 sentences max.

## Output format — strict JSON, no markdown, no commentary
Return ONLY the JSON object below — no surrounding text, no ```json fences.

{{
  "goal": {{
    "name": "Short goal name (max 200 chars)",
    "description": "1-3 sentences of context and success criteria",
    "target_metric": "Measurable target (e.g. '15% market share increase')",
    "target_date": "YYYY-MM-DD"
  }},
  "missions": [
    {{
      "name": "Mission name",
      "description": "1-2 sentences",
      "why": "1 sentence explaining why this mission is critical for the goal",
      "strategies": [
        {{
          "name": "Strategy name",
          "description": "1-2 sentences",
          "boards": [
            {{
              "name": "Board name",
              "description": "1-2 sentences about this board's purpose",
              "columns": ["To Do", "In Progress", "Review", "Done"],
              "tasks": [
                {{
                  "title": "Concrete task title",
                  "description": "1-2 sentences",
                  "priority": "High",
                  "item_type": "task"
                }}
              ]
            }}
          ]
        }}
      ]
    }}
  ],
  "explainability": {{
    "reasoning": "2-3 sentences explaining why you structured the workspace this way — what about the goal drove these specific missions and strategies",
    "assumptions": ["Assumption 1 you made about the organization or goal", "Assumption 2"],
    "customization_hints": ["Suggestion 1 for what the user might want to adjust", "Suggestion 2"],
    "confidence_score": 0.0 to 1.0 (how confident you are that this structure is useful for the stated goal)
  }}
}}
"""

    try:
        response_text = generate_ai_content(
            prompt,
            task_type='workspace_generation',
            use_cache=False,   # Each user's goal is unique
        )
        if not response_text:
            logger.error("Empty response from Gemini for workspace generation")
            return None

        # Strip code-block fences if present
        if "```json" in response_text:
            response_text = response_text.split("```json")[1].split("```")[0].strip()
        elif "```" in response_text:
            response_text = response_text.split("```")[1].strip()

        response_text = response_text.strip()

        # Isolate JSON object
        if not response_text.startswith('{'):
            start_idx = response_text.find('{')
            end_idx = response_text.rfind('}')
            if start_idx != -1 and end_idx != -1:
                response_text = response_text[start_idx:end_idx + 1]

        data = json.loads(response_text)

        # Basic structural validation
        if 'goal' not in data or 'missions' not in data:
            logger.error("Workspace generation JSON missing top-level keys")
            return None
        if not isinstance(data['missions'], list) or len(data['missions']) == 0:
            logger.error("Workspace generation returned no missions")
            return None

        # Deep hierarchy validation — reject truncated responses
        for mi, mission in enumerate(data['missions']):
            if not isinstance(mission.get('strategies'), list) or len(mission['strategies']) == 0:
                logger.error(f"Workspace generation truncated: Mission {mi} has no strategies")
                return None
            for si, strategy in enumerate(mission['strategies']):
                if not isinstance(strategy.get('boards'), list) or len(strategy['boards']) == 0:
                    logger.error(f"Workspace generation truncated: Strategy {si} in Mission {mi} has no boards")
                    return None
                for bi, board in enumerate(strategy['boards']):
                    if not isinstance(board.get('tasks'), list) or len(board['tasks']) == 0:
                        logger.error(f"Workspace generation truncated: Board {bi} in Strategy {si}/Mission {mi} has no tasks")
                        return None
                    if not isinstance(board.get('columns'), list) or len(board['columns']) == 0:
                        board['columns'] = ['To Do', 'In Progress', 'Review', 'Done']

        return data

    except json.JSONDecodeError as e:
        logger.error(f"JSON parse error in workspace generation: {e}")
        return None
    except Exception as e:
        logger.error(f"Error in generate_workspace_from_goal: {e}")
        return None


def get_fallback_workspace(goal_text: str) -> Dict:
    """
    Template-based fallback workspace when Gemini is unavailable.

    Returns a sensible default hierarchy so the user is never stuck.
    """
    today = datetime.now()
    target = (today + timedelta(days=180)).strftime('%Y-%m-%d')

    return {
        "goal": {
            "name": goal_text[:200],
            "description": f"Organization goal: {goal_text}",
            "target_metric": "To be defined",
            "target_date": target,
        },
        "missions": [
            {
                "name": "Planning & Foundation",
                "description": "Establish the groundwork, define scope, and align stakeholders.",
                "strategies": [
                    {
                        "name": "Project Kickoff & Requirements",
                        "description": "Define clear requirements, milestones, and team responsibilities.",
                        "boards": [
                            {
                                "name": "Project Setup",
                                "description": "Initial planning, requirements gathering, and team onboarding.",
                                "columns": ["To Do", "In Progress", "Review", "Done"],
                                "tasks": [
                                    {"title": "Define project scope and objectives", "description": "Document the high-level scope, deliverables, and success criteria.", "priority": "High", "item_type": "task"},
                                    {"title": "Identify key stakeholders", "description": "List all stakeholders and their roles in the project.", "priority": "High", "item_type": "task"},
                                    {"title": "Create initial project timeline", "description": "Draft a high-level timeline with major milestones.", "priority": "Medium", "item_type": "task"},
                                    {"title": "Set up team communication channels", "description": "Establish Slack/Teams channels, meetings cadence, and reporting structure.", "priority": "Medium", "item_type": "task"},
                                ],
                            }
                        ],
                    }
                ],
            },
            {
                "name": "Execution & Delivery",
                "description": "Execute the core work, track progress, and deliver results.",
                "strategies": [
                    {
                        "name": "Core Delivery Pipeline",
                        "description": "Manage the primary workstream to deliver key outcomes.",
                        "boards": [
                            {
                                "name": "Delivery Tracker",
                                "description": "Track day-to-day execution of core deliverables.",
                                "columns": ["To Do", "In Progress", "Testing", "Done"],
                                "tasks": [
                                    {"title": "Break down first deliverable into subtasks", "description": "Decompose the first major deliverable into actionable work items.", "priority": "High", "item_type": "task"},
                                    {"title": "Assign team responsibilities", "description": "Map each work item to a team member based on skills and capacity.", "priority": "Medium", "item_type": "task"},
                                    {"title": "Establish progress reporting cadence", "description": "Set up weekly status updates and review checkpoints.", "priority": "Medium", "item_type": "task"},
                                ],
                            }
                        ],
                    }
                ],
            },
        ],
    }


# ---------------------------------------------------------------------------
# WORKSPACE VALIDATION — HITL coherence check
# ---------------------------------------------------------------------------

def validate_workspace_coherence(workspace_data: Dict) -> Dict:
    """
    Send the edited workspace JSON to Gemini for a lightweight coherence check.

    Returns a dict with:
    {
      "status": "clear" | "suggestions" | "structural_issue",
      "flags": [
        {
          "level": "goal" | "mission" | "strategy" | "board",
          "item_title": "string",
          "message": "plain English description",
          "suggested_fix": "plain English suggestion"
        }
      ]
    }
    """
    # Build a compact representation for the prompt
    goal_obj = workspace_data.get('goal', {})
    goal_name = goal_obj.get('name', '')
    goal_description = goal_obj.get('description', '')
    missions_summary = []
    for m in workspace_data.get('missions', []):
        strategies = []
        for s in m.get('strategies', []):
            boards = [b.get('name', '') for b in s.get('boards', [])]
            strategies.append({'name': s.get('name', ''), 'boards': boards})
        missions_summary.append({
            'name': m.get('name', ''),
            'strategies': strategies
        })

    workspace_summary = json.dumps({
        'goal': goal_name,
        'goal_description': goal_description,
        'missions': missions_summary
    }, indent=2)

    prompt = f"""You are a strict reviewer of an AI-generated project management workspace.
The user may have edited titles or deleted items. Your job is to catch semantic mismatches and structural problems.

Workspace structure:
{workspace_summary}

CRITICAL — Semantic coherence checks (do these FIRST):
1. For each Mission, evaluate whether its title could plausibly be a strategic pillar for achieving the stated Goal. Consider the Goal's domain, industry, and objectives. If a Mission title is generic, nonsensical, or completely unrelated to the Goal domain, you MUST flag it as a suggestion. Example: a Mission called "Random Xyz Operations" under a restaurant inventory SaaS goal is clearly incoherent and must be flagged.
2. For each Strategy, evaluate whether its title makes logical sense as an approach to achieve its parent Mission. If a Strategy title is unrelated to its Mission, flag it.
3. For each Board, check that its name relates to its parent Strategy.

Structural checks:
4. Are there structural gaps (e.g. a Mission with no Strategies, a Strategy with no Boards)?
5. Are any titles duplicated across the same level?

Rules:
- Return a MAXIMUM of 3 flags. Prioritise semantic mismatches over structural gaps.
- If everything looks fine AND every Mission logically relates to the Goal, return status "clear" with an empty flags array.
- If there are structural problems (orphaned items, empty parents), return status "structural_issue".
- If there are naming/coherence suggestions, return status "suggestions".
- When in doubt about whether a Mission fits the Goal, FLAG IT — err on the side of flagging rather than passing.
- Return ONLY the JSON object below — no surrounding text, no markdown fences.

{{
  "status": "clear" | "suggestions" | "structural_issue",
  "flags": [
    {{
      "level": "goal | mission | strategy | board",
      "item_title": "the title of the item in question",
      "message": "plain English description of the issue",
      "suggested_fix": "plain English suggestion for how to fix it"
    }}
  ]
}}"""

    try:
        response_text = generate_ai_content(
            prompt,
            task_type='simple',
            use_cache=False,
        )
        if not response_text:
            logger.error("Empty response from Gemini for workspace validation")
            return {'status': 'clear', 'flags': []}

        # Strip code-block fences if present
        if "```json" in response_text:
            response_text = response_text.split("```json")[1].split("```")[0].strip()
        elif "```" in response_text:
            response_text = response_text.split("```")[1].strip()

        response_text = response_text.strip()
        if not response_text.startswith('{'):
            start_idx = response_text.find('{')
            end_idx = response_text.rfind('}')
            if start_idx != -1 and end_idx != -1:
                response_text = response_text[start_idx:end_idx + 1]

        result = json.loads(response_text)

        # Validate structure
        if 'status' not in result:
            result['status'] = 'clear'
        if 'flags' not in result or not isinstance(result['flags'], list):
            result['flags'] = []

        # Cap at 3 flags
        result['flags'] = result['flags'][:3]

        return result

    except json.JSONDecodeError as e:
        logger.error(f"JSON parse error in workspace validation: {e}")
        return {'status': 'clear', 'flags': []}
    except Exception as e:
        logger.error(f"Error in validate_workspace_coherence: {e}")
        return {'status': 'clear', 'flags': []}


def regenerate_child_titles(parent_title: str, parent_level: str, current_children: list) -> Optional[list]:
    """
    Given a renamed parent and its current child titles, generate updated
    child titles that are coherent with the new parent name.

    Args:
        parent_title: The new title of the renamed parent
        parent_level: 'mission' or 'strategy'
        current_children: List of current child title strings

    Returns:
        A list of new title strings in the same order, or None on failure.
    """
    child_type = 'Strategies' if parent_level == 'mission' else 'Boards'

    prompt = f"""You are an expert project management consultant.
A user renamed a {parent_level.title()} in their workspace to: "{parent_title}"

The current {child_type} under this {parent_level.title()} are:
{json.dumps(current_children)}

Generate updated titles for these {child_type} that are coherent with the new
{parent_level.title()} name. Keep the same number of items. Make titles specific
and actionable — avoid generic corporate buzzwords.

Return ONLY a JSON array of new titles in the same order — no surrounding text,
no markdown fences.

Example: ["New Title 1", "New Title 2"]"""

    try:
        response_text = generate_ai_content(
            prompt,
            task_type='simple',
            use_cache=False,
        )
        if not response_text:
            logger.error("Empty response from Gemini for child title regeneration")
            return None

        # Strip code-block fences if present
        if "```json" in response_text:
            response_text = response_text.split("```json")[1].split("```")[0].strip()
        elif "```" in response_text:
            response_text = response_text.split("```")[1].strip()

        response_text = response_text.strip()
        if not response_text.startswith('['):
            start_idx = response_text.find('[')
            end_idx = response_text.rfind(']')
            if start_idx != -1 and end_idx != -1:
                response_text = response_text[start_idx:end_idx + 1]

        titles = json.loads(response_text)

        if not isinstance(titles, list):
            logger.error("Child title regeneration did not return a list")
            return None

        # Ensure same count
        if len(titles) != len(current_children):
            logger.warning(f"Regeneration returned {len(titles)} titles but expected {len(current_children)}")
            # Pad or truncate to match
            while len(titles) < len(current_children):
                titles.append(current_children[len(titles)])
            titles = titles[:len(current_children)]

        return titles

    except json.JSONDecodeError as e:
        logger.error(f"JSON parse error in child title regeneration: {e}")
        return None
    except Exception as e:
        logger.error(f"Error in regenerate_child_titles: {e}")
        return None


# ---------------------------------------------------------------------------
# GOAL-AWARE ANALYTICS — Board classification, narratives, proxy metrics
# ---------------------------------------------------------------------------

def classify_board_project_type(board):
    """
    Classify a board into one of 3 project type profiles using Gemini.

    Traverses the hierarchy (board → strategy → mission → goal) to gather
    context, then asks Gemini to classify:
      - product_tech
      - marketing_campaign
      - operations

    Returns a dict: {project_type, confidence, reason} or None on failure.
    """
    import time
    from api.ai_usage_utils import track_ai_request
    from kanban.audit_utils import log_audit

    # --- Gather context ---
    board_name = board.name
    board_description = board.description or ''
    column_names = list(board.columns.values_list('name', flat=True))

    goal_text = ''
    try:
        if board.strategy and board.strategy.mission:
            mission = board.strategy.mission
            if mission.organization_goal:
                goal = mission.organization_goal
                goal_text = goal.name
                if goal.description:
                    goal_text += f' — {goal.description}'
    except Exception:
        pass  # hierarchy may be incomplete

    # --- Build prompt ---
    prompt = (
        "You are a project classification engine. Classify the following project board "
        "into exactly one of three types: product_tech, marketing_campaign, or operations.\n\n"
        f"Board name: {board_name}\n"
        f"Board description: {board_description}\n"
        f"Column names: {', '.join(column_names) if column_names else 'None'}\n"
        f"Linked Goal: {goal_text if goal_text else 'None'}\n\n"
        "Respond with ONLY valid JSON — no preamble, no markdown, no explanation outside the JSON:\n"
        '{\n'
        '  "project_type": "product_tech" | "marketing_campaign" | "operations",\n'
        '  "confidence": 0.0 to 1.0,\n'
        '  "reason": "one sentence explaining the classification"\n'
        '}'
    )

    start_ms = time.time()
    result = generate_ai_content(prompt, task_type='board_classification', use_cache=False)
    elapsed_ms = int((time.time() - start_ms) * 1000)

    if not result:
        logger.error(f"Board classification returned None for board {board.id}")
        return None

    try:
        # Strip markdown fences if present
        cleaned = result.strip()
        if cleaned.startswith('```'):
            cleaned = '\n'.join(cleaned.split('\n')[1:])
        if cleaned.endswith('```'):
            cleaned = cleaned[:cleaned.rfind('```')]
        data = json.loads(cleaned.strip())

        project_type = data.get('project_type', 'operations')
        confidence = float(data.get('confidence', 0.0))
        reason = data.get('reason', '')

        valid_types = ['product_tech', 'marketing_campaign', 'operations']
        if project_type not in valid_types:
            project_type = 'operations'
            confidence = 0.0

        # Default to operations if low confidence
        if confidence < 0.6:
            project_type = 'operations'

        classification = {
            'project_type': project_type,
            'confidence': confidence,
            'reason': reason,
        }

        # Track AI usage
        try:
            track_ai_request(
                user=board.created_by,
                feature='board_classification',
                request_type='classify',
                board_id=board.id,
                ai_model='gemini',
                success=True,
                tokens_used=0,
                response_time_ms=elapsed_ms,
            )
        except Exception as e:
            logger.warning(f"Failed to track AI request for board classification: {e}")

        # Audit log
        try:
            log_audit(
                'board.classified',
                user=board.created_by,
                object_type='board',
                object_id=board.id,
                object_repr=board.name,
                board_id=board.id,
            )
        except Exception as e:
            logger.warning(f"Failed to log audit for board classification: {e}")

        return classification

    except (json.JSONDecodeError, ValueError, KeyError) as e:
        logger.error(f"Error parsing board classification response for board {board.id}: {e}")
        return None


def generate_board_analytics_narrative(board, metrics_dict):
    """
    Generate a 2-sentence narrative explaining what current board metrics
    mean for the linked Goal.

    Args:
        board: Board model instance
        metrics_dict: dict of current promoted metric values

    Returns:
        plain text string (2 sentences) or None on failure
    """
    import time
    from api.ai_usage_utils import track_ai_request
    from kanban.audit_utils import log_audit

    # Get goal context
    goal_text = ''
    target_date = ''
    try:
        if board.strategy and board.strategy.mission and board.strategy.mission.organization_goal:
            goal = board.strategy.mission.organization_goal
            goal_text = goal.name
            if goal.description:
                goal_text += f' — {goal.description}'
            if goal.target_date:
                target_date = goal.target_date.strftime('%Y-%m-%d')
    except Exception:
        pass

    project_type_label = dict(board.PROJECT_TYPE_CHOICES).get(board.project_type, board.project_type or 'Unknown')

    metrics_lines = '\n'.join(f'  {k}: {v}' for k, v in metrics_dict.items())

    prompt = (
        "You are a data analyst writing a 2-sentence executive summary for a project board.\n\n"
        f"Board: {board.name}\n"
        f"Project type: {project_type_label}\n"
        f"Goal: {goal_text or 'Not linked to a goal'}\n"
        f"Goal target date: {target_date or 'Not set'}\n"
        f"Today's date: {datetime.now().strftime('%Y-%m-%d')}\n"
        f"Current metrics:\n{metrics_lines}\n\n"
        "Write exactly 2 sentences:\n"
        "Sentence 1: describe what the metrics currently show (factual, specific to the numbers).\n"
        "Sentence 2: connect it to the Goal — what does this mean for achieving the stated objective?\n\n"
        "Rules:\n"
        "- Return plain text only. No JSON, no markdown, no bullet points.\n"
        "- Be specific to the actual metric values. Avoid generic PM jargon.\n"
        "- If no goal is linked, sentence 2 should discuss overall board health instead.\n"
    )

    start_ms = time.time()
    result = generate_ai_content(prompt, task_type='analytics_narrative', use_cache=False)
    elapsed_ms = int((time.time() - start_ms) * 1000)

    if not result:
        return None

    try:
        track_ai_request(
            user=board.created_by,
            feature='analytics_narrative',
            request_type='generate',
            board_id=board.id,
            ai_model='gemini',
            success=True,
            tokens_used=0,
            response_time_ms=elapsed_ms,
        )
    except Exception as e:
        logger.warning(f"Failed to track AI request for analytics narrative: {e}")

    try:
        log_audit(
            'board.narrative_generated',
            user=board.created_by,
            object_type='board',
            object_id=board.id,
            object_repr=board.name,
            board_id=board.id,
        )
    except Exception as e:
        logger.warning(f"Failed to log audit for analytics narrative: {e}")

    return result.strip()


def generate_portfolio_analytics_narrative(record, record_type, groups_data):
    """
    Generate a 2-sentence narrative summarising the health of all linked
    boards for a Goal, Mission, or Strategy.

    Args:
        record: OrganizationGoal, Mission, or Strategy instance
        record_type: 'goal', 'mission', or 'strategy'
        groups_data: list of dicts, each with {type, label, board_count, metrics}

    Returns:
        plain text string or None on failure
    """
    import time
    from api.ai_usage_utils import track_ai_request
    from kanban.audit_utils import log_audit

    goal_text = ''
    target_date = ''
    try:
        if record_type == 'goal':
            goal_text = record.name
            if record.description:
                goal_text += f' — {record.description}'
            if record.target_date:
                target_date = record.target_date.strftime('%Y-%m-%d')
        elif record_type == 'mission' and record.organization_goal:
            goal = record.organization_goal
            goal_text = goal.name
            if goal.target_date:
                target_date = goal.target_date.strftime('%Y-%m-%d')
        elif record_type == 'strategy' and record.mission and record.mission.organization_goal:
            goal = record.mission.organization_goal
            goal_text = goal.name
            if goal.target_date:
                target_date = goal.target_date.strftime('%Y-%m-%d')
    except Exception:
        pass

    groups_summary = ''
    for g in groups_data:
        metrics_str = ', '.join(f'{k}: {v}' for k, v in g.get('metrics', {}).items())
        groups_summary += f"  {g['label']} ({g['board_count']} boards): {metrics_str}\n"

    prompt = (
        f"You are a data analyst writing a 2-sentence portfolio summary for a {record_type}.\n\n"
        f"{record_type.title()}: {record.name}\n"
        f"Goal context: {goal_text or 'Not available'}\n"
        f"Goal target date: {target_date or 'Not set'}\n"
        f"Today's date: {datetime.now().strftime('%Y-%m-%d')}\n\n"
        f"Board groups:\n{groups_summary}\n"
        "Write exactly 2 sentences:\n"
        "Sentence 1: summarise the current state across all board groups (factual).\n"
        "Sentence 2: assess the primary risk or opportunity for achieving the Goal.\n\n"
        "Rules: plain text only, no JSON, no markdown, be specific to the numbers.\n"
    )

    start_ms = time.time()
    result = generate_ai_content(prompt, task_type='portfolio_narrative', use_cache=False)
    elapsed_ms = int((time.time() - start_ms) * 1000)

    if not result:
        return None

    try:
        track_ai_request(
            user=record.created_by,
            feature='portfolio_narrative',
            request_type='generate',
            board_id=None,
            ai_model='gemini',
            success=True,
            tokens_used=0,
            response_time_ms=elapsed_ms,
        )
    except Exception as e:
        logger.warning(f"Failed to track AI request for portfolio narrative: {e}")

    try:
        log_audit(
            f'{record_type}.portfolio_narrative_generated',
            user=record.created_by,
            object_type=record_type,
            object_id=record.id,
            object_repr=record.name,
        )
    except Exception as e:
        logger.warning(f"Failed to log audit for portfolio narrative: {e}")

    return result.strip()


def generate_proxy_metrics(goal):
    """
    Generate 3 proxy metrics (outcome indicators) for an OrganizationGoal.

    Uses the full Gemini model for deeper reasoning. Returns a list of dicts:
    [{ name, why_it_matters, how_to_measure }, ...]  or None on failure.
    """
    import time
    from api.ai_usage_utils import track_ai_request
    from kanban.audit_utils import log_audit

    goal_text = goal.name
    if goal.description:
        goal_text += f' — {goal.description}'
    target_date = goal.target_date.strftime('%Y-%m-%d') if goal.target_date else 'Not set'

    # Collect project types from linked boards
    board_types = set()
    try:
        for mission in goal.missions.all():
            for strategy in mission.strategies.all():
                for board in strategy.boards.filter(project_type__isnull=False):
                    label = dict(board.PROJECT_TYPE_CHOICES).get(board.project_type, board.project_type)
                    board_types.add(label)
    except Exception:
        pass

    # Collect existing proxy metric values for context
    existing_metrics = ''
    try:
        for pm in goal.proxy_metrics.all():
            if pm.current_value:
                existing_metrics += f'  {pm.name}: {pm.current_value}\n'
    except Exception:
        pass

    prompt = (
        "You are a strategic advisor. Suggest exactly 3 Proxy Metrics (outcome indicators) "
        "for the following organizational goal. These must be:\n"
        "- Specific to the goal's domain (not generic)\n"
        "- Measurable in the real world (not inside a project management tool)\n"
        "- Outcome indicators (not task outputs like 'tasks completed')\n\n"
        f"Goal: {goal_text}\n"
        f"Target date: {target_date}\n"
        f"Linked board types: {', '.join(board_types) if board_types else 'None classified yet'}\n"
        f"Previously tracked metrics:\n{existing_metrics if existing_metrics else '  None yet'}\n\n"
        "Respond with ONLY a JSON array — no preamble, no markdown:\n"
        '[\n'
        '  {\n'
        '    "name": "string",\n'
        '    "why_it_matters": "one sentence",\n'
        '    "how_to_measure": "one sentence"\n'
        '  }\n'
        ']\n'
    )

    start_ms = time.time()
    result = generate_ai_content(prompt, task_type='proxy_metrics', use_cache=False)
    elapsed_ms = int((time.time() - start_ms) * 1000)

    if not result:
        logger.error(f"Proxy metric generation returned None for goal {goal.id}")
        return None

    try:
        cleaned = result.strip()
        if cleaned.startswith('```'):
            cleaned = '\n'.join(cleaned.split('\n')[1:])
        if cleaned.endswith('```'):
            cleaned = cleaned[:cleaned.rfind('```')]
        metrics = json.loads(cleaned.strip())

        if not isinstance(metrics, list):
            logger.error("Proxy metric generation did not return an array")
            return None

        # Validate each metric has required fields
        validated = []
        for m in metrics[:3]:
            if all(k in m for k in ('name', 'why_it_matters', 'how_to_measure')):
                validated.append({
                    'name': str(m['name'])[:200],
                    'why_it_matters': str(m['why_it_matters']),
                    'how_to_measure': str(m['how_to_measure']),
                })

        if not validated:
            logger.error("No valid proxy metrics in Gemini response")
            return None

        try:
            track_ai_request(
                user=goal.created_by,
                feature='proxy_metrics',
                request_type='generate',
                board_id=None,
                ai_model='gemini',
                success=True,
                tokens_used=0,
                response_time_ms=elapsed_ms,
            )
        except Exception as e:
            logger.warning(f"Failed to track AI request for proxy metrics: {e}")

        try:
            log_audit(
                'goal.proxy_metrics_generated',
                user=goal.created_by,
                object_type='organizationgoal',
                object_id=goal.id,
                object_repr=goal.name,
            )
        except Exception as e:
            logger.warning(f"Failed to log audit for proxy metrics: {e}")

        return validated

    except (json.JSONDecodeError, ValueError) as e:
        logger.error(f"Error parsing proxy metrics response for goal {goal.id}: {e}")
        return None
