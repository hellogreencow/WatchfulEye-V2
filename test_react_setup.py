#!/usr/bin/env python3
"""
Test script to verify React frontend setup
"""

import os
import sys
import subprocess
import json
import time

def test_backend_api():
    """Test if backend API is accessible"""
    print("🔍 Testing backend API...")
    
    try:
        import requests
        response = requests.get('http://localhost:5002/api/health', timeout=5)
        if response.status_code == 200:
            print("✅ Backend API is running on port 5002")
            return True
        else:
            print(f"❌ Backend API returned status {response.status_code}")
            return False
    except Exception as e:
        print(f"❌ Cannot connect to backend API: {e}")
        return False

def test_frontend_files():
    """Test if React frontend files exist"""
    print("\n🔍 Checking React frontend files...")
    
    required_files = [
        'frontend/package.json',
        'frontend/src/Dashboard.tsx',
        'frontend/src/App.tsx',
        'frontend/src/index.css',
        'frontend/tailwind.config.js',
        'frontend/postcss.config.js'
    ]
    
    all_exist = True
    for file in required_files:
        if os.path.exists(file):
            print(f"✅ {file} exists")
        else:
            print(f"❌ {file} is missing")
            all_exist = False
    
    return all_exist

def test_node_modules():
    """Test if node_modules are installed"""
    print("\n🔍 Checking if dependencies are installed...")
    
    if os.path.exists('frontend/node_modules'):
        print("✅ node_modules directory exists")
        
        # Check for specific packages
        packages = ['react', 'recharts', 'tailwindcss', 'framer-motion']
        for package in packages:
            if os.path.exists(f'frontend/node_modules/{package}'):
                print(f"✅ {package} is installed")
            else:
                print(f"❌ {package} is not installed")
                return False
        return True
    else:
        print("❌ node_modules directory not found - run 'npm install' in frontend/")
        return False

def test_env_file():
    """Test if .env file exists in frontend"""
    print("\n🔍 Checking environment configuration...")
    
    if os.path.exists('frontend/.env'):
        print("✅ frontend/.env file exists")
        return True
    else:
        print("❌ frontend/.env file not found")
        print("   Run: echo 'REACT_APP_API_URL=http://localhost:5002' > frontend/.env")
        return False

def main():
    print("🚀 DiatomsAI React Frontend Setup Test")
    print("=====================================\n")
    
    tests = [
        ("Frontend files", test_frontend_files),
        ("Node modules", test_node_modules),
        ("Environment file", test_env_file),
        ("Backend API", test_backend_api)
    ]
    
    results = []
    for test_name, test_func in tests:
        results.append(test_func())
    
    print("\n=====================================")
    print("📊 Test Summary:")
    print("=====================================")
    
    if all(results):
        print("✅ All tests passed! Your React frontend is ready to use.")
        print("\nTo start development:")
        print("  ./run_dev.sh")
        print("\nOr manually:")
        print("  Backend: PORT=5002 python3 web_app.py")
        print("  Frontend: cd frontend && npm start")
    else:
        print("❌ Some tests failed. Please fix the issues above.")
        
        if not results[1]:  # node_modules test failed
            print("\n💡 Tip: Install frontend dependencies:")
            print("  cd frontend && npm install")
        
        if not results[2]:  # env file test failed
            print("\n💡 Tip: Create environment file:")
            print("  echo 'REACT_APP_API_URL=http://localhost:5002' > frontend/.env")

if __name__ == "__main__":
    main() 