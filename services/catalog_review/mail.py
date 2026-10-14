"""Opt-in Scaleway TEM adapter and durable at-most-one-POST invitation dispatcher.

TEM does not document a send-idempotency contract. No Idempotency-Key is invented.
Never use this adapter with workers.deliver_invitation, which blindly retries
exceptions. The composition root must exclusively select this dispatcher for TEM.
Unknown acceptance, including a crashed worker, remains uncertain indefinitely
until an operator reconciles it. A 404 lookup is NOT permission to send again.
No external client is constructed until TEMTransport is explicitly instantiated;
even then sending defaults off. Tests inject httpx.MockTransport, never credentials.

https://www.scaleway.com/en/developers/api/transactional-email/emails
https://www.scaleway.com/en/docs/transactional-email/how-to/manage-email-activity/
"""

import json
import re
import time
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from urllib.parse import urlsplit
from uuid import UUID, uuid4

import httpx

from .intake import normalize_email
from .security import ReviewError

TEM_URL = "https://api.scaleway.com/transactional-email/v1alpha1/regions/fr-par/emails"
PORTAL_ORIGINS = {
    "https://review.test",
    "https://review.spacemusic.io",
    "https://review-staging.spacemusic.io",
}
MAX_RESPONSE = 64 * 1024


@dataclass(frozen=True)
class MailResult:
    status: str
    reason: str
    provider_reference: str = field(default=None, repr=False)


@dataclass(frozen=True, repr=False)
class PreparedMail:
    """Sensitive in-memory payload; never log, persist or return to the browser."""

    payload: dict
    recipient: str
    expires_at: datetime


