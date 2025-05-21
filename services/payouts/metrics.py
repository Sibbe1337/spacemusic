from prometheus_client import Counter, Histogram, Gauge, start_http_server
import os

# --- HTTP Metrics (for Payouts API component) ---
HTTP_REQUESTS_TOTAL = Counter(
    "payouts_api_http_requests_total",
    "Total HTTP requests to Payouts API.",
    ["method", "path", "status_code"]
)

HTTP_REQUEST_LATENCY_SECONDS = Histogram(
    "payouts_api_http_request_latency_seconds",
    "HTTP request latency for Payouts API.",
    ["method", "path"]
)

# --- Celery Task Metrics (for Payouts Worker component) ---
CELERY_TASKS_PROCESSED_TOTAL = Counter(
    "payouts_celery_tasks_processed_total",
    "Total Celery tasks processed by Payouts worker.",
    ["task_name", "status"]
)

CELERY_TASK_DURATION_SECONDS = Histogram(
    "payouts_celery_task_duration_seconds",
    "Celery task duration for Payouts worker.",
    ["task_name"]
)

# --- Payment Provider Metrics ---
STRIPE_PAYOUTS_TOTAL = Counter(
    "payouts_stripe_payouts_total",
    "Total Stripe payout attempts.",
    ["outcome"] # e.g., success, api_error, card_error, config_error
)

STRIPE_API_LATENCY_SECONDS = Histogram(
    "payouts_stripe_api_latency_seconds",
    "Stripe API call latency.",
    ["api_call"] # e.g., "transfer_create"
)

WISE_TRANSFERS_TOTAL = Counter(
    "payouts_wise_transfers_total",
    "Total Wise transfer attempts.",
    ["outcome"]
)

# Gauge for Stripe success rate (can be calculated in Grafana or here)
# For direct Prometheus gauge, it would be more complex, often done with recording rules.
# Simpler to count success/failure and calculate rate in Grafana.
STRIPE_CIRCUIT_BREAKER_STATE = Gauge(
    "payouts_stripe_circuit_breaker_state",
    "State of the Stripe circuit breaker (0=closed, 1=open, 0.5=half-open).",
    []
)

# --- Ledger Metrics ---
LEDGER_ENTRIES_CREATED_TOTAL = Counter(
    "payouts_ledger_entries_created_total",
    "Total ledger entries created.",
    ["transaction_type", "payout_method"]
)

# --- General Application Metrics ---
APP_ERRORS_TOTAL = Counter(
    "payouts_app_errors_total",
    "Total application errors in Payouts service (API or worker).",
    ["component", "error_type"] # component: 'api', 'worker', 'stripe_call', 'wise_call'
)

def start_worker_metrics_server(port: int = 8003, addr: str = '0.0.0.0'): # Different default port for worker
    metrics_port = int(os.getenv("PAYOUTS_WORKER_METRICS_PORT", str(port)))
    try:
        start_http_server(metrics_port, addr=addr)
        print(f"Payouts Worker Prometheus metrics server started on port {metrics_port}")
    except OSError as e:
        print(f"Payouts Worker Prometheus metrics server failed to start on port {metrics_port}: {e}")

# Note: The Payouts API (FastAPI part) will use starlette-prometheus middleware to expose its HTTP metrics on /metrics.
# The Payouts Worker (Celery part) needs to call start_worker_metrics_server(). 