-- Retention delivery is independent of case activity and never extends its date.
ALTER TABLE retention_notices DROP CONSTRAINT retention_notices_status_check;
ALTER TABLE retention_notices ADD CONSTRAINT retention_notices_status_check
    CHECK (status IN ('queued','uncertain','accepted','delivered','bounced','cancelled','failed'));
ALTER TABLE retention_notices ADD COLUMN attempt_id uuid;
ALTER TABLE retention_notices ADD COLUMN provider_reference uuid;
ALTER TABLE retention_notices ADD COLUMN reason text NOT NULL DEFAULT 'queued';
ALTER TABLE retention_notices ADD COLUMN updated_at timestamptz;
UPDATE retention_notices SET updated_at=created_at;
ALTER TABLE retention_notices ALTER COLUMN updated_at SET DEFAULT CURRENT_TIMESTAMP;
ALTER TABLE retention_notices ALTER COLUMN updated_at SET NOT NULL;
CREATE UNIQUE INDEX retention_mail_provider_reference ON retention_notices(provider_reference)
    WHERE provider_reference IS NOT NULL;

CREATE FUNCTION guard_retention_mail_transition() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
    IF NEW.workspace_id <> OLD.workspace_id OR NEW.activity_version <> OLD.activity_version
        OR NEW.deadline <> OLD.deadline OR NEW.created_at <> OLD.created_at
        OR (OLD.attempt_id IS NOT NULL AND NEW.attempt_id IS DISTINCT FROM OLD.attempt_id)
        OR (OLD.provider_reference IS NOT NULL AND NEW.provider_reference IS DISTINCT FROM OLD.provider_reference)
        OR NOT (
            NEW.status = OLD.status
            OR (OLD.status = 'queued' AND NEW.status IN ('uncertain', 'failed', 'cancelled'))
            OR (OLD.status = 'uncertain' AND NEW.status IN ('accepted', 'delivered', 'bounced', 'failed', 'cancelled'))
            OR (OLD.status = 'accepted' AND NEW.status IN ('delivered', 'bounced', 'failed', 'cancelled'))
            OR (OLD.status = 'delivered' AND NEW.status = 'bounced')
        ) THEN
        RAISE EXCEPTION 'invalid_retention_mail_transition';
    END IF;
    RETURN NEW;
END $$;
CREATE TRIGGER retention_mail_transition BEFORE UPDATE ON retention_notices
    FOR EACH ROW EXECUTE FUNCTION guard_retention_mail_transition();
-- Existing SELECT/INSERT/UPDATE runtime grants and forced workspace RLS apply.
-- DELETE remains exclusively with the separately provisioned erasure worker.
