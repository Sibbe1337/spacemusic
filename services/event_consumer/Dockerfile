# services/event_consumer/Dockerfile
# Stage 1: Build stage
FROM python:3.12-slim as builder

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

COPY . .

# Stage 2: Final stage
FROM python:3.12-slim

WORKDIR /app

# Create a non-root user
RUN addgroup --system app && adduser --system --group app

COPY --from=builder /usr/local/lib/python3.12/site-packages /usr/local/lib/python3.12/site-packages
COPY --from=builder /app .

USER app

# Command to run the consumer script
# The consumer.py script itself has the main loop.
CMD ["python", "consumer.py"] 