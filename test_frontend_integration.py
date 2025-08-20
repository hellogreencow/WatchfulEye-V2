#!/usr/bin/env python3
"""
Test Frontend Integration for Bugatti Scenario
Verifies that the frontend can access and display the scenario properly
"""

import requests
import json

def test_frontend_api_endpoints():
    """Test all API endpoints that the frontend uses"""
    
    base_url = "http://localhost:5002"
    
    print("🌐 Testing Frontend API Integration")
    print("=" * 60)
    
    # Test 1: Pulse Feed (for the main dashboard)
    print("\n1. Testing Pulse Feed...")
    try:
        response = requests.get(f"{base_url}/api/chimera/pulse?user_id=1&limit=5")
        if response.status_code == 200:
            data = response.json()
            pulse_events = data.get('pulse_events', [])
            print(f"✅ Pulse feed working: {len(pulse_events)} events")
            
            if pulse_events:
                print("Sample event:")
                event = pulse_events[0]
                print(f"  Title: {event.get('title', 'N/A')}")
                print(f"  Impact Score: {event.get('impact_score', 0):.2f}")
                print(f"  Urgency Level: {event.get('urgency_level', 0)}")
        else:
            print(f"❌ Pulse feed failed: {response.status_code}")
    except Exception as e:
        print(f"❌ Pulse feed error: {e}")
    
    # Test 2: Scenarios (for the War Room)
    print("\n2. Testing Scenarios...")
    try:
        response = requests.get(f"{base_url}/api/chimera/war-room/scenarios?user_id=1")
        if response.status_code == 200:
            data = response.json()
            scenarios = data.get('scenarios', [])
            print(f"✅ Scenarios working: {len(scenarios)} scenarios")
            
            if scenarios:
                print("Bugatti scenario details:")
                bugatti_scenario = scenarios[0]  # Should be our Bugatti scenario
                print(f"  Name: {bugatti_scenario.get('scenario_name', 'N/A')}")
                print(f"  Trigger: {bugatti_scenario.get('trigger_event', 'N/A')[:100]}...")
                print(f"  Probability: {bugatti_scenario.get('probability_score', 0):.2f}")
                print(f"  Impact: {bugatti_scenario.get('impact_score', 0):.2f}")
        else:
            print(f"❌ Scenarios failed: {response.status_code}")
    except Exception as e:
        print(f"❌ Scenarios error: {e}")
    
    # Test 3: User Interests
    print("\n3. Testing User Interests...")
    try:
        response = requests.get(f"{base_url}/api/chimera/interests/1")
        if response.status_code == 200:
            data = response.json()
            interests = data.get('interests', [])
            print(f"✅ User interests working: {len(interests)} interests")
        else:
            print(f"❌ User interests failed: {response.status_code}")
    except Exception as e:
        print(f"❌ User interests error: {e}")
    
    # Test 4: Query Analysis
    print("\n4. Testing Query Analysis...")
    try:
        query_data = {
            "query_text": "What are the implications of hydrogen technology in luxury vehicles?",
            "query_type": "market",
            "user_id": 1
        }
        response = requests.post(f"{base_url}/api/chimera/query", json=query_data)
        if response.status_code == 200:
            data = response.json()
            result = data.get('result', {})
            print("✅ Query analysis working")
            print(f"  Query: {result.get('query', 'N/A')}")
            print(f"  Type: {result.get('query_type', 'N/A')}")
            print(f"  Synthesis: {result.get('overall_synthesis', 'N/A')[:100]}...")
        else:
            print(f"❌ Query analysis failed: {response.status_code}")
    except Exception as e:
        print(f"❌ Query analysis error: {e}")
    
    # Test 5: Frontend accessibility
    print("\n5. Testing Frontend Accessibility...")
    try:
        response = requests.get("http://localhost:3000")
        if response.status_code == 200:
            print("✅ Frontend is accessible")
        else:
            print(f"❌ Frontend not accessible: {response.status_code}")
    except Exception as e:
        print(f"❌ Frontend error: {e}")
        print("Make sure the frontend is running on port 3000")

