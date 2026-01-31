"""
Comprehensive Caching System for PrizmAI

This module provides a multi-tier caching strategy optimized for cloud deployment,
reducing API calls, database queries, and compute costs.

Cache Tiers:
1. Local Memory Cache (L1) - Fastest, single process
2. Redis Cache (L2) - Shared across processes, persistent
3. Database Query Cache - ORM-level caching

Usage:
    from kanban_board.cache import cache_manager, cached_view, cached_ai_response
    
    # Cache a function result
    @cached_ai_response(timeout=3600)
    def get_ai_recommendation(task_id):
        ...
    
    # Cache a view response
    @cached_view(timeout=300, key_prefix='board_detail')
    def board_detail_view(request, board_id):
        ...
    
    # Manual cache operations
    cache_manager.set('key', value, timeout=300)
    value = cache_manager.get('key')
"""

import hashlib
import json
import logging
import functools
from typing import Any, Callable, Optional, Union
from datetime import timedelta

from django.core.cache import caches, cache
from django.conf import settings
from django.http import HttpRequest
from django.db.models import QuerySet

logger = logging.getLogger(__name__)


# =============================================================================
# CACHE KEY GENERATORS
# =============================================================================

def make_cache_key(*args, **kwargs) -> str:
    """
    Generate a unique cache key from arguments.
    
    Args:
        *args: Positional arguments to include in key
        **kwargs: Keyword arguments to include in key
        
    Returns:
        A hashed cache key string
    """
    key_parts = [str(arg) for arg in args]
    key_parts.extend(f"{k}={v}" for k, v in sorted(kwargs.items()))
    key_string = ":".join(key_parts)
    return hashlib.md5(key_string.encode()).hexdigest()


def make_user_cache_key(user_id: int, prefix: str, *args) -> str:
    """Generate a user-specific cache key."""
    return f"user:{user_id}:{prefix}:{make_cache_key(*args)}"


def make_board_cache_key(board_id: int, prefix: str, *args) -> str:
    """Generate a board-specific cache key."""
    return f"board:{board_id}:{prefix}:{make_cache_key(*args)}"


def make_org_cache_key(org_id: int, prefix: str, *args) -> str:
    """Generate an organization-specific cache key."""
    return f"org:{org_id}:{prefix}:{make_cache_key(*args)}"


# =============================================================================
# CACHE MANAGER CLASS
# =============================================================================

