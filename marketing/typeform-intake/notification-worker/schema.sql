CREATE TABLE IF NOT EXISTS notifications (
  id TEXT PRIMARY KEY,
  submitted_at TEXT NOT NULL,
  created_at INTEGER NOT NULL,
  reply_cipher TEXT,
  is_test INTEGER NOT NULL DEFAULT 0 CHECK(is_test IN (0, 1)),
  status TEXT NOT NULL CHECK(status IN ('pending', 'accepted', 'failed')),
  attempts INTEGER NOT NULL DEFAULT 0,
  first_attempt INTEGER,
  next_attempt INTEGER NOT NULL,
  lease_until INTEGER NOT NULL DEFAULT 0,
  lease_token TEXT,
  provider_id TEXT,
  error_code TEXT
);
CREATE INDEX IF NOT EXISTS notification_due ON notifications(status, next_attempt);
