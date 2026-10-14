"""Core erasure extension; never use ordinary runtime credentials for deletion."""

from uuid import UUID

from .contracts import ProviderError

ERASURE_TABLES = (
    "toolost_source_facts",
    "toolost_import_pages",
    "toolost_import_runs",
    "toolost_oauth_attempts",
    "toolost_connections",
)


class ProviderErasureParticipant:
    """Register with core erase_workspace(extensions=(participant, ...)).

    The caller owns the transaction and verifies the durable external tombstone.
    This participant never changes that journal, workspace status or source keys.
    """

    def erase_in_transaction(self, cur, workspace):
        workspace = str(UUID(str(workspace)))
        cur.execute("SELECT current_setting('space.workspace_id',true) AS workspace")
        if cur.fetchone()["workspace"] != workspace:
            raise ProviderError("erasure_workspace_mismatch")
        cur.execute(
            "SELECT rolsuper,rolbypassrls FROM pg_roles WHERE rolname=current_user"
        )
        role = cur.fetchone()
        if role["rolsuper"] or role["rolbypassrls"]:
            raise ProviderError("dedicated_scoped_erasure_role_required")
        for table in ERASURE_TABLES:
            cur.execute(
                """SELECT has_table_privilege(current_user,%s,'DELETE') AS allowed,
                relrowsecurity AND relforcerowsecurity AS isolated,
                pg_get_userbyid(relowner)=current_user AS owned
                FROM pg_class WHERE oid=to_regclass(%s)""",
                (table, "public." + table),
            )
            permissions = cur.fetchone()
            if (
                not permissions
                or not permissions["allowed"]
                or not permissions["isolated"]
                or permissions["owned"]
            ):
                raise ProviderError("dedicated_scoped_erasure_role_required")
        cur.execute(
            "SELECT workspace_id FROM workspaces WHERE workspace_id=%s FOR UPDATE",
            (workspace,),
        )
        cur.execute(
            """UPDATE toolost_connections SET generation=generation+1,
            status='disconnected',credentials=NULL,refresh_lease=NULL,refresh_until=NULL
            WHERE workspace_id=%s""",
            (workspace,),
        )
        cur.execute(
            """UPDATE toolost_import_runs SET status='cancelled',
            lease_id=NULL,lease_until=NULL WHERE workspace_id=%s""",
            (workspace,),
        )
        counts = {}
        for table in ERASURE_TABLES:
            cur.execute("DELETE FROM " + table + " WHERE workspace_id=%s", (workspace,))
            counts[table] = cur.rowcount
        return counts
