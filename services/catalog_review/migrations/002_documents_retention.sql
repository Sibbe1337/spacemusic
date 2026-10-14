ALTER TABLE workspaces ADD COLUMN last_activity_at timestamptz;
UPDATE workspaces SET last_activity_at=created_at;
ALTER TABLE workspaces ALTER COLUMN last_activity_at SET NOT NULL;
ALTER TABLE workspaces ADD COLUMN activity_version bigint NOT NULL DEFAULT 0;
ALTER TABLE workspaces ADD COLUMN notice_version bigint;
ALTER TABLE review_questions ADD COLUMN request_documents boolean NOT NULL DEFAULT false;
ALTER TABLE review_replies ADD COLUMN document_ids jsonb NOT NULL DEFAULT '[]'
    CHECK (jsonb_typeof(document_ids)='array' AND jsonb_array_length(document_ids)<=40);
ALTER TABLE documents ADD COLUMN question_id uuid;
ALTER TABLE documents ADD FOREIGN KEY (workspace_id, question_id) REFERENCES review_questions;
CREATE TABLE review_supplements (
    workspace_id uuid NOT NULL REFERENCES workspaces,
    supplement_id uuid NOT NULL,
    version integer NOT NULL CHECK (version>0),
    submission_id uuid NOT NULL REFERENCES submissions(submission_id),
    question_id uuid NOT NULL,
    documents jsonb NOT NULL CHECK (jsonb_typeof(documents)='array'),
    created_at timestamptz NOT NULL,
    PRIMARY KEY(workspace_id,supplement_id),
    UNIQUE(workspace_id,version),
    UNIQUE(workspace_id,question_id),
    FOREIGN KEY(workspace_id,question_id) REFERENCES review_replies
);
ALTER TABLE review_supplements ENABLE ROW LEVEL SECURITY;
ALTER TABLE review_supplements FORCE ROW LEVEL SECURITY;
CREATE POLICY workspace_scope ON review_supplements
    USING (workspace_id::text=current_setting('space.workspace_id',true))
    WITH CHECK (workspace_id::text=current_setting('space.workspace_id',true));
ALTER TABLE outbox DROP CONSTRAINT outbox_status_check;
ALTER TABLE outbox ADD CONSTRAINT outbox_status_check
    CHECK (status IN ('queued','leased','accepted','dead','uncertain','delivered','bounced'));
