from fastapi import FastAPI
import structlog

# Prometheus metrics for FastAPI app
from starlette_prometheus import PrometheusMiddleware, metrics as starlette_metrics
# from .metrics import HTTP_REQUESTS_TOTAL, HTTP_REQUEST_LATENCY_SECONDS # Custom HTTP metrics if needed beyond starlette-prometheus

from .routes import router as payout_routes_router
# from .worker import celery_app # If you wanted to inspect tasks, etc.

logger = structlog.get_logger(__name__)

app = FastAPI(
    title="Payouts Service API", # Clarified title
    description="Manages payout operations and provides internal endpoints.",
    version="0.1.0"
)

# Add Prometheus middleware to expose /metrics endpoint for FastAPI app
app.add_middleware(PrometheusMiddleware, app_name="payouts-api") # Added app_name for metric labels
# app.add_route("/metrics", starlette_metrics) # Middleware usually handles this

@app.on_event("startup")
async def on_startup():
    logger.info("payouts_service_api_startup", service="payouts-api", event="service_starting")
    # Perform any async setup needed for the API part of the service here
    # e.g., if there was an async DB connection specifically for the API
    logger.info("payouts_service_api_startup_complete", service="payouts-api", event="service_started")

app.include_router(payout_routes_router)

@app.get("/payouts-health", tags=["health"])
async def health_check():
    # Basic health check for the API component of the service
    logger.debug("Payouts service API health check endpoint hit")
    return {"status": "ok", "service": "payouts-api"}

# To run this API (if needed independently or for testing routes):
# uvicorn services.payouts.main:app --reload --port 800X 