class CacheManager:
    """
    Multi-tier cache manager for PrizmAI.
    
    Provides a unified interface for caching with support for:
    - Multiple cache backends (local, redis)
    - Cache versioning for invalidation
    - Automatic key prefixing
    - Cache statistics and monitoring
    """
    
    # Cache timeout presets (in seconds)
    TIMEOUTS = {
        'short': 60,           # 1 minute - for frequently changing data
        'medium': 300,         # 5 minutes - for moderately static data
        'long': 3600,          # 1 hour - for stable data
        'extended': 86400,     # 24 hours - for rarely changing data
        'ai_response': 1800,   # 30 minutes - for AI-generated content
        'user_session': 7200,  # 2 hours - for user session data
        'static': 604800,      # 1 week - for static content
    }
    
    # Cache key prefixes
    PREFIXES = {
        'ai': 'ai',
        'board': 'board',
        'task': 'task',
        'user': 'user',
        'analytics': 'analytics',
        'coach': 'coach',
        'conflict': 'conflict',
        'burndown': 'burndown',
        'budget': 'budget',
        'wiki': 'wiki',
        'permission': 'perm',
    }
    
    def __init__(self):
        self._version = 1
        self._stats = {
            'hits': 0,
            'misses': 0,
            'sets': 0,
        }
    
    def _get_cache(self, cache_name: str = 'default'):
        """Get the cache backend."""
        return caches[cache_name]
    
    def _make_key(self, key: str, prefix: Optional[str] = None) -> str:
        """Generate a versioned cache key."""
        if prefix:
            return f"prizmAI:v{self._version}:{prefix}:{key}"
        return f"prizmAI:v{self._version}:{key}"
    
    def get(self, key: str, default: Any = None, prefix: Optional[str] = None,
            cache_name: str = 'default') -> Any:
        """
        Get a value from cache.
        
        Args:
            key: The cache key
            default: Default value if key not found
            prefix: Optional key prefix
            cache_name: Cache backend name
            
        Returns:
            Cached value or default
        """
        full_key = self._make_key(key, prefix)
        cache_backend = self._get_cache(cache_name)
        
        try:
            value = cache_backend.get(full_key, default)
            if value is not None and value != default:
                self._stats['hits'] += 1
                logger.debug(f"Cache HIT: {full_key}")
            else:
                self._stats['misses'] += 1
                logger.debug(f"Cache MISS: {full_key}")
            return value
        except Exception as e:
            logger.warning(f"Cache get error for {full_key}: {e}")
            return default
    
    def set(self, key: str, value: Any, timeout: Optional[int] = None,
            prefix: Optional[str] = None, cache_name: str = 'default') -> bool:
        """
        Set a value in cache.
        
        Args:
            key: The cache key
            value: Value to cache
            timeout: Cache timeout in seconds (None for default)
            prefix: Optional key prefix
            cache_name: Cache backend name
            
        Returns:
            True if successful
        """
        full_key = self._make_key(key, prefix)
        cache_backend = self._get_cache(cache_name)
        
        if timeout is None:
            timeout = self.TIMEOUTS['medium']
        
        try:
            cache_backend.set(full_key, value, timeout)
            self._stats['sets'] += 1
            logger.debug(f"Cache SET: {full_key} (timeout: {timeout}s)")
            return True
        except Exception as e:
            logger.warning(f"Cache set error for {full_key}: {e}")
            return False
    
    def delete(self, key: str, prefix: Optional[str] = None,
               cache_name: str = 'default') -> bool:
        """Delete a key from cache."""
        full_key = self._make_key(key, prefix)
        cache_backend = self._get_cache(cache_name)
        
        try:
            cache_backend.delete(full_key)
            logger.debug(f"Cache DELETE: {full_key}")
            return True
        except Exception as e:
            logger.warning(f"Cache delete error for {full_key}: {e}")
            return False
    
    def delete_pattern(self, pattern: str, cache_name: str = 'default') -> int:
        """
        Delete all keys matching a pattern.
        Note: Only works with Redis backend.
        
        Args:
            pattern: Key pattern (e.g., "board:123:*")
            cache_name: Cache backend name
            
        Returns:
            Number of keys deleted
        """
        cache_backend = self._get_cache(cache_name)
        full_pattern = self._make_key(pattern)
        
        # Check if using Redis
        if hasattr(cache_backend, 'delete_pattern'):
            try:
                return cache_backend.delete_pattern(full_pattern)
            except Exception as e:
                logger.warning(f"Cache delete_pattern error for {full_pattern}: {e}")
        else:
            # Fallback for non-Redis backends
            logger.warning("delete_pattern not supported for this cache backend")
        return 0
    
    def get_or_set(self, key: str, default_func: Callable, timeout: Optional[int] = None,
                   prefix: Optional[str] = None, cache_name: str = 'default') -> Any:
        """
        Get value from cache, or compute and set it.
        
        Args:
            key: The cache key
            default_func: Callable to generate value if not cached
            timeout: Cache timeout in seconds
            prefix: Optional key prefix
            cache_name: Cache backend name
            
        Returns:
            Cached or computed value
        """
        value = self.get(key, prefix=prefix, cache_name=cache_name)
        
        if value is None:
            value = default_func()
            if value is not None:
                self.set(key, value, timeout=timeout, prefix=prefix, cache_name=cache_name)
        
        return value
    
    def invalidate_board(self, board_id: int) -> None:
        """Invalidate all caches related to a board."""
        patterns = [
            f"board:{board_id}:*",
            f"task:board:{board_id}:*",
            f"burndown:{board_id}:*",
            f"conflict:{board_id}:*",
        ]
        for pattern in patterns:
            self.delete_pattern(pattern)
        logger.info(f"Invalidated board cache for board_id={board_id}")
    
    def invalidate_user(self, user_id: int) -> None:
        """Invalidate all caches related to a user."""
        self.delete_pattern(f"user:{user_id}:*")
        logger.info(f"Invalidated user cache for user_id={user_id}")
    
    def invalidate_org(self, org_id: int) -> None:
        """Invalidate all caches related to an organization."""
        self.delete_pattern(f"org:{org_id}:*")
        logger.info(f"Invalidated org cache for org_id={org_id}")
    
    def get_stats(self) -> dict:
        """Get cache statistics."""
        total = self._stats['hits'] + self._stats['misses']
        hit_rate = (self._stats['hits'] / total * 100) if total > 0 else 0
        
        return {
            **self._stats,
            'total_requests': total,
            'hit_rate': f"{hit_rate:.2f}%",
        }
    
    def bump_version(self) -> None:
        """Bump the cache version, effectively invalidating all cached data."""
        self._version += 1
        logger.info(f"Cache version bumped to {self._version}")


