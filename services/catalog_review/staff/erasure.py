"""Privileged case erasure participant; never called by the staff HTTP role."""

from uuid import UUID


class StaffErasureParticipant:
    def erase_in_transaction(self, db, workspace):
        """Use the erasure worker's existing transaction after journal fencing.

        Removes only this case's assignment footprint, not global principals,
        enrolled keys or identity audit. No connection, commit or nested txn.
        """
        workspace = str(UUID(str(workspace)))
        db.execute(
            "DELETE FROM catalog_staff.assignments WHERE workspace_id=%s",
            (workspace,),
        )
