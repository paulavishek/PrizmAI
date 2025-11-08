"""
Quick API Test Script
Tests the PrizmAI API endpoints
"""
import requests
import json

BASE_URL = "http://127.0.0.1:8000/api/v1"

# Test 1: API Status (without authentication)
print("=" * 60)
print("TEST 1: API Status Check")
print("=" * 60)

try:
    response = requests.get(f"{BASE_URL}/status/", timeout=5)
    print(f"Status Code: {response.status_code}")
    if response.status_code == 200:
        print("✅ API is up and running!")
        print(json.dumps(response.json(), indent=2))
    else:
        print(f"❌ Unexpected status code: {response.status_code}")
except Exception as e:
    print(f"❌ Error: {e}")

print("\n" + "=" * 60)
print("TEST 2: List Boards (requires authentication)")
print("=" * 60)

# Note: This will return 401 without a token
try:
    response = requests.get(f"{BASE_URL}/boards/", timeout=5)
    print(f"Status Code: {response.status_code}")
    if response.status_code == 401:
        print("✅ Authentication required (as expected)")
        print(json.dumps(response.json(), indent=2))
    elif response.status_code == 200:
        print("✅ Boards retrieved successfully")
        print(json.dumps(response.json(), indent=2))
except Exception as e:
    print(f"❌ Error: {e}")

print("\n" + "=" * 60)
print("TEST 3: List Tasks (requires authentication)")
print("=" * 60)

try:
    response = requests.get(f"{BASE_URL}/tasks/", timeout=5)
    print(f"Status Code: {response.status_code}")
    if response.status_code == 401:
        print("✅ Authentication required (as expected)")
        print(json.dumps(response.json(), indent=2))
    elif response.status_code == 200:
        print("✅ Tasks retrieved successfully")
        print(json.dumps(response.json(), indent=2))
except Exception as e:
    print(f"❌ Error: {e}")

print("\n" + "=" * 60)
print("API TESTS COMPLETED")
print("=" * 60)
print("\nTo test with authentication:")
print("1. Create a user account")
print("2. Create an API token:")
print("   python manage.py create_api_token <username> 'Test Token' --scopes '*'")
print("3. Use the token in requests:")
print("   headers = {'Authorization': 'Bearer <your_token>'}")
print("   requests.get(f'{BASE_URL}/boards/', headers=headers)")
