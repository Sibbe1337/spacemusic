# Stage 1: Build stage
FROM python:3.12-slim as builder

WORKDIR /app

# Install build dependencies if any (e.g., for psycopg2 if not using binary)
# RUN apt-get update && apt-get install -y --no-install-recommends build-essential libpq-dev

COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

COPY . .

# Stage 2: Final stage
FROM python:3.12-slim

WORKDIR /app

# Create a non-root user
RUN addgroup --system app && adduser --system --group app

# Copy installed Python dependencies from builder stage
COPY --from=builder /usr/local/lib/python3.12/site-packages /usr/local/lib/python3.12/site-packages
# Copy application code
COPY --from=builder /app .

USER app

# This Dockerfile can run either the Celery worker or the FastAPI app for internal routes.
# The CMD will be overridden in docker-compose.yml for each specific role (worker vs api).
# Default CMD could be the worker, or nothing, relying on docker-compose.
CMD ["sh", "-c", "echo 'Please specify a command for this image, e.g., Celery worker or FastAPI app via docker-compose.'"] 