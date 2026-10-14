# Stage 1: Build stage. Use the repository root as the Docker context.
FROM python:3.12-slim AS builder

WORKDIR /app

# Install build dependencies if any (e.g., for psycopg2 if not using binary)
# RUN apt-get update && apt-get install -y --no-install-recommends build-essential libpq-dev

COPY services/payouts/requirements.txt .
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

COPY libs ./libs
COPY services ./services
COPY schema ./schema

# Stage 2: Final stage
FROM python:3.12-slim

WORKDIR /app

# Create a non-root user
RUN addgroup --system app && adduser --system --group app

# Copy installed Python dependencies from builder stage
COPY --from=builder /usr/local/lib/python3.12/site-packages /usr/local/lib/python3.12/site-packages
# Copy application code
COPY --from=builder /app/libs ./libs
COPY --from=builder /app/services ./services
COPY --from=builder /app/schema ./schema

USER app

# This Dockerfile can run either the Celery worker or the FastAPI app for internal routes.
# The CMD will be overridden in docker-compose.yml for each specific role (worker vs api).
# Default CMD could be the worker, or nothing, relying on docker-compose.
CMD ["celery", "-A", "services.payouts.worker.celery_app", "worker", "-l", "INFO", "-Q", "payouts"]
