-- Dedicated erasure worker only; never grant these to the HTTP runtime role.
GRANT USAGE ON SCHEMA catalog_staff TO catalog_staff_erasure;
GRANT SELECT (workspace_id) ON catalog_staff.assignments TO catalog_staff_erasure;
GRANT DELETE ON catalog_staff.assignments TO catalog_staff_erasure;
