import hashlib
from dataclasses import replace
from pathlib import Path

import pytest
from psycopg2.pool import ThreadedConnectionPool
from test_operations_config import configuration

from services.catalog_review.database import CommitOutcomeUnknown
from services.catalog_review.operations.config import ConfigurationError
from services.catalog_review.operations.migrations import (
    Migration,
    MigrationError,
    load_pilot_plan,
    load_plan,
    plan_digest,
    run_migrations,
)
from services.catalog_review.operations.pool import PooledDatabase, PoolUnavailable


class Cursor:
    def __init__(self, connection):
        self.connection = connection
        self.statement = ""

    def __enter__(self):
        return self

    def __exit__(self, *_):
        pass

    def execute(self, statement, params=None):
        self.statement = statement
        self.connection.statements.append((statement, params))
        if self.connection.fail_discard and statement == "DISCARD ALL":
            raise RuntimeError("cleanup failed")
        if self.connection.fail_sql and statement == "SELECT 'migration'":
            raise RuntimeError("migration failed")

    def fetchone(self):
        if "pg_auth_members" in self.statement:
            return self.connection.erasure_membership
        if "WHERE rolname='review_erasure'" in self.statement:
            return self.connection.erasure_role
        if "current_database()" in self.statement:
            return self.connection.identity
        if "pg_try_advisory" in self.statement:
            return (self.connection.lock_available,)
        if "rolsuper" in self.statement:
            return {"rolsuper": self.connection.unsafe_role, "rolbypassrls": False}
        if "rolcreaterole" in self.statement:
            return {"rolcreaterole": False, "rolcreatedb": False}
        if "relrowsecurity" in self.statement and "WHERE oid=" in self.statement:
            return {"relrowsecurity": True, "relforcerowsecurity": True}
        if "has_table_privilege" in self.statement:
            return {"allowed": False}
        if " AS relation" in self.statement:
            return {"relation": None}
        return None

    def fetchall(self):
        return self.connection.history


class Connection:
    def __init__(self):
        self.closed = False
        self.autocommit = False
        self.statements = []
        self.commits = 0
        self.rollbacks = 0
        self.fail_commit = self.fail_rollback = self.fail_discard = self.fail_sql = (
            False
        )
        self.unsafe_role = False
        self.identity = ("review_migration", "review_prod", False, False)
        self.lock_available = True
        self.history = []
        self.erasure_role = (False, False, False, False, False, True)
        self.erasure_membership = None

    def cursor(self, **_):
        return Cursor(self)

    def commit(self):
        self.commits += 1
        if self.fail_commit:
            raise RuntimeError("commit acknowledgement lost")

    def rollback(self):
        self.rollbacks += 1
        if self.fail_rollback:
            raise RuntimeError("rollback acknowledgement lost")

    def close(self):
        self.closed = True


class Pool:
    def __init__(self, connection=None):
        self.connection = connection or Connection()
        self.returned = []
        self.closed = False
        self.get_failure = False

    def factory(self, minconn, maxconn, **kwargs):
        self.bounds = (minconn, maxconn)
        self.kwargs = kwargs
        return self

    def getconn(self):
        if self.get_failure:
            raise RuntimeError("secret connection failure")
        return self.connection

    def putconn(self, connection, close=False):
        self.returned.append(close)
        if close:
            connection.close()

    def closeall(self):
        self.closed = True


def database():
    pool = Pool()
    config = replace(
        configuration().database, max_connections=1, checkout_timeout_seconds=0.01
    )
    return PooledDatabase(config, pool_factory=pool.factory), pool


