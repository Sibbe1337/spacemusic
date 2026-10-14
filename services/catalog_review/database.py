from contextlib import contextmanager
from uuid import UUID

import psycopg2
from psycopg2.extras import RealDictCursor


class CommitOutcomeUnknown(RuntimeError):
    """Commit acknowledgement was lost; reconcile before destructive cleanup."""


class Database:
    """A fresh transaction/connection per operation; no tenant context can leak."""

    def __init__(self, dsn):
        self._dsn = dsn
        with self.transaction() as db:
            db.execute(
                "SELECT rolsuper, rolbypassrls FROM pg_roles WHERE rolname=current_user"
            )
            role = db.fetchone()
            if role["rolsuper"] or role["rolbypassrls"]:
                raise RuntimeError("Runtime role must not bypass row-level security")
            db.execute(
                "SELECT 1 FROM pg_tables WHERE schemaname='public' AND tableowner=current_user"
            )
            if db.fetchone():
                raise RuntimeError("Runtime role must not own tables")
            for table in (
                "workspaces",
                "memberships",
                "invitations",
                "sessions",
                "outbox",
                "documents",
                "submissions",
                "audit",
                "review_questions",
                "review_replies",
                "review_supplements",
                "interest_events",
                "retention_notices",
                "staff_session_links",
                "dealflow_reviews", "dealflow_packages", "dealflow_decisions",
            ):
                db.execute(
                    """SELECT relrowsecurity, relforcerowsecurity FROM pg_class
                    WHERE oid=to_regclass(%s)""",
                    ("public." + table,),
                )
                policy = db.fetchone()
                if (
                    not policy
                    or not policy["relrowsecurity"]
                    or not policy["relforcerowsecurity"]
                ):
                    raise RuntimeError("Required row-level security is not enabled")
            for table in (
                "receipts",
                "auth_limits",
                "workspaces",
                "memberships",
                "invitations",
                "sessions",
                "outbox",
                "documents",
                "submissions",
                "audit",
                "review_questions",
                "review_replies",
                "review_supplements",
                "interest_events",
                "retention_notices",
                "staff_session_links",
                "dealflow_reviews", "dealflow_packages", "dealflow_decisions",
            ):
                db.execute(
                    "SELECT has_table_privilege(current_user,%s,'TRUNCATE') AS allowed",
                    ("public." + table,),
                )
                if db.fetchone()["allowed"]:
                    raise RuntimeError("Runtime role must not have TRUNCATE privileges")
            for table in (
                "submissions",
                "audit",
                "review_questions",
                "review_replies",
                "review_supplements",
                "interest_events",
                "staff_session_links",
                "dealflow_reviews", "dealflow_packages", "dealflow_decisions",
            ):
                db.execute(
                    """SELECT has_table_privilege(current_user,%s,'UPDATE,DELETE')
                        OR has_any_column_privilege(current_user,%s,'UPDATE') AS allowed""",
                    ("public." + table, "public." + table),
                )
                if db.fetchone()["allowed"]:
                    raise RuntimeError(
                        "Immutable records have unsafe runtime privileges"
                    )

    @contextmanager
    def transaction(self, workspace_id=None):
        connection = psycopg2.connect(self._dsn, connect_timeout=5)
        try:
            with connection.cursor(cursor_factory=RealDictCursor) as db:
                db.execute("SET LOCAL search_path TO public, pg_catalog")
                db.execute("SET LOCAL statement_timeout TO '5s'")
                db.execute("SET LOCAL lock_timeout TO '3s'")
                db.execute(
                    "SELECT set_config('space.workspace_id', %s, true)",
                    (str(UUID(str(workspace_id))) if workspace_id else "",),
                )
                yield db
            try:
                connection.commit()
            except Exception:
                raise CommitOutcomeUnknown(
                    "Database outcome unknown; reconciliation required"
                ) from None
        except CommitOutcomeUnknown:
            raise
        except Exception:
            try:
                connection.rollback()
            except Exception:
                raise CommitOutcomeUnknown(
                    "Rollback unconfirmed; reconciliation required"
                ) from None
            raise
        finally:
            connection.close()
