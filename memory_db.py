import sqlite3
import json
from datetime import datetime, timedelta
import asyncio
import aiosqlite
import os

VALID_PREFS = {
    'lang': ['id', 'en', 'jawa', 'sunda'],
    'tone': ['casual', 'formal', 'santai', 'sarkas'],
    'response_length': ['short', 'normal', 'detailed'],
    'emoji_level': ['none', 'minimal', 'normal', 'heavy'],
}

DEFAULT_PREFS = {
    'lang': 'id',
    'tone': 'casual',
    'nickname': None,
    'response_length': 'short',
    'emoji_level': 'minimal',
}

NICKNAME_MAX_LEN = 32


class BotMemoryDB:
    def __init__(self, db_path="data/bot_memory.db"):
        self.db_path = db_path
        
    async def init_db(self):
        """Initialize database tables"""
        # Ensure data directory exists
        os.makedirs(os.path.dirname(self.db_path), exist_ok=True)
        
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute("""
                CREATE TABLE IF NOT EXISTS conversations (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    channel_id TEXT,
                    user_id TEXT,
                    username TEXT,
                    message TEXT,
                    response TEXT,
                    conversation_id TEXT,
                    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            await db.execute("""
                CREATE INDEX IF NOT EXISTS idx_channel_timestamp 
                ON conversations(channel_id, timestamp)
            """)
            
            await db.execute("""
                CREATE INDEX IF NOT EXISTS idx_search
                ON conversations(message, response)
            """)

            await db.execute("""
                CREATE TABLE IF NOT EXISTS user_preferences (
                    user_id TEXT PRIMARY KEY,
                    lang TEXT DEFAULT 'id',
                    tone TEXT DEFAULT 'casual',
                    nickname TEXT,
                    response_length TEXT DEFAULT 'short',
                    emoji_level TEXT DEFAULT 'minimal',
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)

            await db.commit()
            print(f"[✓] Database initialized at {self.db_path}")
    
    async def save_conversation(self, channel_id, user_id, username, message, response, conversation_id):
        """Save single conversation exchange"""
        try:
            async with aiosqlite.connect(self.db_path) as db:
                await db.execute("""
                    INSERT INTO conversations (channel_id, user_id, username, message, response, conversation_id)
                    VALUES (?, ?, ?, ?, ?, ?)
                """, (str(channel_id), str(user_id), username, message, response, conversation_id))
                await db.commit()
                print(f"[✓] Saved conversation to DB: {username} in channel {channel_id}")
        except Exception as e:
            print(f"[ERROR] Failed to save conversation: {e}")
    
    async def load_conversation_history(self, channel_id, days=7, limit=10):
        """Load conversation history for context"""
        since_date = datetime.now() - timedelta(days=days)
        
        try:
            async with aiosqlite.connect(self.db_path) as db:
                async with db.execute("""
                    SELECT username, message, response, timestamp
                    FROM conversations 
                    WHERE channel_id = ? AND timestamp > ?
                    ORDER BY timestamp DESC
                    LIMIT ?
                """, (str(channel_id), since_date, limit)) as cursor:
                    rows = await cursor.fetchall()
                    
                    conversations = []
                    for row in rows:
                        conversations.append({
                            'username': row[0],
                            'message': row[1], 
                            'response': row[2],
                            'timestamp': row[3]
                        })
                    
                    # Reverse to get chronological order (oldest first)
                    conversations.reverse()
                    print(f"[DEBUG] Loaded {len(conversations)} conversations from DB for channel {channel_id}")
                    return conversations
        except Exception as e:
            print(f"[ERROR] Failed to load conversation history: {e}")
            return []
    
    async def search_conversations(self, keyword, channel_id=None, days=30, limit=10):
        """Search conversations by keyword"""
        since_date = datetime.now() - timedelta(days=days)
        
        try:
            if channel_id:
                query = """
                    SELECT channel_id, username, message, response, timestamp
                    FROM conversations 
                    WHERE (message LIKE ? OR response LIKE ?) 
                    AND channel_id = ? AND timestamp > ?
                    ORDER BY timestamp DESC LIMIT ?
                """
                params = (f"%{keyword}%", f"%{keyword}%", str(channel_id), since_date, limit)
            else:
                query = """
                    SELECT channel_id, username, message, response, timestamp
                    FROM conversations 
                    WHERE (message LIKE ? OR response LIKE ?) 
                    AND timestamp > ?
                    ORDER BY timestamp DESC LIMIT ?
                """
                params = (f"%{keyword}%", f"%{keyword}%", since_date, limit)
                
            async with aiosqlite.connect(self.db_path) as db:
                async with db.execute(query, params) as cursor:
                    results = await cursor.fetchall()
                    print(f"[DEBUG] Found {len(results)} search results for '{keyword}'")
                    return results
        except Exception as e:
            print(f"[ERROR] Failed to search conversations: {e}")
            return []
    
    async def get_channel_stats(self, channel_id, days=30):
        """Get channel conversation statistics"""
        since_date = datetime.now() - timedelta(days=days)
        
        try:
            async with aiosqlite.connect(self.db_path) as db:
                async with db.execute("""
                    SELECT COUNT(*) as total_conversations,
                           COUNT(DISTINCT user_id) as unique_users,
                           MIN(timestamp) as first_message,
                           MAX(timestamp) as last_message
                    FROM conversations 
                    WHERE channel_id = ? AND timestamp > ?
                """, (str(channel_id), since_date)) as cursor:
                    row = await cursor.fetchone()
                    return {
                        'total_conversations': row[0],
                        'unique_users': row[1],
                        'first_message': row[2],
                        'last_message': row[3]
                    }
        except Exception as e:
            print(f"[ERROR] Failed to get channel stats: {e}")
            return {
                'total_conversations': 0,
                'unique_users': 0,
                'first_message': None,
                'last_message': None
            }
    
    async def cleanup_old_conversations(self, days=90):
        """Clean up conversations older than specified days"""
        cutoff_date = datetime.now() - timedelta(days=days)
        
        try:
            async with aiosqlite.connect(self.db_path) as db:
                cursor = await db.execute("""
                    DELETE FROM conversations WHERE timestamp < ?
                """, (cutoff_date,))
                deleted_count = cursor.rowcount
                await db.commit()
                print(f"[✓] Cleaned up {deleted_count} old conversations")
                return deleted_count
        except Exception as e:
            print(f"[ERROR] Failed to cleanup old conversations: {e}")
            return 0
    
    async def purge_channel_data(self, channel_id):
        """Permanently delete all conversations for a channel"""
        try:
            async with aiosqlite.connect(self.db_path) as db:
                cursor = await db.execute("""
                    DELETE FROM conversations 
                    WHERE channel_id = ?
                """, (str(channel_id),))
                
                deleted_count = cursor.rowcount
                await db.commit()
                
                print(f"[INFO] Purged {deleted_count} conversations from channel {channel_id}")
                return deleted_count
        except Exception as e:
            print(f"[ERROR] Failed to purge channel data: {e}")
            return 0
    
    async def get_user_preferences(self, user_id):
        """Get user preferences, fallback to defaults if not set."""
        try:
            async with aiosqlite.connect(self.db_path) as db:
                async with db.execute("""
                    SELECT lang, tone, nickname, response_length, emoji_level
                    FROM user_preferences WHERE user_id = ?
                """, (str(user_id),)) as cursor:
                    row = await cursor.fetchone()
                    if not row:
                        return dict(DEFAULT_PREFS)
                    return {
                        'lang': row[0],
                        'tone': row[1],
                        'nickname': row[2],
                        'response_length': row[3],
                        'emoji_level': row[4],
                    }
        except Exception as e:
            print(f"[ERROR] Failed to get user preferences: {e}")
            return dict(DEFAULT_PREFS)

    async def set_user_preferences(self, user_id, **updates):
        """Upsert user preferences. Returns the full updated prefs dict."""
        current = await self.get_user_preferences(user_id)
        current.update(updates)
        try:
            async with aiosqlite.connect(self.db_path) as db:
                await db.execute("""
                    INSERT INTO user_preferences
                        (user_id, lang, tone, nickname, response_length, emoji_level, updated_at)
                    VALUES (?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
                    ON CONFLICT(user_id) DO UPDATE SET
                        lang = excluded.lang,
                        tone = excluded.tone,
                        nickname = excluded.nickname,
                        response_length = excluded.response_length,
                        emoji_level = excluded.emoji_level,
                        updated_at = CURRENT_TIMESTAMP
                """, (
                    str(user_id),
                    current['lang'],
                    current['tone'],
                    current['nickname'],
                    current['response_length'],
                    current['emoji_level'],
                ))
                await db.commit()
            return current
        except Exception as e:
            print(f"[ERROR] Failed to set user preferences: {e}")
            return current

    async def reset_user_preferences(self, user_id):
        """Delete the user's prefs row so defaults apply again."""
        try:
            async with aiosqlite.connect(self.db_path) as db:
                await db.execute(
                    "DELETE FROM user_preferences WHERE user_id = ?",
                    (str(user_id),),
                )
                await db.commit()
            return True
        except Exception as e:
            print(f"[ERROR] Failed to reset user preferences: {e}")
            return False

    async def get_database_info(self):
        """Get overall database statistics"""
        try:
            async with aiosqlite.connect(self.db_path) as db:
                async with db.execute("""
                    SELECT 
                        COUNT(*) as total_conversations,
                        COUNT(DISTINCT channel_id) as total_channels,
                        COUNT(DISTINCT user_id) as total_users,
                        MIN(timestamp) as oldest_message,
                        MAX(timestamp) as newest_message
                    FROM conversations
                """) as cursor:
                    row = await cursor.fetchone()
                    return {
                        'total_conversations': row[0],
                        'total_channels': row[1], 
                        'total_users': row[2],
                        'oldest_message': row[3],
                        'newest_message': row[4]
                    }
        except Exception as e:
            print(f"[ERROR] Failed to get database info: {e}")
            return {
                'total_conversations': 0,
                'total_channels': 0,
                'total_users': 0,
                'oldest_message': None,
                'newest_message': None
            }
