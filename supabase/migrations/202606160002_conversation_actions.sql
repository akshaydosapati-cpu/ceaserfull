ALTER TABLE conversations ADD COLUMN IF NOT EXISTS pinned BOOLEAN;
ALTER TABLE conversations ADD COLUMN IF NOT EXISTS archived BOOLEAN;
UPDATE conversations SET pinned = false WHERE pinned IS NULL;
UPDATE conversations SET archived = false WHERE archived IS NULL;
ALTER TABLE conversations ALTER COLUMN pinned SET NOT NULL;
ALTER TABLE conversations ALTER COLUMN archived SET NOT NULL;
