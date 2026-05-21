"""Render a screenshot of the live dashboard to docs/dashboard.png.

Used to produce listing imagery for marketplaces / readme without
needing a human to open a browser.
"""
from __future__ import annotations

import asyncio
import os
import sys
from pathlib import Path

from playwright.async_api import async_playwright

URL = os.environ.get("ES_DASHBOARD_URL", "http://127.0.0.1:8765/")
OUT = Path(__file__).resolve().parent.parent / "docs" / "dashboard.png"


async def main() -> None:
    OUT.parent.mkdir(parents=True, exist_ok=True)
    async with async_playwright() as p:
        browser = await p.chromium.launch()
        context = await browser.new_context(viewport={"width": 1440, "height": 1800})
        page = await context.new_page()
        await page.goto(URL, wait_until="networkidle", timeout=20000)
        # Wait for actual data to populate — poll for the hypotheses card to render
        try:
            await page.wait_for_function(
                "document.querySelector('#hypotheses') && "
                "document.querySelector('#hypotheses').textContent.length > 50",
                timeout=15000,
            )
        except Exception:
            pass
        await asyncio.sleep(2)
        await page.screenshot(path=str(OUT), full_page=True)
        await browser.close()
    size_kb = OUT.stat().st_size // 1024
    print(f"wrote {OUT} ({size_kb} KB)")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except Exception as e:
        print(f"FAIL: {e}", file=sys.stderr)
        sys.exit(1)
