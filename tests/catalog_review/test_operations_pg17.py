"""Opt-in local Docker PG17 integration; synthetic data and no cloud access.

REVIEW_RUN_PG17_SMOKE=1 enables this test. It never pulls images, mounts files,
or starts application/scanner services. Only host-loopback PostgreSQL traffic
is used; no external requests are made. Docker's bridge is needed because
Docker Desktop does not publish ports on internal/network-none containers.
"""

import json
import os
import subprocess
import time
from contextlib import closing
from dataclasses import replace
from pathlib import Path
from uuid import uuid4

import psycopg2
import pytest
from psycopg2.pool import ThreadedConnectionPool
from test_operations_config import configuration

from services.catalog_review.operations.migrations import (
    load_pilot_plan,
    plan_digest,
    run_migrations,
)
from services.catalog_review.operations.pool import PooledDatabase
from services.catalog_review.staff.erasure import StaffErasureParticipant


def docker(*args, check=True, **kwargs):
    result = subprocess.run(
        ["docker", *args],
        check=False,
        text=True,
        capture_output=True,
        timeout=60,
        **kwargs,
    )
    if check:
        assert result.returncode == 0, result.stderr
    return result


@pytest.fixture
def postgres17():
    if os.environ.get("REVIEW_RUN_PG17_SMOKE") != "1":
        pytest.skip("explicit local PG17 smoke opt-in required")
    assert not os.environ.get("DOCKER_HOST") and not os.environ.get("DOCKER_CONTEXT")
    context = json.loads(docker("context", "inspect").stdout)[0]
    assert context["Endpoints"]["docker"]["Host"].startswith("unix://"), (
        "local Docker socket required"
    )
    image = json.loads(docker("image", "inspect", "postgres:17").stdout)[0]["Id"]
    name = "catalog-review-pg17-test-" + uuid4().hex
    try:
        docker(
            "run",
            "--detach",
            "--pull=never",
            "--name",
            name,
            "--network",
            "bridge",
            "--publish",
            "127.0.0.1::5432",
            "--memory",
            "512m",
            "--pids-limit",
            "128",
            "--tmpfs",
            "/var/lib/postgresql/data:rw,size=268435456",
            "--env",
            "POSTGRES_HOST_AUTH_METHOD=trust",
            image,
        )
        for _ in range(100):
            if (
                docker(
                    "exec",
                    name,
                    "pg_isready",
                    "-h",
                    "127.0.0.1",
                    "-U",
                    "postgres",
                    check=False,
                ).returncode
                == 0
            ):
                break
            time.sleep(0.1)
        else:
            pytest.fail("isolated PG17 did not become ready")
        details = json.loads(docker("inspect", name).stdout)[0]
        assert not details["Mounts"] or all(
            m["Type"] == "tmpfs" for m in details["Mounts"]
        )
        binding = details["NetworkSettings"]["Ports"]["5432/tcp"][0]
        assert binding["HostIp"] == "127.0.0.1"
        port = int(binding["HostPort"])
        docker(
            "exec",
            "-i",
            name,
            "psql",
            "-U",
            "postgres",
            "-v",
            "ON_ERROR_STOP=1",
            input="""
CREATE ROLE review_migration LOGIN NOSUPERUSER NOBYPASSRLS NOCREATEDB NOCREATEROLE;
CREATE ROLE review_runtime LOGIN NOSUPERUSER NOBYPASSRLS NOCREATEDB NOCREATEROLE;
CREATE ROLE review_erasure LOGIN NOSUPERUSER NOBYPASSRLS NOCREATEDB NOCREATEROLE NOINHERIT;
CREATE DATABASE review_staging OWNER review_migration;
""",
        )
        yield dict(
            host="127.0.0.1", port=port, dbname="review_staging", connect_timeout=5
        )
    finally:
        docker("rm", "--force", "--volumes", name, check=False)


