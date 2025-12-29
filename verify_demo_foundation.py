#!/usr/bin/env python
"""
Demo Foundation Verification Script
====================================
Comprehensive verification of all demo components (Steps 1-12)

Usage:
    python verify_demo_foundation.py
    
This script checks:
- Database models and migrations
- Demo organization and personas
- Demo boards and tasks
- Analytics models
- Session management
- All implemented features

Run this before manual testing to ensure foundation is solid.
"""

import os
import sys
import django
from datetime import datetime, timedelta
from collections import defaultdict

# Setup Django environment
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'kanban_board.settings')
django.setup()

from django.contrib.auth.models import User
from django.db import connection
from django.apps import apps


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
    print(f"\n{Colors.BOLD}{Colors.CYAN}{'='*70}{Colors.END}")
    print(f"{Colors.BOLD}{Colors.CYAN}{text:^70}{Colors.END}")
    print(f"{Colors.BOLD}{Colors.CYAN}{'='*70}{Colors.END}\n")


def print_section(text):
    """Print a section divider"""
    print(f"\n{Colors.BOLD}{Colors.BLUE}{text}{Colors.END}")
    print(f"{Colors.BLUE}{'-'*70}{Colors.END}")


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


class DemoVerifier:
    """Main verification class"""
    
    def __init__(self):
        self.errors = []
        self.warnings = []
        self.success_count = 0
        self.total_checks = 0
        
    def check(self, condition, success_msg, error_msg):
        """Perform a check and record result"""
        self.total_checks += 1
        if condition:
            self.success_count += 1
            print_success(success_msg)
            return True
        else:
            self.errors.append(error_msg)
            print_error(error_msg)
            return False
    
    def warn(self, condition, success_msg, warning_msg):
        """Perform a check with warning instead of error"""
        self.total_checks += 1
        if condition:
            self.success_count += 1
            print_success(success_msg)
            return True
        else:
            self.warnings.append(warning_msg)
            print_warning(warning_msg)
            return True  # Don't fail on warnings
    
    def verify_migrations(self):
        """Step 1: Verify all migrations are applied"""
        print_section("Step 1: Verifying Migrations")
        
        try:
            from django.db.migrations.recorder import MigrationRecorder
            recorder = MigrationRecorder(connection)
            applied_migrations = recorder.applied_migrations()
            
            # Check for key migrations
            key_migrations = [
                ('accounts', '0004_organization_is_demo'),
                ('kanban', '0049_board_created_by_session_and_more'),
                ('analytics', '0004_demosession_democonversion_demoanalytics_and_more'),
                ('analytics', '0006_add_nudges_dismissed_field'),
            ]
            
            for app, migration in key_migrations:
                found = any(m[0] == app and migration in m[1] for m in applied_migrations)
                self.check(
                    found,
                    f"Migration {app}.{migration} applied",
                    f"Missing migration: {app}.{migration}"
                )
            
        except Exception as e:
            print_error(f"Error checking migrations: {e}")
            self.errors.append(f"Migration check failed: {e}")
    
    def verify_models(self):
        """Step 2: Verify all required models exist"""
        print_section("Step 2: Verifying Models")
        
        # Check Organization model
        try:
            from accounts.models import Organization
            self.check(
                hasattr(Organization, 'is_demo'),
                "Organization.is_demo field exists",
                "Organization.is_demo field missing"
            )
        except Exception as e:
            print_error(f"Error checking Organization model: {e}")
            self.errors.append(f"Organization model check failed: {e}")
        
        # Check Board model
        try:
            from kanban.models import Board
            self.check(
                hasattr(Board, 'is_official_demo_board'),
                "Board.is_official_demo_board field exists",
                "Board.is_official_demo_board field missing"
            )
            self.check(
                hasattr(Board, 'created_by_session'),
                "Board.created_by_session field exists",
                "Board.created_by_session field missing"
            )
        except Exception as e:
            print_error(f"Error checking Board model: {e}")
            self.errors.append(f"Board model check failed: {e}")
        
        # Check Task model
        try:
            from kanban.models import Task
            self.check(
                hasattr(Task, 'created_by_session'),
                "Task.created_by_session field exists",
                "Task.created_by_session field missing"
            )
        except Exception as e:
            print_error(f"Error checking Task model: {e}")
            self.errors.append(f"Task model check failed: {e}")
        
        # Check Analytics models
        try:
            from analytics.models import DemoSession, DemoAnalytics, DemoConversion
            
            self.check(
                DemoSession is not None,
                "DemoSession model exists",
                "DemoSession model missing"
            )
            self.check(
                DemoAnalytics is not None,
                "DemoAnalytics model exists",
                "DemoAnalytics model missing"
            )
            self.check(
                DemoConversion is not None,
                "DemoConversion model exists",
                "DemoConversion model missing"
            )
            
            # Check DemoSession fields
            required_fields = [
                'session_id', 'demo_mode', 'current_role', 'created_at', 
                'expires_at', 'features_explored', 'aha_moments', 
                'extensions_count', 'nudges_dismissed'
            ]
            for field in required_fields:
                self.check(
                    hasattr(DemoSession, field),
                    f"DemoSession.{field} field exists",
                    f"DemoSession.{field} field missing"
                )
            
        except ImportError as e:
            print_error(f"Error importing analytics models: {e}")
            self.errors.append(f"Analytics models missing: {e}")
    
    def verify_demo_organization(self):
        """Step 4: Verify demo organization exists"""
        print_section("Step 4: Verifying Demo Organization")
        
        try:
            from accounts.models import Organization
            
            demo_orgs = Organization.objects.filter(is_demo=True)
            count = demo_orgs.count()
            
            self.check(
                count > 0,
                f"Demo organization exists (found {count})",
                "No demo organization found"
            )
            
            if count > 0:
                demo_org = demo_orgs.first()
                print_info(f"Demo org: {demo_org.name}")
                print_info(f"Domain: {demo_org.domain}")
                
                # Check if it has members
                member_count = demo_org.members.count()
                self.check(
                    member_count >= 3,
                    f"Demo organization has {member_count} members",
                    f"Demo organization has only {member_count} members (expected 3+)"
                )
            
        except Exception as e:
            print_error(f"Error checking demo organization: {e}")
            self.errors.append(f"Demo organization check failed: {e}")
    
    def verify_demo_personas(self):
        """Step 4: Verify demo personas exist"""
        print_section("Step 4: Verifying Demo Personas")
        
        try:
            expected_personas = [
                ('alex_chen_demo', 'alex.chen@demo.prizmai.local', 'Alex Chen'),
                ('sam_rivera_demo', 'sam.rivera@demo.prizmai.local', 'Sam Rivera'),
                ('jordan_taylor_demo', 'jordan.taylor@demo.prizmai.local', 'Jordan Taylor'),
            ]
            
            for username, email, full_name in expected_personas:
                user_exists = User.objects.filter(
                    username=username,
                    email=email
                ).exists()
                
                self.check(
                    user_exists,
                    f"Persona '{full_name}' exists ({username})",
                    f"Persona '{full_name}' missing ({username})"
                )
                
                if user_exists:
                    user = User.objects.get(username=username)
                    # Check if user has skills (if UserSkill model exists)
                    try:
                        from kanban.models import UserSkill
                        skill_count = UserSkill.objects.filter(user=user).count()
                        print_info(f"  {full_name} has {skill_count} skills")
                    except:
                        pass
            
        except Exception as e:
            print_error(f"Error checking demo personas: {e}")
            self.errors.append(f"Demo personas check failed: {e}")
    
    def verify_demo_boards(self):
        """Step 4: Verify demo boards exist"""
        print_section("Step 4: Verifying Demo Boards")
        
        try:
            from kanban.models import Board
            
            demo_boards = Board.objects.filter(is_official_demo_board=True)
            count = demo_boards.count()
            
            self.check(
                count >= 3,
                f"Demo boards exist (found {count})",
                f"Insufficient demo boards (found {count}, expected 3+)"
            )
            
            if count > 0:
                print_info(f"\nDemo boards:")
                for board in demo_boards:
                    print_info(f"  • {board.name}")
                    
                    # Check board has columns
                    column_count = board.columns.count() if hasattr(board, 'columns') else 0
                    print_info(f"    Columns: {column_count}")
                    
                    # Check board has members
                    member_count = board.members.count() if hasattr(board, 'members') else 0
                    print_info(f"    Members: {member_count}")
            
        except Exception as e:
            print_error(f"Error checking demo boards: {e}")
            self.errors.append(f"Demo boards check failed: {e}")
    
    def verify_demo_tasks(self):
        """Step 5: Verify demo tasks exist"""
        print_section("Step 5: Verifying Demo Tasks")
        
        try:
            from kanban.models import Task, Board
            
            demo_boards = Board.objects.filter(is_official_demo_board=True)
            
            if demo_boards.exists():
                total_tasks = 0
                print_info(f"\nTasks per board:")
                
                for board in demo_boards:
                    # Tasks are related through Column → Task
                    task_count = 0
                    for column in board.columns.all():
                        task_count += column.tasks.count()
                    total_tasks += task_count
                    print_info(f"  • {board.name}: {task_count} tasks")
                
                self.check(
                    total_tasks >= 100,
                    f"Demo tasks exist (found {total_tasks})",
                    f"Insufficient demo tasks (found {total_tasks}, expected 100+)"
                )
                
                # Check task distribution by status
                if total_tasks > 0:
                    print_info(f"\nTask status distribution:")
                    status_counts = defaultdict(int)
                    for board in demo_boards:
                        for column in board.columns.all():
                            for task in column.tasks.all():
                                status = column.name  # Status is the column name
                                status_counts[status] += 1
                    
                    for status, count in status_counts.items():
                        print_info(f"  • {status}: {count}")
            else:
                print_warning("No demo boards found, skipping task verification")
            
        except Exception as e:
            print_error(f"Error checking demo tasks: {e}")
            self.errors.append(f"Demo tasks check failed: {e}")
    
    def verify_demo_views(self):
        """Step 6-12: Verify demo views and URLs exist"""
        print_section("Steps 6-12: Verifying Demo Views & URLs")
        
        try:
            from django.urls import resolve, reverse
            from kanban import demo_views
            
            # Check views exist
            views_to_check = [
                'demo_mode_selection',
                'demo_dashboard',
                'switch_demo_role',
                'reset_demo_data',
                'extend_demo_session',
                'track_demo_event',
                'check_nudge',
                'track_nudge',
            ]
            
            for view_name in views_to_check:
                self.check(
                    hasattr(demo_views, view_name),
                    f"View {view_name}() exists",
                    f"View {view_name}() missing"
                )
            
            # Check URL routes (if they're named)
            urls_to_check = [
                ('demo_mode_selection', '/demo/start/'),
            ]
            
            for url_name, expected_path in urls_to_check:
                try:
                    path = reverse(url_name)
                    self.check(
                        path == expected_path,
                        f"URL route '{url_name}' configured correctly",
                        f"URL route '{url_name}' misconfigured (expected {expected_path}, got {path})"
                    )
                except Exception:
                    print_warning(f"URL route '{url_name}' not found (might use different name)")
            
        except Exception as e:
            print_error(f"Error checking demo views: {e}")
            self.errors.append(f"Demo views check failed: {e}")
    
    def verify_middleware(self):
        """Step 8: Verify middleware is configured"""
        print_section("Step 8: Verifying Middleware")
        
        try:
            from django.conf import settings
            
            middleware_to_check = [
                'kanban.middleware.demo_session.DemoSessionMiddleware',
                'kanban.middleware.demo_session.DemoAnalyticsMiddleware',
            ]
            
            for middleware in middleware_to_check:
                self.warn(
                    middleware in settings.MIDDLEWARE,
                    f"Middleware {middleware.split('.')[-1]} configured",
                    f"Middleware {middleware.split('.')[-1]} not in MIDDLEWARE settings"
                )
            
        except Exception as e:
            print_error(f"Error checking middleware: {e}")
            self.errors.append(f"Middleware check failed: {e}")
    
    def verify_context_processor(self):
        """Step 8: Verify context processor is configured"""
        print_section("Step 8: Verifying Context Processor")
        
        try:
            from django.conf import settings
            
            # Check if context processor is in settings
            templates = settings.TEMPLATES
            if templates:
                context_processors = templates[0].get('OPTIONS', {}).get('context_processors', [])
                
                self.warn(
                    'kanban.context_processors.demo_context' in context_processors,
                    "Context processor demo_context configured",
                    "Context processor demo_context not configured"
                )
            
        except Exception as e:
            print_error(f"Error checking context processor: {e}")
            self.errors.append(f"Context processor check failed: {e}")
    
    def verify_management_commands(self):
        """Verify management commands exist"""
        print_section("Verifying Management Commands")
        
        try:
            from django.core.management import get_commands
            commands = get_commands()
            
            commands_to_check = [
                'create_demo_organization',
                'populate_demo_data',
                'cleanup_demo_sessions',
            ]
            
            for cmd in commands_to_check:
                self.check(
                    cmd in commands,
                    f"Management command '{cmd}' exists",
                    f"Management command '{cmd}' missing"
                )
            
        except Exception as e:
            print_error(f"Error checking management commands: {e}")
            self.errors.append(f"Management commands check failed: {e}")
    
    def verify_templates(self):
        """Verify demo templates exist"""
        print_section("Verifying Templates")
        
        try:
            from django.conf import settings
            import os
            
            # Get template directories
            template_dirs = []
            for template_config in settings.TEMPLATES:
                template_dirs.extend(template_config.get('DIRS', []))
            
            # Add app template directories
            for app_config in apps.get_app_configs():
                app_template_dir = os.path.join(app_config.path, 'templates')
                if os.path.exists(app_template_dir):
                    template_dirs.append(app_template_dir)
            
            templates_to_check = [
                'demo/mode_selection.html',
                'demo/partials/demo_banner.html',
                'demo/partials/expiry_warning.html',
                'demo/partials/aha_moment_celebration.html',
                'demo/nudges/soft.html',
                'demo/nudges/medium.html',
                'demo/nudges/peak.html',
                'demo/nudges/exit_intent.html',
            ]
            
            for template_path in templates_to_check:
                found = False
                for template_dir in template_dirs:
                    full_path = os.path.join(template_dir, template_path)
                    if os.path.exists(full_path):
                        found = True
                        break
                
                self.check(
                    found,
                    f"Template '{template_path}' exists",
                    f"Template '{template_path}' missing"
                )
            
        except Exception as e:
            print_error(f"Error checking templates: {e}")
            self.errors.append(f"Templates check failed: {e}")
    
    def verify_static_files(self):
        """Verify JavaScript files exist"""
        print_section("Verifying Static Files")
        
        try:
            from django.conf import settings
            import os
            
            # Check static directories
            static_dirs = getattr(settings, 'STATICFILES_DIRS', [])
            if hasattr(settings, 'STATIC_ROOT') and settings.STATIC_ROOT:
                static_dirs.append(settings.STATIC_ROOT)
            
            # Add app static directories
            for app_config in apps.get_app_configs():
                app_static_dir = os.path.join(app_config.path, 'static')
                if os.path.exists(app_static_dir):
                    static_dirs.append(app_static_dir)
            
            js_files_to_check = [
                'js/aha_moment_detection.js',
                'js/conversion_nudges.js',
            ]
            
            for js_file in js_files_to_check:
                found = False
                for static_dir in static_dirs:
                    full_path = os.path.join(static_dir, js_file)
                    if os.path.exists(full_path):
                        found = True
                        break
                
                self.warn(
                    found,
                    f"JavaScript file '{js_file}' exists",
                    f"JavaScript file '{js_file}' not found (might be in different location)"
                )
            
        except Exception as e:
            print_error(f"Error checking static files: {e}")
            self.warnings.append(f"Static files check failed: {e}")
    
    def verify_demo_sessions(self):
        """Check existing demo sessions"""
        print_section("Checking Existing Demo Sessions")
        
        try:
            from analytics.models import DemoSession
            
            total_sessions = DemoSession.objects.count()
            active_sessions = DemoSession.objects.filter(
                expires_at__gt=datetime.now()
            ).count()
            expired_sessions = DemoSession.objects.filter(
                expires_at__lte=datetime.now()
            ).count()
            
            print_info(f"Total demo sessions: {total_sessions}")
            print_info(f"Active sessions: {active_sessions}")
            print_info(f"Expired sessions: {expired_sessions}")
            
            if expired_sessions > 0:
                print_warning(
                    f"{expired_sessions} expired sessions found. "
                    f"Run 'python manage.py cleanup_demo_sessions' to clean up."
                )
            
        except Exception as e:
            print_info(f"No demo sessions yet (or error checking): {e}")
    
    def print_summary(self):
        """Print verification summary"""
        print_header("VERIFICATION SUMMARY")
        
        print(f"\n{Colors.BOLD}Total Checks:{Colors.END} {self.total_checks}")
        print(f"{Colors.GREEN}✅ Passed:{Colors.END} {self.success_count}")
        print(f"{Colors.RED}❌ Failed:{Colors.END} {len(self.errors)}")
        print(f"{Colors.YELLOW}⚠️  Warnings:{Colors.END} {len(self.warnings)}")
        
        success_rate = (self.success_count / self.total_checks * 100) if self.total_checks > 0 else 0
        print(f"\n{Colors.BOLD}Success Rate:{Colors.END} {success_rate:.1f}%")
        
        if self.errors:
            print(f"\n{Colors.RED}{Colors.BOLD}ERRORS FOUND:{Colors.END}")
            for i, error in enumerate(self.errors, 1):
                print(f"{Colors.RED}  {i}. {error}{Colors.END}")
        
        if self.warnings:
            print(f"\n{Colors.YELLOW}{Colors.BOLD}WARNINGS:{Colors.END}")
            for i, warning in enumerate(self.warnings, 1):
                print(f"{Colors.YELLOW}  {i}. {warning}{Colors.END}")
        
        if not self.errors:
            print(f"\n{Colors.GREEN}{Colors.BOLD}🎉 ALL CHECKS PASSED! Demo foundation is solid.{Colors.END}")
            print(f"{Colors.GREEN}You can proceed with manual testing.{Colors.END}")
        else:
            print(f"\n{Colors.RED}{Colors.BOLD}⚠️  ISSUES FOUND! Fix errors before testing.{Colors.END}")
        
        print(f"\n{Colors.CYAN}{'='*70}{Colors.END}\n")
    
    def run_all_checks(self):
        """Run all verification checks"""
        print_header("🔍 DEMO FOUNDATION VERIFICATION")
        print(f"{Colors.WHITE}Checking all demo components (Steps 1-12)...{Colors.END}")
        
        self.verify_migrations()
        self.verify_models()
        self.verify_demo_organization()
        self.verify_demo_personas()
        self.verify_demo_boards()
        self.verify_demo_tasks()
        self.verify_demo_views()
        self.verify_middleware()
        self.verify_context_processor()
        self.verify_management_commands()
        self.verify_templates()
        self.verify_static_files()
        self.verify_demo_sessions()
        
        self.print_summary()
        
        return len(self.errors) == 0


def main():
    """Main entry point"""
    verifier = DemoVerifier()
    success = verifier.run_all_checks()
    
    sys.exit(0 if success else 1)


if __name__ == '__main__':
    main()
