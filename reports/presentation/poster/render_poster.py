"""Renders a poster page to PNG (1240x1754 CSS px at 2x = 2480x3508, A-series portrait).

  .venv/Scripts/python reports/presentation/poster/render_poster.py [poster|video_poster]
"""
import sys
from pathlib import Path

from playwright.sync_api import sync_playwright

HERE = Path(__file__).resolve().parent
name = sys.argv[1] if len(sys.argv) > 1 else "poster"
with sync_playwright() as p:
    b = p.chromium.launch(channel="msedge")
    pg = b.new_page(viewport={"width": 1240, "height": 1754}, device_scale_factor=2)
    pg.goto((HERE / f"{name}.html").as_uri())
    pg.evaluate("document.fonts.ready")
    pg.wait_for_timeout(300)
    pg.screenshot(path=str(HERE / f"{name}.png"))
    b.close()
print("saved", HERE / f"{name}.png")
