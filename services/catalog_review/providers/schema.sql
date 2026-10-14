-- Explicit additive migration after catalog_review/schema.sql; never auto-applied.
-- Fresh disposable databases only in this tranche. review_runtime already exists.
CREATE TABLE toolost_connections (
    workspace_id uuid NOT NULL REFERENCES workspaces,
    connection_id uuid NOT NULL,
    environment text NOT NULL CHECK (environment IN ('sandbox','production')),
    principal_id uuid NOT NULL,
    generation integer NOT NULL CHECK (generation > 0),
    status text NOT NULL CHECK (status IN ('auth_pending','awaiting_confirmation','active','reauth_required','disconnected')),
    account_id text,
    scopes jsonb NOT NULL DEFAULT '[]',
    credentials jsonb,
    token_version integer NOT NULL DEFAULT 0,
    access_expires_at timestamptz,
    refresh_lease uuid,
    refresh_until timestamptz,
    confirmed_at timestamptz,
    PRIMARY KEY (workspace_id, connection_id),
    UNIQUE (workspace_id, environment),
    FOREIGN KEY (workspace_id, principal_id) REFERENCES memberships
);
CREATE TABLE toolost_oauth_attempts (
    workspace_id uuid NOT NULL,
    state_digest text NOT NULL,
    connection_id uuid NOT NULL,
    generation integer NOT NULL,
    environment text NOT NULL,
    session_digest text NOT NULL,
    principal_id uuid NOT NULL,
    callback_uri text NOT NULL,
    client_digest text NOT NULL,
    verifier jsonb,
    expires_at timestamptz NOT NULL,
    status text NOT NULL CHECK (status IN ('pending','exchanging','complete','failed')),
    PRIMARY KEY (workspace_id, state_digest),
    FOREIGN KEY (workspace_id, connection_id) REFERENCES toolost_connections
);
CREATE TABLE toolost_import_runs (
    workspace_id uuid NOT NULL,
    run_id uuid NOT NULL,
    connection_id uuid NOT NULL,
    generation integer NOT NULL,
    principal_id uuid NOT NULL,
    request_id uuid NOT NULL,
    payload_hash text NOT NULL,
    manifest text NOT NULL,
    resources jsonb NOT NULL,
    selection jsonb NOT NULL,
    account_id text NOT NULL,
    status text NOT NULL CHECK (status IN ('queued','running','retryable','complete','partial','cancelled')),
    resource_index integer NOT NULL DEFAULT 0,
    next_page integer NOT NULL DEFAULT 1,
    expected_totals jsonb,
    page_count integer NOT NULL DEFAULT 0,
    record_count integer NOT NULL DEFAULT 0,
    call_count integer NOT NULL DEFAULT 0,
    failures integer NOT NULL DEFAULT 0,
    lease_id uuid,
    lease_until timestamptz,
    available_at timestamptz NOT NULL,
    created_at timestamptz NOT NULL,
    deadline timestamptz NOT NULL,
    error_code text,
    coverage jsonb NOT NULL,
    PRIMARY KEY (workspace_id, run_id),
    UNIQUE (workspace_id, request_id),
    FOREIGN KEY (workspace_id, connection_id) REFERENCES toolost_connections,
    FOREIGN KEY (workspace_id, principal_id) REFERENCES memberships
);
CREATE UNIQUE INDEX toolost_one_import ON toolost_import_runs(workspace_id, connection_id)
    WHERE status IN ('queued','running','retryable');
CREATE TABLE toolost_import_pages (
    workspace_id uuid NOT NULL,
    run_id uuid NOT NULL,
    resource text NOT NULL,
    page integer NOT NULL,
    fingerprint text NOT NULL,
    fetched_at timestamptz NOT NULL,
    PRIMARY KEY (workspace_id, run_id, resource, page),
    UNIQUE (workspace_id, run_id, resource, fingerprint),
    FOREIGN KEY (workspace_id, run_id) REFERENCES toolost_import_runs
);
CREATE TABLE toolost_source_facts (
    workspace_id uuid NOT NULL,
    run_id uuid NOT NULL,
    resource text NOT NULL,
    page integer NOT NULL,
    record_key text NOT NULL,
    payload jsonb NOT NULL,
    amount numeric,
    currency text CHECK (currency IS NULL),
    period_kind text NOT NULL DEFAULT 'unknown' CHECK (period_kind = 'unknown'),
    gross_net_basis text CHECK (gross_net_basis IS NULL),
    PRIMARY KEY (workspace_id, run_id, resource, record_key),
    FOREIGN KEY (workspace_id, run_id, resource, page) REFERENCES toolost_import_pages
);
CREATE TABLE toolost_quota (
    environment text NOT NULL,
    pool text NOT NULL,
    month_start timestamptz NOT NULL,
    month_calls integer NOT NULL DEFAULT 0,
    minute_start timestamptz NOT NULL,
    minute_calls integer NOT NULL DEFAULT 0,
    provider_remaining integer,
    blocked boolean NOT NULL DEFAULT false,
    pause_until timestamptz,
    PRIMARY KEY (environment, pool)
);
DO $$
DECLARE tab text;
BEGIN
    FOREACH tab IN ARRAY ARRAY['toolost_connections','toolost_oauth_attempts','toolost_import_runs','toolost_import_pages','toolost_source_facts'] LOOP
        EXECUTE format('ALTER TABLE %I ENABLE ROW LEVEL SECURITY', tab);
        EXECUTE format('ALTER TABLE %I FORCE ROW LEVEL SECURITY', tab);
        EXECUTE format('CREATE POLICY workspace_scope ON %I USING (workspace_id::text = current_setting(''space.workspace_id'', true)) WITH CHECK (workspace_id::text = current_setting(''space.workspace_id'', true))', tab);
    END LOOP;
END $$;
ALTER TABLE toolost_quota ENABLE ROW LEVEL SECURITY;
ALTER TABLE toolost_quota FORCE ROW LEVEL SECURITY;
CREATE POLICY pool_scope ON toolost_quota USING (
    environment = current_setting('space.toolost_environment', true)
    AND pool = current_setting('space.toolost_pool', true)
) WITH CHECK (
    environment = current_setting('space.toolost_environment', true)
    AND pool = current_setting('space.toolost_pool', true)
);
GRANT SELECT, INSERT, UPDATE ON toolost_connections, toolost_oauth_attempts, toolost_import_runs, toolost_quota TO review_runtime;
GRANT SELECT, INSERT ON toolost_import_pages, toolost_source_facts TO review_runtime;
