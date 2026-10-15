# MindScan Multimodal Clinical Backend Production Dockerfile
FROM python:3.10-slim

# Prevent Python from writing .pyc files and enable unbuffered output
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PORT=10000 \
    WEB_CONCURRENCY=1

# Install OS dependencies: FFmpeg for audio conversion, libpq-dev for PostgreSQL, curl for utilities
RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg \
    libpq-dev \
    gcc \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Create dedicated non-root application user for container security
RUN useradd -m -u 1000 appuser

WORKDIR /app

# 1. Install CPU-only PyTorch first (180MB instead of 3GB CUDA build) to keep image lightweight and fast
COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir torch torchvision --index-url https://download.pytorch.org/whl/cpu && \
    pip install --no-cache-dir -r requirements.txt

# 2. Copy backend application source code
COPY . .

# 3. Ensure startup script ownership and permissions
RUN chmod +x entrypoint.sh && \
    chown -R appuser:appuser /app

# Switch to unprivileged user
USER appuser

EXPOSE 10000

# Note: Health checks are performed natively by Render via healthCheckPath: /health
ENTRYPOINT ["/bin/sh", "entrypoint.sh"]
