-- Append-only internal reviews and recipient/version-bound owner decisions.
CREATE TABLE dealflow_reviews (
    workspace_id uuid NOT NULL REFERENCES workspaces,
    revision integer NOT NULL CHECK (revision > 0),
    request_id uuid NOT NULL,
    author_id uuid NOT NULL,
    source_digest text NOT NULL CHECK (source_digest ~ '^[0-9a-f]{64}$'),
    body jsonb NOT NULL CHECK (jsonb_typeof(body)='object'),
    created_at timestamptz NOT NULL,
    PRIMARY KEY (workspace_id,revision),
    UNIQUE (workspace_id,request_id),
    FOREIGN KEY (workspace_id,author_id) REFERENCES memberships
);
CREATE TABLE dealflow_packages (
    workspace_id uuid NOT NULL,
    package_id uuid NOT NULL,
    request_id uuid NOT NULL,
    revision integer NOT NULL,
    author_id uuid NOT NULL,
    request_body jsonb NOT NULL,
    payload jsonb NOT NULL,
    digest text NOT NULL CHECK (digest ~ '^[0-9a-f]{64}$'),
    created_at timestamptz NOT NULL,
    expires_at timestamptz NOT NULL,
    PRIMARY KEY (workspace_id,package_id),
    UNIQUE (workspace_id,request_id),
    FOREIGN KEY (workspace_id,revision) REFERENCES dealflow_reviews,
    FOREIGN KEY (workspace_id,author_id) REFERENCES memberships
);
CREATE TABLE dealflow_decisions (
    workspace_id uuid NOT NULL,
    sequence integer NOT NULL CHECK (sequence > 0),
    request_id uuid NOT NULL,
    package_id uuid NOT NULL,
    author_id uuid NOT NULL,
    digest text NOT NULL,
    decision text NOT NULL CHECK (decision IN ('approved','declined','revoked')),
    created_at timestamptz NOT NULL,
    PRIMARY KEY (workspace_id,sequence),
    UNIQUE (workspace_id,request_id),
    FOREIGN KEY (workspace_id,package_id) REFERENCES dealflow_packages,
    FOREIGN KEY (workspace_id,author_id) REFERENCES memberships
);
DO $$
DECLARE tab text;
BEGIN
    FOREACH tab IN ARRAY ARRAY['dealflow_reviews','dealflow_packages','dealflow_decisions'] LOOP
        EXECUTE format('ALTER TABLE %I ENABLE ROW LEVEL SECURITY',tab);
        EXECUTE format('ALTER TABLE %I FORCE ROW LEVEL SECURITY',tab);
        EXECUTE format('CREATE POLICY workspace_scope ON %I USING (workspace_id::text=current_setting(''space.workspace_id'',true)) WITH CHECK (workspace_id::text=current_setting(''space.workspace_id'',true))',tab);
    END LOOP;
END $$;
