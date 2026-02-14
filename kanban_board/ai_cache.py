"""
AI Response Caching System for PrizmAI

Provides intelligent caching for AI API calls to reduce costs and improve performance.

Features:
- Content-based caching (hashes prompts to avoid duplicate API calls)
- Tiered TTL by operation type
- Statistics tracking for cache efficiency
- Graceful fallback when cache unavailable
- Easy-to-use decorators for any AI function

Usage:
    from kanban_board.ai_cache import cache_ai_call, ai_cache_manager
    
    # As a decorator
    @cache_ai_call(operation='budget_analysis', ttl=3600)
    def analyze_budget(board_id):
        return call_gemini_api(...)
    
    # Manual caching
    result = ai_cache_manager.get_or_call(
        prompt='...',
        call_func=lambda: model.generate_content(prompt),
        operation='risk_assessment',
        context_hash='board_123'
    )
"""

import hashlib
import functools
import json
import logging
import time
from typing import Any, Callable, Dict, Optional, Union
from datetime import datetime

from django.core.cache import caches
from django.conf import settings

logger = logging.getLogger(__name__)


# =============================================================================
# TTL CONFIGURATION BY OPERATION TYPE
# =============================================================================

AI_CACHE_TTLS = {
    # Long-lived caches (1-6 hours) - Results that don't change frequently
    'budget_analysis': 3600,          # 1 hour - Budget data changes infrequently
    'skill_analysis': 7200,           # 2 hours - Skills don't change often
    'skill_gap': 7200,                # 2 hours
    'team_capacity': 3600,            # 1 hour
    'pm_performance': 7200,           # 2 hours - Performance analysis
    'learning_content': 21600,        # 6 hours - Educational content is stable
    'scope_analysis': 3600,           # 1 hour
    
    # Medium caches (15-60 minutes) - Results that need periodic refresh
    'risk_assessment': 1800,          # 30 minutes
    'priority_suggestion': 1800,      # 30 minutes
    'workflow_optimization': 1800,    # 30 minutes
    'column_recommendations': 3600,   # 1 hour
    'board_setup': 3600,              # 1 hour
    'retrospective': 1800,            # 30 minutes
    'conflict_suggestion': 1800,      # 30 minutes
    'task_enhancement': 900,          # 15 minutes
    'coaching_suggestion': 1800,      # 30 minutes
    'coaching_advice': 1800,          # 30 minutes
    
    # Short caches (5-15 minutes) - More dynamic results
    'task_description': 900,          # 15 minutes
    'comment_summary': 600,           # 10 minutes
    'chat_response': 300,             # 5 minutes - Conversations should feel fresh
    'transcript_analysis': 1800,      # 30 minutes - Meeting transcripts
    'task_extraction': 1800,          # 30 minutes
    
    # Very short (1-5 minutes) - Near real-time data
    'dashboard_insights': 300,        # 5 minutes
    'velocity_forecast': 300,         # 5 minutes
    
    # Default
    'default': 1800,                  # 30 minutes
}

# Apply settings overrides if configured
if hasattr(settings, 'AI_CACHE_TTL_OVERRIDES') and settings.AI_CACHE_TTL_OVERRIDES:
    AI_CACHE_TTLS.update(settings.AI_CACHE_TTL_OVERRIDES)
    logger.info(f"AI cache TTLs updated with {len(settings.AI_CACHE_TTL_OVERRIDES)} overrides from settings")


def get_ttl_for_operation(operation: str) -> int:
    """Get the appropriate TTL for an operation type."""
    return AI_CACHE_TTLS.get(operation, AI_CACHE_TTLS['default'])


# =============================================================================
# AI CACHE MANAGER CLASS
# =============================================================================

