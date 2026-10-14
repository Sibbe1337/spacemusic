"""Bounded workers with injected transports. No vendor network client exists."""

import hashlib
import hmac

from .security import ReviewError


def deliver_invitation(service, workspace, transport):
    if service.settings.mode != "test":
        raise ReviewError("durable_mail_dispatcher_required", 503)
    job = service.claim_invitation(workspace)
    if job is None:
        return "no_job"
    try:
        reference = transport.send(
            recipient=job["recipient"],
            url=job["url"],
            idempotency_key=job["idempotency_key"],
        )
    except Exception:
        service.finish_invitation(job, accepted=False)
        return "retry_scheduled"
    service.finish_invitation(job, accepted=True, provider_reference=reference)
    return "accepted"  # Never claim inbox delivery from an API acceptance.


def scan_document(service, workspace, document, blobs, scanner, parser=None):
    if parser is None and service.settings.mode != "test":
        raise ReviewError("isolated_parser_required", 503)
    job = service.claim_scan(workspace, document)
    if job is None:
        return "no_job"
    content = blobs.get(job["object_key"])
    checksum = hashlib.sha256(content).hexdigest()
    if len(content) != job["size_bytes"] or not hmac.compare_digest(
        checksum, job["sha256"]
    ):
        service.complete_scan(job, clean=False, scanned_sha256=job["sha256"])
        return "rejected"
    # An unavailable scanner leaves a leased quarantine job for bounded retry,
    # never an accepted document. Production implementation must enforce parser
    # resource budgets and private malware scanning before returning True.
    if parser is not None:
        from .document_validation import validate_document

        verdict = validate_document(
            content=content,
            filename=job["filename"],
            expected_sha256=checksum,
            expected_size=job["size_bytes"],
            scanner=scanner,
            parser=parser,
        )
    else:
        verdict = scanner.inspect(content=content, filename=job["filename"])
    if verdict not in (True, False) or not isinstance(verdict, bool):
        raise ReviewError("scanner_unavailable", 503)
    service.complete_scan(job, clean=verdict, scanned_sha256=checksum)
    return "accepted_for_review" if verdict else "rejected"
