"""Adds short sound effects (no music, no background) to kass_layer_video.mp4, timed to the animation in kass_video.html.

  .venv/Scripts/python reports/presentation/video/add_sfx.py
The effects are synthesised here; the times mirror the scene starts (S) and the offsets in each scene's update function.
"""
import subprocess
import wave
from pathlib import Path

import imageio_ffmpeg
import numpy as np

HERE = Path(__file__).resolve().parent
VIDEO = HERE.parent / "kass_layer_video.mp4"
SR = 48000
DUR = 130
rng = np.random.default_rng(7)


def t_(d):
    return np.arange(int(SR * d)) / SR


def env(n, attack=0.002, decay=0.05):
    t = np.arange(n) / SR
    return np.minimum(1, t / attack) * np.exp(-t / decay)


def band(x, lo, hi):
    f = np.fft.rfftfreq(len(x), 1 / SR)
    X = np.fft.rfft(x)
    X[(f < lo) | (f > hi)] = 0
    return np.fft.irfft(X, len(x))


def click():
    n = int(SR * .03)
    return .5 * band(rng.standard_normal(n), 1500, 7000) * env(n, .0005, .004) + .35 * np.sin(2 * np.pi * 2400 * t_(.03)) * env(n, .0005, .008)


def key():
    n = int(SR * .02)
    return .14 * band(rng.standard_normal(n), 2000, 8000) * env(n, .0003, .003) * rng.uniform(.6, 1)


def tick(f=1700, a=.22):
    n = int(SR * .05)
    return a * np.sin(2 * np.pi * f * t_(.05)) * env(n, .0005, .01)


def pop(a=.35):
    t = t_(.09)
    f = np.linspace(380, 950, len(t))
    return a * np.sin(2 * np.pi * np.cumsum(f) / SR) * env(len(t), .002, .025)


def swish(a=.16, d=.32):
    n = int(SR * d)
    x = band(rng.standard_normal(n), 900, 5000)
    return a * x * np.hanning(n) / (np.abs(x).max() or 1) * 3


def chime(a=.22):
    out = np.zeros(int(SR * .45))
    for k, f in enumerate([880, 1318.5]):
        s, n = int(SR * .07 * k), int(SR * .38)
        tt = t_(.38)
        out[s:s + n] += a * (np.sin(2 * np.pi * f * tt) + .3 * np.sin(4 * np.pi * f * tt)) * env(n, .003, .12)
    return out


def nope(a=.2):
    out = np.zeros(int(SR * .3))
    for k, f in enumerate([330, 247]):
        s, n = int(SR * .09 * k), int(SR * .18)
        tt = t_(.18)
        out[s:s + n] += a * np.tanh(2 * np.sin(2 * np.pi * f * tt)) * env(n, .003, .06)
    return out


def strike(a=.22):
    n = int(SR * .22)
    x = band(rng.standard_normal(n), 1200, 6000)
    return a * x / np.abs(x).max() * np.linspace(.3, 1, n) * env(n, .01, .08)


def thud(a=.4):
    tt = t_(.16)
    return a * np.sin(2 * np.pi * np.linspace(140, 70, len(tt)).cumsum() / SR) * env(len(tt), .002, .05)


track = np.zeros(SR * DUR)


def at(sec, snd):
    s = int(sec * SR)
    e = min(len(track), s + len(snd))
    if 0 <= s < len(track):
        track[s:e] += snd[:e - s]


S = dict(s0=0, s1=4.5, s2=11, s3=20, s4=42, s5=54, s7=87, s8=99, s9=109, s10=125)
for k, v in S.items():  # a light swish as each scene comes in
    if v:
        at(v - .15, swish(.1))

# 0 title
at(.3, pop(.3)); at(.9, tick(1200, .15)); at(1.4, tick(1500, .12))
# 1 typing (one key per character, as render types it) and the domain click
SENT = "بنينا عميل ذكي يستخدم المودل والـ LLM لتحليل البيانات"
for i in range(len(SENT)):
    if SENT[i] != " ":
        at(S["s1"] + .5 + 3 * i / len(SENT), key())
at(S["s1"] + 4.2, click())
# 2 normalisation: arrow, then the dropped letters
for i, drops in enumerate([True, True, True, True]):
    a = S["s2"] + .4 + i * 1.9
    at(a, swish(.08, .2)); at(a + 1.0, pop(.25))
# 3 index lookup: bracket move, scanning ticks, hit or miss
HITS = [False, False, True, False, True, True, True]
for st, hit in enumerate(HITS):
    a = S["s3"] + .3 + st * 2.9
    at(a, tick(1300, .16))
    for j in range(8):
        at(a + .5 + j / 14, tick(2600, .05))
    at(a + 1.1, chime() if hit else nope(.13))
# 4 found terms drop into the dictionaries
for i in range(4):
    at(S["s4"] + 1.8 + i * 1.0 + .85, pop(.3))
at(S["s4"] + .1, click())
# 5 context gate, twice
for base, n_lean, n_vec, ok in [(S["s5"], 9, 6, True), (S["s5"] + 18, 3, 3, False)]:
    for i in range(n_lean):
        at(base + .8 + i * .25, tick(1100 + 60 * i, .1))
    at(base + 4.5, swish(.12, .25))
    for i in range(n_vec):
        at(base + 5.5 + i * .35, tick(1900, .08))
    at(base + 8.5, swish(.14, .3))
    at(base + 11, chime() if ok else nope(.17))
# 6 filters: card in, strike, stamp
for i in range(3):
    a = S["s7"] + .3 + i * 3.4
    at(a, swish(.1, .25)); at(a + 1.2, strike()); at(a + 1.6, thud(.3))
# 7 ranking: bars, reorder, the winner, the criteria
for i in range(3):
    at(S["s8"] + 1 + i * .3, tick(1400, .1))
for i in range(4):
    at(S["s8"] + 1.2 + i * .7, pop(.18))
at(S["s8"] + 5.5, swish(.12, .3)); at(S["s8"] + 6.3, chime(.18))
# 8 result: tiers, the click on the word, the popup, the click on the button, the replacements
for i in range(3):
    at(S["s9"] + 2 + i * .6, pop(.22))
at(S["s9"] + 7.8, click()); at(S["s9"] + 8, pop(.2)); at(S["s9"] + 11, click()); at(S["s9"] + 11.25, chime(.18))
at(S["s9"] + 13.5, tick(1600, .14))
# 9 end
at(S["s10"] + .3, pop(.25))

track /= max(1, np.abs(track).max() / .7)
wav = HERE / "sfx.wav"
with wave.open(str(wav), "wb") as w:
    w.setnchannels(1); w.setsampwidth(2); w.setframerate(SR)
    w.writeframes((track * 32767).astype(np.int16).tobytes())
silent = HERE / "_video_only.mp4"
ff = imageio_ffmpeg.get_ffmpeg_exe()
subprocess.run([ff, "-y", "-loglevel", "error", "-i", str(VIDEO), "-an", "-c:v", "copy", str(silent)], check=True)
subprocess.run([ff, "-y", "-loglevel", "error", "-i", str(silent), "-i", str(wav), "-c:v", "copy", "-c:a", "aac", "-b:a", "160k",
                "-shortest", "-movflags", "+faststart", str(VIDEO)], check=True)
silent.unlink(); wav.unlink()
print("saved", VIDEO)
