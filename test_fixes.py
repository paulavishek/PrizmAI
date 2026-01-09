"""
Quick Test Script for Google Services and AI Summary Fix

Run this after starting the Django server to verify all fixes are working.
"""
import requests
import json

BASE_URL = "http://127.0.0.1:8000"

def test_ai_summary_endpoint():
    """Test the AI summary endpoint"""
    print("\n" + "="*60)
    print("TESTING AI SUMMARY ENDPOINT")
    print("="*60)
    
    # You'll need to be logged in for this to work
    # This test assumes board ID 3 exists (from the screenshot)
    board_id = 3
    url = f"{BASE_URL}/api/summarize-board-analytics/{board_id}/"
    
    try:
        response = requests.get(url, timeout=30)
        print(f"Status Code: {response.status_code}")
        
        if response.status_code == 200:
            data = response.json()
            summary = data.get('summary')
            
            if isinstance(summary, dict):
                print("✅ Received structured JSON response")
                print(f"   Has executive_summary: {'executive_summary' in summary}")
                print(f"   Has key_insights: {'key_insights' in summary}")
                print(f"   Has recommendations: {'process_improvement_recommendations' in summary}")
            elif isinstance(summary, str):
                print("✅ Received string response (legacy format)")
                print(f"   Length: {len(summary)} characters")
            else:
                print(f"❌ Unexpected response type: {type(summary)}")
                
        elif response.status_code == 403:
            print("⚠️  Authentication required - please login first")
        elif response.status_code == 404:
            print("⚠️  Board not found - try a different board_id")
        else:
            print(f"❌ Error: {response.status_code}")
            print(f"   Response: {response.text[:200]}")
            
    except requests.exceptions.RequestException as e:
        print(f"❌ Request failed: {e}")
    except Exception as e:
        print(f"❌ Error: {e}")


def test_oauth_config():
    """Test OAuth configuration"""
    print("\n" + "="*60)
    print("TESTING OAUTH CONFIGURATION")
    print("="*60)
    
    url = f"{BASE_URL}/accounts/google/login/"
    
    try:
        response = requests.get(url, allow_redirects=False, timeout=10)
        print(f"Status Code: {response.status_code}")
        
        if response.status_code in [302, 301]:
            print("✅ OAuth redirect is working")
            print(f"   Redirects to: {response.headers.get('Location', 'Unknown')[:80]}...")
        elif response.status_code == 404:
            print("❌ OAuth endpoint not found - check URL configuration")
        else:
            print(f"⚠️  Unexpected status: {response.status_code}")
            
    except requests.exceptions.RequestException as e:
        print(f"❌ Request failed: {e}")


def main():
    print("\n")
    print("╔" + "═"*58 + "╗")
    print("║" + " "*15 + "GOOGLE SERVICES TEST" + " "*23 + "║")
    print("╚" + "═"*58 + "╝")
    print("\n⚠️  IMPORTANT: Make sure Django server is running!")
    print("   Command: python manage.py runserver\n")
    
    input("Press Enter when server is running...")
    
    test_oauth_config()
    test_ai_summary_endpoint()
    
    print("\n" + "="*60)
    print("TESTING COMPLETE")
    print("="*60)
    print("\n📝 Next Steps:")
    print("   1. If OAuth test failed, configure it in Django admin")
    print("   2. If AI Summary needs authentication, login first")
    print("   3. Test in browser: http://127.0.0.1:8000/boards/3/analytics/")
    print("   4. Click 'Generate AI Summary' button")
    print("\n")


if __name__ == "__main__":
    main()
