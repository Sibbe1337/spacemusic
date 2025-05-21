import pytest
import os
import uuid
from unittest.mock import patch, MagicMock
from pathlib import Path
import hashlib
from datetime import datetime

# Adjust these imports based on your actual project structure
# This assumes services.docgen.renderer and services.offers.models are discoverable
from services.docgen.renderer import render_termsheet_pdf, render_html, generate_pdf_from_html, calculate_sha256, upload_to_s3
from services.offers.models import Offer, Creator # As used in the template and renderer

@pytest.fixture
def mock_offer_fixture():
    """Provides a mock Offer object for testing."""
    # Create a mock Creator object first if Offer.creator is accessed directly
    mock_creator = Creator(
        id=1, # Assuming int PK for Creator for now
        platform_id="test_platform_123",
        platform_name="TestPlatform",
        username="testuser",
        display_name="Test User Display Name",
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow()
        # Add other fields if Creator model has them and they are accessed
    )
    
    offer_id = uuid.uuid4()
    mock_offer = Offer(
        id=offer_id,
        creator_id=mock_creator.id, # Link to mock_creator
        creator=mock_creator, # Direct assignment for template access
        title="Super Duper Test Offer",
        description="A fantastic offer for testing PDF generation.",
        status="OFFER_READY",
        amount_cents=1234500, # 12345.00
        currency_code="USD",
        price_low_eur=1000000,
        price_median_eur=1200000,
        price_high_eur=1400000,
        valuation_confidence=0.92,
        pdf_url=None, # Initially None
        pdf_hash=None, # Initially None
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow()
    )
    return mock_offer

def test_render_html(mock_offer_fixture):
    """Test HTML rendering from Jinja2 template."""
    html_content = render_html(mock_offer_fixture)
    assert "<title>Term Sheet - Super Duper Test Offer</title>" in html_content
    assert "Offer ID:</span> " + str(mock_offer_fixture.id) in html_content
    assert "Creator Name:</span> Test User Display Name" in html_content
    assert "12000.00 EUR" in html_content # Median price example
    assert "12345.00 USD" in html_content # Offer amount

@patch("services.docgen.renderer.HTML") # Patch WeasyPrint's HTML class
def test_generate_pdf_from_html(mock_weasyprint_html, mock_offer_fixture):
    """Test PDF generation (mocking WeasyPrint actual PDF writing)."""
    mock_pdf_content_bytes = b"%PDF-1.4 mock_pdf_content"
    mock_html_instance = MagicMock()
    mock_html_instance.write_pdf.return_value = mock_pdf_content_bytes
    mock_weasyprint_html.return_value = mock_html_instance

    test_html = "<h1>Test PDF</h1>"
    offer_id_for_pdf = mock_offer_fixture.id
    
    # Ensure /tmp directory exists or use a temporary directory fixture from pytest for robustness
    # For this test, assume /tmp is writable.
    if not os.path.exists("/tmp"):
        os.makedirs("/tmp") # Should ideally be handled by test environment setup

    local_path, pdf_bytes = generate_pdf_from_html(test_html, offer_id_for_pdf)

    mock_weasyprint_html.assert_called_once_with(string=test_html)
    mock_html_instance.write_pdf.assert_called_once()
    assert local_path == f"/tmp/termsheet_offer_{str(offer_id_for_pdf)}.pdf"
    assert pdf_bytes == mock_pdf_content_bytes
    assert os.path.exists(local_path) # Check if file was actually written by the mock setup
    os.remove(local_path) # Clean up

def test_calculate_sha256():
    """Test SHA256 hash calculation."""
    pdf_bytes = b"some pdf content"
    expected_hash = hashlib.sha256(pdf_bytes).hexdigest()
    actual_hash = calculate_sha256(pdf_bytes)
    assert actual_hash == expected_hash
    assert len(actual_hash) == 64

