#!/usr/bin/env python3
"""
Test script untuk menguji migrasi dari Dify ke Langchain + DeepSeek
"""

import asyncio
import os
from dotenv import load_dotenv
from langchain_client import ask_langchain

async def test_langchain():
    """Test Langchain client dengan DeepSeek"""
    print("🔧 Testing Langchain + DeepSeek migration...")
    
    # Load environment
    load_dotenv()
    
    # Check required environment variables
    deepseek_key = os.getenv("DEEPSEEK_API_KEY")
    discord_token = os.getenv("DISCORD_TOKEN")
    
    print(f"✓ DEEPSEEK_API_KEY loaded: {'Yes' if deepseek_key else 'No'}")
    print(f"✓ DISCORD_TOKEN loaded: {'Yes' if discord_token else 'No'}")
    
    if not deepseek_key:
        print("❌ DEEPSEEK_API_KEY not found in .env")
        print("Please add your DeepSeek API key to .env file:")
        print("DEEPSEEK_API_KEY=your_api_key_here")
        return False
    
    # Test simple query
    print("\n🧪 Testing Langchain query...")
    try:
        test_query = "Hello! Can you introduce yourself in one sentence?"
        user_id = "test_user_123"
        
        print(f"Query: {test_query}")
        print("Waiting for response...")
        
        response, conv_id = await ask_langchain(test_query, user_id)
        
        print(f"✓ Response received!")
        print(f"Conversation ID: {conv_id}")
        print(f"Response: {response[:200]}..." if len(response) > 200 else f"Response: {response}")
        
        # Test follow-up with same conversation
        print("\n🧪 Testing follow-up query...")
        follow_up = "What's your name?"
        response2, conv_id2 = await ask_langchain(follow_up, user_id, conv_id)
        
        print(f"✓ Follow-up response received!")
        print(f"Same conversation ID: {conv_id == conv_id2}")
        print(f"Response: {response2[:200]}..." if len(response2) > 200 else f"Response: {response2}")
        
        return True
        
    except Exception as e:
        print(f"❌ Test failed with error: {e}")
        import traceback
        traceback.print_exc()
        return False

async def test_bot_import():
    """Test bahwa bot.py bisa diimport tanpa error"""
    print("\n🤖 Testing bot.py import...")
    try:
        # Try to import bot module
        import bot
        print("✓ bot.py imports successfully")
        return True
    except Exception as e:
        print(f"❌ Failed to import bot.py: {e}")
        import traceback
        traceback.print_exc()
        return False

async def main():
    """Run all tests"""
    print("=" * 60)
    print("🧪 MIGRATION TEST SUITE")
    print("=" * 60)
    
    # Test 1: Environment
    print("\n1. Environment Test")
    print("-" * 40)
    env_ok = await test_langchain()
    
    # Test 2: Bot import
    print("\n2. Bot Import Test")
    print("-" * 40)
    import_ok = await test_bot_import()
    
    # Summary
    print("\n" + "=" * 60)
    print("📊 TEST SUMMARY")
    print("=" * 60)
    print(f"Environment Test: {'✅ PASS' if env_ok else '❌ FAIL'}")
    print(f"Bot Import Test:  {'✅ PASS' if import_ok else '❌ FAIL'}")
    
    if env_ok and import_ok:
        print("\n🎉 All tests passed! Migration successful.")
        print("\nNext steps:")
        print("1. Update your .env file with DeepSeek API key")
        print("2. Install new dependencies: pip install -r requirements.txt")
        print("3. Run the bot: python bot.py")
    else:
        print("\n⚠️ Some tests failed. Please check the errors above.")

if __name__ == "__main__":
    asyncio.run(main())