# Global cache manager instance
cache_manager = CacheManager()


# =============================================================================
# CACHING DECORATORS
# =============================================================================

def cached(timeout: Optional[int] = None, prefix: Optional[str] = None,
           key_func: Optional[Callable] = None):
    """
    General-purpose caching decorator.
    
    Args:
        timeout: Cache timeout in seconds
        prefix: Key prefix for namespacing
        key_func: Optional function to generate cache key from args
        
    Example:
        @cached(timeout=300, prefix='analytics')
        def get_project_stats(project_id):
            ...
    """
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            # Generate cache key
            if key_func:
                cache_key = key_func(*args, **kwargs)
            else:
                cache_key = f"{func.__name__}:{make_cache_key(*args, **kwargs)}"
            
            # Try to get from cache
            result = cache_manager.get(cache_key, prefix=prefix)
            if result is not None:
                return result
            
            # Compute and cache
            result = func(*args, **kwargs)
            if result is not None:
                cache_manager.set(cache_key, result, timeout=timeout, prefix=prefix)
            
            return result
        
        # Add cache control methods to the wrapper
        wrapper.cache_clear = lambda: cache_manager.delete_pattern(f"{func.__name__}:*")
        
        return wrapper
    return decorator


def cached_ai_response(timeout: int = 1800, include_user: bool = True):
    """
    Caching decorator specifically for AI responses.
    
    Caches AI-generated content to reduce API costs.
    
    Args:
        timeout: Cache timeout (default 30 minutes)
        include_user: Whether to include user_id in cache key
        
    Example:
        @cached_ai_response(timeout=3600)
        def get_ai_task_suggestions(board_id, user_id):
            ...
    """
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            # Build cache key
            key_parts = [func.__name__]
            key_parts.extend(str(arg) for arg in args)
            
            if include_user and 'user' in kwargs:
                key_parts.append(f"user:{kwargs['user'].id}")
            elif include_user and 'user_id' in kwargs:
                key_parts.append(f"user:{kwargs['user_id']}")
            
            cache_key = make_cache_key(*key_parts)
            
            # Try cache first
            result = cache_manager.get(cache_key, prefix='ai')
            if result is not None:
                logger.debug(f"AI response cache hit for {func.__name__}")
                return result
            
            # Call the AI function
            result = func(*args, **kwargs)
            
            # Cache the result
            if result is not None:
                cache_manager.set(cache_key, result, timeout=timeout, prefix='ai')
                logger.debug(f"AI response cached for {func.__name__}")
            
            return result
        
        return wrapper
    return decorator


