import secrets
import shutil
import subprocess
import tempfile
from contextlib import closing, contextmanager
from datetime import datetime, timedelta, timezone
from pathlib import Path
from uuid import uuid4

import psycopg2
import pytest
from psycopg2 import sql
from psycopg2.extras import RealDictCursor

from services.catalog_review.database import Database
from services.catalog_review.security import Settings
from services.catalog_review.service import ReviewService


class Clock:
    def __init__(self):
        self.now = datetime(2026, 9, 18, 12, tzinfo=timezone.utc)

    def __call__(self):
        return self.now

    def advance(self, seconds):
        self.now += timedelta(seconds=seconds)


class SyntheticBlobs:
    """Test fixture only. Not a production storage adapter."""

    def __init__(self):
        self.objects = {}

    def put_if_absent(self, key, value):
        assert key not in self.objects
        self.objects[key] = bytes(value)

    def get(self, key):
        return self.objects[key]

    def delete(self, key):
        self.objects.pop(key, None)

    def erase_and_verify(self, workspace):
        prefix = str(workspace) + "/"
        for key in list(self.objects):
            if key.startswith(prefix):
                self.delete(key)
        assert not any(key.startswith(prefix) for key in self.objects)


@pytest.fixture(scope="session")
def cluster():
    """Disposable socket-only PostgreSQL; never reads a configured DATABASE_URL."""
    for binary in ("initdb", "pg_ctl"):
        if not shutil.which(binary):
            pytest.skip(f"{binary} required for real PostgreSQL isolation tests")
    with tempfile.TemporaryDirectory(prefix="space-review-pg-", dir="/tmp") as root:
        data = root + "/data"
        subprocess.run(
            [
                "initdb",
                "-D",
                data,
                "-A",
                "trust",
                "-U",
                "review_migration",
                "--no-locale",
                "--encoding=UTF8",
            ],
            check=True,
            capture_output=True,
        )
        subprocess.run(
            [
                "pg_ctl",
                "-D",
                data,
                "-l",
                root + "/server.log",
                "-o",
                f"-c listen_addresses='' -k {root} -p 55487",
                "-w",
                "start",
            ],
            check=True,
            capture_output=True,
        )
        dsn = f"host={root} port=55487 user=review_migration dbname=postgres"
        try:
            with closing(psycopg2.connect(dsn)) as connection, connection:
                with connection.cursor() as cur:
                    cur.execute(
                        "CREATE ROLE review_runtime LOGIN NOSUPERUSER NOBYPASSRLS NOCREATEDB NOCREATEROLE"
                    )
                    cur.execute(
                        "CREATE ROLE review_erasure LOGIN NOSUPERUSER NOBYPASSRLS NOCREATEDB NOCREATEROLE NOINHERIT"
                    )
            yield dsn
        finally:
            subprocess.run(
                ["pg_ctl", "-D", data, "-m", "immediate", "-w", "stop"],
                check=True,
                capture_output=True,
            )


@pytest.fixture
def backend(cluster):
    name = "review_" + uuid4().hex
    connection = psycopg2.connect(cluster)
    connection.autocommit = True
    with connection.cursor() as cur:
        cur.execute(sql.SQL("CREATE DATABASE {}").format(sql.Identifier(name)))
    owner_dsn = cluster.replace("dbname=postgres", "dbname=" + name)
    runtime_dsn = owner_dsn.replace("user=review_migration", "user=review_runtime")
    with closing(psycopg2.connect(owner_dsn)) as owner, owner:
        with owner.cursor() as cur:
            cur.execute(Path("services/catalog_review/schema.sql").read_text())
            for migration in sorted(
                Path("services/catalog_review/migrations").glob("*.sql")
            ):
                cur.execute(migration.read_text())
            cur.execute(Path("services/catalog_review/grants.sql").read_text())
    clock = Clock()
    service = ReviewService(
        Database(runtime_dsn),
        Settings(
            "https://review.test", secrets.token_bytes(32), secrets.token_bytes(32)
        ),
        clock,
    )
    service.test_owner_dsn = owner_dsn
    service.test_runtime_dsn = runtime_dsn
    service.test_blobs = SyntheticBlobs()
    try:
        yield service
    finally:
        with connection.cursor() as cur:
            cur.execute(sql.SQL("DROP DATABASE {}").format(sql.Identifier(name)))
        connection.close()


@contextmanager
def owner_cursor(service):
    with closing(psycopg2.connect(service.test_owner_dsn)) as connection, connection:
        with connection.cursor(cursor_factory=RealDictCursor) as cur:
            yield cur


def receipt(reference="response-1", email="alex@example.com"):
    return {
        "source": "typeform",
        "form_id": "synthetic-form",
        "response_id": reference,
        "email": email,
    }


def sign_in(service, reference="response-1", email="alex@example.com"):
    workspace = service.ingest(receipt(reference, email))["workspace_id"]
    with owner_cursor(service) as cur:
        cur.execute(
            "SELECT invitation_id FROM invitations WHERE workspace_id=%s", (workspace,)
        )
        invitation = str(cur.fetchone()["invitation_id"])
    token = service.invitation_token(workspace, invitation)
    return workspace, service.exchange_invitation(token), token


def draft(document_ids=()):
    return {
        "source": "documents",
        "rights": [{"release_reference": "release-one", "ownership": "unknown"}],
        "document_ids": list(document_ids),
        "future_music_excluded": True,
    }
