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
            
            # Task-specific token limits - generous limits to ensure complete responses
            self.task_token_limits = {
                'simple': 4096,  # Generous for explainability JSON fields
                'complex': 8192,  # Complex tasks need more tokens for detailed JSON
                'retrospective': 8192,  # Retrospectives generate comprehensive reports with evidence
                'chat_response': 6144,  # Chat responses with full context and explanations
                'analysis': 8192,  # Analysis reports with recommendations + explainability
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

    # ------------------------------------------------------------------
    # Tier 1: Intent classification via Flash-Lite
    # ------------------------------------------------------------------

    def classify_intent(self, message, system_prompt=None):
        """
        Use Flash-Lite to classify user intent quickly and cheaply.

        Returns dict with 'intent' (str) and 'confidence' (float),
        or None if the call fails (caller should fall back to regex).
        """
        model = self.get_model(task_complexity='simple')  # Flash-Lite
        if not model:
            return None

        default_system = (
            "You are an intent classifier for a project management AI assistant called Spectra.\n"
            "Classify the user's message into exactly ONE intent.\n"
            "Respond with JSON only: {\"intent\": \"<intent>\", \"confidence\": <0.0-1.0>}\n\n"
            "Intents:\n"
            "- \"conversation\" — questions, chat, analysis, help, greetings, anything that is NOT an action request\n"
            "- \"create_task\" — wants to create or add a task\n"
            "- \"create_board\" — wants to create a new project board\n"
            "- \"activate_automation\" — wants to pick from predefined automation templates (generic 'set up automation')\n"
            "- \"create_automation\" — wants to create a custom automation with specific trigger/action (e.g. 'when a task is marked done, notify the creator')\n"
            "- \"create_scheduled_automation\" — wants a time-based recurring automation (e.g. 'every day at 9 AM', 'daily', 'weekly')\n"
            "- \"send_message\" — wants to send a message or DM to a team member\n"
            "- \"log_time\" — wants to log time or hours worked on a task\n"
            "- \"schedule_event\" — wants to schedule a meeting, event, or calendar entry\n"
            "- \"create_retrospective\" — wants to generate or create a retrospective\n"
            "- \"confirm_action\" — saying yes, confirm, go ahead, looks good (affirming a pending action)\n"
            "- \"cancel_action\" — saying no, cancel, stop, nevermind (cancelling a pending action)\n"
        )
        prompt = f"{system_prompt or default_system}\n\nUser message: {message}"

        try:
            generation_config = {
                'temperature': 0.1,
                'top_p': 0.8,
                'top_k': 40,
                'max_output_tokens': 100,
            }
            response = model.generate_content(prompt, generation_config=generation_config)

            if not response.candidates or not response.candidates[0].content.parts:
                return None

            text = response.text.strip()
            # Extract JSON from response (handle markdown code blocks)
            if '```' in text:
                text = text.split('```')[1]
                if text.startswith('json'):
                    text = text[4:]
                text = text.strip()

            result = json.loads(text)
            intent = result.get('intent', 'conversation')
            confidence = float(result.get('confidence', 0.5))

            valid_intents = {
                'conversation', 'create_task', 'create_board',
                'activate_automation', 'create_automation', 'create_scheduled_automation',
                'send_message', 'log_time', 'schedule_event', 'create_retrospective',
                'confirm_action', 'cancel_action',
            }
            if intent not in valid_intents:
                intent = 'conversation'

            logger.info(f"Intent classified: {intent} (confidence: {confidence:.2f}) for: {message[:80]}")
            return {'intent': intent, 'confidence': confidence}

        except (json.JSONDecodeError, ValueError, KeyError) as e:
            logger.warning(f"Intent classification parse error: {e}")
            return None
        except Exception as e:
            logger.error(f"Intent classification failed: {e}")
            return None

    # ------------------------------------------------------------------
    # Tier 2: Function Calling via Flash
    # ------------------------------------------------------------------

    def get_function_call_response(self, message, system_prompt, tools,
                                   conversation_history=None, temperature=0.2):
        """
        Use Gemini Flash with native Function Calling to extract structured
        parameters from user messages.

        Args:
            message: Current user message
            system_prompt: Context (user, board, members, columns, etc.)
            tools: list of genai.types.Tool objects with FunctionDeclarations
            conversation_history: Optional prior turns in this action flow
            temperature: Low for deterministic extraction (default 0.2)

        Returns:
            dict with either:
              - 'function_call': {'name': str, 'args': dict}  (all params ready)
              - 'text': str  (model asking follow-up for missing params)
              - 'error': str  (on failure)
            Plus 'tokens' and 'model_used' metadata.
        """
        if self.models is None:
            return {'error': 'Model not initialized', 'tokens': 0, 'model_used': 'none'}

        try:
            from google.generativeai.types import content_types
            import google.generativeai as genai

            # Always use Flash for function calling (needs capable model)
            model_name = 'gemini-2.5-flash'

            # Create a model instance with tools (separate from cached plain models)
            fc_model = genai.GenerativeModel(
                model_name,
                generation_config={
                    'temperature': temperature,
                    'top_p': 0.8,
                    'top_k': 40,
                    'max_output_tokens': 2048,
                },
                safety_settings=self.safety_settings,
                tools=tools,
            )

            # Build the prompt with conversation history
            parts = []
            if system_prompt:
                parts.append(f"{system_prompt}\n\n")
            if conversation_history:
                parts.append("Previous conversation in this flow:\n")
                for turn in conversation_history:
                    parts.append(f"{turn}\n")
                parts.append("\n")
            parts.append(f"User: {message}")

            full_prompt = ''.join(parts)

            response = fc_model.generate_content(full_prompt)

            # Calculate tokens
            token_count = 0
            if hasattr(response, 'usage_metadata') and response.usage_metadata:
                token_count = (
                    getattr(response.usage_metadata, 'prompt_token_count', 0) +
                    getattr(response.usage_metadata, 'candidates_token_count', 0)
                )

            # Check if the model returned a function call
            if (response.candidates and response.candidates[0].content.parts):
                for part in response.candidates[0].content.parts:
                    if hasattr(part, 'function_call') and part.function_call.name:
                        fc = part.function_call
                        # Convert proto args to dict
                        args = dict(fc.args) if fc.args else {}
                        logger.info(
                            f"Function call extracted: {fc.name}({args}) "
                            f"[tokens: {token_count}]"
                        )
                        return {
                            'function_call': {'name': fc.name, 'args': args},
                            'tokens': token_count,
                            'model_used': model_name,
                        }

                # Model returned text instead of function call — it's asking follow-up
                text = response.text if hasattr(response, 'text') else ''
                logger.info(f"FC model returned text (follow-up): {text[:100]}...")
                return {
                    'text': text,
                    'tokens': token_count,
                    'model_used': model_name,
                }

            return {
                'text': "I need a bit more information to proceed. Could you provide more details?",
                'tokens': token_count,
                'model_used': model_name,
            }

        except Exception as e:
            logger.error(f"Function calling failed: {e}")
            return {
                'error': str(e),
                'tokens': 0,
                'model_used': 'none',
            }
