from unittest.mock import MagicMock, patch
from uuid import uuid4

from services.docgen import tasks


def test_document_tasks_are_registered():
    assert "services.docgen.tasks.generate_termsheet" in tasks.celery_app.tasks
    assert "services.docgen.tasks.generate_receipt_pdf" in tasks.celery_app.tasks


def test_receipt_task_publishes_only_after_success():
    offer_id = str(uuid4())
    event_data = {
        "status": "SUCCESS",
        "offer_id": offer_id,
        "completed_at_micros": 1_700_000_000_000_000,
    }
    producer = MagicMock()

    with patch.object(tasks, "render_receipt_pdf_and_upload", return_value=("https://signed.example/receipt", "abc123")),          patch.object(tasks, "get_offer_receipt_generated_producer", return_value=producer),          patch.object(tasks, "_offer_receipt_generated_schema_str", "schema"):
        result = tasks.generate_receipt_pdf(offer_id=offer_id, event_data=event_data)

    assert result["status"] == "success"
    payload = producer.produce.call_args.kwargs["value"]
    assert payload["offer_id"] == offer_id
    assert payload["receipt_hash_sha256"] == "abc123"
