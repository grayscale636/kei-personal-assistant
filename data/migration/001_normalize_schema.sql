-- 001_normalize_schema.sql
-- Normalize schema: add users + channels tables, FKs, CHECK constraints,
-- TIMESTAMPTZ, full-text index, JSONB metadata, auto-upsert trigger.
-- Idempotent: safe to re-run.

BEGIN;

-- ---------------------------------------------------------------
-- 1. users table
-- ---------------------------------------------------------------
CREATE TABLE IF NOT EXISTS users (
    user_id        TEXT PRIMARY KEY,
    username       TEXT,
    first_seen     TIMESTAMPTZ DEFAULT NOW(),
    last_seen      TIMESTAMPTZ DEFAULT NOW(),
    total_messages INT DEFAULT 0
);

-- ---------------------------------------------------------------
-- 2. channels table
-- ---------------------------------------------------------------
CREATE TABLE IF NOT EXISTS channels (
    channel_id   TEXT PRIMARY KEY,
    channel_name TEXT,
    guild_id     TEXT,
    first_seen   TIMESTAMPTZ DEFAULT NOW()
);

-- ---------------------------------------------------------------
-- 3. Backfill users from existing conversations
-- ---------------------------------------------------------------
INSERT INTO users (user_id, username, first_seen, last_seen, total_messages)
SELECT
    user_id,
    MAX(username),
    MIN(timestamp) AT TIME ZONE 'UTC',
    MAX(timestamp) AT TIME ZONE 'UTC',
    COUNT(*)
FROM conversations
WHERE user_id IS NOT NULL
GROUP BY user_id
ON CONFLICT (user_id) DO NOTHING;

-- ---------------------------------------------------------------
-- 4. Backfill channels from existing conversations
-- ---------------------------------------------------------------
INSERT INTO channels (channel_id, first_seen)
SELECT
    channel_id,
    MIN(timestamp) AT TIME ZONE 'UTC'
FROM conversations
WHERE channel_id IS NOT NULL
GROUP BY channel_id
ON CONFLICT (channel_id) DO NOTHING;

-- ---------------------------------------------------------------
-- 5. Rename conversations.timestamp -> created_at
-- ---------------------------------------------------------------
DO $$
BEGIN
    IF EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_name = 'conversations' AND column_name = 'timestamp'
    ) THEN
        ALTER TABLE conversations RENAME COLUMN timestamp TO created_at;
    END IF;
END $$;

-- ---------------------------------------------------------------
-- 6. Convert TIMESTAMP -> TIMESTAMPTZ
-- ---------------------------------------------------------------
ALTER TABLE conversations
    ALTER COLUMN created_at TYPE TIMESTAMPTZ USING created_at AT TIME ZONE 'UTC';

ALTER TABLE user_preferences
    ALTER COLUMN updated_at TYPE TIMESTAMPTZ USING updated_at AT TIME ZONE 'UTC';

-- ---------------------------------------------------------------
-- 7. JSONB metadata column on conversations
-- ---------------------------------------------------------------
ALTER TABLE conversations
    ADD COLUMN IF NOT EXISTS metadata JSONB DEFAULT '{}'::jsonb;

-- ---------------------------------------------------------------
-- 8. Foreign keys (drop+recreate so script is idempotent)
-- ---------------------------------------------------------------
ALTER TABLE conversations DROP CONSTRAINT IF EXISTS fk_conversations_user;
ALTER TABLE conversations ADD CONSTRAINT fk_conversations_user
    FOREIGN KEY (user_id) REFERENCES users(user_id) ON DELETE SET NULL;

ALTER TABLE conversations DROP CONSTRAINT IF EXISTS fk_conversations_channel;
ALTER TABLE conversations ADD CONSTRAINT fk_conversations_channel
    FOREIGN KEY (channel_id) REFERENCES channels(channel_id) ON DELETE SET NULL;

ALTER TABLE user_preferences DROP CONSTRAINT IF EXISTS fk_prefs_user;
ALTER TABLE user_preferences ADD CONSTRAINT fk_prefs_user
    FOREIGN KEY (user_id) REFERENCES users(user_id) ON DELETE CASCADE;

-- Backfill users from existing user_preferences too (in case of orphans)
INSERT INTO users (user_id)
SELECT user_id FROM user_preferences
ON CONFLICT (user_id) DO NOTHING;

-- ---------------------------------------------------------------
-- 9. CHECK constraints on user_preferences enums
-- ---------------------------------------------------------------
ALTER TABLE user_preferences DROP CONSTRAINT IF EXISTS lang_valid;
ALTER TABLE user_preferences ADD CONSTRAINT lang_valid
    CHECK (lang IN ('id','en','jawa','sunda'));

ALTER TABLE user_preferences DROP CONSTRAINT IF EXISTS tone_valid;
ALTER TABLE user_preferences ADD CONSTRAINT tone_valid
    CHECK (tone IN ('casual','formal','santai','sarkas'));

ALTER TABLE user_preferences DROP CONSTRAINT IF EXISTS response_length_valid;
ALTER TABLE user_preferences ADD CONSTRAINT response_length_valid
    CHECK (response_length IN ('short','normal','detailed'));

ALTER TABLE user_preferences DROP CONSTRAINT IF EXISTS emoji_level_valid;
ALTER TABLE user_preferences ADD CONSTRAINT emoji_level_valid
    CHECK (emoji_level IN ('none','minimal','normal','heavy'));

-- ---------------------------------------------------------------
-- 10. Indexes
-- ---------------------------------------------------------------
CREATE INDEX IF NOT EXISTS idx_conversations_user_id
    ON conversations(user_id);

CREATE INDEX IF NOT EXISTS idx_conversations_message_fts
    ON conversations USING GIN (
        to_tsvector('simple', coalesce(message, '') || ' ' || coalesce(response, ''))
    );

-- Drop the old idx_search (LIKE-style index, useless for ILIKE)
DROP INDEX IF EXISTS idx_search;

-- ---------------------------------------------------------------
-- 11. BEFORE INSERT trigger: auto-upsert users + channels,
--     bump users.last_seen + total_messages
-- ---------------------------------------------------------------
CREATE OR REPLACE FUNCTION ensure_user_channel() RETURNS TRIGGER AS $$
BEGIN
    IF NEW.user_id IS NOT NULL THEN
        INSERT INTO users (user_id, username, first_seen, last_seen, total_messages)
        VALUES (NEW.user_id, NEW.username, NOW(), NOW(), 1)
        ON CONFLICT (user_id) DO UPDATE SET
            username       = COALESCE(EXCLUDED.username, users.username),
            last_seen      = NOW(),
            total_messages = users.total_messages + 1;
    END IF;

    IF NEW.channel_id IS NOT NULL THEN
        INSERT INTO channels (channel_id) VALUES (NEW.channel_id)
        ON CONFLICT (channel_id) DO NOTHING;
    END IF;

    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_conversations_ensure_refs ON conversations;
CREATE TRIGGER trg_conversations_ensure_refs
    BEFORE INSERT ON conversations
    FOR EACH ROW EXECUTE FUNCTION ensure_user_channel();

COMMIT;
