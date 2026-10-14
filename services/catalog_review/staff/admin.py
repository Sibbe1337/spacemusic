import secrets
from datetime import timedelta
from uuid import UUID, uuid4

from .config import GOOGLE_ISSUER, StaffError, utcnow
from .repository import audit, lock_principal, transaction


class StaffAdministration:
    """Trusted supervised control plane, NEVER expose as public/self-service APIs.

    Requires a separate administrator DSN. The runtime role cannot preapprove
    principals, create enrollment permits, change assignments or reset identities.
    References identify recorded human supervision, not an email-based identity check.
    """

    def __init__(self, admin_dsn, settings, clock=utcnow):
        settings.validate()
        self._dsn, self.settings, self.clock = admin_dsn, settings, clock

    @staticmethod
    def _reference(reference):
        if (
            not isinstance(reference, str)
            or not reference.strip()
            or len(reference) > 200
        ):
            raise StaffError("supervision_reference_required", 403)
        return reference

    def preapprove(
        self, *, issuer, subject, display_name, supervision_reference, role="reviewer"
    ):
        reference = self._reference(supervision_reference)
        if (
            issuer != GOOGLE_ISSUER
            or not isinstance(subject, str)
            or not 1 <= len(subject) <= 255
        ):
            raise StaffError("invalid_staff_principal", 403)
        if (
            not isinstance(display_name, str)
            or not 1 <= len(display_name.strip()) <= 120
        ):
            raise StaffError("named_staff_required", 403)
        if role not in ("reviewer", "operator"):
            raise StaffError("invalid_staff_role", 403)
        principal = str(uuid4())
        with transaction(self._dsn) as db:
            db.execute(
                """INSERT INTO catalog_staff.principals(principal_id,issuer,subject,display_name,role)
                VALUES(%s,%s,%s,%s,%s)""",
                (principal, issuer, subject, display_name, role),
            )
            audit(db, principal, "preapproved", self.clock(), reference)
        return principal

    def set_role(self, principal, role, *, supervision_reference):
        reference = self._reference(supervision_reference)
        if role not in ("reviewer", "operator"):
            raise StaffError("invalid_staff_role", 403)
        with transaction(self._dsn) as db:
            lock_principal(db, principal)
            db.execute(
                "UPDATE catalog_staff.principals SET role=%s,enrollment_epoch=enrollment_epoch+1 WHERE principal_id=%s",
                (role, principal),
            )
            db.execute(
                "UPDATE catalog_staff.sessions SET revoked_at=%s WHERE principal_id=%s",
                (self.clock(), principal),
            )
            audit(db, principal, "role_changed", self.clock(), reference)

    def approve_enrollment(self, principal, slot, *, supervision_reference):
        reference = self._reference(supervision_reference)
        if slot not in ("primary", "backup"):
            raise StaffError("invalid_enrollment_slot", 403)
        permit = secrets.token_urlsafe(32)
        with transaction(self._dsn) as db:
            row = lock_principal(db, principal)
            if row["state"] != "enrolling":
                raise StaffError("supervised_reset_required", 403)
            db.execute(
                """INSERT INTO catalog_staff.enrollment_permits
                (permit_digest,principal_id,enrollment_epoch,generation,slot,supervision_reference,expires_at)
                VALUES(%s,%s,%s,%s,%s,%s,%s)""",
                (
                    self.settings.digest("permit", permit),
                    principal,
                    row["enrollment_epoch"],
                    self.settings.generation,
                    slot,
                    reference,
                    self.clock() + timedelta(minutes=10),
                ),
            )
            audit(db, principal, "enrollment_approved", self.clock(), reference)
        return permit

    def _invalidate(self, db, principal, state, reference):
        lock_principal(db, principal)
        now = self.clock()
        db.execute(
            "UPDATE catalog_staff.principals SET state=%s,enrollment_epoch=enrollment_epoch+1 WHERE principal_id=%s",
            (state, principal),
        )
        db.execute(
            "UPDATE catalog_staff.sessions SET revoked_at=%s WHERE principal_id=%s",
            (now, principal),
        )
        db.execute(
            "UPDATE catalog_staff.credentials SET active=false WHERE principal_id=%s",
            (principal,),
        )
        db.execute(
            "UPDATE catalog_staff.enrollment_permits SET consumed_at=%s WHERE principal_id=%s AND consumed_at IS NULL",
            (now, principal),
        )
        db.execute(
            "UPDATE catalog_staff.assignments SET active=false WHERE principal_id=%s",
            (principal,),
        )
        audit(
            db,
            principal,
            "enrollment_reset" if state == "enrolling" else "principal_suspended",
            now,
            reference,
        )

    def suspend(self, principal, *, supervision_reference):
        with transaction(self._dsn) as db:
            self._invalidate(
                db, principal, "suspended", self._reference(supervision_reference)
            )

    def reset_enrollment(self, principal, *, supervision_reference):
        """Lost keys require supervised identity re-proof and TWO new credentials.

        No recovery code, email link, Google amr claim or remaining boolean MFA
        flag can unsuspend access. Existing assignments also need reapproval.
        """
        with transaction(self._dsn) as db:
            self._invalidate(
                db, principal, "enrolling", self._reference(supervision_reference)
            )

    def assign(self, principal, workspace, *, active, supervision_reference):
        reference = self._reference(supervision_reference)
        if type(active) is not bool:
            raise StaffError("invalid_assignment", 403)
        workspace = str(UUID(str(workspace)))
        with transaction(self._dsn) as db:
            row = lock_principal(db, principal)
            if active and row["state"] != "active":
                raise StaffError("staff_enrollment_required", 403)
            db.execute(
                """INSERT INTO catalog_staff.assignments VALUES(%s,%s,%s)
                ON CONFLICT(principal_id,workspace_id) DO UPDATE SET active=EXCLUDED.active""",
                (principal, workspace, active),
            )
            audit(db, principal, "assignment_changed", self.clock(), reference)
