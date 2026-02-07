FROM python:3.11-slim

WORKDIR /app

# Install system dependencies for Playwright
RUN apt-get update && apt-get install -y \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies
COPY pyproject.toml .
RUN pip install --no-cache-dir -e .

# Install Playwright browsers
RUN playwright install chromium --with-deps

# Copy source code
COPY src/ src/

# Expose the server port
EXPOSE 9222

# Default: run the HTTP server
CMD ["python", "-m", "src.server"]
