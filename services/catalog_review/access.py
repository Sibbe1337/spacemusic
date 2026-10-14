"""Mailbox possession is still required; recovery never returns a login token."""

import hmac
from datetime import timedelta
from uuid import uuid4

from .contracts import LiveRequestAccess, RequestAccess


class AccessRecovery:
    def request_access(self, value):
        item = (
            LiveRequestAccess if self.settings.mode == "production" else RequestAccess
        ).model_validate(value)
        workspace, now = str(item.workspace_id), self.clock()
        result = {"status": "request_received"}
        with self.db.transaction(workspace) as db:
            db.execute(
                "SELECT status FROM workspaces WHERE workspace_id=%s FOR UPDATE",
                (workspace,),
            )
            row = db.fetchone()
            if not row or row["status"] != "active":
                return result
            if self.deletion_journal and self.deletion_journal.contains(workspace):
                return result
            if self.deletion_journal:
                db.execute(
                    "SELECT source_digest FROM receipts WHERE workspace_id=%s",
                    (workspace,),
                )
                source = db.fetchone()
                if source and self.deletion_journal.suppresses(source["source_digest"]):
                    return result
            db.execute(
                """SELECT i.* FROM invitations i JOIN memberships m
                USING(workspace_id,principal_id) WHERE m.active AND m.role='owner'
                ORDER BY i.expires_at DESC LIMIT 1"""
            )
            latest = db.fetchone()
            if not latest or not hmac.compare_digest(
                latest["recipient"].encode(), item.email.encode()
            ):
                return result
            # Do not invalidate a usable invitation or send duplicate mail while
            # an invitation is pending. Expired links can be replaced, bounded by
            # a per-workspace hourly cap in addition to the HTTP peer throttle.
            if latest["expires_at"] > now and latest["consumed_at"] is None:
                return result
            # A consumed link cannot log the owner in again. Permit replacement
            # after a one-minute cooldown without revoking any active session.
            if latest["expires_at"] - timedelta(minutes=15) > now - timedelta(
                minutes=1
            ):
                return result
            db.execute(
                "SELECT count(*) AS count FROM invitations WHERE expires_at>%s",
                (now - timedelta(minutes=45),),
            )
            if db.fetchone()["count"] >= 5:
                return result
            invitation = str(uuid4())
            token = self.invitation_token(workspace, invitation)
            db.execute(
                """INSERT INTO invitations
                (workspace_id,invitation_id,principal_id,recipient,token_digest,expires_at)
                VALUES(%s,%s,%s,%s,%s,%s)""",
                (
                    workspace,
                    invitation,
                    latest["principal_id"],
                    latest["recipient"],
                    self._hash("invitation", token),
                    now + timedelta(minutes=15),
                ),
            )
            db.execute(
                "INSERT INTO outbox(workspace_id,invitation_id,available_at) VALUES(%s,%s,%s)",
                (workspace, invitation, now),
            )
            self._audit(db, workspace, "access_requested")
        return result
