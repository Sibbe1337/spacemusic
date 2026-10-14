-- Optional, explicit grants to the separately provisioned scoped erasure role.
-- Core owns that role's authentication, workspace/journal gate and core grants.
-- No ownership, BYPASSRLS, TRUNCATE, DDL or runtime-role grants are added here.
GRANT SELECT, DELETE ON toolost_source_facts, toolost_import_pages,
    toolost_import_runs, toolost_oauth_attempts, toolost_connections TO review_erasure;
GRANT UPDATE ON toolost_connections, toolost_import_runs TO review_erasure;