class AICacheManager:
    """
    Intelligent cache manager for AI API responses.
    
    Uses content-based hashing to deduplicate similar prompts and
    provides tiered caching based on operation type.
    
    Can be disabled via AI_CACHE_ENABLED setting or environment variable.
    """
    
    # Default cache backend
    CACHE_NAME = 'ai_cache'
    FALLBACK_CACHE = 'default'
    
    # Key prefix for all AI cache entries
    KEY_PREFIX = 'prizmAI:ai_response'
    
    def __init__(self):
        self._stats = {
            'hits': 0,
            'misses': 0,
            'errors': 0,
            'api_calls_saved': 0,
            'estimated_cost_saved': 0.0,  # Estimated based on avg Gemini pricing
            'cache_bypassed': 0,  # Count of requests when cache is disabled
        }
        self._last_reset = datetime.now()
    
    def is_enabled(self) -> bool:
        """Check if AI caching is enabled via settings."""
        return getattr(settings, 'AI_CACHE_ENABLED', True)
    
    def _get_cache(self):
        """Get the cache backend with fallback."""
        try:
            return caches[self.CACHE_NAME]
        except Exception:
            try:
                return caches[self.FALLBACK_CACHE]
            except Exception as e:
                logger.error(f"Failed to get cache backend: {e}")
                return None
    
    def _generate_cache_key(self, prompt: str, operation: str, 
                           context_hash: Optional[str] = None) -> str:
        """
        Generate a unique cache key based on content.
        
        Uses MD5 hash of prompt + context to create deterministic keys.
        Same prompt + context will always produce the same key.
        """
        # Normalize prompt (strip whitespace, lowercase for consistency)
        normalized_prompt = prompt.strip().lower()
        
        # Create content string for hashing
        content = f"{operation}:{normalized_prompt}"
        if context_hash:
            content = f"{content}:{context_hash}"
        
        # Generate hash
        content_hash = hashlib.md5(content.encode('utf-8')).hexdigest()
        
        return f"{self.KEY_PREFIX}:{operation}:{content_hash}"
    
    def get(self, prompt: str, operation: str = 'default',
            context_hash: Optional[str] = None) -> Optional[Any]:
        """
        Try to get a cached AI response.
        
        Args:
            prompt: The AI prompt
            operation: Type of operation (for TTL selection)
            context_hash: Optional additional context identifier
            
        Returns:
            Cached response or None if not found/disabled
        """
        # Skip cache if disabled
        if not self.is_enabled():
            self._stats['cache_bypassed'] += 1
            logger.debug("AI cache disabled - bypassing cache lookup")
            return None
        
        cache = self._get_cache()
        if cache is None:
            return None
        
        cache_key = self._generate_cache_key(prompt, operation, context_hash)
        
        try:
            result = cache.get(cache_key)
            if result is not None:
                self._stats['hits'] += 1
                self._stats['api_calls_saved'] += 1
                # Estimated savings based on ~$0.0002 per 1K tokens (Gemini Flash)
                self._stats['estimated_cost_saved'] += 0.0005
                logger.debug(f"AI cache HIT for operation: {operation}")
                return result
            else:
                self._stats['misses'] += 1
                return None
        except Exception as e:
            self._stats['errors'] += 1
            logger.warning(f"AI cache get error: {e}")
            return None
    
    def set(self, prompt: str, result: Any, operation: str = 'default',
            context_hash: Optional[str] = None, ttl: Optional[int] = None) -> bool:
        """
        Cache an AI response.
        
        Args:
            prompt: The AI prompt
            result: The AI response to cache
            operation: Type of operation (for TTL selection)
            context_hash: Optional additional context identifier
            ttl: Optional override for TTL
            
        Returns:
            True if cached successfully, False if disabled or failed
        """
        # Skip cache if disabled
        if not self.is_enabled():
            logger.debug("AI cache disabled - skipping cache storage")
            return False
        
        cache = self._get_cache()
        if cache is None:
            return False
        
        if result is None:
            return False
        
        cache_key = self._generate_cache_key(prompt, operation, context_hash)
        timeout = ttl or get_ttl_for_operation(operation)
        
        try:
            cache.set(cache_key, result, timeout)
            logger.debug(f"AI response cached for operation: {operation}, TTL: {timeout}s")
            return True
        except Exception as e:
            self._stats['errors'] += 1
            logger.warning(f"AI cache set error: {e}")
            return False
    
    def get_or_call(self, prompt: str, call_func: Callable, 
                    operation: str = 'default',
                    context_hash: Optional[str] = None,
                    ttl: Optional[int] = None) -> Any:
        """
        Get from cache or call the function and cache the result.
        
        This is the primary method for wrapping AI calls.
        
        Args:
            prompt: The AI prompt
            call_func: Function to call if cache miss (should return the AI response)
            operation: Type of operation
            context_hash: Optional context identifier
            ttl: Optional TTL override
            
        Returns:
            AI response (from cache or fresh call)
        """
        # Try cache first
        cached = self.get(prompt, operation, context_hash)
        if cached is not None:
            return cached
        
        # Call the function
        try:
            result = call_func()
        except Exception as e:
            logger.error(f"AI call failed for operation {operation}: {e}")
            return None
        
        # Cache the result
        if result is not None:
            self.set(prompt, result, operation, context_hash, ttl)
        
        return result
    
    def invalidate(self, prompt: str, operation: str = 'default',
                   context_hash: Optional[str] = None) -> bool:
        """Invalidate a specific cached response."""
        cache = self._get_cache()
        if cache is None:
            return False
        
        cache_key = self._generate_cache_key(prompt, operation, context_hash)
        
        try:
            cache.delete(cache_key)
            logger.debug(f"AI cache invalidated for operation: {operation}")
            return True
        except Exception as e:
            logger.warning(f"AI cache invalidate error: {e}")
            return False
    
    def invalidate_operation(self, operation: str) -> int:
        """
        Invalidate all cached responses for an operation type.
        Note: Only works with Redis backend that supports pattern deletion.
        """
        cache = self._get_cache()
        if cache is None:
            return 0
        
        pattern = f"{self.KEY_PREFIX}:{operation}:*"
        
        try:
            if hasattr(cache, 'delete_pattern'):
                count = cache.delete_pattern(pattern)
                logger.info(f"Invalidated {count} cache entries for operation: {operation}")
                return count
            else:
                logger.warning("Pattern deletion not supported by cache backend")
                return 0
        except Exception as e:
            logger.warning(f"AI cache pattern invalidation error: {e}")
            return 0
    
    def get_stats(self) -> Dict:
        """Get cache statistics."""
        total = self._stats['hits'] + self._stats['misses']
        hit_rate = (self._stats['hits'] / total * 100) if total > 0 else 0
        
        return {
            **self._stats,
            'total_requests': total,
            'hit_rate': f"{hit_rate:.2f}%",
            'since': self._last_reset.isoformat(),
            'enabled': self.is_enabled(),
        }
    
    def reset_stats(self):
        """Reset statistics."""
        self._stats = {
            'hits': 0,
            'misses': 0,
            'errors': 0,
            'api_calls_saved': 0,
            'estimated_cost_saved': 0.0,
            'cache_bypassed': 0,
        }
        self._last_reset = datetime.now()


