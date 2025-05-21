from fastapi import FastAPI, Depends
import structlog # Assuming structlog is in requirements.txt
from sqlmodel import SQLModel # For potential route response models
from typing import List # For list responses
from libs.py_common.flags import LaunchDarklyClient, close_ld_client

# Prometheus metrics
from starlette_prometheus import PrometheusMiddleware, metrics as starlette_metrics # Corrected import
# from . import metrics # Your custom metrics, if you plan to expose them via the same endpoint manually or use them in routes

# Assuming db.py and models.py are in the same directory (services/offers)
from .db import get_session, init_db # init_db might be called on startup
from .models import OfferRead, OfferCreate, CreatorRead, CreatorCreate # Example models
# Import other specific models as needed for routes

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

@app.on_event("startup")
async def on_startup():
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