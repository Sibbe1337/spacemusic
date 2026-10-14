"""Explicit erasure primitives. Run with separate scoped erasure credentials.

Not a lifecycle-policy assertion: every live object and backup version must be
confirmed absent. External form/mail actions are reported separately.
"""

from uuid import UUID

from .database import Database
from .security import ReviewError


class ErasureUnconfirmed(RuntimeError):
    pass


class ErasureDatabase(Database):
    """Distinct operator-owned credentials, still subject to workspace RLS."""

    def __init__(self, dsn):
        self._dsn = dsn
        with self.transaction() as db:
            db.execute(
                "SELECT rolname,rolsuper,rolbypassrls,rolcreaterole,rolcreatedb FROM pg_roles WHERE rolname=current_user"
            )
            role = db.fetchone()
            if role["rolname"] != "review_erasure" or any(
                role[name]
                for name in ("rolsuper", "rolbypassrls", "rolcreaterole", "rolcreatedb")
            ):
                raise RuntimeError("Separate constrained erasure role required")
            db.execute("""SELECT 1 FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace
                WHERE n.nspname='public' AND c.relkind='r' AND
                (pg_get_userbyid(c.relowner)=current_user OR
                 has_table_privilege(current_user,c.oid,'TRUNCATE') OR
                 (EXISTS (SELECT 1 FROM pg_attribute a WHERE a.attrelid=c.oid AND a.attname='workspace_id')
                  AND c.relname NOT IN ('receipts','intake_admissions') AND
                  (NOT c.relrowsecurity OR NOT c.relforcerowsecurity)))""")
            if db.fetchone():
                raise RuntimeError("Unsafe erasure privileges or RLS")


class VersionedBackupStore:
    def __init__(self, client, bucket):
        self.client, self.bucket = client, bucket
        self._check_client()

    def _check_client(self):
        if self.client.meta.endpoint_url != "https://s3.fr-par.scw.cloud":
            raise ValueError("Paris backup endpoint required")
        endpoint = getattr(self.client, "_endpoint", None)
        if (
            getattr(endpoint, "host", None) != "https://s3.fr-par.scw.cloud"
            or getattr(getattr(endpoint, "http_session", None), "_verify", None)
            is not True
        ):
            raise ValueError("Backup TLS verification required")
        for name in ("read_timeout", "connect_timeout"):
            value = getattr(self.client.meta.config, name, None)
            if type(value) not in (int, float) or not 0 < value <= 10:
                raise ValueError("Bounded backup transport required")

    def versions(self, workspace):
        self._check_client()
        prefix = str(UUID(str(workspace))) + "/"
        args = {"Bucket": self.bucket, "Prefix": prefix, "MaxKeys": 1000}
        found, markers = [], set()
        for _ in range(100):
            response = self.client.list_object_versions(**args)
            for row in response.get("Versions", []) + response.get("DeleteMarkers", []):
                if not row["Key"].startswith(prefix) or not row.get("VersionId"):
                    raise ErasureUnconfirmed("Invalid version inventory")
                found.append({"Key": row["Key"], "VersionId": row["VersionId"]})
            if response.get("IsTruncated") is False:
                return found
            marker = (
                response.get("NextKeyMarker"),
                response.get("NextVersionIdMarker"),
            )
            if not all(marker) or marker in markers:
                raise ErasureUnconfirmed("Incomplete version inventory")
            markers.add(marker)
            args.update(KeyMarker=marker[0], VersionIdMarker=marker[1])
        raise ErasureUnconfirmed("Version inventory exceeds review limit")

    def erase_and_verify(self, workspace):
        for version in self.versions(workspace):
            self._check_client()
            self.client.delete_object(Bucket=self.bucket, **version)
        if self.versions(workspace):
            raise ErasureUnconfirmed("Backup versions remain")


def erase_workspace(
    database, journal, workspace, live_store, backup_store, *, extensions=()
):
    """Delete only a journal-blocked workspace; retain minimal source suppression.

    Each installed subsystem must supply an erasure participant. Deployment stays
    closed until that inventory and the separate-role grants have been reviewed.
    Object failures stop database erasure so operators can retry the same manifest.
    """
    workspace = str(UUID(str(workspace)))
    with database.transaction(workspace) as db:
        db.execute(
            "SELECT source_digest FROM receipts WHERE workspace_id=%s", (workspace,)
        )
        receipt = db.fetchone()
        if not journal.reconcile(
            workspace, receipt["source_digest"] if receipt else None
        ):
            raise ReviewError("durable_deletion_required", 409)
        db.execute(
            "SELECT status FROM workspaces WHERE workspace_id=%s FOR UPDATE",
            (workspace,),
        )
        row = db.fetchone()
        # Independent prefix inventory includes orphan writes and cases missing
        # from restored databases. Never infer absence from an empty DB manifest.
        live_store.erase_and_verify(workspace)
        # Check even after rows are gone: an older backup process may have left
        # versions; its deployment generation must also be fenced externally.
        backup_store.erase_and_verify(workspace)
        for participant in extensions:
            participant.erase_in_transaction(db, workspace)
        if row:
            for table in (
                "dealflow_decisions",
                "dealflow_packages",
                "dealflow_reviews",
                "review_supplements",
                "review_replies",
                "documents",
                "review_questions",
                "submissions",
                "outbox",
                "invitations",
                "sessions",
                "memberships",
                "interest_events",
                "retention_notices",
                "audit",
                "workspaces",
            ):
                db.execute(
                    "DELETE FROM " + table + " WHERE workspace_id=%s", (workspace,)
                )
    return {
        "portal_records_erased": True,
        "object_versions_confirmed_absent": True,
        "database_backup_expiry_days": 7,
        "all_backups_erased": False,
        "source_system_actions": "pending_separate_verification",
    }