class TEMTransport:
    """No redirect, ambient proxy, SDK retry, or automatic POST retry.

    The injected httpx transport is trusted not to retry POSTs itself. Use
    dispatch(), not _send_once(), to retain the durable no-blind-retry guarantee.
    fr-par is an API selection, NOT an attestation of all processing residency.
    """

    def __init__(
        self,
        *,
        token,
        project_id,
        sender,
        portal_origin,
        enabled=False,
        http_transport=None,
        clock=None,
    ):
        if (
            not isinstance(token, str)
            or not 1 <= len(token) <= 512
            or any(ord(c) < 33 or ord(c) > 126 for c in token)
        ):
            raise ValueError("Invalid TEM credential")
        try:
            self._project_id = str(UUID(str(project_id)))
        except (TypeError, ValueError):
            raise ValueError("Invalid TEM project") from None
        if portal_origin not in PORTAL_ORIGINS or type(enabled) is not bool:
            raise ValueError("Invalid mail configuration")
        self._sender = normalize_email(sender)
        self._origin = portal_origin
        self.enabled = enabled
        self.clock = clock or (lambda: datetime.now(timezone.utc))
        self._client = httpx.Client(
            transport=http_transport,
            trust_env=False,
            follow_redirects=False,
            timeout=httpx.Timeout(10.0, connect=5.0),
            headers={"X-Auth-Token": token, "Accept": "application/json"},
        )

    def close(self):
        self._client.close()

    def prepare(self, *, recipient, url, expires_at):
        recipient = normalize_email(recipient)
        try:
            parsed = urlsplit(url)
            if (
                parsed.scheme + "://" + parsed.netloc != self._origin
                or parsed.path != "/workspace/"
                or parsed.query
                or not re.fullmatch(
                    r"invitation=[A-Za-z0-9_.-]{70,160}", parsed.fragment
                )
                or any(ord(c) < 33 for c in url)
            ):
                raise ValueError()
            if not isinstance(expires_at, datetime) or expires_at.tzinfo is None:
                raise ValueError()
        except (ValueError, TypeError, AttributeError):
            raise ReviewError("invalid_invitation_mail", 422) from None
        return PreparedMail(
            payload={
                "project_id": self._project_id,
                "from": {"email": self._sender, "name": "SPACE"},
                "to": [{"email": recipient}],
                "subject": "Your SPACE catalog review invitation",
                "text": "Open your invitation to continue your catalog review:\n\n"
                + url
                + "\n\nThe link expires at "
                + expires_at.astimezone(timezone.utc).isoformat()
                + ". Opening the page does not consume the invitation; choose Open invitation to continue."
                + "\n\nIf you did not request this review, ignore this message.",
                "send_before": expires_at.astimezone(timezone.utc).isoformat(),
            },
            recipient=recipient,
            expires_at=expires_at,
        )

    def _request(self, method, url, payload=None):
        started = time.monotonic()
        try:
            with self._client.stream(method, url, json=payload) as response:
                if response.status_code != 200:
                    return response.status_code, None
                if (
                    response.headers.get("content-type", "")
                    .split(";", 1)[0]
                    .strip()
                    .lower()
                    != "application/json"
                ):
                    return 200, None
                body = bytearray()
                for chunk in response.iter_bytes():
                    if (
                        len(body) + len(chunk) > MAX_RESPONSE
                        or time.monotonic() - started > 15
                    ):
                        return 200, None
                    body.extend(chunk)
                return 200, json.loads(body)
        except Exception:
            # Exception chains and response bodies can contain credentials/URLs.
            return None, None

    def prepare_retention(self, *, recipient, workspace, deadline):
        recipient = normalize_email(recipient)
        try:
            workspace = str(UUID(str(workspace)))
            if not isinstance(deadline, datetime) or deadline.tzinfo is None:
                raise ValueError()
        except (TypeError, ValueError):
            raise ReviewError("invalid_retention_mail", 422) from None
        date = deadline.astimezone(timezone.utc).isoformat()
        return PreparedMail(
            payload={
                "project_id": self._project_id,
                "from": {"email": self._sender, "name": "SPACE"},
                "to": [{"email": recipient}],
                "subject": "Your SPACE review retention deadline",
                "text": "Your SPACE catalog review case is scheduled for deletion after inactivity."
                + "\n\nCase ID: "
                + workspace
                + "\nCurrent deletion deadline (UTC): "
                + date
                + "\n\nOpen "
                + self._origin
                + "/workspace/"
                + " to sign in and review your case. You will need a usable invitation or an active session."
                + " This email is not an access link."
                + '\n\nTo keep your case open, choose "I want to continue this review" in the portal before the deadline.'
                + " Receiving or opening this email does not extend the retention period.",
                "send_before": date,
            },
            recipient=recipient,
            expires_at=deadline,
        )

    def _record_result(self, record, recipient, expected_id=None):
        try:
            reference = str(UUID(record["id"]))
            if (
                expected_id is not None
                and reference != expected_id
                or record["project_id"] != self._project_id
                or record["mail_from"] != self._sender
                or record["mail_rcpt"] != recipient
            ):
                raise ValueError()
            status, flags = record["status"], record.get("flags", [])
            if not isinstance(flags, list) or any(
                not isinstance(flag, str) for flag in flags
            ):
                raise ValueError()
            if status == "failed":
                if "hard_bounce" in flags or "mailbox_not_found" in flags:
                    return MailResult("bounced", "provider_bounced", reference)
                return MailResult("failed", "provider_failed", reference)
            statuses = {
                "new": "accepted",
                "sending": "accepted",
                "sent": "delivered",
                "canceled": "canceled",
            }
            if status in statuses:
                return MailResult(statuses[status], "provider_" + status, reference)
            return MailResult("uncertain", "provider_status_unknown", reference)
        except (ValueError, TypeError, KeyError, AttributeError):
            return MailResult("uncertain", "provider_response_invalid")

    def _send_once(self, message):
        if not self.enabled:
            raise ReviewError("mail_transport_disabled", 503)
        if message.expires_at <= self.clock():
            return MailResult("canceled", "invitation_expired")
        status, payload = self._request("POST", TEM_URL, message.payload)
        if status in (400, 401, 403, 404, 413, 422):
            return MailResult("failed", "provider_rejected")
        if status != 200 or not isinstance(payload, dict):
            return MailResult("uncertain", "acceptance_unconfirmed")
        records = payload.get("emails")
        if not isinstance(records, list) or len(records) != 1:
            return MailResult("uncertain", "provider_response_invalid")
        return self._record_result(records[0], message.recipient)

    def lookup(self, *, provider_reference, recipient):
        """Only an acknowledged provider UUID is lookup authority, not an email match."""
        if not self.enabled:
            raise ReviewError("mail_transport_disabled", 503)
        try:
            reference = str(UUID(str(provider_reference)))
        except ValueError:
            raise ReviewError("invalid_provider_reference", 422) from None
        status, record = self._request("GET", TEM_URL + "/" + reference)
        if status != 200 or not isinstance(record, dict):
            return MailResult("uncertain", "lookup_unconfirmed", reference)
        return self._record_result(record, normalize_email(recipient), reference)


