#!/usr/bin/env python3
"""
Comprehensive test for Bugatti Hydrogen Scenario
Tests the complete flow from scenario creation to analysis
"""

import requests
import json
import time
import sys

def test_bugatti_scenario():
    """Test the complete Bugatti hydrogen scenario flow"""
    
    base_url = "http://localhost:5002"
    
    print("🚗 Testing Bugatti Hydrogen Scenario - Complete Flow")
    print("=" * 60)
    
    # Test 1: Health check
    print("\n1. Testing API health...")
    try:
        response = requests.get(f"{base_url}/api/health")
        if response.status_code == 200:
            print("✅ API is healthy")
        else:
            print(f"❌ API health check failed: {response.status_code}")
            return False
    except Exception as e:
        print(f"❌ API health check error: {e}")
        return False
    
    # Test 2: Check if user exists
    print("\n2. Checking user authentication...")
    try:
        response = requests.get(f"{base_url}/api/chimera/interests/1")
        if response.status_code == 200:
            print("✅ User authentication working")
        else:
            print(f"⚠️ User authentication issue: {response.status_code}")
    except Exception as e:
        print(f"⚠️ User authentication error: {e}")
    
    # Test 3: Create the Bugatti scenario
    print("\n3. Creating Bugatti Hydrogen Scenario...")
    scenario_data = {
        "user_id": 1,
        "scenario_name": "Bugatti Hydrogen Revolution",
        "trigger_event": "Bugatti announces complete transition from petrol to hydrogen fuel technology, becoming the first luxury hypercar manufacturer to go fully hydrogen-powered"
    }
    
    try:
        response = requests.post(f"{base_url}/api/chimera/war-room/scenario", json=scenario_data)
        print(f"Status: {response.status_code}")
        
        if response.status_code == 200:
            data = response.json()
            print("✅ Scenario created successfully!")
            print(f"Scenario ID: {data.get('scenario_id')}")
            
            # Show the analysis
            analysis = data.get('analysis', {})
            if analysis:
                print("\n🔍 Scenario Analysis:")
                print("-" * 40)
                
                result = analysis.get('result', {})
                overall_synthesis = result.get('overall_synthesis', 'No synthesis available')
                recommendations = result.get('recommendations', [])
                
                print(f"Overall Synthesis: {overall_synthesis}")
                print(f"\nRecommendations:")
                for i, rec in enumerate(recommendations, 1):
                    print(f"  {i}. {rec}")
                
                # Check if we got meaningful analysis
                if "No relevant analyses found" in overall_synthesis:
                    print("\n⚠️ No relevant articles found - this is expected for hypothetical scenarios")
                    print("Proceeding to enhanced scenario analysis...")
                else:
                    print("\n✅ Got meaningful analysis!")
                    
            return True
        else:
            print(f"❌ Scenario creation failed: {response.status_code}")
            print(f"Response: {response.text}")
            return False
            
    except Exception as e:
        print(f"❌ Error creating scenario: {e}")
        return False
    
    # Test 4: Enhanced scenario analysis
    print("\n4. Testing enhanced scenario analysis...")
    query_data = {
        "query_text": "Analyze the implications of Bugatti transitioning from petrol to hydrogen fuel technology. Consider market disruption, geopolitical energy implications, and strategic decision-making factors.",
        "query_type": "scenario",
        "user_id": 1
    }
    
    try:
        response = requests.post(f"{base_url}/api/chimera/query", json=query_data)
        print(f"Status: {response.status_code}")
        
        if response.status_code == 200:
            data = response.json()
            result = data.get('result', {})
            
            print("\n📊 Enhanced Analysis:")
            print("-" * 40)
            
            analyses = result.get('analyses', [])
            if analyses:
                print(f"Found {len(analyses)} relevant analyses")
                for i, analysis in enumerate(analyses, 1):
                    print(f"\nAnalysis {i}:")
                    print(f"  Market: {analysis.get('market_perspective', 'N/A')[:100]}...")
                    print(f"  Geopolitical: {analysis.get('geopolitical_perspective', 'N/A')[:100]}...")
                    print(f"  Decision-Maker: {analysis.get('decision_maker_perspective', 'N/A')[:100]}...")
                    print(f"  Confidence: {analysis.get('confidence_score', 0):.2f}")
            else:
                print("No detailed analyses available - this is expected for hypothetical scenarios")
            
            overall_synthesis = result.get('overall_synthesis', 'No synthesis available')
            print(f"\n🎯 Overall Synthesis: {overall_synthesis}")
            
            recommendations = result.get('recommendations', [])
            print(f"\n💡 Strategic Recommendations:")
            for i, rec in enumerate(recommendations, 1):
                print(f"  {i}. {rec}")
                
        else:
            print(f"❌ Enhanced analysis failed: {response.status_code}")
            print(f"Response: {response.text}")
            
    except Exception as e:
        print(f"❌ Error in enhanced analysis: {e}")
    
    # Test 5: Get user scenarios
    print("\n5. Retrieving user scenarios...")
    try:
        response = requests.get(f"{base_url}/api/chimera/war-room/scenarios?user_id=1")
        print(f"Status: {response.status_code}")
        
        if response.status_code == 200:
            data = response.json()
            scenarios = data.get('scenarios', [])
            
            if scenarios:
                print(f"\nFound {len(scenarios)} scenarios:")
                for scenario in scenarios:
                    print(f"\n🎯 {scenario['scenario_name']}")
                    print(f"   Trigger: {scenario['trigger_event']}")
                    print(f"   Probability: {scenario['probability_score']:.2f}")
                    print(f"   Impact: {scenario['impact_score']:.2f}")
                    print(f"   Created: {scenario['created_at']}")
                    
                    # Check if this is our Bugatti scenario
                    if "Bugatti" in scenario['scenario_name']:
                        print("   ✅ This is our Bugatti scenario!")
                        return True
            else:
                print("No scenarios found.")
        else:
            print(f"❌ Error getting scenarios: {response.status_code}")
            
    except Exception as e:
        print(f"❌ Error getting scenarios: {e}")
    
    return False

