# libs/py_common/celery_config.py
import os
from celery import Celery

# Default Redis broker URL, can be overridden by environment variable
# Ensure this matches your docker-compose.yml or deployed Redis service
CELERY_BROKER_URL = os.getenv("CELERY_BROKER_URL", "redis://localhost:6379/0")
CELERY_RESULT_BACKEND_URL = os.getenv("CELERY_RESULT_BACKEND_URL", "redis://localhost:6379/0")

def create_celery_app(app_name: str) -> Celery:
    """Creates and configures a Celery application instance."""
    app = Celery(
        app_name,
        broker=CELERY_BROKER_URL,
        backend=CELERY_RESULT_BACKEND_URL,
        include=[]  # Tasks will be auto-discovered or explicitly included by services
    )

    # Optional Celery configuration
    app.conf.update(
        task_serializer='json',
        accept_content=['json'],  # Ignore other content
        result_serializer='json',
        timezone='UTC',
        enable_utc=True,
        # Add other common Celery settings here
        # task_acks_late = True, # Example: for tasks that must complete
        # worker_prefetch_multiplier = 1, # Example: for long running tasks
    )
    return app

# print(f"Celery config loaded. Broker: {CELERY_BROKER_URL}, Backend: {CELERY_RESULT_BACKEND_URL}") 