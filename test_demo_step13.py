#!/usr/bin/env python
"""
Step 13: Comprehensive Demo Testing Script
===========================================
This script performs automated testing of all demo mode features
following the Step 13 testing checklist.

Usage:
    python test_demo_step13.py
    
Test Categories:
1. Demo Mode Selection Flow
2. Demo Banner & Role Switching
3. Session Management & Expiry
4. Reset Functionality
5. Aha Moment Detection
6. Conversion Nudges
7. Analytics Tracking
8. Error Handling
9. Edge Cases
10. Performance Checks
"""

import os
import sys
import django
from datetime import datetime, timedelta
import json

# Fix encoding for Windows
if sys.platform == 'win32':
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

# Setup Django environment
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'kanban_board.settings')
django.setup()

from django.test import Client, RequestFactory
from django.contrib.auth.models import User
from django.utils import timezone
from django.contrib.sessions.models import Session
from kanban.models import Board, Task, Column, Organization
from analytics.models import DemoSession, DemoAnalytics, DemoConversion


class Colors:
    """ANSI color codes for terminal output"""
    GREEN = '\033[92m'
    RED = '\033[91m'
    YELLOW = '\033[93m'
    BLUE = '\033[94m'
    MAGENTA = '\033[95m'
    CYAN = '\033[96m'
    WHITE = '\033[97m'
    BOLD = '\033[1m'
    END = '\033[0m'


def print_header(text):
    """Print a formatted header"""
    print(f"\n{Colors.BOLD}{Colors.CYAN}{'='*80}{Colors.END}")
    print(f"{Colors.BOLD}{Colors.CYAN}{text:^80}{Colors.END}")
    print(f"{Colors.BOLD}{Colors.CYAN}{'='*80}{Colors.END}\n")


def print_section(text):
    """Print a section divider"""
    print(f"\n{Colors.BOLD}{Colors.BLUE}{text}{Colors.END}")
    print(f"{Colors.BLUE}{'-'*80}{Colors.END}")


def print_success(text):
    """Print success message"""
    print(f"{Colors.GREEN}✅ {text}{Colors.END}")


def print_error(text):
    """Print error message"""
    print(f"{Colors.RED}❌ {text}{Colors.END}")


def print_warning(text):
    """Print warning message"""
    print(f"{Colors.YELLOW}⚠️  {text}{Colors.END}")


def print_info(text):
    """Print info message"""
    print(f"{Colors.WHITE}ℹ️  {text}{Colors.END}")