class MailDispatcher:
    """Trusted worker boundary; not an unauthenticated send endpoint.

    Requires exclusive ownership of invitation delivery. Disable the legacy
    outbox worker in the composition root. url_for(workspace, invitation) must
    reconstruct the original invitation, not mint a replacement on each attempt.
    current_workspace_guard(cursor, workspace) must lock the core workspace,
    check its active state AND the current external deletion journal, and raise
    on denial or journal failure. Bind the production core _active hook only
    with a mandatory journal; an explicit test profile may use its test guard.
    All coordination uses portal_mail_attempts from intake-schema.sql.
    """

    def __init__(self, db, transport, *, url_for, current_workspace_guard, clock=None):
        if not callable(current_workspace_guard):
            raise ValueError("Current workspace/deletion-journal guard required")
        self.db, self.transport, self._url_for = db, transport, url_for
        self._guard = current_workspace_guard
        self.clock = clock or (lambda: datetime.now(timezone.utc))

    @staticmethod
    def enqueue_in_transaction(cur, workspace, invitation, now):
        cur.execute(
            """INSERT INTO portal_mail_attempts
            (workspace_id,invitation_id,created_at,updated_at) VALUES(%s,%s,%s,%s)
            ON CONFLICT DO NOTHING""",
            (workspace, invitation, now, now),
        )

    @staticmethod
    def _view(row):
        return MailResult(
            row["status"],
            row["reason"],
            str(row["provider_reference"]) if row["provider_reference"] else None,
        )

    def dispatch(self, workspace, invitation):
        if not self.transport.enabled:
            raise ReviewError("mail_transport_disabled", 503)
        workspace, invitation = str(UUID(str(workspace))), str(UUID(str(invitation)))
        with self.db.transaction(workspace) as cur:
            self._guard(cur, workspace)
            # Same lock as core revocation/deletion; never resurrect a stopped job.
            cur.execute(
                "SELECT status FROM workspaces WHERE workspace_id=%s FOR UPDATE",
                (workspace,),
            )
            state = cur.fetchone()
            cur.execute(
                """SELECT i.*,m.active,m.role FROM invitations i JOIN memberships m
                USING(workspace_id,principal_id) WHERE i.invitation_id=%s""",
                (invitation,),
            )
            item = cur.fetchone()
            if not state or not item:
                raise ReviewError("invitation_unavailable", 404)
            self.enqueue_in_transaction(cur, workspace, invitation, self.clock())
            cur.execute(
                "SELECT * FROM portal_mail_attempts WHERE invitation_id=%s FOR UPDATE",
                (invitation,),
            )
            row = cur.fetchone()
            if row["status"] != "queued":
                return self._view(row)
            if (
                state["status"] != "active"
                or not item["active"]
                or item["role"] != "owner"
                or item["consumed_at"] is not None
                or item["expires_at"] <= self.clock()
            ):
                cur.execute(
                    "UPDATE portal_mail_attempts SET status='canceled',reason='invitation_unavailable',updated_at=%s WHERE invitation_id=%s",
                    (self.clock(), invitation),
                )
                return MailResult("canceled", "invitation_unavailable")
            message = self.transport.prepare(
                recipient=item["recipient"],
                url=self._url_for(workspace, invitation),
                expires_at=item["expires_at"],
            )
            attempt = str(uuid4())
            cur.execute(
                """UPDATE portal_mail_attempts SET status='uncertain',attempt_id=%s,
                reason='dispatch_started',updated_at=%s WHERE invitation_id=%s""",
                (attempt, self.clock(), invitation),
            )
        # A lost commit acknowledgement raises before this POST. A crash here
        # deliberately leaves uncertain, rather than permitting duplicate mail.
        with self.db.transaction(workspace) as cur:
            # Mandatory fresh external-journal check, even after a database restore.
            # Hold the core workspace lock through the POST so core deletion and
            # revocation cannot start a conflicting transaction between this
            # check and dispatch. External journal failures propagate fail-closed.
            self._guard(cur, workspace)
            cur.execute(
                "SELECT * FROM portal_mail_attempts WHERE invitation_id=%s FOR UPDATE",
                (invitation,),
            )
            current = cur.fetchone()
            if (
                not current
                or current["status"] != "uncertain"
                or str(current["attempt_id"]) != attempt
            ):
                if current:
                    return self._view(current)
                raise ReviewError("mail_attempt_unavailable", 404)
            cur.execute(
                """SELECT i.expires_at,i.consumed_at,m.active,m.role FROM invitations i
                JOIN memberships m USING(workspace_id,principal_id) WHERE invitation_id=%s""",
                (invitation,),
            )
            latest = cur.fetchone()
            if (
                not latest
                or not latest["active"]
                or latest["role"] != "owner"
                or latest["consumed_at"] is not None
                or latest["expires_at"] <= self.clock()
            ):
                result = MailResult("canceled", "invitation_unavailable")
            else:
                try:
                    result = self.transport._send_once(message)
                except Exception:
                    result = MailResult("uncertain", "acceptance_unconfirmed")
            cur.execute(
                """UPDATE portal_mail_attempts SET status=%s,reason=%s,
                provider_reference=%s,updated_at=%s WHERE invitation_id=%s
                AND attempt_id=%s AND status='uncertain'""",
                (
                    result.status,
                    result.reason,
                    result.provider_reference,
                    self.clock(),
                    invitation,
                    attempt,
                ),
            )
        return result

    def refresh(self, workspace, invitation):
        workspace, invitation = str(UUID(str(workspace))), str(UUID(str(invitation)))
        with self.db.transaction(workspace) as cur:
            self._guard(cur, workspace)
            cur.execute(
                """SELECT a.*,i.recipient FROM portal_mail_attempts a JOIN invitations i
                USING(workspace_id,invitation_id) WHERE invitation_id=%s""",
                (invitation,),
            )
            row = cur.fetchone()
            if not row:
                raise ReviewError("mail_attempt_unavailable", 404)
            if not row["provider_reference"] or row["status"] in (
                "bounced",
                "failed",
                "canceled",
            ):
                return self._view(row)
        result = self.transport.lookup(
            provider_reference=str(row["provider_reference"]),
            recipient=row["recipient"],
        )
        with self.db.transaction(workspace) as cur:
            self._guard(cur, workspace)
            cur.execute(
                "SELECT * FROM portal_mail_attempts WHERE invitation_id=%s FOR UPDATE",
                (invitation,),
            )
            current = cur.fetchone()
            allowed = {
                "uncertain": {"accepted", "delivered", "bounced", "failed", "canceled"},
                "accepted": {"delivered", "bounced", "failed", "canceled"},
                "delivered": {"bounced"},
            }
            if result.status in allowed.get(current["status"], set()):
                cur.execute(
                    "UPDATE portal_mail_attempts SET status=%s,reason=%s,updated_at=%s WHERE invitation_id=%s",
                    (result.status, result.reason, self.clock(), invitation),
                )
                return result
            return self._view(current)

    @staticmethod
    def _retention_version(value):
        if type(value) is not int or value < 0:
            raise ReviewError("invalid_activity_version", 422)
        return value

    def _retention_rows(self, cur, workspace, version):
        self._guard(cur, workspace)
        cur.execute(
            "SELECT * FROM workspaces WHERE workspace_id=%s FOR UPDATE", (workspace,)
        )
        state = cur.fetchone()
        if not state or state["status"] != "active":
            raise ReviewError("workspace_unavailable", 404)
        cur.execute(
            "SELECT * FROM retention_notices WHERE workspace_id=%s AND activity_version=%s FOR UPDATE",
            (workspace, version),
        )
        notice = cur.fetchone()
        if not notice:
            raise ReviewError("retention_notice_unavailable", 404)
        return state, notice

    @staticmethod
    def _retention_recipient(cur, workspace):
        # Never guess between owners or differing original owner addresses.
        cur.execute(
            """SELECT DISTINCT i.recipient,m.principal_id FROM invitations i JOIN memberships m
            USING(workspace_id,principal_id) WHERE i.workspace_id=%s AND m.role='owner' AND m.active""",
            (workspace,),
        )
        rows = cur.fetchall()
        return rows[0]["recipient"] if len(rows) == 1 else None

    def _retention_invalid(self, state, notice, version):
        if state["activity_version"] != version or notice["deadline"] != state[
            "last_activity_at"
        ] + timedelta(days=90):
            return "notice_superseded"
        if (
            not notice["deadline"] - timedelta(days=14)
            <= self.clock()
            < notice["deadline"]
        ):
            return "outside_notice_window"
        return None

    @classmethod
    def _retention_view(cls, notice):
        # SQL keeps the existing British spelling; MailResult uses one vocabulary.
        return cls._view(
            {
                **notice,
                "status": "canceled"
                if notice["status"] == "cancelled"
                else notice["status"],
            }
        )

    def _finish_retention(self, cur, workspace, version, result):
        cur.execute(
            """UPDATE retention_notices SET status=%s,reason=%s,provider_reference=%s,updated_at=%s
            WHERE workspace_id=%s AND activity_version=%s""",
            (
                "cancelled" if result.status == "canceled" else result.status,
                result.reason,
                result.provider_reference,
                self.clock(),
                workspace,
                version,
            ),
        )

    def dispatch_retention(self, workspace, activity_version):
        """Deliver only a prequeued notice. Unknown acceptance is never requeued.

        Neither dispatch nor provider reconciliation updates case activity.
        failed/bounced/uncertain are operator-attention states, not extensions.
        """
        if not self.transport.enabled:
            raise ReviewError("mail_transport_disabled", 503)
        workspace = str(UUID(str(workspace)))
        version = self._retention_version(activity_version)
        with self.db.transaction(workspace) as cur:
            state, notice = self._retention_rows(cur, workspace, version)
            if notice["status"] != "queued":
                return self._retention_view(notice)
            invalid = self._retention_invalid(state, notice, version)
            recipient = self._retention_recipient(cur, workspace)
            if invalid or recipient is None:
                result = (
                    MailResult("canceled", invalid)
                    if invalid
                    else MailResult("failed", "owner_recipient_unavailable")
                )
                self._finish_retention(cur, workspace, version, result)
                return result
            message = self.transport.prepare_retention(
                recipient=recipient,
                workspace=workspace,
                deadline=notice["deadline"],
            )
            cur.execute(
                """UPDATE retention_notices SET status='uncertain',attempt_id=%s,
                reason='dispatch_started',updated_at=%s WHERE workspace_id=%s AND activity_version=%s""",
                (str(uuid4()), self.clock(), workspace, version),
            )
        # Unknown commit outcomes raise before any network request. The next
        # transaction holds the same core lock through the final check and POST.
        with self.db.transaction(workspace) as cur:
            state, notice = self._retention_rows(cur, workspace, version)
            if notice["status"] != "uncertain":
                return self._retention_view(notice)
            invalid = self._retention_invalid(state, notice, version)
            if invalid or self._retention_recipient(cur, workspace) != recipient:
                result = MailResult("canceled", invalid or "owner_recipient_changed")
            else:
                try:
                    result = self.transport._send_once(message)
                except Exception:
                    result = MailResult("uncertain", "acceptance_unconfirmed")
            self._finish_retention(cur, workspace, version, result)
        return result

    def refresh_retention(self, workspace, activity_version):
        """Poll only an acknowledged provider ID; this method never sends mail."""
        workspace = str(UUID(str(workspace)))
        version = self._retention_version(activity_version)
        with self.db.transaction(workspace) as cur:
            _, notice = self._retention_rows(cur, workspace, version)
            if not notice["provider_reference"] or notice["status"] in (
                "bounced",
                "failed",
                "cancelled",
            ):
                return self._retention_view(notice)
            recipient = self._retention_recipient(cur, workspace)
            if recipient is None:
                raise ReviewError("retention_recipient_unavailable", 409)
        result = self.transport.lookup(
            provider_reference=str(notice["provider_reference"]), recipient=recipient
        )
        with self.db.transaction(workspace) as cur:
            _, current = self._retention_rows(cur, workspace, version)
            allowed = {
                "uncertain": {"accepted", "delivered", "bounced", "failed", "canceled"},
                "accepted": {"delivered", "bounced", "failed", "canceled"},
                "delivered": {"bounced"},
            }
            if result.status in allowed.get(current["status"], set()):
                self._finish_retention(cur, workspace, version, result)
                return result
            return self._retention_view(current)
