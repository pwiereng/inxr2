FROM python:3.11-slim

WORKDIR /app

# Copy source and install runtime dependencies from the hash-pinned lock
# (reproducible), then the package itself without re-resolving.
# requirements-prod.lock is the runtime-only resolution (NO [dev] tooling)
# generated from mcp-server/pyproject.toml + the repo-root requirements-build.in,
# run from the repo root:
#   uv pip compile mcp-server/pyproject.toml requirements-build.in \
#       --generate-hashes -o mcp-server/requirements-prod.lock
# --no-build-isolation builds the wheel against the locked hatchling instead of
# fetching unpinned, unhashed build backends fresh from PyPI.
COPY pyproject.toml requirements-prod.lock ./
COPY src/ src/
RUN pip install --no-cache-dir --upgrade 'pip>=26.0' && \
    pip install --no-cache-dir --require-hashes -r requirements-prod.lock && \
    pip install --no-cache-dir --no-deps --no-build-isolation .

# Expose the SSE server port
EXPOSE 3000

# Default: run the MCP server in SSE mode
ENV MCP_TRANSPORT=sse
CMD ["python", "-m", "src.server"]
