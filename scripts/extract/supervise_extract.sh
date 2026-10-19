#!/bin/zsh
# Keep one dictionary extraction alive: restart it when it exits early or stops saving progress.
#
# Usage: scripts/extract/supervise_extract.sh NAME [STALL_SECONDS]
#   NAME is a target key in extract_finance_media.py (aerospace, legal, ...).
#   A run whose progress.json has not changed for STALL_SECONDS (default 600) is killed and restarted;
#   saved batches are kept, so the restart resumes from the last checkpoint.
set -u
cd "$(dirname "$0")/../.."
name=$1
stall=${2:-600}
dictionary_id=$(python3 -c "import sys; sys.path.insert(0, 'scripts/extract'); from extract_finance_media import TARGETS; print(TARGETS['$name'])" 2>/dev/null)
[[ -n $dictionary_id ]] || { echo "unknown dictionary: $name"; exit 1; }
progress=data/dictionaries/raw/siwar/by_dictionary/$dictionary_id/progress.json

is_complete() {
  python3 -c "import json,sys; sys.exit(json.load(open('$progress')).get('status') != 'complete')" 2>/dev/null
}

until is_complete; do
  echo "== $(date '+%F %T') starting $name"
  python3 scripts/extract/extract_finance_media.py extract "$name" --delay-seconds 5 --retries 50 &
  pid=$!
  started=$(date +%s)
  while kill -0 $pid 2>/dev/null; do
    /bin/sleep 60
    last=$(stat -f %m "$progress")
    (( last < started )) && last=$started  # an old checkpoint is not a stall of this run
    age=$(( $(date +%s) - last ))
    if (( age > stall )) && kill -0 $pid 2>/dev/null; then
      echo "== $(date '+%F %T') no progress for ${age}s; restarting $name"
      kill -TERM $pid; /bin/sleep 5; kill -KILL $pid 2>/dev/null
    fi
  done
  wait $pid 2>/dev/null
  is_complete || /bin/sleep 30
done
echo "== $(date '+%F %T') $name complete"
