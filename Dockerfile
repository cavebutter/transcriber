# Multi-stage build for RealRecap webapp
FROM nvidia/cuda:12.1-runtime-ubuntu22.04 AS base

# Install system dependencies
RUN apt-get update && apt-get install -y \
    python3 \
    python3-pip \
    python3-dev \
    ffmpeg \
    pandoc \
    texlive-xetex \
    texlive-fonts-recommended \
    texlive-plain-generic \
    git \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Set Python environment
ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1

# Create app user
RUN useradd --create-home --shell /bin/bash app

# Dependencies stage
FROM base AS dependencies

# Set working directory
WORKDIR /app

# Copy requirements first for better Docker layer caching
COPY requirements-webapp.txt .

# Install Python dependencies
RUN pip3 install --no-cache-dir --upgrade pip && \
    pip3 install --no-cache-dir -r requirements-webapp.txt

# Runtime stage
FROM dependencies AS runtime

# Set working directory
WORKDIR /app

# Create necessary directories
RUN mkdir -p uploads templates static logs && \
    chown -R app:app /app

# Copy application code
COPY --chown=app:app . .

# Set up environment variables
ENV FLASK_APP=run.py
ENV FLASK_ENV=production
ENV PYTHONPATH=/app

# Switch to app user
USER app

# Expose ports
EXPOSE 5000

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:5000/api/system/health || exit 1

# Default command
CMD ["gunicorn", "--bind", "0.0.0.0:5000", "--workers", "4", "--timeout", "300", "run:app"]