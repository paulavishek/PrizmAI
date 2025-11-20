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
            
            # Configure generation settings to disable caching and session persistence
            self.generation_config = {
                'temperature': 0.7,
                'top_p': 0.8,
                'top_k': 40,
                'max_output_tokens': 2048,
            }
            
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
    
    def get_response(self, prompt, system_prompt=None, history=None, task_complexity='simple'):
        """
        Get response from Gemini model using stateless generation with smart routing.
        
        Routes to appropriate model:
        - 'complex': Uses Gemini 2.5 Flash for complex reasoning
        - 'simple': Uses Gemini 2.5 Flash-Lite for fast, cost-effective responses
        
        Args:
            prompt (str): User prompt
            system_prompt (str): System context (combined with prompt for this call only)
            history (list): DEPRECATED - Not used to prevent session persistence
            task_complexity (str): 'simple' or 'complex' for model routing
            
        Returns:
            dict: Response with content, token info, and model used
        """
        model = self.get_model(task_complexity=task_complexity)
        if not model:
            return {
                'content': 'Gemini service is unavailable',
                'error': 'Model not initialized',
                'tokens': 0,
                'model_used': 'none'
            }
        
        try:
            # Build a fresh, one-time prompt with NO persistent history
            full_prompt = prompt
            if system_prompt:
                full_prompt = f"{system_prompt}\n\n{prompt}"
            
            # NOTE: history parameter is intentionally ignored to prevent session persistence
            if history:
                logger.warning("History parameter provided but ignored - using stateless mode to prevent token accumulation")
            
            # Determine which model we're using for logging
            model_name = 'gemini-2.5-flash' if task_complexity == 'complex' else 'gemini-2.5-flash-lite'
            
            # Generate content WITHOUT using chat sessions
            response = model.generate_content(full_prompt)
            
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
            
            logger.info(f"Gemini response generated - Model: {model_name}, Tokens: {token_count}, Complexity: {task_complexity}")
            
            return {
                'content': response.text,
                'error': None,
                'tokens': token_count,
                'session_mode': 'stateless',
                'model_used': model_name,
                'task_complexity': task_complexity
            }
        
        except Exception as e:
            logger.error(f"Error getting Gemini response: {e}")
            return {
                'content': f"Error: {str(e)}",
                'error': str(e),
                'tokens': 0,
                'session_mode': 'error',
                'model_used': 'none'
            }
