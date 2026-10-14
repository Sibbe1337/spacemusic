-- Provision review_erasure separately as LOGIN NOSUPERUSER NOBYPASSRLS
-- NOCREATEDB NOCREATEROLE NOINHERIT. Never mount this credential in the API.
GRANT USAGE ON SCHEMA public TO review_erasure;
GRANT SELECT, DELETE ON workspaces, memberships, invitations, sessions, outbox,
    documents, submissions, audit, review_questions, review_replies,
    review_supplements, interest_events, retention_notices TO review_erasure;
GRANT SELECT ON receipts TO review_erasure;
-- PostgreSQL requires an UPDATE privilege to acquire FOR UPDATE row locks.
GRANT UPDATE(status) ON workspaces TO review_erasure;
GRANT SELECT, DELETE ON staff_session_links TO review_erasure;
GRANT SELECT, DELETE ON dealflow_reviews, dealflow_packages, dealflow_decisions TO review_erasure;
