-- Apply separately as a migration owner. Never apply to the public/core schema.
CREATE SCHEMA catalog_staff;
REVOKE ALL ON SCHEMA catalog_staff FROM PUBLIC;

CREATE TABLE catalog_staff.principals (
    principal_id uuid PRIMARY KEY,
    issuer text NOT NULL CHECK (issuer = 'https://accounts.google.com'),
    subject text NOT NULL CHECK (length(subject) BETWEEN 1 AND 255),
    display_name text NOT NULL CHECK (length(display_name) BETWEEN 1 AND 120),
    role text NOT NULL DEFAULT 'reviewer' CHECK (role IN ('reviewer','operator')),
    state text NOT NULL DEFAULT 'enrolling' CHECK (state IN ('enrolling','active','suspended')),
    enrollment_epoch integer NOT NULL DEFAULT 0 CHECK (enrollment_epoch >= 0),
    UNIQUE (issuer, subject)
);
CREATE TABLE catalog_staff.enrollment_permits (
    permit_digest text PRIMARY KEY,
    principal_id uuid NOT NULL REFERENCES catalog_staff.principals,
    enrollment_epoch integer NOT NULL,
    generation uuid NOT NULL,
    slot text NOT NULL CHECK (slot IN ('primary','backup')),
    supervision_reference text NOT NULL CHECK (length(supervision_reference) BETWEEN 1 AND 200),
    expires_at timestamptz NOT NULL,
    consumed_at timestamptz
);
CREATE TABLE catalog_staff.credentials (
    credential_id bytea PRIMARY KEY CHECK (octet_length(credential_id) BETWEEN 16 AND 1024),
    principal_id uuid NOT NULL REFERENCES catalog_staff.principals,
    slot text NOT NULL CHECK (slot IN ('primary','backup')),
    public_key bytea NOT NULL,
    public_key_digest text NOT NULL UNIQUE,
    sign_count bigint NOT NULL CHECK (sign_count >= 0),
    permit_digest text NOT NULL UNIQUE REFERENCES catalog_staff.enrollment_permits,
    active boolean NOT NULL DEFAULT true,
    confirmed_at timestamptz,
    UNIQUE (principal_id, credential_id)
);
CREATE UNIQUE INDEX staff_active_slot ON catalog_staff.credentials(principal_id,slot) WHERE active;
CREATE TABLE catalog_staff.sessions (
    session_digest text PRIMARY KEY,
    principal_id uuid NOT NULL REFERENCES catalog_staff.principals,
    enrollment_epoch integer NOT NULL,
    generation uuid NOT NULL,
    created_at timestamptz NOT NULL,
    expires_at timestamptz NOT NULL,
    revoked_at timestamptz,
    uv_at timestamptz,
    uv_credential_id bytea,
    FOREIGN KEY (principal_id,uv_credential_id) REFERENCES catalog_staff.credentials(principal_id,credential_id),
    CHECK ((uv_at IS NULL) = (uv_credential_id IS NULL))
);
CREATE TABLE catalog_staff.challenges (
    challenge_id uuid PRIMARY KEY,
    kind text NOT NULL CHECK (kind IN ('oidc','enroll','confirm','authenticate')),
    binding_digest text NOT NULL,
    generation uuid NOT NULL,
    payload jsonb NOT NULL CHECK (jsonb_typeof(payload) = 'object'),
    created_at timestamptz NOT NULL,
    expires_at timestamptz NOT NULL,
    consumed_at timestamptz
);
CREATE INDEX staff_challenge_expiry ON catalog_staff.challenges(expires_at);
CREATE TABLE catalog_staff.assignments (
    principal_id uuid NOT NULL REFERENCES catalog_staff.principals,
    workspace_id uuid NOT NULL,
    active boolean NOT NULL,
    PRIMARY KEY (principal_id,workspace_id)
);
CREATE TABLE catalog_staff.audit (
    event_id uuid PRIMARY KEY,
    principal_id uuid REFERENCES catalog_staff.principals,
    action text NOT NULL CHECK (action IN (
        'preapproved','enrollment_approved','credential_registered','credential_confirmed',
        'enrollment_completed','oidc_authenticated','uv_verified','session_revoked',
        'principal_suspended','enrollment_reset','assignment_changed','role_changed')),
    reference text CHECK (length(reference) BETWEEN 1 AND 200),
    created_at timestamptz NOT NULL
);