def cached_queryset(timeout: int = 300, prefix: str = 'qs'):
    """
    Caching decorator for Django QuerySet results.
    
    Caches the evaluated QuerySet as a list.
    
    Args:
        timeout: Cache timeout in seconds
        prefix: Cache key prefix
        
    Example:
        @cached_queryset(timeout=600, prefix='board_tasks')
        def get_board_tasks(board_id):
            return Task.objects.filter(column__board_id=board_id)
    """
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            cache_key = f"{func.__name__}:{make_cache_key(*args, **kwargs)}"
            
            # Try cache
            result = cache_manager.get(cache_key, prefix=prefix)
            if result is not None:
                return result
            
            # Execute and cache
            result = func(*args, **kwargs)
            
            # Convert QuerySet to list for caching
            if isinstance(result, QuerySet):
                result = list(result)
            
            if result is not None:
                cache_manager.set(cache_key, result, timeout=timeout, prefix=prefix)
            
            return result
        
        return wrapper
    return decorator


def cached_view(timeout: int = 300, key_prefix: str = 'view',
                vary_on_user: bool = True, vary_on_get: bool = False):
    """
    Caching decorator for Django views.
    
    Args:
        timeout: Cache timeout in seconds
        key_prefix: Cache key prefix
        vary_on_user: Whether to vary cache by user
        vary_on_get: Whether to include GET params in key
        
    Example:
        @cached_view(timeout=300, key_prefix='dashboard')
        def dashboard_view(request):
            ...
    """
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        def wrapper(request: HttpRequest, *args, **kwargs):
            # Build cache key
            key_parts = [key_prefix, func.__name__, request.path]
            
            if vary_on_user and request.user.is_authenticated:
                key_parts.append(f"user:{request.user.id}")
            
            if vary_on_get and request.GET:
                key_parts.append(request.GET.urlencode())
            
            key_parts.extend(str(v) for v in args)
            key_parts.extend(f"{k}={v}" for k, v in kwargs.items())
            
            cache_key = make_cache_key(*key_parts)
            
            # Check cache
            response = cache_manager.get(cache_key, prefix='view')
            if response is not None:
                return response
            
            # Generate response
            response = func(request, *args, **kwargs)
            
            # Cache successful responses
            if hasattr(response, 'status_code') and response.status_code == 200:
                cache_manager.set(cache_key, response, timeout=timeout, prefix='view')
            
            return response
        
        return wrapper
    return decorator


# =============================================================================
# CACHE CONTEXT MANAGERS
# =============================================================================

class CacheContext:
    """
    Context manager for grouped cache operations.
    
    Example:
        with CacheContext(prefix='board', timeout=300) as ctx:
            ctx.set('tasks', tasks)
            ctx.set('columns', columns)
    """
    
    def __init__(self, prefix: str, timeout: int = 300):
        self.prefix = prefix
        self.timeout = timeout
    
    def __enter__(self):
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        return False
    
    def get(self, key: str, default: Any = None) -> Any:
        return cache_manager.get(key, default=default, prefix=self.prefix)
    
    def set(self, key: str, value: Any, timeout: Optional[int] = None) -> bool:
        return cache_manager.set(
            key, value,
            timeout=timeout or self.timeout,
            prefix=self.prefix
        )
    
    def delete(self, key: str) -> bool:
        return cache_manager.delete(key, prefix=self.prefix)


# =============================================================================
# CACHE WARMUP UTILITIES
# =============================================================================

def warmup_board_cache(board_id: int) -> None:
    """
    Pre-populate cache for a board.
    
    Called after significant board changes to ensure cache is warm.
    """
    from kanban.models import Board, Column, Task
    
    try:
        board = Board.objects.select_related('owner', 'organization').get(id=board_id)
        
        # Cache board data
        cache_manager.set(
            f"detail:{board_id}",
            {
                'id': board.id,
                'title': board.title,
                'owner_id': board.owner_id,
                'org_id': board.organization_id,
            },
            timeout=cache_manager.TIMEOUTS['long'],
            prefix='board'
        )
        
        # Cache column data
        columns = list(Column.objects.filter(board_id=board_id).values(
            'id', 'title', 'order', 'wip_limit'
        ))
        cache_manager.set(
            f"columns:{board_id}",
            columns,
            timeout=cache_manager.TIMEOUTS['medium'],
            prefix='board'
        )
        
        # Cache task count
        task_count = Task.objects.filter(column__board_id=board_id).count()
        cache_manager.set(
            f"task_count:{board_id}",
            task_count,
            timeout=cache_manager.TIMEOUTS['short'],
            prefix='board'
        )
        
        logger.info(f"Board cache warmed for board_id={board_id}")
        
    except Board.DoesNotExist:
        logger.warning(f"Board {board_id} not found for cache warmup")
    except Exception as e:
        logger.error(f"Error warming board cache: {e}")


