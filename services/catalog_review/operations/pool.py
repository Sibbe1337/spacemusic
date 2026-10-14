"""Bounded synchronous pool implementing the core Database.transaction interface.

https://www.psycopg.org/docs/pool.html
https://www.postgresql.org/docs/current/sql-discard.html
"""

import os
from contextlib import contextmanager
from threading import BoundedSemaphore, Lock
from uuid import UUID

from psycopg2.extras import RealDictCursor
from psycopg2.pool import ThreadedConnectionPool

from ..database import CommitOutcomeUnknown, Database
from .config import require


class PoolUnavailable(RuntimeError):
    pass


def _close(connection):
    try:
        connection.close()
    except BaseException:
        pass


class PooledDatabase(Database):
    """Create after fork. Call close only after draining requests/workers.

    pool_factory is an explicit trusted test seam, never selected by configuration.
    No migration credentials or ambient DATABASE_URL are read by this adapter.
    """

    def __init__(self, config, *, pool_factory=ThreadedConnectionPool):
        config.validate()
        require(config.user == "review_runtime", "runtime_role_required")
        self._pid = os.getpid()
        self._slots = BoundedSemaphore(config.max_connections)
        self._lock = Lock()
        self._active = 0
        self._closed = False
        self._wait = config.checkout_timeout_seconds
        self._pool = pool_factory(1, config.max_connections, **config.connect_kwargs())
        try:
            # Reuse, rather than silently weaken, the shared startup RLS checks.
            super().__init__(None)
            with self.transaction() as cursor:
                cursor.execute(
                    "SELECT rolcreaterole, rolcreatedb FROM pg_roles WHERE rolname=current_user"
                )
                role = cursor.fetchone()
                if role["rolcreaterole"] or role["rolcreatedb"]:
                    raise RuntimeError(
                        "Runtime role must not manage roles or databases"
                    )
                cursor.execute("""SELECT c.relname FROM pg_class c
                    JOIN pg_namespace n ON n.oid=c.relnamespace
                    WHERE n.nspname='public' AND c.relkind IN ('r','p')
                      AND c.relname NOT IN ('receipts', 'intake_admissions')
                      AND EXISTS (SELECT 1 FROM pg_attribute a WHERE a.attrelid=c.oid
                                  AND a.attname='workspace_id' AND NOT a.attisdropped)
                      AND (NOT c.relrowsecurity OR NOT c.relforcerowsecurity)""")
                if cursor.fetchone():
                    raise RuntimeError("Every workspace table must force RLS")
                cursor.execute(
                    "SELECT to_regclass('public.review_supplements') AS relation"
                )
                if cursor.fetchone()["relation"]:
                    cursor.execute("""SELECT has_table_privilege(current_user,'public.review_supplements','UPDATE,DELETE,TRUNCATE')
                        OR has_any_column_privilege(current_user,'public.review_supplements','UPDATE') AS allowed""")
                    if cursor.fetchone()["allowed"]:
                        raise RuntimeError(
                            "Supplements must be immutable to the runtime role"
                        )
        except BaseException:
            self.close()
            raise

    @contextmanager
    def _lease(self):
        if os.getpid() != self._pid:
            raise PoolUnavailable("pool_created_before_fork")
        if not self._slots.acquire(timeout=self._wait):
            raise PoolUnavailable("database_pool_exhausted")
        connection = None
        registered = False
        try:
            with self._lock:
                if self._closed:
                    raise PoolUnavailable("database_pool_closed")
                self._active += 1
                registered = True
            try:
                connection = self._pool.getconn()
            except Exception:
                raise PoolUnavailable("database_connection_unavailable") from None
            yield connection
        finally:
            if connection is not None:
                discard = True
                try:
                    # Reset GUCs, roles, temp objects and advisory locks between
                    # tenants. RESET alone does not remove all session state.
                    if not connection.closed:
                        connection.rollback()
                        connection.autocommit = True
                        with connection.cursor() as cursor:
                            cursor.execute("DISCARD ALL")
                        connection.autocommit = False
                        discard = False
                except Exception:
                    discard = True
                try:
                    self._pool.putconn(connection, close=discard)
                except Exception:
                    _close(connection)
            if registered:
                with self._lock:
                    self._active -= 1
            self._slots.release()

    @contextmanager
    def transaction(self, workspace_id=None):
        workspace = str(UUID(str(workspace_id))) if workspace_id is not None else ""
        with self._lease() as connection:
            try:
                with connection.cursor(cursor_factory=RealDictCursor) as cursor:
                    cursor.execute("SET LOCAL search_path TO public, pg_catalog")
                    cursor.execute("SET LOCAL statement_timeout TO '5s'")
                    cursor.execute("SET LOCAL lock_timeout TO '3s'")
                    cursor.execute(
                        "SET LOCAL idle_in_transaction_session_timeout TO '15s'"
                    )
                    cursor.execute(
                        "SELECT set_config('space.workspace_id', %s, true)",
                        (workspace,),
                    )
                    yield cursor
                try:
                    connection.commit()
                except BaseException:
                    _close(connection)
                    raise CommitOutcomeUnknown(
                        "Database outcome unknown; reconciliation required"
                    ) from None
            except CommitOutcomeUnknown:
                _close(connection)
                raise
            except BaseException:
                try:
                    connection.rollback()
                except BaseException:
                    _close(connection)
                    raise CommitOutcomeUnknown(
                        "Rollback unconfirmed; reconciliation required"
                    ) from None
                raise

    def close(self):
        with self._lock:
            if self._active:
                raise PoolUnavailable("drain_database_users_before_close")
            if not self._closed:
                self._closed = True
                self._pool.closeall()
