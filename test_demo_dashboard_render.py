"""
Check what the demo_dashboard view is actually returning
"""
import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'kanban_board.settings')
django.setup()

from django.test import RequestFactory
from django.contrib.auth.models import User, AnonymousUser
from django.contrib.sessions.middleware import SessionMiddleware
from kanban.demo_views import demo_dashboard

print("\n" + "="*80)
print("SIMULATING DEMO_DASHBOARD VIEW CALL")
print("="*80)

# Create a request factory
factory = RequestFactory()

# Get demo_admin_solo user
demo_admin = User.objects.get(username='demo_admin_solo')

# Create a GET request
request = factory.get('/demo/dashboard/')

# Add session
middleware = SessionMiddleware(lambda x: None)
middleware.process_request(request)
request.session.save()

# Set demo session variables
request.session['is_demo_mode'] = True
request.session['demo_mode'] = 'solo'
request.session['demo_mode_selected'] = True
request.session['demo_role'] = 'admin'
request.session['demo_admin_logged_in'] = True
request.session.save()

# Authenticate as demo_admin_solo
request.user = demo_admin

print(f"\nRequest setup:")
print(f"  User: {request.user.username}")
print(f"  is_demo_mode: {request.session.get('is_demo_mode')}")
print(f"  demo_mode: {request.session.get('demo_mode')}")
print(f"  demo_mode_selected: {request.session.get('demo_mode_selected')}")

# Call the view
print("\nCalling demo_dashboard view...")
response = demo_dashboard(request)

print(f"\nResponse status: {response.status_code}")

# Check context
if hasattr(response, 'context_data'):
    context = response.context_data
    print(f"\nContext variables:")
    print(f"  demo_available: {context.get('demo_available')}")
    print(f"  demo_mode: {context.get('demo_mode')}")
    print(f"  demo_boards count: {len(context.get('demo_boards', []))}")
    
    if context.get('demo_boards'):
        print(f"\nBoards in context:")
        for board_data in context['demo_boards']:
            print(f"  - {board_data['board'].name}")
    else:
        print(f"\n❌ NO BOARDS IN CONTEXT!")
        
    print(f"\n  task_count: {context.get('task_count')}")
    print(f"  completed_count: {context.get('completed_count')}")
    print(f"  message: {context.get('message', 'N/A')}")
else:
    print("\n⚠️  Response has no context_data attribute")
    print("This might be a redirect or a different response type")

# Try to parse the rendered content
try:
    content = response.content.decode('utf-8')
    if 'Demo Environment Not Available' in content:
        print("\n❌ FOUND: 'Demo Environment Not Available' message in content!")
    if 'Demo Boards' in content:
        print("\n✓ FOUND: 'Demo Boards' section in content")
    if 'Software Development' in content:
        print("✓ FOUND: 'Software Development' board in content")
    if 'Bug Tracking' in content:
        print("✓ FOUND: 'Bug Tracking' board in content")
    if 'Marketing Campaign' in content:
        print("✓ FOUND: 'Marketing Campaign' board in content")
        
    # Check for the limitations banner
    if 'Demo Mode Limitations' in content:
        print("✓ FOUND: 'Demo Mode Limitations' banner in content")
        
except Exception as e:
    print(f"\n⚠️  Could not decode response content: {e}")
