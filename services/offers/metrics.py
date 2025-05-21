from prometheus_client import Counter, Histogram, Gauge

# --- HTTP Metrics (for FastAPI) ---
HTTP_REQUESTS_TOTAL = Counter(
    "http_requests_total",
    "Total number of HTTP requests made.",
    ["method", "path", "status_code"]
)

HTTP_REQUEST_LATENCY_SECONDS = Histogram(
    "http_request_latency_seconds",
    "HTTP request latency in seconds.",
    ["method", "path"]
)

HTTP_REQUEST_ERRORS_TOTAL = Counter(
    "http_request_errors_total",
    "Total number of HTTP request errors.",
    ["method", "path", "error_type"]
)

# --- General Application Metrics (can be used by workers or API) ---
APP_ERRORS_TOTAL = Counter(
    "app_errors_total",
    "Total number of application errors.",
    ["service_name", "error_type", "component"]
)

# If this service had Celery tasks, you would add Celery metrics here too.
# Example (though offers service doesn't have tasks defined yet):
# CELERY_TASKS_TOTAL = Counter(
#     "celery_tasks_total",
#     "Total number of Celery tasks processed.",
#     ["task_name", "status"] # status could be success, failure, retry
# )

# CELERY_TASK_DURATION_SECONDS = Histogram(
#     "celery_task_duration_seconds",
#     "Celery task processing time in seconds.",
#     ["task_name"]
# )

# Example Gauge (not directly applicable to offers service without more context)
# ACTIVE_USERS_GAUGE = Gauge(
#     "active_users",
#     "Number of active users.",
#     ["service_name"]
# )

# You can add more specific metrics relevant to the offers service, e.g.:
OFFERS_CREATED_TOTAL = Counter(
    "offers_created_total",
    "Total number of offers created.",
    ["platform_name"] # Example label
)

OFFER_STATUS_UPDATES_TOTAL = Counter(
    "offer_status_updates_total",
    "Total number of offer status updates.",
    ["old_status", "new_status"]
)

# Note: For starlette-prometheus, many HTTP metrics are auto-instrumented.
# These custom HTTP_ metrics can be used if you need more specific labeling or control,
# or if you are instrumenting parts not covered by the middleware.
# starlette-prometheus typically exposes /metrics endpoint automatically. 