from contextlib import asynccontextmanager

from fastapi import FastAPI
import structlog

# Prometheus metrics for FastAPI app
from starlette_prometheus import PrometheusMiddleware
# from .metrics import HTTP_REQUESTS_TOTAL, HTTP_REQUEST_LATENCY_SECONDS # Custom HTTP metrics if needed beyond starlette-prometheus

from .routes import router as payout_routes_router
# from .worker import celery_app # If you wanted to inspect tasks, etc.

logger = structlog.get_logger(__name__)


@asynccontextmanager
async def lifespan(_: FastAPI):
    logger.info(
        "payouts_service_api_startup", service="payouts-api", event="service_started"
    )
    yield


app = FastAPI(
    title="Payouts Service API",  # Clarified title
    description="Manages payout operations and provides internal endpoints.",
    version="0.1.0",
    lifespan=lifespan,
)

# Add Prometheus middleware to expose /metrics endpoint for FastAPI app
app.add_middleware(PrometheusMiddleware)
# app.add_route("/metrics", starlette_metrics) # Middleware usually handles this

app.include_router(payout_routes_router)


@app.get("/payouts-health", tags=["health"])
async def health_check():
    # Basic health check for the API component of the service
    logger.debug("Payouts service API health check endpoint hit")
    return {"status": "ok", "service": "payouts-api"}


# To run this API (if needed independently or for testing routes):
# uvicorn services.payouts.main:app --reload --port 800X
