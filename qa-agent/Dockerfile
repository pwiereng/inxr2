FROM python:3.11-slim

WORKDIR /app

# Install system dependencies for Playwright.
# libatomic1: the Node driver bundled with recent playwright releases links
# against libatomic.so.1, which python:3.11-slim does not ship.
RUN apt-get update && apt-get install -y \
    curl \
    libatomic1 \
    && rm -rf /var/lib/apt/lists/*

# Install runtime dependencies from the hash-pinned lock (reproducible: the
# playwright pin also fixes which Chromium build `playwright install` fetches).
# requirements.lock is generated from qa-agent/pyproject.toml + the repo-root
# requirements-build.in (same convention as mcp-server/requirements-prod.lock),
# run from the repo root with the uv version pinned in CI's `lockfiles` job:
#   uv pip compile qa-agent/pyproject.toml requirements-build.in \
#       --generate-hashes -o qa-agent/requirements.lock
COPY pyproject.toml requirements.lock ./
RUN pip install --no-cache-dir --upgrade 'pip>=26.0' && \
    pip install --no-cache-dir --require-hashes -r requirements.lock

# Install Playwright browsers (before copying src/ so source edits don't
# invalidate this slow layer).
RUN playwright install chromium --with-deps

# Copy source code, then install the package itself without re-resolving.
# --no-build-isolation builds against the locked hatchling instead of fetching
# unpinned, unhashed build backends fresh from PyPI.
COPY src/ src/
RUN pip install --no-cache-dir --no-deps --no-build-isolation .

# Expose the server port
EXPOSE 9222

# Default: run the HTTP server
CMD ["python", "-m", "src.server"]
