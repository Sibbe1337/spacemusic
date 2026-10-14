# Stage 1: Build stage. Use the repository root as the Docker context.
FROM python:3.12-slim AS builder

WORKDIR /app

COPY services/event_consumer/requirements.txt .
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

COPY --from=builder /usr/local/lib/python3.12/site-packages /usr/local/lib/python3.12/site-packages
COPY --from=builder /app/libs ./libs
COPY --from=builder /app/services ./services
COPY --from=builder /app/schema ./schema

USER app

# Command to run the consumer script
# The consumer.py script itself has the main loop.
CMD ["python", "services/event_consumer/consumer.py"]
