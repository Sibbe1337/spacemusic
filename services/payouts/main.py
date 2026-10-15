from contextlib import asynccontextmanager
from typing import Tuple

from fastapi import FastAPI, Request
import structlog
from starlette.routing import Match
from starlette_prometheus import PrometheusMiddleware

from .routes import router as payout_routes_router


class SafePrometheusMiddleware(PrometheusMiddleware):
    @staticmethod
    def get_path_template(request: Request) -> Tuple[str, bool]:
        for route in request.app.routes:
            match, _ = route.matches(request.scope)
            if match == Match.FULL:
                return getattr(route, "path", request.url.path), True
        return request.url.path, False

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
app.add_middleware(SafePrometheusMiddleware)
# app.add_route("/metrics", starlette_metrics) # Middleware usually handles this

app.include_router(payout_routes_router)


@app.get("/payouts-health", tags=["health"])
async def health_check():
    # Basic health check for the API component of the service
    logger.debug("Payouts service API health check endpoint hit")
    return {"status": "ok", "service": "payouts-api"}


# To run this API (if needed independently or for testing routes):
# uvicorn services.payouts.main:app --reload --port 800X
