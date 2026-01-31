"""
Cache Decorators for PrizmAI Views and Functions

This module provides easy-to-use decorators for caching various types of data
including AI responses, database queries, and view responses.

Usage Examples:

    # Cache AI responses
    @cache_ai_response(timeout=1800)
    def get_ai_recommendation(task_id, user_id):
        return ai_client.generate(...)
    
    # Cache expensive database queries
    @cache_queryset(timeout=300)
    def get_board_statistics(board_id):
        return Task.objects.filter(...).aggregate(...)
    
    # Cache entire view responses
    @cache_page_for_user(timeout=60)
    def dashboard_view(request):
        return render(...)
    
    # Cache with tags for group invalidation
    @cache_with_tags(['board', 'analytics'], timeout=300)
    def get_board_burndown(board_id):
        return calculate_burndown(...)
"""

import functools
import hashlib
import json
import logging
from typing import Any, Callable, List, Optional, Union

from django.conf import settings
from django.core.cache import caches
from django.http import HttpRequest, HttpResponse

logger = logging.getLogger(__name__)


def _get_cache(cache_name: str = 'default'):
    """Get cache backend by name."""
    return caches[cache_name]


def _make_key(prefix: str, *args, **kwargs) -> str:
    """Generate a unique cache key."""
    key_parts = [str(arg) for arg in args]
    key_parts.extend(f"{k}={v}" for k, v in sorted(kwargs.items()) if v is not None)
    key_string = ':'.join(key_parts)
    hashed = hashlib.md5(key_string.encode()).hexdigest()[:16]
    return f"prizmAI:{prefix}:{hashed}"


def cache_ai_response(timeout: int = 1800, cache_name: str = 'ai_cache',
                      key_prefix: str = 'ai'):
    """
    Decorator for caching AI-generated responses.
    
    Specifically designed for expensive AI API calls to reduce costs.
    
    Args:
        timeout: Cache timeout in seconds (default 30 minutes)
        cache_name: Cache backend to use
        key_prefix: Prefix for cache keys
        
    Example:
        @cache_ai_response(timeout=3600)
        def get_task_priority_suggestion(task_id):
            return gemini_client.generate_priority(task_id)
    """
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            # Build cache key
            cache_key = _make_key(f"{key_prefix}:{func.__name__}", *args, **kwargs)
            
            # Try cache
            try:
                cache = _get_cache(cache_name)
                cached = cache.get(cache_key)
                if cached is not None:
                    logger.debug(f"AI cache HIT: {func.__name__}")
                    return cached
            except Exception as e:
                logger.warning(f"AI cache read error: {e}")
            
            # Call function
            result = func(*args, **kwargs)
            
            # Cache result
            if result is not None:
                try:
                    cache.set(cache_key, result, timeout)
                    logger.debug(f"AI response cached: {func.__name__}")
                except Exception as e:
                    logger.warning(f"AI cache write error: {e}")
            
            return result
        
        # Add cache control methods
        wrapper.cache_key = lambda *args, **kwargs: _make_key(
            f"{key_prefix}:{func.__name__}", *args, **kwargs
        )
        wrapper.invalidate = lambda *args, **kwargs: _get_cache(cache_name).delete(
            wrapper.cache_key(*args, **kwargs)
        )
        
        return wrapper
    return decorator


def cache_queryset(timeout: int = 300, cache_name: str = 'default',
                   key_prefix: str = 'qs'):
    """
    Decorator for caching QuerySet results.
    
    Evaluates and caches QuerySet as a list.
    
    Args:
        timeout: Cache timeout in seconds
        cache_name: Cache backend to use
        key_prefix: Prefix for cache keys
        
    Example:
        @cache_queryset(timeout=600)
        def get_active_tasks(board_id):
            return Task.objects.filter(column__board_id=board_id, completed=False)
    """
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            cache_key = _make_key(f"{key_prefix}:{func.__name__}", *args, **kwargs)
            
            try:
                cache = _get_cache(cache_name)
                cached = cache.get(cache_key)
                if cached is not None:
                    logger.debug(f"QuerySet cache HIT: {func.__name__}")
                    return cached
            except Exception as e:
                logger.warning(f"QuerySet cache read error: {e}")
            
            # Execute query
            result = func(*args, **kwargs)
            
            # Convert QuerySet to list for caching
            from django.db.models import QuerySet
            if isinstance(result, QuerySet):
                result = list(result)
            
            # Cache result
            if result is not None:
                try:
                    cache.set(cache_key, result, timeout)
                    logger.debug(f"QuerySet cached: {func.__name__}")
                except Exception as e:
                    logger.warning(f"QuerySet cache write error: {e}")
            
            return result
        
        wrapper.invalidate = lambda *args, **kwargs: _get_cache(cache_name).delete(
            _make_key(f"{key_prefix}:{func.__name__}", *args, **kwargs)
        )
        
        return wrapper
    return decorator


