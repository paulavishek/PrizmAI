import logging
import requests
from django.conf import settings
from django.core.cache import cache
import time

logger = logging.getLogger(__name__)


class GoogleSearchClient:
    """Google Custom Search API client for RAG"""
    
    def __init__(self):
        self.api_key = getattr(settings, 'GOOGLE_SEARCH_API_KEY', None)
        self.search_engine_id = getattr(settings, 'GOOGLE_SEARCH_ENGINE_ID', None)
        self.enabled = getattr(settings, 'ENABLE_WEB_SEARCH', False)
        self.max_results = 10
        self.rate_limit_retries = 3
        self.cache_ttl = 3600  # 1 hour
    
    def search(self, query, num_results=None, use_cache=True):
        """
        Perform Google Custom Search
        
        Args:
            query (str): Search query
            num_results (int): Number of results to return
            use_cache (bool): Whether to use cached results
            
        Returns:
            list: Search results with title, link, snippet
        """
        if not self.enabled or not self.api_key or not self.search_engine_id:
            logger.warning("Google Search not properly configured")
            return []
        
        try:
            # Check cache
            if use_cache:
                cache_key = f"google_search:{query}"
                cached_result = cache.get(cache_key)
                if cached_result:
                    logger.info(f"Using cached search results for: {query}")
                    return cached_result
            
            num = min(num_results or self.max_results, 10)
            
            params = {
                'key': self.api_key,
                'cx': self.search_engine_id,
                'q': query,
                'num': num,
            }
            
            # Retry logic for rate limiting
            for attempt in range(self.rate_limit_retries):
                try:
                    response = requests.get(
                        'https://www.googleapis.com/customsearch/v1',
                        params=params,
                        timeout=10
                    )
                    response.raise_for_status()
                    
                    data = response.json()
                    
                    # Extract results
                    results = []
                    if 'items' in data:
                        for item in data['items'][:num]:
                            results.append({
                                'title': item.get('title', ''),
                                'link': item.get('link', ''),
                                'snippet': item.get('snippet', ''),
                            })
                    
                    # Cache results
                    if use_cache:
                        cache.set(f"google_search:{query}", results, self.cache_ttl)
                    
                    logger.info(f"Google Search returned {len(results)} results for: {query}")
                    return results
                
                except requests.exceptions.HTTPError as e:
                    if response.status_code == 429:  # Rate limited
                        if attempt < self.rate_limit_retries - 1:
                            wait_time = 2 ** attempt  # Exponential backoff
                            logger.warning(f"Rate limited, waiting {wait_time}s before retry")
                            time.sleep(wait_time)
                            continue
                    elif response.status_code == 403:
                        logger.error(f"Google Search API access forbidden (403). Please check:\n"
                                   f"  1. API key is valid\n"
                                   f"  2. Custom Search API is enabled in Google Cloud Console\n"
                                   f"  3. Search Engine ID is correct\n"
                                   f"  4. No IP/domain restrictions on the API key\n"
                                   f"  Query: {query}")
                        return []
                    elif response.status_code == 400:
                        logger.error(f"Google Search bad request (400). Invalid search engine ID or query. Query: {query}")
                        return []
                    raise
        
        except requests.exceptions.HTTPError as e:
            logger.error(f"Error performing Google Search: {e}")
            return []
        except Exception as e:
            logger.error(f"Unexpected error performing Google Search: {e}")
            return []
    
    def get_search_context(self, query, max_results=3, use_cache=True):
        """
        Get search results formatted as context for AI models
        
        Args:
            query (str): Search query
            max_results (int): Number of results to include
            use_cache (bool): Whether to use cache
            
        Returns:
            str: Formatted context with sources (None if search failed)
        """
        results = self.search(query, max_results, use_cache)
        
        if not results:
            # Return None instead of error message to allow fallback handling
            logger.info(f"No web search results available for: {query}")
            return None
        
        context = "**Recent Information from Web Search:**\n\n"
        
        for i, result in enumerate(results, 1):
            context += f"**[Source {i}] {result['title']}**\n"
            context += f"URL: {result['link']}\n"
            context += f"Summary: {result['snippet']}\n\n"
        
        return context
