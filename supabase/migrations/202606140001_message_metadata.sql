ALTER TABLE messages ADD COLUMN IF NOT EXISTS metadata JSON;
UPDATE messages SET metadata = '{}' WHERE metadata IS NULL;
ALTER TABLE messages ALTER COLUMN metadata SET NOT NULL;
