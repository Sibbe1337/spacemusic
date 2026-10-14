import hashlib
import os
from datetime import datetime
from unittest.mock import patch
from uuid import uuid4

from services.docgen import renderer
from services.offers.models import Creator, Offer


def _offer() -> Offer:
    creator = Creator(
        id=1,
        platform_id="synthetic",
        platform_name="distributor",
        username="synthetic",
        display_name="Synthetic Seller",
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow(),
    )
    return Offer(
        id=uuid4(),
        creator_id=creator.id,
        creator=creator,
        title="Synthetic Soundscape",
        description="Test offer",
        status="OFFER_READY",
        amount_cents=120_000,
        currency_code="EUR",
        price_low_eur=100_000,
        price_median_eur=120_000,
        price_high_eur=140_000,
        valuation_confidence=0.9,
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow(),
    )


def test_render_html_uses_offer_data():
    html = renderer.render_html(_offer())

    assert "Synthetic Soundscape" in html
    assert "1200.00 EUR" in html


@patch("services.docgen.renderer.HTML")
def test_generate_pdf_from_html_is_hashable(mock_html):
    pdf_bytes = b"%PDF-1.4 synthetic"
    mock_html.return_value.write_pdf.return_value = pdf_bytes

    path, actual = renderer.generate_pdf_from_html("<h1>Test</h1>", _offer().id)

    assert actual == pdf_bytes
    assert path is not None
    assert os.path.exists(path)
    assert renderer.calculate_sha256(actual) == hashlib.sha256(pdf_bytes).hexdigest()
    os.remove(path)


@patch("services.docgen.renderer.s3_client")
def test_upload_to_s3_returns_private_presigned_url(mock_client):
    with patch("services.docgen.renderer.S3_BUCKET_NAME", "test-bucket"):
        mock_client.generate_presigned_url.return_value = "https://signed.example/receipt"
        result = renderer.upload_to_s3(b"pdf", uuid4())

    assert result == "https://signed.example/receipt"
    mock_client.put_object.assert_called_once()
    mock_client.generate_presigned_url.assert_called_once()


def test_render_termsheet_pdf_returns_none_when_renderer_unavailable():
    with patch("services.docgen.renderer.generate_pdf_from_html", return_value=(None, None)):
        result = renderer.render_termsheet_pdf(_offer())

    assert result == (None, None)