def cache_page_for_user(timeout: int = 60, cache_name: str = 'default'):
    """
    Decorator for caching view responses per user.
    
    Unlike Django's cache_page, this creates separate cache entries
    for each authenticated user.
    
    Args:
        timeout: Cache timeout in seconds
        cache_name: Cache backend to use
        
    Example:
        @cache_page_for_user(timeout=120)
        def user_dashboard(request):
            return render(request, 'dashboard.html', context)
    """
    def decorator(view_func: Callable) -> Callable:
        @functools.wraps(view_func)
        def wrapper(request: HttpRequest, *args, **kwargs):
            # Only cache GET requests
            if request.method != 'GET':
                return view_func(request, *args, **kwargs)
            
            # Build user-specific cache key
            user_key = f"user:{request.user.id}" if request.user.is_authenticated else "anon"
            cache_key = _make_key(
                f"view:{view_func.__name__}:{user_key}",
                request.path,
                *args,
                **kwargs
            )
            
            try:
                cache = _get_cache(cache_name)
                cached = cache.get(cache_key)
                if cached is not None:
                    logger.debug(f"View cache HIT: {view_func.__name__}")
                    cached['X-Cache'] = 'HIT'
                    return cached
            except Exception as e:
                logger.warning(f"View cache read error: {e}")
            
            # Generate response
            response = view_func(request, *args, **kwargs)
            
            # Cache successful responses
            if response.status_code == 200:
                try:
                    response['X-Cache'] = 'MISS'
                    cache.set(cache_key, response, timeout)
                    logger.debug(f"View cached: {view_func.__name__}")
                except Exception as e:
                    logger.warning(f"View cache write error: {e}")
            
            return response
        
        return wrapper
    return decorator


def cache_with_tags(tags: List[str], timeout: int = 300, cache_name: str = 'default'):
    """
    Decorator for caching with tag-based invalidation.
    
    Allows invalidating groups of cached items by tag.
    
    Args:
        tags: List of tags for grouping cached items
        timeout: Cache timeout in seconds
        cache_name: Cache backend to use
        
    Example:
        @cache_with_tags(['board:123', 'analytics'], timeout=600)
        def get_board_metrics(board_id):
            return calculate_metrics(board_id)
        
        # Later, invalidate all 'analytics' caches:
        invalidate_cache_tag('analytics')
    """
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            cache_key = _make_key(f"tagged:{func.__name__}", *args, **kwargs)
            
            try:
                cache = _get_cache(cache_name)
                cached = cache.get(cache_key)
                if cached is not None:
                    return cached
            except Exception as e:
                logger.warning(f"Tagged cache read error: {e}")
            
            # Execute function
            result = func(*args, **kwargs)
            
            # Cache result and register with tags
            if result is not None:
                try:
                    cache.set(cache_key, result, timeout)
                    
                    # Register key with each tag
                    for tag in tags:
                        tag_key = f"prizmAI:tag:{tag}"
                        tag_keys = cache.get(tag_key, set())
                        if not isinstance(tag_keys, set):
                            tag_keys = set()
                        tag_keys.add(cache_key)
                        cache.set(tag_key, tag_keys, timeout + 60)
                except Exception as e:
                    logger.warning(f"Tagged cache write error: {e}")
            
            return result
        
        return wrapper
    return decorator