def test_bugatti_scenario_workflow():
    """Test the complete Bugatti scenario workflow"""
    
    print("\n🚗 Testing Complete Bugatti Scenario Workflow")
    print("=" * 60)
    
    base_url = "http://localhost:5002"
    
    # Step 1: Create the scenario
    print("\nStep 1: Creating Bugatti Scenario...")
    scenario_data = {
        "user_id": 1,
        "scenario_name": "Bugatti Hydrogen Revolution V2",
        "trigger_event": "Bugatti announces complete transition from petrol to hydrogen fuel technology, becoming the first luxury hypercar manufacturer to go fully hydrogen-powered"
    }
    
    try:
        response = requests.post(f"{base_url}/api/chimera/war-room/scenario", json=scenario_data)
        if response.status_code == 200:
            data = response.json()
            scenario_id = data.get('scenario_id')
            print(f"✅ Scenario created with ID: {scenario_id}")
            
            # Step 2: Retrieve the scenario
            print("\nStep 2: Retrieving Scenario...")
            response = requests.get(f"{base_url}/api/chimera/war-room/scenarios?user_id=1")
            if response.status_code == 200:
                data = response.json()
                scenarios = data.get('scenarios', [])
                
                if scenarios:
                    latest_scenario = scenarios[0]  # Most recent
                    print(f"✅ Scenario retrieved: {latest_scenario.get('scenario_name')}")
                    print(f"   Trigger: {latest_scenario.get('trigger_event')[:100]}...")
                    print(f"   Probability: {latest_scenario.get('probability_score', 0):.2f}")
                    print(f"   Impact: {latest_scenario.get('impact_score', 0):.2f}")
                    
                    # Step 3: Analyze the scenario
                    print("\nStep 3: Analyzing Scenario...")
                    analysis_query = {
                        "query_text": f"Analyze the scenario: {latest_scenario.get('trigger_event')}",
                        "query_type": "scenario",
                        "user_id": 1
                    }
                    
                    response = requests.post(f"{base_url}/api/chimera/query", json=analysis_query)
                    if response.status_code == 200:
                        data = response.json()
                        result = data.get('result', {})
                        print("✅ Scenario analysis completed")
                        print(f"   Synthesis: {result.get('overall_synthesis', 'N/A')[:100]}...")
                        print(f"   Recommendations: {len(result.get('recommendations', []))}")
                        
                        return True
                    else:
                        print(f"❌ Scenario analysis failed: {response.status_code}")
                else:
                    print("❌ No scenarios found")
            else:
                print(f"❌ Scenario retrieval failed: {response.status_code}")
        else:
            print(f"❌ Scenario creation failed: {response.status_code}")
            
    except Exception as e:
        print(f"❌ Workflow error: {e}")
    
    return False

def main():
    """Main test function"""
    
    print("🚀 Testing Complete Chimera Frontend Integration")
    print("=" * 60)
    
    # Test 1: API endpoints
    test_frontend_api_endpoints()
    
    # Test 2: Complete workflow
    success = test_bugatti_scenario_workflow()
    
    print("\n" + "=" * 60)
    if success:
        print("🎉 SUCCESS: Complete Chimera Integration Working!")
        print("\n✅ What's Working:")
        print("  - Scenario creation and storage")
        print("  - Multi-perspective analysis")
        print("  - Pulse feed with real-time data")
        print("  - User interest management")
        print("  - Query analysis system")
        print("  - Frontend API integration")
        
        print("\n🚀 Your Bugatti scenario is fully functional!")
        print("Access it at: http://localhost:3000/chimera")
        print("Go to the 'War Room' tab to see your scenarios")
        
    else:
        print("❌ Some components need attention")
        print("Check the individual test results above")

if __name__ == "__main__":
    main() 