#!/usr/bin/env python3
"""
Interactive Playwright REPL for browser testing.

Run in Docker, then send commands via: docker exec -i <container> python src/repl.py
Commands are JSON, one per line. Responses are JSON.

Example:
  {"cmd": "goto", "url": "http://localhost:5173"}
  {"cmd": "text", "selector": "h1"}
  {"cmd": "click", "selector": "button"}
"""

import json
import sys

from playwright.sync_api import sync_playwright


def main():
    print(json.dumps({"status": "starting"}), flush=True)

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        page.set_default_timeout(15000)

        print(json.dumps({"status": "ready"}), flush=True)

        for line in sys.stdin:
            line = line.strip()
            if not line:
                continue

            try:
                cmd = json.loads(line)
                result = execute(page, cmd)
                print(json.dumps(result), flush=True)
            except json.JSONDecodeError as e:
                print(json.dumps({"error": f"Invalid JSON: {e}"}), flush=True)
            except Exception as e:
                print(json.dumps({"error": str(e)}), flush=True)


def execute(page, cmd: dict) -> dict:
    """Execute a command and return result."""
    action = cmd.get("cmd", "")

    if action == "goto":
        page.goto(cmd["url"])
        page.wait_for_load_state("networkidle")
        return {"ok": True, "url": page.url, "title": page.title()}

    elif action == "click":
        page.click(cmd["selector"])
        page.wait_for_timeout(500)  # Brief pause for UI update
        return {"ok": True}

    elif action == "text":
        el = page.query_selector(cmd["selector"])
        if not el:
            return {"ok": False, "error": "not found"}
        return {"ok": True, "text": el.inner_text()}

    elif action == "html":
        el = page.query_selector(cmd["selector"])
        if not el:
            return {"ok": False, "error": "not found"}
        html = el.inner_html()
        return {"ok": True, "html": html[:5000]}

    elif action == "elements":
        limit = cmd.get("limit", 20)
        els = page.query_selector_all(cmd["selector"])
        results = []
        for el in els[:limit]:
            text = el.inner_text()
            results.append(
                {
                    "text": text[:200] if text else "",
                    "tag": el.evaluate("el => el.tagName.toLowerCase()"),
                }
            )
        return {"ok": True, "count": len(results), "elements": results}

    elif action == "fill":
        page.fill(cmd["selector"], cmd["value"])
        return {"ok": True}

    elif action == "press":
        page.keyboard.press(cmd["key"])
        return {"ok": True}

    elif action == "wait":
        timeout = cmd.get("timeout", 10000)
        page.wait_for_selector(cmd["selector"], timeout=timeout)
        return {"ok": True}

    elif action == "screenshot":
        path = cmd.get("path", "/tmp/screenshot.png")
        page.screenshot(path=path)
        return {"ok": True, "path": path}

    elif action == "url":
        return {"ok": True, "url": page.url}

    elif action == "eval":
        result = page.evaluate(cmd["script"])
        return {"ok": True, "result": result}

    else:
        return {"error": f"Unknown command: {action}"}


if __name__ == "__main__":
    main()
