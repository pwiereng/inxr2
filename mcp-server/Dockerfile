FROM python:3.11-slim

WORKDIR /app

# Copy source and install
COPY pyproject.toml .
COPY src/ src/
RUN pip install --no-cache-dir .

# Expose the SSE server port
EXPOSE 3000

# Default: run the MCP server in SSE mode
ENV MCP_TRANSPORT=sse
CMD ["python", "-m", "src.server"]
