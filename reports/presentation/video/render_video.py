"""Renders kass_video.html frame by frame (Edge via Playwright) and encodes it with ffmpeg.

  .venv/Scripts/python reports/presentation/video/render_video.py               → kass_layer_video.mp4
  .venv/Scripts/python reports/presentation/video/render_video.py 12 30.5 ...   → preview PNGs at those seconds
"""
import subprocess
import sys
from pathlib import Path

import imageio_ffmpeg
from playwright.sync_api import sync_playwright

HERE = Path(__file__).resolve().parent
PAGE = (HERE / "kass_video.html").as_uri()
OUT = HERE.parent / "kass_layer_video.mp4"
FPS = 30

with sync_playwright() as p:
    b = p.chromium.launch(channel="msedge")
    pg = b.new_page(viewport={"width": 1920, "height": 1080})
    pg.goto(PAGE)
    pg.evaluate("document.fonts.ready")
    if len(sys.argv) > 1:
        for s in sys.argv[1:]:
            pg.evaluate(f"render({float(s)})")
            pg.screenshot(path=str(HERE / f"frame_{s}.png"))
        b.close()
        sys.exit()
    dur = pg.evaluate("window.DURATION")
    ff = subprocess.Popen([imageio_ffmpeg.get_ffmpeg_exe(), "-y", "-loglevel", "error", "-f", "image2pipe", "-framerate", str(FPS),
                           "-i", "-", "-c:v", "libx264", "-pix_fmt", "yuv420p", "-crf", "18", "-preset", "medium", "-movflags", "+faststart", str(OUT)],
                          stdin=subprocess.PIPE)
    n = int(dur * FPS)
    for i in range(n):
        pg.evaluate(f"render({i / FPS})")
        ff.stdin.write(pg.screenshot(type="png"))
        if i % 300 == 0:
            print(f"{i}/{n}", flush=True)
    ff.stdin.close()
    ff.wait()
    b.close()
    print("saved", OUT, f"{dur}s")
