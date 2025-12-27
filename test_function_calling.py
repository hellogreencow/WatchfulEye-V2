#!/usr/bin/env python3
"""
Comprehensive test script for the new function calling architecture
"""
import requests
import json
import time
import sys
import os

# Add the current directory to Python path for imports
sys.path.insert(0, os.path.dirname(__file__))

BASE_URL = "http://localhost:5002"

def test_helper_functions():
    """Test the helper functions directly"""
    print("🧪 Testing Helper Functions")

    try:
        import web_app

        # Test execute_search_web
        print("   Testing execute_search_web...")
        result = web_app.execute_search_web("test query")
        assert result == {'enabled': True, 'query': 'test query'}
        print("   ✅ execute_search_web works")

        # Test execute_search_rag (basic smoke test)
        print("   Testing execute_search_rag...")
        sources, context = web_app.execute_search_rag("test query", limit=1)
        assert isinstance(sources, list)
        assert isinstance(context, str)
        print(f"   ✅ execute_search_rag works (returned {len(sources)} sources, {len(context)} chars)")

        # Test TOOL_DEFINITIONS
        print("   Testing TOOL_DEFINITIONS...")
        assert len(web_app.TOOL_DEFINITIONS) == 1
        assert web_app.TOOL_DEFINITIONS[0]['function']['name'] == 'search_rag'
        print("   ✅ TOOL_DEFINITIONS correct (only search_rag)")

        return True

    except Exception as e:
        print(f"   ❌ Helper function test failed: {e}")
        return False

def test_scenario(name, query, use_search=False, expected_tools=None, expected_model=None):
    print(f"\n🧪 Testing: {name}")
    print(f"   Query: '{query}'")
    print(f"   Web Search: {'ON' if use_search else 'OFF'}")

    start_time = time.time()

    try:
        response = requests.post(
            f"{BASE_URL}/api/chat/conversations",
            json={"title": f"Test: {name}"},
            headers={"Content-Type": "application/json"},
            timeout=10
        )

        if response.status_code != 200:
            print(f"❌ Failed to create conversation: {response.status_code}")
            return False

        conversation = response.json()
        conversation_id = conversation['id']

        # Send message
        message_data = {
            "content": query,
            "use_rag": True,
            "use_search": use_search,
            "angle": "neutral",
            "horizon": "medium"
        }

        response = requests.post(
            f"{BASE_URL}/api/chat/conversations/{conversation_id}/messages/stream",
            json=message_data,
            headers={"Content-Type": "application/json"},
            timeout=30,
            stream=True
        )

        if response.status_code != 200:
            print(f"❌ Message failed: {response.status_code} - {response.text}")
            return False

        # Collect streaming response
        full_response = ""
        tools_used = []
        model_used = ""
        sources_count = 0

        for line in response.iter_lines():
            if line:
                line = line.decode('utf-8')
                if line.startswith('data: '):
                    data = line[6:]
                    if data == '[DONE]':
                        break
                    try:
                        chunk = json.loads(data)
                        if chunk.get('type') == 'chunk':
                            full_response += chunk.get('content', '')
                        elif chunk.get('type') == 'sources':
                            sources_count = len(chunk.get('sources', []))
                        elif chunk.get('type') == 'complete':
                            metadata = chunk.get('metadata', {})
                            tools_used = metadata.get('tools_used', [])
                            model_used = metadata.get('model_used', '')
                    except:
                        pass

        elapsed = time.time() - start_time

        # Analyze results
        print(".2f")
        print(f"   Tools used: {tools_used}")
        print(f"   Model: {model_used}")
        print(f"   Sources: {sources_count}")
        print(f"   Response preview: {full_response[:100]}...")

        # Validate expectations
        success = True

        if expected_tools is not None:
            if set(tools_used) != set(expected_tools):
                print(f"❌ Expected tools {expected_tools}, got {tools_used}")
                success = False
            else:
                print("✅ Tools match expected")

        if expected_model and expected_model not in model_used:
            print(f"❌ Expected model containing '{expected_model}', got '{model_used}'")
            success = False
        elif expected_model:
            print("✅ Model matches expected")

        if success:
            print("✅ Test PASSED")
        else:
            print("❌ Test FAILED")

        return success

    except Exception as e:
        print(f"❌ Exception: {e}")
        return False

def manual_api_test():
    """Manual test of the API logic (requires authentication)"""
    print("\n🔍 MANUAL API TEST (requires authentication)")
    print("   To test fully, you need to:")
    print("   1. Log in to the web interface")
    print("   2. Get a session cookie")
    print("   3. Test the chat endpoints")
    print("   4. Check server logs for tool decisions")

    # Check if we can at least reach the health endpoint
    try:
        response = requests.get(f"{BASE_URL}/api/health", timeout=5)
        if response.status_code == 200:
            print("   ✅ API server is running and healthy")
            return True
        else:
            print(f"   ❌ API health check failed: {response.status_code}")
            return False
    except Exception as e:
        print(f"   ❌ Cannot reach API: {e}")
        return False

def main():
    print("🚀 COMPREHENSIVE FUNCTION CALLING TESTS")
    print("=" * 50)

    # Test 1: Helper functions
    helper_passed = test_helper_functions()

    # Test 2: API availability
    api_passed = manual_api_test()

    print("\n" + "=" * 50)
    print("📊 TEST RESULTS")

    if helper_passed and api_passed:
        print("✅ CORE COMPONENTS WORKING")
        print("\n📋 MANUAL TESTING REQUIRED:")
        print("   1. Start the frontend: cd frontend && npm start")
        print("   2. Log in and test chat with web search ON/OFF")
        print("   3. Check server logs for '[CHAT] Tool decision' messages")
        print("   4. Verify responses are appropriate for each query type")
        print("\n🎯 EXPECTED BEHAVIORS:")
        print("   • 'hello' → No tools, instant response")
        print("   • 'ethereum price?' → Web ON = Perplexity (web search), Web OFF = Claude (no web search)")
        print("   • 'FTX history?' → search_rag tool (both models)")
        print("   • Web ON → Perplexity with web search, Web OFF → Claude without web search")
        return 0
    else:
        print("❌ CORE COMPONENTS FAILED")
        return 1

if __name__ == "__main__":
    sys.exit(main())
