"""
Test HubSpot CSP Configuration

This script verifies your CSP settings have all required HubSpot domains.
"""

import os
import django

# Setup Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'kanban_board.settings')
django.setup()

from django.conf import settings

def test_csp_configuration():
    """Test if all required HubSpot domains are in CSP settings."""
    
    print("=" * 70)
    print("HUBSPOT CSP CONFIGURATION TEST")
    print("=" * 70)
    
    # Required domains based on your errors
    required_connect_src = [
        "https://forms-na2.hsforms.com",
        "https://*.hsforms.com",
        "https://*.hsforms.net",
        "https://*.hubspot.com",
        "https://api.hsforms.com",
        "https://js-na2.hsforms.net",
    ]
    
    required_frame_src = [
        "https://forms-na2.hsforms.com",
        "https://*.hsforms.com",
        "https://*.hsforms.net",
        "https://share.hsforms.com",
        "https://js-na2.hsforms.net",
    ]
    
    required_form_action = [
        "https://forms-na2.hsforms.com",
        "https://*.hsforms.com",
        "https://*.hubspot.com",
    ]
    
    # Test CSP_CONNECT_SRC
    print("\n1. Testing CSP_CONNECT_SRC:")
    print("-" * 70)
    connect_src = getattr(settings, 'CSP_CONNECT_SRC', ())
    for domain in required_connect_src:
        if domain in connect_src:
            print(f"   ✅ {domain}")
        else:
            print(f"   ❌ MISSING: {domain}")
    
    # Test CSP_FRAME_SRC
    print("\n2. Testing CSP_FRAME_SRC:")
    print("-" * 70)
    frame_src = getattr(settings, 'CSP_FRAME_SRC', ())
    for domain in required_frame_src:
        if domain in frame_src:
            print(f"   ✅ {domain}")
        else:
            print(f"   ❌ MISSING: {domain}")
    
    # Test CSP_FORM_ACTION
    print("\n3. Testing CSP_FORM_ACTION:")
    print("-" * 70)
    form_action = getattr(settings, 'CSP_FORM_ACTION', ())
    for domain in required_form_action:
        if domain in form_action:
            print(f"   ✅ {domain}")
        else:
            print(f"   ❌ MISSING: {domain}")
    
    # Test HubSpot environment variables
    print("\n4. Testing HubSpot Environment Variables:")
    print("-" * 70)
    hubspot_config = {
        'HUBSPOT_PORTAL_ID': getattr(settings, 'HUBSPOT_PORTAL_ID', ''),
        'HUBSPOT_FORM_ID': getattr(settings, 'HUBSPOT_FORM_ID', ''),
        'HUBSPOT_REGION': getattr(settings, 'HUBSPOT_REGION', ''),
    }
    
    for key, value in hubspot_config.items():
        if value:
            print(f"   ✅ {key}: {value}")
        else:
            print(f"   ❌ {key}: NOT SET")
    
    # Test CSP Report Mode
    print("\n5. Testing CSP Settings:")
    print("-" * 70)
    csp_report_only = getattr(settings, 'CSP_REPORT_ONLY', False)
    print(f"   CSP_REPORT_ONLY: {csp_report_only}")
    if csp_report_only:
        print("   ⚠️  CSP is in REPORT ONLY mode (violations logged but not blocked)")
    else:
        print("   ✅ CSP is in ENFORCEMENT mode (violations will be blocked)")
    
    print("\n" + "=" * 70)
    print("TEST COMPLETE")
    print("=" * 70)
    print("\nNEXT STEPS:")
    print("1. If you see any ❌ MISSING domains, add them to settings.py")
    print("2. Restart Django server: python manage.py runserver")
    print("3. Hard refresh browser: Ctrl+Shift+R (Windows) or Cmd+Shift+R (Mac)")
    print("4. Check console for CSP violations")
    print("\nIf still having issues, check:")
    print("- Is your HubSpot form published and set to 'Public'?")
    print("- Try setting CSP_REPORT_ONLY = True in settings.py to debug")
    print("=" * 70)

if __name__ == '__main__':
    test_csp_configuration()
