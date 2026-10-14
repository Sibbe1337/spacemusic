"""Bounded, explicit pilot job ticks. No scheduler starts on module import.

Run scan ticks in the single scanner-worker service. Other ticks use the API
worker identity. Erasure is a separate process/credential; no deletion privilege
is made available to this runner. Providers are deliberately not scheduled here.
"""

from threading import BoundedSemaphore

from .security import ReviewError
from .workers import scan_document


class PilotJobs:
    def __init__(
        self, service, *, require_ready, mail_dispatcher, blobs, scanner, parser
    ):
        self.service = service
        self.require_ready = require_ready
        self.mail = mail_dispatcher
        self.blobs, self.scanner, self.parser = blobs, scanner, parser
        self._scan_slot = BoundedSemaphore(1)

    def _workspaces(self):
        self.require_ready()
        with self.service.db.transaction() as db:
            db.execute(
                "SELECT workspace_id FROM receipts ORDER BY workspace_id LIMIT 6"
            )
            rows = db.fetchall()
        if len(rows) > 5:
            raise ReviewError("pilot_inventory_limit", 503)
        return [str(row["workspace_id"]) for row in rows]

    def scan_tick(self):
        if not self._scan_slot.acquire(blocking=False):
            return {"processed": 0, "status": "busy"}
        try:
            for workspace in self._workspaces():
                self.require_ready()
                try:
                    with self.service.db.transaction(workspace) as db:
                        self.service._active(db, workspace)
                        db.execute(
                            """SELECT document_id FROM documents WHERE scan_attempts<3
                            AND (status='quarantined' OR (status='scanning' AND scan_lease_until<=%s))
                            ORDER BY document_id LIMIT 1""",
                            (self.service.clock(),),
                        )
                        row = db.fetchone()
                    if row:
                        result = scan_document(
                            self.service,
                            workspace,
                            str(row["document_id"]),
                            self.blobs,
                            self.scanner,
                            self.parser,
                        )
                        return {"processed": 1, "status": result}
                except ReviewError as error:
                    if error.code != "workspace_unavailable":
                        raise
            return {"processed": 0, "status": "idle"}
        finally:
            self._scan_slot.release()

    def mail_tick(self):
        processed = 0
        for workspace in self._workspaces():
            self.require_ready()
            try:
                with self.service.db.transaction(workspace) as db:
                    self.service._active(db, workspace)
                    db.execute(
                        "SELECT invitation_id FROM outbox WHERE status='queued' ORDER BY available_at LIMIT 1"
                    )
                    row = db.fetchone()
                if row:
                    self.mail.dispatch(workspace, str(row["invitation_id"]))
                    processed += 1
            except ReviewError as error:
                if error.code != "workspace_unavailable":
                    raise
        return {"processed": processed}

    def retention_tick(self):
        queued, expired = 0, 0
        for workspace in self._workspaces():
            self.require_ready()
            try:
                state = self.service.retention_state(workspace)
                if state["deletion_due"]:
                    expired += int(
                        self.service.expire_inactive(
                            workspace, state["activity_version"]
                        )["expired"]
                    )
                elif state["notice_due"]:
                    result = self.service.queue_retention_notice(
                        workspace, state["activity_version"]
                    )
                    queued += int(result["queued"])
                    self.mail.dispatch_retention(workspace, state["activity_version"])
            except ReviewError as error:
                if error.code != "workspace_unavailable":
                    raise
        return {
            "notices_queued": queued,
            "access_stopped": expired,
            "erasure_completed": False,
        }
