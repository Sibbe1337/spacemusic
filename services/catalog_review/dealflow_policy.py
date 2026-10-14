"""Explainable preparation checks, not valuation or investment advice."""

from decimal import Decimal

POLICY_VERSION = "2026-09-25-v1"
QUESTIONS = {
    "scope": (
        "Define the transaction",
        "Please confirm the rights, share, term and existing releases you want considered. Future music remains excluded.",
    ),
    "authority": (
        "Confirm who can instruct SPACE",
        "Please provide the owner's instruction or your authority to act for the owner. An inquiry alone is not a mandate to circulate a catalog.",
    ),
    "ownership": (
        "Review the rights chain",
        "Please provide ownership and split agreements for the rights offered, including any unresolved claims.",
    ),
    "income": (
        "Reconcile the royalty history",
        "Please provide a complete twelve-month royalty history, its currency, reporting dates and the basis of net receipts. Do not combine overlapping exports.",
    ),
    "agreements": (
        "Review existing restrictions",
        "Please provide relevant distribution, administration and financing agreements, including restrictions, recoupment and third-party approvals.",
    ),
    "catalog": (
        "Identify the included recordings or works",
        "Please provide a release or works list with identifiers, rightsholders and the items excluded from the proposed transaction.",
    ),
}


def assess(record, *, stale, today):
    checks = {item["key"]: item for item in record["checks"]} if record else {}
    actions = []
    if stale:
        actions.append(
            {
                "key": "refresh",
                "title": "Re-review the changed evidence",
                "question": "New material has arrived since this review. Reconcile the original and new evidence before preparing an introduction.",
            }
        )
    for key, (title, question) in QUESTIONS.items():
        check = checks.get(key, {"status": "missing"})
        if check["status"] != "reviewed":
            actions.append(
                {
                    "key": key,
                    "title": title,
                    "question": question,
                    "status": check["status"],
                }
            )
    conflicts = [key for key, item in checks.items() if item["status"] == "conflicting"]
    matches = []
    for buyer in record["buyers"] if record else []:
        reasons, missing = [], []
        if (
            buyer["checked_on"] > today.isoformat()
            or buyer["expires_on"] < today.isoformat()
        ):
            missing.append("Buyer criteria need reconfirmation.")
        if record["rights"] == "unknown":
            missing.append("Rights offered are unknown.")
        elif record["rights"] not in buyer["rights"]:
            reasons.append("Offered rights do not match the recorded mandate.")
        if record["structure"] == "unknown":
            missing.append("Transaction structure is unknown.")
        elif record["structure"] not in buyer["structures"]:
            reasons.append("The proposed structure is outside the recorded mandate.")
        if buyer["minimum_annual_net"] is not None:
            if checks["income"]["status"] != "reviewed" or record["annual_net"] is None:
                missing.append("The required net revenue has not been reviewed.")
            elif buyer["currency"] != record["currency"]:
                missing.append(
                    "Currencies differ; no automatic conversion is permitted."
                )
            elif Decimal(record["annual_net"]) < Decimal(buyer["minimum_annual_net"]):
                reasons.append(
                    "Documented net revenue is below this mandate's minimum."
                )
        if actions:
            missing.append("Complete the evidence checklist before an introduction.")
        matches.append(
            {
                "buyer_id": buyer["buyer_id"],
                "name": buyer["name"],
                "status": "outside_mandate"
                if reasons
                else "needs_review"
                if missing
                else "candidate_for_introduction",
                "reasons": reasons + missing
                or [
                    "Matches the limited criteria recorded here. Buyer interest and transaction terms are not confirmed."
                ],
            }
        )
    return {
        "policy_version": POLICY_VERSION,
        "stage": "re_review_required"
        if stale
        else "conflicting_evidence"
        if conflicts
        else "needs_information"
        if actions
        else "ready_for_manual_matching",
        "reviewed_checks": sum(c["status"] == "reviewed" for c in checks.values()),
        "total_checks": len(QUESTIONS),
        "actions": actions,
        "conflicts": conflicts,
        "matches": matches,
        "limitations": "Human checklist, not verified ownership, a valuation, a buyer commitment or permission to share. No automated outreach.",
    }
