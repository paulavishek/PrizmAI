import os
import json
import logging
from django.conf import settings

logger = logging.getLogger(__name__)


class GeminiClient:
    """
    Google Gemini AI client - Stateless implementation
    
    IMPORTANT: Each request is completely independent with NO session persistence.
    This prevents accumulating token costs from cached history/context.
    """
    
    def __init__(self):
        try:
            import google.generativeai as genai
            self.genai = genai
            api_key = getattr(settings, 'GEMINI_API_KEY', None)
            if not api_key:
                raise ValueError("GEMINI_API_KEY not configured in settings")
            genai.configure(api_key=api_key)
            
            # Configure generation settings to disable caching and session persistence
            generation_config = {
                'temperature': 0.7,
                'top_p': 0.8,
                'top_k': 40,
                'max_output_tokens': 2048,
            }
            
            # Safety settings
            safety_settings = [
                {
                    "category": "HARM_CATEGORY_HARASSMENT",
                    "threshold": "BLOCK_MEDIUM_AND_ABOVE"
                },
                {
                    "category": "HARM_CATEGORY_HATE_SPEECH",
                    "threshold": "BLOCK_MEDIUM_AND_ABOVE"
                },
            ]
            
            # Initialize model WITHOUT chat session (stateless)
            self.model = genai.GenerativeModel(
                'gemini-2.0-flash-exp',
                generation_config=generation_config,
                safety_settings=safety_settings
            )
            logger.info("Gemini client initialized successfully (STATELESS MODE - no session persistence)")
        except ImportError:
            logger.error("google-generativeai package not installed")
            self.model = None
        except Exception as e:
            logger.error(f"Error initializing Gemini client: {e}")
            self.model = None
    
    def get_response(self, prompt, system_prompt=None, history=None):
        """
        Get response from Gemini model using STATELESS generation.
        
        IMPORTANT: This method does NOT use chat sessions or maintain conversation history
        to prevent accumulating token costs. Each call is completely independent.
        
        Args:
            prompt (str): User prompt
            system_prompt (str): System context (combined with prompt for this call only)
            history (list): DEPRECATED - Not used to prevent session persistence
            
        Returns:
            dict: Response with content and token info
        """
        if not self.model:
            return {
                'content': 'Gemini service is unavailable',
                'error': 'Model not initialized',
                'tokens': 0
            }
        
        try:
            # Build a fresh, one-time prompt with NO persistent history
            full_prompt = prompt
            if system_prompt:
                full_prompt = f"{system_prompt}\n\n{prompt}"
            
            # NOTE: history parameter is intentionally ignored to prevent session persistence
            # Each generate_content() call is completely independent and stateless
            if history:
                logger.warning("History parameter provided but ignored - using stateless mode to prevent token accumulation")
            
            # Generate content WITHOUT using chat sessions
            # This ensures each request is independent with no cached history
            response = self.model.generate_content(
                full_prompt,
                # No history, no caching, completely fresh request
            )
            
            # Calculate approximate token usage
            # Note: This is approximate. Use response.usage_metadata if available for accurate counts
            token_count = 0
            if hasattr(response, 'usage_metadata') and response.usage_metadata:
                token_count = (
                    getattr(response.usage_metadata, 'prompt_token_count', 0) +
                    getattr(response.usage_metadata, 'candidates_token_count', 0)
                )
            else:
                # Fallback: rough approximation
                token_count = len(full_prompt.split()) + len(response.text.split())
            
            logger.info(f"Gemini response generated - Tokens used: {token_count} (stateless mode)")
            
            return {
                'content': response.text,
                'error': None,
                'tokens': token_count,
                'session_mode': 'stateless',  # Explicitly indicate no session persistence
            }
        
        except Exception as e:
            logger.error(f"Error getting Gemini response: {e}")
            return {
                'content': f"Error: {str(e)}",
                'error': str(e),
                'tokens': 0,
                'session_mode': 'error',
            }