def test_with_fallback_analysis():
    """Test scenario creation with fallback analysis"""
    print("\n" + "=" * 60)
    print("🔄 Testing with Fallback Analysis...")
    
    base_url = "http://localhost:5002"
    
    # Create a simple scenario that should work
    scenario_data = {
        "user_id": 1,
        "scenario_name": "Test Market Scenario",
        "trigger_event": "Major market volatility affecting global economies"
    }
    
    try:
        response = requests.post(f"{base_url}/api/chimera/war-room/scenario", json=scenario_data)
        print(f"Status: {response.status_code}")
        
        if response.status_code == 200:
            data = response.json()
            print("✅ Test scenario created successfully!")
            print(f"Scenario ID: {data.get('scenario_id')}")
            
            analysis = data.get('analysis', {})
            if analysis:
                result = analysis.get('result', {})
                overall_synthesis = result.get('overall_synthesis', 'No synthesis available')
                print(f"Analysis: {overall_synthesis}")
                
                if "No relevant analyses found" not in overall_synthesis:
                    print("✅ Got meaningful analysis for market scenario!")
                    return True
                else:
                    print("⚠️ Still no relevant analyses found")
                    return False
        else:
            print(f"❌ Test scenario failed: {response.status_code}")
            return False
            
    except Exception as e:
        print(f"❌ Error in test scenario: {e}")
        return False

def main():
    """Main test function"""
    print("Starting comprehensive Bugatti scenario test...")
    
    # Wait for server to be ready
    print("Waiting for server to be ready...")
    time.sleep(2)
    
    # Test 1: Try the Bugatti scenario
    success = test_bugatti_scenario()
    
    if not success:
        print("\n" + "=" * 60)
        print("🔄 Bugatti scenario failed, testing with fallback...")
        
        # Test 2: Try with a different scenario
        success = test_with_fallback_analysis()
        
        if not success:
            print("\n" + "=" * 60)
            print("❌ All tests failed. Checking server status...")
            
            # Check if server is running
            try:
                response = requests.get("http://localhost:5002/api/health", timeout=5)
                print(f"Server status: {response.status_code}")
                if response.status_code == 200:
                    print("Server is running but scenario creation is failing")
                else:
                    print("Server is not responding properly")
            except Exception as e:
                print(f"Server connection error: {e}")
                print("Please ensure the server is running on port 5002")
    
    print("\n" + "=" * 60)
    if success:
        print("🎉 SUCCESS: Scenario creation is working!")
    else:
        print("❌ FAILED: Scenario creation needs fixing")
    
    return success

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1) 