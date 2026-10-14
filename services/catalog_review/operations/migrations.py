"""Separate, checksum-bound migration job; never run from API startup.

SQL is trusted release code, not user input. Each script must be transaction-safe
(no COMMIT/ROLLBACK/VACUUM/CREATE INDEX CONCURRENTLY or external side effects).
https://www.postgresql.org/docs/current/explicit-locking.html#ADVISORY-LOCKS
"""

import hashlib
import re
from dataclasses import dataclass
from pathlib import Path

import psycopg2

from ..database import CommitOutcomeUnknown
from .config import require, sha256_value

LOCK_ID = 734608132
MAX_SCRIPT_BYTES = 1024 * 1024
EXTENSION_NAMES = frozenset(
    {"8000_intake_schema.sql", "8100_staff_schema.sql", "8200_provider_schema.sql"}
)


class MigrationError(RuntimeError):
    pass


@dataclass(frozen=True)
class Migration:
    name: str
    sql: str
    sha256: str

    def validate(self):
        require(
            isinstance(self.name, str)
            and re.fullmatch(r"[0-9]{3,4}_[a-z0-9_]+\.sql", self.name),
            "invalid_migration_name",
        )
        require(
            isinstance(self.sql, str)
            and 0 < len(self.sql.encode()) <= MAX_SCRIPT_BYTES,
            "invalid_migration_size",
        )
        require(
            sha256_value(self.sha256)
            and hashlib.sha256(self.sql.encode()).hexdigest() == self.sha256,
            "migration_checksum_mismatch",
        )
        # Catch accidental explicit transaction control. This is not an SQL
        # sandbox: release review must reject non-transactional SQL in functions.
        top_level = re.sub(
            r"(?s)(\$[a-zA-Z_0-9]*\$).*?\1|'(?:''|[^'])*'|--[^\n]*|/\*.*?\*/",
            " ",
            self.sql,
        )
        require(
            not re.search(
                r"(?im)(?:^|;)\s*(?:COMMIT|ROLLBACK|END|BEGIN|START\s+TRANSACTION)\b",
                top_level,
            ),
            "migration_transaction_control_forbidden",
        )
        return self


def _read(path, name):
    require(not path.is_symlink(), "migration_symlink_forbidden")
    with path.open("rb") as stream:
        content = stream.read(MAX_SCRIPT_BYTES + 1)
    require(len(content) <= MAX_SCRIPT_BYTES, "invalid_migration_size")
    text = content.decode("utf-8")
    return Migration(name, text, hashlib.sha256(content).hexdigest()).validate()


def load_plan(root):
    """Baseline once, then sorted migrations; grants are reapplied last each run."""
    root = Path(root)
    baseline = _read(root / "schema.sql", "000_baseline.sql")
    paths = sorted((root / "migrations").glob("*.sql"))
    require(len(paths) <= 128, "too_many_migrations")
    migrations = (baseline,) + tuple(_read(path, path.name) for path in paths)
    names = [item.name for item in migrations]
    require(names == sorted(set(names)), "migration_order_invalid")
    require(
        len({name.split("_", 1)[0] for name in names}) == len(names),
        "migration_version_reused",
    )
    grants = _read(root / "grants.sql", "9999_runtime_grants.sql")
    require(
        sum(len(item.sql.encode()) for item in migrations + (grants,))
        <= 4 * MAX_SCRIPT_BYTES,
        "migration_plan_too_large",
    )
    return migrations, grants


def load_pilot_plan(
    root, *, staff_runtime_role="review_runtime", include_providers=False
):
    """Reference original SQL in place; never copy shared schemas or use fixtures.

    The core numbering range is below 8000. Extension anchors run after core SQL on
    initialization, exactly once. Later core migrations remain append-only within
    their own sequence, even though extension anchors have already been recorded.
    """
    require(
        staff_runtime_role in ("review_runtime", "catalog_staff_runtime"),
        "invalid_staff_runtime_role",
    )
    require(type(include_providers) is bool, "invalid_provider_selection")
    root = Path(root)
    core, core_grants = load_plan(root)
    require(
        all(int(item.name.split("_", 1)[0]) < 8000 for item in core),
        "reserved_migration_number",
    )
    scripts = core + (
        _read(root / "intake-schema.sql", "8000_intake_schema.sql"),
        _read(root / "staff" / "schema.sql", "8100_staff_schema.sql"),
    )
    staff = _read(root / "staff" / "grants.sql", "9999_staff_grants.sql")
    staff_erasure = _read(
        root / "staff" / "erasure-grants.sql", "9999_staff_erasure_grants.sql"
    )
    erasure = _read(root / "erasure-grants.sql", "9999_erasure_grants.sql")
    grant_parts = [
        core_grants.sql,
        re.sub(r"\bcatalog_staff_runtime\b", staff_runtime_role, staff.sql),
        erasure.sql,
        re.sub(r"\bcatalog_staff_erasure\b", "review_erasure", staff_erasure.sql),
    ]
    # Exact minimum rights documented by intake-schema.sql for the independently
    # authenticated erasure job, never the API role. Workspace checks/journal
    # binding remain mandatory inside that job for the global intake indexes.
    grant_parts.append("""
GRANT SELECT ON intake_inbox, intake_admissions TO review_erasure;
GRANT SELECT(workspace_id) ON portal_mail_attempts TO review_erasure;
GRANT DELETE ON intake_inbox, portal_mail_attempts TO review_erasure;
GRANT UPDATE(payload_cipher) ON intake_inbox TO review_erasure;
GRANT UPDATE(intake_id,workspace_id,request_id,approved_by,erased_at)
    ON intake_admissions TO review_erasure;
""")
    if include_providers:
        scripts += (
            _read(root / "providers" / "schema.sql", "8200_provider_schema.sql"),
        )
        grant_parts.append(
            _read(
                root / "providers" / "erasure-grants.sql",
                "9999_provider_erasure_grants.sql",
            ).sql
        )
    text = "\n".join(grant_parts)
    grants = Migration(
        "9999_pilot_grants.sql", text, hashlib.sha256(text.encode()).hexdigest()
    ).validate()
    require(
        sum(len(item.sql.encode()) for item in scripts + (grants,))
        <= 4 * MAX_SCRIPT_BYTES,
        "migration_plan_too_large",
    )
    return scripts, grants


