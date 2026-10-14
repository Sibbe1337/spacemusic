"""Transactions use the existing Database but only the additive provider tables."""

from contextlib import contextmanager
from dataclasses import dataclass
from datetime import timedelta
from uuid import UUID

from psycopg2.extras import Json

from ..security import ReviewError, workspace_from_token
from .contracts import ProviderError

TABLES = (
    "toolost_connections",
    "toolost_oauth_attempts",
    "toolost_import_runs",
    "toolost_import_pages",
    "toolost_source_facts",
    "toolost_quota",
)


@dataclass(frozen=True)
class Actor:
    workspace: str
    principal: str
    session_digest: str


class ReviewSessionAuthority:
    """Coordinator bridge. No public HTTP caller may supply an Actor directly."""

    def __init__(self, review_service):
        self._review = review_service

    def workspace(self, session):
        return workspace_from_token(session)

    def authorize(self, cursor, session):
        workspace, member, _ = self._review._authorize(cursor, session, owner=True)
        return Actor(
            workspace,
            str(member["principal_id"]),
            self._review._hash("session", session),
        )


class Repository:
    def __init__(self, database, authority, config, clock, *, workspace_guard):
        if not callable(workspace_guard):
            raise ValueError("external_workspace_guard_required")
        self.db, self.authority, self.config, self.clock = (
            database,
            authority,
            config,
            clock,
        )
        self.workspace_guard = workspace_guard
        with database.transaction() as db:
            db.execute(
                "SELECT rolsuper, rolbypassrls FROM pg_roles WHERE rolname=current_user"
            )
            role = db.fetchone()
            if role["rolsuper"] or role["rolbypassrls"]:
                raise RuntimeError("provider_runtime_must_not_bypass_rls")
            for table in TABLES:
                db.execute(
                    """SELECT relrowsecurity, relforcerowsecurity,
                    pg_get_userbyid(relowner)=current_user AS owned
                    FROM pg_class WHERE oid=to_regclass(%s)""",
                    ("public." + table,),
                )
                row = db.fetchone()
                if (
                    not row
                    or row["owned"]
                    or not row["relrowsecurity"]
                    or not row["relforcerowsecurity"]
                ):
                    raise RuntimeError("provider_schema_not_isolated")
                db.execute(
                    "SELECT has_table_privilege(current_user,%s,'TRUNCATE') AS allowed",
                    (table,),
                )
                if db.fetchone()["allowed"]:
                    raise RuntimeError("provider_runtime_must_not_truncate")
            for table in ("toolost_import_pages", "toolost_source_facts"):
                db.execute(
                    """SELECT has_table_privilege(current_user,%s,'UPDATE,DELETE')
                    OR has_any_column_privilege(current_user,%s,'UPDATE') AS allowed""",
                    (table, table),
                )
                if db.fetchone()["allowed"]:
                    raise RuntimeError("provider_facts_must_be_immutable")

    @contextmanager
    def owner(self, session):
        workspace = self.authority.workspace(session)
        with self.db.transaction(workspace) as db:
            self.workspace_guard(db, workspace)
            actor = self.authority.authorize(db, session)
            if actor.workspace != workspace:
                raise ProviderError("provider_authorization_invalid")
            yield db, actor

    def connection(self, db, workspace, connection_id):
        connection_id = str(UUID(str(connection_id)))
        db.execute(
            """SELECT * FROM toolost_connections
            WHERE workspace_id=%s AND connection_id=%s AND environment=%s FOR UPDATE""",
            (workspace, connection_id, self.config.environment),
        )
        row = db.fetchone()
        if not row:
            raise ProviderError("connection_unavailable")
        return row

    @contextmanager
    def worker(self, workspace, run_id):
        """Internal worker boundary: current owner membership plus durable consent.

        A browser session is not persisted in a queue. The scheduler supplies only
        workspace/run IDs; this rechecks the creator and connection on each step.
        """
        workspace, run_id = str(UUID(str(workspace))), str(UUID(str(run_id)))
        with self.db.transaction(workspace) as db:
            # The external journal, not a restored database's active status, is
            # authoritative. The supplied guard must take the workspace row lock.
            try:
                self.workspace_guard(db, workspace)
            except ReviewError:
                raise ProviderError("workspace_unavailable") from None
            db.execute(
                "SELECT * FROM toolost_import_runs WHERE workspace_id=%s AND run_id=%s FOR UPDATE",
                (workspace, run_id),
            )
            run = db.fetchone()
            if not run:
                raise ProviderError("import_unavailable")
            db.execute(
                """SELECT 1 FROM memberships WHERE workspace_id=%s
                AND principal_id=%s AND active AND role='owner'""",
                (workspace, run["principal_id"]),
            )
            if not db.fetchone():
                raise ProviderError("import_authorization_revoked")
            connection = self.connection(db, workspace, run["connection_id"])
            yield db, run, connection

    @contextmanager
    def pool(self):
        with self.db.transaction() as db:
            db.execute(
                "SELECT set_config('space.toolost_environment',%s,true)",
                (self.config.environment,),
            )
            db.execute(
                "SELECT set_config('space.toolost_pool',%s,true)",
                (self.config.developer_pool,),
            )
            yield db

    def reserve_call(self):
        now = self.clock()
        month = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        minute = now.replace(second=0, microsecond=0)
        identity = (self.config.environment, self.config.developer_pool)
        with self.pool() as db:
            db.execute(
                """INSERT INTO toolost_quota(environment,pool,month_start,minute_start)
                VALUES(%s,%s,%s,%s) ON CONFLICT DO NOTHING""",
                identity + (month, minute),
            )
            db.execute(
                "SELECT * FROM toolost_quota WHERE environment=%s AND pool=%s FOR UPDATE",
                identity,
            )
            row = db.fetchone()
            if row["blocked"] or row["provider_remaining"] == 0:
                raise ProviderError("provider_quota_exceeded")
            if row["pause_until"] and row["pause_until"] > now:
                raise ProviderError(
                    "provider_rate_limited",
                    retry_after=int((row["pause_until"] - now).total_seconds()) + 1,
                )
            monthly = row["month_calls"] if row["month_start"] == month else 0
            per_minute = row["minute_calls"] if row["minute_start"] == minute else 0
            if monthly >= self.config.monthly_calls:
                raise ProviderError("local_monthly_budget_exhausted")
            if per_minute >= self.config.minute_calls:
                raise ProviderError("local_rate_limited", retry_after=60)
            db.execute(
                """UPDATE toolost_quota SET month_start=%s,month_calls=%s,
                minute_start=%s,minute_calls=%s,
                provider_remaining=CASE WHEN provider_remaining IS NULL THEN NULL
                    ELSE GREATEST(provider_remaining-1,0) END
                WHERE environment=%s AND pool=%s""",
                (month, monthly + 1, minute, per_minute + 1) + identity,
            )

    def observe_quota(self, headers):
        value = headers.get("x-api-quota-remaining")
        if value is None or not value.isdecimal() or len(value) > 9:
            return
        with self.pool() as db:
            db.execute(
                """UPDATE toolost_quota SET provider_remaining=
                CASE WHEN provider_remaining IS NULL THEN %s ELSE LEAST(provider_remaining,%s) END
                WHERE environment=%s AND pool=%s""",
                (
                    int(value),
                    int(value),
                    self.config.environment,
                    self.config.developer_pool,
                ),
            )

    def pause_quota(self, error):
        with self.pool() as db:
            if error.code == "provider_quota_exceeded":
                db.execute(
                    "UPDATE toolost_quota SET blocked=true WHERE environment=%s AND pool=%s",
                    (self.config.environment, self.config.developer_pool),
                )
            elif error.code == "provider_rate_limited":
                db.execute(
                    """UPDATE toolost_quota SET pause_until=GREATEST(pause_until,%s)
                    WHERE environment=%s AND pool=%s""",
                    (
                        self.clock() + timedelta(seconds=error.retry_after or 60),
                        self.config.environment,
                        self.config.developer_pool,
                    ),
                )

    @staticmethod
    def revoke(db, workspace, connection_id, generation):
        db.execute(
            """UPDATE toolost_connections SET status='reauth_required',
            generation=generation+1,credentials=NULL,refresh_lease=NULL,refresh_until=NULL
            WHERE workspace_id=%s AND connection_id=%s AND generation=%s
            AND status<>'disconnected'""",
            (workspace, connection_id, generation),
        )
        db.execute(
            """UPDATE toolost_import_runs SET status='cancelled',
            lease_id=NULL,lease_until=NULL,error_code='reauth_required'
            WHERE workspace_id=%s AND connection_id=%s AND generation=%s
            AND status IN ('queued','running','retryable')""",
            (workspace, connection_id, generation),
        )

    @staticmethod
    def public_run(run):
        return {
            "run_id": str(run["run_id"]),
            "request_id": str(run["request_id"]),
            "status": run["status"],
            "pages": run["page_count"],
            "records": run["record_count"],
            "calls": run["call_count"],
            "error": run["error_code"],
            "coverage": run["coverage"],
        }

    @staticmethod
    def json(value):
        return Json(value)
