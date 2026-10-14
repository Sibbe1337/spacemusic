from contextlib import contextmanager
from uuid import UUID, uuid4

import psycopg2
from psycopg2.extras import Json, RealDictCursor

from .config import StaffError


@contextmanager
def transaction(dsn):
    connection = psycopg2.connect(dsn, connect_timeout=5)
    try:
        with connection:
            with connection.cursor(cursor_factory=RealDictCursor) as db:
                db.execute("SET LOCAL search_path TO pg_catalog")
                db.execute("SET LOCAL statement_timeout TO '5s'")
                db.execute("SET LOCAL lock_timeout TO '3s'")
                yield db
    finally:
        connection.close()


def audit(db, principal, action, now, reference=None):
    db.execute(
        "INSERT INTO catalog_staff.audit VALUES (%s,%s,%s,%s,%s)",
        (str(uuid4()), principal, action, reference, now),
    )


def lock_principal(db, principal):
    db.execute(
        "SELECT * FROM catalog_staff.principals WHERE principal_id=%s FOR UPDATE",
        (str(UUID(str(principal))),),
    )
    row = db.fetchone()
    if not row:
        raise StaffError()
    return row


class StaffRepository:
    """Authentication data only; separate least-privilege runtime role required."""

    def __init__(self, dsn=None, *, database=None):
        if (dsn is None) == (database is None):
            raise ValueError(
                "Supply either an isolated DSN or a bounded transaction provider"
            )
        self._dsn, self._database = dsn, database
        with self.transaction() as db:
            db.execute(
                "SELECT rolsuper,rolbypassrls,rolcreaterole,rolcreatedb FROM pg_roles WHERE rolname=current_user"
            )
            if any(db.fetchone().values()):
                raise RuntimeError("Unsafe staff runtime role")
            db.execute(
                "SELECT has_schema_privilege(current_user,'catalog_staff','CREATE') AS allowed"
            )
            if db.fetchone()["allowed"]:
                raise RuntimeError(
                    "Staff runtime must not own or create schema objects"
                )
            for table in (
                "principals",
                "enrollment_permits",
                "credentials",
                "sessions",
                "challenges",
                "assignments",
                "audit",
            ):
                db.execute(
                    "SELECT has_table_privilege(current_user,%s,'DELETE,TRUNCATE') AS allowed",
                    ("catalog_staff." + table,),
                )
                if db.fetchone()["allowed"]:
                    raise RuntimeError("Unsafe staff runtime privileges")
            for table in ("principals", "enrollment_permits", "assignments"):
                db.execute(
                    "SELECT has_any_column_privilege(current_user,%s,'INSERT') AS allowed",
                    ("catalog_staff." + table,),
                )
                if db.fetchone()["allowed"]:
                    raise RuntimeError(
                        "Provisioning belongs to the supervised administrator"
                    )
            for table in ("assignments", "audit"):
                db.execute(
                    "SELECT has_any_column_privilege(current_user,%s,'UPDATE') AS allowed",
                    ("catalog_staff." + table,),
                )
                if db.fetchone()["allowed"]:
                    raise RuntimeError("Unsafe staff runtime mutation privileges")
            for table, allowed in {
                "principals": ["state"],
                "enrollment_permits": ["consumed_at"],
                "credentials": ["sign_count", "confirmed_at"],
                "sessions": ["revoked_at", "uv_at", "uv_credential_id"],
                "challenges": ["consumed_at"],
            }.items():
                db.execute(
                    """SELECT 1 FROM pg_attribute WHERE attrelid=to_regclass(%s)
                    AND attnum>0 AND NOT attisdropped AND NOT (attname=ANY(%s))
                    AND has_column_privilege(current_user,attrelid,attnum,'UPDATE')""",
                    ("catalog_staff." + table, allowed),
                )
                if db.fetchone():
                    raise RuntimeError("Unsafe staff runtime column privileges")

    def transaction(self):
        if self._database is not None:
            return self._database.transaction()
        return transaction(self._dsn)

    @staticmethod
    def add_challenge(db, *, kind, binding, generation, payload, now, expires):
        identifier = str(uuid4())
        db.execute(
            """INSERT INTO catalog_staff.challenges
            (challenge_id,kind,binding_digest,generation,payload,created_at,expires_at)
            VALUES (%s,%s,%s,%s,%s,%s,%s)""",
            (identifier, kind, binding, generation, Json(payload), now, expires),
        )
        return identifier

    def take_challenge(self, identifier, kind, binding, generation, now):
        try:
            identifier = str(UUID(str(identifier)))
        except ValueError:
            raise StaffError("staff_challenge_invalid") from None
        # Commit consumption BEFORE verification: failed proofs cannot retry a
        # challenge, and a later transaction rollback cannot resurrect it.
        with self.transaction() as db:
            db.execute(
                """UPDATE catalog_staff.challenges SET consumed_at=%s
                WHERE challenge_id=%s AND kind=%s AND binding_digest=%s AND generation=%s
                AND consumed_at IS NULL AND expires_at>%s AND created_at<=%s RETURNING *""",
                (now, identifier, kind, binding, generation, now, now),
            )
            row = db.fetchone()
        if not row:
            raise StaffError("staff_challenge_invalid")
        return row
