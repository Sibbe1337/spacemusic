from fastapi import FastAPI
# ... other imports ...
from libs.py_common.flags import LaunchDarklyClient, close_ld_client

app = FastAPI()

@app.on_event("startup")
async def startup_event():
    # Initialize LaunchDarkly client
    LaunchDarklyClient.get_client()
    # ... other startup logic ...

@app.on_event("shutdown")
async def shutdown_event():
    # Close LaunchDarkly client
    close_ld_client()
    # ... other shutdown logic ...

# ... rest of the file ... 