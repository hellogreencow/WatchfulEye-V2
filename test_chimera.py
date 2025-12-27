#!/usr/bin/env python3
"""
Test script for Chimera API functionality
"""

import requests
import json

def test_chimera_api():
    """Test the Chimera API endpoints"""
    
    base_url = "http://localhost:5002"
    
    print("Testing Chimera API endpoints...")
    
    # Test 1: Health check
    print("\n1. Testing health endpoint...")
    try:
        response = requests.get(f"{base_url}/api/health")
        print(f"Status: {response.status_code}")
        print(f"Response: {response.json()}")
    except Exception as e:
        print(f"Error: {e}")
    
    # Test 2: Pulse feed
    print("\n2. Testing pulse feed...")
    try:
        response = requests.get(f"{base_url}/api/chimera/pulse?user_id=1&limit=5")
        print(f"Status: {response.status_code}")
        if response.status_code == 200:
            try:
                data = response.json()
                print(f"Response: {json.dumps(data, indent=2)}")
            except:
                print(f"Response (not JSON): {response.text[:200]}...")
        else:
            print(f"Response: {response.text[:200]}...")
    except Exception as e:
        print(f"Error: {e}")
    
    # Test 3: Query analysis
    print("\n3. Testing query analysis...")
    try:
        data = {
            "query_text": "What are the latest market trends?",
            "query_type": "market",
            "user_id": 1
        }
        response = requests.post(f"{base_url}/api/chimera/query", json=data)
        print(f"Status: {response.status_code}")
        if response.status_code == 200:
            try:
                data = response.json()
                print(f"Response: {json.dumps(data, indent=2)}")
            except:
                print(f"Response (not JSON): {response.text[:200]}...")
        else:
            print(f"Response: {response.text[:200]}...")
    except Exception as e:
        print(f"Error: {e}")
    
    # Test 4: User interests
    print("\n4. Testing user interests...")
    try:
        response = requests.get(f"{base_url}/api/chimera/interests/1")
        print(f"Status: {response.status_code}")
        if response.status_code == 200:
            try:
                data = response.json()
                print(f"Response: {json.dumps(data, indent=2)}")
            except:
                print(f"Response (not JSON): {response.text[:200]}...")
        else:
            print(f"Response: {response.text[:200]}...")
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    test_chimera_api() 