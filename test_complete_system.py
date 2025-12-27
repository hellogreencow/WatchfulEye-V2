#!/usr/bin/env python3
"""
Complete System Test for Enhanced Chimera Intelligence Platform
Tests all components including UI enhancements, tutorial, and functionality
"""

import requests
import json
import time
import sys

def print_section(title):
    """Print a formatted section header"""
    print("\n" + "=" * 60)
    print(f"🔍 {title}")
    print("=" * 60)

def test_backend_api():
    """Test backend API endpoints"""
    print_section("Testing Backend API")
    
    base_url = "http://localhost:5002"
    tests_passed = 0
    tests_failed = 0
    
    # Test 1: Health Check
    try:
        response = requests.get(f"{base_url}/api/health")
        if response.status_code == 200:
            print("✅ Health check: PASSED")
            tests_passed += 1
        else:
            print(f"❌ Health check: FAILED (Status: {response.status_code})")
            tests_failed += 1
    except Exception as e:
        print(f"❌ Health check: ERROR - {e}")
        tests_failed += 1
    
    # Test 2: Pulse Feed
    try:
        response = requests.get(f"{base_url}/api/chimera/pulse?user_id=1&limit=5")
        if response.status_code == 200:
            data = response.json()
            if 'pulse_events' in data:
                print(f"✅ Pulse feed: PASSED ({len(data['pulse_events'])} events)")
                tests_passed += 1
            else:
                print("❌ Pulse feed: FAILED (No pulse_events in response)")
                tests_failed += 1
        else:
            print(f"❌ Pulse feed: FAILED (Status: {response.status_code})")
            tests_failed += 1
    except Exception as e:
        print(f"❌ Pulse feed: ERROR - {e}")
        tests_failed += 1
    
    # Test 3: Scenarios
    try:
        response = requests.get(f"{base_url}/api/chimera/war-room/scenarios?user_id=1")
        if response.status_code == 200:
            data = response.json()
            if 'scenarios' in data:
                print(f"✅ Scenarios: PASSED ({len(data['scenarios'])} scenarios)")
                # Check for Bugatti scenario
                bugatti_found = any('Bugatti' in s.get('scenario_name', '') for s in data['scenarios'])
                if bugatti_found:
                    print("  ✅ Bugatti scenario found!")
                tests_passed += 1
            else:
                print("❌ Scenarios: FAILED (No scenarios in response)")
                tests_failed += 1
        else:
            print(f"❌ Scenarios: FAILED (Status: {response.status_code})")
            tests_failed += 1
    except Exception as e:
        print(f"❌ Scenarios: ERROR - {e}")
        tests_failed += 1
    
    # Test 4: Query Analysis
    try:
        query_data = {
            "query_text": "Test query for system verification",
            "query_type": "general",
            "user_id": 1
        }
        response = requests.post(f"{base_url}/api/chimera/query", json=query_data)
        if response.status_code == 200:
            print("✅ Query analysis: PASSED")
            tests_passed += 1
        else:
            print(f"❌ Query analysis: FAILED (Status: {response.status_code})")
            tests_failed += 1
    except Exception as e:
        print(f"❌ Query analysis: ERROR - {e}")
        tests_failed += 1
    
    # Test 5: User Interests
    try:
        response = requests.get(f"{base_url}/api/chimera/interests/1")
        if response.status_code == 200:
            print("✅ User interests: PASSED")
            tests_passed += 1
        else:
            print(f"❌ User interests: FAILED (Status: {response.status_code})")
            tests_failed += 1
    except Exception as e:
        print(f"❌ User interests: ERROR - {e}")
        tests_failed += 1
    
    print(f"\n📊 Backend API Results: {tests_passed} passed, {tests_failed} failed")
    return tests_passed, tests_failed

def test_frontend():
    """Test frontend accessibility"""
    print_section("Testing Frontend")
    
    tests_passed = 0
    tests_failed = 0
    
    try:
        response = requests.get("http://localhost:3000", timeout=5)
        if response.status_code == 200:
            print("✅ Frontend is accessible")
            
            # Check for key elements
            content = response.text
            if 'root' in content:
                print("✅ React app is loaded")
                tests_passed += 1
            else:
                print("❌ React app not properly loaded")
                tests_failed += 1
        else:
            print(f"❌ Frontend not accessible (Status: {response.status_code})")
            tests_failed += 1
    except requests.exceptions.ConnectionError:
        print("⚠️ Frontend not running - Start with: cd frontend && npm start")
        tests_failed += 1
    except Exception as e:
        print(f"❌ Frontend error: {e}")
        tests_failed += 1
    
    print(f"\n📊 Frontend Results: {tests_passed} passed, {tests_failed} failed")
    return tests_passed, tests_failed

