"""Renders fusha_video.html frame by frame (Edge via Playwright), encodes it with ffmpeg and adds short sound effects.

  .venv/Scripts/python reports/presentation/video/render_fusha.py              → kass_fusha_video.mp4
  .venv/Scripts/python reports/presentation/video/render_fusha.py 12 30.5 ...  → preview PNGs at those seconds
The effect times mirror the scene starts (S in the page) and the offsets in each scene's update function.
"""
import subprocess
import sys
import wave
from pathlib import Path

import imageio_ffmpeg
import numpy as np
from playwright.sync_api import sync_playwright

HERE = Path(__file__).resolve().parent
# the synthesised effects of add_sfx.py (its definitions only: the rest of that file mixes the first video's track)
_src = (HERE / "add_sfx.py").read_text(encoding="utf-8")
_fx: dict = {"__file__": str(HERE / "add_sfx.py")}
exec(_src[:_src.index("track = np.zeros")], _fx)
chime, click, nope, pop, swish, tick = (_fx[k] for k in ("chime", "click", "nope", "pop", "swish", "tick"))

PAGE = (HERE / "fusha_video.html").as_uri()
OUT = HERE.parent / "kass_fusha_video.mp4"
FPS = 30
SR = 48000


def sound(dur: float) -> np.ndarray:
    track = np.zeros(int(SR * dur))

    def at(sec, snd):
        s = int(sec * SR)
        e = min(len(track), s + len(snd))
        if 0 <= s < len(track):
            track[s:e] += snd[:e - s]

    S = dict(s0=0, s1=5, s2=17, s3=31, s4=52, s5=73, s6=98, s7=110, s8=124, s9=133)
    for v in S.values():
        if v:
            at(v - .15, swish(.1))
    at(.3, pop(.3))
    for i in range(3):
        at(S["s1"] + .4 + i * 3, pop(.22))
    for i in range(4):
        at(S["s2"] + .4 + i * 2.8, pop(.2))
    for s in ("s3", "s4"):
        for a in (.3, 3.5, 8):
            at(S[s] + a, tick(1500, .14))
        for a in (.6, 3.8, 8.2):
            at(S[s] + a + .1, pop(.2))
        for i in range(5):
            at(S[s] + 11 + i * 1.6, tick(1800 + 100 * i, .12))
    at(S["s3"] + 8.4, nope(.12))
    for a in (.3, 3, 11.5, 18, 21):
        at(S["s5"] + a, tick(1500, .14))
    for a in (3.2, 6, 11.6):
        at(S["s5"] + a, pop(.2))
    at(S["s5"] + 9.6, nope(.12))
    for i in range(5):
        at(S["s5"] + 11.9 + i * 1.1, tick(2000, .1))
    at(S["s5"] + 18, chime(.18))
    for i in range(4):
        at(S["s6"] + .4 + i * 2.6, pop(.2))
    for i in range(8):
        at(S["s7"] + .3 + i * 1.5, tick(1400, .12))
    for a in (.3, 2, 3.6):
        at(S["s8"] + a, pop(.22))
    at(S["s8"] + .5, chime(.15))
    at(S["s9"] + .3, pop(.25))
    return track / max(1, np.abs(track).max() / .7)


with sync_playwright() as p:
    b = p.chromium.launch(channel="msedge")
    pg = b.new_page(viewport={"width": 1920, "height": 1080})
    pg.goto(PAGE)
    pg.evaluate("document.fonts.ready")
    if len(sys.argv) > 1:
        for s in sys.argv[1:]:
            pg.evaluate(f"render({float(s)})")
            pg.screenshot(path=str(HERE / f"fusha_{s}.png"))
        b.close()
        sys.exit()
    dur = pg.evaluate("window.DURATION")
    silent = HERE / "_fusha_video_only.mp4"
    ff = subprocess.Popen([imageio_ffmpeg.get_ffmpeg_exe(), "-y", "-loglevel", "error", "-f", "image2pipe", "-framerate", str(FPS),
                           "-i", "-", "-c:v", "libx264", "-pix_fmt", "yuv420p", "-crf", "18", "-preset", "medium", str(silent)],
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

wav = HERE / "_fusha_sfx.wav"
with wave.open(str(wav), "wb") as w:
    w.setnchannels(1); w.setsampwidth(2); w.setframerate(SR)
    w.writeframes((sound(dur) * 32767).astype(np.int16).tobytes())
subprocess.run([imageio_ffmpeg.get_ffmpeg_exe(), "-y", "-loglevel", "error", "-i", str(silent), "-i", str(wav), "-c:v", "copy", "-c:a", "aac",
                "-b:a", "160k", "-shortest", "-movflags", "+faststart", str(OUT)], check=True)
silent.unlink(); wav.unlink()
print("saved", OUT, f"{dur}s")
