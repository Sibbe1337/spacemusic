CREATE TABLE retention_notices (
    workspace_id uuid NOT NULL REFERENCES workspaces,
    activity_version bigint NOT NULL,
    deadline timestamptz NOT NULL,
    status text NOT NULL DEFAULT 'queued' CHECK(status IN ('queued','uncertain','accepted','delivered','bounced','cancelled')),
    created_at timestamptz NOT NULL,
    PRIMARY KEY(workspace_id,activity_version)
);
ALTER TABLE retention_notices ENABLE ROW LEVEL SECURITY;
ALTER TABLE retention_notices FORCE ROW LEVEL SECURITY;
CREATE POLICY workspace_scope ON retention_notices
    USING(workspace_id::text=current_setting('space.workspace_id',true))
    WITH CHECK(workspace_id::text=current_setting('space.workspace_id',true));
