# INXR2 QA Agent

Claude-driven browser automation for exploratory UI testing.

## Overview

This is a **headless browser container** that Claude Code controls via HTTP/curl commands. The workflow is:

1. **Claude Code** decides what to test and which actions to take
2. **QA Agent** (this container) executes browser actions via Playwright
3. **Claude Code** interprets results and continues testing

The agent is intentionally simple - just a browser automation server. All the intelligence comes from Claude Code, which issues curl commands like:

```bash
curl "http://localhost:9222/navigate?url=http://localhost:5173"
curl "http://localhost:9222/click?selector=span.symbol-name"
curl "http://localhost:9222/text?selector=.references-panel"
```

**No LLM API is used inside the QA agent** - Claude Code is already the LLM driving the testing session.

### Why a Separate Container?

- **Isolation**: Browser dependencies (Chromium, X11 libs) stay out of `inxr2-dev`
- **Specialization**: `inxr2-dev` is for development, `inxr2-playwright` is for UI testing
- **Cleanliness**: No Playwright installation polluting the dev environment

## Quick Start: Interactive Testing with Claude Code

The most common use case is exploratory testing during development.

### 1. Start the QA Agent

```bash
# From project root, start the playwright container
docker-compose -f docker-compose.dev.yml --profile qa up -d inxr2-playwright

# Verify it's running
curl http://localhost:9222/health
# {"status":"ok","browser":true}
```

**Note:** The playwright service uses a profile, so `--profile qa` is required.

### 2. Use curl to Control the Browser

The server exposes simple GET endpoints that Claude Code can call:

```bash
# Navigate to a page
curl "http://localhost:9222/navigate?url=http://localhost:5173/browse/inxr2"

# Click an element
curl "http://localhost:9222/click?selector=a[href*='symbol_kind']"

# Get text content
curl "http://localhost:9222/text?selector=.file-content"

# List elements matching a selector
curl "http://localhost:9222/elements?selector=span.symbol&limit=10"

# Take a screenshot
curl "http://localhost:9222/screenshot/save?path=/tmp/test.png"

# Evaluate JavaScript
curl "http://localhost:9222/eval?script=document.title"
```

### 3. Available Endpoints

| Endpoint | Parameters | Description |
|----------|------------|-------------|
| `GET /health` | - | Check server status |
| `GET /navigate` | `url` | Navigate to URL |
| `GET /click` | `selector` | Click element |
| `GET /text` | `selector` | Get element text |
| `GET /html` | `selector` | Get element HTML |
| `GET /elements` | `selector`, `limit` | List matching elements |
| `GET /fill` | `selector`, `value` | Fill input field |
| `GET /keyboard` | `key` | Press keyboard key |
| `GET /wait` | `selector`, `timeout` | Wait for element |
| `GET /screenshot` | - | Get screenshot as base64 |
| `GET /screenshot/save` | `path` | Save screenshot to file |
| `GET /url` | - | Get current URL |
| `GET /eval` | `script` | Evaluate JavaScript |

## Key Design Decisions

- **HTTP API**: Simple curl commands that Claude Code can call
- **DOM over screenshots**: Text-based verification is cheaper and faster than image analysis
- **Stateful session**: Browser stays open between requests for multi-step testing
- **Network host mode**: Container accesses localhost:5173 (frontend) and localhost:8000 (backend)
- **No LLM in the agent**: Claude Code is the intelligence - the agent is just browser automation

## Automated Scenarios (Legacy/Optional)

Pre-built scenarios exist for automated testing with Claude API verification. These are **optional** - the primary use case is Claude Code driving the browser interactively.

| Scenario | Description |
|----------|-------------|
| `file-navigation` | Browse to a file, verify content matches git |
| `symbol-lookup` | Click a symbol, verify references match grep |
| `search` | Search for text, verify results match grep |
| `diff-viewer` | (TODO) Compare versions, verify diff accuracy |

### Running Automated Scenarios

These require `ANTHROPIC_API_KEY` for Claude-based verification:

```bash
docker run --rm --network host \
  -e ANTHROPIC_API_KEY \
  -v /path/to/test-repos:/repos/test-repos:ro \
  inxr2-playwright test --scenario file-navigation
```

## Cost Tracking (Automated Scenarios)

When running automated scenarios with Claude verification, the agent tracks API usage:

```
Test Summary
  Total: 5
  Passed: 4
  Failed: 1
  API calls: 3
  Est. cost: $0.0042
```

Default model is `claude-sonnet-4-20250514` for cost efficiency.

## Development

The QA agent code lives in `/qa-agent/`. To modify it:

```bash
# Edit files in qa-agent/src/
# Then rebuild the container
docker-compose -f docker-compose.dev.yml build inxr2-playwright

# Restart to pick up changes
docker-compose -f docker-compose.dev.yml restart inxr2-playwright
```

For local development without Docker:

```bash
cd qa-agent
pip install -e ".[dev]"
playwright install chromium
pytest
```

## Adding New Scenarios

1. Create `src/scenarios/your_scenario.py`
2. Implement `async def run(page, verifier, config) -> dict`
3. Register in `src/agent.py` scenarios dict
4. Add to `config.enabled_scenarios` for random exploration

## Troubleshooting

### Connection refused to localhost:9222

The playwright container isn't running:
```bash
docker-compose -f docker-compose.dev.yml up -d inxr2-playwright
```

### Connection refused to localhost:5173

The frontend dev server isn't running. In `inxr2-dev`:
```bash
cd frontend && npm run dev
```

### URLs not working from inside container

The playwright container can't reach `localhost` on the host machine. Use `host.docker.internal` instead:
```bash
# Instead of localhost:5173, use:
curl "http://localhost:9222/navigate?url=http://host.docker.internal:5173/browse/inxr2"
```

### Element not found errors

The UI structure may have changed. Use `/elements` to explore:
```bash
curl "http://localhost:9222/elements?selector=*&limit=50"
```

## Limitations

- Requires INXR2 frontend and backend to be running
- Depends on specific DOM structure (may break on UI changes)
- Git repos must be accessible for verification (automated scenarios)
- API costs scale with test count (automated scenarios only)
