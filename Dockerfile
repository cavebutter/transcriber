# Alternative Dockerfile using Ubuntu base instead of CUDA base
FROM ubuntu:22.04 AS base

# Avoid interactive prompts during build
ENV DEBIAN_FRONTEND=noninteractive
ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1

# Install system dependencies including CUDA support
RUN apt-get update && apt-get install -y \
    python3 \
    python3-pip \
    python3-venv \
    ffmpeg \
    pandoc \
    texlive-xetex \
    texlive-fonts-recommended \
    texlive-latex-extra \
    curl \
    wget \
    git \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Create non-root user for security
RUN useradd --create-home --shell /bin/bash appuser

# Stage 2: Python dependencies
FROM base AS dependencies

# Copy requirements file
COPY requirements-webapp.txt /tmp/requirements-webapp.txt

# Create virtual environment and install Python packages
RUN python3 -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

# Upgrade pip and install dependencies
RUN pip install --upgrade pip setuptools wheel && \
    pip install --no-cache-dir -r /tmp/requirements-webapp.txt

# Stage 3: Application runtime
FROM base AS runtime

# Copy virtual environment from dependencies stage
COPY --from=dependencies /opt/venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

# Set working directory
WORKDIR /app

# Copy application code
COPY . /app/

# Create necessary directories
RUN mkdir -p /app/uploads /app/logs /app/templates && \
    chown -R appuser:appuser /app

# Switch to non-root user
USER appuser

# Set environment variables
ENV FLASK_APP=run.py
ENV PYTHONPATH=/app
ENV UPLOAD_FOLDER=/app/uploads

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=60s --retries=3 \
    CMD python -c "import requests; requests.get('http://localhost:5000/api/system/health', timeout=5).raise_for_status()" || exit 1

# Expose port
EXPOSE 5000

# Default command (can be overridden by docker-compose)
CMD ["python", "run.py"]