# Global instance
ai_cache_manager = AICacheManager()


# =============================================================================
# DECORATOR FOR AI FUNCTIONS
# =============================================================================

def cache_ai_call(operation: str = 'default', ttl: Optional[int] = None,
                  key_args: Optional[list] = None, include_kwargs: bool = True):
    """
    Decorator for caching AI function calls.
    
    Automatically caches the result of AI functions based on their arguments.
    
    Args:
        operation: Type of AI operation (for TTL selection)
        ttl: Optional TTL override in seconds
        key_args: Optional list of argument names to include in cache key
        include_kwargs: Whether to include kwargs in cache key
        
    Example:
        @cache_ai_call(operation='budget_analysis', ttl=3600)
        def analyze_budget(board_id, user_id=None):
            return call_gemini_api(...)
            
        @cache_ai_call(operation='skill_analysis', key_args=['task_id'])
        def analyze_skills(task_id, include_soft_skills=True):
            return call_gemini_api(...)
    """
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            # Build context hash from arguments
            context_parts = []
            
            # Include specified args or all args
            if key_args:
                # Get function parameter names
                import inspect
                sig = inspect.signature(func)
                params = list(sig.parameters.keys())
                
                for key_arg in key_args:
                    if key_arg in kwargs:
                        context_parts.append(f"{key_arg}={kwargs[key_arg]}")
                    elif key_arg in params:
                        idx = params.index(key_arg)
                        if idx < len(args):
                            context_parts.append(f"{key_arg}={args[idx]}")
            else:
                # Include all args
                context_parts.extend(str(arg) for arg in args)
            
            # Include kwargs if specified
            if include_kwargs and not key_args:
                context_parts.extend(f"{k}={v}" for k, v in sorted(kwargs.items()))
            
            context_hash = ':'.join(context_parts) if context_parts else None
            
            # Generate a prompt-like key from function name and args
            prompt_key = f"{func.__module__}.{func.__name__}:{context_hash or 'no_args'}"
            
            # Check cache
            cached = ai_cache_manager.get(prompt_key, operation, context_hash)
            if cached is not None:
                logger.debug(f"Cache HIT for {func.__name__}")
                return cached
            
            # Call function
            result = func(*args, **kwargs)
            
            # Cache result
            if result is not None:
                ai_cache_manager.set(prompt_key, result, operation, context_hash, ttl)
                logger.debug(f"Cached result for {func.__name__}")
            
            return result
        
        # Add utility methods to wrapper
        wrapper.cache_clear = lambda: ai_cache_manager.invalidate_operation(operation)
        
        return wrapper
    return decorator


