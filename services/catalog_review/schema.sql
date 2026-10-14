-- Apply once to an empty, dedicated database as a migration owner, not the app role.
CREATE TABLE receipts (
    source_digest text PRIMARY KEY,
    payload_digest text NOT NULL,
    workspace_id uuid NOT NULL UNIQUE
);
CREATE TABLE auth_limits (
    bucket_digest text PRIMARY KEY,
    started_at timestamptz NOT NULL,
    attempts integer NOT NULL CHECK (attempts > 0)
);
CREATE TABLE workspaces (
    workspace_id uuid PRIMARY KEY,
    status text NOT NULL DEFAULT 'active' CHECK (status IN ('active', 'deletion_requested')),
    revision integer NOT NULL DEFAULT 0 CHECK (revision >= 0),
    draft jsonb NOT NULL DEFAULT '{}' CHECK (jsonb_typeof(draft) = 'object'),
    landing_path text NOT NULL CHECK (landing_path IN ('/', '/apply/', '/sell/', '/calculator/', '/guides/music-catalog-valuation-2026/')),
    created_at timestamptz NOT NULL
);
CREATE TABLE memberships (
    workspace_id uuid NOT NULL REFERENCES workspaces,
    principal_id uuid NOT NULL,
    role text NOT NULL CHECK (role IN ('owner', 'reviewer')),
    active boolean NOT NULL DEFAULT true,
    PRIMARY KEY (workspace_id, principal_id)
);
CREATE TABLE invitations (
    workspace_id uuid NOT NULL REFERENCES workspaces,
    invitation_id uuid NOT NULL,
    principal_id uuid NOT NULL,
    recipient text NOT NULL CHECK (recipient ~ '^[a-zA-Z0-9._+-]+@example[.]com$'),
    token_digest text NOT NULL UNIQUE,
    expires_at timestamptz NOT NULL,
    consumed_at timestamptz,
    PRIMARY KEY (workspace_id, invitation_id),
    FOREIGN KEY (workspace_id, principal_id) REFERENCES memberships
);
CREATE TABLE sessions (
    workspace_id uuid NOT NULL REFERENCES workspaces,
    token_digest text NOT NULL,
    principal_id uuid NOT NULL,
    mfa boolean NOT NULL DEFAULT false,
    expires_at timestamptz NOT NULL,
    PRIMARY KEY (workspace_id, token_digest),
    FOREIGN KEY (workspace_id, principal_id) REFERENCES memberships
);
CREATE TABLE outbox (
    workspace_id uuid NOT NULL REFERENCES workspaces,
    invitation_id uuid NOT NULL,
    status text NOT NULL DEFAULT 'queued' CHECK (status IN ('queued', 'leased', 'accepted', 'dead')),
    attempts integer NOT NULL DEFAULT 0,
    available_at timestamptz NOT NULL,
    lease_id uuid,
    lease_until timestamptz,
    provider_reference text,
    PRIMARY KEY (workspace_id, invitation_id),
    FOREIGN KEY (workspace_id, invitation_id) REFERENCES invitations
);
CREATE INDEX outbox_ready ON outbox(workspace_id, available_at) WHERE status IN ('queued', 'leased');
CREATE TABLE documents (
    workspace_id uuid NOT NULL REFERENCES workspaces,
    document_id uuid NOT NULL,
    uploader_id uuid NOT NULL,
    object_key text NOT NULL UNIQUE,
    filename text NOT NULL,
    size_bytes integer NOT NULL CHECK (size_bytes > 0 AND size_bytes <= 26214400),
    sha256 text NOT NULL CHECK (sha256 ~ '^[0-9a-f]{64}$'),
    status text NOT NULL DEFAULT 'quarantined' CHECK (status IN ('quarantined', 'scanning', 'accepted_for_review', 'rejected')),
    scan_attempts integer NOT NULL DEFAULT 0,
    scan_lease_id uuid,
    scan_lease_until timestamptz,
    upload_request_id uuid,
    PRIMARY KEY (workspace_id, document_id),
    UNIQUE (workspace_id, upload_request_id),
    FOREIGN KEY (workspace_id, uploader_id) REFERENCES memberships
);
CREATE TABLE submissions (
    workspace_id uuid PRIMARY KEY REFERENCES workspaces,
    submission_id uuid NOT NULL UNIQUE,
    request_id uuid NOT NULL,
    revision integer NOT NULL,
    snapshot jsonb NOT NULL,
    created_at timestamptz NOT NULL
);
CREATE TABLE audit (
    workspace_id uuid NOT NULL REFERENCES workspaces,
    event_id uuid NOT NULL,
    action text NOT NULL CHECK (action IN ('application_received', 'invitation_consumed', 'draft_saved', 'document_quarantined', 'document_scanned', 'document_read', 'submitted', 'deletion_requested', 'session_closed', 'review_question_asked', 'review_question_answered', 'access_requested')),
    created_at timestamptz NOT NULL,
    PRIMARY KEY (workspace_id, event_id)
);

CREATE TABLE review_questions (
    workspace_id uuid NOT NULL REFERENCES submissions(workspace_id),
    question_id uuid NOT NULL,
    request_id uuid NOT NULL,
    author_id uuid NOT NULL,
    body text NOT NULL CHECK (char_length(body) BETWEEN 1 AND 4000),
    created_at timestamptz NOT NULL,
    PRIMARY KEY (workspace_id, question_id),
    UNIQUE (workspace_id, request_id),
    FOREIGN KEY (workspace_id, author_id) REFERENCES memberships
);
CREATE TABLE review_replies (
    workspace_id uuid NOT NULL,
    question_id uuid NOT NULL,
    request_id uuid NOT NULL,
    author_id uuid NOT NULL,
    body text NOT NULL CHECK (char_length(body) BETWEEN 1 AND 4000),
    created_at timestamptz NOT NULL,
    PRIMARY KEY (workspace_id, question_id),
    UNIQUE (workspace_id, request_id),
    FOREIGN KEY (workspace_id, question_id) REFERENCES review_questions,
    FOREIGN KEY (workspace_id, author_id) REFERENCES memberships
);

-- Authentication/routing chooses a workspace; every service operation must ALSO
-- authorize current membership. RLS is defense in depth, not authentication.
DO $$
DECLARE tab text;
BEGIN
    FOREACH tab IN ARRAY ARRAY['workspaces','memberships','invitations','sessions','outbox','documents','submissions','audit','review_questions','review_replies'] LOOP
        EXECUTE format('ALTER TABLE %I ENABLE ROW LEVEL SECURITY', tab);
        EXECUTE format('ALTER TABLE %I FORCE ROW LEVEL SECURITY', tab);
        EXECUTE format('CREATE POLICY workspace_scope ON %I USING (workspace_id::text = current_setting(''space.workspace_id'', true)) WITH CHECK (workspace_id::text = current_setting(''space.workspace_id'', true))', tab);
    END LOOP;
END $$;

-- The runtime role receives explicit privileges in the test harness/runbook.
-- Never grant UPDATE/DELETE on submissions or audit, or any DDL/TRUNCATE rights.
