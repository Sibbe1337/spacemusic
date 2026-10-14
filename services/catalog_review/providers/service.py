"""Coordinator API. No route mounting, scheduler, secret discovery or live transport."""

import secrets
from datetime import timedelta
from uuid import UUID, uuid4

from .contracts import (
    MANIFEST,
    SCOPES,
    ProviderError,
    coverage,
    fingerprint,
    provider_id,
)
from .crypto import pkce, state_digest
from .normalization import normalize_page

TERMINAL = {"complete", "partial", "cancelled"}


def token_binding(connection):
    return {
        "purpose": "tokens",
        "workspace": str(connection["workspace_id"]),
        "connection": str(connection["connection_id"]),
        "environment": connection["environment"],
        "generation": connection["generation"],
        "version": connection["token_version"],
        "account": connection["account_id"],
        "principal": str(connection["principal_id"]),
    }


def oauth_binding(attempt):
    return {
        "purpose": "pkce",
        "workspace": str(attempt["workspace_id"]),
        "state": attempt["state_digest"],
        "session": attempt["session_digest"],
        "environment": attempt["environment"],
        "callback": attempt["callback_uri"],
        "principal": str(attempt["principal_id"]),
        "client": attempt["client_digest"],
        "generation": attempt["generation"],
        "connection": str(attempt["connection_id"]),
    }


