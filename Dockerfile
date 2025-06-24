FROM python:3.11-slim

# Set environment variables
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    gcc \
    curl \
    && rm -rf /var/lib/apt/lists/* \
    && apt-get clean

# Copy requirements first for better caching
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Create directories for logs and data
RUN mkdir -p /app/logs /app/data

# Copy application code
COPY . .

# Copy environment configuration
COPY .env.example .env

# Create non-root user and set permissions
RUN useradd --create-home --shell /bin/bash --uid 1000 app \
    && chown -R app:app /app \
    && chmod +x /app/scripts/*.sh 2>/dev/null || true \
    && chmod +x /app/deploy/*.sh 2>/dev/null || true

USER app

# Expose ports (API and Flower monitoring)
EXPOSE 8000 5555

# Health check
HEALTHCHECK --interval=30s --timeout=30s --start-period=10s --retries=3 \
    CMD curl -f http://localhost:8000/health/ || exit 1

# Default command
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--reload"]