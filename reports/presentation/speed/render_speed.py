"""Renders speed.html with the numbers in bench.json to speed.png (1920×1080).

  .venv/Scripts/python reports/presentation/speed/bench_speed.py reports/presentation/speed/bench.json   (measure)
  .venv/Scripts/python reports/presentation/speed/render_speed.py                                        (draw)
"""
from pathlib import Path

from playwright.sync_api import sync_playwright

HERE = Path(__file__).resolve().parent
data = (HERE / "bench.json").read_text(encoding="utf-8")

with sync_playwright() as p:
    b = p.chromium.launch(channel="msedge")
    pg = b.new_page(viewport={"width": 1920, "height": 1080})
    pg.add_init_script(f"window.DATA = {data};")
    pg.goto((HERE / "speed.html").as_uri())
    pg.evaluate("document.fonts.ready")
    pg.screenshot(path=str(HERE / "speed.png"))
    b.close()
print("saved", HERE / "speed.png")