def test_pool_bounds_tls_and_transaction_workspace(monkeypatch):
    monkeypatch.setenv("DATABASE_URL", "postgres://secret@external.example/db")
    db, pool = database()
    assert pool.bounds == (1, 1)
    assert pool.kwargs["sslmode"] == "verify-full"
    assert pool.kwargs["host"] == "10.2.0.3"
    workspace = "cad910bd-d86e-4a55-a680-8c7808a727ee"
    with db.transaction(workspace):
        with pytest.raises(PoolUnavailable, match="exhausted"):
            with db.transaction():
                pass
        with pytest.raises(PoolUnavailable, match="drain"):
            db.close()
    assert (
        "SELECT set_config('space.workspace_id', %s, true)",
        (workspace,),
    ) in pool.connection.statements
    assert pool.connection.statements[-1][0] == "DISCARD ALL"
    with db.transaction():
        pass
    assert (
        "SELECT set_config('space.workspace_id', %s, true)",
        ("",),
    ) in pool.connection.statements
    db.close()
    db.close()
    with pytest.raises(PoolUnavailable, match="closed"):
        with db.transaction():
            pass


def test_pool_rejects_unsafe_role_and_closes_on_failed_startup():
    pool = Pool()
    pool.connection.unsafe_role = True
    with pytest.raises(RuntimeError, match="bypass"):
        PooledDatabase(configuration().database, pool_factory=pool.factory)
    assert pool.closed


@pytest.mark.parametrize("failure", ["fail_commit", "fail_rollback"])
def test_pool_preserves_unknown_outcome_and_discards_connection(failure):
    db, pool = database()
    setattr(pool.connection, failure, True)
    with pytest.raises(CommitOutcomeUnknown):
        with db.transaction():
            if failure == "fail_rollback":
                raise RuntimeError("operation failed")
    assert pool.returned[-1] is True
    assert pool.connection.closed
    db.close()


def test_known_commit_is_not_reclassified_when_cleanup_fails():
    db, pool = database()
    pool.connection.fail_discard = True
    with db.transaction():
        pass
    assert pool.returned[-1] is True
    db.close()


def test_exception_rolls_back_and_failed_checkout_releases_capacity():
    db, pool = database()
    with pytest.raises(ValueError, match="business error"):
        with db.transaction():
            raise ValueError("business error")
    assert pool.connection.rollbacks > 0
    pool.get_failure = True
    with pytest.raises(PoolUnavailable, match="unavailable"):
        with db.transaction():
            pass
    pool.get_failure = False
    with db.transaction():
        pass
    db.close()


def test_real_postgres_tenant_and_session_state_do_not_leak(backend):
    config = replace(configuration().database, max_connections=1)

    def factory(minconn, maxconn, **_):
        return ThreadedConnectionPool(minconn, maxconn, backend.test_runtime_dsn)

    db = PooledDatabase(config, pool_factory=factory)
    workspace = "cad910bd-d86e-4a55-a680-8c7808a727ee"
    try:
        with db.transaction(workspace) as cur:
            cur.execute("SELECT current_setting('space.workspace_id') AS workspace")
            assert cur.fetchone()["workspace"] == workspace
            cur.execute("CREATE TEMP TABLE tenant_leak_probe(id integer)")
            cur.execute("SELECT pg_advisory_lock(52963)")
        with db.transaction() as cur:
            cur.execute(
                "SELECT current_setting('space.workspace_id') AS workspace, to_regclass('pg_temp.tenant_leak_probe') AS temporary"
            )
            row = cur.fetchone()
            assert row == {"workspace": "", "temporary": None}
            cur.execute(
                "SELECT count(*) AS count FROM pg_locks WHERE pid=pg_backend_pid() AND locktype='advisory'"
            )
            assert cur.fetchone()["count"] == 0
    finally:
        db.close()


def migration(name="001_test.sql", text="SELECT 'migration'"):
    return Migration(name, text, hashlib.sha256(text.encode()).hexdigest())


def execute(connection, migrations=None, grants=None, **overrides):
    migrations = migrations or (migration(),)
    grants = grants or migration("9999_grants.sql", "SELECT 'grants'")
    config = replace(
        configuration().database,
        user="review_migration",
        passfile="/run/secrets/migration-pgpass",
    )
    kwargs = dict(
        expected_plan_sha256=plan_digest(migrations, grants),
        connect=lambda **_: connection,
    )
    kwargs.update(overrides)
    return run_migrations(config, migrations, grants, **kwargs)


