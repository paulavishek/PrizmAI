#!/usr/bin/env python
"""
Risk Management Integration Verification Script

This script verifies that all risk management features are properly installed
and configured in your PrizmAI application.
"""

import os
import sys
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'kanban_board.settings')
django.setup()

from django.conf import settings
from django.db import connection
from kanban.models import Task, Board
from kanban.utils.ai_utils import (
    calculate_task_risk_score,
    generate_risk_mitigation_suggestions,
    assess_task_dependencies_and_risks
)

class Colors:
    GREEN = '\033[92m'
    RED = '\033[91m'
    YELLOW = '\033[93m'
    BLUE = '\033[94m'
    END = '\033[0m'

def print_header(text):
    print(f"\n{Colors.BLUE}{'='*60}{Colors.END}")
    print(f"{Colors.BLUE}{text.center(60)}{Colors.END}")
    print(f"{Colors.BLUE}{'='*60}{Colors.END}\n")

def check_mark():
    return f"{Colors.GREEN}✅{Colors.END}"

def cross_mark():
    return f"{Colors.RED}❌{Colors.END}"

def warning_mark():
    return f"{Colors.YELLOW}⚠️{Colors.END}"

def verify_model_fields():
    """Verify that all risk-related fields exist in the Task model"""
    print_header("1. Verifying Task Model Fields")
    
    required_fields = [
        'risk_likelihood',
        'risk_impact',
        'risk_score',
        'risk_level',
        'risk_indicators',
        'mitigation_suggestions',
        'risk_analysis',
        'last_risk_assessment'
    ]
    
    task_fields = [f.name for f in Task._meta.get_fields()]
    all_present = True
    
    for field in required_fields:
        if field in task_fields:
            print(f"  {check_mark()} Field '{field}' exists")
        else:
            print(f"  {cross_mark()} Field '{field}' is MISSING")
            all_present = False
    
    return all_present

def verify_database_tables():
    """Verify that database tables are properly created"""
    print_header("2. Verifying Database Tables")
    
    with connection.cursor() as cursor:
        try:
            cursor.execute("SELECT 1 FROM kanban_task LIMIT 1")
            print(f"  {check_mark()} kanban_task table exists")
            return True
        except Exception as e:
            print(f"  {cross_mark()} Error checking kanban_task table: {e}")
            return False

def verify_api_functions():
    """Verify that AI utility functions are available"""
    print_header("3. Verifying AI Utility Functions")
    
    functions = [
        ('calculate_task_risk_score', calculate_task_risk_score),
        ('generate_risk_mitigation_suggestions', generate_risk_mitigation_suggestions),
        ('assess_task_dependencies_and_risks', assess_task_dependencies_and_risks)
    ]
    
    all_available = True
    for func_name, func in functions:
        if callable(func):
            print(f"  {check_mark()} Function '{func_name}' is available")
        else:
            print(f"  {cross_mark()} Function '{func_name}' is NOT available")
            all_available = False
    
    return all_available

def verify_gemini_api():
    """Verify Gemini API configuration"""
    print_header("4. Verifying Gemini API Configuration")
    
    gemini_key = getattr(settings, 'GEMINI_API_KEY', None)
    
    if gemini_key:
        print(f"  {check_mark()} GEMINI_API_KEY is configured")
        if len(gemini_key) > 10:
            masked_key = gemini_key[:7] + '*' * (len(gemini_key) - 14) + gemini_key[-7:]
            print(f"         Key: {masked_key}")
        return True
    else:
        print(f"  {cross_mark()} GEMINI_API_KEY is NOT configured")
        print(f"         Add to Django settings: GEMINI_API_KEY = 'your-key-here'")
        return False

def verify_urls():
    """Verify that risk management URLs are registered"""
    print_header("5. Verifying URL Routes")
    
    from django.urls import reverse
    
    routes = [
        ('calculate_task_risk_api', 'API: Calculate Task Risk'),
        ('get_mitigation_suggestions_api', 'API: Get Mitigation Suggestions'),
        ('assess_task_dependencies_api', 'API: Assess Task Dependencies')
    ]
    
    all_exist = True
    for route_name, description in routes:
        try:
            url = reverse(route_name)
            print(f"  {check_mark()} {description}")
            print(f"         Route: {url}")
        except Exception as e:
            print(f"  {cross_mark()} {description} - NOT FOUND")
            all_exist = False
    
    return all_exist

def verify_static_files():
    """Verify that static JavaScript files exist"""
    print_header("6. Verifying Static Files")
    
    js_file = 'static/js/risk_management.js'
    if os.path.exists(js_file):
        print(f"  {check_mark()} {js_file} exists")
        # Check file size
        size = os.path.getsize(js_file)
        print(f"         Size: {size} bytes")
        return True
    else:
        print(f"  {cross_mark()} {js_file} NOT FOUND")
        return False

