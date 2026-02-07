# INXR2 QA Agent

Exploratory testing agent for INXR2, powered by Claude and Playwright.

## Overview

This agent performs "manual" testing of the INXR2 UI by:
1. Using Playwright to interact with the web UI
2. Extracting what the UI displays (DOM-based, not screenshots)
3. Comparing against the actual git source using grep
4. Using Claude to verify correctness when simple comparison isn't enough

## Key Design Decisions

- **DOM over screenshots**: Cheaper API calls, faster verification
- **Exploratory focus**: Random sampling of functionality, not exhaustive
- **Cost-conscious**: Tracks API usage, uses Sonnet by default
- **Regression-ready**: Scenarios can become regression tests

## Scenarios

| Scenario | Description |
|----------|-------------|
| `file-navigation` | Browse to a file, verify content matches git |
| `symbol-lookup` | Click a symbol, verify references match grep |
| `search` | Search for text, verify results match grep |
| `diff-viewer` | (TODO) Compare versions, verify diff accuracy |

## Setup

### Prerequisites

- INXR2 running (backend + frontend)
- Docker
- `ANTHROPIC_API_KEY` environment variable

### Build

```bash
cd qa-agent
docker build -t inxr2-qa-agent .
```

### Run

```bash
# Check INXR2 is accessible
docker run --rm --network host inxr2-qa-agent check

# Run random exploration (5 tests)
docker run --rm --network host \
  -e ANTHROPIC_API_KEY \
  -v /path/to/test-repos:/repos/test-repos:ro \
  inxr2-qa-agent test --count 5

# Run specific scenario
docker run --rm --network host \
  -e ANTHROPIC_API_KEY \
  -v /path/to/test-repos:/repos/test-repos:ro \
  inxr2-qa-agent test --scenario file-navigation

# With visible browser (for debugging)
docker run --rm --network host \
  -e ANTHROPIC_API_KEY \
  -v /path/to/test-repos:/repos/test-repos:ro \
  inxr2-qa-agent test --no-headless --scenario symbol-lookup
```

## Cost Tracking

The agent tracks API usage and estimates costs:

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

```bash
# Install locally (for development)
cd qa-agent
pip install -e ".[dev]"
playwright install chromium

# Run tests
pytest
```

## Adding New Scenarios

1. Create `src/scenarios/your_scenario.py`
2. Implement `async def run(page, verifier, config) -> dict`
3. Register in `src/agent.py` scenarios dict
4. Add to `config.enabled_scenarios` for random exploration

## Limitations

- Requires INXR2 to be running
- Depends on specific DOM structure (may break on UI changes)
- Git repos must be accessible for verification
- API costs scale with test count
