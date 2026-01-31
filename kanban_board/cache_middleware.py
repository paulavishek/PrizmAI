"""
Cache Middleware for PrizmAI

Provides automatic caching for views and API responses.
"""

import hashlib
import logging
from typing import Optional

from django.conf import settings
from django.core.cache import caches
from django.http import HttpRequest, HttpResponse
from django.utils.cache import get_cache_key, learn_cache_key, patch_response_headers
from django.utils.deprecation import MiddlewareMixin

logger = logging.getLogger(__name__)


class ConditionalCacheMiddleware(MiddlewareMixin):
    """
    Conditional caching middleware that caches responses based on URL patterns.
    
    This middleware provides:
    - Automatic caching for GET requests to specified URL patterns
    - User-aware caching (different cache per user)
    - Cache bypass for authenticated dynamic content
    - Automatic cache invalidation headers
    """
    
    # URL prefixes that should be cached (GET requests only)
    CACHEABLE_PREFIXES = [
        '/api/v1/boards/',
        '/api/v1/tasks/',
        '/burndown/',
        '/analytics/',
    ]
    
    # URL prefixes that should NEVER be cached
    NEVER_CACHE_PREFIXES = [
        '/admin/',
        '/accounts/',
        '/login/',
        '/logout/',
        '/register/',
        '/api/v1/auth/',
        '/ws/',
        '/demo/',
    ]
    
    # Default cache timeout in seconds
    DEFAULT_CACHE_TIMEOUT = 60
    
    def __init__(self, get_response=None):
        super().__init__(get_response)
        self.cache = caches['default']
        self.cache_timeout = getattr(settings, 'CACHE_MIDDLEWARE_SECONDS', self.DEFAULT_CACHE_TIMEOUT)
    
    def _should_cache(self, request: HttpRequest) -> bool:
        """Determine if request should be cached."""
        # Only cache GET and HEAD requests
        if request.method not in ('GET', 'HEAD'):
            return False
        
        # Check never-cache patterns
        for prefix in self.NEVER_CACHE_PREFIXES:
            if request.path.startswith(prefix):
                return False
        
        # Check cacheable patterns
        for prefix in self.CACHEABLE_PREFIXES:
            if request.path.startswith(prefix):
                return True
        
        return False
    
    def _get_cache_key(self, request: HttpRequest) -> str:
        """Generate cache key for request."""
        key_parts = [
            'view_cache',
            request.method,
            request.path,
        ]
        
        # Include user ID for authenticated requests
        if request.user.is_authenticated:
            key_parts.append(f'user:{request.user.id}')
        else:
            key_parts.append('anon')
        
        # Include query string
        if request.GET:
            key_parts.append(request.GET.urlencode())
        
        key_string = ':'.join(key_parts)
        return f"prizmAI:view:{hashlib.md5(key_string.encode()).hexdigest()}"
    
    def process_request(self, request: HttpRequest) -> Optional[HttpResponse]:
        """Check cache for existing response."""
        if not self._should_cache(request):
            return None
        
        cache_key = self._get_cache_key(request)
        response = self.cache.get(cache_key)
        
        if response is not None:
            logger.debug(f"Cache HIT for {request.path}")
            # Add cache hit header
            response['X-Cache'] = 'HIT'
            return response
        
        # Store key in request for later use
        request._cache_key = cache_key
        return None
    
    def process_response(self, request: HttpRequest, response: HttpResponse) -> HttpResponse:
        """Cache the response if applicable."""
        if not self._should_cache(request):
            return response
        
        # Only cache successful responses
        if response.status_code != 200:
            return response
        
        # Don't cache if response says not to
        if response.get('Cache-Control', '').lower() == 'no-cache':
            return response
        
        cache_key = getattr(request, '_cache_key', None)
        if cache_key:
            # Store in cache
            self.cache.set(cache_key, response, self.cache_timeout)
            logger.debug(f"Cached response for {request.path}")
            response['X-Cache'] = 'MISS'
        
        return response