class TooLostService:
    def __init__(self, repository, vault, adapter):
        if adapter.config != repository.config:
            raise ValueError("provider_configuration_mismatch")
        self.repo, self.vault, self.adapter = repository, vault, adapter
        self.config, self.clock = repository.config, repository.clock

    def _hooks(self, guard):
        def before_send():
            self.config.require_enabled()
            self.repo.reserve_call()
            guard()

        return {
            "before_send": before_send,
            "observe": self.repo.observe_quota,
            "now": self.clock(),
        }

    def start_oauth(self, session):
        self.config.require_enabled()
        verifier, challenge = pkce()
        state = secrets.token_urlsafe(32)
        digest = state_digest(state)
        with self.repo.owner(session) as (db, actor):
            db.execute(
                "SELECT * FROM toolost_connections WHERE workspace_id=%s AND environment=%s FOR UPDATE",
                (actor.workspace, self.config.environment),
            )
            connection = db.fetchone()
            if connection and connection["status"] in (
                "active",
                "awaiting_confirmation",
            ):
                raise ProviderError("disconnect_required")
            connection_id = (
                str(connection["connection_id"]) if connection else str(uuid4())
            )
            generation = connection["generation"] + 1 if connection else 1
            db.execute(
                """UPDATE toolost_import_runs SET status='cancelled',
                lease_id=NULL,lease_until=NULL,error_code='connection_replaced'
                WHERE workspace_id=%s AND connection_id=%s AND status IN ('queued','running','retryable')""",
                (actor.workspace, connection_id),
            )
            db.execute(
                """INSERT INTO toolost_connections
                (workspace_id,connection_id,environment,principal_id,generation,status)
                VALUES(%s,%s,%s,%s,%s,'auth_pending')
                ON CONFLICT(workspace_id,environment) DO UPDATE SET
                principal_id=EXCLUDED.principal_id,generation=EXCLUDED.generation,
                status='auth_pending',credentials=NULL,account_id=NULL,scopes='[]',
                refresh_lease=NULL,refresh_until=NULL,confirmed_at=NULL,token_version=0""",
                (
                    actor.workspace,
                    connection_id,
                    self.config.environment,
                    actor.principal,
                    generation,
                ),
            )
            db.execute(
                """UPDATE toolost_oauth_attempts SET status='failed',verifier=NULL
                WHERE workspace_id=%s AND connection_id=%s AND status IN ('pending','exchanging')""",
                (actor.workspace, connection_id),
            )
            attempt = {
                "workspace_id": actor.workspace,
                "state_digest": digest,
                "session_digest": actor.session_digest,
                "environment": self.config.environment,
                "callback_uri": self.config.callback,
                "client_digest": fingerprint(self.config.client_id),
                "principal_id": actor.principal,
                "generation": generation,
                "connection_id": connection_id,
            }
            envelope = self.vault.seal({"verifier": verifier}, oauth_binding(attempt))
            db.execute(
                """INSERT INTO toolost_oauth_attempts
                (workspace_id,state_digest,connection_id,generation,environment,session_digest,
                principal_id,callback_uri,client_digest,verifier,expires_at,status)
                VALUES(%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,'pending')""",
                (
                    actor.workspace,
                    digest,
                    connection_id,
                    generation,
                    self.config.environment,
                    actor.session_digest,
                    actor.principal,
                    self.config.callback,
                    fingerprint(self.config.client_id),
                    self.repo.json(envelope),
                    self.clock() + timedelta(minutes=10),
                ),
            )
        return {
            "authorization_url": self.adapter.authorization_url(state, challenge),
            "expires_in": 600,
        }

    def callback(self, session, *, state, callback_uri, code=None, error=None):
        self.config.require_enabled()
        self.config.validate_callback(callback_uri)
        if (code is None) == (error is None):
            raise ProviderError("oauth_response_invalid")
        digest = state_digest(state)
        with self.repo.owner(session) as (db, actor):
            db.execute(
                "SELECT * FROM toolost_oauth_attempts WHERE workspace_id=%s AND state_digest=%s FOR UPDATE",
                (actor.workspace, digest),
            )
            attempt = db.fetchone()
            if (
                not attempt
                or attempt["status"] != "pending"
                or attempt["expires_at"] <= self.clock()
            ):
                raise ProviderError("oauth_state_unavailable")
            if (
                attempt["session_digest"] != actor.session_digest
                or str(attempt["principal_id"]) != actor.principal
                or attempt["client_digest"] != fingerprint(self.config.client_id)
                or attempt["environment"] != self.config.environment
                or attempt["callback_uri"] != callback_uri
            ):
                raise ProviderError("oauth_binding_mismatch")
            connection = self.repo.connection(
                db, actor.workspace, attempt["connection_id"]
            )
            if (
                connection["generation"] != attempt["generation"]
                or connection["status"] != "auth_pending"
            ):
                raise ProviderError("oauth_state_unavailable")
            verifier = self.vault.open(attempt["verifier"], oauth_binding(attempt))[
                "verifier"
            ]
            db.execute(
                "UPDATE toolost_oauth_attempts SET status=%s,verifier=NULL WHERE workspace_id=%s AND state_digest=%s",
                (
                    "failed" if error is not None else "exchanging",
                    actor.workspace,
                    digest,
                ),
            )
            if error is not None:
                self.repo.revoke(
                    db,
                    actor.workspace,
                    connection["connection_id"],
                    connection["generation"],
                )
        if error is not None:
            raise ProviderError("oauth_denied")

        def guard():
            with self.repo.owner(session) as (db, current):
                row = self.repo.connection(
                    db, current.workspace, connection["connection_id"]
                )
                if (
                    row["generation"] != connection["generation"]
                    or row["status"] != "auth_pending"
                ):
                    raise ProviderError("oauth_state_unavailable")

        try:
            tokens = self.adapter.tokens(
                code=code, verifier=verifier, **self._hooks(guard)
            )
            token_received_at = self.clock()
            profile = self.adapter.get(
                "me", tokens["access_token"], **self._hooks(guard)
            )
            if not isinstance(profile.get("data"), dict):
                raise ProviderError("provider_schema_invalid")
            account = provider_id(profile["data"].get("id"))
            with self.repo.owner(session) as (db, actor):
                current = self.repo.connection(
                    db, actor.workspace, connection["connection_id"]
                )
                if (
                    current["generation"] != connection["generation"]
                    or current["status"] != "auth_pending"
                ):
                    raise ProviderError("oauth_state_unavailable")
                if self.clock() >= attempt["expires_at"]:
                    raise ProviderError("oauth_state_unavailable")
                current.update(account_id=account, token_version=1)
                envelope = self.vault.seal(tokens, token_binding(current))
                db.execute(
                    """UPDATE toolost_connections SET account_id=%s,status='awaiting_confirmation',
                    token_version=1,credentials=%s,scopes=%s,access_expires_at=%s
                    WHERE workspace_id=%s AND connection_id=%s""",
                    (
                        account,
                        self.repo.json(envelope),
                        self.repo.json(tokens["scopes"]),
                        token_received_at + timedelta(seconds=tokens["expires_in"]),
                        actor.workspace,
                        current["connection_id"],
                    ),
                )
                db.execute(
                    "UPDATE toolost_oauth_attempts SET status='complete' WHERE workspace_id=%s AND state_digest=%s",
                    (actor.workspace, digest),
                )
            return {
                "connection_id": str(connection["connection_id"]),
                "account_id": account,
                "status": "awaiting_confirmation",
            }
        except Exception as failure:
            if isinstance(failure, ProviderError):
                self.repo.pause_quota(failure)
            self._invalidate(actor.workspace, connection)
            raise

    def _invalidate(self, workspace, connection):
        # No late response can restore disconnected credentials. This cleanup needs
        # no still-live browser session, and is deliberately restricted by generation.
        with self.repo.db.transaction(workspace) as db:
            self.repo.revoke(
                db, workspace, connection["connection_id"], connection["generation"]
            )
            db.execute(
                """UPDATE toolost_oauth_attempts SET status='failed',verifier=NULL
                WHERE workspace_id=%s AND connection_id=%s AND generation=%s AND status='exchanging'""",
                (workspace, connection["connection_id"], connection["generation"]),
            )

    def confirm_account(self, session, connection_id, account_id):
        self.config.require_enabled()
        with self.repo.owner(session) as (db, actor):
            connection = self.repo.connection(db, actor.workspace, connection_id)
            if str(connection["principal_id"]) != actor.principal or connection[
                "account_id"
            ] != provider_id(account_id):
                raise ProviderError("account_confirmation_mismatch")
            if connection["status"] not in ("awaiting_confirmation", "active"):
                raise ProviderError("connection_unavailable")
            db.execute(
                "UPDATE toolost_connections SET status='active',confirmed_at=COALESCE(confirmed_at,%s) WHERE workspace_id=%s AND connection_id=%s",
                (self.clock(), actor.workspace, connection_id),
            )
        return {
            "connection_id": str(connection_id),
            "account_id": account_id,
            "status": "active",
        }

    def disconnect(self, session, connection_id):
        # Local disconnection remains available when the feature flag is off.
        with self.repo.owner(session) as (db, actor):
            self.repo.connection(db, actor.workspace, connection_id)
            db.execute(
                """UPDATE toolost_connections SET status='disconnected',generation=generation+1,
                credentials=NULL,refresh_lease=NULL,refresh_until=NULL,access_expires_at=NULL
                WHERE workspace_id=%s AND connection_id=%s""",
                (actor.workspace, connection_id),
            )
            db.execute(
                "UPDATE toolost_oauth_attempts SET verifier=NULL,status='failed' WHERE workspace_id=%s AND connection_id=%s AND status IN ('pending','exchanging')",
                (actor.workspace, connection_id),
            )
            db.execute(
                "UPDATE toolost_import_runs SET status='cancelled',lease_id=NULL,lease_until=NULL,error_code='connection_disconnected' WHERE workspace_id=%s AND connection_id=%s AND status IN ('queued','running','retryable')",
                (actor.workspace, connection_id),
            )
        return {
            "status": "disconnected",
            "remote_revocation_confirmed": False,
            "erasure_completed": False,
        }

    def rewrap_credentials(self, session, connection_id):
        with self.repo.owner(session) as (db, actor):
            connection = self.repo.connection(db, actor.workspace, connection_id)
            if connection["credentials"] is None:
                raise ProviderError("credential_unavailable")
            envelope = self.vault.rewrap(
                connection["credentials"], token_binding(connection)
            )
            db.execute(
                "UPDATE toolost_connections SET credentials=%s WHERE workspace_id=%s AND connection_id=%s",
                (self.repo.json(envelope), actor.workspace, connection_id),
            )
        return {"key_version": self.vault.active_key}

    def _tokens(self, context, *, force_version=None, reserve=None):
        self.config.require_enabled()
        expired_lease = False
        with context() as (db, workspace, connection):
            if connection["status"] != "active" or connection["scopes"] != list(SCOPES):
                raise ProviderError("reauth_required")
            if connection["refresh_lease"]:
                if connection["refresh_until"] > self.clock():
                    raise ProviderError("refresh_busy", retry_after=2)
                self.repo.revoke(
                    db, workspace, connection["connection_id"], connection["generation"]
                )
                expired_lease = True
            elif connection["access_expires_at"] > self.clock() + timedelta(
                seconds=60
            ) and (
                force_version is None or connection["token_version"] != force_version
            ):
                return self.vault.open(
                    connection["credentials"], token_binding(connection)
                ), connection["token_version"]
            if not expired_lease:
                tokens = self.vault.open(
                    connection["credentials"], token_binding(connection)
                )
                lease = str(uuid4())
                db.execute(
                    "UPDATE toolost_connections SET refresh_lease=%s,refresh_until=%s WHERE workspace_id=%s AND connection_id=%s",
                    (
                        lease,
                        self.clock() + timedelta(seconds=self.config.lease_seconds),
                        workspace,
                        connection["connection_id"],
                    ),
                )
        if expired_lease:
            raise ProviderError("reauth_required")

        def guard():
            with context() as (_, _, row):
                if (
                    str(row["refresh_lease"]) != lease
                    or row["generation"] != connection["generation"]
                    or row["refresh_until"] <= self.clock()
                ):
                    raise ProviderError("refresh_fence_lost")
            if reserve is not None:
                reserve()

        try:
            refreshed = self.adapter.tokens(
                refresh_token=tokens["refresh_token"], **self._hooks(guard)
            )
            with context() as (db, workspace, current):
                if (
                    str(current["refresh_lease"]) != lease
                    or current["generation"] != connection["generation"]
                    or current["refresh_until"] <= self.clock()
                ):
                    raise ProviderError("refresh_fence_lost")
                current["token_version"] += 1
                envelope = self.vault.seal(refreshed, token_binding(current))
                db.execute(
                    """UPDATE toolost_connections SET credentials=%s,token_version=%s,
                    access_expires_at=%s,refresh_lease=NULL,refresh_until=NULL
                    WHERE workspace_id=%s AND connection_id=%s""",
                    (
                        self.repo.json(envelope),
                        current["token_version"],
                        self.clock() + timedelta(seconds=refreshed["expires_in"]),
                        workspace,
                        current["connection_id"],
                    ),
                )
            return refreshed, current["token_version"]
        except Exception as failure:
            if isinstance(failure, ProviderError):
                self.repo.pause_quota(failure)
            self._invalidate(workspace, connection)
            raise

    def refresh(self, session, connection_id):
        from contextlib import contextmanager

        @contextmanager
        def context():
            with self.repo.owner(session) as (db, actor):
                connection = self.repo.connection(db, actor.workspace, connection_id)
                if str(connection["principal_id"]) != actor.principal:
                    raise ProviderError("connection_unavailable")
                yield db, actor.workspace, connection

        _, version = self._tokens(context)
        return {"status": "active", "token_version": version}

    def start_import(self, session, connection_id, request_id, release_ids=()):
        self.config.require_enabled()
        request_id = str(UUID(str(request_id)))
        connection_id = str(UUID(str(connection_id)))
        if (
            not isinstance(release_ids, (tuple, list))
            or len(release_ids) > self.config.max_releases
        ):
            raise ProviderError("import_selection_invalid")
        selection = sorted({provider_id(value) for value in release_ids})
        body_hash = fingerprint([MANIFEST, connection_id, selection])
        with self.repo.owner(session) as (db, actor):
            db.execute(
                "SELECT * FROM toolost_import_runs WHERE workspace_id=%s AND request_id=%s",
                (actor.workspace, request_id),
            )
            existing = db.fetchone()
            if existing:
                if (
                    existing["payload_hash"] != body_hash
                    or str(existing["principal_id"]) != actor.principal
                ):
                    raise ProviderError("import_request_conflict")
                return self.repo.public_run(existing)
            connection = self.repo.connection(db, actor.workspace, connection_id)
            if (
                connection["status"] != "active"
                or str(connection["principal_id"]) != actor.principal
            ):
                raise ProviderError("connection_unavailable")
            db.execute(
                "SELECT 1 FROM toolost_import_runs WHERE workspace_id=%s AND connection_id=%s AND status IN ('queued','running','retryable')",
                (actor.workspace, connection_id),
            )
            if db.fetchone():
                raise ProviderError("import_in_progress")
            resources = ["releases"] + [
                f"sales/releases/{identity}/overview" for identity in selection
            ]
            db.execute(
                """INSERT INTO toolost_import_runs
                (workspace_id,run_id,connection_id,generation,principal_id,request_id,payload_hash,
                manifest,resources,selection,account_id,status,available_at,created_at,deadline,coverage)
                VALUES(%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,'queued',%s,%s,%s,%s) RETURNING *""",
                (
                    actor.workspace,
                    str(uuid4()),
                    connection_id,
                    connection["generation"],
                    actor.principal,
                    request_id,
                    body_hash,
                    MANIFEST,
                    self.repo.json(resources),
                    self.repo.json(selection),
                    connection["account_id"],
                    self.clock(),
                    self.clock(),
                    self.clock() + timedelta(seconds=self.config.job_seconds),
                    self.repo.json(coverage()),
                ),
            )
            return self.repo.public_run(db.fetchone())

    @staticmethod
    def _valid_run(run, connection):
        if (
            connection["status"] != "active"
            or connection["generation"] != run["generation"]
            or connection["account_id"] != run["account_id"]
        ):
            raise ProviderError("import_connection_changed")

    def _run_context(self, workspace, run_id, lease):
        from contextlib import contextmanager

        @contextmanager
        def context():
            with self.repo.worker(workspace, run_id) as (db, run, connection):
                self._valid_run(run, connection)
                if (
                    str(run["lease_id"]) != lease
                    or run["lease_until"] <= self.clock()
                    or run["deadline"] <= self.clock()
                ):
                    raise ProviderError("import_fence_lost")
                yield db, workspace, connection

        return context

    def step_import(self, workspace, run_id):
        """Internal scheduler entry: at most one page per call; no background threads."""
        self.config.require_enabled()
        with self.repo.worker(workspace, run_id) as (db, run, connection):
            if run["status"] in TERMINAL:
                return self.repo.public_run(run)
            self._valid_run(run, connection)
            if run["deadline"] <= self.clock():
                db.execute(
                    "UPDATE toolost_import_runs SET status='partial',error_code='import_deadline',lease_id=NULL,lease_until=NULL WHERE workspace_id=%s AND run_id=%s RETURNING *",
                    (workspace, run_id),
                )
                return self.repo.public_run(db.fetchone())
            if run["available_at"] > self.clock() or (
                run["lease_until"] and run["lease_until"] > self.clock()
            ):
                raise ProviderError("import_busy", retry_after=2)
            lease = str(uuid4())
            db.execute(
                "UPDATE toolost_import_runs SET status='running',lease_id=%s,lease_until=%s WHERE workspace_id=%s AND run_id=%s",
                (
                    lease,
                    self.clock() + timedelta(seconds=self.config.lease_seconds),
                    workspace,
                    run_id,
                ),
            )
            resource = run["resources"][run["resource_index"]]
        context = self._run_context(workspace, run_id, lease)

        def budget():
            with self.repo.worker(workspace, run_id) as (db, current, connection):
                self._valid_run(current, connection)
                if (
                    str(current["lease_id"]) != lease
                    or current["lease_until"] <= self.clock()
                    or current["deadline"] <= self.clock()
                ):
                    raise ProviderError("import_fence_lost")
                if current["call_count"] >= self.config.max_calls:
                    raise ProviderError("import_call_limit")
                db.execute(
                    "UPDATE toolost_import_runs SET call_count=call_count+1 WHERE workspace_id=%s AND run_id=%s",
                    (workspace, run_id),
                )

        try:
            tokens, version = self._tokens(context, reserve=budget)
            try:
                response = self.adapter.get(
                    resource,
                    tokens["access_token"],
                    page=run["next_page"],
                    **self._hooks(budget),
                )
            except ProviderError as error:
                if error.code != "provider_unauthorized":
                    raise
                tokens, _ = self._tokens(context, force_version=version, reserve=budget)
                response = self.adapter.get(
                    resource,
                    tokens["access_token"],
                    page=run["next_page"],
                    **self._hooks(budget),
                )
            facts, totals, terminal = normalize_page(
                resource,
                response,
                run["next_page"],
                max_records=self.config.max_records,
            )
            return self._commit_page(
                workspace, run_id, lease, resource, facts, totals, terminal
            )
        except ProviderError as error:
            self.repo.pause_quota(error)
            return self._fail_import(workspace, run_id, lease, error)

    def _commit_page(self, workspace, run_id, lease, resource, facts, totals, terminal):
        self.config.require_enabled()
        with self.repo.worker(workspace, run_id) as (db, run, connection):
            self._valid_run(run, connection)
            if (
                str(run["lease_id"]) != lease
                or run["lease_until"] <= self.clock()
                or run["deadline"] <= self.clock()
            ):
                raise ProviderError("import_fence_lost")
            if (
                run["page_count"] >= self.config.max_pages
                or run["record_count"] + len(facts) > self.config.max_records
            ):
                raise ProviderError("import_record_or_page_limit")
            if run["expected_totals"] is not None and run["expected_totals"] != totals:
                raise ProviderError("provider_pagination_changed")
            page_hash = fingerprint(facts)
            db.execute(
                "SELECT 1 FROM toolost_import_pages WHERE workspace_id=%s AND run_id=%s AND resource=%s AND fingerprint=%s",
                (workspace, run_id, resource, page_hash),
            )
            if db.fetchone():
                raise ProviderError("provider_repeated_page")
            keys = [fact["key"] for fact in facts]
            db.execute(
                "SELECT 1 FROM toolost_source_facts WHERE workspace_id=%s AND run_id=%s AND resource=%s AND record_key=ANY(%s)",
                (workspace, run_id, resource, keys),
            )
            if db.fetchone():
                raise ProviderError("provider_duplicate_record")
            db.execute(
                "INSERT INTO toolost_import_pages VALUES(%s,%s,%s,%s,%s,%s)",
                (
                    workspace,
                    run_id,
                    resource,
                    run["next_page"],
                    page_hash,
                    self.clock(),
                ),
            )
            for fact in facts:
                db.execute(
                    """INSERT INTO toolost_source_facts
                    (workspace_id,run_id,resource,page,record_key,payload,amount)
                    VALUES(%s,%s,%s,%s,%s,%s,%s)""",
                    (
                        workspace,
                        run_id,
                        resource,
                        run["next_page"],
                        fact["key"],
                        self.repo.json(fact["payload"]),
                        fact["amount"],
                    ),
                )
            if resource == "releases" and terminal and run["selection"]:
                db.execute(
                    "SELECT record_key FROM toolost_source_facts WHERE workspace_id=%s AND run_id=%s AND resource='releases'",
                    (workspace, run_id),
                )
                if not set(run["selection"]).issubset(
                    {row["record_key"] for row in db.fetchall()}
                ):
                    raise ProviderError("selected_release_missing")
            resource_index = run["resource_index"] + int(terminal)
            done = resource_index == len(run["resources"])
            db.execute(
                """UPDATE toolost_import_runs SET resource_index=%s,next_page=%s,
                expected_totals=%s,page_count=page_count+1,record_count=record_count+%s,
                status=%s,failures=0,error_code=NULL,lease_id=NULL,lease_until=NULL
                WHERE workspace_id=%s AND run_id=%s RETURNING *""",
                (
                    resource_index,
                    1 if terminal else run["next_page"] + 1,
                    self.repo.json(totals) if not terminal else None,
                    len(facts),
                    "complete" if done else "queued",
                    workspace,
                    run_id,
                ),
            )
            return self.repo.public_run(db.fetchone())

    def _fail_import(self, workspace, run_id, lease, error):
        with self.repo.worker(workspace, run_id) as (db, run, _):
            if str(run["lease_id"]) != lease:
                return self.repo.public_run(run)
            retry = (
                error.retry_after is not None
                and run["failures"] < 2
                and self.clock() + timedelta(seconds=error.retry_after)
                < run["deadline"]
            )
            db.execute(
                """UPDATE toolost_import_runs SET status=%s,error_code=%s,
                failures=failures+1,available_at=%s,lease_id=NULL,lease_until=NULL
                WHERE workspace_id=%s AND run_id=%s RETURNING *""",
                (
                    "retryable" if retry else "partial",
                    error.code,
                    self.clock() + timedelta(seconds=error.retry_after or 0),
                    workspace,
                    run_id,
                ),
            )
            return self.repo.public_run(db.fetchone())

    def import_status(self, session, run_id):
        with self.repo.owner(session) as (db, actor):
            db.execute(
                "SELECT * FROM toolost_import_runs WHERE workspace_id=%s AND run_id=%s",
                (actor.workspace, str(UUID(str(run_id)))),
            )
            run = db.fetchone()
            if not run:
                raise ProviderError("import_unavailable")
            self.repo.connection(db, actor.workspace, run["connection_id"])
            return self.repo.public_run(run)

    def snapshot(self, session, run_id):
        with self.repo.owner(session) as (db, actor):
            db.execute(
                "SELECT * FROM toolost_import_runs WHERE workspace_id=%s AND run_id=%s",
                (actor.workspace, str(UUID(str(run_id)))),
            )
            run = db.fetchone()
            if not run:
                raise ProviderError("import_unavailable")
            if run["status"] != "complete":
                raise ProviderError("import_not_complete")
            self.repo.connection(db, actor.workspace, run["connection_id"])
            db.execute(
                "SELECT resource,page,record_key,payload FROM toolost_source_facts WHERE workspace_id=%s AND run_id=%s ORDER BY resource,page,record_key",
                (actor.workspace, run_id),
            )
            return {
                **self.repo.public_run(run),
                "manifest": run["manifest"],
                "facts": [dict(row) for row in db.fetchall()],
            }
