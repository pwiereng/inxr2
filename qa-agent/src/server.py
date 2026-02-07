"""
Simple Playwright HTTP server for interactive testing.

Provides endpoints that Claude can call via curl to interact with the browser.
Keeps a browser session alive between requests.
"""

import asyncio
import base64
import json
from contextlib import asynccontextmanager

from fastapi import FastAPI, Query
from fastapi.responses import JSONResponse
from playwright.async_api import Browser, Page, Playwright, async_playwright

# Global state
playwright: Playwright | None = None
browser: Browser | None = None
page: Page | None = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Manage browser lifecycle."""
    global playwright, browser, page

    print("Starting Playwright browser...")
    playwright = await async_playwright().start()
    browser = await playwright.chromium.launch(
        headless=True,
        args=[
            "--disable-web-security",
            "--disable-features=IsolateOrigins,site-per-process",
            "--ignore-certificate-errors",
        ],
    )
    page = await browser.new_page()
    page.set_default_timeout(15000)
    print("Browser ready!")

    yield

    print("Shutting down browser...")
    if browser:
        await browser.close()
    if playwright:
        await playwright.stop()


app = FastAPI(title="Playwright Tool Server", lifespan=lifespan)


@app.get("/health")
async def health():
    """Health check."""
    return {"status": "ok", "browser": browser is not None}


@app.get("/navigate")
async def navigate(url: str = Query(..., description="URL to navigate to")):
    """Navigate to a URL."""
    try:
        await page.goto(url)
        await page.wait_for_load_state("networkidle")
        return {
            "success": True,
            "url": page.url,
            "title": await page.title(),
        }
    except Exception as e:
        return JSONResponse({"success": False, "error": str(e)}, status_code=500)


@app.get("/click")
async def click(selector: str = Query(..., description="CSS selector to click")):
    """Click an element."""
    try:
        await page.click(selector)
        await page.wait_for_load_state("networkidle")
        return {"success": True, "clicked": selector}
    except Exception as e:
        return JSONResponse({"success": False, "error": str(e)}, status_code=500)


@app.get("/text")
async def get_text(selector: str = Query(..., description="CSS selector")):
    """Get text content of an element."""
    try:
        element = await page.query_selector(selector)
        if not element:
            return {"success": False, "error": f"Element not found: {selector}"}
        text = await element.inner_text()
        return {"success": True, "text": text}
    except Exception as e:
        return JSONResponse({"success": False, "error": str(e)}, status_code=500)


@app.get("/html")
async def get_html(selector: str = Query(..., description="CSS selector")):
    """Get HTML of an element."""
    try:
        element = await page.query_selector(selector)
        if not element:
            return {"success": False, "error": f"Element not found: {selector}"}
        html = await element.inner_html()
        return {"success": True, "html": html[:5000]}  # Limit size
    except Exception as e:
        return JSONResponse({"success": False, "error": str(e)}, status_code=500)


@app.get("/elements")
async def list_elements(
    selector: str = Query(..., description="CSS selector"),
    limit: int = Query(20, description="Max elements to return"),
):
    """List elements matching a selector."""
    try:
        elements = await page.query_selector_all(selector)
        results = []
        for el in elements[:limit]:
            text = await el.inner_text()
            tag = await el.evaluate("el => el.tagName.toLowerCase()")
            attrs = await el.evaluate(
                "el => Object.fromEntries([...el.attributes].map(a => [a.name, a.value]))"
            )
            results.append(
                {
                    "tag": tag,
                    "text": text[:200] if text else "",
                    "attributes": attrs,
                }
            )
        return {"success": True, "count": len(results), "elements": results}
    except Exception as e:
        return JSONResponse({"success": False, "error": str(e)}, status_code=500)


@app.get("/screenshot")
async def screenshot():
    """Take a screenshot, return as base64."""
    try:
        img_bytes = await page.screenshot()
        b64 = base64.b64encode(img_bytes).decode()
        return {"success": True, "image_base64": b64}
    except Exception as e:
        return JSONResponse({"success": False, "error": str(e)}, status_code=500)


@app.get("/screenshot/save")
async def screenshot_save(path: str = Query("/tmp/screenshot.png")):
    """Take a screenshot and save to file."""
    try:
        await page.screenshot(path=path)
        return {"success": True, "path": path}
    except Exception as e:
        return JSONResponse({"success": False, "error": str(e)}, status_code=500)


@app.get("/fill")
async def fill(
    selector: str = Query(..., description="CSS selector"),
    value: str = Query(..., description="Value to fill"),
):
    """Fill an input field."""
    try:
        await page.fill(selector, value)
        return {"success": True, "filled": selector, "value": value}
    except Exception as e:
        return JSONResponse({"success": False, "error": str(e)}, status_code=500)


@app.get("/keyboard")
async def keyboard(
    key: str = Query(..., description="Key to press (e.g., Enter, Tab)")
):
    """Press a keyboard key."""
    try:
        await page.keyboard.press(key)
        return {"success": True, "pressed": key}
    except Exception as e:
        return JSONResponse({"success": False, "error": str(e)}, status_code=500)


@app.get("/wait")
async def wait(
    selector: str = Query(..., description="CSS selector to wait for"),
    timeout: int = Query(10000, description="Timeout in ms"),
):
    """Wait for an element to appear."""
    try:
        await page.wait_for_selector(selector, timeout=timeout)
        return {"success": True, "found": selector}
    except Exception as e:
        return JSONResponse({"success": False, "error": str(e)}, status_code=500)


@app.get("/url")
async def get_url():
    """Get current page URL."""
    return {"success": True, "url": page.url}


@app.get("/eval")
async def evaluate(script: str = Query(..., description="JavaScript to evaluate")):
    """Evaluate JavaScript in the page context."""
    try:
        result = await page.evaluate(script)
        return {"success": True, "result": result}
    except Exception as e:
        return JSONResponse({"success": False, "error": str(e)}, status_code=500)


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=9222)
