# Production Dockerfile for INXR2
# Multi-stage build: Frontend -> Backend -> Final image

# Stage 1: Build frontend
FROM node:20-alpine AS frontend-builder

WORKDIR /build/frontend

# Copy frontend package files
COPY frontend/package*.json ./

# Install dependencies
RUN npm ci --only=production

# Copy frontend source
COPY frontend/ ./

# Build frontend for production
RUN npm run build

# Stage 2: Build backend
FROM python:3.14-slim AS backend-builder

WORKDIR /build

# Install build dependencies
RUN apt-get update && apt-get install -y \
    build-essential \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# Copy Python package files
COPY pyproject.toml ./
COPY src/ ./src/

# Install Python dependencies
RUN pip install --no-cache-dir --upgrade 'pip>=26.0' 'wheel>=0.46.2' && \
    pip install --no-cache-dir build && \
    pip install --no-cache-dir .

# Stage 3: Final production image
FROM python:3.14-slim

# Install runtime dependencies
RUN apt-get update && apt-get install -y \
    postgresql-client \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Create non-root user
RUN groupadd -r inxr2 && \
    useradd -r -g inxr2 -s /bin/bash inxr2

# Set working directory
WORKDIR /app

# Copy Python packages from builder
COPY --from=backend-builder /usr/local/lib/python3.11/site-packages /usr/local/lib/python3.11/site-packages
COPY --from=backend-builder /usr/local/bin /usr/local/bin

# Copy application source
COPY --chown=inxr2:inxr2 src/ ./src/

# Copy built frontend from frontend-builder
COPY --from=frontend-builder --chown=inxr2:inxr2 /build/frontend/dist ./frontend/dist

# Switch to non-root user
USER inxr2

# Expose port
EXPOSE 8000

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8000/api/health || exit 1

# Run the application
CMD ["inxr2", "serve", "--host", "0.0.0.0", "--port", "8000"]