def test_migration_applies_checksum_ledger_then_grants_and_closes():
    connection = Connection()
    assert execute(connection) == 1
    sql = [item[0] for item in connection.statements]
    assert sql[-1] == "SELECT 'grants'"
    assert sql.index("SELECT 'migration'") < sql.index("SELECT 'grants'")
    assert connection.commits == 1 and connection.closed


def test_migration_reapplication_is_noop_except_grants():
    connection = Connection()
    item = migration()
    connection.history = [(item.name, item.sha256)]
    assert execute(connection) == 0
    assert "SELECT 'migration'" not in [item[0] for item in connection.statements]


@pytest.mark.parametrize(
    "history", [[("001_test.sql", "f" * 64)], [("999_unknown.sql", "a" * 64)]]
)
def test_migration_refuses_history_drift(history):
    connection = Connection()
    connection.history = history
    with pytest.raises(MigrationError, match="drift"):
        execute(connection)
    assert connection.rollbacks == 1 and connection.closed and not connection.commits


@pytest.mark.parametrize(
    "failure", ["lock", "role", "database", "sql", "commit", "rollback"]
)
def test_migration_failure_is_closed_and_not_automatically_retried(failure):
    connection = Connection()
    if failure == "lock":
        connection.lock_available = False
    elif failure == "role":
        connection.identity = ("review_migration", "review_prod", True, False)
    elif failure == "database":
        connection.identity = ("review_migration", "wrong", False, False)
    else:
        setattr(connection, "fail_" + failure, True)
        if failure == "rollback":
            connection.fail_sql = True
    with pytest.raises((MigrationError, RuntimeError, CommitOutcomeUnknown)):
        execute(connection)
    assert connection.closed
    assert connection.commits <= 1


def test_unapproved_plan_never_connects():
    connection = Connection()
    with pytest.raises(ConfigurationError, match="unapproved"):
        execute(connection, expected_plan_sha256="f" * 64)
    assert not connection.statements and not connection.closed


def test_plan_loads_baseline_sorted_migrations_then_grants(tmp_path):
    (tmp_path / "schema.sql").write_text("DO $$ BEGIN PERFORM 1; END $$;")
    (tmp_path / "grants.sql").write_text("SELECT 1;")
    directory = tmp_path / "migrations"
    directory.mkdir()
    (directory / "002_documents_retention.sql").write_text("SELECT 2;")
    (directory / "001_first.sql").write_text("SELECT 1;")
    migrations, grants = load_plan(tmp_path)
    assert [item.name for item in migrations] == [
        "000_baseline.sql",
        "001_first.sql",
        "002_documents_retention.sql",
    ]
    assert grants.name == "9999_runtime_grants.sql"
    (directory / "003_bad.sql").write_text("COMMIT;")
    with pytest.raises(ConfigurationError, match="transaction_control"):
        load_plan(tmp_path)


def test_script_checksum_size_and_symlink_rejected(tmp_path):
    with pytest.raises(ConfigurationError):
        replace(migration(), sha256="f" * 64).validate()
    with pytest.raises(ConfigurationError):
        migration(text="x" * (1024 * 1024 + 1)).validate()
    (tmp_path / "schema.sql").symlink_to("/not/read")
    with pytest.raises(ConfigurationError, match="symlink"):
        load_plan(tmp_path)


SOURCE = Path(__file__).resolve().parents[2] / "services/catalog_review"