def test_ai_functionality():
    """Test basic AI functionality"""
    print_header("7. Testing AI Functionality")
    
    print(f"  {warning_mark()} Testing with sample task...")
    
    try:
        test_result = calculate_task_risk_score(
            task_title="Sample Task",
            task_description="This is a test task to verify AI functionality is working.",
            task_priority="medium",
            board_context="Test Board"
        )
        
        if test_result and 'likelihood' in test_result:
            print(f"  {check_mark()} AI Risk Scoring is functional")
            print(f"         Likelihood Score: {test_result['likelihood']['score']}/3")
            print(f"         Impact Score: {test_result['impact']['score']}/3")
            print(f"         Risk Level: {test_result['risk_assessment']['risk_level']}")
            return True
        else:
            print(f"  {warning_mark()} AI returned unexpected format")
            return False
            
    except Exception as e:
        print(f"  {cross_mark()} AI Test Failed: {str(e)}")
        print(f"         Verify GEMINI_API_KEY is valid")
        return False

def verify_documentation():
    """Verify that documentation files exist"""
    print_header("8. Verifying Documentation")
    
    docs = [
        ('RISK_MANAGEMENT_INTEGRATION.md', 'Risk Management Integration Guide'),
        ('RISK_MANAGEMENT_EXAMPLES.py', 'Risk Management Examples')
    ]
    
    all_exist = True
    for doc_file, description in docs:
        if os.path.exists(doc_file):
            print(f"  {check_mark()} {description}")
            print(f"         File: {doc_file}")
        else:
            print(f"  {warning_mark()} {description} NOT FOUND")
            all_exist = False
    
    return all_exist

def generate_summary(results):
    """Generate summary report"""
    print_header("Summary Report")
    
    checks = [
        ('Model Fields', results['model_fields']),
        ('Database Tables', results['db_tables']),
        ('API Functions', results['api_functions']),
        ('Gemini API Config', results['gemini_api']),
        ('URL Routes', results['urls']),
        ('Static Files', results['static_files']),
        ('AI Functionality', results['ai_test']),
        ('Documentation', results['docs'])
    ]
    
    passed = sum(1 for _, result in checks if result)
    total = len(checks)
    
    print(f"Checks Passed: {passed}/{total}\n")
    
    for check_name, result in checks:
        status = f"{check_mark()} PASS" if result else f"{cross_mark()} FAIL"
        print(f"  {status:20} - {check_name}")
    
    print(f"\n{Colors.YELLOW}{'='*60}{Colors.END}")
    
    if passed == total:
        print(f"{Colors.GREEN}✅ All checks passed! Risk management is ready to use.{Colors.END}")
        return True
    elif passed >= total - 1:
        print(f"{Colors.YELLOW}⚠️  Most checks passed. Review any failures above.{Colors.END}")
        return True
    else:
        print(f"{Colors.RED}❌ Several checks failed. Review configuration above.{Colors.END}")
        return False

def main():
    """Main verification routine"""
    print(f"\n{Colors.BLUE}🛡️  PrizmAI Risk Management Integration Verification{Colors.END}\n")
    
    results = {
        'model_fields': verify_model_fields(),
        'db_tables': verify_database_tables(),
        'api_functions': verify_api_functions(),
        'gemini_api': verify_gemini_api(),
        'urls': verify_urls(),
        'static_files': verify_static_files(),
        'docs': verify_documentation(),
    }
    
    # Only test AI if Gemini API is configured
    if results['gemini_api']:
        results['ai_test'] = test_ai_functionality()
    else:
        results['ai_test'] = False
        print_header("7. Testing AI Functionality")
        print(f"  {cross_mark()} Skipped (Gemini API not configured)")
    
    success = generate_summary(results)
    
    print(f"\n{Colors.BLUE}Quick Start:{Colors.END}")
    print("""
  1. Open any task in your Kanban board
  2. Click the "Assess Risk" button (🛡️)
  3. AI will analyze and provide risk assessment
  4. Click "Get Mitigation Strategies" for recommendations
  5. View risk indicators on task cards
    """)
    
    if not results['gemini_api']:
        print(f"\n{Colors.YELLOW}⚠️  To enable AI features, configure your GEMINI_API_KEY:{Colors.END}")
        print("""
  1. Get API key from: https://makersuite.google.com/app/apikey
  2. Add to Django settings.py:
     GEMINI_API_KEY = 'your-api-key-here'
  3. Or set environment variable:
     export GEMINI_API_KEY='your-api-key-here'
        """)
    
    sys.exit(0 if success else 1)

if __name__ == '__main__':
    main()
