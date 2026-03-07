---
name: qa-testing
description: "Exploratory UI testing via the QA Agent (Playwright container). Starts services, provides curl-based browser control commands, and guides testing workflow."
user-invocable: true
argument-hint: "[optional: URL path to start testing, e.g. '/browse/inxr2']"
---

# QA Testing Skill

Interactive UI testing using the **`inxr2-playwright`** container. Claude Code decides what to test and issues commands; the QA Agent executes browser actions via Playwright.

## Container Setup

- **`inxr2-dev`**: Development container (coding, tests, database)
- **`inxr2-playwright`**: Browser automation container (Playwright + Chromium)

⚠️ **NEVER install Playwright/Chromium in `inxr2-dev`** — use the dedicated QA container.

## Detect Container and Ports

```bash
if [ -f .env ]; then
  CONTAINER=$(grep COMPOSE_CONTAINER_PREFIX .env | cut -d= -f2)-dev
  QA_PORT=$(grep QA_PORT .env 2>/dev/null | cut -d= -f2 || echo 9222)
  FRONTEND_PORT=$(grep FRONTEND_PORT .env 2>/dev/null | cut -d= -f2 || echo 5173)
else
  CONTAINER=inxr2-dev
  QA_PORT=9222
  FRONTEND_PORT=5173
fi
```

## Prerequisites

1. Start backend if not running:
   ```bash
   docker exec -d $CONTAINER inxr2 serve --reload
   ```

2. Start frontend if not running:
   ```bash
   docker exec -d -w /workspace/frontend $CONTAINER npm run dev
   ```

3. Start QA agent:
   ```bash
   docker compose -f docker-compose.dev.yml --profile qa up -d playwright
   curl http://localhost:$QA_PORT/health  # verify
   ```

## Browser Control via curl

```bash
# Navigate to a page
curl "http://localhost:$QA_PORT/navigate?url=http://host.docker.internal:$FRONTEND_PORT/browse/inxr2"

# Click an element
curl "http://localhost:$QA_PORT/click?selector=span.symbol-name"

# Get text content
curl "http://localhost:$QA_PORT/text?selector=.references-panel"

# List matching elements
curl "http://localhost:$QA_PORT/elements?selector=a&limit=10"

# Take a screenshot
curl "http://localhost:$QA_PORT/screenshot/save?path=/tmp/screenshot.png"
```

**Note:** The QA agent's browser runs inside a container. Use `host.docker.internal` (not `localhost`) for URLs the browser navigates to.

## Testing Workflow

1. Ensure backend + frontend are running in `$CONTAINER`
2. Navigate to the page being tested
3. Use curl commands to interact and verify UI behavior
4. Keep a log of steps to reproduce any bugs found
5. Take screenshots of failures

If `$ARGUMENTS` is provided, navigate to that path first:
```bash
curl "http://localhost:$QA_PORT/navigate?url=http://host.docker.internal:$FRONTEND_PORT$ARGUMENTS"
```

See `qa-agent/README.md` for complete API documentation.