def invalidate_cache_tag(tag: str, cache_name: str = 'default') -> int:
    """
    Invalidate all cache entries with a specific tag.
    
    Args:
        tag: The tag to invalidate
        cache_name: Cache backend to use
        
    Returns:
        Number of entries invalidated
    """
    cache = _get_cache(cache_name)
    tag_key = f"prizmAI:tag:{tag}"
    
    try:
        tag_keys = cache.get(tag_key, set())
        if not isinstance(tag_keys, set):
            tag_keys = set()
        
        count = 0
        for key in tag_keys:
            if cache.delete(key):
                count += 1
        
        cache.delete(tag_key)
        logger.info(f"Invalidated {count} cache entries for tag '{tag}'")
        return count
    except Exception as e:
        logger.warning(f"Tag invalidation error: {e}")
        return 0


def cache_board_data(timeout: int = 300):
    """
    Specialized decorator for caching board-related data.
    
    Automatically includes board_id in cache key and provides
    easy invalidation by board.
    
    Example:
        @cache_board_data(timeout=600)
        def get_board_summary(board_id):
            return Board.objects.get(id=board_id)
    """
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        def wrapper(board_id, *args, **kwargs):
            cache_key = _make_key(f"board:{board_id}:{func.__name__}", *args, **kwargs)
            
            cache = _get_cache('default')
            cached = cache.get(cache_key)
            if cached is not None:
                return cached
            
            result = func(board_id, *args, **kwargs)
            
            if result is not None:
                cache.set(cache_key, result, timeout)
            
            return result
        
        wrapper.invalidate_for_board = lambda board_id: invalidate_board_cache(board_id)
        
        return wrapper
    return decorator


def invalidate_board_cache(board_id: int, cache_name: str = 'default') -> None:
    """
    Invalidate all cache entries for a specific board.
    
    Args:
        board_id: The board ID to invalidate
        cache_name: Cache backend to use
    """
    cache = _get_cache(cache_name)
    
    # If using Redis, use pattern deletion
    pattern = f"prizmAI:board:{board_id}:*"
    try:
        if hasattr(cache, 'delete_pattern'):
            cache.delete_pattern(pattern)
            logger.info(f"Invalidated cache for board {board_id}")
        else:
            logger.warning("Pattern deletion not supported - board cache may be stale")
    except Exception as e:
        logger.warning(f"Board cache invalidation error: {e}")


def invalidate_user_cache(user_id: int, cache_name: str = 'default') -> None:
    """
    Invalidate all cache entries for a specific user.
    
    Args:
        user_id: The user ID to invalidate
        cache_name: Cache backend to use
    """
    cache = _get_cache(cache_name)
    
    pattern = f"prizmAI:*:user:{user_id}:*"
    try:
        if hasattr(cache, 'delete_pattern'):
            cache.delete_pattern(pattern)
            logger.info(f"Invalidated cache for user {user_id}")
    except Exception as e:
        logger.warning(f"User cache invalidation error: {e}")


# =============================================================================
# CACHE UTILITIES
# =============================================================================

def get_cache_stats(cache_name: str = 'default') -> dict:
    """
    Get cache statistics (if supported by backend).
    
    Returns:
        Dictionary with cache statistics
    """
    cache = _get_cache(cache_name)
    
    stats = {
        'backend': cache.__class__.__name__,
        'available': True,
    }
    
    try:
        # Try to get Redis info
        if hasattr(cache, 'client'):
            client = cache.client.get_client()
            if hasattr(client, 'info'):
                info = client.info()
                stats.update({
                    'used_memory': info.get('used_memory_human'),
                    'connected_clients': info.get('connected_clients'),
                    'total_keys': info.get('db0', {}).get('keys', 'N/A'),
                    'hits': info.get('keyspace_hits'),
                    'misses': info.get('keyspace_misses'),
                })
    except Exception as e:
        stats['error'] = str(e)
    
    return stats


def clear_all_caches() -> None:
    """Clear all configured caches."""
    for cache_name in settings.CACHES.keys():
        try:
            cache = _get_cache(cache_name)
            cache.clear()
            logger.info(f"Cleared cache: {cache_name}")
        except Exception as e:
            logger.warning(f"Error clearing cache {cache_name}: {e}")
