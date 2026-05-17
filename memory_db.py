import json
from datetime import datetime, timedelta
from pathlib import Path
import os
import asyncpg

MIGRATION_DIR = Path(__file__).parent / 'data' / 'migration'

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


def _ts(value):
    """Normalize a datetime/None into ISO string so bot.py slicing still works."""
    if value is None:
        return None
    if isinstance(value, datetime):
        return value.isoformat(sep=' ')
    return str(value)


class BotMemoryDB:
    def __init__(self, db_url=None):
        self.db_url = db_url or os.getenv(
            "DATABASE_URL",
            "postgresql://keibot:KeiBot2024!@172.24.0.1:5432/bot_kei",
        )
        self.pool = None

    async def init_db(self):
        """Create the connection pool and apply any pending migrations."""
        self.pool = await asyncpg.create_pool(
            self.db_url, min_size=1, max_size=5
        )
        await self._run_migrations()
        print(f"[✓] PostgreSQL pool ready")

    async def _run_migrations(self):
        """Apply *.sql files in MIGRATION_DIR in order, tracked by schema_migrations."""
        async with self.pool.acquire() as conn:
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS schema_migrations (
                    filename   TEXT PRIMARY KEY,
                    applied_at TIMESTAMPTZ DEFAULT NOW()
                )
            """)
            applied = {
                r['filename']
                for r in await conn.fetch("SELECT filename FROM schema_migrations")
            }

            if not MIGRATION_DIR.exists():
                print(f"[WARN] Migration dir not found: {MIGRATION_DIR}")
                return

            files = sorted(MIGRATION_DIR.glob('*.sql'))
            pending = [f for f in files if f.name not in applied]
            if not pending:
                print(f"[✓] Schema up to date ({len(applied)} migrations applied)")
                return

            for f in pending:
                print(f"[INFO] Applying migration: {f.name}")
                await conn.execute(f.read_text())
                await conn.execute(
                    "INSERT INTO schema_migrations (filename) VALUES ($1)",
                    f.name,
                )
                print(f"[✓] Migration applied: {f.name}")

    async def save_conversation(self, channel_id, user_id, username, message, response, conversation_id):
        try:
            async with self.pool.acquire() as conn:
                await conn.execute("""
                    INSERT INTO conversations
                        (channel_id, user_id, username, message, response, conversation_id)
                    VALUES ($1, $2, $3, $4, $5, $6)
                """, str(channel_id), str(user_id), username, message, response, conversation_id)
                print(f"[✓] Saved conversation to DB: {username} in channel {channel_id}")
        except Exception as e:
            print(f"[ERROR] Failed to save conversation: {e}")

    async def load_conversation_history(self, channel_id, days=7, limit=10):
        since_date = datetime.now() - timedelta(days=days)
        try:
            async with self.pool.acquire() as conn:
                rows = await conn.fetch("""
                    SELECT username, message, response, created_at
                    FROM conversations
                    WHERE channel_id = $1 AND created_at > $2
                    ORDER BY created_at DESC
                    LIMIT $3
                """, str(channel_id), since_date, limit)

                conversations = [
                    {
                        'username': r['username'],
                        'message': r['message'],
                        'response': r['response'],
                        'timestamp': _ts(r['created_at']),
                    }
                    for r in rows
                ]
                conversations.reverse()
                print(f"[DEBUG] Loaded {len(conversations)} conversations from DB for channel {channel_id}")
                return conversations
        except Exception as e:
            print(f"[ERROR] Failed to load conversation history: {e}")
            return []

    async def search_conversations(self, keyword, channel_id=None, days=30, limit=10):
        since_date = datetime.now() - timedelta(days=days)
        # Full-text search using GIN index on (message || response)
        try:
            async with self.pool.acquire() as conn:
                if channel_id:
                    rows = await conn.fetch("""
                        SELECT channel_id, username, message, response, created_at
                        FROM conversations
                        WHERE to_tsvector('simple', coalesce(message,'') || ' ' || coalesce(response,''))
                              @@ plainto_tsquery('simple', $1)
                          AND channel_id = $2 AND created_at > $3
                        ORDER BY created_at DESC LIMIT $4
                    """, keyword, str(channel_id), since_date, limit)
                else:
                    rows = await conn.fetch("""
                        SELECT channel_id, username, message, response, created_at
                        FROM conversations
                        WHERE to_tsvector('simple', coalesce(message,'') || ' ' || coalesce(response,''))
                              @@ plainto_tsquery('simple', $1)
                          AND created_at > $2
                        ORDER BY created_at DESC LIMIT $3
                    """, keyword, since_date, limit)

                results = [
                    (r['channel_id'], r['username'], r['message'], r['response'], _ts(r['created_at']))
                    for r in rows
                ]
                print(f"[DEBUG] Found {len(results)} search results for '{keyword}'")
                return results
        except Exception as e:
            print(f"[ERROR] Failed to search conversations: {e}")
            return []

    async def get_channel_stats(self, channel_id, days=30):
        since_date = datetime.now() - timedelta(days=days)
        try:
            async with self.pool.acquire() as conn:
                row = await conn.fetchrow("""
                    SELECT COUNT(*) AS total_conversations,
                           COUNT(DISTINCT user_id) AS unique_users,
                           MIN(created_at) AS first_message,
                           MAX(created_at) AS last_message
                    FROM conversations
                    WHERE channel_id = $1 AND created_at > $2
                """, str(channel_id), since_date)
                return {
                    'total_conversations': row['total_conversations'],
                    'unique_users': row['unique_users'],
                    'first_message': _ts(row['first_message']),
                    'last_message': _ts(row['last_message']),
                }
        except Exception as e:
            print(f"[ERROR] Failed to get channel stats: {e}")
            return {
                'total_conversations': 0,
                'unique_users': 0,
                'first_message': None,
                'last_message': None,
            }

    async def cleanup_old_conversations(self, days=90):
        cutoff_date = datetime.now() - timedelta(days=days)
        try:
            async with self.pool.acquire() as conn:
                result = await conn.execute(
                    "DELETE FROM conversations WHERE created_at < $1",
                    cutoff_date,
                )
                deleted_count = int(result.split()[-1]) if result else 0
                print(f"[✓] Cleaned up {deleted_count} old conversations")
                return deleted_count
        except Exception as e:
            print(f"[ERROR] Failed to cleanup old conversations: {e}")
            return 0

    async def purge_channel_data(self, channel_id):
        try:
            async with self.pool.acquire() as conn:
                result = await conn.execute(
                    "DELETE FROM conversations WHERE channel_id = $1",
                    str(channel_id),
                )
                deleted_count = int(result.split()[-1]) if result else 0
                print(f"[INFO] Purged {deleted_count} conversations from channel {channel_id}")
                return deleted_count
        except Exception as e:
            print(f"[ERROR] Failed to purge channel data: {e}")
            return 0

    async def get_user_preferences(self, user_id):
        """Get user preferences, fallback to defaults if not set."""
        try:
            async with self.pool.acquire() as conn:
                row = await conn.fetchrow("""
                    SELECT lang, tone, nickname, response_length, emoji_level
                    FROM user_preferences WHERE user_id = $1
                """, str(user_id))
                if not row:
                    return dict(DEFAULT_PREFS)
                return {
                    'lang': row['lang'],
                    'tone': row['tone'],
                    'nickname': row['nickname'],
                    'response_length': row['response_length'],
                    'emoji_level': row['emoji_level'],
                }
        except Exception as e:
            print(f"[ERROR] Failed to get user preferences: {e}")
            return dict(DEFAULT_PREFS)

    async def set_user_preferences(self, user_id, **updates):
        """Upsert user preferences. Returns the full updated prefs dict."""
        current = await self.get_user_preferences(user_id)
        current.update(updates)
        try:
            async with self.pool.acquire() as conn:
                await conn.execute("""
                    INSERT INTO user_preferences
                        (user_id, lang, tone, nickname, response_length, emoji_level, updated_at)
                    VALUES ($1, $2, $3, $4, $5, $6, CURRENT_TIMESTAMP)
                    ON CONFLICT (user_id) DO UPDATE SET
                        lang = EXCLUDED.lang,
                        tone = EXCLUDED.tone,
                        nickname = EXCLUDED.nickname,
                        response_length = EXCLUDED.response_length,
                        emoji_level = EXCLUDED.emoji_level,
                        updated_at = CURRENT_TIMESTAMP
                """,
                    str(user_id),
                    current['lang'],
                    current['tone'],
                    current['nickname'],
                    current['response_length'],
                    current['emoji_level'],
                )
            return current
        except Exception as e:
            print(f"[ERROR] Failed to set user preferences: {e}")
            return current

    async def reset_user_preferences(self, user_id):
        try:
            async with self.pool.acquire() as conn:
                await conn.execute(
                    "DELETE FROM user_preferences WHERE user_id = $1",
                    str(user_id),
                )
            return True
        except Exception as e:
            print(f"[ERROR] Failed to reset user preferences: {e}")
            return False

    async def get_database_info(self):
        try:
            async with self.pool.acquire() as conn:
                row = await conn.fetchrow("""
                    SELECT
                        COUNT(*) AS total_conversations,
                        COUNT(DISTINCT channel_id) AS total_channels,
                        COUNT(DISTINCT user_id) AS total_users,
                        MIN(created_at) AS oldest_message,
                        MAX(created_at) AS newest_message
                    FROM conversations
                """)
                return {
                    'total_conversations': row['total_conversations'],
                    'total_channels': row['total_channels'],
                    'total_users': row['total_users'],
                    'oldest_message': _ts(row['oldest_message']),
                    'newest_message': _ts(row['newest_message']),
                }
        except Exception as e:
            print(f"[ERROR] Failed to get database info: {e}")
            return {
                'total_conversations': 0,
                'total_channels': 0,
                'total_users': 0,
                'oldest_message': None,
                'newest_message': None,
            }