class APICacheMiddleware(MiddlewareMixin):
    """
    Specialized caching middleware for API endpoints.
    
    Features:
    - Longer cache times for stable API endpoints
    - ETag support for conditional requests
    - Automatic cache invalidation on POST/PUT/DELETE
    """
    
    # Cache timeouts by endpoint pattern
    CACHE_TIMEOUTS = {
        '/api/v1/boards/': 120,      # 2 minutes
        '/api/v1/tasks/': 60,        # 1 minute
        '/api/v1/analytics/': 300,   # 5 minutes
        '/api/v1/user/': 600,        # 10 minutes
    }
    
    def __init__(self, get_response=None):
        super().__init__(get_response)
        self.cache = caches['default']
    
    def _get_timeout(self, path: str) -> int:
        """Get cache timeout for path."""
        for pattern, timeout in self.CACHE_TIMEOUTS.items():
            if path.startswith(pattern):
                return timeout
        return 60  # Default 1 minute
    
    def _get_cache_key(self, request: HttpRequest) -> str:
        """Generate cache key for API request."""
        key_parts = [
            'api_cache',
            request.method,
            request.path,
        ]
        
        if request.user.is_authenticated:
            key_parts.append(f'user:{request.user.id}')
        
        if request.GET:
            key_parts.append(request.GET.urlencode())
        
        # Include Accept header for content negotiation
        accept = request.headers.get('Accept', 'application/json')
        key_parts.append(f'accept:{accept}')
        
        key_string = ':'.join(key_parts)
        return f"prizmAI:api:{hashlib.md5(key_string.encode()).hexdigest()}"
    
    def _generate_etag(self, response: HttpResponse) -> str:
        """Generate ETag for response content."""
        content = response.content if hasattr(response, 'content') else b''
        return f'"{hashlib.md5(content).hexdigest()}"'
    
    def process_request(self, request: HttpRequest) -> Optional[HttpResponse]:
        """Check cache for API requests."""
        if not request.path.startswith('/api/'):
            return None
        
        if request.method not in ('GET', 'HEAD'):
            return None
        
        cache_key = self._get_cache_key(request)
        cached = self.cache.get(cache_key)
        
        if cached:
            response, etag = cached
            
            # Check If-None-Match header
            if_none_match = request.headers.get('If-None-Match')
            if if_none_match and if_none_match == etag:
                return HttpResponse(status=304)
            
            response['X-Cache'] = 'HIT'
            response['ETag'] = etag
            return response
        
        request._api_cache_key = cache_key
        return None
    
    def process_response(self, request: HttpRequest, response: HttpResponse) -> HttpResponse:
        """Cache API response and add headers."""
        if not request.path.startswith('/api/'):
            return response
        
        # Invalidate cache on mutations
        if request.method in ('POST', 'PUT', 'PATCH', 'DELETE'):
            self._invalidate_related(request)
            return response
        
        if request.method not in ('GET', 'HEAD'):
            return response
        
        if response.status_code != 200:
            return response
        
        cache_key = getattr(request, '_api_cache_key', None)
        if cache_key:
            etag = self._generate_etag(response)
            timeout = self._get_timeout(request.path)
            
            self.cache.set(cache_key, (response, etag), timeout)
            
            response['X-Cache'] = 'MISS'
            response['ETag'] = etag
            response['Cache-Control'] = f'private, max-age={timeout}'
        
        return response
    
    def _invalidate_related(self, request: HttpRequest) -> None:
        """Invalidate related cache entries after mutations."""
        path = request.path
        
        # Extract resource type and ID from path
        parts = path.strip('/').split('/')
        if len(parts) >= 3:
            # e.g., /api/v1/boards/123/
            resource_type = parts[2]  # 'boards', 'tasks', etc.
            
            # Delete all cached entries for this resource type
            pattern = f"prizmAI:api:*{resource_type}*"
            # Note: Pattern deletion requires Redis backend
            try:
                if hasattr(self.cache, 'delete_pattern'):
                    self.cache.delete_pattern(pattern)
            except Exception as e:
                logger.warning(f"Could not invalidate cache pattern {pattern}: {e}")
