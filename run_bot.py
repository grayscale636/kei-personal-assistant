#!/usr/bin/env python3
"""
Script untuk menjalankan bot @Kei dengan migrasi Langchain + DeepSeek
"""

import asyncio
import sys
import os

# Add current directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

async def main():
    print("=" * 60)
    print("🚀 STARTING BOT @Kei - LANGCHAIN + DEEPSEEK MIGRATION")
    print("=" * 60)
    
    try:
        # Import bot module
        import bot
        
        print("✅ Bot module loaded successfully")
        print(f"✅ Discord token: {'Loaded' if bot.TOKEN else 'Missing'}")
        print(f"✅ DeepSeek API key: {'Loaded' if os.getenv('DEEPSEEK_API_KEY') else 'Missing'}")
        
        # Start the bot
        print("\n🔗 Connecting to Discord...")
        async with bot.bot:
            await bot.bot.start(bot.TOKEN)
            
    except KeyboardInterrupt:
        print("\n\n🛑 Bot stopped by user")
    except Exception as e:
        print(f"\n❌ Error starting bot: {e}")
        import traceback
        traceback.print_exc()
        return 1
    
    return 0

if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)