CREATE TABLE staff_session_links (
    workspace_id uuid NOT NULL,
    token_digest text NOT NULL,
    staff_session_digest text NOT NULL,
    PRIMARY KEY(workspace_id,token_digest),
    FOREIGN KEY(workspace_id,token_digest) REFERENCES sessions ON DELETE CASCADE
);
ALTER TABLE staff_session_links ENABLE ROW LEVEL SECURITY;
ALTER TABLE staff_session_links FORCE ROW LEVEL SECURITY;
CREATE POLICY workspace_scope ON staff_session_links
    USING(workspace_id::text=current_setting('space.workspace_id',true))
    WITH CHECK(workspace_id::text=current_setting('space.workspace_id',true));
