import os
import json
import logging
from django.conf import settings

logger = logging.getLogger(__name__)


class GeminiClient:
    """
    Google Gemini AI client with smart model routing
    
    Routes requests to appropriate model based on task complexity:
    - Gemini 2.5 Flash: Complex reasoning, analysis
    - Gemini 2.5 Flash-Lite: Simple tasks, chat responses (default)
    
    Each request is stateless to prevent token accumulation.
    """
    
    def __init__(self, default_model='gemini-2.5-flash-lite'):
        """
        Initialize Gemini client with configurable default model.
        
        Args:
            default_model: Default model to use ('gemini-2.5-flash' or 'gemini-2.5-flash-lite')
        """
        try:
            import google.generativeai as genai
            self.genai = genai
            api_key = getattr(settings, 'GEMINI_API_KEY', None)
            if not api_key:
                raise ValueError("GEMINI_API_KEY not configured in settings")
            genai.configure(api_key=api_key)
            
            # Base generation config - temperature can be overridden per request
            # Default 0.7 for general use, but specific features use optimized values
            # max_output_tokens increased to prevent JSON truncation for complex responses
            self.base_generation_config = {
                'temperature': 0.7,  # Default - will be overridden per task type
                'top_p': 0.8,
                'top_k': 40,
                'max_output_tokens': 6144,  # Increased from 3072 for comprehensive JSON responses
            }
            
            # Task-specific token limits - use higher limits for complex analysis
            self.task_token_limits = {
                'simple': 3072,  # Increased for explainability JSON fields
                'complex': 8192,  # Complex tasks need more tokens for detailed JSON
                'retrospective': 6144,  # Retrospectives generate comprehensive reports
                'chat_response': 3072,  # Chat responses with context
                'analysis': 6144,  # Analysis reports with recommendations
            }
            
            # For backward compatibility
            self.generation_config = self.base_generation_config
            
            # Safety settings - permissive for business/technical content
            self.safety_settings = [
                {
                    "category": "HARM_CATEGORY_HARASSMENT",
                    "threshold": "BLOCK_ONLY_HIGH"
                },
                {
                    "category": "HARM_CATEGORY_HATE_SPEECH",
                    "threshold": "BLOCK_ONLY_HIGH"
                },
                {
                    "category": "HARM_CATEGORY_SEXUALLY_EXPLICIT",
                    "threshold": "BLOCK_ONLY_HIGH"
                },
                {
                    "category": "HARM_CATEGORY_DANGEROUS_CONTENT",
                    "threshold": "BLOCK_ONLY_HIGH"
                },
            ]
            
            # Store models for reuse (singleton pattern per model type)
            self.models = {}
            self.default_model = default_model
            
            logger.info(f"Gemini client initialized with smart routing (default: {default_model})")
        except ImportError:
            logger.error("google-generativeai package not installed")
            self.models = None
        except Exception as e:
            logger.error(f"Error initializing Gemini client: {e}")
            self.models = None
    
    def get_model(self, model_name=None, task_complexity='simple'):
        """
        Get or create a model instance with smart routing.
        
        Args:
            model_name: Specific model name or None to use routing
            task_complexity: 'simple' or 'complex' for automatic routing
            
        Returns:
            GenerativeModel instance
        """
        if self.models is None:
            return None
            
        # Determine which model to use
        if model_name is None:
            # Smart routing based on task complexity
            model_name = 'gemini-2.5-flash' if task_complexity == 'complex' else 'gemini-2.5-flash-lite'
        
        # Reuse existing model instance (singleton per model type)
        if model_name not in self.models:
            self.models[model_name] = self.genai.GenerativeModel(
                model_name,
                generation_config=self.generation_config,
                safety_settings=self.safety_settings
            )
            logger.info(f"Created model instance: {model_name}")
        
        return self.models[model_name]
    
    def _get_ai_cache(self):
        """Get the AI cache manager."""
        try:
            from kanban_board.ai_cache import ai_cache_manager
            return ai_cache_manager
        except ImportError:
            return None
    
    def get_response(self, prompt, system_prompt=None, history=None, task_complexity='simple', 
                     temperature=None, use_cache=False, cache_operation='chat_response', 
                     context_id=None):
        """
        Get response from Gemini model using stateless generation with smart routing.
        
        Routes to appropriate model:
        - 'complex': Uses Gemini 2.5 Flash for complex reasoning
        - 'simple': Uses Gemini 2.5 Flash-Lite for fast, cost-effective responses
        
        Temperature Guidelines:
        - 0.2-0.3: Deterministic (column recommendations, board setup, structured outputs)
        - 0.4: Analytical (risk assessment, skill gap, budget analysis, performance reports)
        - 0.5: Balanced (dashboard insights, help queries)
        - 0.6: Creative content (task descriptions, retrospectives)
        - 0.7: Conversational (chat, general assistance)
        
        Args:
            prompt (str): User prompt
            system_prompt (str): System context (combined with prompt for this call only)
            history (list): DEPRECATED - Not used to prevent session persistence
            task_complexity (str): 'simple' or 'complex' for model routing
            temperature (float): Override temperature for this request (0.0-1.0)
            use_cache (bool): Whether to cache this response (default False for chat)
            cache_operation (str): Operation type for TTL selection
            context_id (str): Optional context identifier for caching
            
        Returns:
            dict: Response with content, token info, model used, and temperature used
        """
        # Build prompt for caching
        full_prompt = prompt
        if system_prompt:
            full_prompt = f"{system_prompt}\n\n{prompt}"
        
        # Try cache first if enabled
        ai_cache = self._get_ai_cache()
        if use_cache and ai_cache:
            cached = ai_cache.get(full_prompt, cache_operation, context_id)
            if cached and isinstance(cached, dict):
                logger.debug(f"GeminiClient cache HIT for operation: {cache_operation}")
                cached['from_cache'] = True
                return cached
        
        model = self.get_model(task_complexity=task_complexity)
        if not model:
            return {
                'content': 'Gemini service is unavailable',
                'error': 'Model not initialized',
                'tokens': 0,
                'model_used': 'none'
            }
        
        try:            
            # NOTE: history parameter is intentionally ignored to prevent session persistence
            if history:
                logger.warning("History parameter provided but ignored - using stateless mode to prevent token accumulation")
            
            # Determine which model we're using for logging
            model_name = 'gemini-2.5-flash' if task_complexity == 'complex' else 'gemini-2.5-flash-lite'
            
            # Get token limit based on task complexity and operation type
            token_limit = self.task_token_limits.get(
                cache_operation, 
                self.task_token_limits.get(task_complexity, 3072)
            )
            
            # Build generation config with temperature override and task-specific token limit
            temp_used = self.base_generation_config.get('temperature', 0.7)
            generation_config = {
                **self.base_generation_config,
                'max_output_tokens': token_limit,
            }
            
            if temperature is not None:
                generation_config['temperature'] = temperature
                temp_used = temperature
                logger.debug(f"Using custom temperature: {temperature}")
            
            logger.debug(f"GeminiClient using max_output_tokens: {token_limit} for operation: {cache_operation}")
            
            # Generate content WITHOUT using chat sessions
            response = model.generate_content(full_prompt, generation_config=generation_config)
            
            # Check if response was blocked by safety filters
            if not response.candidates or not response.candidates[0].content.parts:
                finish_reason = response.candidates[0].finish_reason if response.candidates else None
                error_msg = f"Response blocked by Gemini safety filters (finish_reason: {finish_reason})"
                logger.warning(error_msg)
                return {
                    'content': 'The AI response was blocked by safety filters. Please try with different data or time period.',
                    'error': error_msg,
                    'tokens': 0,
                    'session_mode': 'blocked',
                    'model_used': model_name,
                    'task_complexity': task_complexity
                }
            
            # Calculate token usage
            token_count = 0
            if hasattr(response, 'usage_metadata') and response.usage_metadata:
                token_count = (
                    getattr(response.usage_metadata, 'prompt_token_count', 0) +
                    getattr(response.usage_metadata, 'candidates_token_count', 0)
                )
            else:
                # Fallback: rough approximation
                token_count = len(full_prompt.split()) + len(response.text.split())
            
            logger.info(f"Gemini response generated - Model: {model_name}, Tokens: {token_count}, Complexity: {task_complexity}, Temp: {temp_used}")
            
            result = {
                'content': response.text,
                'error': None,
                'tokens': token_count,
                'session_mode': 'stateless',
                'model_used': model_name,
                'task_complexity': task_complexity,
                'temperature_used': temp_used,
                'from_cache': False
            }
            
            # Cache the result if caching is enabled
            if use_cache and ai_cache and not result.get('error'):
                ai_cache.set(full_prompt, result, cache_operation, context_id)
                logger.debug(f"GeminiClient response cached for operation: {cache_operation}")
            
            return result
        
        except Exception as e:
            logger.error(f"Error getting Gemini response: {e}")
            return {
                'content': f"Error: {str(e)}",
                'error': str(e),
                'tokens': 0,
                'session_mode': 'error',
                'model_used': 'none'
            }
