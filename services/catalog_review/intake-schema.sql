-- Additive migration, applied by the migration owner after schema.sql.
-- Inbox access is a trusted ingress/operator boundary, never a customer API.
CREATE TABLE intake_key_binding (
    singleton boolean PRIMARY KEY CHECK (singleton),
    key_check text NOT NULL CHECK (key_check ~ '^[0-9a-f]{64}$')
);
CREATE TABLE intake_inbox (
    intake_id uuid PRIMARY KEY,
    source text NOT NULL CHECK (source IN ('typeform', 'short_form')),
    form_id text NOT NULL,
    source_digest text NOT NULL UNIQUE CHECK (source_digest ~ '^[0-9a-f]{64}$'),
    payload_digest text NOT NULL CHECK (payload_digest ~ '^[0-9a-f]{64}$'),
    mapping_version integer NOT NULL CHECK (mapping_version > 0),
    inquiry_kind text NOT NULL CHECK (inquiry_kind IN ('owner', 'representative', 'partnership', 'unknown')),
    payload_cipher bytea NOT NULL CHECK (octet_length(payload_cipher) BETWEEN 1 AND 16384),
    submitted_at timestamptz NOT NULL,
    received_at timestamptz NOT NULL,
    recorded_by uuid
);
-- Five lifetime admissions, not five concurrent cases. Deleting a case does not
-- free a pilot place. The PK and CHECK enforce the ceiling even under races.
CREATE TABLE intake_admissions (
    slot integer PRIMARY KEY CHECK (slot BETWEEN 1 AND 5),
    intake_id uuid UNIQUE REFERENCES intake_inbox ON DELETE SET NULL,
    workspace_id uuid UNIQUE,
    request_id uuid UNIQUE,
    approved_by uuid,
    approved_at timestamptz NOT NULL,
    erased_at timestamptz,
    CHECK ((erased_at IS NULL AND intake_id IS NOT NULL AND workspace_id IS NOT NULL
            AND request_id IS NOT NULL AND approved_by IS NOT NULL)
        OR (erased_at IS NOT NULL AND intake_id IS NULL AND workspace_id IS NULL
            AND request_id IS NULL AND approved_by IS NULL))
);
REVOKE ALL ON intake_key_binding, intake_inbox, intake_admissions FROM PUBLIC;
GRANT SELECT, INSERT ON intake_key_binding, intake_inbox, intake_admissions TO review_runtime;

-- Separate TEM ledger. The legacy retrying invitation worker MUST NOT be used
-- for TEM. Mark uncertain durably BEFORE the one permitted provider POST.
CREATE TABLE portal_mail_attempts (
    workspace_id uuid NOT NULL,
    invitation_id uuid NOT NULL,
    status text NOT NULL DEFAULT 'queued' CHECK (status IN ('queued', 'uncertain', 'accepted', 'delivered', 'bounced', 'failed', 'canceled')),
    attempt_id uuid,
    provider_reference uuid,
    reason text NOT NULL DEFAULT 'queued',
    created_at timestamptz NOT NULL,
    updated_at timestamptz NOT NULL,
    PRIMARY KEY (workspace_id, invitation_id),
    FOREIGN KEY (workspace_id, invitation_id) REFERENCES invitations,
    CHECK (status IN ('queued', 'canceled') OR attempt_id IS NOT NULL)
);
CREATE UNIQUE INDEX portal_mail_provider_reference ON portal_mail_attempts(provider_reference)
    WHERE provider_reference IS NOT NULL;
ALTER TABLE portal_mail_attempts ENABLE ROW LEVEL SECURITY;
ALTER TABLE portal_mail_attempts FORCE ROW LEVEL SECURITY;
CREATE POLICY workspace_scope ON portal_mail_attempts
    USING (workspace_id::text = current_setting('space.workspace_id', true))
    WITH CHECK (workspace_id::text = current_setting('space.workspace_id', true));
REVOKE ALL ON portal_mail_attempts FROM PUBLIC;
GRANT SELECT, INSERT, UPDATE ON portal_mail_attempts TO review_runtime;

CREATE FUNCTION guard_portal_mail_transition() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
    IF NEW.workspace_id <> OLD.workspace_id OR NEW.invitation_id <> OLD.invitation_id
        OR (OLD.attempt_id IS NOT NULL AND NEW.attempt_id IS DISTINCT FROM OLD.attempt_id)
        OR (OLD.provider_reference IS NOT NULL AND NEW.provider_reference IS DISTINCT FROM OLD.provider_reference)
        OR NOT (
            NEW.status = OLD.status
            OR (OLD.status = 'queued' AND NEW.status IN ('uncertain', 'canceled'))
            OR (OLD.status = 'uncertain' AND NEW.status IN ('accepted', 'delivered', 'bounced', 'failed', 'canceled'))
            OR (OLD.status = 'accepted' AND NEW.status IN ('delivered', 'bounced', 'failed', 'canceled'))
            OR (OLD.status = 'delivered' AND NEW.status = 'bounced')
        ) THEN
        RAISE EXCEPTION 'invalid_mail_transition';
    END IF;
    RETURN NEW;
END $$;
CREATE TRIGGER portal_mail_transition BEFORE UPDATE ON portal_mail_attempts
    FOR EACH ROW EXECUTE FUNCTION guard_portal_mail_transition();

-- Separate erasure worker role only, assembled by the deployment migration:
-- GRANT SELECT ON intake_inbox, intake_admissions TO <erasure_worker>;
-- GRANT SELECT(workspace_id) ON portal_mail_attempts TO <erasure_worker>;
-- GRANT DELETE ON intake_inbox, portal_mail_attempts TO <erasure_worker>;
-- PostgreSQL row locking requires an UPDATE privilege. This column grant is
-- worker-only; submission/receipt timestamps remain immutable to both roles.
-- GRANT UPDATE(payload_cipher) ON intake_inbox TO <erasure_worker>;
-- GRANT UPDATE(intake_id,workspace_id,request_id,approved_by,erased_at)
--     ON intake_admissions TO <erasure_worker>;
-- Do NOT grant these privileges to review_runtime. Set the worker's local
-- space.workspace_id; do not give it BYPASSRLS, ownership or DDL privileges.
