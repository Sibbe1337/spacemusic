# Stage 1: Build stage
FROM python:3.12-slim as builder

WORKDIR /app

# Install build dependencies if any (e.g., for compiling C extensions)
# RUN apt-get update && apt-get install -y --no-install-recommends build-essential libpq-dev

COPY requirements.txt .
# Ensure pip is upgraded and install dependencies
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# Copy application code (including model.pkl and rules.yaml)
COPY . .

# Stage 2: Final stage
FROM python:3.12-slim

WORKDIR /app

# Create a non-root user
RUN addgroup --system app && adduser --system --group app

# Copy installed dependencies from builder stage
COPY --from=builder /usr/local/lib/python3.12/site-packages /usr/local/lib/python3.12/site-packages
# Copy application code from builder stage (includes model.pkl, rules.yaml)
COPY --from=builder /app . 

USER app

# Command to run the Celery worker
# This assumes that celery_app is discoverable at services.valuation.worker.celery_app
CMD ["celery", "-A", "services.valuation.worker.celery_app", "worker", "-l", "INFO", "-Q", "valuation"] # Added specific queue 