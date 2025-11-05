"""
Google Custom Search API Diagnostic Tool

This script helps diagnose issues with Google Custom Search API setup.
It will test your API credentials and provide specific troubleshooting steps.
"""

import os
import sys
import requests
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

def test_google_search_api():
    """Test Google Custom Search API credentials"""
    
    print("=" * 80)
    print("GOOGLE CUSTOM SEARCH API DIAGNOSTIC")
    print("=" * 80)
    
    # Get credentials from environment
    api_key = os.getenv('GOOGLE_SEARCH_API_KEY', '')
    search_engine_id = os.getenv('GOOGLE_SEARCH_ENGINE_ID', '')
    
    print("\n1. CHECKING CREDENTIALS")
    print("-" * 80)
    
    if not api_key:
        print("❌ GOOGLE_SEARCH_API_KEY is NOT set in .env file")
        print("\nTo fix:")
        print("  1. Go to: https://console.cloud.google.com/apis/credentials")
        print("  2. Create or select an API key")
        print("  3. Add it to .env file: GOOGLE_SEARCH_API_KEY=your-key-here")
        return
    else:
        print(f"✓ API Key found: {api_key[:20]}...{api_key[-4:]}")
    
    if not search_engine_id:
        print("❌ GOOGLE_SEARCH_ENGINE_ID is NOT set in .env file")
        print("\nTo fix:")
        print("  1. Go to: https://programmablesearchengine.google.com/")
        print("  2. Create a search engine or get existing ID")
        print("  3. Add it to .env file: GOOGLE_SEARCH_ENGINE_ID=your-id-here")
        return
    else:
        print(f"✓ Search Engine ID found: {search_engine_id}")
    
    # Test API request
    print("\n2. TESTING API REQUEST")
    print("-" * 80)
    
    test_query = "project management best practices"
    
    params = {
        'key': api_key,
        'cx': search_engine_id,
        'q': test_query,
        'num': 3,
    }
    
    try:
        print(f"Testing search for: '{test_query}'")
        response = requests.get(
            'https://www.googleapis.com/customsearch/v1',
            params=params,
            timeout=10
        )
        
        print(f"Response status code: {response.status_code}")
        
        if response.status_code == 200:
            print("\n✅ SUCCESS! Google Search API is working correctly.")
            
            data = response.json()
            if 'items' in data:
                print(f"\nFound {len(data['items'])} results:")
                for i, item in enumerate(data['items'][:3], 1):
                    print(f"\n{i}. {item.get('title', 'No title')}")
                    print(f"   URL: {item.get('link', 'No link')}")
                    print(f"   Snippet: {item.get('snippet', 'No snippet')[:100]}...")
            else:
                print("\n⚠ Warning: API returned success but no results found.")
                print("This might be due to search engine configuration.")
        
        elif response.status_code == 403:
            print("\n❌ ERROR 403: FORBIDDEN")
            print("\nThis error means the API request is not authorized. Possible causes:")
            print("\n1. API KEY RESTRICTIONS:")
            print("   - Go to: https://console.cloud.google.com/apis/credentials")
            print("   - Select your API key")
            print("   - Check 'API restrictions' section")
            print("   - Ensure 'Custom Search API' is allowed")
            print("   - Remove or adjust IP/domain restrictions if any")
            
            print("\n2. CUSTOM SEARCH API NOT ENABLED:")
            print("   - Go to: https://console.cloud.google.com/apis/library")
            print("   - Search for 'Custom Search API'")
            print("   - Click 'Enable' if not already enabled")
            
            print("\n3. BILLING NOT SET UP:")
            print("   - Go to: https://console.cloud.google.com/billing")
            print("   - Ensure billing is enabled for your project")
            print("   - Note: First 100 queries/day are FREE")
            
            print("\n4. INVALID API KEY:")
            print("   - The API key might be incorrect or revoked")
            print("   - Try creating a new API key")
            
            # Try to get more details from response
            try:
                error_data = response.json()
                if 'error' in error_data:
                    print(f"\nAPI Error Details:")
                    print(f"  Message: {error_data['error'].get('message', 'No message')}")
                    print(f"  Reason: {error_data['error'].get('errors', [{}])[0].get('reason', 'Unknown')}")
            except:
                pass
        
        elif response.status_code == 400:
            print("\n❌ ERROR 400: BAD REQUEST")
            print("\nThis error means the request is invalid. Possible causes:")
            print("\n1. INVALID SEARCH ENGINE ID:")
            print("   - Go to: https://programmablesearchengine.google.com/")
            print("   - Verify your Search Engine ID is correct")
            print("   - Copy the ID from 'Search engine ID' field")
            
            print("\n2. SEARCH ENGINE NOT SET TO 'SEARCH THE ENTIRE WEB':")
            print("   - Edit your search engine")
            print("   - Under 'Sites to search', select 'Search the entire web'")
            print("   - Or add specific sites you want to search")
            
            try:
                error_data = response.json()
                if 'error' in error_data:
                    print(f"\nAPI Error Details:")
                    print(f"  Message: {error_data['error'].get('message', 'No message')}")
            except:
                pass
        
        elif response.status_code == 429:
            print("\n❌ ERROR 429: TOO MANY REQUESTS")
            print("\nYou've exceeded the rate limit.")
            print("  - Free tier: 100 queries per day")
            print("  - Wait 24 hours or upgrade to paid plan")
        
        else:
            print(f"\n❌ UNEXPECTED ERROR: {response.status_code}")
            print(f"Response: {response.text[:500]}")
    
    except requests.exceptions.RequestException as e:
        print(f"\n❌ NETWORK ERROR: {e}")
        print("\nCheck your internet connection.")
    
    except Exception as e:
        print(f"\n❌ UNEXPECTED ERROR: {e}")
    
    print("\n" + "=" * 80)
    print("SUMMARY & NEXT STEPS")
    print("=" * 80)
    
    print("\n📋 CHECKLIST:")
    print("  1. [ ] API Key is set in .env file")
    print("  2. [ ] Search Engine ID is set in .env file")
    print("  3. [ ] Custom Search API is enabled in Google Cloud Console")
    print("  4. [ ] Billing is set up (required even for free tier)")
    print("  5. [ ] No API restrictions preventing access")
    print("  6. [ ] Search engine configured to search entire web")
    
    print("\n💡 WORKAROUND:")
    print("If you can't fix the API issue immediately, the AI Assistant will still work!")
    print("It will use project data and Gemini's built-in knowledge to answer questions.")
    print("Web search (RAG) enhances answers but is not required for functionality.")
    
    print("\n📚 USEFUL LINKS:")
    print("  - API Console: https://console.cloud.google.com/apis/credentials")
    print("  - Search Engine: https://programmablesearchengine.google.com/")
    print("  - Documentation: https://developers.google.com/custom-search/v1/overview")

if __name__ == "__main__":
    test_google_search_api()