def warmup_user_cache(user_id: int) -> None:
    """
    Pre-populate cache for a user.
    
    Called after login to ensure fast page loads.
    """
    from kanban.models import Board, BoardMembership
    from django.contrib.auth import get_user_model
    
    User = get_user_model()
    
    try:
        user = User.objects.select_related('profile').get(id=user_id)
        
        # Cache user's boards
        owned_boards = list(Board.objects.filter(owner_id=user_id).values(
            'id', 'title', 'created_at'
        )[:20])
        cache_manager.set(
            f"owned_boards:{user_id}",
            owned_boards,
            timeout=cache_manager.TIMEOUTS['medium'],
            prefix='user'
        )
        
        # Cache memberships
        memberships = list(BoardMembership.objects.filter(user_id=user_id).values(
            'board_id', 'role__name', 'joined_at'
        )[:50])
        cache_manager.set(
            f"memberships:{user_id}",
            memberships,
            timeout=cache_manager.TIMEOUTS['medium'],
            prefix='user'
        )
        
        logger.info(f"User cache warmed for user_id={user_id}")
        
    except User.DoesNotExist:
        logger.warning(f"User {user_id} not found for cache warmup")
    except Exception as e:
        logger.error(f"Error warming user cache: {e}")


# =============================================================================
# CACHE INVALIDATION SIGNALS
# =============================================================================

def setup_cache_signals():
    """
    Set up Django signals for automatic cache invalidation.
    
    Call this in AppConfig.ready() method.
    """
    from django.db.models.signals import post_save, post_delete, m2m_changed
    from django.dispatch import receiver
    
    # Import models here to avoid circular imports
    try:
        from kanban.models import Board, Column, Task, Comment, BoardMembership
        
        @receiver(post_save, sender=Board)
        def invalidate_board_cache_on_save(sender, instance, **kwargs):
            cache_manager.invalidate_board(instance.id)
            if instance.owner_id:
                cache_manager.delete(f"owned_boards:{instance.owner_id}", prefix='user')
        
        @receiver(post_delete, sender=Board)
        def invalidate_board_cache_on_delete(sender, instance, **kwargs):
            cache_manager.invalidate_board(instance.id)
            if instance.owner_id:
                cache_manager.delete(f"owned_boards:{instance.owner_id}", prefix='user')
        
        @receiver(post_save, sender=Task)
        def invalidate_task_cache_on_save(sender, instance, **kwargs):
            if instance.column_id:
                cache_manager.delete(f"task_count:{instance.column.board_id}", prefix='board')
        
        @receiver(post_delete, sender=Task)
        def invalidate_task_cache_on_delete(sender, instance, **kwargs):
            if instance.column_id:
                cache_manager.delete(f"task_count:{instance.column.board_id}", prefix='board')
        
        @receiver(post_save, sender=BoardMembership)
        def invalidate_membership_cache(sender, instance, **kwargs):
            cache_manager.delete(f"memberships:{instance.user_id}", prefix='user')
        
        @receiver(post_delete, sender=BoardMembership)
        def invalidate_membership_cache_on_delete(sender, instance, **kwargs):
            cache_manager.delete(f"memberships:{instance.user_id}", prefix='user')
        
        logger.info("Cache invalidation signals registered")
        
    except Exception as e:
        logger.warning(f"Could not set up cache signals: {e}")
