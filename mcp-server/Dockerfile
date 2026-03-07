FROM python:3.11-slim

WORKDIR /app

# Install Python dependencies
COPY pyproject.toml .
RUN pip install --no-cache-dir -e ".[dev]"

# Copy source code
COPY src/ src/
COPY tests/ tests/

# Expose the SSE server port
EXPOSE 3000

# Default: run the MCP server in SSE mode
ENV MCP_TRANSPORT=sse
CMD ["python", "-m", "src.server"]
