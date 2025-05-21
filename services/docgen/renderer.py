import os
import uuid
from datetime import datetime
import hashlib
from pathlib import Path
import time # For duration measurement

from jinja2 import Environment, FileSystemLoader
from weasyprint import HTML
import boto3
from botocore.exceptions import NoCredentialsError, PartialCredentialsError, ClientError
import structlog

# Assuming services/offers/models.py contains the Offer model definition
# This creates a dependency. Adjust path if your structure is different or models are in libs.
import sys
PROJECT_ROOT_DOCGEN = Path(__file__).resolve().parent.parent.parent
sys.path.append(str(PROJECT_ROOT_DOCGEN))
from services.offers.models import Offer # This import style relies on PYTHONPATH setup

# Import metrics
from .metrics import (
    PDF_GENERATION_TOTAL,
    PDF_GENERATION_DURATION_SECONDS,
    S3_UPLOADS_TOTAL,
    S3_UPLOAD_DURATION_SECONDS,
    APP_ERRORS_TOTAL
)

logger = structlog.get_logger(__name__)

# Initialize Jinja2 environment
TEMPLATE_DIR = Path(__file__).parent / "templates"
jinja_env = Environment(loader=FileSystemLoader(TEMPLATE_DIR), autoescape=True)

# S3 Configuration
S3_BUCKET_NAME = os.getenv("TERM_SHEETS_S3_BUCKET")
S3_REGION = os.getenv("AWS_REGION", "eu-north-1") # Ensure your worker env has AWS_REGION
s3_client = boto3.client("s3", region_name=S3_REGION) if S3_BUCKET_NAME else None
if not S3_BUCKET_NAME:
    logger.warning("TERM_SHEETS_S3_BUCKET environment variable not set. S3 upload will be disabled.")

def render_html(offer: Offer) -> str:
    """Renders the termsheet HTML using Jinja2."""
    template = jinja_env.get_template("termsheet.html")
    generation_date_str = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S UTC")
    # Ensure offer.creator is loaded if it's a lazy-loaded relationship
    # This might require fetching it explicitly before calling render_html
    # if the Offer object comes from a session that might be closed.
    # For now, assume offer.creator is accessible.
    html_content = template.render(offer=offer, generation_date=generation_date_str)
    return html_content

def generate_pdf_from_html(html_content: str, offer_id: uuid.UUID) -> tuple[str | None, bytes | None]:
    """Generates a PDF from HTML content and returns its path and content."""
    # Using /tmp for PDF generation, ensure worker has write access
    # Filename could be more robust, e.g., include a timestamp or unique ID portion
    pdf_filename = f"termsheet_offer_{str(offer_id)}.pdf"
    # In a containerized environment, /tmp is usually fine.
    # For serverless/lambda, ensure /tmp is writable and has enough space.
    local_pdf_path = f"/tmp/{pdf_filename}"
    
    logger.info("Generating PDF", offer_id=str(offer_id), path=local_pdf_path)
    
    start_time = time.monotonic()
    outcome = "failure_render"
    pdf_bytes = None
    try:
        pdf_bytes = HTML(string=html_content).write_pdf()
        with open(local_pdf_path, "wb") as f:
            f.write(pdf_bytes)
        logger.info("PDF generated successfully", local_path=local_pdf_path)
        outcome = "success"
        return local_pdf_path, pdf_bytes
    except Exception as e:
        logger.error("Failed to generate or write PDF", error=str(e), offer_id=str(offer_id), exc_info=True)
        APP_ERRORS_TOTAL.labels(error_type="pdf_generation", component="generate_pdf_from_html").inc()
        outcome = "failure_write" # More specific error if possible
        return None, None
    finally:
        PDF_GENERATION_DURATION_SECONDS.observe(time.monotonic() - start_time)
        PDF_GENERATION_TOTAL.labels(outcome=outcome).inc()

def upload_to_s3(pdf_bytes: bytes, offer_id: uuid.UUID) -> str | None:
    """Uploads the PDF to S3 and returns a presigned URL."""
    if not s3_client or not S3_BUCKET_NAME:
        logger.error("S3 client or bucket name not configured. Cannot upload.")
        S3_UPLOADS_TOTAL.labels(outcome="failure_config").inc()
        return None

    s3_key = f"termsheets/{str(offer_id)}/termsheet_{datetime.utcnow().strftime("%Y%m%d%H%M%S")}.pdf"
    logger.info("Uploading PDF to S3", bucket=S3_BUCKET_NAME, key=s3_key, offer_id=str(offer_id))
    
    start_time = time.monotonic()
    outcome = "failure_unknown"
    try:
        s3_client.put_object(Bucket=S3_BUCKET_NAME, Key=s3_key, Body=pdf_bytes, ContentType='application/pdf')
        
        # Generate a presigned URL (valid for 24 hours)
        presigned_url = s3_client.generate_presigned_url(
            'get_object',
            Params={'Bucket': S3_BUCKET_NAME, 'Key': s3_key},
            ExpiresIn=24 * 3600  # 24 hours
        )
        logger.info("PDF uploaded to S3 successfully", s3_key=s3_key)
        outcome = "success"
        return presigned_url
    except (NoCredentialsError, PartialCredentialsError) as e:
        logger.error("S3 credentials not found or incomplete.", error=str(e), offer_id=str(offer_id))
        APP_ERRORS_TOTAL.labels(error_type="s3_credentials", component="upload_to_s3").inc()
        outcome = "failure_credentials"
    except ClientError as e:
        logger.error("S3 ClientError during upload.", error=str(e.response.get('Error',{}).get('Code')), offer_id=str(offer_id))
        APP_ERRORS_TOTAL.labels(error_type="s3_client_error", component="upload_to_s3").inc()
        outcome = "failure_client_error"
    except Exception as e:
        logger.error("Unexpected error during S3 upload.", error=str(e), offer_id=str(offer_id), exc_info=True)
        APP_ERRORS_TOTAL.labels(error_type="s3_unknown_error", component="upload_to_s3").inc()
    finally:
        S3_UPLOAD_DURATION_SECONDS.observe(time.monotonic() - start_time)
        S3_UPLOADS_TOTAL.labels(outcome=outcome).inc()
    return None

