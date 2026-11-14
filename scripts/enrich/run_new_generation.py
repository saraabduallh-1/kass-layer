"""Stage 1 of enrichment for the 9 dictionaries extracted on 2026-11-13: Gemma (Ollama, settings in .env) proposes
variants for every sense not generated yet. Resumable: rerun to continue. Log: logs/enrich-new.log,
logs/enrich-new.done at the end. Stage 2 (Claude review) is scripts/enrich/session_review.py.

  .venv\\Scripts\\python scripts\\enrich\\run_new_generation.py
"""
import os
import subprocess
import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts" / "extract"))
from extract_finance_media import NEW_TERM_DICTIONARIES, TARGETS  # noqa: E402

LOG = ROOT / "logs" / "enrich-new.log"
DONE = ROOT / "logs" / "enrich-new.done"


def log(line: str) -> None:
    with LOG.open("a", encoding="utf-8") as f:
        f.write(line + "\n")


def main() -> None:
    LOG.parent.mkdir(exist_ok=True)
    DONE.unlink(missing_ok=True)
    env = dict(os.environ, PYTHONIOENCODING="utf-8", PYTHONUNBUFFERED="1")
    for name in NEW_TERM_DICTIONARIES:
        for attempt in range(3):  # senses missing from a reply stay pending; a rerun retries them
            log(f"== {datetime.now():%Y-%m-%d %H:%M:%S} {name} attempt {attempt + 1}")
            with LOG.open("a", encoding="utf-8") as out:
                code = subprocess.call([sys.executable, str(ROOT / "scripts/enrich/enrich_dictionaries.py"), "generate",
                                        "--dictionary", TARGETS[name], "--workers", "2"],
                                       cwd=ROOT, env=env, stdout=out, stderr=subprocess.STDOUT)
            if code == 0:
                break
    log(f"== {datetime.now():%Y-%m-%d %H:%M:%S} generation finished for all nine")
    DONE.write_text("done\n", encoding="utf-8")


if __name__ == "__main__":
    main()
