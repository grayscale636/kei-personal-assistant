#!/usr/bin/env python3
"""
Test Discord connection dengan token yang ada
"""

import asyncio
import os
import sys
from dotenv import load_dotenv

load_dotenv()

TOKEN = os.getenv('DISCORD_TOKEN')

async def test_token():
    """Test apakah token Discord valid"""
    print("🔍 Testing Discord token...")
    print(f"Token: {TOKEN[:10]}...")
    
    if not TOKEN:
        print("❌ Token tidak ditemukan di .env")
        return False
    
    # Coba import discord dan test minimal
    try:
        import discord
        
        # Buat client sederhana
        intents = discord.Intents.default()
        intents.message_content = True
        
        client = discord.Client(intents=intents)
        
        @client.event
        async def on_ready():
            print(f"✅ Connected as {client.user}")
            await client.close()
        
        @client.event 
        async def on_connect():
            print("🌐 Connected to Discord gateway")
        
        @client.event
        async def on_disconnect():
            print("🔌 Disconnected from Discord")
        
        # Jalankan dengan timeout
        try:
            print("🔄 Connecting to Discord...")
            await asyncio.wait_for(client.start(TOKEN), timeout=10)
            return True
        except asyncio.TimeoutError:
            print("⏰ Timeout connecting to Discord")
            return False
        except discord.LoginFailure as e:
            print(f"❌ Login failed: {e}")
            print("Mungkin token sudah expired atau invalid")
            return False
        except Exception as e:
            print(f"❌ Error: {type(e).__name__}: {e}")
            return False
            
    except ImportError:
        print("❌ discord.py not installed")
        return False

async def main():
    print("=" * 50)
    print("DISCORD CONNECTION TEST")
    print("=" * 50)
    
    success = await test_token()
    
    print("\n" + "=" * 50)
    if success:
        print("✅ Discord connection test PASSED")
        print("\nBot @Kei siap dijalankan!")
        print("Jalankan: python bot.py")
    else:
        print("❌ Discord connection test FAILED")
        print("\nPerlu diperbaiki:")
        print("1. Cek token Discord di .env")
        print("2. Token mungkin expired")
        print("3. Buat token baru di Discord Developer Portal")
        print("4. Update .env dengan token baru")
    
    return 0 if success else 1

if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)