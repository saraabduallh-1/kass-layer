"""Renders poster.html to poster.png (1240x1754 CSS px at 2x = 2480x3508, A-series portrait)."""
from pathlib import Path

from playwright.sync_api import sync_playwright

HERE = Path(__file__).resolve().parent
with sync_playwright() as p:
    b = p.chromium.launch(channel="msedge")
    pg = b.new_page(viewport={"width": 1240, "height": 1754}, device_scale_factor=2)
    pg.goto((HERE / "poster.html").as_uri())
    pg.evaluate("document.fonts.ready")
    pg.wait_for_timeout(300)
    pg.screenshot(path=str(HERE / "poster.png"))
    b.close()
print("saved", HERE / "poster.png")
