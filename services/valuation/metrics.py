from prometheus_client import Counter, Histogram, Gauge, start_http_server
import os

# --- Celery Task Metrics ---
CELERY_TASKS_PROCESSED_TOTAL = Counter(
    "valuation_celery_tasks_processed_total",
    "Total number of Celery tasks processed by the valuation worker.",
    ["task_name", "status"]  # status: e.g., 'success', 'failure', 'retry'
)

CELERY_TASK_DURATION_SECONDS = Histogram(
    "valuation_celery_task_duration_seconds",
    "Celery task processing time in seconds for the valuation worker.",
    ["task_name"]
)

# --- External API Call Metrics (e.g., Spotify) ---
SPOTIFY_API_CALLS_TOTAL = Counter(
    "valuation_spotify_api_calls_total",
    "Total Spotify API calls made by valuation worker.",
    ["endpoint", "status_code"]
)

SPOTIFY_API_LATENCY_SECONDS = Histogram(
    "valuation_spotify_api_latency_seconds",
    "Spotify API call latency from valuation worker.",
    ["endpoint"]
)

# --- Cache Metrics ---
CACHE_HITS_TOTAL = Counter(
    "valuation_cache_hits_total",
    "Total cache hits for valuation worker.",
    ["cache_name"] # e.g., 'spotify_artist_data'
)

CACHE_MISSES_TOTAL = Counter(
    "valuation_cache_misses_total",
    "Total cache misses for valuation worker.",
    ["cache_name"]
)

# --- Model Prediction Metrics ---
MODEL_PREDICTIONS_TOTAL = Counter(
    "valuation_model_predictions_total",
    "Total model predictions made by valuation worker.",
    ["outcome"] # e.g., 'success', 'error'
)

# --- General Application Metrics ---
APP_ERRORS_TOTAL = Counter(
    "valuation_app_errors_total",
    "Total number of application errors in valuation worker.",
    ["error_type", "component"] # component e.g., 'spotify_fetch', 'db_update', 'model_predict'
)

def start_metrics_server(port: int = 8001, addr: str = '0.0.0.0'):
    """Starts an HTTP server for Prometheus to scrape metrics."""
    # Ensure port is not conflicting with other services if run locally on same host
    # In K8s, each pod gets its own IP, so port conflicts are less of an issue for fixed ports.
    # Port can be configured via environment variable.
    metrics_port = int(os.getenv("VALUATION_METRICS_PORT", str(port)))
    start_http_server(metrics_port, addr=addr)
    print(f"Prometheus metrics server started on port {metrics_port}")

# Note: This worker is Celery-based. For Prometheus to scrape it,
# the start_metrics_server() needs to be called when the worker starts.
# This can be done in the worker startup logic (e.g., in worker.py or a celeryconfig.py signal).
# Alternatively, if using a multi-process Celery worker, each process might need its own server
# or use a method suitable for multi-process applications (e.g., prometheus_client.exposition.MultiprocDirectory).
# For simplicity, this example assumes start_metrics_server is called once by the main worker process
# or you are running with a single worker process for scraping, or using a Celery Prometheus exporter. 