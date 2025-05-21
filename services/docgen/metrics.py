from prometheus_client import Counter, Histogram, Gauge, start_http_server
import os

# --- Celery Task Metrics ---
CELERY_TASKS_PROCESSED_TOTAL = Counter(
    "docgen_celery_tasks_processed_total",
    "Total number of Celery tasks processed by the docgen worker.",
    ["task_name", "status"]  # status: e.g., 'success', 'failure', 'retry', 'skipped'
)

CELERY_TASK_DURATION_SECONDS = Histogram(
    "docgen_celery_task_duration_seconds",
    "Celery task processing time in seconds for the docgen worker.",
    ["task_name"]
)

# --- PDF Generation Metrics ---
PDF_GENERATION_TOTAL = Counter(
    "docgen_pdf_generation_total",
    "Total PDF generation attempts by docgen worker.",
    ["outcome"] # e.g., 'success', 'failure_render', 'failure_write'
)

PDF_GENERATION_DURATION_SECONDS = Histogram(
    "docgen_pdf_generation_duration_seconds",
    "PDF generation time in seconds.",
    [] # No specific labels here, or add one if e.g. different templates existed
)

# --- S3 Upload Metrics ---
S3_UPLOADS_TOTAL = Counter(
    "docgen_s3_uploads_total",
    "Total S3 upload attempts for generated documents.",
    ["outcome"] # e.g., 'success', 'failure_credentials', 'failure_client_error'
)

S3_UPLOAD_DURATION_SECONDS = Histogram(
    "docgen_s3_upload_duration_seconds",
    "S3 upload time in seconds.",
    []
)

# --- General Application Metrics ---
APP_ERRORS_TOTAL = Counter(
    "docgen_app_errors_total",
    "Total number of application errors in docgen worker.",
    ["error_type", "component"] # e.g., 's3_upload', 'db_update', 'pdf_render'
)

def start_metrics_server(port: int = 8002, addr: str = '0.0.0.0'): # Different default port
    """Starts an HTTP server for Prometheus to scrape metrics."""
    metrics_port = int(os.getenv("DOCGEN_METRICS_PORT", str(port)))
    try:
        start_http_server(metrics_port, addr=addr)
        print(f"Docgen Prometheus metrics server started on port {metrics_port}")
    except OSError as e: # Python 3.3+
        print(f"Docgen Prometheus metrics server failed to start on port {metrics_port}: {e}")
        # Handle case where port might be in use if running multiple workers locally without proper port management

# Called when the Celery worker starts. 