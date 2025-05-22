from fastapi import FastAPI, Depends
import structlog # Assuming structlog is in requirements.txt
from sqlmodel import SQLModel # For potential route response models
from typing import List # For list responses
from libs.py_common.flags import LaunchDarklyClient, close_ld_client
from libs.py_common.logging import setup_logging # Import setup_logging

# Prometheus metrics
from starlette_prometheus import PrometheusMiddleware, metrics as starlette_metrics # Corrected import
# from . import metrics # Your custom metrics, if you plan to expose them via the same endpoint manually or use them in routes

# Assuming db.py and models.py are in the same directory (services/offers)
from .db import get_session, init_db # init_db might be called on startup
from .models import OfferRead, OfferCreate, CreatorRead, CreatorCreate # Example models
# Import other specific models as needed for routes

import time # Added for middleware
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint # Added for middleware
from starlette.requests import Request # Added for middleware
from starlette.responses import Response # Added for middleware

app = FastAPI(
    title="Offers Service",
    description="API for managing creators and offers.",
    version="0.1.0"
)

# Add Prometheus middleware
app.add_middleware(PrometheusMiddleware)
# This will expose /metrics endpoint by default
# app.add_route("/metrics", starlette_metrics) # No longer needed if middleware adds it by default

logger = structlog.get_logger(__name__)

# Add Structlog Request Logging Middleware
class StructlogRequestLoggingMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        structlog.contextvars.clear_contextvars()
        # Optional: Bind initial request info to be available on all logs within this request context
        # structlog.contextvars.bind_contextvars(
        #     path=request.url.path,
        #     method=request.method,
        #     client_host=request.client.host,
        # )

        start_time = time.time()
        status_code = 500 # Default status code for unhandled exceptions

        try:
            response = await call_next(request)
            status_code = response.status_code
        except Exception as exc:
            # Log unhandled exceptions before they are re-raised or handled by FastAPI's default.
            logger.error(
                "unhandled_exception_during_request", 
                exc_info=True, 
                path=str(request.url.path),
                method=request.method,
                client_host=request.client.host
            )
            raise # Re-raise the exception to be handled by FastAPI or other exception handlers
        finally:
            process_time = time.time() - start_time
            
            # Prepare log event common to success and handled exceptions that might set a status code
            log_event = {
                "http": {
                    "request": {
                        "method": request.method,
                        "url": str(request.url),
                        "headers": {k:v for k,v in request.headers.items() if k.lower() not in ['authorization', 'cookie', 'x-api-key']} # Exclude sensitive headers
                    },
                    "response": {
                        "status_code": status_code,
                    }
                },
                "network": {"client": {"ip": request.client.host, "port": request.client.port}},
                "duration_ms": round(process_time * 1000, 2),
                "service": "offers", # Or use an environment variable/config for service name
                "path": str(request.url.path), # Explicitly log path for easier filtering
                "method": request.method      # Explicitly log method for easier filtering
            }
            logger.info("http_request_completed", **log_event)
        
        return response

app.add_middleware(StructlogRequestLoggingMiddleware)

@app.on_event("startup")
async def on_startup():
    setup_logging() # Call setup_logging early
    logger.info("offers_service_startup", service="offers", event="service_starting")
    # Initialize the database and tables if needed (idempotent)
    # Consider if this should be manual or handled by migrations more explicitly outside app startup.
    # await init_db() # Commented out as migrations are handled by docker-compose command
    LaunchDarklyClient.get_client() # Initialize LD client
    logger.info("offers_service_startup_complete", service="offers", event="service_started")

@app.on_event("shutdown")
async def shutdown_event():
    close_ld_client() # Close LD client
    # ... other shutdown logic ...

@app.get("/")
async def read_root():
    logger.info("root_accessed_offers", service="offers", request_id="dummy_request_id")
    return {"message": "Welcome to the Offers Service"}

# Placeholder for API routes. These would typically be in a routes.py file.
# Example:
# @app.post("/offers/", response_model=OfferRead)
# async def create_offer_route(offer: OfferCreate, session: AsyncSession = Depends(get_session)):
#     # db_offer = create_offer(session=session, offer=offer) # Your CRUD function
#     # return db_offer
#     pass

# @app.get("/creators/", response_model=List[CreatorRead])
# async def read_creators_route(session: AsyncSession = Depends(get_session)):
#     # creators = get_creators(session=session) # Your CRUD function
#     # return creators
#     pass

# To run this directly (though usually run by Uvicorn via Docker):
if __name__ == "__main__":
    import uvicorn
    # It's good practice to load .env file here if not using a system-wide env manager for local dev
    # from dotenv import load_dotenv
    # load_dotenv()
    uvicorn.run(app, host="0.0.0.0", port=8000, reload=True) 