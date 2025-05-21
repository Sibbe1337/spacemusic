# Stage 1: Build stage
FROM python:3.12-slim as builder

WORKDIR /app

# Install build dependencies if any (e.g., for compiling packages)
# RUN apt-get update && apt-get install -y --no-install-recommends build-essential

# Copy requirements and install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

# Stage 2: Final stage
FROM python:3.12-slim

WORKDIR /app

# Create a non-root user
RUN addgroup --system app && adduser --system --group app
USER app

# Copy installed dependencies from builder stage
COPY --from=builder /usr/local/lib/python3.12/site-packages /usr/local/lib/python3.12/site-packages
COPY --from=builder /app/requirements.txt .

# Copy application code
COPY . .

# Expose port (if applicable)
EXPOSE 8000

# Command to run the application
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"] 