@patch("services.docgen.renderer.s3_client")
def test_upload_to_s3_success(mock_boto_s3_client, mock_offer_fixture):
    """Test S3 upload success case."""
    # Ensure the global s3_client in renderer module is the mocked one
    # Also, ensure S3_BUCKET_NAME is set for the test context
    with patch.dict(os.environ, {"TERM_SHEETS_S3_BUCKET": "test-bucket"}):
        # Re-patch the s3_client inside renderer if it's module-level and already initialized
        # or ensure the fixture correctly patches the one used by the function.
        # The global patch on renderer.s3_client should suffice if it's module level.
        # If renderer.s3_client is None due to env var not set at import, this test needs adjustment.
        # For this test, let's assume S3_BUCKET_NAME will be picked up by the patched s3_client context.
        
        # We need to ensure that the `s3_client` within `upload_to_s3` is our mock.
        # If `services.docgen.renderer.s3_client` was initialized to None because
        # `S3_BUCKET_NAME` was not set when the module was imported, the patch might not work as expected.
        # A safer way is to also patch `boto3.client` call if `s3_client` is initialized dynamically, 
        # or ensure the module level `s3_client` is our mock.
        
        # For this test, we assume the @patch("services.docgen.renderer.s3_client") works directly.
        # If S3_BUCKET_NAME was initially None, the s3_client in renderer might be None.
        # Let's mock the S3_BUCKET_NAME as well for the scope of this test.
        with patch('services.docgen.renderer.S3_BUCKET_NAME', "test-bucket"):
            # Ensure the s3_client in the renderer module is our mock for this test execution context
            # This is a bit tricky due to module-level global `s3_client`
            # The `patch` decorator should handle replacing `services.docgen.renderer.s3_client`
            # If it was `None`, the function would return early. We test the upload path here.
            services.docgen.renderer.s3_client = mock_boto_s3_client # Ensure it is our mock

            mock_boto_s3_client.put_object.return_value = {}
            expected_presigned_url = "https://test-bucket.s3.eu-north-1.amazonaws.com/some_key?AWSAccessKeyId=..."
            mock_boto_s3_client.generate_presigned_url.return_value = expected_presigned_url

            pdf_bytes = b"dummy pdf data for s3"
            offer_id_for_s3 = mock_offer_fixture.id
            
            presigned_url = upload_to_s3(pdf_bytes, offer_id_for_s3)

            mock_boto_s3_client.put_object.assert_called_once()
            # We can add more specific assertions on put_object args (Bucket, Key, Body, ContentType)
            mock_boto_s3_client.generate_presigned_url.assert_called_once_with(
                'get_object',
                Params=MatchDictContains({'Bucket': "test-bucket"}), # Helper for partial dict match
                ExpiresIn=24 * 3600
            )
            assert presigned_url == expected_presigned_url

# Helper for partial dictionary matching in mock calls
class MatchDictContains:
    def __init__(self, subset):
        self.subset = subset
    def __eq__(self, other):
        return self.subset.items() <= other.items()
    def __repr__(self):
        return f"MatchDictContains({self.subset})"


@patch("services.docgen.renderer.upload_to_s3")
@patch("services.docgen.renderer.calculate_sha256")
@patch("services.docgen.renderer.generate_pdf_from_html")
@patch("services.docgen.renderer.render_html")
def test_render_termsheet_pdf_success(
    mock_render_html,
    mock_generate_pdf,
    mock_calculate_sha,
    mock_upload_s3,
    mock_offer_fixture
):
    """Test the main orchestrator function render_termsheet_pdf for success."""
    mock_render_html.return_value = "<html>mock html</html>"
    mock_generate_pdf.return_value = (" /tmp/mock.pdf", b"mock pdf bytes")
    mock_calculate_sha.return_value = "mocksha256hash"
    mock_upload_s3.return_value = "https://mock_s3_url.com/mock.pdf"

    s3_url, pdf_hash = render_termsheet_pdf(mock_offer_fixture)

    mock_render_html.assert_called_once_with(mock_offer_fixture)
    mock_generate_pdf.assert_called_once_with("<html>mock html</html>", mock_offer_fixture.id)
    mock_calculate_sha.assert_called_once_with(b"mock pdf bytes")
    mock_upload_s3.assert_called_once_with(b"mock pdf bytes", mock_offer_fixture.id)

    assert s3_url == "https://mock_s3_url.com/mock.pdf"
    assert pdf_hash == "mocksha256hash"

@patch("services.docgen.renderer.render_html", side_effect=Exception("HTML Render Fail"))
def test_render_termsheet_pdf_html_failure(mock_render_html_fail, mock_offer_fixture):
    s3_url, pdf_hash = render_termsheet_pdf(mock_offer_fixture)
    assert s3_url is None
    assert pdf_hash is None
    mock_render_html_fail.assert_called_once()

# Add more tests for S3 upload failure, PDF generation failure, etc.
# Test the Celery task in tasks.py separately, mocking render_termsheet_pdf function. 