#!/usr/bin/env python
"""
Demo Testing Script
Creates a test user and tests demo functionality programmatically
"""

import os
import sys
import django
from datetime import datetime

# Setup Django environment
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'kanban_board.settings')
django.setup()

from django.contrib.auth.models import User
from django.test import Client
from django.urls import reverse


def test_demo_functionality():
    """Test demo functionality with a test user"""
    print("🧪 Starting Demo Functionality Test")
    print("=" * 50)
    
    # Create test client
    client = Client()
    
    # Create or get test user
    test_user, created = User.objects.get_or_create(
        username='demo_tester',
        defaults={
            'email': 'demo_tester@test.com',
            'first_name': 'Demo',
            'last_name': 'Tester',
        }
    )
    
    if created:
        test_user.set_password('testpass123')
        test_user.save()
        print(f"✅ Created test user: {test_user.username}")
    else:
        print(f"✅ Using existing test user: {test_user.username}")
    
    # Login test user
    login_success = client.login(username='demo_tester', password='testpass123')
    if login_success:
        print("✅ Successfully logged in test user")
    else:
        print("❌ Failed to login test user")
        return False
    
    # Test 1: Access demo mode selection page
    print("\n🧪 Test 1: Demo Mode Selection Page")
    try:
        response = client.get('/demo/start/')
        print(f"Status: {response.status_code}")
        
        if response.status_code == 200:
            print("✅ Demo mode selection page loads successfully")
            
            # Check if template renders correctly
            if b'Solo Exploration' in response.content or b'Team Mode' in response.content:
                print("✅ Demo mode selection content found")
            else:
                print("⚠️  Demo mode selection content not found in response")
                
        elif response.status_code == 302:
            print(f"🔄 Redirected to: {response.url}")
        else:
            print(f"❌ Unexpected status code: {response.status_code}")
            
    except Exception as e:
        print(f"❌ Error accessing demo selection page: {e}")
        return False
    
    # Test 2: Test Solo mode selection
    print("\n🧪 Test 2: Solo Mode Selection")
    try:
        response = client.post('/demo/start/', {
            'mode': 'solo',
            'selection_method': 'selected'
        })
        
        print(f"Status: {response.status_code}")
        
        if response.status_code == 302:
            print(f"✅ Successfully submitted solo mode, redirected to: {response.url}")
            
            # Check session variables
            session = client.session
            if session.get('is_demo_mode'):
                print("✅ Demo mode session variable set")
            if session.get('demo_mode') == 'solo':
                print("✅ Demo mode set to 'solo'")
            if session.get('demo_role') == 'admin':
                print("✅ Demo role set to 'admin'")
                
        else:
            print(f"❌ Unexpected status code: {response.status_code}")
            
    except Exception as e:
        print(f"❌ Error testing solo mode selection: {e}")
        return False
    
    # Test 3: Access demo dashboard
    print("\n🧪 Test 3: Demo Dashboard Access")
    try:
        response = client.get('/demo/')
        print(f"Status: {response.status_code}")
        
        if response.status_code == 200:
            print("✅ Demo dashboard loads successfully")
            
            # Check for demo boards
            if b'Software Development' in response.content:
                print("✅ Demo boards found in dashboard")
            else:
                print("⚠️  Demo boards not found in dashboard")
                print("Content preview:", response.content[:500].decode('utf-8', 'ignore'))
                
        else:
            print(f"❌ Unexpected status code: {response.status_code}")
            
    except Exception as e:
        print(f"❌ Error accessing demo dashboard: {e}")
        return False
    
    # Test 4: Test Team mode
    print("\n🧪 Test 4: Team Mode Selection")
    try:
        # Reset session
        client.session.flush()
        client.login(username='demo_tester', password='testpass123')
        
        response = client.post('/demo/start/', {
            'mode': 'team',
            'selection_method': 'selected'
        })
        
        print(f"Status: {response.status_code}")
        
        if response.status_code == 302:
            print(f"✅ Successfully submitted team mode, redirected to: {response.url}")
            
            session = client.session
            if session.get('demo_mode') == 'team':
                print("✅ Demo mode set to 'team'")
                
        else:
            print(f"❌ Unexpected status code: {response.status_code}")
            
    except Exception as e:
        print(f"❌ Error testing team mode selection: {e}")
        return False
    
    # Test 5: Analytics tracking
    print("\n🧪 Test 5: Analytics Tracking")
    try:
        from analytics.models import DemoSession, DemoAnalytics
        
        demo_sessions = DemoSession.objects.filter(session_id=client.session.session_key)
        if demo_sessions.exists():
            demo_session = demo_sessions.first()
            print(f"✅ DemoSession created: {demo_session}")
            print(f"   Mode: {demo_session.demo_mode}")
            print(f"   Role: {demo_session.current_role}")
            print(f"   Created: {demo_session.created_at}")
        else:
            print("⚠️  No DemoSession record found")
        
        analytics_events = DemoAnalytics.objects.filter(session_id=client.session.session_key)
        print(f"✅ Analytics events: {analytics_events.count()}")
        
        for event in analytics_events[:3]:  # Show first 3 events
            print(f"   Event: {event.event_type} at {event.timestamp}")
            
    except Exception as e:
        print(f"⚠️  Analytics check failed: {e}")
    
    print("\n🎉 Demo functionality test completed!")
    return True


if __name__ == '__main__':
    success = test_demo_functionality()
    sys.exit(0 if success else 1)