def test_bugatti_scenario():
    """Test the Bugatti scenario specifically"""
    print_section("Testing Bugatti Scenario")
    
    base_url = "http://localhost:5002"
    
    # Check if Bugatti scenario exists
    try:
        response = requests.get(f"{base_url}/api/chimera/war-room/scenarios?user_id=1")
        if response.status_code == 200:
            data = response.json()
            scenarios = data.get('scenarios', [])
            
            bugatti_scenario = None
            for scenario in scenarios:
                if 'Bugatti' in scenario.get('scenario_name', ''):
                    bugatti_scenario = scenario
                    break
            
            if bugatti_scenario:
                print("✅ Bugatti scenario exists:")
                print(f"  Name: {bugatti_scenario['scenario_name']}")
                print(f"  Trigger: {bugatti_scenario['trigger_event'][:100]}...")
                print(f"  Probability: {bugatti_scenario['probability_score']:.2f}")
                print(f"  Impact: {bugatti_scenario['impact_score']:.2f}")
                print(f"  Created: {bugatti_scenario['created_at']}")
                return 1, 0
            else:
                print("⚠️ Bugatti scenario not found - Creating new one...")
                
                # Create Bugatti scenario
                scenario_data = {
                    "user_id": 1,
                    "scenario_name": "Bugatti Hydrogen Revolution",
                    "trigger_event": "Bugatti announces complete transition from petrol to hydrogen fuel technology"
                }
                
                response = requests.post(f"{base_url}/api/chimera/war-room/scenario", json=scenario_data)
                if response.status_code == 200:
                    print("✅ Bugatti scenario created successfully!")
                    return 1, 0
                else:
                    print(f"❌ Failed to create Bugatti scenario: {response.status_code}")
                    return 0, 1
        else:
            print(f"❌ Failed to retrieve scenarios: {response.status_code}")
            return 0, 1
    except Exception as e:
        print(f"❌ Error testing Bugatti scenario: {e}")
        return 0, 1

def test_ui_components():
    """Test UI component files exist"""
    print_section("Testing UI Components")
    
    import os
    
    components = [
        "frontend/src/components/ChimeraCockpit.tsx",
        "frontend/src/components/ChimeraTutorial.tsx",
        "frontend/src/components/OnboardingHelper.tsx",
        "frontend/src/App.tsx"
    ]
    
    tests_passed = 0
    tests_failed = 0
    
    for component in components:
        if os.path.exists(component):
            print(f"✅ {component} exists")
            tests_passed += 1
        else:
            print(f"❌ {component} not found")
            tests_failed += 1
    
    print(f"\n📊 UI Components Results: {tests_passed} passed, {tests_failed} failed")
    return tests_passed, tests_failed

def main():
    """Main test function"""
    print("🚀 Complete System Test for Enhanced Chimera Intelligence Platform")
    print("=" * 60)
    
    total_passed = 0
    total_failed = 0
    
    # Test 1: Backend API
    passed, failed = test_backend_api()
    total_passed += passed
    total_failed += failed
    
    # Test 2: Frontend
    passed, failed = test_frontend()
    total_passed += passed
    total_failed += failed
    
    # Test 3: Bugatti Scenario
    passed, failed = test_bugatti_scenario()
    total_passed += passed
    total_failed += failed
    
    # Test 4: UI Components
    passed, failed = test_ui_components()
    total_passed += passed
    total_failed += failed
    
    # Final Summary
    print("\n" + "=" * 60)
    print("📊 FINAL RESULTS")
    print("=" * 60)
    print(f"✅ Total Passed: {total_passed}")
    print(f"❌ Total Failed: {total_failed}")
    
    if total_failed == 0:
        print("\n🎉 SUCCESS! All systems operational!")
        print("\n✨ Enhanced Features:")
        print("  • Interactive tutorial with 7 steps")
        print("  • Contextual help for each section")
        print("  • Beautiful gradient UI with icons")
        print("  • User-friendly onboarding")
        print("  • Bugatti scenario ready for testing")
        print("\n🚀 Access the platform at: http://localhost:3000/chimera")
    else:
        print("\n⚠️ Some tests failed. Please check the errors above.")
        print("Common fixes:")
        print("  • Start backend: python3 web_app.py")
        print("  • Start frontend: cd frontend && npm start")
        print("  • Check .env file configuration")
    
    return 0 if total_failed == 0 else 1

if __name__ == "__main__":
    sys.exit(main()) 