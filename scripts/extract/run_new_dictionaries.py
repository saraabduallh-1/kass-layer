"""Background extraction of the nine terminology dictionaries left in SIWAR (Windows and Mac; no Claude, no model).

  .venv/Scripts/python scripts/extract/run_new_dictionaries.py            (start; safe to run again, it resumes)
  .venv/Scripts/python scripts/extract/extract_finance_media.py status legal_glossary theatre ...   (progress)
Log: logs/extract-new.log. Done when logs/extract-new.done exists.

Runs extract_finance_media.py for each dictionary in NEW_TERM_DICTIONARIES at the robots.txt pace (5 s between
requests) and restarts a run that exits early or stops saving progress for 10 minutes; saved batches are kept, so a
restart resumes from the last checkpoint. Takes about a day for ~17,400 entries.
"""
from __future__ import annotations

import json
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts" / "extract"))
from extract_finance_media import NEW_TERM_DICTIONARIES, TARGETS  # noqa: E402

LOG = ROOT / "logs" / "extract-new.log"
DONE = ROOT / "logs" / "extract-new.done"
STALL_SECONDS = 600
PY = sys.executable


def log(msg: str) -> None:
    LOG.parent.mkdir(exist_ok=True)
    with LOG.open("a", encoding="utf-8") as f:
        f.write(f"== {datetime.now():%Y-%m-%d %H:%M:%S} {msg}\n")


def progress_path(name: str) -> Path:
    return ROOT / "data" / "dictionaries" / "raw" / "siwar" / "by_dictionary" / TARGETS[name] / "progress.json"


def complete(name: str) -> bool:
    try:
        return json.loads(progress_path(name).read_text(encoding="utf-8")).get("status") == "complete"
    except (OSError, ValueError):
        return False


def run(name: str) -> None:
    while not complete(name):
        log(f"starting {name}")
        with LOG.open("a", encoding="utf-8") as out:
            proc = subprocess.Popen([PY, str(ROOT / "scripts" / "extract" / "extract_finance_media.py"), "extract", name,
                                     "--delay-seconds", "5", "--retries", "50"], cwd=ROOT, stdout=out, stderr=out,
                                    env={**__import__("os").environ, "PYTHONIOENCODING": "utf-8", "PYTHONUNBUFFERED": "1"})
        started = time.time()
        while proc.poll() is None:
            time.sleep(60)
            p = progress_path(name)
            last = max(p.stat().st_mtime if p.exists() else 0, started)  # an old checkpoint is not a stall of this run
            if time.time() - last > STALL_SECONDS and proc.poll() is None:
                log(f"no progress for {int(time.time() - last)}s; restarting {name}")
                proc.kill()
                proc.wait()
        if not complete(name):
            time.sleep(30)
    log(f"{name} complete")


if __name__ == "__main__":
    DONE.unlink(missing_ok=True)
    for n in NEW_TERM_DICTIONARIES:
        run(n)
    DONE.write_text(datetime.now().isoformat(), encoding="utf-8")
    log("all nine complete")
