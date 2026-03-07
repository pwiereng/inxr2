FROM python:3.11-slim

WORKDIR /app

# Install Python dependencies
COPY pyproject.toml .
RUN pip install --no-cache-dir -e .

# Copy source code
COPY src/ src/

# Expose the SSE server port
EXPOSE 3000

# Default: run the MCP server in SSE mode
ENV MCP_TRANSPORT=sse
CMD ["python", "-m", "src.server"]
