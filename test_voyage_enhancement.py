#!/usr/bin/env python3
"""
Test script for Voyage RAG Enhancement with Rerank-2.5
"""

import os
import sys
import logging
from typing import List, Dict, Any

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def test_embedding_models():
    """Test different Voyage embedding models"""
    print("🧪 Testing Voyage Embedding Models...")
    
    try:
        import voyageai
        client = voyageai.Client(api_key=os.getenv('VOYAGE_API_KEY'))
        
        test_text = "The stock market showed strong performance today with technology stocks leading gains."
        models = ['voyage-3.5-lite', 'voyage-3.5', 'voyage-3-large']
        
        results = {}
        for model in models:
            try:
                result = client.embed(texts=[test_text], model=model)
                embedding = result.embeddings[0]
                results[model] = {
                    'dimensions': len(embedding),
                    'success': True
                }
                print(f"   ✅ {model}: {len(embedding)} dimensions")
            except Exception as e:
                results[model] = {
                    'error': str(e),
                    'success': False
                }
                print(f"   ❌ {model}: {e}")
        
        return results
        
    except Exception as e:
        print(f"❌ Embedding test failed: {e}")
        return {}

def test_rerank_functionality():
    """Test Rerank-2.5 functionality"""
    print("\n🧪 Testing Rerank-2.5...")
    
    try:
        import voyageai
        client = voyageai.Client(api_key=os.getenv('VOYAGE_API_KEY'))
        
        # Test documents
        documents = [
            "Apple Inc. reported record quarterly earnings with iPhone sales exceeding expectations.",
            "The weather forecast predicts sunny skies for the weekend.",
            "Tesla stock surged 15% after announcing new electric vehicle models.",
            "A new restaurant opened in downtown with innovative fusion cuisine.",
            "Microsoft announced major updates to their cloud computing platform."
        ]
        
        query = "What happened with technology stocks today?"
        
        result = client.rerank(
            query=query,
            documents=documents,
            model="rerank-2.5",
            top_k=3
        )
        
        print("   ✅ Rerank-2.5 working correctly")
        print("   📊 Results:")
        for i, item in enumerate(result.results):
            doc_text = documents[item.index][:60] + "..." if len(documents[item.index]) > 60 else documents[item.index]
            print(f"      {i+1}. Score: {item.relevance_score:.3f} | {doc_text}")
        
        return True
        
    except Exception as e:
        print(f"   ❌ Rerank-2.5 test failed: {e}")
        return False

def test_web_app_integration():
    """Test the web app integration"""
    print("\n🧪 Testing Web App Integration...")
    
    try:
        # Import the web app functions
        sys.path.append(os.path.dirname(os.path.abspath(__file__)))
        
        # Test embedding function
        from web_app import _embed_text_voyage, _rerank_with_voyage
        
        test_text = "Bitcoin reached new all-time highs as institutional adoption increases."
        
        # Test embedding
        try:
            embedding = _embed_text_voyage(test_text)
            print(f"   ✅ Embedding: {len(embedding)} dimensions")
        except Exception as e:
            print(f"   ❌ Embedding failed: {e}")
            return False
        
        # Test reranking
        try:
            documents = [
                "Cryptocurrency markets showed volatility today.",
                "Traditional banking sector reported stable growth.",
                "Bitcoin and Ethereum both reached new price milestones.",
                "Federal Reserve announced new monetary policy measures."
            ]
            
            reranked = _rerank_with_voyage(test_text, documents, top_k=2)
            print(f"   ✅ Reranking: {len(reranked)} results")
            for idx, score in reranked:
                print(f"      Document {idx}: Score {score:.3f}")
                
        except Exception as e:
            print(f"   ❌ Reranking failed: {e}")
            return False
        
        return True
        
    except Exception as e:
        print(f"   ❌ Web app integration test failed: {e}")
        return False

def check_environment_config():
    """Check environment configuration"""
    print("🔧 Checking Environment Configuration...")
    
    config = {
        'VOYAGE_API_KEY': os.getenv('VOYAGE_API_KEY'),
        'VOYAGE_MODEL': os.getenv('VOYAGE_MODEL', 'voyage-3.5-lite'),
        'ENABLE_RERANK': os.getenv('ENABLE_RERANK', 'true'),
        'VOYAGE_EMBED_DIM': os.getenv('VOYAGE_EMBED_DIM', '1024')
    }
    
    for key, value in config.items():
        if value:
            print(f"   ✅ {key}: {value}")
        else:
            print(f"   ⚠️  {key}: Not set")
    
    return config

def performance_comparison():
    """Show performance comparison"""
    print("\n📊 Performance Comparison:")
    print("=" * 40)
    
    comparison = {
        'Current Setup (OpenAI)': {
            'cost': '$0.02 per million tokens',
            'performance': 'Baseline',
            'context': '8K tokens'
        },
        'Voyage-3.5-Lite': {
            'cost': '$0.02 per million tokens',
            'performance': '+6.34% better',
            'context': '32K tokens'
        },
        'Voyage-3.5-Lite + Rerank-2.5': {
            'cost': '$0.02 + $0.05 per million tokens',
            'performance': '+6.34% + 15-25% rerank improvement',
            'context': '32K tokens'
        }
    }
    
    for setup, specs in comparison.items():
        print(f"\n🔹 {setup}:")
        print(f"   Cost: {specs['cost']}")
        print(f"   Performance: {specs['performance']}")
        print(f"   Context: {specs['context']}")

def main():
    """Main test function"""
    print("🚀 Voyage RAG Enhancement Test")
    print("=" * 40)
    
    # Check environment
    config = check_environment_config()
    
    if not config['VOYAGE_API_KEY']:
        print("\n❌ VOYAGE_API_KEY not found!")
        print("   Please set it in your .env file")
        return False
    
    # Test embedding models
    embedding_results = test_embedding_models()
    
    # Test reranking
    rerank_success = test_rerank_functionality()
    
    # Test web app integration
    integration_success = test_web_app_integration()
    
    # Show performance comparison
    performance_comparison()
    
    # Summary
    print("\n📋 Test Summary:")
    print("=" * 40)
    
    working_models = [model for model, result in embedding_results.items() if result.get('success', False)]
    print(f"✅ Working embedding models: {', '.join(working_models) if working_models else 'None'}")
    print(f"{'✅' if rerank_success else '❌'} Rerank-2.5: {'Working' if rerank_success else 'Failed'}")
    print(f"{'✅' if integration_success else '❌'} Web App Integration: {'Working' if integration_success else 'Failed'}")
    
    if working_models and rerank_success and integration_success:
        print("\n🎉 All tests passed! Your Voyage enhancement is ready.")
        print("\n📝 Next steps:")
        print("1. Restart your application")
        print("2. Test the enhanced search functionality")
        print("3. Monitor performance improvements")
    else:
        print("\n⚠️  Some tests failed. Please check the configuration.")
    
    return True

if __name__ == "__main__":
    main()

