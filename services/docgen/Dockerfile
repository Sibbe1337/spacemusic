# Stage 1: Build stage - Install WeasyPrint dependencies and Python packages
FROM python:3.12-slim as builder

WORKDIR /app

# Install WeasyPrint system dependencies
# Based on https://weasyprint.readthedocs.io/en/stable/install.html#debian-ubuntu
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
    build-essential \
    python3-dev \
    python3-pip \
    python3-setuptools \
    python3-wheel \
    python3-cffi \
    libffi-dev \
    libxml2-dev \
    libxslt1-dev \
    zlib1g-dev \
    libpango-1.0-0 \
    libpangoft2-1.0-0 \
    libcairo2 \
    # libpangoocairo-1.0-0 # Usually pulled in by libpango-1.0-0 or libcairo2
    # For specific font support, you might need to install font packages, e.g., fonts-noto
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

COPY . .

# Stage 2: Final stage - Copy artifacts to a clean image
FROM python:3.12-slim

WORKDIR /app

# Copy WeasyPrint system dependencies from the builder stage
# This is tricky as system libs are spread out. It's often easier to install them directly.
# For WeasyPrint, it's usually better to install OS deps in the final stage directly if image size is not extremely critical,
# or use a base image that already has them (e.g., a Debian-based one with these libs).
# However, to try and keep it smaller, let's install them here again minimally.
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
    libffi8 \
    libxml2 \
    libxslt1.1 \
    zlib1g \
    libpango-1.0-0 \
    libpangoft2-1.0-0 \
    libcairo2 \
    # Ensure fonts are available. A minimal set might be needed.
    # fonts-liberation # Example minimal font set
    && rm -rf /var/lib/apt/lists/*

# Create a non-root user
RUN addgroup --system app && adduser --system --group app

# Copy installed Python dependencies from builder stage
COPY --from=builder /usr/local/lib/python3.12/site-packages /usr/local/lib/python3.12/site-packages
# Copy application code (including templates folder)
COPY --from=builder /app . 

USER app

# Command to run the Celery worker for docgen
CMD ["celery", "-A", "services.docgen.tasks.celery_app", "worker", "-l", "INFO", "-Q", "docgen"] # Specific queue for docgen 