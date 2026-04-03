#!/usr/bin/env python
"""
Test script to verify the invite flow works correctly.
This simulates what happens when a user accesses an invite link.
"""
import requests
import json

BASE_URL = "http://localhost:8003"  # Collaboration service
TOKEN = "1455e240-be5a-4eaa-873d-f149963272cc"  # Valid invite token for playlist 116

print("=" * 60)
print("Testing Collaboration Invite Flow")
print("=" * 60)

# Test 1: GET request to check invite validity (without auth)
print("\n1. Testing GET /api/collab/join/{token}/ (without auth)")
print("-" * 60)
try:
    response = requests.get(f"{BASE_URL}/api/collab/join/{TOKEN}/")
    print(f"Status Code: {response.status_code}")
    print(f"Response: {json.dumps(response.json(), indent=2)}")
except Exception as e:
    print(f"Error: {e}")

# Test 2: POST request to accept invite (without auth - should fail)
print("\n2. Testing POST /api/collab/join/{token}/ (without auth)")
print("-" * 60)
try:
    response = requests.post(f"{BASE_URL}/api/collab/join/{TOKEN}/")
    print(f"Status Code: {response.status_code}")
    try:
        print(f"Response: {json.dumps(response.json(), indent=2)}")
    except:
        print(f"Response: {response.text}")
except Exception as e:
    print(f"Error: {e}")

# Test 3: Check logs for any core service calls
print("\n3. Checking collaboration service logs for core service calls")
print("-" * 60)
print("Run: docker logs spotify_isd_backend-collaboration-1 --tail 50")
print("Look for:")
print("  - 'Core service response status:'")
print("  - 'Playlist name:'")
print("  - 'Attempting to update playlist'")
