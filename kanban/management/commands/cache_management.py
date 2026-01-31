"""
Management command for cache operations in PrizmAI.

Usage:
    python manage.py cache_management --action=stats
    python manage.py cache_management --action=clear --cache=default
    python manage.py cache_management --action=clear-all
    python manage.py cache_management --action=warmup --board=123
    python manage.py cache_management --action=invalidate --board=123
"""

from django.core.management.base import BaseCommand, CommandError
from django.conf import settings
from django.core.cache import caches

import logging

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = 'Manage PrizmAI cache operations'
    
    def add_arguments(self, parser):
        parser.add_argument(
            '--action',
            type=str,
            required=True,
            choices=['stats', 'clear', 'clear-all', 'warmup', 'invalidate', 'test'],
            help='Cache action to perform'
        )
        parser.add_argument(
            '--cache',
            type=str,
            default='default',
            help='Cache backend name (default: default)'
        )
        parser.add_argument(
            '--board',
            type=int,
            help='Board ID for warmup/invalidate actions'
        )
        parser.add_argument(
            '--user',
            type=int,
            help='User ID for warmup/invalidate actions'
        )
        parser.add_argument(
            '--verbose',
            action='store_true',
            help='Verbose output'
        )
    
    def handle(self, *args, **options):
        action = options['action']
        cache_name = options['cache']
        verbose = options['verbose']
        
        self.stdout.write(f"\n{'='*60}")
        self.stdout.write(f"PrizmAI Cache Management - Action: {action}")
        self.stdout.write(f"{'='*60}\n")
        
        if action == 'stats':
            self._show_stats(cache_name, verbose)
        elif action == 'clear':
            self._clear_cache(cache_name)
        elif action == 'clear-all':
            self._clear_all_caches()
        elif action == 'warmup':
            self._warmup_cache(options.get('board'), options.get('user'))
        elif action == 'invalidate':
            self._invalidate_cache(options.get('board'), options.get('user'))
        elif action == 'test':
            self._test_cache(cache_name)
    
    def _show_stats(self, cache_name: str, verbose: bool):
        """Display cache statistics."""
        self.stdout.write(self.style.HTTP_INFO("Cache Configuration:"))
        self.stdout.write("-" * 40)
        
        for name, config in settings.CACHES.items():
            backend = config.get('BACKEND', 'Unknown')
            location = config.get('LOCATION', 'N/A')
            timeout = config.get('TIMEOUT', 'N/A')
            
            marker = " (selected)" if name == cache_name else ""
            self.stdout.write(f"\n  {name}{marker}:")
            self.stdout.write(f"    Backend: {backend.split('.')[-1]}")
            self.stdout.write(f"    Location: {location}")
            self.stdout.write(f"    Default Timeout: {timeout}s")
        
        self.stdout.write("\n")
        
        # Try to get detailed stats from Redis
        try:
            cache = caches[cache_name]
            
            if hasattr(cache, '_cache') and hasattr(cache._cache, 'get_client'):
                # Django Redis
                client = cache._cache.get_client()
                if hasattr(client, 'info'):
                    info = client.info()
                    self.stdout.write(self.style.SUCCESS("\nRedis Statistics:"))
                    self.stdout.write("-" * 40)
                    self.stdout.write(f"  Used Memory: {info.get('used_memory_human', 'N/A')}")
                    self.stdout.write(f"  Peak Memory: {info.get('used_memory_peak_human', 'N/A')}")
                    self.stdout.write(f"  Connected Clients: {info.get('connected_clients', 'N/A')}")
                    self.stdout.write(f"  Total Commands: {info.get('total_commands_processed', 'N/A')}")
                    self.stdout.write(f"  Keyspace Hits: {info.get('keyspace_hits', 'N/A')}")
                    self.stdout.write(f"  Keyspace Misses: {info.get('keyspace_misses', 'N/A')}")
                    
                    hits = info.get('keyspace_hits', 0)
                    misses = info.get('keyspace_misses', 0)
                    total = hits + misses
                    if total > 0:
                        hit_rate = (hits / total) * 100
                        self.stdout.write(f"  Hit Rate: {hit_rate:.2f}%")
                    
                    if verbose:
                        self.stdout.write("\n  Database Info:")
                        for key, value in info.items():
                            if key.startswith('db'):
                                self.stdout.write(f"    {key}: {value}")
            else:
                self.stdout.write(self.style.WARNING(
                    f"\nUsing {cache.__class__.__name__} - detailed stats not available"
                ))
        except Exception as e:
            self.stdout.write(self.style.ERROR(f"\nError getting stats: {e}"))
    
    def _clear_cache(self, cache_name: str):
        """Clear a specific cache."""
        try:
            cache = caches[cache_name]
            cache.clear()
            self.stdout.write(self.style.SUCCESS(f"✓ Cache '{cache_name}' cleared successfully"))
        except Exception as e:
            raise CommandError(f"Failed to clear cache '{cache_name}': {e}")
    
    def _clear_all_caches(self):
        """Clear all configured caches."""
        for name in settings.CACHES.keys():
            try:
                cache = caches[name]
                cache.clear()
                self.stdout.write(self.style.SUCCESS(f"✓ Cache '{name}' cleared"))
            except Exception as e:
                self.stdout.write(self.style.ERROR(f"✗ Failed to clear '{name}': {e}"))
        
        self.stdout.write(self.style.SUCCESS("\nAll caches cleared!"))
    
    def _warmup_cache(self, board_id: int = None, user_id: int = None):
        """Warmup cache for board or user."""
        from kanban_board.cache import warmup_board_cache, warmup_user_cache
        
        if board_id:
            self.stdout.write(f"Warming up cache for board {board_id}...")
            warmup_board_cache(board_id)
            self.stdout.write(self.style.SUCCESS(f"✓ Board {board_id} cache warmed"))
        
        if user_id:
            self.stdout.write(f"Warming up cache for user {user_id}...")
            warmup_user_cache(user_id)
            self.stdout.write(self.style.SUCCESS(f"✓ User {user_id} cache warmed"))
        
        if not board_id and not user_id:
            self.stdout.write(self.style.WARNING(
                "Please specify --board=ID or --user=ID for warmup"
            ))
    
    def _invalidate_cache(self, board_id: int = None, user_id: int = None):
        """Invalidate cache for board or user."""
        from kanban_board.cache import cache_manager
        
        if board_id:
            cache_manager.invalidate_board(board_id)
            self.stdout.write(self.style.SUCCESS(f"✓ Board {board_id} cache invalidated"))
        
        if user_id:
            cache_manager.invalidate_user(user_id)
            self.stdout.write(self.style.SUCCESS(f"✓ User {user_id} cache invalidated"))
        
        if not board_id and not user_id:
            self.stdout.write(self.style.WARNING(
                "Please specify --board=ID or --user=ID for invalidation"
            ))
    
    def _test_cache(self, cache_name: str):
        """Test cache connectivity and operations."""
        self.stdout.write(f"Testing cache '{cache_name}'...")
        
        try:
            cache = caches[cache_name]
            
            # Test set
            test_key = 'prizmAI:test:connection'
            test_value = {'test': True, 'message': 'Cache working!'}
            cache.set(test_key, test_value, 60)
            self.stdout.write(self.style.SUCCESS("  ✓ SET operation successful"))
            
            # Test get
            retrieved = cache.get(test_key)
            if retrieved == test_value:
                self.stdout.write(self.style.SUCCESS("  ✓ GET operation successful"))
            else:
                self.stdout.write(self.style.ERROR("  ✗ GET returned incorrect value"))
            
            # Test delete
            cache.delete(test_key)
            if cache.get(test_key) is None:
                self.stdout.write(self.style.SUCCESS("  ✓ DELETE operation successful"))
            else:
                self.stdout.write(self.style.ERROR("  ✗ DELETE failed"))
            
            # Test get_or_set
            result = cache.get_or_set('prizmAI:test:get_or_set', lambda: 'computed', 60)
            if result == 'computed':
                self.stdout.write(self.style.SUCCESS("  ✓ GET_OR_SET operation successful"))
            cache.delete('prizmAI:test:get_or_set')
            
            self.stdout.write(self.style.SUCCESS(f"\n✓ Cache '{cache_name}' is working correctly!"))
            
        except Exception as e:
            self.stdout.write(self.style.ERROR(f"\n✗ Cache test failed: {e}"))
            raise CommandError(f"Cache test failed: {e}")
