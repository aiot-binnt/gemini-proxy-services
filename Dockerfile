# Multi-stage build for optimized production image
FROM python:3.12-slim as builder

# Set working directory
WORKDIR /app

# Install build dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements first for better caching
COPY requirements.txt .

# Install dependencies
RUN pip install --no-cache-dir --user -r requirements.txt

# Production stage
FROM python:3.12-slim

# Set working directory
WORKDIR /app

# Install runtime dependencies (wget for healthcheck)
RUN apt-get update && apt-get install -y --no-install-recommends \
    wget \
    && rm -rf /var/lib/apt/lists/*

# Copy Python dependencies from builder
COPY --from=builder /root/.local /home/appuser/.local

# Create non-root user for security
RUN useradd -m -u 1000 appuser && \
    chown -R appuser:appuser /app && \
    chown -R appuser:appuser /home/appuser/.local

# Make sure scripts in .local are usable
ENV PATH=/home/appuser/.local/bin:$PATH

# Copy application files
COPY --chown=appuser:appuser app.py .
COPY --chown=appuser:appuser gemini_proxy_service.py .

# Switch to non-root user
USER appuser

# Expose port
EXPOSE 5001

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=40s --retries=3 \
    CMD wget --no-verbose --tries=1 --spider http://localhost:5001/health || exit 1

# Run application with optimized settings
# Using gevent worker class for better async performance
# Workers: 4 (recommended for production)
# Timeout: 60s for Gemini API calls
CMD ["gunicorn", "--bind", "0.0.0.0:5001", "--workers", "4", "--worker-class", "gevent", "--timeout", "60", "--log-level", "info", "--access-logfile", "-", "--error-logfile", "-", "app:app"]