def cache_ai_prompt(operation: str = 'default', ttl: Optional[int] = None,
                    prompt_arg: str = 'prompt'):
    """
    Decorator for caching AI calls based on prompt content.
    
    Uses the prompt text itself to generate the cache key, enabling
    deduplication of identical prompts across different callers.
    
    Args:
        operation: Type of AI operation (for TTL selection)
        ttl: Optional TTL override in seconds
        prompt_arg: Name of the argument containing the prompt
        
    Example:
        @cache_ai_prompt(operation='risk_assessment')
        def assess_risk(prompt, model=None):
            return model.generate_content(prompt).text
    """
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            # Extract prompt from arguments
            prompt = None
            
            # Check kwargs first
            if prompt_arg in kwargs:
                prompt = kwargs[prompt_arg]
            else:
                # Check positional args
                import inspect
                sig = inspect.signature(func)
                params = list(sig.parameters.keys())
                
                if prompt_arg in params:
                    idx = params.index(prompt_arg)
                    if idx < len(args):
                        prompt = args[idx]
            
            if prompt is None:
                logger.warning(f"Could not extract prompt from {func.__name__}, calling without cache")
                return func(*args, **kwargs)
            
            # Use cache manager
            return ai_cache_manager.get_or_call(
                prompt=str(prompt),
                call_func=lambda: func(*args, **kwargs),
                operation=operation,
                ttl=ttl
            )
        
        wrapper.cache_clear = lambda: ai_cache_manager.invalidate_operation(operation)
        
        return wrapper
    return decorator


# =============================================================================
# CONVENIENCE FUNCTIONS
# =============================================================================

def get_cached_ai_response(prompt: str, model_call: Callable,
                           operation: str = 'default',
                           context_id: Optional[str] = None,
                           ttl: Optional[int] = None) -> Optional[str]:
    """
    Convenience function for caching AI model responses.
    
    Args:
        prompt: The prompt to send to the AI
        model_call: Callable that returns the AI response (e.g., model.generate_content)
        operation: Type of operation for TTL selection
        context_id: Optional identifier for the context (e.g., board_id)
        ttl: Optional TTL override
        
    Returns:
        AI response text or None
        
    Example:
        response = get_cached_ai_response(
            prompt="Analyze this budget...",
            model_call=lambda: model.generate_content(prompt),
            operation='budget_analysis',
            context_id=f"board_{board_id}"
        )
    """
    def extract_text(result):
        # Handle different response types
        if result is None:
            return None
        if hasattr(result, 'text'):
            return result.text
        if isinstance(result, str):
            return result
        return str(result)
    
    # Get from cache or call
    cached = ai_cache_manager.get(prompt, operation, context_id)
    if cached is not None:
        return cached
    
    try:
        raw_result = model_call()
        result = extract_text(raw_result)
        
        if result:
            ai_cache_manager.set(prompt, result, operation, context_id, ttl)
        
        return result
    except Exception as e:
        logger.error(f"AI call failed: {e}")
        return None


def cache_warm_ai_responses(board_id: int) -> Dict:
    """
    Pre-warm common AI caches for a board.
    
    Called after significant board changes to ensure cache is populated.
    
    Returns:
        Dict with warming results
    """
    results = {'warmed': [], 'errors': []}
    
    try:
        from kanban.models import Board
        board = Board.objects.get(id=board_id)
        
        # Warm board analytics summary
        # This would call your analytics functions which are now cached
        logger.info(f"Cache warming initiated for board {board_id}")
        
        # Add specific warming logic here as needed
        results['warmed'].append('board_context')
        
    except Exception as e:
        results['errors'].append(str(e))
        logger.error(f"Cache warming error for board {board_id}: {e}")
    
    return results


# =============================================================================
# STATISTICS AND MANAGEMENT
# =============================================================================

def get_ai_cache_stats() -> Dict:
    """Get AI cache statistics."""
    return ai_cache_manager.get_stats()


def reset_ai_cache_stats():
    """Reset AI cache statistics."""
    ai_cache_manager.reset_stats()


def clear_ai_cache(operation: Optional[str] = None) -> int:
    """
    Clear AI cache entries.
    
    Args:
        operation: Optional operation type to clear, None for all
        
    Returns:
        Number of entries cleared
    """
    if operation:
        return ai_cache_manager.invalidate_operation(operation)
    else:
        # Clear all AI cache operations
        total = 0
        for op in AI_CACHE_TTLS.keys():
            total += ai_cache_manager.invalidate_operation(op)
        return total
