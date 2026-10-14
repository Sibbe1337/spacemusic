-- The migration harness creates review_runtime separately. Never give this role
-- ownership, BYPASSRLS, role-management privileges or migration credentials.
REVOKE CREATE ON SCHEMA public FROM PUBLIC;
GRANT USAGE ON SCHEMA public TO review_runtime;
GRANT SELECT, INSERT ON receipts, submissions, audit, review_questions, review_replies TO review_runtime;
GRANT SELECT, INSERT ON review_supplements TO review_runtime;
GRANT SELECT, INSERT ON interest_events TO review_runtime;
GRANT SELECT, INSERT, UPDATE ON retention_notices TO review_runtime;
GRANT SELECT, INSERT ON staff_session_links TO review_runtime;
GRANT SELECT, INSERT ON dealflow_reviews, dealflow_packages, dealflow_decisions TO review_runtime;
GRANT SELECT, INSERT, UPDATE ON workspaces, memberships, invitations, outbox, documents TO review_runtime;
GRANT SELECT, INSERT, UPDATE, DELETE ON sessions, auth_limits TO review_runtime;
