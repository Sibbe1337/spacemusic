CREATE TABLE interest_events (
    workspace_id uuid NOT NULL REFERENCES workspaces,
    request_id uuid NOT NULL,
    PRIMARY KEY(workspace_id,request_id)
);
ALTER TABLE interest_events ENABLE ROW LEVEL SECURITY;
ALTER TABLE interest_events FORCE ROW LEVEL SECURITY;
CREATE POLICY workspace_scope ON interest_events
    USING(workspace_id::text=current_setting('space.workspace_id',true))
    WITH CHECK(workspace_id::text=current_setting('space.workspace_id',true));
