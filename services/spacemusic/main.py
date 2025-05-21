from fastapi import FastAPI
import structlog

app = FastAPI()
logger = structlog.get_logger(__name__)

@app.on_event("startup")
async def startup_event():
    logger.info("spacemusic_service_startup", service="spacemusic", event="service_started")

@app.get("/")
async def read_root():
    logger.info("root_accessed", service="spacemusic", request_id="dummy_request_id") # Replace with actual request_id
    return {"message": "Welcome to SpaceMusic Service"}

# Further imports and routes would go into routes.py
# from . import routes
# app.include_router(routes.router)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000) 