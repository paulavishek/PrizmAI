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
    'column_recommendations'
]

SIMPLE_TASKS = [
    'task_description',
    'comment_summary',
    'lean_classification',
    'task_enhancement',
    'mitigation_suggestions'
]

# Temperature settings for different AI task types
# Lower = more deterministic/consistent, Higher = more creative/varied
TASK_TEMPERATURE_MAP = {
    # Deterministic tasks (0.2-0.3) - Need consistent, predictable outputs
    'column_recommendations': 0.3,      # Same project should get similar column structure
    'board_setup': 0.2,                  # Phase count, team size should be consistent
    'task_breakdown': 0.3,               # Subtask structure should be predictable
    'resource_optimization': 0.3,        # Workload calculations need consistency
    
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
    
    # Defaults
    'simple': 0.6,                       # Default for simple tasks
    'complex': 0.4,                      # Default for complex tasks
}

# Token limits for different AI task types
# Lower limits = faster responses, Higher limits = more detailed outputs
# Optimized for latency while maintaining quality - increased to prevent JSON truncation
TASK_TOKEN_LIMITS = {
    # Short responses (1536-2048 tokens) - increased to prevent truncation of explainability fields
    'lean_classification': 2048,          # Classification + detailed explanation + confidence + alternatives
    'comment_summary': 2560,              # Summary with sentiment analysis, action items, and participant analysis
    'mitigation_suggestions': 2048,       # Mitigation strategies with action steps
    
    # Medium responses (2048-3072 tokens)
    'task_description': 1536,            # Concise description + simple checklist (simplified prompt)
    'priority_suggestion': 3072,         # Priority with full comparison and recommendations
    'dashboard_insights': 2048,          # Quick insights with reasoning
    'velocity_forecast': 2048,           # Forecast data with explanations
    'simple': 2048,                      # Default for simple tasks - increased for explainability
    
    # Standard responses (3072-4096 tokens)
    'task_enhancement': 3072,            # Enhanced description + checklist + acceptance criteria + reasoning
    'board_analytics_summary': 3072,     # Comprehensive analytics with health factors
    'risk_assessment': 3072,             # Risk analysis with mitigation and explainability
    'retrospective': 3072,               # Retrospective summary with patterns and recommendations
    'skill_gap_analysis': 3072,          # Skill analysis with recommendations
    'budget_analysis': 4096,             # Budget insights with trends and recommendations
    'dependency_analysis': 3072,         # Dependency and cascading risk analysis
    'deadline_prediction': 1536,         # Simplified timeline prediction (reduced from complex explainability)
    
    # Extended responses (4096-6144 tokens) - complex nested JSON structures
    'workflow_optimization': 4096,       # Workflow analysis with bottlenecks and recommendations
    'task_breakdown': 2048,              # Simplified subtask list (reduced from verbose explainability)
    'critical_path': 6144,               # Critical path with task analysis and scheduling
    'complex': 6144,                     # General complex analysis tasks - increased for comprehensive JSON
    'timeline_generation': 4096,         # Timeline details with milestones
    
    # Large responses (6144-8192 tokens) - extensive board-wide analysis
    'column_recommendations': 6144,      # Complex structure with full explainability (4-7 columns)
    'board_setup': 4096,                 # Full board configuration with explainability
    'task_summary': 8192,                # Comprehensive task summary with all aspects analyzed - needs high limit
    
    # Default
    'default': 3072,                     # Default for unspecified tasks - increased to prevent truncation
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
        
        # Generate content with optimized settings
        response = model.generate_content(prompt, generation_config=generation_config)
        
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
            context_info = f"Project: {context.get('board_name', 'General')}"
        
        prompt = f"""Generate a task description for: "{title}"
{context_info}

RULES:
- DO NOT include time estimates, effort predictions, or deadlines
- DO NOT suggest priority levels
- Keep each section brief and actionable

Return JSON only:
{{
    "objective": "1-2 sentence goal",
    "key_deliverables": ["Deliverable 1", "Deliverable 2", "Deliverable 3"],
    "action_steps": ["Step 1", "Step 2", "Step 3", "Step 4"],
    "potential_obstacles": ["Risk/obstacle 1", "Risk/obstacle 2"],
    "success_criteria": "How to know this task is complete"
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
                
                result['markdown_description'] = "\n".join(md_parts)
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

def suggest_lean_classification(title: str, description: str, estimated_cost: float = None, estimated_hours: float = None, hourly_rate: float = None) -> Optional[Dict]:
    """
    Suggest Lean Six Sigma classification for a task based on its title, description, and budget data.
    
    Provides explainable AI output including confidence scores, contributing factors,
    and alternative classifications to support user decision-making.
    
    Args:
        title: The task title
        description: The task description
        estimated_cost: Estimated cost for this task (optional)
        estimated_hours: Estimated hours to complete (optional)
        hourly_rate: Hourly rate for labor cost calculation (optional)
        
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
                budget_context = "\n\nBudget & Cost Information:\n- " + "\n- ".join(budget_parts)
        
        prompt = f"""Analyze this task for Lean Six Sigma classification. Task: "{title}". Description: "{description or 'None'}".{budget_context}

Classifications: Value-Added (transforms product/service for customer), Necessary Non-Value-Added (required but not customer-valued), Waste/Eliminate (no value, should remove).

Return ONLY valid JSON with NO line breaks inside strings:
{{"classification":"Value-Added|Necessary Non-Value-Added|Waste/Eliminate","justification":"Brief reason in one sentence","confidence_score":0.XX,"confidence_level":"high|medium|low","contributing_factors":[{{"factor":"Factor1","contribution_percentage":XX,"description":"Brief desc"}}],"classification_reasoning":{{"value_added_indicators":["indicator1"],"non_value_indicators":["indicator1"],"primary_driver":"Main reason"}},"alternative_classification":{{"classification":"Alternative","confidence_score":0.XX,"conditions":"When applies"}},"assumptions":["assumption1"],"improvement_suggestions":["suggestion1"],"lean_waste_type":null}}"""
        
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
        - Due Date: {due_date or 'No due date set'}{budget_info if budget_info else ''}
        
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
        Complexity: {complexity_score}/10 | Current workload: {current_workload} active tasks
        {estimated_hours_note}
        {start_date_note}
        
        DATA AVAILABILITY: {history_note}
        
        IMPORTANT RULES:
        - Predict number of WORKING DAYS needed to complete this task (not calendar date)
        - Be HONEST about data availability in your reasoning
        - If no historical data exists, say "estimated based on task complexity" NOT "based on historical averages"
        - Keep response concise. Return JSON only:
        
        {{
            "estimated_days_to_complete": number,
            "confidence_level": "high|medium|low",
            "reasoning": "One honest sentence explaining basis for timeline (mention if no history available)",
            "risk_factors": ["2-3 brief risks"],
            "optimistic_days": number,
            "pessimistic_days": number
        }}
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
                ai_response['risk_factors'] = ["AI response parsing had issues", "Timeline based on complexity estimate"]
                
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
        Analyze this task and suggest a breakdown into smaller subtasks.
        
        Task: {title}
        Description: {description or 'No description'}
        Priority: {priority}
        Due: {due_date or 'Not set'}
        
        IMPORTANT: Keep response concise. Maximum 4-6 subtasks with brief descriptions.
        
        Return JSON only:
        {{
            "is_breakdown_recommended": true|false,
            "complexity_score": 1-10,
            "reasoning": "One sentence explaining recommendation",
            "subtasks": [
                {{
                    "title": "Short subtask title",
                    "description": "One sentence describing what to do",
                    "estimated_effort": "1-2 days",
                    "priority": "low|medium|high",
                    "order": 1
                }}
            ],
            "total_estimated_effort": "Total time estimate"
        }}
        """
        
        response_text = generate_ai_content(prompt, task_type='task_breakdown')
        if response_text:
            # Handle code block formatting
            if "```json" in response_text:
                response_text = response_text.split("```json")[1].split("```")[0].strip()
            elif "```" in response_text:
                response_text = response_text.split("```")[1].strip()
            
            # Clean up common JSON issues from AI responses
            response_text = response_text.replace('True', 'true').replace('False', 'false')
            response_text = response_text.replace('None', 'null')
            response_text = re.sub(r',\s*([}\]])', r'\1', response_text)  # Remove trailing commas
            
            try:
                return json.loads(response_text)
            except json.JSONDecodeError as json_err:
                logger.error(f"Task breakdown JSON parse error: {json_err}. Response text (first 500 chars): {response_text[:500]}")
                # Try a more aggressive cleanup
                response_text = re.sub(r'[\x00-\x1f\x7f-\x9f]', '', response_text)  # Remove control characters
                
                try:
                    return json.loads(response_text)
                except json.JSONDecodeError as second_err:
                    logger.error(f"Second JSON parse attempt failed: {second_err}")
                    # Try to repair truncated JSON
                    try:
                        cleaned = response_text.rstrip()
                        if not cleaned.endswith('}'):
                            # Find the last properly closed object
                            depth = 0
                            last_valid_pos = -1
                            for i, char in enumerate(cleaned):
                                if char == '{':
                                    depth += 1
                                elif char == '}':
                                    depth -= 1
                                    if depth == 0:
                                        last_valid_pos = i
                            
                            if last_valid_pos > 0:
                                cleaned = cleaned[:last_valid_pos + 1]
                                logger.info("Successfully repaired truncated JSON for task breakdown")
                                return json.loads(cleaned)
                            else:
                                raise json.JSONDecodeError("Could not repair JSON", response_text, 0)
                        else:
                            raise second_err
                    except Exception as repair_err:
                        logger.error(f"Failed to repair JSON: {repair_err}")
                        # Return a minimal valid response indicating failure
                        return {
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
                        }
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