def calculate_sha256(pdf_bytes: bytes) -> str:
    """Calculates the SHA256 hash of the PDF content."""
    sha256_hash = hashlib.sha256(pdf_bytes).hexdigest()
    logger.info("SHA256 hash calculated", hash_value=sha256_hash)
    return sha256_hash

# Main function to be called by the Celery task
def render_termsheet_pdf(offer: Offer) -> tuple[str | None, str | None]:
    """
    Renders a term sheet PDF for the given offer, uploads to S3,
    and returns the S3 presigned URL and SHA256 hash.
    Returns (None, None) if any step fails critically.
    """
    logger.info("Starting termsheet generation process for offer", offer_id=str(offer.id))
    try:
        # 1. Render HTML from Jinja2 template
        html_content = render_html(offer)
        
        # 2. Generate PDF from HTML
        # generate_pdf_from_html now returns (local_path, pdf_bytes)
        _local_pdf_path, pdf_bytes = generate_pdf_from_html(html_content, offer.id)
        if not pdf_bytes:
            logger.error("PDF generation failed, no bytes produced.", offer_id=str(offer.id))
            # Metric for this case already handled in generate_pdf_from_html
            return None, None

        # 3. Calculate SHA256 hash of the PDF content
        pdf_hash = calculate_sha256(pdf_bytes)

        # 4. Upload PDF to S3 and get presigned URL
        s3_presigned_url = upload_to_s3(pdf_bytes, offer.id)
        # If upload fails, we might still want to return the hash, or handle differently
        if not s3_presigned_url:
            logger.warning("S3 upload failed, PDF not stored in S3 but hash calculated.", offer_id=str(offer.id))
            # Still return hash, but no URL. Task might decide how to handle this.

        logger.info("Termsheet PDF processed", offer_id=str(offer.id), s3_url=s3_presigned_url, pdf_hash=pdf_hash)
        return s3_presigned_url, pdf_hash

    except Exception as e:
        logger.error("Error in render_termsheet_pdf process", error=str(e), offer_id=str(offer.id), exc_info=True)
        APP_ERRORS_TOTAL.labels(error_type="orchestration_error", component="render_termsheet_pdf").inc()
        return None, None

# Example usage (for local testing, not part of Celery task directly):
# if __name__ == '__main__':
#     # This requires a mock Offer object or connection to a DB to fetch one.
#     class MockCreator:
#         def __init__(self, id, platform_id, platform_name, username, display_name):
#             self.id = id
#             self.platform_id = platform_id
#             self.platform_name = platform_name
#             self.username = username
#             self.display_name = display_name

#     class MockOffer(Offer):
#         # You might need to mock the relationship to prevent DB calls if not using a real session
#         # For full model, it might be easier to fetch from DB.
#         # This is a simplified mock.
        
#         # Override creator to be a simple object for template rendering
#         # This is a hack for local testing without a DB.
#         # In real use, offer.creator will be a SQLModel object.

#         @property # Mocking the relationship property
#         def creator(self):
#             return MockCreator(id=self.creator_id, platform_id="spotify123", platform_name="Spotify", username="testuser", display_name="Test User Display")

#     mock_offer_data = {
#         "id": uuid.uuid4(),
#         "title": "Test Offer Title",
#         "description": "This is a detailed description of the test offer.",
#         "status": "OFFER_READY",
#         "creator_id": 1, # Assuming int for now
#         "amount_cents": 500000, # 5000 EUR
#         "currency_code": "EUR",
#         "price_low_eur": 450000,
#         "price_median_eur": 500000,
#         "price_high_eur": 550000,
#         "valuation_confidence": 0.88,
#         "created_at": datetime.utcnow(),
#         "updated_at": datetime.utcnow()
#     }
#     # This direct instantiation is tricky due to SQLModel's table=True metaclass.
#     # test_offer = MockOffer(**mock_offer_data) 
#     # For local testing, it's better to create a dummy DB and fetch.

#     # For simplicity in this example, let's assume render_termsheet_pdf can be called with a dict-like object
#     # if the template is simple enough or the Offer model allows easy dict conversion.
#     # However, the function expects an Offer instance.
    
#     # To test properly, you would need to set up a test DB, create an Offer, and pass it.
#     # print("Local test run would require a proper Offer object.")
#     pass 