def plan_digest(migrations, grants):
    values = []
    for item in tuple(migrations) + (grants,):
        item.validate()
        values.append(item.name + ":" + item.sha256)
    return hashlib.sha256("\n".join(values).encode()).hexdigest()


def run_migrations(
    config, migrations, grants, *, expected_plan_sha256, connect=psycopg2.connect
):
    config.validate()
    require(config.user == "review_migration", "migration_role_required")
    migrations = tuple(migrations)
    require(1 <= len(migrations) <= 129, "invalid_migration_count")
    require(
        [m.name for m in migrations] == sorted({m.name for m in migrations}),
        "migration_order_invalid",
    )
    require(
        sha256_value(expected_plan_sha256)
        and plan_digest(migrations, grants) == expected_plan_sha256,
        "unapproved_migration_plan",
    )
    connection = connect(**config.connect_kwargs())
    try:
        require(connection.autocommit is False, "migration_transaction_required")
        with connection.cursor() as cursor:
            cursor.execute(
                "SELECT current_user, current_database(), rolsuper, rolbypassrls FROM pg_roles WHERE rolname=current_user"
            )
            role, database, superuser, bypass = cursor.fetchone()
            if role != config.user or database != config.dbname or superuser or bypass:
                raise MigrationError("migration_connection_identity_invalid")
            cursor.execute("SELECT pg_try_advisory_xact_lock(%s)", (LOCK_ID,))
            if cursor.fetchone()[0] is not True:
                raise MigrationError("migration_already_running")
            if any(item.name in EXTENSION_NAMES for item in migrations):
                cursor.execute("""SELECT rolsuper, rolbypassrls, rolcreaterole, rolcreatedb, rolinherit, rolcanlogin
                    FROM pg_roles WHERE rolname='review_erasure'""")
                erasure = cursor.fetchone()
                if not erasure or any(erasure[:5]) or erasure[5] is not True:
                    raise MigrationError("restricted_erasure_role_required")
                cursor.execute("""SELECT 1 FROM pg_auth_members WHERE member=
                    (SELECT oid FROM pg_roles WHERE rolname='review_erasure')""")
                if cursor.fetchone():
                    raise MigrationError("erasure_role_membership_forbidden")
            cursor.execute("SET LOCAL statement_timeout TO '60s'")
            cursor.execute("SET LOCAL lock_timeout TO '3s'")
            cursor.execute("CREATE SCHEMA IF NOT EXISTS catalog_review_operations")
            cursor.execute("REVOKE ALL ON SCHEMA catalog_review_operations FROM PUBLIC")
            cursor.execute("""CREATE TABLE IF NOT EXISTS catalog_review_operations.migrations (
                name text PRIMARY KEY, sha256 text NOT NULL,
                applied_at timestamptz NOT NULL DEFAULT now())""")
            cursor.execute(
                "SELECT name, sha256 FROM catalog_review_operations.migrations ORDER BY name"
            )
            applied = cursor.fetchall()
            desired = [(item.name, item.sha256) for item in migrations]
            desired_map = dict(desired)
            applied_core = [row for row in applied if row[0] not in EXTENSION_NAMES]
            desired_core = [row for row in desired if row[0] not in EXTENSION_NAMES]
            if (
                any(desired_map.get(name) != digest for name, digest in applied)
                or applied_core != desired_core[: len(applied_core)]
            ):
                raise MigrationError("migration_history_drift")
            pending = [item for item in migrations if item.name not in dict(applied)]
            for item in pending:
                cursor.execute(item.sql)
                cursor.execute(
                    "INSERT INTO catalog_review_operations.migrations(name,sha256) VALUES (%s,%s)",
                    (item.name, item.sha256),
                )
            cursor.execute(grants.sql)
        try:
            connection.commit()
        except BaseException:
            raise CommitOutcomeUnknown(
                "Migration commit unconfirmed; inspect ledger before retry"
            ) from None
        return len(pending)
    except CommitOutcomeUnknown:
        raise
    except BaseException:
        try:
            connection.rollback()
        except BaseException:
            raise CommitOutcomeUnknown(
                "Migration rollback unconfirmed; inspect ledger"
            ) from None
        raise
    finally:
        try:
            connection.close()
        except BaseException:
            pass