def test_pg17_full_pilot_migrations_rerun_pool_rls_and_rollback(postgres17):
    config = replace(
        configuration().database, dbname="review_staging", user="review_migration"
    )
    source = Path(__file__).resolve().parents[2] / "services/catalog_review"
    plan, grants = load_pilot_plan(source)

    def connect(**_):
        return psycopg2.connect(**postgres17, user="review_migration")

    kwargs = dict(expected_plan_sha256=plan_digest(plan, grants), connect=connect)
    assert run_migrations(config, plan, grants, **kwargs) == len(plan)
    assert run_migrations(config, plan, grants, **kwargs) == 0
    with closing(connect()) as connection, connection:
        with connection.cursor() as cursor:
            cursor.execute("SHOW server_version_num")
            assert 170000 <= int(cursor.fetchone()[0]) < 180000
            cursor.execute(
                "SELECT name,sha256 FROM catalog_review_operations.migrations ORDER BY name"
            )
            assert cursor.fetchall() == [(item.name, item.sha256) for item in plan]
            cursor.execute(
                "SELECT to_regclass('intake_inbox'),to_regclass('catalog_staff.principals')"
            )
            assert all(cursor.fetchone())
            cursor.execute("""SELECT has_schema_privilege('review_runtime','catalog_staff','USAGE'),
                has_table_privilege('review_runtime','catalog_staff.challenges','INSERT'),
                has_table_privilege('review_runtime','catalog_staff.principals','DELETE'),
                has_column_privilege('review_erasure','intake_inbox','payload_cipher','UPDATE')""")
            assert cursor.fetchone() == (True, True, False, True)
            cursor.execute("""SELECT
                has_schema_privilege('review_erasure','catalog_staff','USAGE'),
                has_column_privilege('review_erasure','catalog_staff.assignments','workspace_id','SELECT'),
                has_table_privilege('review_erasure','catalog_staff.assignments','DELETE'),
                has_table_privilege('review_runtime','catalog_staff.assignments','DELETE'),
                has_table_privilege('review_erasure','catalog_staff.credentials','DELETE'),
                has_table_privilege('review_erasure','catalog_staff.principals','DELETE')""")
            assert cursor.fetchone() == (True, True, True, False, False, False)
            principal, erased_workspace, retained_workspace = (
                str(uuid4()) for _ in range(3)
            )
            cursor.execute(
                """INSERT INTO catalog_staff.principals
                (principal_id,issuer,subject,display_name)
                VALUES (%s,'https://accounts.google.com','synthetic-subject','Synthetic staff')""",
                (principal,),
            )
            cursor.execute(
                """INSERT INTO catalog_staff.assignments
                (principal_id,workspace_id,active) VALUES (%s,%s,true),(%s,%s,true)""",
                (principal, erased_workspace, principal, retained_workspace),
            )
    with (
        closing(psycopg2.connect(**postgres17, user="review_erasure")) as connection,
        connection,
    ):
        with connection.cursor() as cursor:
            StaffErasureParticipant().erase_in_transaction(cursor, erased_workspace)
            cursor.execute("SELECT workspace_id::text FROM catalog_staff.assignments")
            assert cursor.fetchall() == [(retained_workspace,)]

    def factory(minconn, maxconn, **_):
        return ThreadedConnectionPool(
            minconn, maxconn, **postgres17, user="review_runtime"
        )

    pool = PooledDatabase(
        replace(config, user="review_runtime", max_connections=1), pool_factory=factory
    )
    tenant_a, tenant_b = str(uuid4()), str(uuid4())
    insert = "INSERT INTO workspaces(workspace_id,landing_path,created_at,last_activity_at) VALUES (%s,'/',now(),now())"
    try:
        with pool.transaction(tenant_a) as cursor:
            cursor.execute(insert, (tenant_a,))
        with pool.transaction(tenant_b) as cursor:
            cursor.execute("SELECT count(*) AS count FROM workspaces")
            assert cursor.fetchone()["count"] == 0
        with pytest.raises(psycopg2.errors.InsufficientPrivilege):
            with pool.transaction(tenant_a) as cursor:
                cursor.execute(insert, (tenant_b,))
        with pytest.raises(RuntimeError, match="rollback smoke"):
            with pool.transaction(tenant_b) as cursor:
                cursor.execute(insert, (tenant_b,))
                raise RuntimeError("rollback smoke")
        with pool.transaction(tenant_b) as cursor:
            cursor.execute("SELECT count(*) AS count FROM workspaces")
            assert cursor.fetchone()["count"] == 0
        with pool.transaction(tenant_a) as cursor:
            cursor.execute("SELECT count(*) AS count FROM workspaces")
            assert cursor.fetchone()["count"] == 1
        with pool.transaction() as cursor:
            cursor.execute("SELECT current_setting('space.workspace_id') AS scope")
            assert cursor.fetchone()["scope"] == ""
    finally:
        pool.close()