def test_pilot_plan_includes_original_extension_sql_and_scoped_grants():
    baseline, _ = load_plan(SOURCE)
    scripts, grants = load_pilot_plan(SOURCE)
    assert scripts[: len(baseline)] == baseline
    assert [item.name for item in scripts[-2:]] == [
        "8000_intake_schema.sql",
        "8100_staff_schema.sql",
    ]
    assert scripts[-2].sql == (SOURCE / "intake-schema.sql").read_text()
    assert scripts[-1].sql == (SOURCE / "staff/schema.sql").read_text()
    assert "TO catalog_staff_runtime" not in grants.sql
    assert "ON SCHEMA catalog_staff TO review_runtime" in grants.sql
    assert (SOURCE / "erasure-grants.sql").read_text() in grants.sql
    staff_erasure = (
        (SOURCE / "staff/erasure-grants.sql")
        .read_text()
        .replace("catalog_staff_erasure", "review_erasure")
    )
    assert staff_erasure in grants.sql
    assert "TO catalog_staff_erasure" not in grants.sql
    assert (
        "GRANT DELETE ON catalog_staff.assignments TO review_runtime" not in grants.sql
    )
    assert (
        "GRANT DELETE ON intake_inbox, portal_mail_attempts TO review_erasure"
        in grants.sql
    )
    assert not any("provider" in item.name for item in scripts)
    separate, separate_grants = load_pilot_plan(
        SOURCE, staff_runtime_role="catalog_staff_runtime"
    )
    assert separate == scripts
    assert "ON SCHEMA catalog_staff TO catalog_staff_runtime" in separate_grants.sql
    assert plan_digest(scripts, grants) != plan_digest(separate, separate_grants)


def test_optional_provider_schema_is_checksum_bound_not_enabled_by_default():
    scripts, grants = load_pilot_plan(SOURCE, include_providers=True)
    assert scripts[-1].sql == (SOURCE / "providers/schema.sql").read_text()
    assert scripts[-1].name == "8200_provider_schema.sql"
    assert (SOURCE / "providers/erasure-grants.sql").read_text() in grants.sql


@pytest.mark.parametrize(
    "role", ["postgres", "review_runtime; GRANT ALL", "review_erasure", ""]
)
def test_staff_grants_role_rejects_unapproved_identifiers(role):
    with pytest.raises(ConfigurationError, match="staff_runtime_role"):
        load_pilot_plan(SOURCE, staff_runtime_role=role)


def test_pilot_plan_cannot_silently_skip_missing_staff_or_erasure_sql(tmp_path):
    for source in ("schema.sql", "grants.sql", "intake-schema.sql"):
        (tmp_path / source).write_text("SELECT 1;")
    with pytest.raises(FileNotFoundError):
        load_pilot_plan(tmp_path)
    (tmp_path / "staff").mkdir()
    (tmp_path / "staff/schema.sql").write_text("SELECT 1;")
    (tmp_path / "staff/grants.sql").write_text("SELECT 1;")
    with pytest.raises(FileNotFoundError):
        load_pilot_plan(tmp_path)
    (tmp_path / "erasure-grants.sql").write_text("SELECT 1;")
    with pytest.raises(FileNotFoundError):
        load_pilot_plan(tmp_path)


def test_later_core_migration_can_follow_previously_applied_extensions():
    connection = Connection()
    first = migration()
    later = migration("002_later.sql", "SELECT 'later'")
    intake = migration("8000_intake_schema.sql", "SELECT 'intake'")
    staff = migration("8100_staff_schema.sql", "SELECT 'staff'")
    connection.history = [(item.name, item.sha256) for item in (first, intake, staff)]
    assert execute(connection, (first, later, intake, staff)) == 1
    statements = [statement for statement, _ in connection.statements]
    assert (
        later.sql in statements
        and first.sql not in statements
        and intake.sql not in statements
    )


@pytest.mark.parametrize(
    "erasure_role",
    [
        None,
        (True, False, False, False, False, True),
        (False, True, False, False, False, True),
        (False, False, True, False, False, True),
        (False, False, False, True, False, True),
        (False, False, False, False, True, True),
        (False, False, False, False, False, False),
    ],
)
def test_pilot_requires_separate_restricted_login_erasure_role(erasure_role):
    connection = Connection()
    connection.erasure_role = erasure_role
    with pytest.raises(MigrationError, match="restricted_erasure_role"):
        execute(connection, (migration("8000_intake_schema.sql"),))
    assert not connection.commits


def test_erasure_role_cannot_inherit_or_set_another_role():
    connection = Connection()
    connection.erasure_membership = (1,)
    with pytest.raises(MigrationError, match="membership"):
        execute(connection, (migration("8000_intake_schema.sql"),))
