#!/usr/bin/env python
"""
API Rate Limiting Test Script

This script demonstrates the rate limiting feature by:
1. Creating a test API token (if needed)
2. Making multiple API requests
3. Showing real-time rate limit status
4. Demonstrating rate limit enforcement
5. Monitoring the dashboard statistics

Usage:
    python test_api_rate_limits.py [options]

Options:
    --token TOKEN       Use existing token instead of creating new one
    --requests N        Number of requests to make (default: 50)
    --rapid             Make requests rapidly to test rate limiting
    --demo              Run a full demonstration scenario
"""

import os
import sys
import time
import argparse
import requests
from datetime import datetime
from colorama import init, Fore, Style

# Initialize colorama for colored output
init(autoreset=True)

# Django setup
import django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'kanban_board.settings')
django.setup()

from django.contrib.auth.models import User
from api.models import APIToken, APIRequestLog
from django.utils import timezone


class RateLimitTester:
    def __init__(self, base_url='http://localhost:8000'):
        self.base_url = base_url
        self.token = None
        self.api_token_obj = None
        
    def print_header(self, text):
        """Print a colored header"""
        print(f"\n{Fore.CYAN}{'='*70}")
        print(f"{Fore.CYAN}{text:^70}")
        print(f"{Fore.CYAN}{'='*70}{Style.RESET_ALL}")
    
    def print_status(self, message, status='info'):
        """Print a status message with color"""
        colors = {
            'info': Fore.BLUE,
            'success': Fore.GREEN,
            'warning': Fore.YELLOW,
            'error': Fore.RED
        }
        color = colors.get(status, Fore.WHITE)
        print(f"{color}► {message}{Style.RESET_ALL}")
    
    def create_or_get_token(self, user_id=1):
        """Create a test API token or use existing one"""
        self.print_header("API TOKEN SETUP")
        
        try:
            user = User.objects.get(id=user_id)
            self.print_status(f"Using user: {user.username}", 'info')
        except User.DoesNotExist:
            user = User.objects.first()
            if not user:
                self.print_status("No users found. Please create a user first.", 'error')
                sys.exit(1)
            self.print_status(f"Using first available user: {user.username}", 'warning')
        
        # Check for existing test token
        existing_tokens = APIToken.objects.filter(
            user=user,
            name__startswith='Test Rate Limiting'
        ).first()
        
        if existing_tokens:
            self.api_token_obj = existing_tokens
            self.print_status(f"Using existing token: {existing_tokens.name}", 'success')
        else:
            # Create new token
            self.api_token_obj = APIToken.objects.create(
                user=user,
                name=f'Test Rate Limiting - {datetime.now().strftime("%Y-%m-%d %H:%M")}',
                scopes=['*'],  # All scopes for testing
                rate_limit_per_hour=1000
            )
            self.print_status(f"Created new token: {self.api_token_obj.name}", 'success')
        
        self.token = self.api_token_obj.token
        self.print_status(f"Token ID: {self.api_token_obj.id}", 'info')
        self.print_status(f"Rate Limit: {self.api_token_obj.rate_limit_per_hour} requests/hour", 'info')
        
        return self.token
    
    def show_current_status(self):
        """Display current rate limit status"""
        if not self.api_token_obj:
            return
        
        # Refresh from database
        self.api_token_obj.refresh_from_db()
        
        usage = self.api_token_obj.request_count_current_hour
        limit = self.api_token_obj.rate_limit_per_hour
        remaining = limit - usage
        percent = (usage / limit) * 100
        
        # Create progress bar
        bar_length = 50
        filled = int(bar_length * usage / limit)
        bar = '█' * filled + '░' * (bar_length - filled)
        
        # Color based on usage
        if percent < 50:
            color = Fore.GREEN
        elif percent < 80:
            color = Fore.YELLOW
        else:
            color = Fore.RED
        
        print(f"\n{Fore.WHITE}Rate Limit Status:")
        print(f"{color}[{bar}] {usage}/{limit} ({percent:.1f}%){Style.RESET_ALL}")
        print(f"{Fore.WHITE}Remaining: {Fore.GREEN}{remaining}{Fore.WHITE} requests")
        
        time_until_reset = (self.api_token_obj.rate_limit_reset_at - timezone.now()).total_seconds()
        if time_until_reset > 0:
            minutes = int(time_until_reset // 60)
            seconds = int(time_until_reset % 60)
            print(f"{Fore.WHITE}Reset in: {Fore.CYAN}{minutes}m {seconds}s{Style.RESET_ALL}")
    
    def make_request(self, endpoint='/api/v1/status/', method='GET'):
        """Make an API request and return response"""
        url = f"{self.base_url}{endpoint}"
        headers = {
            'Authorization': f'Bearer {self.token}',
            'User-Agent': 'RateLimitTester/1.0'
        }
        
        try:
            if method == 'GET':
                response = requests.get(url, headers=headers, timeout=10)
            else:
                response = requests.post(url, headers=headers, timeout=10)
            
            return response
        except requests.exceptions.RequestException as e:
            self.print_status(f"Request failed: {e}", 'error')
            return None
    
    def test_basic_requests(self, count=50, delay=0.1):
        """Make a series of API requests"""
        self.print_header(f"MAKING {count} API REQUESTS")
        
        success_count = 0
        error_count = 0
        rate_limited_count = 0
        
        for i in range(1, count + 1):
            response = self.make_request()
            
            if response:
                if response.status_code == 200:
                    success_count += 1
                    self.print_status(
                        f"Request {i}/{count}: {Fore.GREEN}✓{Fore.BLUE} Status {response.status_code}",
                        'success'
                    )
                elif response.status_code == 429:
                    rate_limited_count += 1
                    self.print_status(
                        f"Request {i}/{count}: {Fore.RED}✗{Fore.YELLOW} Rate Limited!",
                        'warning'
                    )
                else:
                    error_count += 1
                    self.print_status(
                        f"Request {i}/{count}: {Fore.RED}✗{Fore.RED} Status {response.status_code}",
                        'error'
                    )
            
            if delay > 0:
                time.sleep(delay)
            
            # Show status every 10 requests
            if i % 10 == 0:
                self.show_current_status()
        
        # Final summary
        print(f"\n{Fore.WHITE}{'─'*70}")
        print(f"{Fore.GREEN}Success: {success_count}")
        print(f"{Fore.RED}Errors: {error_count}")
        print(f"{Fore.YELLOW}Rate Limited: {rate_limited_count}")
        print(f"{Fore.WHITE}{'─'*70}")
        
        self.show_current_status()
    
    def test_rapid_requests(self):
        """Test rate limiting by making rapid requests"""
        self.print_header("RAPID REQUEST TEST - TRIGGERING RATE LIMIT")
        
        self.print_status("Making 100 rapid requests to test rate limiting...", 'warning')
        
        # Temporarily increase rate limit for demo
        original_limit = self.api_token_obj.rate_limit_per_hour
        self.api_token_obj.rate_limit_per_hour = 20  # Set low limit for demo
        self.api_token_obj.save()
        
        self.print_status(f"Temporarily set rate limit to 20 requests/hour", 'info')
        
        rate_limited_at = None
        
        for i in range(1, 101):
            response = self.make_request()
            
            if response and response.status_code == 429:
                rate_limited_at = i
                self.print_status(
                    f"🚫 Rate limit hit at request #{i}!",
                    'error'
                )
                break
            elif i % 5 == 0:
                self.print_status(f"Sent {i} requests...", 'info')
        
        self.show_current_status()
        
        # Restore original limit
        self.api_token_obj.rate_limit_per_hour = original_limit
        self.api_token_obj.request_count_current_hour = 0  # Reset for continued testing
        self.api_token_obj.save()
        
        self.print_status(f"Restored rate limit to {original_limit} requests/hour", 'success')
    
    def show_dashboard_info(self):
        """Show information about accessing the dashboard"""
        self.print_header("DASHBOARD ACCESS")
        
        dashboard_url = f"{self.base_url}/api/v1/dashboard/rate-limits/"
        
        print(f"{Fore.WHITE}View the Rate Limiting Dashboard at:")
        print(f"{Fore.CYAN}{dashboard_url}{Style.RESET_ALL}")
        print()
        print(f"{Fore.WHITE}The dashboard shows:")
        print(f"  • Real-time rate limit status for all tokens")
        print(f"  • Live countdown timers until reset")
        print(f"  • Request analytics and charts")
        print(f"  • Top endpoints and response times")
        print(f"  • Status code distribution")
        print()
        print(f"{Fore.YELLOW}💡 Tip: Keep the dashboard open while running this script")
        print(f"   to see real-time updates!{Style.RESET_ALL}")
    
    def run_demo(self):
        """Run a full demonstration scenario"""
        self.print_header("🚀 RATE LIMITING DASHBOARD DEMONSTRATION")
        
        print(f"{Fore.WHITE}This demo will showcase the rate limiting features:")
        print(f"  1. API token creation")
        print(f"  2. Normal request patterns")
        print(f"  3. Rate limit monitoring")
        print(f"  4. Rate limit enforcement (429 responses)")
        print(f"  5. Dashboard visualization")
        print()
        input(f"{Fore.YELLOW}Press Enter to start the demo...{Style.RESET_ALL}")
        
        # Step 1: Create token
        self.create_or_get_token()
        time.sleep(2)
        
        # Step 2: Show dashboard info
        self.show_dashboard_info()
        time.sleep(2)
        
        # Step 3: Make normal requests
        self.test_basic_requests(count=30, delay=0.2)
        time.sleep(2)
        
        # Step 4: Test rapid requests and rate limiting
        self.test_rapid_requests()
        time.sleep(2)
        
        # Step 5: Final status
        self.print_header("✅ DEMONSTRATION COMPLETE")
        self.show_current_status()
        
        print(f"\n{Fore.GREEN}The dashboard now contains:")
        print(f"  ✓ Request history from this test")
        print(f"  ✓ Rate limit usage statistics")
        print(f"  ✓ Charts showing request patterns")
        print(f"  ✓ Performance metrics")
        print()
        print(f"{Fore.CYAN}Visit the dashboard to see all the data visualized!{Style.RESET_ALL}")


def main():
    parser = argparse.ArgumentParser(description='Test API rate limiting functionality')
    parser.add_argument('--token', help='Use existing token')
    parser.add_argument('--requests', type=int, default=50, help='Number of requests to make')
    parser.add_argument('--rapid', action='store_true', help='Make rapid requests to test limits')
    parser.add_argument('--demo', action='store_true', help='Run full demonstration')
    parser.add_argument('--base-url', default='http://localhost:8000', help='Base URL for API')
    
    args = parser.parse_args()
    
    tester = RateLimitTester(base_url=args.base_url)
    
    if args.token:
        tester.token = args.token
        tester.api_token_obj = APIToken.objects.get(token=args.token)
    else:
        tester.create_or_get_token()
    
    if args.demo:
        tester.run_demo()
    elif args.rapid:
        tester.test_rapid_requests()
    else:
        tester.test_basic_requests(count=args.requests)
        tester.show_dashboard_info()


if __name__ == '__main__':
    try:
        main()
    except KeyboardInterrupt:
        print(f"\n{Fore.YELLOW}Test interrupted by user{Style.RESET_ALL}")
        sys.exit(0)
    except Exception as e:
        print(f"\n{Fore.RED}Error: {e}{Style.RESET_ALL}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
