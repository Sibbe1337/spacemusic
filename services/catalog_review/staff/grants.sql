-- Create catalog_staff_runtime separately with NOSUPERUSER NOBYPASSRLS
-- NOCREATEROLE NOCREATEDB and no membership in owner/admin roles.
GRANT USAGE ON SCHEMA catalog_staff TO catalog_staff_runtime;
GRANT SELECT ON ALL TABLES IN SCHEMA catalog_staff TO catalog_staff_runtime;
GRANT UPDATE (state) ON catalog_staff.principals TO catalog_staff_runtime;
GRANT UPDATE (consumed_at) ON catalog_staff.enrollment_permits TO catalog_staff_runtime;
GRANT INSERT ON catalog_staff.credentials TO catalog_staff_runtime;
GRANT UPDATE (sign_count,confirmed_at) ON catalog_staff.credentials TO catalog_staff_runtime;
GRANT INSERT ON catalog_staff.sessions TO catalog_staff_runtime;
GRANT UPDATE (revoked_at,uv_at,uv_credential_id) ON catalog_staff.sessions TO catalog_staff_runtime;
GRANT INSERT ON catalog_staff.challenges TO catalog_staff_runtime;
GRANT UPDATE (consumed_at) ON catalog_staff.challenges TO catalog_staff_runtime;
GRANT INSERT ON catalog_staff.audit TO catalog_staff_runtime;
-- No assignment/provisioning/permit INSERT rights, DELETE, TRUNCATE, or DDL.