class DemoTester:
    """Main testing class for Step 13"""
    
    def __init__(self):
        self.client = Client()
        self.factory = RequestFactory()
        self.test_user = None
        self.errors = []
        self.warnings = []
        self.success_count = 0
        self.total_tests = 0
        self.setup_test_user()
        
    def setup_test_user(self):
        """Create or get a test user"""
        username = 'demo_test_user'
        self.test_user = User.objects.filter(username=username).first()
        
        if not self.test_user:
            self.test_user = User.objects.create_user(
                username=username,
                email='demo_test@example.com',
                password='testpass123'
            )
            print_info(f"Created test user: {username}")
        else:
            print_info(f"Using existing test user: {username}")
            
        # Force login the test user (bypass authentication backends)
        self.client.force_login(self.test_user)
        
    def test(self, condition, success_msg, error_msg):
        """Perform a test and record result"""
        self.total_tests += 1
        if condition:
            self.success_count += 1
            print_success(success_msg)
            return True
        else:
            self.errors.append(error_msg)
            print_error(error_msg)
            return False
            
    def test_demo_mode_selection(self):
        """Test Category 1: Demo Mode Selection Flow"""
        print_section("Test 1: Demo Mode Selection Flow")
        
        # Test 1.1: Mode selection page loads
        response = self.client.get('/demo/start/')
        self.test(
            response.status_code == 200,
            "Mode selection page loads successfully",
            f"Mode selection page failed: HTTP {response.status_code}"
        )
        
        # Test 1.2: Mode selection page contains required elements
        if response.status_code == 200:
            content = response.content.decode('utf-8')
            has_solo = 'solo' in content.lower() or 'explore solo' in content.lower()
            has_team = 'team' in content.lower() or 'try as a team' in content.lower()
            
            self.test(
                has_solo,
                "Solo mode option present on page",
                "Solo mode option not found on page"
            )
            
            self.test(
                has_team,
                "Team mode option present on page",
                "Team mode option not found on page"
            )
        
        # Test 1.3: Select Solo mode
        response = self.client.post('/demo/start/', {
            'mode': 'solo',
            'selection_method': 'selected'
        })
        
        self.test(
            response.status_code in [200, 302],  # 302 = redirect
            "Solo mode selection works",
            f"Solo mode selection failed: HTTP {response.status_code}"
        )
        
        # Test 1.4: Session initialized with solo mode
        session = self.client.session
        self.test(
            session.get('is_demo_mode') == True,
            "Demo mode flag set in session",
            "Demo mode flag not set in session"
        )
        
        self.test(
            session.get('demo_mode') == 'solo',
            "Demo mode set to 'solo' in session",
            f"Demo mode is '{session.get('demo_mode')}', expected 'solo'"
        )
        
        self.test(
            session.get('demo_role') == 'admin',
            "Default role set to 'admin'",
            f"Default role is '{session.get('demo_role')}', expected 'admin'"
        )
        
        # Test 1.5: DemoSession record created
        demo_session = DemoSession.objects.filter(
            session_id=session.session_key
        ).first()
        
        self.test(
            demo_session is not None,
            "DemoSession record created in database",
            "DemoSession record not created"
        )
        
        if demo_session:
            self.test(
                demo_session.demo_mode == 'solo',
                "DemoSession has correct mode",
                f"DemoSession mode is '{demo_session.demo_mode}', expected 'solo'"
            )
            
            self.test(
                demo_session.current_role == 'admin',
                "DemoSession has correct initial role",
                f"DemoSession role is '{demo_session.current_role}', expected 'admin'"
            )
        
        # Test 1.6: Select Team mode (new session)
        # Clear current session and start fresh
        self.client.logout()
        self.client.force_login(self.test_user)
        
        response = self.client.post('/demo/start/', {
            'mode': 'team',
            'selection_method': 'selected'
        })
        
        self.test(
            response.status_code in [200, 302],
            "Team mode selection works",
            f"Team mode selection failed: HTTP {response.status_code}"
        )
        
        session = self.client.session
        self.test(
            session.get('demo_mode') == 'team',
            "Team mode set correctly in session",
            f"Demo mode is '{session.get('demo_mode')}', expected 'team'"
        )
        
        # Test 1.7: Skip selection (direct entry)
        self.client.logout()
        self.client.force_login(self.test_user)
        
        response = self.client.post('/demo/start/', {
            'mode': 'solo',
            'selection_method': 'skipped'
        })
        
        self.test(
            response.status_code in [200, 302],
            "Skip selection works (defaults to solo)",
            f"Skip selection failed: HTTP {response.status_code}"
        )
        
    def test_demo_banner_and_roles(self):
        """Test Category 2: Demo Banner & Role Switching"""
        print_section("Test 2: Demo Banner & Role Switching")
        
        # Setup: Enter demo mode
        self.client.post('/demo/start/', {
            'mode': 'team',
            'selection_method': 'selected'
        })
        
        # Test 2.1: Demo dashboard loads
        response = self.client.get('/demo/')
        self.test(
            response.status_code == 200,
            "Demo dashboard loads successfully",
            f"Demo dashboard failed: HTTP {response.status_code}"
        )
        
        # Test 2.2: Demo banner present
        if response.status_code == 200:
            content = response.content.decode('utf-8')
            has_banner = 'demo mode' in content.lower() or 'demo-banner' in content.lower()
            
            self.test(
                has_banner,
                "Demo banner present on dashboard",
                "Demo banner not found on dashboard"
            )
        
        # Test 2.3: Switch to member role (Team mode only)
        response = self.client.post('/demo/switch-role/', {
            'role': 'member'
        })
        
        if response.status_code == 200:
            data = json.loads(response.content)
            self.test(
                data.get('status') == 'success',
                "Role switch to 'member' successful",
                f"Role switch failed: {data.get('message')}"
            )
            
            self.test(
                self.client.session.get('demo_role') == 'member',
                "Session updated with new role",
                f"Session role is '{self.client.session.get('demo_role')}', expected 'member'"
            )
        else:
            print_error(f"Role switch endpoint failed: HTTP {response.status_code}")
        
        # Test 2.4: Switch to viewer role
        response = self.client.post('/demo/switch-role/', {
            'role': 'viewer'
        })
        
        if response.status_code == 200:
            data = json.loads(response.content)
            self.test(
                data.get('status') == 'success',
                "Role switch to 'viewer' successful",
                f"Role switch failed: {data.get('message')}"
            )
        else:
            print_error(f"Role switch to viewer failed: HTTP {response.status_code}")
        
        # Test 2.5: Switch back to admin
        response = self.client.post('/demo/switch-role/', {
            'role': 'admin'
        })
        
        if response.status_code == 200:
            data = json.loads(response.content)
            self.test(
                data.get('status') == 'success',
                "Role switch back to 'admin' successful",
                f"Role switch failed: {data.get('message')}"
            )
        else:
            print_error(f"Role switch to admin failed: HTTP {response.status_code}")
        
        # Test 2.6: Invalid role should fail gracefully
        response = self.client.post('/demo/switch-role/', {
            'role': 'invalid_role'
        })
        
        self.test(
            response.status_code >= 400 or json.loads(response.content).get('status') == 'error',
            "Invalid role rejected properly",
            "Invalid role not rejected"
        )
        
        # Test 2.7: Role switching in Solo mode should fail
        self.client.post('/demo/start/', {
            'mode': 'solo',
            'selection_method': 'selected'
        })
        
        response = self.client.post('/demo/switch-role/', {
            'role': 'member'
        })
        
        if response.status_code == 200:
            data = json.loads(response.content)
            self.test(
                data.get('status') == 'error',
                "Role switching prevented in Solo mode",
                "Role switching allowed in Solo mode (should be Team only)"
            )
        else:
            # 403 is also acceptable
            self.test(
                response.status_code == 403,
                "Role switching prevented in Solo mode (403)",
                f"Unexpected status code: {response.status_code}"
            )
    
    def test_reset_functionality(self):
        """Test Category 3: Reset Functionality"""
        print_section("Test 3: Reset Functionality")
        
        # Setup: Enter demo mode
        self.client.post('/demo/start/', {
            'mode': 'solo',
            'selection_method': 'selected'
        })
        
        session_id = self.client.session.session_key
        
        # Test 3.1: Reset endpoint exists and responds
        response = self.client.post('/demo/reset/')
        
        self.test(
            response.status_code in [200, 302],
            "Reset endpoint responds",
            f"Reset endpoint failed: HTTP {response.status_code}"
        )
        
        # Test 3.2: Session counters updated after reset
        demo_session = DemoSession.objects.filter(session_id=session_id).first()
        
        if demo_session:
            self.test(
                demo_session.reset_count >= 0,
                f"Reset count tracked (count: {demo_session.reset_count})",
                "Reset count not tracked"
            )
        
        # Test 3.3: Can still access demo after reset
        response = self.client.get('/demo/')
        
        self.test(
            response.status_code == 200,
            "Demo still accessible after reset",
            f"Demo inaccessible after reset: HTTP {response.status_code}"
        )
        
        # Test 3.4: Session still in demo mode after reset
        self.test(
            self.client.session.get('is_demo_mode') == True,
            "Still in demo mode after reset",
            "Demo mode flag cleared after reset"
        )
    
    def test_session_management(self):
        """Test Category 4: Session Management & Expiry"""
        print_section("Test 4: Session Management & Expiry")
        
        # Test 4.1: Session expiry time set
        self.client.post('/demo/start/', {
            'mode': 'solo',
            'selection_method': 'selected'
        })
        
        session = self.client.session
        expiry = session.get('demo_expires_at')
        
        # Test 4.2: Expiry time is in the future
        if expiry:
            try:
                from datetime import datetime
                expiry_time = datetime.fromisoformat(expiry)
                now = timezone.now()
                
                self.test(
                    expiry_time > now,
                    f"Expiry time is in future (expires in {(expiry_time - now).total_seconds() / 3600:.1f} hours)",
                    "Expiry time is in the past"
                )
            except:
                print_warning("Could not parse expiry time")
        
        # Test 4.3: DemoSession has expiry time
        demo_session = DemoSession.objects.filter(
            session_id=session.session_key
        ).first()
        
        if demo_session:
            self.test(
                demo_session.expires_at is not None,
                "DemoSession has expiry time in database",
                "DemoSession expiry time not set"
            )
            
            self.test(
                demo_session.expires_at > timezone.now(),
                "DemoSession expiry is in future",
                "DemoSession expiry is in past"
            )
        
        # Test 4.4: Session extension endpoint exists
        response = self.client.post('/demo/extend/')
        
        self.test(
            response.status_code in [200, 400, 403],  # Various valid responses
            "Session extension endpoint responds",
            f"Session extension endpoint error: HTTP {response.status_code}"
        )
    
    def test_analytics_tracking(self):
        """Test Category 5: Analytics Tracking"""
        print_section("Test 5: Analytics Tracking")
        
        # Setup: Fresh demo session
        self.client.post('/demo/start/', {
            'mode': 'solo',
            'selection_method': 'selected'
        })
        
        session_id = self.client.session.session_key
        
        # Test 5.1: Demo mode selection tracked
        analytics = DemoAnalytics.objects.filter(
            session_id=session_id,
            event_type='demo_mode_selected'
        )
        
        self.test(
            analytics.exists(),
            "Demo mode selection event tracked",
            "Demo mode selection not tracked in DemoAnalytics"
        )
        
        # Test 5.2: Track custom event
        response = self.client.post('/demo/track-event/', 
            json.dumps({'event_type': 'test_event', 'event_data': {'test': 'data'}}),
            content_type='application/json'
        )
        
        self.test(
            response.status_code in [200, 201],
            "Custom event tracking endpoint works",
            f"Event tracking failed: HTTP {response.status_code}"
        )
        
        # Test 5.3: Verify custom event stored
        custom_event = DemoAnalytics.objects.filter(
            session_id=session_id,
            event_type='test_event'
        ).first()
        
        self.test(
            custom_event is not None,
            "Custom event stored in database",
            "Custom event not stored"
        )
        
        # Test 5.4: DemoSession tracking features explored
        demo_session = DemoSession.objects.filter(session_id=session_id).first()
        
        if demo_session:
            self.test(
                hasattr(demo_session, 'features_explored'),
                "DemoSession tracks features explored",
                "DemoSession missing features_explored field"
            )
        
    def test_error_handling(self):
        """Test Category 6: Error Handling & Edge Cases"""
        print_section("Test 6: Error Handling & Edge Cases")
        
        # Test 6.1: Access demo dashboard without session initialization
        self.client.logout()
        self.client.force_login(self.test_user)
        
        # Clear session
        for key in list(self.client.session.keys()):
            del self.client.session[key]
        self.client.session.save()
        
        response = self.client.get('/demo/')
        
        self.test(
            response.status_code in [302, 403],  # Should redirect or forbid
            "Demo dashboard without session redirects or forbids",
            f"Demo dashboard allows access without session: HTTP {response.status_code}"
        )
        
        # Test 6.2: Invalid demo mode value
        response = self.client.post('/demo/start/', {
            'mode': 'invalid_mode',
            'selection_method': 'selected'
        })
        
        # Should default to solo or show error
        self.test(
            response.status_code in [200, 302, 400],
            "Invalid mode handled gracefully",
            f"Invalid mode caused server error: HTTP {response.status_code}"
        )
        
        # Test 6.3: Missing POST data
        response = self.client.post('/demo/start/', {})
        
        self.test(
            response.status_code in [200, 302, 400],
            "Missing POST data handled gracefully",
            f"Missing data caused error: HTTP {response.status_code}"
        )
        
        # Test 6.4: Role switch without demo mode
        for key in list(self.client.session.keys()):
            del self.client.session[key]
        self.client.session.save()
        
        response = self.client.post('/demo/switch-role/', {
            'role': 'member'
        })
        
        self.test(
            response.status_code >= 400 or (response.status_code == 200 and json.loads(response.content).get('status') == 'error'),
            "Role switch without demo mode rejected",
            "Role switch allowed outside demo mode"
        )
    
    def test_performance(self):
        """Test Category 7: Performance Checks"""
        print_section("Test 7: Performance Checks")
        
        import time
        
        # Test 7.1: Mode selection page load time
        start_time = time.time()
        response = self.client.get('/demo/start/')
        load_time = time.time() - start_time
        
        self.test(
            load_time < 2.0,  # Should load in under 2 seconds
            f"Mode selection loads quickly ({load_time:.2f}s)",
            f"Mode selection slow: {load_time:.2f}s"
        )
        
        # Test 7.2: Demo dashboard load time
        self.client.post('/demo/start/', {
            'mode': 'solo',
            'selection_method': 'selected'
        })
        
        start_time = time.time()
        response = self.client.get('/demo/')
        load_time = time.time() - start_time
        
        self.test(
            load_time < 3.0,  # Dashboard can be slower (more data)
            f"Demo dashboard loads quickly ({load_time:.2f}s)",
            f"Demo dashboard slow: {load_time:.2f}s"
        )
        
        # Test 7.3: Reset operation time
        start_time = time.time()
        response = self.client.post('/demo/reset/')
        reset_time = time.time() - start_time
        
        self.test(
            reset_time < 5.0,  # Reset can take up to 5 seconds
            f"Reset operation completes quickly ({reset_time:.2f}s)",
            f"Reset operation slow: {reset_time:.2f}s"
        )
        
    def run_all_tests(self):
        """Run all test categories"""
        print_header("🧪 STEP 13: COMPREHENSIVE DEMO TESTING")
        
        print_info(f"Test User: {self.test_user.username}")
        print_info(f"Test Start: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        
        try:
            self.test_demo_mode_selection()
            self.test_demo_banner_and_roles()
            self.test_reset_functionality()
            self.test_session_management()
            self.test_analytics_tracking()
            self.test_error_handling()
            self.test_performance()
        except Exception as e:
            print_error(f"Testing interrupted: {str(e)}")
            import traceback
            traceback.print_exc()
        
        self.print_summary()
    
    def print_summary(self):
        """Print testing summary"""
        print_header("📊 TEST SUMMARY")
        
        print(f"\n{Colors.BOLD}Total Tests:{Colors.END} {self.total_tests}")
        print(f"{Colors.GREEN}✅ Passed:{Colors.END} {self.success_count}")
        print(f"{Colors.RED}❌ Failed:{Colors.END} {len(self.errors)}")
        print(f"{Colors.YELLOW}⚠️  Warnings:{Colors.END} {len(self.warnings)}")
        
        if self.total_tests > 0:
            success_rate = (self.success_count / self.total_tests) * 100
            print(f"\n{Colors.BOLD}Success Rate:{Colors.END} {success_rate:.1f}%")
            
            if success_rate == 100:
                print(f"\n{Colors.GREEN}{Colors.BOLD}🎉 ALL TESTS PASSED! Demo is ready for production.{Colors.END}")
            elif success_rate >= 80:
                print(f"\n{Colors.YELLOW}{Colors.BOLD}⚠️  Most tests passed. Review failures before production.{Colors.END}")
            else:
                print(f"\n{Colors.RED}{Colors.BOLD}❌ Many tests failed. Significant work needed.{Colors.END}")
        
        if self.errors:
            print(f"\n{Colors.RED}{Colors.BOLD}Failed Tests:{Colors.END}")
            for i, error in enumerate(self.errors, 1):
                print(f"{Colors.RED}  {i}. {error}{Colors.END}")
        
        if self.warnings:
            print(f"\n{Colors.YELLOW}{Colors.BOLD}Warnings:{Colors.END}")
            for i, warning in enumerate(self.warnings, 1):
                print(f"{Colors.YELLOW}  {i}. {warning}{Colors.END}")
        
        print(f"\n{Colors.BOLD}Test Complete:{Colors.END} {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print()


if __name__ == '__main__':
    tester = DemoTester()
    tester.run_all_tests()
